"""Account-tool invariants with mocked transports/registrar, never live signup.

The small persistence module and three registrar functions are loaded in isolated
namespaces so these checks need only stdlib, even without the browser packages.
This is implementation verification, not user-facing POV acceptance.
"""
from __future__ import annotations
import ast
import asyncio
import fcntl
import importlib.util
import json
import multiprocessing
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import account_tools as accounts

ROOT = Path(__file__).resolve().parent
KEY = 'fixture-account-credential-0123456789'


def isolated_runtime():
    spec = importlib.util.spec_from_file_location('_account_env_fixture', ROOT / 'runtime_env.py')
    module = importlib.util.module_from_spec(spec)
    dotenv = types.ModuleType('dotenv')
    dotenv.load_dotenv = Mock()
    with patch.dict('sys.modules', {'dotenv': dotenv}):
        spec.loader.exec_module(module)
    return module


def registrar_function(name, namespace):
    tree = ast.parse((ROOT / 'autonomous_registration.py').read_text())
    node = next(item for item in tree.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / 'autonomous_registration.py'), 'exec'), namespace)
    return namespace[name]


def child_locked(directory, output):
    result = asyncio.run(accounts.register_developer_account({'provider': 'steel'}, data_dir=Path(directory),
        environ={'STEEL_API_KEY': KEY}, verifier=AsyncMock(return_value=True)))
    output.put(result['status'])


class AccountToolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / 'data'
        self.env = {}
        self.verify = AsyncMock(return_value=True)
        self.agent = types.SimpleNamespace(run=AsyncMock(return_value={'status': 'email_verification_required'}))
        self.factory = Mock(return_value=self.agent)
        for name in ('socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('Network forbidden in account tests'))
            guard.start()
            self.addCleanup(guard.stop)

    async def register(self, provider='firecrawl'):
        return await accounts.register_developer_account({'provider': provider}, data_dir=self.data,
            environ=self.env, verifier=self.verify, registrar_factory=self.factory)

    def state(self, provider='firecrawl'):
        return json.loads((self.data / 'accounts' / f'{provider}.json').read_text())

    async def test_existing_key_is_verified_without_registration(self):
        self.env['FIRECRAWL_API_KEY'] = KEY
        result = await self.register()
        self.assertEqual(result['status'], 'verified_existing')
        self.assertTrue(result['credential_verified'])
        self.assertFalse(result['registration_attempted'])
        self.verify.assert_awaited_once_with('firecrawl', KEY)
        self.factory.assert_not_called()
        self.assertNotIn(KEY, json.dumps(result))
        self.assertNotIn(KEY, json.dumps(self.state()))

    async def test_invalid_existing_key_never_creates_replacement_account(self):
        self.env['FIRECRAWL_API_KEY'] = KEY
        self.verify.return_value = False
        result = await self.register()
        self.assertEqual(result['status'], 'verification_failed')
        self.assertFalse(result['credential_verified'])
        self.factory.assert_not_called()

    async def test_verifier_exception_is_redacted_and_not_success(self):
        self.env['FIRECRAWL_API_KEY'] = KEY
        self.verify.side_effect = RuntimeError('Authorization: Bearer ' + KEY)
        result = await self.register()
        self.assertEqual(result['checks'][0]['status'], 'error')
        self.assertFalse(result['credential_verified'])
        self.assertNotIn(KEY, json.dumps(result))
        self.factory.assert_not_called()

    async def test_verifier_must_return_literal_true(self):
        self.env['FIRECRAWL_API_KEY'] = KEY
        self.verify.return_value = {'status': 'success'}
        self.assertFalse((await self.register())['credential_verified'])

    async def test_new_credential_requires_separate_native_verification(self):
        async def run(provider, *, bootstrap):
            state = self.state()
            self.assertEqual(state['status'], 'in_progress')
            self.assertTrue(state['registration_claimed'])
            self.assertFalse(bootstrap)
            self.env['FIRECRAWL_API_KEY'] = KEY
            return {'status': 'key_persisted', 'key': KEY, 'last_observation': 'private page', 'mail': 'private mail'}
        self.agent.run.side_effect = run
        result = await self.register()
        self.assertEqual(result['status'], 'verified_new')
        self.assertTrue(result['credential_verified'])
        self.verify.assert_awaited_once_with('firecrawl', KEY)
        for private in (KEY, 'private page', 'private mail'):
            self.assertNotIn(private, json.dumps(result))
            self.assertNotIn(private, json.dumps(self.state()))
        self.assertEqual(os.stat(self.data / 'accounts/firecrawl.json').st_mode & 0o777, 0o600)
        again = await self.register()
        self.assertEqual(again['status'], 'verified_existing')
        self.assertEqual(self.agent.run.await_count, 1)

    async def test_registrar_claim_without_credential_cannot_succeed(self):
        self.agent.run.return_value = {'status': 'verified_new', 'credential_verified': True, 'reason': KEY}
        result = await self.register()
        self.assertEqual(result['status'], 'verification_required')
        self.assertFalse(result['credential_verified'])
        self.verify.assert_not_called()
        await self.register()
        self.assertEqual(self.agent.run.await_count, 1)

    async def test_cloud_bootstrap_only_for_cloud_account_provider(self):
        await self.register('steel')
        self.agent.run.assert_awaited_once_with('steel', bootstrap=True)

    async def test_existing_cloud_backend_disables_bootstrap(self):
        self.env['HYPERBROWSER_API_KEY'] = KEY
        await self.register('steel')
        self.agent.run.assert_awaited_once_with('steel', bootstrap=False)

    async def test_pending_legacy_registration_does_not_open_browser(self):
        path = self.data / 'autonomous/firecrawl.checkpoint.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'result': {'status': 'email_verification_required', 'last_observation': KEY}}))
        result = await self.register()
        self.assertEqual(result['status'], 'email_verification_required')
        self.factory.assert_not_called()
        self.assertNotIn(KEY, json.dumps(result))
        self.assertEqual((await self.register())['status'], 'email_verification_required')

    async def test_malformed_or_interrupted_legacy_checkpoint_blocks_replay(self):
        path = self.data / 'autonomous/firecrawl.checkpoint.json'
        path.parent.mkdir(parents=True)
        for payload in ('not json', '{"status":"executing"}', '{"result":{"status":[]}}'):
            path.write_text(payload)
            result = await self.register()
            self.assertEqual(result['status'], 'verification_required')
        self.factory.assert_not_called()

    async def test_existing_key_can_resolve_pending_registration(self):
        self.data.joinpath('accounts').mkdir(parents=True)
        accounts._write(self.data / 'accounts/firecrawl.json', {'registration_claimed': True, 'status': 'in_progress'})
        self.env['FIRECRAWL_API_KEY'] = KEY
        result = await self.register()
        self.assertEqual(result['status'], 'verified_existing')
        self.factory.assert_not_called()

    async def test_cancellation_preserves_no_replay_claim(self):
        self.agent.run.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await self.register()
        self.assertEqual(self.state()['status'], 'verification_required')
        self.agent.run.side_effect = None
        result = await self.register()
        self.assertEqual(result['status'], 'verification_required')
        self.assertEqual(self.agent.run.await_count, 1)

    async def test_crash_intent_blocks_new_process_attempt(self):
        self.data.joinpath('accounts').mkdir(parents=True)
        accounts._write(self.data / 'accounts/firecrawl.json', {'registration_claimed': True, 'status': 'in_progress'})
        result = await self.register()
        self.assertEqual(result['status'], 'verification_required')
        self.factory.assert_not_called()

    async def test_concurrent_calls_only_open_one_browser(self):
        started, finish = asyncio.Event(), asyncio.Event()
        async def run(provider, *, bootstrap):
            started.set()
            await finish.wait()
            return {'status': 'email_verification_required'}
        self.agent.run.side_effect = run
        first = asyncio.create_task(self.register())
        await asyncio.wait_for(started.wait(), 2)
        try:
            second = await self.register()
            self.assertEqual(second['status'], 'already_running')
            self.assertFalse(second['credential_verified'])
        finally:
            finish.set()
            await first
        self.assertEqual(self.agent.run.await_count, 1)

    async def test_lock_is_cross_process(self):
        directory = self.data / 'accounts'
        directory.mkdir(parents=True)
        with (directory / 'steel.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            ctx = multiprocessing.get_context('fork')
            output = ctx.Queue()
            process = ctx.Process(target=child_locked, args=(str(self.data), output))
            process.start()
            try:
                self.assertEqual(output.get(timeout=5), 'already_running')
                process.join(timeout=5)
                self.assertEqual(process.exitcode, 0)
            finally:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
                output.close()
                output.join_thread()

    async def test_safe_preflight_failure_can_retry_after_capability_is_ready(self):
        self.agent.run.return_value = {'status': 'cloud_credentials_unavailable'}
        result = await self.register()
        self.assertFalse(result['registration_attempted'])
        await self.register()
        self.assertEqual(self.agent.run.await_count, 2)

    async def test_unknown_provider_and_input_fields_are_rejected(self):
        for value in ({'provider': 'unknown'}, {'provider': []}, {'provider': 'steel', 'key': KEY}, [], None):
            with self.subTest(value=value), self.assertRaises(accounts.AccountError):
                await accounts.register_developer_account(value, data_dir=self.data, environ=self.env,
                    verifier=self.verify, registrar_factory=self.factory)
        self.factory.assert_not_called()
        self.verify.assert_not_called()

    async def test_catalog_is_offline_redacted_and_invalidates_changed_key(self):
        self.env['FIRECRAWL_API_KEY'] = KEY
        await self.register()
        self.verify.reset_mock()
        catalog = accounts.account_catalog(data_dir=self.data, environ=self.env)
        provider = next(item for item in catalog['providers'] if item['id'] == 'firecrawl')
        self.assertTrue(provider['credential_verified'])
        self.env['FIRECRAWL_API_KEY'] = KEY + '-changed'
        provider = next(item for item in accounts.account_catalog(data_dir=self.data, environ=self.env)['providers'] if item['id'] == 'firecrawl')
        self.assertEqual(provider['status'], 'configured_unverified')
        self.assertFalse(provider['credential_verified'])
        self.assertNotIn(KEY, json.dumps(catalog))
        self.verify.assert_not_called()

    async def test_devhunt_uses_website_profile_instead_of_api_verification(self):
        profile = AsyncMock(return_value={'status': 'browser_signin_required', 'reason': 'Official Google/GitHub website sign-in required.'})
        result = await accounts.register_developer_account({'provider': 'devhunt'}, data_dir=self.data,
            environ=self.env, verifier=self.verify, registrar_factory=self.factory, profile_runner=profile)
        self.assertEqual(result['status'], 'browser_signin_required')
        self.assertEqual(result['authentication_method'], 'browser_session')
        self.assertFalse(result['credential_verified'])
        profile.assert_awaited_once_with({'update_name': True})
        self.factory.assert_not_called()
        self.verify.assert_not_called()


class CredentialPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module = isolated_runtime()
        self.module.ROOT = self.root
        self.path = self.root / 'data/provider-credentials.env'

    def test_private_runtime_path_merges_known_keys_and_preserves_server_override(self):
        self.module.persist_provider_credential('STEEL_API_KEY', KEY)
        self.module.persist_provider_credential('FIRECRAWL_API_KEY', KEY + '-firecrawl')
        env = {'STEEL_API_KEY': 'server-credential'}
        restored = self.module.load_provider_credentials(environ=env)
        self.assertEqual(restored, 1)
        self.assertEqual(env['STEEL_API_KEY'], 'server-credential')
        self.assertEqual(env['FIRECRAWL_API_KEY'], KEY + '-firecrawl')
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root / '.env').exists())

    def test_unknown_names_and_interpolation_cannot_enter_runtime_env(self):
        self.path.parent.mkdir()
        self.path.write_text("PATH='/attacker/bin'\nFIRECRAWL_API_KEY='${OTHER_TOKEN}'\nSTEEL_API_KEY='" + KEY + "'\n")
        self.path.chmod(0o600)
        env = {}
        self.module.load_provider_credentials(environ=env)
        self.assertEqual(env, {'STEEL_API_KEY': KEY})
        for name, value in [('PATH', KEY), ('STEEL_API_KEY', 'short'), ('STEEL_API_KEY', KEY + '\nEVIL=value')]:
            with self.assertRaises(ValueError):
                self.module.persist_provider_credential(name, value)

    def test_public_or_symlink_credential_files_are_rejected(self):
        self.path.parent.mkdir()
        self.path.write_text("STEEL_API_KEY='" + KEY + "'\n")
        self.path.chmod(0o644)
        with self.assertRaises(ValueError):
            self.module.load_provider_credentials(environ={})
        self.path.chmod(0o600)
        alias = self.path.with_name('alias.env')
        alias.symlink_to(self.path)
        with self.assertRaises(ValueError):
            self.module.load_provider_credentials(alias, environ={})

    def test_environment_loading_preserves_alias_and_uses_private_fallback(self):
        self.module.persist_provider_credential('STEEL_API_KEY', KEY)
        vault = types.ModuleType('notion_db_setup')
        vault.restore_environment_secrets = Mock()
        with patch.dict(os.environ, {'STEELDEV_API': 'explicit-alias-credential'}, clear=True), patch.dict('sys.modules', {'notion_db_setup': vault}):
            self.module.load_environment()
            self.assertEqual(os.environ['STEEL_API_KEY'], 'explicit-alias-credential')
        with patch.dict(os.environ, {}, clear=True), patch.dict('sys.modules', {'notion_db_setup': vault}):
            self.module.load_environment()
            self.assertEqual(os.environ['STEEL_API_KEY'], KEY)

    def test_registrar_persistence_uses_data_file_and_preserves_vault(self):
        namespace = {'PROVIDERS': {'steel': {'env': 'STEEL_API_KEY'}}, 'BASE': self.root / 'data/autonomous',
                     'persist_provider_credential': self.module.persist_provider_credential,
                     'private_json': Mock(), 'encrypt_secret': Mock(return_value='encrypted-fixture'),
                     'store_secret': AsyncMock(return_value={'status': 'stored'}), 'os': os}
        persist = registrar_function('persist_key', namespace)
        with patch.dict(os.environ, {'NOTION_API_KEY': 'fixture-notion-key'}, clear=True):
            result = asyncio.run(persist('steel', 'STEEL_API_KEY', KEY))
            self.assertEqual(os.environ['STEEL_API_KEY'], KEY)
            self.assertEqual(result['notion_vault'], 'stored')
            self.assertNotIn(KEY, json.dumps(result))
        self.assertTrue(self.path.exists())
        self.assertFalse((self.root / '.env').exists())
        namespace['private_json'].assert_called_once()
        namespace['store_secret'].assert_awaited_once_with('steel', KEY)

    def test_registrar_does_not_replace_explicit_server_key(self):
        namespace = {'PROVIDERS': {'steel': {'env': 'STEEL_API_KEY'}}, 'BASE': self.root / 'data/autonomous',
                     'persist_provider_credential': Mock(), 'private_json': Mock(), 'encrypt_secret': Mock(),
                     'store_secret': AsyncMock(), 'os': os}
        persist = registrar_function('persist_key', namespace)
        with patch.dict(os.environ, {'STEEL_API_KEY': 'existing-server-credential'}, clear=True):
            with self.assertRaises(ValueError):
                asyncio.run(persist('steel', 'STEEL_API_KEY', KEY))
        namespace['persist_provider_credential'].assert_not_called()

    def test_native_verification_rejects_redirect_html_and_error_payload(self):
        class HTTPError(Exception):
            pass
        calls = []
        response = types.SimpleNamespace(status_code=200, content=b'{}', json=lambda: {'sessions': []})
        class Client:
            def __init__(self, **kwargs):
                calls.append(kwargs)
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return None
            async def get(self, url, headers):
                calls.append({'url': url, 'headers': headers})
                return response
        namespace = {'httpx': types.SimpleNamespace(AsyncClient=Client, HTTPError=HTTPError)}
        verify = registrar_function('verify_key', namespace)
        self.assertTrue(asyncio.run(verify('steel', KEY)))
        self.assertFalse(calls[0]['follow_redirects'])
        self.assertEqual(calls[1]['url'], accounts.CHECK_ENDPOINTS['steel'])
        self.assertEqual(calls[1]['headers'], {'steel-api-key': KEY})
        response.status_code = 302
        self.assertFalse(asyncio.run(verify('steel', KEY)))
        response.status_code = 200
        response.json = Mock(side_effect=ValueError('HTML login page'))
        self.assertFalse(asyncio.run(verify('steel', KEY)))
        response.json = lambda: {'success': False, 'error': 'invalid key'}
        self.assertFalse(asyncio.run(verify('steel', KEY)))
        self.assertFalse(asyncio.run(verify('devhunt', KEY)))

    def test_interrupted_registrar_checkpoint_retains_submission_marker(self):
        namespace = {'PENDING_REGISTRATION': {'email_verification_required', 'registration_submission_pending'},
                     'json': json, 're': __import__('re')}
        pending = registrar_function('pending_registration', namespace)
        self.assertEqual(pending({'status': 'executing'}), 'registration_submission_pending')
        self.assertEqual(pending({'submission_started': True, 'result': {'status': 'failed'}}), 'registration_submission_pending')
        self.assertEqual(pending({'result': {'status': 'failed', 'agent_actions': [{'signup_submission': True}]}}), 'registration_submission_pending')


if __name__ == '__main__':
    unittest.main()
