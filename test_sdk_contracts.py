"""Contract checks against installed SDKs and selected LLM routing."""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from apify_client._models import ActorListItem
from cloud_actor import mapping
from notion_client import AsyncClient
import notion_db_setup as notion
from token_optimizer import TokenOptimizer, load_config


class SDKContracts(unittest.IsolatedAsyncioTestCase):
    async def test_notion_database_create_keeps_schema_in_new_sdk(self):
        requests = []
        def handle(request):
            requests.append(request)
            payload = json.loads(request.content)
            self.assertIn('initial_data_source', payload)
            self.assertEqual(payload['initial_data_source']['properties']['Name'], {'title': {}})
            self.assertEqual(request.headers['Notion-Version'], '2026-03-11')
            return httpx.Response(200, json={'id':'database-fixture','data_sources':[{'id':'source-fixture'}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as transport:
            client = AsyncClient(auth='fixture',client=transport,notion_version='2026-03-11')
            result = await client.databases.create(parent={'page_id':'fixture-parent'},title=[{'text':{'content':'Fixture'}}],initial_data_source={'properties':{'Name':{'title':{}}}})
            self.assertEqual(result['id'],'database-fixture')
        self.assertEqual(len(requests),1)

    async def test_selected_provider_routes_to_real_configured_base(self):
        config = load_config(); config['models']['provider_selection'] = 'configured'
        def handle(request):
            self.assertEqual(str(request.url),'https://integrate.api.nvidia.com/v1/chat/completions')
            self.assertEqual(request.headers['Authorization'],'Bearer fixture-nvidia-key')
            self.assertEqual(json.loads(request.content)['model'],'nvidia/fixture-model')
            return httpx.Response(200,json={'choices':[{'message':{'content':'{"status":"ok"}'}}],'usage':{'prompt_tokens':10,'completion_tokens':6}})
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'NVIDIA_API_KEY':'fixture-nvidia-key'}):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                optimizer = TokenOptimizer(config=config,client=client)
                optimizer.provider={'base_url':'https://integrate.api.nvidia.com/v1','key_env':'NVIDIA_API_KEY','model':'nvidia/fixture-model'}
                optimizer.path=Path(directory)/'usage.json'
                before=optimizer.usage.get('unpriced_requests',0)
                self.assertEqual(json.loads(await optimizer.complete('schema',[{'role':'user','content':'fixture'}]))['status'],'ok')
                self.assertEqual(optimizer.usage['unpriced_requests'],before+1)

    async def test_apify_sdk_models_keep_api_aliases(self):
        model=ActorListItem.model_construct(id='fixture',name='registration',username='fixture',created_at=None,modified_at=None)
        result=mapping(model)
        self.assertEqual(result['id'],'fixture')
        self.assertEqual(result['name'],'registration')
        self.assertIn('createdAt',result)


if __name__=='__main__': unittest.main()
