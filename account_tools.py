"""Bounded account registration with native verification and durable no-replay intent.

Catalog reads never contact providers. Only an explicit registration tool call may
verify a configured key or invoke the existing browser registrar. Public receipts
contain classifications and check metadata, never credentials or browser contents.
"""
from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROVIDERS = {
    'hyperbrowser': ('Hyperbrowser', 'https://www.hyperbrowser.ai/', 'HYPERBROWSER_API_KEY'),
    'steel': ('Steel', 'https://steel.dev/', 'STEEL_API_KEY'),
    'firecrawl': ('Firecrawl', 'https://www.firecrawl.dev/signin', 'FIRECRAWL_API_KEY'),
    'peerpush': ('PeerPush', 'https://peerpush.com/api-reference', 'PEERPUSH_API_KEY'),
    'devhunt': ('DevHunt', 'https://devhunt.org/', 'DEVHUNT_API_KEY'),
}
CHECK_ENDPOINTS = {
    'hyperbrowser': 'https://api.hyperbrowser.ai/api/sessions',
    'steel': 'https://api.steel.dev/v1/sessions',
    'firecrawl': 'https://api.firecrawl.dev/v1/team/credit-usage',
    'peerpush': 'https://peerpush.com/api/v1/products?limit=1',
}
REASONS = {
    'not_configured': 'No provider credential or registration receipt is recorded.',
    'configured_unverified': 'A credential is configured; an authenticated provider check is required.',
    'verified_existing': 'The configured credential passed an authenticated provider API check. No signup was attempted.',
    'verified_new': 'The acquired credential passed an authenticated provider API check and is stored privately on the server.',
    'verification_failed': 'The configured credential did not pass verification. Existing accounts are not replaced by a new signup.',
    'verification_unavailable': 'No supported native authenticated verification endpoint is established for this provider. Registration is blocked until one is available.',
    'verification_required': 'The previous operation may have submitted an account or created a key. Reconcile with the provider before retrying; automatic replay is disabled.',
    'in_progress': 'An account operation was reserved. Its provider outcome is not yet verified.',
    'already_running': 'Another operation owns this provider. Follow its task or refresh the receipt.',
    'email_verification_required': 'An existing submission requires email verification. Duplicate signup is suppressed.',
    'registration_submission_pending': 'A previous account submission is pending. Duplicate signup is suppressed.',
    'captcha_required': 'The provider requires a human challenge. No verified credential was obtained.',
    'identity_verification_required': 'The existing identity requires verification. No new identity will be created.',
    'existing_google_identity_required': 'A usable existing Google identity is required; identity creation is outside this operation.',
    'platform_verification_block': 'The provider blocked automated identity verification. No success is claimed.',
    'browser_security_rejected': 'Google rejected this browser during sign-in: “This browser or app may not be secure.” The existing account uses Google sign-in; this is not a pending email-verification code.',
    'cloud_credentials_unavailable': 'A configured cloud browser is required for this provider. Cloud-account providers can use the existing bootstrap path.',
    'capability_unavailable': 'The server registration dependencies or browser runtime are unavailable.',
    'configuration_error': 'The configured credential is invalid for an authenticated request.',
}
SAFE_TO_RETRY = {'cloud_credentials_unavailable', 'capability_unavailable'}


class AccountError(ValueError):
    pass


def _environment(environ):
    if environ is not None:
        return environ
    from runtime_env import load_environment
    load_environment()
    return os.environ


def _read(path):
    try:
        with path.open() as handle:
            raw = handle.read(262145)
        if len(raw) > 262144:
            raise ValueError('receipt size')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError('receipt shape')
        return value
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, RecursionError):
        return {'status': 'verification_required', 'registration_claimed': True}


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, separators=(',', ':'), allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _fingerprint(key):
    return hashlib.sha256(key.encode()).hexdigest() if isinstance(key, str) and key else None


def _public(provider, state, *, key=None, override=None):
    status = override or state.get('status', 'configured_unverified' if key else 'not_configured')
    if not isinstance(status, str) or status not in REASONS:
        status = 'verification_required'
    verified = (status in {'verified_existing', 'verified_new'} and state.get('credential_verified') is True
                and bool(key) and state.get('credential_fingerprint') == _fingerprint(key))
    if status in {'verified_existing', 'verified_new'} and not verified:
        status = 'configured_unverified' if key else 'verification_required'
    checked_at = state.get('checked_at')
    checked_at = checked_at if type(checked_at) in (int, float) and 0 < checked_at < 10**12 else None
    attempt = state.get('attempt_id')
    attempt = attempt if isinstance(attempt, str) and re.fullmatch(r'[0-9a-f]{32}', attempt) else None
    checks = []
    check = state.get('check')
    if isinstance(check, dict) and isinstance(check.get('status'), str) and check.get('status') in {'passed', 'failed', 'error', 'unsupported'}:
        checks.append({'kind': 'authenticated_provider_api', 'status': check['status'],
                       'method': 'GET', 'endpoint': CHECK_ENDPOINTS.get(provider), 'checked_at': checked_at})
    return {'provider': provider, 'status': status, 'credential_verified': verified,
            'credential_present': bool(key), 'attempt_id': attempt, 'checked_at': checked_at,
            'registration_attempted': state.get('registration_claimed') is True,
            'reason': REASONS[status], 'checks': checks}


def _prior_registration(data_dir, provider, state):
    if state.get('registration_claimed'):
        if state.get('status') in ('email_verification_required', 'registration_submission_pending',
                                  'captcha_required', 'identity_verification_required',
                                  'existing_google_identity_required', 'platform_verification_block', 'browser_security_rejected'):
            return state['status']
        return 'verification_required'
    checkpoint = _read(data_dir / 'autonomous' / f'{provider}.checkpoint.json')
    if not checkpoint:
        return None
    result = checkpoint.get('result')
    if not isinstance(result, dict):
        result = {}
    status = result.get('status') or checkpoint.get('status')
    if not isinstance(status, str):
        return 'verification_required'
    if status in SAFE_TO_RETRY:
        return None
    if status in {'email_verification_required', 'registration_submission_pending', 'captcha_required',
                  'identity_verification_required', 'existing_google_identity_required', 'platform_verification_block', 'browser_security_rejected'}:
        return status
    # Incomplete, legacy, malformed, or unverified checkpoint: do not infer that
    # no signup happened from the absence of a terminal success record.
    return 'verification_required'


async def _verify(provider, key):
    from autonomous_registration import verify_key
    return await verify_key(provider, key)


def _registrar():
    from autonomous_registration import BrowserRegistrationAgent
    return BrowserRegistrationAgent()


def website_receipt(result):
    """Website authentication is distinct from an authenticated API credential."""
    from devhunt_profile import profile_url
    verified = result.get('status') == 'verified_profile'
    endpoint = profile_url(result.get('profile_url')) if verified else 'https://devhunt.org/login'
    return {'provider': 'devhunt', 'status': 'verified_profile' if verified else 'browser_signin_required',
            'credential_verified': False, 'credential_present': False,
            'authentication_method': 'browser_session', 'profile_url': endpoint,
            'attempt_id': None, 'checked_at': result.get('checked_at'), 'registration_attempted': False,
            'reason': result.get('reason', 'Continue the website profile workflow.'),
            'checks': [{'kind': 'authenticated_provider_website', 'status': 'passed' if verified else 'pending',
                        'method': 'GET', 'endpoint': endpoint, 'checked_at': result.get('checked_at')}]}


async def register_developer_account(value, *, data_dir=None, environ=None, verifier=None, registrar_factory=None, profile_runner=None):
    """Verify existing credentials first; reserve one browser attempt per provider.

    Optional keyword dependencies support offline tests only. Public tool input
    is exactly {"provider": one of PROVIDERS}. No caller-supplied URLs or keys.
    """
    if (not isinstance(value, dict) or set(value) != {'provider'} or
            not isinstance(value.get('provider'), str) or value['provider'] not in PROVIDERS):
        raise AccountError('provider must name one supported developer platform')
    provider = value['provider']
    if provider == 'devhunt':
        from devhunt_profile import manage_devhunt_profile
        runner = profile_runner or manage_devhunt_profile
        return website_receipt(await runner({'update_name': True}))
    data_dir = Path(data_dir) if data_dir is not None else ROOT / 'data'
    directory = data_dir / 'accounts'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / f'{provider}.json'
    env = _environment(environ)
    env_name = PROVIDERS[provider][2]
    key = env.get(env_name)
    fd = os.open(directory / f'{provider}.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as lock:
        os.fchmod(lock.fileno(), 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return _public(provider, _read(path), key=key, override='already_running')
        state = _read(path)
        verify = verifier or _verify
        factory = registrar_factory or _registrar

        def finish(status, *, checked=None, credential=None):
            state.update(status=status, checked_at=int(time.time()), credential_verified=status in {'verified_existing', 'verified_new'})
            if checked:
                state['check'] = {'status': checked}
            else:
                state.pop('check', None)
            if credential:
                state['credential_fingerprint'] = _fingerprint(credential)
            _write(path, state)
            return _public(provider, state, key=env.get(env_name))

        async def check(candidate):
            if (not isinstance(candidate, str) or not 12 <= len(candidate) <= 4096 or
                    not candidate.isascii() or re.search(r'[\s\x00-\x1f\x7f]', candidate)):
                return 'invalid'
            try:
                return 'passed' if await verify(provider, candidate) is True else 'failed'
            except Exception:
                return 'error'

        if provider not in CHECK_ENDPOINTS:
            return finish('verification_unavailable', checked='unsupported')
        if key:
            checked = await check(key)
            if checked == 'invalid':
                return finish('configuration_error')
            return finish('verified_existing' if checked == 'passed' else 'verification_failed',
                          checked=checked, credential=key if checked == 'passed' else None)
        pending = _prior_registration(data_dir, provider, state)
        if pending:
            state['registration_claimed'] = True
            return finish(pending)
        try:
            agent = factory()
        except Exception:
            return finish('capability_unavailable')
        state.update(attempt_id=uuid.uuid4().hex, registration_claimed=True,
                     status='in_progress', credential_verified=False, checked_at=int(time.time()))
        _write(path, state)  # Commit before browser navigation or any signup side effect.
        bootstrap = provider in {'hyperbrowser', 'steel'} and not any(
            env.get(name) for name in ('HYPERBROWSER_API_KEY', 'STEEL_API_KEY'))
        try:
            result = await agent.run(provider, bootstrap=bootstrap)
        except asyncio.CancelledError:
            finish('verification_required')
            raise
        except Exception:
            return finish('verification_required')
        # Reload a key that the registrar persisted before an interrupted vault sync.
        if environ is None:
            env = _environment(None)
        new_key = env.get(env_name)
        if new_key:
            checked = await check(new_key)
            return finish('verified_new' if checked == 'passed' else 'verification_required',
                          checked=checked if checked != 'invalid' else 'failed',
                          credential=new_key if checked == 'passed' else None)
        status = result.get('status') if isinstance(result, dict) else None
        if not isinstance(status, str):
            status = 'verification_required'
        if status in SAFE_TO_RETRY:
            state['registration_claimed'] = False
        if status not in REASONS or status in {'verified_existing', 'verified_new'}:
            status = 'verification_required'
        return finish(status)


def account_catalog(value=None, *, data_dir=None, environ=None):
    """Return last local evidence only. This GET never performs authentication."""
    if value is not None and (not isinstance(value, dict) or value):
        raise AccountError('account catalog takes no input fields')
    data_dir = Path(data_dir) if data_dir is not None else ROOT / 'data'
    env = _environment(environ)
    providers = []
    for provider, (name, url, env_name) in PROVIDERS.items():
        if provider == 'devhunt':
            saved = _read(data_dir / 'web-profiles/devhunt.json')
            receipt = website_receipt(saved or {'reason': 'Connect the DevHunt public profile through its Google/GitHub website sign-in. No DevHunt API key is needed.'})
            providers.append({'id': provider, 'name': name, 'url': url, 'verification_supported': True,
                              'workflow_kind': 'public_profile', **receipt})
            continue
        state = _read(data_dir / 'accounts' / f'{provider}.json')
        key = env.get(env_name)
        if not state:
            pending = _prior_registration(data_dir, provider, {})
            if pending:
                state = {'status': pending, 'registration_claimed': True}
            elif provider not in CHECK_ENDPOINTS:
                state = {'status': 'verification_unavailable'}
        receipt = _public(provider, state, key=key)
        providers.append({'id': provider, 'name': name, 'url': url,
                          'verification_supported': provider in CHECK_ENDPOINTS, **receipt})
    return {'providers': providers, 'checked_at': int(time.time()),
            'note': 'Local credential presence and prior receipts only. Verify through an account task; catalog reads do not make provider requests.'}


def account_tools():
    return [{'name': 'register_developer_account',
             'description': 'Verify an existing provider credential first, otherwise attempt the existing free developer registration flow once. Only verified_existing or verified_new with credential_verified true is success. Pending or uncertain submissions are never replayed.',
             'inputSchema': {'type': 'object', 'required': ['provider'],
                             'properties': {'provider': {'type': 'string', 'enum': list(PROVIDERS)}},
                             'additionalProperties': False}}]
