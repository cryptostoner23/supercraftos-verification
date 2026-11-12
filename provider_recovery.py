"""Authenticated provider reconnection; keys never appear in public receipts."""
import os
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal, InvalidOperation

import httpx

from runtime_env import ROOT, _credential_valid, persist_provider_credential
from notion_db_setup import encrypt_secret, private_json

PROVIDERS = {
    'airtable': ('AIRTABLE_API_KEY', 'https://airtable.com/create/tokens', 'https://api.airtable.com/v0/meta/whoami', 'Authorization', 'Bearer '),
    'hyrve': ('HYRVE_API_KEY', 'https://app.hyrveai.com', 'https://api.hyrveai.com/v1/wallet', 'X-API-Key', ''),
    'skyfire': ('SKYFIRE_API_KEY', 'https://app.skyfire.xyz', 'https://api.skyfire.xyz/api/v1/agents/balance', 'skyfire-api-key', ''),
    'opencode_models': ('OPENCODE_GO_API_KEY', 'https://opencode.ai/auth', 'https://opencode.ai/zen/go/v1/models', 'Authorization', 'Bearer '),
    'hyperbrowser': ('HYPERBROWSER_API_KEY', 'https://app.hyperbrowser.ai', 'https://api.hyperbrowser.ai/api/sessions', 'x-api-key', ''),
    'steel': ('STEEL_API_KEY', 'https://app.steel.dev', 'https://api.steel.dev/v1/sessions', 'steel-api-key', ''),
    'firecrawl': ('FIRECRAWL_API_KEY', 'https://www.firecrawl.dev/app/api-keys', 'https://api.firecrawl.dev/v1/team/credit-usage', 'Authorization', 'Bearer '),
    'peerpush': ('PEERPUSH_API_KEY', 'https://peerpush.com', 'https://peerpush.com/api/v1/products?limit=1', 'X-PeerPush-Api-Key', ''),
}


def recovery_options(name):
    spec = PROVIDERS.get(name)
    return {'reconnect_supported': bool(spec), **({'credential_url': spec[1]} if spec else {})}


async def skyfire_balance(arguments, *, client=None):
    """Read the actual provider balance; this never creates or charges a token."""
    if arguments:
        raise ValueError('Balance lookup takes no arguments')
    from runtime_env import load_environment
    load_environment()
    key = os.getenv('SKYFIRE_API_KEY')
    if not key:
        return {'provider': 'skyfire', 'status': 'not_configured'}
    owned = client is None
    client = client or httpx.AsyncClient(proxy=os.getenv('SUPERCRAFTOS_PROVIDER_PROXY'), timeout=20, follow_redirects=False)
    try:
        response = await client.get(PROVIDERS['skyfire'][2], headers={'skyfire-api-key': key})
        if response.status_code != 200:
            return {'provider': 'skyfire', 'status': 'provider_request_failed', 'http_status': response.status_code}
        body = response.json()
        fields = ('available', 'heldAmount', 'pendingCharges', 'pendingDeposits')
        if not isinstance(body, dict) or not all(isinstance(body.get(name), str) and Decimal(body[name]).is_finite() for name in fields):
            raise ValueError('Invalid balance response')
        return {'provider': 'skyfire', 'status': 'completed', 'http_status': 200,
                'balance': {name: body[name] for name in fields}, 'checked_at': datetime.now(timezone.utc).isoformat()}
    except (httpx.HTTPError, ValueError, InvalidOperation):
        return {'provider': 'skyfire', 'status': 'balance_unavailable'}
    finally:
        if owned:
            await client.aclose()


async def reconnect(payload, *, client=None, root=ROOT):
    if set(payload) != {'provider', 'credential'} or payload.get('provider') not in PROVIDERS:
        raise ValueError('Unknown provider or invalid reconnection fields')
    provider, credential = payload['provider'], payload['credential']
    if not _credential_valid(credential):
        raise ValueError('Invalid credential format')
    variable, _, endpoint, header, prefix = PROVIDERS[provider]
    owned = client is None
    proxy = os.getenv('SUPERCRAFTOS_PROVIDER_PROXY') if provider == 'skyfire' else None
    client = client or httpx.AsyncClient(follow_redirects=False, timeout=15, proxy=proxy)
    try:
        response = await client.get(endpoint, headers={header: prefix + credential})
        code = response.status_code
        edge_challenge = code == 403 and 'text/html' in response.headers.get('content-type', '') and 'Just a moment' in response.text
        valid = False
        if code == 200:
            try:
                body = response.json()
                valid = isinstance(body, dict) and bool(body) and not body.get('error') and body.get('success') is not False
                if provider in {'steel', 'hyperbrowser', 'peerpush'} and isinstance(body, list):
                    valid = True
                if provider == 'skyfire':
                    valid = valid and all(name in body for name in ('available', 'heldAmount', 'pendingCharges', 'pendingDeposits'))
                elif provider == 'airtable':
                    valid = valid and isinstance(body.get('id'), str)
                elif provider == 'opencode_models':
                    valid = valid and isinstance(body.get('data'), list)
            except ValueError:
                pass
    except httpx.HTTPError:
        return {'provider': provider, 'status': 'connection_error', 'saved': False}
    finally:
        if owned:
            await client.aclose()
    status = 'active' if valid else 'invalid_provider_response' if code == 200 else 'network_challenge' if edge_challenge else 'authentication_rejected' if code == 401 else 'access_denied' if code == 403 else 'provider_request_failed'
    result = {'provider': provider, 'status': status, 'http_status': code,
              'saved': valid, 'checked_at': datetime.now(timezone.utc).isoformat()}
    if valid:
        # A replacement is made only after the official provider accepts it.
        root = Path(root)
        private_json(root / 'data' / f'{provider}.credential.enc.json',
                     {'provider': 'opencode-go' if provider == 'opencode_models' else provider,
                      'encrypted': encrypt_secret('opencode-go' if provider == 'opencode_models' else provider, credential)})
        persist_provider_credential(variable, credential, root / 'data/reconnected-providers.env')
        os.environ[variable] = credential
    # Keep the fresh result separate from historical connection evidence.
    private_json(Path(root) / 'data' / f'{provider}.recovery.json', result)
    return result
