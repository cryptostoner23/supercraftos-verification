"""On-demand DevHunt profile workflow using its website, not an API key.

The private browser profile retains the official OAuth session. No language
model, persistent browser daemon, invented API endpoint or paid service is used.
"""
import asyncio
import fcntl
import os
import re
import time
from urllib.parse import urljoin, urlparse

from notion_db_setup import private_json
from runtime_env import ROOT

LOGIN = 'https://devhunt.org/login'


def profile_url(value):
    url = urlparse(urljoin('https://devhunt.org', value or ''))
    if (url.scheme != 'https' or url.hostname != 'devhunt.org' or url.username
            or url.password or url.port or url.query or url.fragment
            or not re.fullmatch(r'/(?:u|user|users|profile|settings|account)(?:/[A-Za-z0-9_-]+)*/?', url.path)):
        raise ValueError('The profile must be a DevHunt profile or account page')
    return url.geturl()


async def drive_profile(page, *, update_name=False, name='HSK'):
    """Use visible account/profile controls; OAuth sign-in is separate evidence."""
    await page.goto(LOGIN, wait_until='domcontentloaded', timeout=25000)
    # Allow hydration before checking auth controls; no optimistic success on HTML.
    await page.locator('body').wait_for()
    login = page.get_by_role('button', name=re.compile(r'^Continue with (Google|Github)$', re.I))
    if await login.count():
        return {'status': 'browser_signin_required', 'reason':
                'DevHunt uses Google or GitHub sign-in. The browser profile is not signed in; no DevHunt API key is required.',
                'authentication_url': LOGIN}
    current = urlparse(page.url)
    if current.hostname != 'devhunt.org':
        return {'status': 'browser_signin_required', 'reason': 'The official identity provider requires sign-in.',
                'authentication_url': LOGIN}
    links = await page.locator('a[href]').evaluate_all('els => els.map(e => ({href:e.getAttribute("href"),label:e.innerText.trim()}))')
    choices = [item for item in links if re.fullmatch(r'(?:My |Your |Edit )?Profile|Account settings|Settings', item['label'], re.I)]
    if choices:
        target = profile_url(choices[0]['href'])
        await page.goto(target, wait_until='domcontentloaded', timeout=25000)
    else:
        try:
            target = profile_url(page.url)
        except ValueError:
            return {'status': 'profile_controls_unavailable', 'reason': 'No authenticated profile controls were found. No profile change was submitted.'}
    field = page.get_by_role('textbox', name=re.compile(r'^(?:Display name|Name|Full name)$', re.I))
    if await field.count() != 1:
        return {'status': 'profile_controls_unavailable', 'reason': 'The authenticated profile name field is unavailable. No profile change was submitted.'}
    if update_name:
        await field.fill(name)
        save = page.get_by_role('button', name=re.compile(r'^(?:Save|Save changes|Update profile)$', re.I))
        if await save.count() != 1:
            return {'status': 'profile_controls_unavailable', 'reason': 'The profile save action is unavailable. No profile change was submitted.'}
        await save.click(timeout=15000)
        # A click is not a saved profile: reload and read the persisted field.
        await page.wait_for_load_state('networkidle', timeout=15000)
        await page.reload(wait_until='domcontentloaded', timeout=25000)
        await field.wait_for()
        if await field.input_value() != name:
            return {'status': 'profile_save_failed', 'reason': 'The website did not retain the requested public name.'}
    return {'status': 'verified_profile', 'profile_url': target,
            'public_name': await field.input_value(),
            'reason': 'Authenticated DevHunt profile controls were read' + (' and the saved name was reloaded.' if update_name else '.')}


async def manage_devhunt_profile(arguments, *, session_factory=None):
    if (not isinstance(arguments, dict) or set(arguments) - {'update_name'}
            or type(arguments.get('update_name', False)) is not bool):
        raise ValueError('Use only the optional update_name boolean')
    directory = ROOT / 'data/web-profiles'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(directory / 'browser.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'provider': 'devhunt', 'status': 'already_running', 'reason': 'The private browser profile is in use.'}
        from playwright.async_api import async_playwright
        os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(ROOT / 'data/browser'))
        try:
            async with asyncio.timeout(80), async_playwright() as playwright:
                factory = session_factory or playwright.chromium.launch_persistent_context
                proxy = os.getenv('SUPERCRAFTOS_PROVIDER_PROXY')
                context = await factory(str(ROOT / 'data/autonomous/bootstrap-profile'),
                    headless=True, args=['--no-sandbox'], proxy={'server': proxy.replace('socks5h:', 'socks5:')} if proxy else None)
                try:
                    page = await context.new_page()
                    async def navigation(route):
                        if route.request.is_navigation_request() and urlparse(route.request.url).hostname != 'devhunt.org':
                            await route.abort()
                        else:
                            await route.continue_()
                    await context.route('**/*', navigation)
                    result = await drive_profile(page, update_name=arguments.get('update_name', False))
                finally:
                    await context.close()
        except Exception as error:
            result = {'status': 'browser_flow_failed', 'reason': 'The profile browser could not complete the operation.', 'error_type': type(error).__name__}
        result.update(provider='devhunt', checked_at=int(time.time()), authentication_method='browser_session')
        private_json(directory / 'devhunt.json', result)
        return result


def tool():
    return {'name': 'manage_devhunt_profile',
            'description': 'Use the DevHunt website to read the signed-in public profile or save the public name HSK. No DevHunt API key is used. Retains the private browser session and reports actual OAuth sign-in requirements.',
            'inputSchema': {'type': 'object', 'properties': {'update_name': {'type': 'boolean', 'default': False}}, 'additionalProperties': False}}
