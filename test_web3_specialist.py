import unittest
import httpx
from unittest.mock import patch
from web3_specialist import consult, URL

class SpecialistTests(unittest.IsolatedAsyncioTestCase):
    async def test_calls_existing_local_ai_with_readonly_enforced(self):
        requests=[]
        def handler(request):
            import json
            requests.append(json.loads(request.content))
            self.assertEqual(str(request.url), URL)
            return httpx.Response(200,json={'answer':'Observed gas','mode':'llm:existing', 'tool_calls':[{'tool':'brain_gas','result':{'source':'rpc'}}]})
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch('web3_specialist.httpx.AsyncClient',return_value=client):
            result=await consult({'question':'Check Ethereum gas'})
        self.assertEqual(requests,[{'message':'Check Ethereum gas','use_llm':True,'read_only':True}])
        self.assertEqual(result['mode'],'llm:existing')
        self.assertEqual(result['tool_calls'][0]['result']['source'],'rpc')
    async def test_service_failure_never_becomes_success(self):
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(503,text='private upstream failure')))
        with patch('web3_specialist.httpx.AsyncClient',return_value=client):
            result=await consult({'question':'Check gas'})
        self.assertEqual(result['status'],'unavailable')
        self.assertNotIn('private',str(result))
