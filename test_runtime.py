"""Offline contract and integration tests; no paid API calls."""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from dynamic_mcp_server import DynamicMCPServer
from langgraph_orchestrator import LangGraphOrchestrator
from lark_bot import LarkBot, build_card
from protocol_agent import validate_webhook, https_url
from token_optimizer import TokenOptimizer, load_config, request_with_retry
from visual_cli import DashboardState


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_schema_error_preserves_id_and_prevents_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            server = DynamicMCPServer(Path(directory) / 'tools.json')
            calls = []
            server.register_new_tool('bounded', 'Validated tool', {'type': 'object', 'properties': {'n': {'type': 'integer', 'minimum': 2}}, 'required': ['n'], 'additionalProperties': False}, lambda args: calls.append(args))
            result = await server.handle({'jsonrpc': '2.0', 'id': 'original', 'method': 'tools/call', 'params': {'name': 'bounded', 'arguments': {'n': 1}}})
            self.assertEqual(result['id'], 'original')
            self.assertEqual(result['error']['code'], -32602)
            self.assertFalse(calls)
            valid = await server.handle({'id': 2, 'method': 'tools/call', 'params': {'name': 'bounded', 'arguments': {'n': 2}}})
            self.assertNotIn('isError', valid['result'])
            self.assertEqual(calls, [{'n': 2}])

    async def test_sandbox_never_falls_back_to_host(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            server = DynamicMCPServer(Path(directory) / 'tools.json')
            marker = Path(directory) / 'host-executed'
            result = await server.handle({'id': 1, 'method': 'tools/call', 'params': {'name': 'execute_python_sandbox', 'arguments': {'code': f'open({str(marker)!r}, "w").write("bad")'}}})
            self.assertTrue(result['result']['isError'])
            self.assertFalse(marker.exists())

    async def test_workflow_restart_approval_and_denial(self):
        class Model:
            def __init__(self): self.calls = 0
            async def complete(self, task, messages):
                self.calls += 1
                return 'Concrete plan' if self.calls % 2 else 'Artifact ready for review'
        with tempfile.TemporaryDirectory() as directory:
            model = Model(); path = Path(directory) / 'workflow.sqlite'
            first = LangGraphOrchestrator(model, path)
            result = await first.start('Build artifact', 'restart')
            self.assertEqual(result['status'], 'awaiting_approval')
            self.assertTrue(result['interrupts'])
            await first.close()
            second = LangGraphOrchestrator(model, path)
            try:
                result = await second.resume('restart', True)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(model.calls, 2)
                with self.assertRaises(ValueError): await second.resume('restart', True)
                await second.start('Decline artifact', 'denial')
                result = await second.resume('denial', False)
                self.assertEqual(result['status'], 'denied')
                self.assertTrue(second.memory.recent())
            finally:
                await second.close()

    async def test_router_accounts_actual_usage(self):
        def handler(request):
            payload = json.loads(request.content)
            self.assertEqual(payload['model'], 'nvidia/nemotron-3.5-lightning-30b-a3b')
            return httpx.Response(200, json={'choices': [{'message': {'content': 'verified'}}], 'usage': {'prompt_tokens': 100, 'completion_tokens': 20}})
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'NVIDIA_API_KEY': 'fixture-key'}, clear=True):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                config = load_config(); config['models']['provider_selection'] = 'configured'
                config['models']['primary'] = 'nvidia/nemotron-3-super-120b-a12b'
                config['models']['lightweight'] = 'nvidia/nemotron-3.5-lightning-30b-a3b'
                optimizer = TokenOptimizer(config=config, client=client)
                optimizer.path = Path(directory) / 'usage.json'
                optimizer.usage = dict(input_tokens=0, output_tokens=0, cost_usd=0., requests=0)
                self.assertEqual(await optimizer.complete('schema', [{'role': 'user', 'content': 'check'}]), 'verified')
                self.assertEqual(optimizer.usage['input_tokens'], 100)
                self.assertAlmostEqual(optimizer.usage['cost_usd'], 0.0)
                self.assertEqual(optimizer.route('architecture planning'), 'nvidia/nemotron-3-super-120b-a12b')

    async def test_retry_only_transient_errors(self):
        attempts = []
        def handler(request):
            attempts.append(1)
            return httpx.Response(429 if len(attempts) == 1 else 200, json={})
        with patch('token_optimizer.asyncio.sleep') as sleep:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                response = await request_with_retry(client, 'GET', 'https://example.com')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(attempts), 2)
                sleep.assert_awaited_once()
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(401))) as client:
            with self.assertRaises(httpx.HTTPStatusError):
                await request_with_retry(client, 'GET', 'https://example.com')

    async def test_lark_approval_and_owner_allowlist(self):
        card = build_card('Review artifact', 'approval', 't1')
        self.assertEqual([a['value']['approved'] for a in card['elements'][1]['actions']], [True, False])
        from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTrigger
        received = []
        async def approve(thread, decision, user): received.append((thread, decision, user))
        bot = LarkBot(load_config()['lark'], DashboardState(), on_approval=approve)
        bot.allowed = {'owner'}
        consumer = asyncio.create_task(bot._consume())
        try:
            for user in ['outsider', 'owner']:
                event = P2CardActionTrigger({'event': {'operator': {'open_id': user}, 'action': {'value': {'thread_id': 't1', 'approved': True}}}})
                bot._enqueue('approval', event)
            await asyncio.wait_for(bot.queue.join(), 2)
            self.assertEqual(received, [('t1', True, 'owner')])
        finally:
            consumer.cancel(); await asyncio.gather(consumer, return_exceptions=True)

    async def test_sdk_card_frame_acknowledgement(self):
        import lark_oapi as lark
        import lark_oapi.ws.client as sdk
        from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse
        from lark_bot import _sdk_client_type
        received, responses = [], []
        def callback(event):
            received.append(event.event.action.value)
            return P2CardActionTriggerResponse({'toast': {'type': 'info', 'content': 'Received'}})
        dispatcher = lark.EventDispatcherHandler.builder('', '').register_p2_card_action_trigger(callback).build()
        client = _sdk_client_type(sdk)('fixture-id', 'fixture-secret', event_handler=dispatcher, log_level=lark.LogLevel.ERROR)
        async def write(data): responses.append(data)
        client._write_message = write
        frame = sdk.Frame(SeqID=1, LogID=1, service=1, method=sdk.FrameType.DATA.value)
        for key, value in [(sdk.HEADER_TYPE, 'card'), (sdk.HEADER_SUM, '1'), (sdk.HEADER_SEQ, '0'), (sdk.HEADER_MESSAGE_ID, 'fixture-message')]:
            header = frame.headers.add(); header.key = key; header.value = value
        frame.payload = json.dumps({'schema': '2.0', 'header': {'event_type': 'card.action.trigger', 'event_id': 'fixture-event'}, 'event': {'operator': {'open_id': 'owner'}, 'action': {'value': {'thread_id': 'fixture', 'approved': True}}}}).encode()
        try:
            await client._handle_data_frame(frame)
            self.assertEqual(received, [{'thread_id': 'fixture', 'approved': True}])
            self.assertEqual(len(responses), 1)
            reply = sdk.Frame(); reply.ParseFromString(responses[0])
            self.assertEqual(json.loads(reply.payload)['code'], 200)
        finally:
            client._cache._cron.cancel()
            await asyncio.gather(client._cache._cron, return_exceptions=True)

    async def test_registry_hot_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tools.json'
            server = DynamicMCPServer(path)
            watcher = asyncio.create_task(server.watch_registry())
            await asyncio.sleep(0)
            path.write_text(json.dumps({'visible': {'name': 'visible', 'description': 'new', 'inputSchema': {'type': 'object'}}}))
            try:
                notice = await asyncio.wait_for(server.notifications.get(), 2)
                self.assertEqual(notice['method'], 'notifications/tools/list_changed')
                self.assertIn('visible', server.tools)
            finally:
                watcher.cancel(); await asyncio.gather(watcher, return_exceptions=True)


class BoundaryTests(unittest.TestCase):
    def test_xml_escapes_and_context_budget(self):
        import xml.etree.ElementTree as ET
        optimizer = TokenOptimizer()
        result = optimizer.compact([{'content': '<untrusted>&data'}], 1)
        ET.fromstring(result[0]['content'].split('\n', 1)[1])
        config = load_config(); config['models']['input_budget_tokens'] = 20
        optimizer.config = config
        with self.assertRaises(ValueError): optimizer.prepare([{'role': 'user', 'content': 'long ' * 100}], 'nvidia/nemotron-3-super-120b-a12b')

    def test_activation_host_and_webhook_tampering(self):
        import hashlib, hmac
        with self.assertRaises(ValueError): https_url('https://evil.example/verify', {'trusted.example'})
        with self.assertRaises(ValueError): https_url('http://trusted.example/verify')
        body = b'{"event_id":"fixture"}'; timestamp = str(int(time.time()))
        signature = hmac.new(b'fixture-secret', timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
        self.assertEqual(validate_webhook(body, timestamp, signature, 'fixture-secret')['event_id'], 'fixture')
        with self.assertRaises(ValueError): validate_webhook(body + b' ', timestamp, signature, 'fixture-secret')

    def test_mcp_transport_parse_error_and_eof(self):
        proc = subprocess.run([sys.executable, 'main.py', 'mcp'], input='not-json\n' + json.dumps({'jsonrpc': '2.0', 'id': 71, 'method': 'tools/list'}) + '\n', capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        results = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(results[0]['error']['code'], -32700)
        self.assertEqual(results[1]['id'], 71)
        self.assertTrue(results[1]['result']['tools'])


if __name__ == '__main__':
    unittest.main()
