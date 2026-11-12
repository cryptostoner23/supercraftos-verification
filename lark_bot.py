"""Outbound-only Lark SDK WebSocket adapter sharing the launcher's asyncio loop."""
from __future__ import annotations
import asyncio
import base64
import json
import os
import random
import time
from collections import OrderedDict
from urllib.parse import parse_qs, urlparse
import httpx
from token_optimizer import request_with_retry


def build_card(text, status='running', thread_id=None):
    colors = {'running': 'blue', 'approval': 'orange', 'complete': 'green', 'error': 'red', 'denied': 'grey'}
    elements = [{'tag': 'markdown', 'content': text[:25000]}]
    if thread_id and status == 'approval':
        elements.append({'tag': 'action', 'actions': [
            {'tag': 'button', 'text': {'tag': 'plain_text', 'content': label}, 'type': kind,
             'value': {'thread_id': thread_id, 'approved': approved}}
            for label, kind, approved in [('Approve', 'primary', True), ('Deny', 'danger', False)]]})
    return {'config': {'wide_screen_mode': True, 'update_multi': True},
            'header': {'template': colors.get(status, 'blue'), 'title': {'tag': 'plain_text', 'content': f'SuperCraftOS · {status.upper()}'}},
            'elements': elements}


def _sdk_client_type(sdk):
    class AsyncSDKClient(sdk.Client):
        async def _handle_data_frame(self, frame):
            # SDK 1.7.5 drops CARD frames. Dispatch them using its own event codec.
            if sdk._get_by_key(frame.headers, sdk.HEADER_TYPE) != sdk.MessageType.CARD.value:
                return await super()._handle_data_frame(frame)
            count = int(sdk._get_by_key(frame.headers, sdk.HEADER_SUM))
            payload = frame.payload
            if count > 1:
                payload = self._combine(sdk._get_by_key(frame.headers, sdk.HEADER_MESSAGE_ID), count, int(sdk._get_by_key(frame.headers, sdk.HEADER_SEQ)), payload)
                if payload is None:
                    return
            result = self._event_handler._do_without_validation(payload)
            response = sdk.Response(code=200)
            if result is not None:
                response.data = base64.b64encode(sdk.JSON.marshal(result).encode())
            frame.payload = sdk.JSON.marshal(response).encode()
            await self._write_message(frame.SerializeToString())
    return AsyncSDKClient


class LarkBot:
    def __init__(self, config, state, on_message=None, on_approval=None):
        self.config, self.state = config, state
        self.on_message, self.on_approval = on_message, on_approval
        self.app_id, self.app_secret = os.getenv('LARK_APP_ID'), os.getenv('LARK_APP_SECRET')
        self.allowed = set(filter(None, (s.strip() for s in os.getenv('LARK_ALLOWED_USER_IDS', '').split(','))))
        self.queue = asyncio.Queue(maxsize=128)
        self.seen = OrderedDict()
        self.token, self.expires = '', 0
        self.client = None
        self._token_lock = asyncio.Lock()

    async def _access_token(self):
        async with self._token_lock:
            if time.monotonic() < self.expires:
                return self.token
            response = await request_with_retry(self.client, 'POST', self.config['domain'] + '/open-apis/auth/v3/tenant_access_token/internal', json={'app_id': self.app_id, 'app_secret': self.app_secret})
            data = response.json()
            if data.get('code') != 0:
                raise RuntimeError('Lark token request rejected')
            self.token = data['tenant_access_token']
            self.expires = time.monotonic() + data['expire'] - 60
            return self.token

    async def _api(self, method, path, payload, params=None):
        token = await self._access_token()
        response = await request_with_retry(self.client, method, self.config['domain'] + path, headers={'Authorization': f'Bearer {token}'}, json=payload, params=params)
        data = response.json()
        if data.get('code') != 0:
            raise RuntimeError(f'Lark API rejected request (code {data.get("code")})')
        return data.get('data', {})

    async def send_card(self, chat_id, card):
        return await self._api('POST', '/open-apis/im/v1/messages', {'receive_id': chat_id, 'msg_type': 'interactive', 'content': json.dumps(card)}, {'receive_id_type': 'chat_id'})

    async def stream_card(self, message_id, text, status='complete', thread_id=None):
        # Throttled edits avoid Lark per-message request limits.
        for end in range(256, min(len(text), 25000), 256):
            await self._api('PATCH', f'/open-apis/im/v1/messages/{message_id}', {'content': json.dumps(build_card(text[:end] + ' ▍'))})
            await asyncio.sleep(self.config.get('stream_interval_seconds', 1))
        await self._api('PATCH', f'/open-apis/im/v1/messages/{message_id}', {'content': json.dumps(build_card(text, status, thread_id))})

    def _enqueue(self, kind, event):
        if not self.queue.full():
            self.queue.put_nowait((kind, event))

    async def _consume(self):
        while True:
            kind, event = await self.queue.get()
            try:
                if kind == 'message':
                    message = event.event.message
                    user = event.event.sender.sender_id.open_id
                    if user not in self.allowed or message.message_type != 'text':
                        continue
                    ident = message.message_id
                    if ident in self.seen:
                        continue
                    self.seen[ident] = True
                    while len(self.seen) > 1024:
                        self.seen.popitem(last=False)
                    text = json.loads(message.content).get('text', '')
                    if self.on_message:
                        await self.on_message(text, message.chat_id, user)
                else:
                    user = event.event.operator.open_id
                    if user not in self.allowed:
                        continue
                    value = event.event.action.value
                    if not isinstance(value.get('approved'), bool) or not isinstance(value.get('thread_id'), str):
                        continue
                    if self.on_approval:
                        await self.on_approval(value['thread_id'], value['approved'], user)
            except Exception as exc:
                self.state.event(f'Lark event failed: {type(exc).__name__}')
            finally:
                self.queue.task_done()

    async def run(self):
        if not self.app_id or not self.app_secret:
            self.state.lark = 'unconfigured'
            return
        import lark_oapi as lark
        from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse
        import lark_oapi.ws.client as sdk
        import websockets
        def card(event):
            self._enqueue('approval', event)
            return P2CardActionTriggerResponse({'toast': {'type': 'info', 'content': 'Decision received'}})
        dispatcher = lark.EventDispatcherHandler.builder('', '').register_p2_im_message_receive_v1(lambda event: self._enqueue('message', event)).register_p2_card_action_trigger(card).build()
        AsyncSDKClient = _sdk_client_type(sdk)
        async with httpx.AsyncClient(timeout=30) as client:
            self.client = client
            consumer = asyncio.create_task(self._consume())
            connection = AsyncSDKClient(self.app_id, self.app_secret, event_handler=dispatcher, domain=self.config['domain'], log_level=lark.LogLevel.ERROR, auto_reconnect=False)
            attempt = 0
            try:
                while True:
                    ping = None
                    try:
                        self.state.lark = 'connecting'
                        response = await request_with_retry(client, 'POST', self.config['domain'] + sdk.GEN_ENDPOINT_URI, json={'AppID': self.app_id, 'AppSecret': self.app_secret})
                        endpoint = response.json()
                        if endpoint.get('code') != 0:
                            raise RuntimeError('Lark WebSocket discovery rejected')
                        data = endpoint['data']; address = data['URL']
                        if urlparse(address).scheme != 'wss':
                            raise ValueError('Lark WebSocket requires TLS')
                        query = parse_qs(urlparse(address).query)
                        connection._service_id = query[sdk.SERVICE_ID][0]
                        connection._conn_id = query[sdk.DEVICE_ID][0]
                        connection._ping_interval = data.get('ClientConfig', {}).get('PingInterval', 120)
                        async with websockets.connect(address, max_size=4 * 1024 * 1024) as websocket:
                            connection._conn = websocket
                            self.state.lark = 'connected'; attempt = 0
                            ping = asyncio.create_task(connection._ping_loop())
                            async for message in websocket:
                                await connection._handle_message(message)
                    except (httpx.HTTPError, OSError, RuntimeError, ValueError, websockets.WebSocketException) as exc:
                        self.state.lark = 'reconnecting'
                        self.state.event(f'Lark connection failed: {type(exc).__name__}')
                        await asyncio.sleep(min(30, 2 ** min(attempt, 5)) + random.random()); attempt += 1
                    finally:
                        connection._conn = None
                        if ping:
                            ping.cancel(); await asyncio.gather(ping, return_exceptions=True)
            finally:
                consumer.cancel(); await asyncio.gather(consumer, return_exceptions=True)
                connection._cache._cron.cancel()
                await asyncio.gather(connection._cache._cron, return_exceptions=True)
                self.client = None
                self.state.lark = 'stopped'
