"""Inspectable browser onboarding with explicit provider workflows.

No CAPTCHA solver or anti-bot bypass is implemented. Challenges and identity
verification are reported as blocked. Workflow JSON names selectors and actions
for the real provider UI; credentials are referenced by environment variable.
"""
from __future__ import annotations
import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import httpx
from notion_db_setup import ROOT, encrypt_secret, load_environment, private_json, store_secret
from protocol_agent import https_url

PORTALS = {
    'devhunt': 'https://devhunt.org/',
    'firecrawl': 'https://www.firecrawl.dev/',
    'composio': 'https://composio.dev/',
    'peerpush': 'https://peerpush.com/',
    # StartupAge has no verified official portal, so it is reported as
    # unverified rather than being given an address that might not be theirs.
    'startupage': None,
}
CHALLENGES = ['iframe[src*="recaptcha"]', 'iframe[src*="challenges.cloudflare.com"]', '.cf-turnstile', '[data-sitekey]']
ENV_KEYS = {'devhunt': 'DEVHUNT_API_KEY', 'firecrawl': 'FIRECRAWL_API_KEY', 'composio': 'COMPOSIO_API_KEY', 'peerpush': 'PEERPUSH_API_KEY'}


async def inspect_portal(url: str) -> dict[str, Any]:
    """Read public HTML without submitting credentials or attempting challenges."""
    https_url(url)
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.get(url)
        text = response.text[:500000].lower()
        challenge = response.status_code in (403, 429) or any(s in text for s in ('cf-chl-', 'verify you are human', 'captcha challenge'))
        return {'status': 'challenge_required' if challenge else 'reachable', 'http_status': response.status_code, 'host': urlparse(url).hostname}
    except httpx.HTTPError as exc:
        return {'status': 'unreachable', 'error_type': type(exc).__name__}


async def execute_workflow(provider: str, workflow: dict[str, Any]) -> dict[str, Any]:
    """Actions: goto, fill (env only), click, check, wait; then success/key selectors."""
    try:
        from camoufox.async_api import AsyncCamoufox
    except ImportError:
        return {'status': 'dependency_missing', 'dependency': 'camoufox'}
    url = workflow['url']
    hosts = {h.lower() for h in workflow.get('allowed_hosts', [urlparse(url).hostname])}
    https_url(url, hosts)
    for action in workflow.get('actions', []):
        if action['action'] == 'fill' and not os.getenv(action['env']):
            return {'status': 'credentials_missing', 'variable': action['env']}
    # HTTP auth passwords (GMAIL_APP_PASSWORD) are not Google sign-in passwords.
    if any(action.get('env') == 'GMAIL_APP_PASSWORD' for action in workflow.get('actions', [])):
        return {'status': 'unsupported_credentials', 'reason': 'Gmail app passwords cannot sign in to developer portals'}
    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        # Explicit provider + OAuth host allowlists contain every network request.
        async def restrict(route):
            parsed = urlparse(route.request.url)
            if parsed.scheme in ('data', 'blob') or (parsed.scheme == 'https' and parsed.hostname in hosts):
                await route.continue_()
            else:
                await route.abort()
        await page.route('**/*', restrict)
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        async def challenged() -> bool:
            for selector in CHALLENGES:
                if await page.locator(selector).count() and await page.locator(selector).first.is_visible():
                    return True
            body = (await page.locator('body').inner_text())[:20000].lower()
            return any(text in body for text in ('verify you are human', 'complete the captcha', 'security verification'))
        for action in workflow.get('actions', []):
            if await challenged():
                return {'status': 'challenge_required'}
            kind = action['action']
            if kind == 'goto':
                await page.goto(https_url(action['url'], hosts), wait_until='domcontentloaded', timeout=30000)
            elif kind == 'fill':
                await page.locator(action['selector']).fill(os.environ[action['env']], timeout=15000)
            elif kind == 'click':
                await page.locator(action['selector']).click(timeout=15000)
            elif kind == 'check':
                await page.locator(action['selector']).check(timeout=15000)
            elif kind == 'wait':
                await page.locator(action['selector']).wait_for(state='visible', timeout=min(60000, int(action.get('timeout_ms', 15000))))
            else:
                raise ValueError('Unknown workflow action')
            https_url(page.url, hosts)
        if await challenged():
            return {'status': 'challenge_required'}
        success = workflow.get('success_selector')
        if not success or not await page.locator(success).is_visible():
            return {'status': 'verification_required'}
        key_selector = workflow.get('key_selector')
        if not key_selector:
            return {'status': 'registered', 'api_key': 'not_offered_by_workflow'}
        locator = page.locator(key_selector)
        if workflow.get('key_source', 'text') == 'value':
            key = await locator.input_value()
        else:
            key = (await locator.inner_text()).strip()
        pattern = workflow.get('key_pattern')
        if not key or (pattern and not re.fullmatch(pattern, key)):
            return {'status': 'registered', 'api_key': 'extraction_failed'}
        # Save authenticated ciphertext before attempting any remote write.
        private_json(ROOT / 'data' / (provider + '_credential.enc.json'), {'provider': provider, 'encrypted': encrypt_secret(provider, key)})
        credential = ENV_KEYS.get(provider)
        if credential:
            from dotenv import set_key
            target = Path('/.env') if Path('/.env').exists() else ROOT / '.env'
            target.touch(mode=0o600, exist_ok=True)
            os.chmod(target, 0o600)
            set_key(str(target), credential, key)
            os.environ[credential] = key
        try:
            vault = await store_secret(provider, key)
            vault_status = vault['status']
        except Exception as exc:
            vault_status = 'pending:' + type(exc).__name__
        return {'status': 'registered', 'api_key': 'persisted', 'notion_vault': vault_status}


async def run_registrations() -> dict[str, Any]:
    load_environment()
    path = Path(os.getenv('REGISTRATION_WORKFLOWS_PATH', str(ROOT / 'data' / 'registration_workflows.json')))
    if not path.exists():
        from autonomous_registration import AutonomousRegistrar
        return await AutonomousRegistrar().run()
    workflows = json.loads(path.read_text())
    results = {}
    # Sequential browser sessions keep peak memory bounded. Browser memory is
    # explicitly outside the lightweight core's budget and is opt-in per workflow.
    for provider, default in PORTALS.items():
        credential = ENV_KEYS.get(provider)
        if credential and os.getenv(credential):
            results[provider] = {'status': 'credential_present'}
            continue
        workflow = workflows.get(provider)
        url = workflow.get('url') if workflow else default
        if not url:
            results[provider] = {'status': 'unverified_portal', 'reason': 'No verified official URL or workflow configured'}
            continue
        inspection = await inspect_portal(url)
        if not workflow:
            results[provider] = {**inspection, 'registration': 'workflow_required'}
            continue
        if inspection['status'] == 'challenge_required':
            results[provider] = inspection
            continue
        try:
            results[provider] = await execute_workflow(provider, workflow)
        except Exception as exc:
            # Browser exceptions can include field contents: only emit the type.
            results[provider] = {'status': 'failed', 'error_type': type(exc).__name__}
    private_json(ROOT / 'data' / 'registration_report.json', results)
    return results


if __name__ == '__main__':
    try:
        print(json.dumps(asyncio.run(run_registrations()), indent=2))
    except Exception as exc:
        print(json.dumps({'status': 'error', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
