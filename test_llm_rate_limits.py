import unittest
from unittest.mock import patch, AsyncMock
import httpx
from token_optimizer import request_with_retry

class RateLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_after_provider_cooldown_then_returns_success(self):
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(429,headers={'Retry-After':'4'},json={}) if len(calls)==1 else httpx.Response(200,json={'ok':True})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch('token_optimizer.asyncio.sleep',new_callable=AsyncMock) as sleep, patch('token_optimizer.random.uniform',return_value=0):
                response=await request_with_retry(client,'GET','https://example.com',attempts=3)
        self.assertEqual(response.status_code,200)
        sleep.assert_awaited_once_with(4)
        self.assertEqual(len(calls),2)

    async def test_long_cooldown_is_not_truncated_into_early_retry(self):
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(429,headers={'Retry-After':'120'},json={})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch('token_optimizer.asyncio.sleep',new_callable=AsyncMock) as sleep:
                with self.assertRaises(httpx.HTTPStatusError):
                    await request_with_retry(client,'GET','https://example.com',attempts=3)
        sleep.assert_not_awaited()
        self.assertEqual(len(calls),1)

    async def test_http_date_cooldown_is_honored(self):
        count=0
        def handler(request):
            nonlocal count
            count+=1
            return httpx.Response(429,headers={'Retry-After':'Thu, 01 Jan 1970 00:16:50 GMT'},json={}) if count==1 else httpx.Response(200,json={})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch('token_optimizer.time.time',return_value=1000), patch('token_optimizer.random.uniform',return_value=0), patch('token_optimizer.asyncio.sleep',new_callable=AsyncMock) as sleep:
                await request_with_retry(client,'GET','https://example.com',attempts=2)
        sleep.assert_awaited_once_with(10)
