"""Cloud-first browser sessions; the browser agent owns every interaction."""
from __future__ import annotations
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from runtime_env import ROOT, load_environment


class CloudUnavailable(RuntimeError):
    pass


@asynccontextmanager
async def browser_session(*, bootstrap=False):
    """Hyperbrowser first, Steel second; local use is limited to cloud signup."""
    load_environment()
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(ROOT / 'data' / 'browser'))
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        key = os.getenv('HYPERBROWSER_API_KEY')
        steel_key = os.getenv('STEEL_API_KEY')
        backend, sdk, session, browser, context = None, None, None, None, None
        started = time.monotonic()
        try:
            if key:
                from hyperbrowser import AsyncHyperbrowser
                sdk = AsyncHyperbrowser(api_key=key)
                session = await sdk.sessions.create({'use_stealth': True, 'use_proxy': False, 'solve_captchas': False, 'enable_web_recording': False, 'enable_log_capture': False, 'timeout_minutes': 5})
                address = session.ws_endpoint
                if urlparse(address).scheme != 'wss':
                    raise ValueError('Cloud CDP endpoint must use TLS')
                browser = await playwright.chromium.connect_over_cdp(address, timeout=30000)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                backend = 'hyperbrowser'
            elif steel_key:
                from steel import AsyncSteel
                sdk = AsyncSteel(steel_api_key=steel_key)
                session = await sdk.sessions.create(solve_captcha=False, use_proxy=False, inactivity_timeout=60000, api_timeout=30000, stealth_config={'auto_captcha_solving': False})
                address = f'wss://connect.steel.dev?apiKey={steel_key}&sessionId={session.id}'
                browser = await playwright.chromium.connect_over_cdp(address, timeout=30000)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                backend = 'steel'
            elif bootstrap or os.getenv('SUPERCRAFTOS_CLOUD_ACTOR') == '1':
                profile = ROOT / 'data' / 'autonomous' / 'bootstrap-profile'
                profile.mkdir(parents=True, exist_ok=True, mode=0o700)
                context = await playwright.chromium.launch_persistent_context(
                    str(profile), headless=True, args=['--no-sandbox'],
                    accept_downloads=False, viewport={'width': 1440, 'height': 900}, is_mobile=False,
                )
                backend = 'apify-cloud' if os.getenv('SUPERCRAFTOS_CLOUD_ACTOR') == '1' else 'local-cloud-account-bootstrap'
            else:
                raise CloudUnavailable('No authenticated cloud browser backend is available')
            yield context, {'backend': backend, 'startup_seconds': round(time.monotonic() - started, 3)}
        finally:
            if context is not None and backend in {'local-cloud-account-bootstrap', 'apify-cloud'}:
                await context.close()
            elif browser is not None:
                await browser.close()
            if session is not None:
                try:
                    if backend == 'steel' or (backend is None and steel_key and not key):
                        await sdk.sessions.release(session.id)
                    else:
                        await sdk.sessions.stop(session.id)
                finally:
                    close = getattr(sdk, 'close', None)
                    if close is not None:
                        await close()
