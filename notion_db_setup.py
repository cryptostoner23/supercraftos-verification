"""Resumable Notion provisioning and authenticated encrypted credential storage."""
from __future__ import annotations
import asyncio
import base64
import json
import os
import random
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_env import load_environment
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'data' / 'notion_databases.json'
SOURCES = ROOT / 'data' / 'notion_data_sources.json'
ENV_NAMES = {'credentials_vault': 'NOTION_VAULT_DB_ID'}
SCHEMAS = {
    'credentials_vault': ('Credentials Vault', {'Name': 'title', 'Provider': 'rich_text', 'Encrypted Secret': 'rich_text', 'Created': 'date'}),
}



def private_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(value, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _client():
    from notion_client import AsyncClient
    token = os.getenv('NOTION_API_KEY') or os.getenv('NOTION_TOKEN')
    if not token:
        raise RuntimeError('NOTION_API_KEY is not configured')
    return AsyncClient(auth=token, notion_version='2026-03-11')


async def notion_request(operation, **kwargs):
    """Five attempts with jitter for transient failures in notion-client 2.x."""
    import httpx
    from notion_client.errors import APIResponseError, RequestTimeoutError
    for attempt in range(5):
        try:
            return await operation(**kwargs)
        except (APIResponseError, RequestTimeoutError, httpx.TransportError) as exc:
            if isinstance(exc, APIResponseError) and exc.status != 429 and exc.status < 500:
                raise
            if attempt == 4:
                raise
            await asyncio.sleep(min(30, 2 ** attempt) + random.random())


async def discover_parent(client):
    """Reuse a dedicated page, or create one inside an accessible project planner."""
    result = await notion_request(client.search, filter={'property': 'object', 'value': 'page'}, page_size=100)
    pages = result['results']
    def title(page):
        return ''.join(t.get('plain_text', '') for prop in page.get('properties', {}).values()
                       if isinstance(prop, dict) and prop.get('type') == 'title' for t in prop.get('title', []))
    dedicated = [p for p in pages if title(p).strip().casefold() == 'supercraftos']
    if dedicated:
        return dedicated[0]['id']
    planners = [p for p in pages if title(p).strip().casefold() in {'project planner', 'projects', 'agent workspace'}]
    if len(planners) != 1:
        return None
    created = await notion_request(client.pages.create, parent={'page_id': planners[0]['id']}, properties={
        'title': {'type': 'title', 'title': [{'type': 'text', 'text': {'content': 'SuperCraftOS'}}]}})
    return created['id']


async def setup_from_env() -> dict[str, Any]:
    """Create missing DBs, persist each ID immediately, then establish relations."""
    load_environment()
    if not (os.getenv('NOTION_API_KEY') or os.getenv('NOTION_TOKEN')):
        return {'status': 'unconfigured', 'reason': 'NOTION_API_KEY missing'}
    parent = os.getenv('NOTION_PARENT_PAGE_ID')
    ids = json.loads(STATE.read_text()) if STATE.exists() else {}
    sources = json.loads(SOURCES.read_text()) if SOURCES.exists() else {}
    async with _client() as client:
        if not parent:
            parent = await discover_parent(client)
            if not parent:
                return {'status': 'unconfigured', 'reason': 'No dedicated or project-planner parent page available'}
            from dotenv import set_key
            for env_file in (Path('/root/.env'), ROOT / '.env'):
                env_file.touch(mode=0o600, exist_ok=True); env_file.chmod(0o600)
                set_key(str(env_file), 'NOTION_PARENT_PAGE_ID', parent)
            os.environ['NOTION_PARENT_PAGE_ID'] = parent
        for key, (title, fields) in SCHEMAS.items():
            configured = os.getenv(ENV_NAMES[key]) or os.getenv('NOTION_' + key.upper() + '_DB_ID')
            if configured:
                ids[key] = configured
            if key not in ids:
                # Discover already created children after interrupted setup.
                cursor = None
                while True:
                    args = {'block_id': parent, 'page_size': 100}
                    if cursor:
                        args['start_cursor'] = cursor
                    children = await notion_request(client.blocks.children.list, **args)
                    for child in children['results']:
                        if child.get('type') == 'child_database' and child['child_database']['title'] == title:
                            ids[key] = child['id']
                    if key in ids or not children.get('has_more'):
                        break
                    cursor = children['next_cursor']
            if key not in ids:
                result = await notion_request(client.databases.create,
                    parent={'type': 'page_id', 'page_id': parent},
                    title=[{'type': 'text', 'text': {'content': title}}],
                    initial_data_source={'properties': {name: {kind: {}} for name, kind in fields.items()}},
                )
                ids[key] = result['id']
            private_json(STATE, ids)
            database = await notion_request(client.databases.retrieve, database_id=ids[key])
            sources[key] = database['data_sources'][0]['id']
            private_json(SOURCES, sources)
        for key in SCHEMAS:
            relations = {
                'Related ' + SCHEMAS[target][0]: {'relation': {'data_source_id': sources[target], 'type': 'single_property', 'single_property': {}}}
                for target in SCHEMAS if target != key
            }
            await notion_request(client.data_sources.update,data_source_id=sources[key], properties=relations)
    # A local dotenv records IDs only; root credentials are never copied.
    from dotenv import set_key
    env_file = ROOT / '.env'
    env_file.touch(mode=0o600, exist_ok=True)
    os.chmod(env_file, 0o600)
    for key, ident in ids.items():
        name = ENV_NAMES[key]
        set_key(str(env_file), name, ident)
        os.environ[name] = ident
    return {'status': 'ready', 'databases': ids}


def encrypt_secret(provider: str, secret: str) -> str:
    """AES-256-GCM with provider as authenticated associated data."""
    key_file = ROOT / 'data' / 'vault.key'
    key_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(secrets.token_bytes(32))
    os.chmod(key_file, 0o600)
    key = key_file.read_bytes()
    if len(key) != 32:
        raise ValueError('Vault key must contain exactly 32 bytes')
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key).encrypt(nonce, secret.encode(), provider.encode())
    return json.dumps({'algorithm': 'AES-256-GCM', 'nonce': base64.b64encode(nonce).decode(), 'ciphertext': base64.b64encode(ciphertext).decode()}, separators=(',', ':'))


def _provider_env_map() -> dict[str, str]:
    """Merge every known provider -> env-variable inventory.

    Combines the integration-key inventory used by sync_environment_vault with the
    registration providers from autonomous_registration. A lazy import avoids a
    module-import cycle (runtime_env <- notion_db_setup <- autonomous_registration).
    """
    inventory = {
        'context-dev': 'CONTEXT_DEV_API_KEY', 'aiflowchart': 'AIFLOWCHART_API_KEY',
        'llmgrid': 'LLMGRID_API_KEY', 'nitrostack': 'NITROSTACK_API_KEY',
        'opencode-go': 'OPENCODE_GO_API_KEY', 'nvidia': 'NVIDIA_API_KEY', 'zerox': 'ZEROX_API_KEY',
        'dune': 'DUNE_API_KEY', 'graph': 'GRAPH_API_KEY', 'apify': 'APIFY_API_TOKEN',
        'hyrve': 'HYRVE_API_KEY', 'browserless': 'BROWSERLESS_API_KEY', 'tavily': 'TAVILY_API_KEY',
        'notion': 'NOTION_API_KEY', 'airtable': 'AIRTABLE_API_KEY', 'skyfire': 'SKYFIRE_API_KEY',
        'composio': 'COMPOSIO_API_KEY', 'hyperbrowser': 'HYPERBROWSER_API_KEY',
        'steel': 'STEEL_API_KEY', 'firecrawl': 'FIRECRAWL_API_KEY', 'peerpush': 'PEERPUSH_API_KEY',
    }
    try:
        from autonomous_registration import PROVIDERS as REG_PROVIDERS
    except Exception:
        REG_PROVIDERS = {}
    for provider, meta in REG_PROVIDERS.items():
        inventory[provider] = meta['env']
    return inventory


def _vault_key() -> bytes | None:
    """Return the 32-byte AES key from data/vault.key, or None if absent/invalid."""
    key_file = ROOT / 'data' / 'vault.key'
    if not key_file.exists():
        return None
    key = key_file.read_bytes()
    return key if len(key) == 32 else None


def restore_environment_secrets() -> dict[str, int]:
    """Decrypt locally-stored provider credentials into the live process env.

    Only fills env variables that are NOT already set, so an explicit process
    environment or a .env value always wins. Never writes secrets back to disk,
    never logs them, and reads only the gitignored data/vault.key plus
    data/*.credential.enc.json artifacts. Returns a non-sensitive summary."""
    key = _vault_key()
    if not key:
        return {'restored': 0, 'reason': 'no_vault_key'}
    env_map = _provider_env_map()
    restored = 0
    skipped_unknown = 0
    for path in (list((ROOT / 'data').glob('*.credential.enc.json')) +
                 list((ROOT / 'data' / 'autonomous').glob('*.credential.enc.json'))):
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        provider = record.get('provider')
        encrypted = record.get('encrypted')
        if provider not in env_map:
            if provider:
                skipped_unknown += 1
            continue
        try:
            envelope = json.loads(encrypted)
            nonce = base64.b64decode(envelope['nonce'])
            ciphertext = base64.b64decode(envelope['ciphertext'])
            secret = AESGCM(key).decrypt(nonce, ciphertext, provider.encode()).decode()
        except Exception:
            continue
        env_name = env_map[provider]
        if not os.environ.get(env_name):
            os.environ[env_name] = secret
            restored += 1
    summary = {'restored': restored, 'skipped_unknown_provider': skipped_unknown}
    private_json(ROOT / 'data' / 'vault_restore.json', summary)
    return summary


async def store_secret(provider: str, secret: str) -> dict[str, str]:
    if not provider or not secret:
        raise ValueError('Provider and secret are required')
    load_environment()
    ident = os.getenv('NOTION_VAULT_DB_ID') or os.getenv('NOTION_CREDENTIALS_VAULT_DB_ID')
    if not ident and STATE.exists():
        ident = json.loads(STATE.read_text()).get('credentials_vault')
    if not ident:
        raise RuntimeError('Credentials Vault is not configured; run setup first')
    sources = json.loads(SOURCES.read_text()) if SOURCES.exists() else {}
    source = sources.get('credentials_vault')
    if not source:
        async with _client() as client:
            database = await notion_request(client.databases.retrieve, database_id=ident)
            source = database['data_sources'][0]['id']
    encrypted = encrypt_secret(provider, secret)
    pieces = [{'type': 'text', 'text': {'content': encrypted[i:i+1900]}} for i in range(0, len(encrypted), 1900)]
    if len(pieces) > 100:
        raise ValueError('Secret exceeds Notion property size limit')
    properties = {
        'Name': {'title': [{'text': {'content': provider}}]},
        'Provider': {'rich_text': [{'text': {'content': provider}}]},
        'Encrypted Secret': {'rich_text': pieces},
        'Created': {'date': {'start': datetime.now(timezone.utc).isoformat()}},
    }
    async with _client() as client:
        existing = await notion_request(client.data_sources.query, data_source_id=source, filter={'property': 'Provider', 'rich_text': {'equals': provider}}, page_size=1)
        if existing['results']:
            result = await notion_request(client.pages.update, page_id=existing['results'][0]['id'], properties=properties)
        else:
            result = await notion_request(client.pages.create, parent={'type': 'data_source_id', 'data_source_id': source}, properties=properties)
    return {'status': 'stored', 'page_id': result['id']}


async def sync_environment_vault():
    """Upsert only the explicit integration credential inventory as ciphertext."""
    load_environment()
    inventory = {
        'context-dev':'CONTEXT_DEV_API_KEY', 'aiflowchart':'AIFLOWCHART_API_KEY',
        'llmgrid':'LLMGRID_API_KEY', 'nitrostack':'NITROSTACK_API_KEY',
        'opencode-go':'OPENCODE_GO_API_KEY', 'nvidia':'NVIDIA_API_KEY', 'zerox':'ZEROX_API_KEY',
        'dune':'DUNE_API_KEY', 'graph':'GRAPH_API_KEY', 'apify':'APIFY_API_TOKEN',
        'hyrve':'HYRVE_API_KEY', 'browserless':'BROWSERLESS_API_KEY', 'tavily':'TAVILY_API_KEY',
        'notion':'NOTION_API_KEY', 'airtable':'AIRTABLE_API_KEY', 'skyfire':'SKYFIRE_API_KEY',
        'composio':'COMPOSIO_API_KEY', 'hyperbrowser':'HYPERBROWSER_API_KEY',
        'steel':'STEEL_API_KEY', 'firecrawl':'FIRECRAWL_API_KEY', 'peerpush':'PEERPUSH_API_KEY',
    }
    results = {}
    for provider, variable in inventory.items():
        if os.getenv(variable):
            result = await store_secret(provider, os.environ[variable])
            results[provider] = result['status']
    private_json(ROOT / 'data' / 'vault_sync.json', results)
    return results


if __name__ == '__main__':
    try:
        print(json.dumps(asyncio.run(setup_from_env()), indent=2))
    except Exception as exc:
        print(json.dumps({'status': 'error', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
