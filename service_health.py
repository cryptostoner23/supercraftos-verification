"""Bounded authenticated service probes and real LLM latency measurements."""
from __future__ import annotations
import asyncio
import json
import os
import time
import uuid
from pathlib import Path
import httpx
from runtime_env import ROOT, load_environment
from notion_db_setup import private_json


def safe_error_code(body):
    """Never persist upstream error strings, which can echo credentials."""
    error = body.get('error', {}) if isinstance(body, dict) else {}
    code = error.get('code') if isinstance(error, dict) else None
    allowed = {'invalid_api_key', 'insufficient_quota', 'model_not_found',
               'rate_limit_exceeded', 'context_length_exceeded', '400', '401',
               '402', '403', '404', '429'}
    return code if isinstance(code, str) and code in allowed else None


class ServiceHealth:
    def __init__(self, client=None):
        load_environment()
        self.client = client
        self.results = {}
        self.slots = asyncio.Semaphore(4)

    async def probe(self, name, method, url, *, env_name, headers=None, payload=None, bearer=True, params=None):
        key = os.getenv(env_name)
        if not key:
            return name, {'status': 'unconfigured'}
        actual_headers = dict(headers or {})
        if bearer:
            actual_headers['Authorization'] = f'Bearer {key}'
        actual_headers = {k: v.replace('{KEY}', key) for k, v in actual_headers.items()}
        # Only the explicitly documented NitroCloud auth endpoint takes this body.
        if name == 'nitrostack_auth':
            payload = {'apiKey': key}
        started = time.monotonic()
        try:
            async with self.slots:
                if name == 'skyfire' and os.getenv('SUPERCRAFTOS_PROVIDER_PROXY'):
                    async with httpx.AsyncClient(proxy=os.environ['SUPERCRAFTOS_PROVIDER_PROXY'], follow_redirects=False) as routed:
                        response = await routed.request(method, url, headers=actual_headers, json=payload, params=params, timeout=25)
                else:
                    response = await self.client.request(method, url, headers=actual_headers, json=payload, params=params, timeout=25)
            result = {'http_status': response.status_code, 'latency_ms': round((time.monotonic()-started)*1000), 'host': httpx.URL(url).host}
            try:
                body = response.json()
            except ValueError:
                body = {}
            if not isinstance(body, dict):
                body = {}
            if response.status_code == 200:
                result['status'] = 'active'
                if name.startswith('composio') and body.get('successful') is not True:
                    result['status'] = 'tool_execution_unverified'
                if name == 'browserless' and 'Example Domain' not in response.text:
                    result['status'] = 'content_not_verified'
                if name == 'graph' and (body.get('errors') or not body.get('data', {}).get('_meta')):
                    result['status'] = 'graphql_request_failed'
                if name in ('nvidia_models', 'llmgrid_models'):
                    result['models'] = [m['id'] for m in body.get('data', []) if isinstance(m, dict) and 'id' in m]
                    result['status'] = 'catalog_reachable'
                if name == 'nitrostack_auth':
                    result['status'] = 'authenticated' if body.get('success') is True and isinstance(body.get('data'), dict) else 'authentication_unverified'
                    result['capability'] = 'account_authentication_only'
                if name.startswith('opencode_models'):
                    result['models'] = [m['id'] for m in body.get('data', []) if isinstance(m, dict) and 'id' in m]
                    result['status'] = 'catalog_reachable'
            elif response.status_code == 401:
                result['status'] = 'authentication_rejected'
            elif response.status_code == 403:
                result['status'] = 'access_denied'
            elif response.status_code == 429:
                result['status'] = 'rate_limited'
            elif response.status_code == 402:
                result['status'] = 'payment_or_credit_required'
            else:
                result['status'] = 'endpoint_or_service_error'
            # Preserve controlled error classifications, never raw upstream messages.
            if code := safe_error_code(body):
                result['error_code'] = code
            return name, result
        except Exception as exc:
            return name, {'status': 'timeout' if isinstance(exc, httpx.TimeoutException) else 'connection_error', 'error_type': type(exc).__name__, 'latency_ms': round((time.monotonic()-started)*1000)}

    async def benchmark(self, name, base, env_name, model):
        key = os.getenv(env_name)
        if not key:
            return name, {'status': 'unconfigured', 'model': model}
        headers = {'Authorization': f'Bearer {key}', 'User-Agent': 'SuperCraftOS/2.0', 'x-opencode-session': 'supercraftos-health-' + uuid.uuid4().hex}
        payload = {'model': model, 'messages': [{'role': 'user', 'content': 'Return only this JSON object, no explanation: {"status":"ok"}'}], 'max_tokens': 128, 'temperature': 0, 'stream': False}
        if name.startswith('nvidia'):
            payload['chat_template_kwargs'] = {'enable_thinking': False}
        started = time.monotonic()
        try:
            async with self.slots:
                response = await self.client.post(base + '/chat/completions', headers=headers, json=payload, timeout=40)
            elapsed = time.monotonic()-started
            try:
                data = response.json()
            except ValueError:
                data = {}
            if not isinstance(data, dict):
                data = {}
            choices = data.get('choices') or [{}]
            content = choices[0].get('message', {}).get('content') or ''
            valid = False
            try:
                valid = json.loads(content.strip().removeprefix('```json').removesuffix('```').strip()).get('status') == 'ok'
            except (ValueError, AttributeError):
                pass
            status = 'active' if response.status_code == 200 and valid else 'no_valid_completion' if response.status_code == 200 else 'authentication_rejected' if response.status_code == 401 else 'rate_limited' if response.status_code == 429 else 'request_rejected'
            result = {'status': status, 'http_status': response.status_code, 'model': model, 'base_url': base, 'key_env': env_name, 'latency_ms': round(elapsed*1000), 'output_tokens': data.get('usage', {}).get('completion_tokens'), 'valid_json': valid}
            if code := safe_error_code(data):
                result['error_code'] = code
            return name, result
        except Exception as exc:
            return name, {'status': 'timeout' if isinstance(exc, httpx.TimeoutException) else 'connection_error', 'error_type': type(exc).__name__, 'model': model, 'latency_ms': round((time.monotonic()-started)*1000)}

    async def run(self, *, llm=True, update_provider=False):
        owned = self.client is None
        self.client = self.client or httpx.AsyncClient(follow_redirects=False)
        try:
            tasks = [
                self.probe('notion', 'GET', 'https://api.notion.com/v1/users/me', env_name='NOTION_API_KEY', headers={'Notion-Version': '2022-06-28'}),
                self.probe('airtable', 'GET', 'https://api.airtable.com/v0/meta/whoami', env_name='AIRTABLE_API_KEY'),
                self.probe('apify', 'GET', 'https://api.apify.com/v2/users/me', env_name='APIFY_API_TOKEN'),
                self.probe('tavily', 'GET', 'https://api.tavily.com/usage', env_name='TAVILY_API_KEY'),
                self.probe('zerox', 'GET', 'https://api.0x.org/sources?chainId=1', env_name='ZEROX_API_KEY', headers={'0x-api-key': '{KEY}', '0x-version': 'v2'}, bearer=False),
                self.probe('dune', 'POST', 'https://api.dune.com/api/v1/usage', env_name='DUNE_API_KEY', headers={'X-Dune-API-Key': '{KEY}'}, payload={}, bearer=False),
                self.probe('composio_supplied', 'POST', 'https://backend.composio.dev/api/v3.1/tools/execute/HACKERNEWS_GET_USER', env_name='COMPOSIO_API_KEY', headers={'x-api-key': '{KEY}'}, payload={'arguments': {'username': 'pg'}}, bearer=False),
                self.probe('nvidia_models', 'GET', 'https://integrate.api.nvidia.com/v1/models', env_name='NVIDIA_API_KEY'),
                self.probe('hyrve', 'GET', 'https://api.hyrveai.com/v1/wallet', env_name='HYRVE_API_KEY', headers={'X-API-Key': '{KEY}'}, bearer=False),
                self.probe('browserless', 'POST', 'https://production-sfo.browserless.io/content', env_name='BROWSERLESS_API_KEY', params={'token': os.getenv('BROWSERLESS_API_KEY', '')}, payload={'url': 'https://example.com/'}, bearer=False),
                self.probe('skyfire', 'GET', 'https://api.skyfire.xyz/api/v1/agents/balance', env_name='SKYFIRE_API_KEY', headers={'skyfire-api-key': '{KEY}'}, bearer=False),
                self.probe('graph', 'POST', 'https://gateway.thegraph.com/api/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV', env_name='GRAPH_API_KEY', payload={'query': '{ _meta { block { number } } }'}),
                self.probe('opencode_models', 'GET', 'https://opencode.ai/zen/go/v1/models', env_name='OPENCODE_GO_API_KEY'),
                self.probe('llmgrid_models', 'GET', 'https://api.llmgrid.ai/v1/models', env_name='LLMGRID_API_KEY'),
                self.probe('nitrostack_auth', 'POST', 'https://api.nitrostack.ai/api/v1/api-keys/auth', env_name='NITROSTACK_API_KEY', bearer=False),
            ]
            for name, result in await asyncio.gather(*tasks):
                self.results[name] = result
            if llm:
                nvmodels = self.results.get('nvidia_models', {}).get('models', [])
                gomodels = self.results.get('opencode_models', {}).get('models', [])
                candidates = []
                nv = [m for m in ['nvidia/nemotron-3-super-120b-a12b', 'nvidia/nemotron-3.5-lightning-30b-a3b', 'meta/llama-3.1-8b-instruct', 'meta/llama-3.3-70b-instruct'] if m in nvmodels][:2]
                go = [m for m in ['qwen3.5-plus', 'glm-5', 'kimi-k2.5', 'glm-5.1', 'deepseek-v4-flash'] if m in gomodels][:2]
                for model in nv:
                    candidates.append(self.benchmark('nvidia:' + model, 'https://integrate.api.nvidia.com/v1', 'NVIDIA_API_KEY', model))
                for model in go:
                    candidates.append(self.benchmark('opencode:' + model, 'https://opencode.ai/zen/go/v1', 'OPENCODE_GO_API_KEY', model))
                # A catalog is not evidence of working inference; test one listed model.
                gridmodels = self.results.get('llmgrid_models', {}).get('models', [])
                if gridmodels:
                    candidates.append(self.benchmark('llmgrid:' + gridmodels[0], 'https://api.llmgrid.ai/v1', 'LLMGRID_API_KEY', gridmodels[0]))
                for name, result in await asyncio.gather(*candidates):
                    self.results[name] = result
                working = [r for name, r in self.results.items() if ':' in name and r.get('status') == 'active']
                if working:
                    fastest = min(working, key=lambda item: item['latency_ms'])
                    self.results['fastest_llm'] = fastest
                    if update_provider:
                        private_json(ROOT / 'data' / 'llm_provider.json', fastest)
            private_json(ROOT / 'data' / 'service_health.json', self.results)
            return self.results
        finally:
            if owned:
                await self.client.aclose()


if __name__ == '__main__':
    result = asyncio.run(ServiceHealth().run())
    print(json.dumps({k: {a: b for a, b in v.items() if a != 'models'} for k, v in result.items()}, indent=2))
