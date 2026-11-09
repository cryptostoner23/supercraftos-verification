"""All automated Context.dev checks use local SDK transport fixtures."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from context.dev import AsyncContextDev
from context_service import ContextService, ContextRequestError
from resolver_research import ResolverResearch


def response(results=None):
    return {'request_id':'fixture-request','query':'fixture','results':results or [],'partial':False,'cache_metadata':{'status':'miss','age_ms':0}}


class ContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_returns_bounded_source_evidence_without_live_call(self):
        from dynamic_mcp_server import DynamicMCPServer
        fixture = {'request_id': 'fixture', 'sources': [{'markdown': 'x' * 14000}]}
        with tempfile.TemporaryDirectory() as directory:
            server = DynamicMCPServer(Path(directory) / 'tools.json')
            with patch('resolver_research.ResolverResearch.collect', return_value=fixture) as collect:
                reply = await server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'research_fusion_resolver', 'arguments': {}}})
            collect.assert_awaited_once_with(3)
            result = json.loads(reply['result']['content'][0]['text'])
            self.assertEqual(len(result['sources'][0]['markdown']), 12000)
            self.assertTrue(result['sources'][0]['markdown_truncated'])

    async def test_official_sdk_sends_auth_current_endpoint_and_freshness(self):
        calls=[]
        def handle(request):
            calls.append(request)
            self.assertEqual(str(request.url),'https://api.context.dev/v1/web/search')
            self.assertEqual(request.headers['Authorization'],'Bearer fixture-key')
            data=json.loads(request.content)
            self.assertEqual(data['numResults'],3)
            self.assertEqual(data['markdownOptions']['maxAgeMs'],0)
            self.assertTrue(data['markdownOptions']['enabled'])
            return httpx.Response(200,json=response())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
            client=AsyncContextDev(api_key='fixture-key',http_client=transport,max_retries=0)
            service=ContextService(client)
            data=await service.search('1inch Fusion resolver')
            self.assertEqual(data['request_id'],'fixture-request')
        self.assertEqual(len(calls),1)

    async def test_validation_failure_is_not_retried(self):
        calls=[]
        def handle(request):
            calls.append(1)
            return httpx.Response(400,json={'error_code':'INVALID_PARAMS','request_id':'fixture-error'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
            service=ContextService(AsyncContextDev(api_key='fixture-key',http_client=transport,max_retries=0))
            with self.assertRaises(ContextRequestError) as captured:
                await service.search('fixture')
            self.assertEqual(captured.exception.code,'INVALID_PARAMS')
            self.assertEqual(captured.exception.request_id,'fixture-error')
        self.assertEqual(len(calls),1)

    async def test_retry_after_is_respected(self):
        calls=[]
        def handle(request):
            calls.append(1)
            return httpx.Response(429,headers={'Retry-After':'2'},json={'error_code':'RATE_LIMITED'}) if len(calls)==1 else httpx.Response(200,json=response())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
            service=ContextService(AsyncContextDev(api_key='fixture',http_client=transport,max_retries=0))
            with patch('context_service.asyncio.sleep') as sleep:
                await service.search('fixture')
                delay=sleep.await_args.args[0]
                self.assertGreaterEqual(delay,2)
                self.assertLess(delay,2.26)
        self.assertEqual(len(calls),2)

    async def test_partial_markdown_is_preserved_as_failed(self):
        class Fixture:
            async def search(self,*args,**kwargs):
                return response([{'title':'Fixture','url':'https://github.com/1inch/fixture','description':'fixture','markdown':{'code':'WEBSITE_BLOCKED','markdown':'must not be used'}}])
        with tempfile.TemporaryDirectory() as directory,patch('resolver_research.ROOT',Path(directory)):
            result=await ResolverResearch(Fixture()).collect()
            self.assertEqual(result['sources'][0]['markdown_status'],'WEBSITE_BLOCKED')
            self.assertIsNone(result['sources'][0]['markdown'])
            self.assertEqual(result['execution_status'],'research_only')


if __name__=='__main__':unittest.main()
