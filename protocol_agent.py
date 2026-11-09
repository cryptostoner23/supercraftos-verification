"""Async HTTPS onboarding, JMAP mail retrieval, and signed activation events.

MAILBOX_PROVISION_URL and MAILBOX_PROVISION_TOKEN describe the operator's real
provider API. No undocumented MailCat or Atomic Mail endpoints are assumed.
"""
from __future__ import annotations
import asyncio
import hashlib
import hmac
import json
import os
import random
import re
import time
from typing import Any
from urllib.parse import urlparse
import httpx
from notion_db_setup import load_environment


def https_url(url: str, allowed_hosts: set[str] | None = None) -> str:
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('An HTTPS URL without embedded credentials is required')
    if allowed_hosts is not None and parsed.hostname.lower() not in allowed_hosts:
        raise ValueError('URL host is outside the configured allowlist')
    return url


class HttpClient:
    def __init__(self, timeout: float = 20, attempts: int = 5):
        self.timeout, self.attempts = timeout, attempts

    async def request(self, url: str, method: str = 'GET', payload: Any = None, headers: dict | None = None) -> Any:
        https_url(url)
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            for attempt in range(self.attempts):
                try:
                    response = await client.request(method, url, json=payload, headers=headers)
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt + 1 < self.attempts:
                            await asyncio.sleep(min(30, 2 ** attempt) + random.random())
                            continue
                    response.raise_for_status()
                    return response.json() if response.content else {}
                except httpx.TransportError:
                    if attempt + 1 == self.attempts:
                        raise
                    await asyncio.sleep(min(30, 2 ** attempt) + random.random())
        raise RuntimeError('Request attempts exhausted')


async def provision_agent_mailbox(client: HttpClient | None = None, endpoint: str | None = None) -> dict[str, Any]:
    load_environment()
    url = endpoint or os.getenv('MAILBOX_PROVISION_URL')
    if not url:
        return {'status': 'unconfigured', 'reason': 'MAILBOX_PROVISION_URL missing'}
    token = os.getenv('MAILBOX_PROVISION_TOKEN')
    payload = json.loads(os.getenv('MAILBOX_PROVISION_PAYLOAD', '{}'))
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    return await (client or HttpClient()).request(url, 'POST', payload, headers)


async def register_via_api(endpoint: str, payload: dict[str, Any], client: HttpClient | None = None) -> dict[str, Any]:
    return await (client or HttpClient()).request(endpoint, 'POST', payload)


class JMAPMailbox:
    def __init__(self, session_url: str, token: str):
        self.session_url = https_url(session_url)
        self.headers = {'Authorization': 'Bearer ' + token}
        self.client = HttpClient()
        self.session: dict[str, Any] | None = None

    async def discover(self) -> dict[str, Any]:
        self.session = await self.client.request(self.session_url, headers=self.headers)
        # The trusted session document delegates its apiUrl, as specified by JMAP.
        https_url(self.session['apiUrl'])
        return self.session

    async def messages(self, limit: int = 20) -> list[dict[str, Any]]:
        session = self.session or await self.discover()
        account = session['primaryAccounts']['urn:ietf:params:jmap:mail']
        response = await self.client.request(session['apiUrl'], 'POST', {
            'using': ['urn:ietf:params:jmap:core', 'urn:ietf:params:jmap:mail'],
            'methodCalls': [
                ['Email/query', {'accountId': account, 'sort': [{'property': 'receivedAt', 'isAscending': False}], 'limit': min(limit, 100)}, 'q'],
                ['Email/get', {'accountId': account, '#ids': {'resultOf': 'q', 'name': 'Email/query', 'path': '/ids'}, 'properties': ['id', 'subject', 'receivedAt', 'textBody', 'htmlBody', 'bodyValues'], 'fetchAllBodyValues': True, 'maxBodyValueBytes': 65536}, 'g'],
            ]}, self.headers)
        for name, data, _ in response['methodResponses']:
            if name == 'error':
                raise RuntimeError('JMAP method failed: ' + data.get('type', 'unknown'))
            if name == 'Email/get':
                return data['list']
        raise RuntimeError('JMAP response omitted Email/get')


async def poll_and_verify_account(mailbox: JMAPMailbox, allowed_hosts: set[str], timeout: float = 120, subject_contains: str = '') -> dict[str, Any]:
    """Activate only links on an explicit provider allowlist; never follow redirects."""
    if not allowed_hosts:
        raise ValueError('An activation host allowlist is required')
    allowed_hosts = {host.lower() for host in allowed_hosts}
    deadline = time.monotonic() + timeout
    started = time.time() - 30
    while time.monotonic() < deadline:
        for message in await mailbox.messages():
            if subject_contains.lower() not in message.get('subject', '').lower():
                continue
            from datetime import datetime
            received = message.get('receivedAt')
            if not received or datetime.fromisoformat(received.replace('Z', '+00:00')).timestamp() < started:
                continue
            body = '\n'.join(part.get('value', '') for part in message.get('bodyValues', {}).values())
            for link in re.findall(r'https://[^\s<>"\']+', body):
                import html
                link = html.unescape(link)
                if not re.search(r'verify|activate|confirm', link, re.I):
                    continue
                try:
                    https_url(link, allowed_hosts)
                except ValueError:
                    continue
                async with httpx.AsyncClient(follow_redirects=False, timeout=20) as client:
                    result = await client.get(link)
                    result.raise_for_status()
                return {'status': 'activation_requested', 'message_id': message['id'], 'host': urlparse(link).hostname}
        await asyncio.sleep(min(3, max(0, deadline - time.monotonic())))
    raise TimeoutError('No matching activation message received')


def validate_webhook(body: bytes, timestamp: str, signature: str, secret: str, tolerance: int = 300) -> dict[str, Any]:
    """Validate HMAC-SHA256(timestamp + '.' + raw body) before parsing an event.

    Caller must durably deduplicate event IDs before applying side effects. This
    format must match the configured provider adapter's signature contract.
    """
    if not secret or abs(time.time() - int(timestamp)) > tolerance:
        raise ValueError('Invalid webhook timestamp or secret')
    expected = hmac.new(secret.encode(), timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature.removeprefix('sha256=')):
        raise ValueError('Invalid webhook signature')
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError('Webhook event must be an object')
    return value


async def process_activation_webhook(body: bytes, timestamp: str, signature: str, secret: str, allowed_hosts: set[str]) -> dict[str, Any]:
    """Process an adapter-normalized signed event without opening an inbound port.

    Event fields are id and activation_url. Persist successful IDs to prevent
    replay. A crash after submitting a request leaves an in-flight receipt for
    inspection rather than resubmitting an activation with unknown outcome.
    """
    import sqlite3
    from notion_db_setup import ROOT
    event = validate_webhook(body, timestamp, signature, secret)
    ident = event.get('id')
    if not isinstance(ident, str) or not ident or len(ident) > 256:
        raise ValueError('Activation event requires a bounded string id')
    if not allowed_hosts:
        raise ValueError('An activation host allowlist is required')
    url = https_url(event['activation_url'], {host.lower() for host in allowed_hosts})
    path = ROOT / 'data' / 'activation_receipts.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS receipts (id TEXT PRIMARY KEY, status TEXT NOT NULL)')
        row = db.execute('SELECT status FROM receipts WHERE id=?', (ident,)).fetchone()
        if row:
            return {'status': 'duplicate', 'previous_status': row[0], 'event_id': ident}
        db.execute('INSERT INTO receipts VALUES (?, ?)', (ident, 'in_flight'))
    os.chmod(path, 0o600)
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=20) as client:
            response = await client.get(url)
            response.raise_for_status()
    except Exception:
        with sqlite3.connect(path) as db:
            db.execute('UPDATE receipts SET status=? WHERE id=?', ('outcome_unknown', ident))
        raise
    with sqlite3.connect(path) as db:
        db.execute('UPDATE receipts SET status=? WHERE id=?', ('submitted', ident))
    return {'status': 'activation_requested', 'event_id': ident}


if __name__ == '__main__':
    load_environment()
    # Provisioning responses may contain passwords; only report their status.
    try:
        result = asyncio.run(provision_agent_mailbox())
        print(json.dumps({'status': result.get('status', 'provision_response_received')}))
    except Exception as exc:
        print(json.dumps({'status': 'error', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
