"""Offline checks for provider evidence and credential-safe reporting."""
import json
import os
import unittest
from unittest.mock import patch

import httpx

from service_health import ServiceHealth, safe_error_code


class ProviderHealthTests(unittest.IsolatedAsyncioTestCase):
    async def test_catalog_is_not_inference_and_errors_cannot_echo_key(self):
        secret = 'private-test-credential'
        def handler(request):
            if request.url.path.endswith('/models'):
                return httpx.Response(200, json={'data': [{'id': 'model-a'}]})
            return httpx.Response(401, json={'error': {'code': secret}})
        with patch.dict(os.environ, {'LLMGRID_API_KEY': secret}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                health = ServiceHealth(client)
                _, catalog = await health.probe('llmgrid_models', 'GET', 'https://api.llmgrid.ai/v1/models', env_name='LLMGRID_API_KEY')
                self.assertEqual(catalog['status'], 'catalog_reachable')
                _, completion = await health.benchmark('llmgrid:model-a', 'https://api.llmgrid.ai/v1', 'LLMGRID_API_KEY', 'model-a')
                self.assertEqual(completion['status'], 'authentication_rejected')
                self.assertNotIn(secret, json.dumps(completion))

    async def test_nitrostack_auth_uses_documented_body_and_reports_no_tokens(self):
        secret = 'private-test-credential'
        def handler(request):
            self.assertEqual(json.loads(request.content), {'apiKey': secret})
            self.assertNotIn('Authorization', request.headers)
            return httpx.Response(200, json={'success': True, 'data': {'accessToken': secret}})
        with patch.dict(os.environ, {'NITROSTACK_API_KEY': secret}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                _, result = await ServiceHealth(client).probe('nitrostack_auth', 'POST', 'https://api.nitrostack.ai/api/v1/api-keys/auth', env_name='NITROSTACK_API_KEY', bearer=False)
        self.assertEqual(result['status'], 'authenticated')
        self.assertNotIn(secret, json.dumps(result))

    async def test_health_run_does_not_change_provider_routing(self):
        async def probe(name, *args, **kwargs):
            return name, {'status': 'catalog_reachable', 'models': []}
        async def benchmark(*args):
            return 'nvidia:test', {'status': 'active', 'latency_ms': 1}
        async with httpx.AsyncClient() as client:
            health = ServiceHealth(client)
            with patch.object(health, 'probe', probe), patch.object(health, 'benchmark', benchmark), patch('service_health.private_json') as write:
                await health.run()
        self.assertEqual(len(write.call_args_list), 1)
        self.assertEqual(write.call_args.args[0].name, 'service_health.json')

    def test_only_known_error_codes_are_saved(self):
        self.assertEqual(safe_error_code({'error': {'code': 'invalid_api_key'}}), 'invalid_api_key')
        self.assertIsNone(safe_error_code({'error': {'code': 'upstream-secret'}}))


if __name__ == '__main__':
    unittest.main()
