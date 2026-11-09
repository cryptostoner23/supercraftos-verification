import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from provider_recovery import reconnect, skyfire_balance
from runtime_env import _provider_values


class ProviderRecoveryTests(unittest.TestCase):
    def call(self, code, root, credential='fixture_replacement_credential'):
        def handler(request):
            self.assertEqual(str(request.url), 'https://api.airtable.com/v0/meta/whoami')
            self.assertEqual(request.headers['Authorization'], 'Bearer ' + credential)
            return httpx.Response(code, json={'id': 'usrfixture'} if code == 200 else {'error': {'message': credential}})
        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await reconnect({'provider': 'airtable', 'credential': credential}, client=client, root=root)
        return asyncio.run(run())

    def test_rejected_key_does_not_replace_working_secret_or_leak_upstream(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'AIRTABLE_API_KEY': 'original'}):
            result = self.call(401, directory)
            self.assertFalse(result['saved'])
            self.assertEqual(os.environ['AIRTABLE_API_KEY'], 'original')
            self.assertFalse((Path(directory) / 'data/reconnected-providers.env').exists())
            self.assertNotIn('fixture_replacement', json.dumps(result))
            self.assertNotIn('fixture_replacement', (Path(directory) / 'data/airtable.recovery.json').read_text())

    def test_verified_replacement_is_private_and_persists(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ), patch('provider_recovery.encrypt_secret', return_value='encrypted-fixture'):
            result = self.call(200, directory)
            target = Path(directory) / 'data/reconnected-providers.env'
            self.assertTrue(result['saved'])
            self.assertEqual(_provider_values(target)['AIRTABLE_API_KEY'], 'fixture_replacement_credential')
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('fixture_replacement', json.dumps(result))

    def test_unknown_provider_and_invalid_credential_fail_before_network(self):
        for value in ({'provider': 'http://localhost', 'credential': 'test'},
                      {'provider': 'airtable', 'credential': 'bad\ncredential'},
                      {'provider': 'airtable', 'credential': 'valid_fixture_secret', 'url': 'http://localhost'}):
            with self.assertRaises(ValueError):
                asyncio.run(reconnect(value))

    def test_skyfire_balance_uses_only_read_endpoint_and_excludes_extra_fields(self):
        async def run():
            def handler(request):
                self.assertEqual(request.method, 'GET')
                self.assertEqual(str(request.url), 'https://api.skyfire.xyz/api/v1/agents/balance')
                return httpx.Response(200, json={'available':'1.25','heldAmount':'0','pendingCharges':'0','pendingDeposits':'0','token':'must-not-export'})
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with patch('runtime_env.load_environment'), patch.dict(os.environ, {'SKYFIRE_API_KEY':'fixture_private_key'}):
                    result = await skyfire_balance({}, client=client)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(result['balance']['available'], '1.25')
                self.assertNotIn('must-not-export', json.dumps(result))
        asyncio.run(run())
