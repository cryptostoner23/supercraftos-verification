"""Offline invariants for autonomous registration and environment discovery."""
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from autonomous_registration import BrowserRegistrationAgent, pending_registration
from runtime_env import load_environment


class EnvTests(unittest.TestCase):
    def test_home_env_and_aliases_without_password_misclassification(self):
        seen = []
        def load(path, override=False):
            seen.append(str(path))
            if str(path) == '/root/.env':
                os.environ['Gmail_USERNAME'] = 'fixture@example.com'
                os.environ['GMAIL_PASSWORD'] = 'fixture-normal-password'
        with patch.dict(os.environ, {}, clear=True), patch('runtime_env.load_dotenv', side_effect=load):
            load_environment()
            self.assertEqual(os.getenv('GMAIL_ADDRESS'), 'fixture@example.com')
            self.assertEqual(os.getenv('GMAIL_LOGIN_PASSWORD'), 'fixture-normal-password')
            self.assertNotIn('GMAIL_APP_PASSWORD', os.environ)
            self.assertEqual(seen[-1], '/root/.env')

    def test_process_settings_take_precedence(self):
        with patch.dict(os.environ, {'GMAIL_ADDRESS': 'process@example.com', 'Gmail_USERNAME': 'other@example.com'}), patch('runtime_env.load_dotenv'):
            load_environment()
            self.assertEqual(os.environ['GMAIL_ADDRESS'], 'process@example.com')


class RegistrationTests(unittest.IsolatedAsyncioTestCase):
    def agent(self):
        optimizer = SimpleNamespace(usage={'cost_usd': 0}, complete=AsyncMock(side_effect=RuntimeError('fixture upstream failure')))
        return BrowserRegistrationAgent(optimizer)

    async def test_password_can_only_go_to_identity_provider(self):
        agent = self.agent()
        page = SimpleNamespace(url='https://peerpush.com/signin')
        page.locator = lambda selector: SimpleNamespace(fill=AsyncMock())
        with self.assertRaises(PermissionError):
            await agent.apply(page, 'peerpush', {'action': 'fill', 'id': 1, 'credential': 'GMAIL_LOGIN_PASSWORD'}, {'controls': [{'id': 1, 'tag': 'input', 'label': 'Password'}]})
        with self.assertRaises(PermissionError):
            await agent.apply(page, 'peerpush', {'action': 'fill', 'id': 1, 'credential': 'X_PASSWORD'}, {'controls': [{'id': 1, 'tag': 'input', 'label': 'Password'}]})

    async def test_password_cannot_go_to_nonpassword_input_on_google(self):
        agent = self.agent()
        page = SimpleNamespace(url='https://accounts.google.com/signin', locator=lambda selector: SimpleNamespace(fill=AsyncMock()))
        with self.assertRaises(PermissionError):
            await agent.apply(page, 'peerpush', {'action': 'fill', 'id': 1, 'credential': 'GMAIL_LOGIN_PASSWORD'}, {'controls': [{'id': 1, 'tag': 'input', 'label': 'Birth day', 'type': 'text'}]})

    async def test_google_account_creation_is_outside_portal_registration(self):
        agent = self.agent()
        page = SimpleNamespace(url='https://accounts.google.com/signin', locator=lambda selector: SimpleNamespace(click=AsyncMock()))
        with self.assertRaises(PermissionError):
            await agent.apply(page, 'peerpush', {'action': 'click', 'id': 1}, {'controls': [{'id': 1, 'tag': 'button', 'label': 'Create account'}]})

    async def test_navigation_rejects_phishing_and_paid_actions(self):
        agent = self.agent()
        page = SimpleNamespace(url='https://peerpush.com/signin', locator=lambda selector: SimpleNamespace(click=AsyncMock()))
        for label, href in [('Sign in', 'https://attacker.example/login'), ('Upgrade', '/upgrade')]:
            with self.assertRaises(PermissionError):
                await agent.apply(page, 'peerpush', {'action': 'click', 'id': 1}, {'controls': [{'id': 1, 'tag': 'a', 'label': label, 'href': href}]})

    async def test_secret_redaction_before_planning(self):
        with patch.dict(os.environ, {'GMAIL_LOGIN_PASSWORD': 'private-fixture-password'}):
            agent = self.agent()
            clean = agent.redact('private-fixture-password user@example.com fc-ZZZ-FIXTURE-0123456789-abcdefghijklmno')
            self.assertNotIn('private-fixture-password', clean)
            self.assertNotIn('user@example.com', clean)
            self.assertNotIn('fc-ZZZ-FIXTURE-0123456789-abcdefghijklmno', clean)

    async def test_planner_failure_uses_autonomous_semantic_fallback(self):
        agent = self.agent()
        result = await agent.decide('peerpush', {'controls': [{'id': 3, 'tag': 'button', 'label': 'Continue with Google'}]}, 'peerpush.com')
        self.assertEqual(result, {'action': 'click', 'id': 3})
        self.assertFalse(agent.model_available)
        self.assertEqual(agent.events[0]['node'], 'planner_fallback')

    async def test_already_filled_identifier_advances_instead_of_repeating(self):
        agent = self.agent()
        agent.optimizer.complete = AsyncMock(return_value='{"action":"fill","id":1,"credential":"GMAIL_ADDRESS"}')
        observation = {'controls': [
            {'id': 1, 'tag': 'input', 'name': 'identifier', 'type': 'text', 'label': '', 'filled': True},
            {'id': 2, 'tag': 'button', 'label': 'Next'},
        ]}
        self.assertEqual(await agent.decide('steel', observation, 'accounts.google.com'), {'action': 'click', 'id': 2})

    def test_legacy_confirm_email_checkpoint_prevents_duplicate_signup(self):
        checkpoint = {'result': {'status': 'no_progress'}, 'events': [{'fingerprint': json.dumps({'url': 'www.firecrawl.dev/signin/confirm-email'})}]}
        self.assertEqual(pending_registration(checkpoint), 'email_verification_required')
        self.assertEqual(pending_registration({'result': {'status': 'registration_submission_pending'}}), 'registration_submission_pending')

    async def test_pending_registration_returns_before_opening_browser(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            checkpoint = Path(directory) / 'firecrawl.checkpoint.json'
            checkpoint.write_text(json.dumps({'result': {'status': 'email_verification_required'}}))
            with patch('autonomous_registration.BASE', Path(directory)), patch('autonomous_registration.browser_session') as session:
                result = await self.agent().run('firecrawl')
                self.assertEqual(result['status'], 'email_verification_required')
                session.assert_not_called()

    async def test_uncertain_signup_submission_is_durable_before_click(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        agent = self.agent()
        agent.actions = [{'action': 'fill', 'credential': 'PROVIDER_PASSWORD'}]
        click = AsyncMock(side_effect=TimeoutError('fixture connection interruption'))
        page = SimpleNamespace(url='https://www.firecrawl.dev/signin', locator=lambda selector: SimpleNamespace(click=click))
        observation = {'controls': [{'id': 1, 'tag': 'button', 'type': 'submit', 'label': 'Create account'}]}
        with TemporaryDirectory() as directory, patch('autonomous_registration.BASE', Path(directory)):
            with self.assertRaises(TimeoutError):
                await agent.apply(page, 'firecrawl', {'action': 'click', 'id': 1}, observation)
            checkpoint = json.loads((Path(directory) / 'firecrawl.checkpoint.json').read_text())
            self.assertEqual(pending_registration(checkpoint), 'registration_submission_pending')
            with self.assertRaises(PermissionError):
                await agent.apply(page, 'firecrawl', {'action': 'click', 'id': 1}, observation)
            self.assertEqual(click.await_count, 1)

    async def test_native_firecrawl_uses_keyless_without_fabricating_identity(self):
        from autonomous_registration import firecrawl_agent_onboarding
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import httpx
        calls = []
        def respond(request):
            calls.append((request.method, request.url.path))
            if request.url.path.endswith('oauth-protected-resource'):
                return httpx.Response(200, json={'resource': 'https://api.firecrawl.dev/'})
            if request.url.path.endswith('oauth-authorization-server'):
                return httpx.Response(200, json={'agent_auth': {'register_uri': 'https://www.firecrawl.dev/agent/auth', 'identity_assertion': {'assertion_types_supported': ['urn:ietf:params:oauth:token-type:id-jag']}}})
            self.assertEqual(request.url.path, '/v2/scrape')
            self.assertNotIn('authorization', request.headers)
            return httpx.Response(200, json={'success': True, 'data': {'markdown': '# Example'}})
        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        with TemporaryDirectory() as directory, patch('autonomous_registration.BASE', Path(directory)), patch('autonomous_registration.httpx.AsyncClient', return_value=client):
            result = await firecrawl_agent_onboarding()
        self.assertEqual(result['status'], 'keyless_available')
        self.assertEqual(result['registration_status'], 'workos_identity_assertion_required')
        self.assertFalse(result['key_obtained'])
        self.assertNotIn(('POST', '/agent/auth'), calls)

    async def test_cloud_unavailable_does_not_use_local_target_browser(self):
        from cloud_browser import browser_session, CloudUnavailable
        with patch.dict(os.environ, {}, clear=True), patch('cloud_browser.load_environment'):
            with self.assertRaises(CloudUnavailable):
                async with browser_session():
                    self.fail('Target registration must not fall back to local Chromium')


if __name__ == '__main__':
    unittest.main()
