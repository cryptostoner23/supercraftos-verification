import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx
from token_optimizer import TokenOptimizer, ModelNotConfigured, ACTION_SCHEMA, REVIEW_SCHEMA

CACHE_ENV = {k: os.environ[k] for k in ('TIKTOKEN_CACHE_DIR',) if k in os.environ}


class ModelConfigurationTests(unittest.IsolatedAsyncioTestCase):
    async def test_custom_provider_and_actual_reported_cost(self):
        def handler(request):
            self.assertEqual(str(request.url),'https://provider.example/v1/chat/completions')
            self.assertEqual(request.headers['Authorization'],'Bearer fixture-key')
            self.assertEqual(json.loads(request.content)['model'],'fixture-model')
            return httpx.Response(200,json={'choices':[{'message':{'content':'done'}}],
                'usage':{'prompt_tokens':12,'completion_tokens':4,'cost':.002}})
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{**CACHE_ENV,'SUPERCRAFTOS_LLM_BASE_URL':'https://provider.example/v1','SUPERCRAFTOS_LLM_API_KEY':'fixture-key','SUPERCRAFTOS_MODEL':'fixture-model'},clear=True):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                optimizer=TokenOptimizer(client=client);optimizer.path=Path(root)/'usage.json'
                optimizer.usage={'input_tokens':0,'output_tokens':0,'cost_usd':0.,'requests':0,'unpriced_requests':0}
                self.assertEqual(await optimizer.complete('agent execution',[{'role':'user','content':'test'}]),'done')
                self.assertAlmostEqual(optimizer.usage['cost_usd'],.002)
                # A second optimizer process must add to persisted counts, not overwrite them.
                second=TokenOptimizer(client=client);second.path=optimizer.path
                await second.complete('agent execution',[{'role':'user','content':'test'}])
                value=json.loads(optimizer.path.read_text())
                self.assertEqual(value['requests'],2);self.assertEqual(value['input_tokens'],24)
                self.assertNotIn('fixture-key',optimizer.path.read_text())
    async def test_missing_credential_is_actionable(self):
        with patch.dict(os.environ,CACHE_ENV,clear=True):
            optimizer=TokenOptimizer()
            with self.assertRaises(ModelNotConfigured):await optimizer.complete('agent execution',[])
    async def test_invalid_endpoint_is_rejected_before_network(self):
        for url in ['http://example.com','https://user:password@example.com','https://example.com?token=secret']:
            with patch.dict(os.environ,{**CACHE_ENV,'SUPERCRAFTOS_LLM_BASE_URL':url},clear=True):
                with self.assertRaises(ValueError):TokenOptimizer()
    async def test_openrouter_uses_dedicated_application_key(self):
        with patch.dict(os.environ,{**CACHE_ENV,'OPENROUTER_API_KEY':'fixture-router-key','SUPERCRAFTOS_MODEL':'openai/fixture'},clear=True):
            optimizer=TokenOptimizer()
            self.assertEqual(optimizer.provider['base_url'],'https://openrouter.ai/api/v1')
            self.assertEqual(optimizer.provider['key_env'],'OPENROUTER_API_KEY')
            self.assertEqual(optimizer.route('agent execution'),'openai/fixture')

    async def test_nvidia_agent_requests_use_action_schema_without_changing_chat(self):
        formats=[]
        thinking=[]
        def handler(request):
            payload=json.loads(request.content);formats.append(payload.get('guided_json'))
            thinking.append(payload['chat_template_kwargs']['enable_thinking'])
            return httpx.Response(200,json={'choices':[{'message':{'content':'{}'}}]})
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{**CACHE_ENV,'NVIDIA_API_KEY':'fixture-key'},clear=True):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                optimizer=TokenOptimizer(client=client)
                optimizer.provider={'base_url':'https://integrate.api.nvidia.com/v1','key_env':'NVIDIA_API_KEY'}
                optimizer.path=Path(root)/'usage.json'
                for task in ('agent execution','acceptance review','summary'):
                    await optimizer.complete(task,[{'role':'user','content':'test'}])
        self.assertEqual(formats,[ACTION_SCHEMA,REVIEW_SCHEMA,None])
        self.assertEqual(thinking,[False,False,False])

    async def test_verified_fallback_cannot_send_key_to_mismatched_host(self):
        calls=[]
        def handler(request):
            calls.append((str(request.url),request.headers['Authorization']))
            if request.url.host=='integrate.api.nvidia.com': return httpx.Response(401,json={})
            self.assertEqual(request.url.host,'opencode.ai')
            return httpx.Response(200,json={'choices':[{'message':{'content':'recovered'}}]})
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{**CACHE_ENV,'NVIDIA_API_KEY':'nv-fixture','OPENCODE_GO_API_KEY':'go-fixture'},clear=True):
            directory=Path(root);(directory/'data').mkdir()
            routes=[{'status':'active','model':'missing-endpoint'}, {'status':'active','base_url':'https://attacker.example','key_env':'NVIDIA_API_KEY','model':'bad'},
                {'status':'active','base_url':'https://opencode.ai/zen/go/v1','key_env':'NVIDIA_API_KEY','model':'mismatched'},
                {'status':'active','base_url':'https://opencode.ai/zen/go/v1','key_env':'OPENCODE_GO_API_KEY','model':'fixture'}]
            (directory/'data/llm_fallbacks.json').write_text(json.dumps(routes))
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                optimizer=TokenOptimizer(client=client);optimizer.provider={'base_url':'https://integrate.api.nvidia.com/v1','key_env':'NVIDIA_API_KEY'}
                optimizer.path=directory/'usage.json'
                with patch('token_optimizer.ROOT',directory):
                    self.assertEqual(await optimizer.complete('summary',[]),'recovered')
            self.assertEqual(len(calls),2)
            self.assertEqual(calls[1][1],'Bearer go-fixture')

    async def test_timeout_moves_to_verified_fallback_without_repeating_failed_route(self):
        calls=[]
        def handler(request):
            model=json.loads(request.content)['model'];calls.append(model)
            if model=='primary':raise httpx.ReadTimeout('fixture timeout',request=request)
            return httpx.Response(200,json={'choices':[{'message':{'content':'recovered'}}]})
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{**CACHE_ENV,'NVIDIA_API_KEY':'fixture-key'},clear=True):
            directory=Path(root);(directory/'data').mkdir()
            fallback={'status':'active','base_url':'https://integrate.api.nvidia.com/v1','key_env':'NVIDIA_API_KEY','model':'fallback'}
            (directory/'data/llm_fallbacks.json').write_text(json.dumps([fallback]))
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                optimizer=TokenOptimizer(client=client);optimizer.provider={**fallback,'model':'primary'};optimizer.path=directory/'usage.json'
                with patch('token_optimizer.ROOT',directory):self.assertEqual(await optimizer.complete('agent execution',[]),'recovered')
            self.assertEqual(calls,['primary','fallback'])

    async def test_empty_completion_fails_over_and_retains_both_reported_costs(self):
        calls=[]
        def handler(request):
            payload=json.loads(request.content);calls.append(payload['model'])
            if payload['model']=='primary':
                return httpx.Response(200,json={'choices':[{'message':{'content':None},'finish_reason':'length'}], 'usage':{'prompt_tokens':5,'completion_tokens':10,'cost':0.01}})
            return httpx.Response(200,json={'choices':[{'message':{'content':'recovered'},'finish_reason':'stop'}], 'usage':{'prompt_tokens':5,'completion_tokens':2,'cost':0.02}})
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{**CACHE_ENV,'NVIDIA_API_KEY':'fixture-key'},clear=True):
            directory=Path(root);(directory/'data').mkdir()
            route={'status':'active','base_url':'https://integrate.api.nvidia.com/v1','key_env':'NVIDIA_API_KEY','model':'fallback'}
            (directory/'data/llm_fallbacks.json').write_text(json.dumps([route]))
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                optimizer=TokenOptimizer(client=client);optimizer.provider={**route,'model':'primary'};optimizer.path=directory/'usage.json'
                optimizer.usage={'input_tokens':0,'output_tokens':0,'cost_usd':0.,'requests':0,'unpriced_requests':0}
                with patch('token_optimizer.ROOT',directory):
                    self.assertEqual(await optimizer.complete('agent execution',[]),'recovered')
                self.assertEqual(optimizer.usage['requests'],2)
                self.assertAlmostEqual(optimizer.usage['cost_usd'],.03)
        self.assertEqual(calls,['primary','fallback'])
