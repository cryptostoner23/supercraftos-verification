"""Fixed account workflow: provider operation, receipt validation, delivery.

Account checks do not need a generative planning/review loop. Only the native
provider adapter can establish success. A new signup may use its bounded browser
planner, but existing-key verification makes no language-model calls.
"""
from __future__ import annotations

import asyncio
import json

from account_tools import PROVIDERS, CHECK_ENDPOINTS, register_developer_account
from agent_tools import Workspace


def validate_receipt(receipt, provider):
    allowed = {'provider', 'status', 'credential_verified', 'credential_present',
               'attempt_id', 'checked_at', 'registration_attempted', 'reason', 'checks', 'authentication_method', 'profile_url'}
    if not isinstance(receipt, dict) or set(receipt) - allowed:
        raise ValueError('Provider returned an unexpected receipt shape')
    if provider == 'devhunt' and receipt.get('status') == 'verified_profile':
        from devhunt_profile import profile_url
        endpoint = profile_url(receipt.get('profile_url'))
        if (receipt.get('provider') != provider or receipt.get('authentication_method') != 'browser_session'
                or not any(check.get('kind') == 'authenticated_provider_website' and check.get('status') == 'passed'
                           and check.get('method') == 'GET' and check.get('endpoint') == endpoint
                           for check in receipt.get('checks', []) if isinstance(check, dict))):
            raise ValueError('Authenticated website profile evidence is missing')
        return
    if (receipt.get('provider') != provider
            or receipt.get('status') not in {'verified_existing', 'verified_new'}
            or receipt.get('credential_verified') is not True
            or receipt.get('credential_present') is not True):
        raise ValueError('No verified provider credential receipt')
    checks = receipt.get('checks')
    if not isinstance(checks, list) or not any(
            isinstance(check, dict) and check.get('kind') == 'authenticated_provider_api'
            and check.get('status') == 'passed' and check.get('method') == 'GET'
            and check.get('endpoint') == CHECK_ENDPOINTS.get(provider)
            for check in checks):
        raise ValueError('Authenticated provider evidence is missing')


async def run_account_workflow(worker, job):
    ident, state = job['id'], job['checkpoint']
    provider = state.get('account_provider')
    if provider not in PROVIDERS:
        worker.store.finish(ident, worker.owner, 'blocked', error='Invalid account provider')
        return
    workspace = Workspace(ident, worker.workspace_root)
    try:
        worker.store.checkpoint(ident, worker.owner, state, 1, 'action',
            {'action': 'native_tool', 'note': 'Run the provider operation directly; no model planning or review is used.',
             'tool_name': 'register_developer_account'})
        async with asyncio.timeout(90):
            receipt = await register_developer_account({'provider': provider})
        evidence = [{'name': 'register_developer_account', 'provider': provider, 'result': receipt}]
        state['native_evidence'] = evidence
        worker.store.checkpoint(ident, worker.owner, state, 2, 'observation',
            {'action': 'native_tool', 'result': json.dumps(receipt)})
        if receipt.get('status') not in {'verified_existing', 'verified_new', 'verified_profile'}:
            worker.store.finish(ident, worker.owner, 'blocked',
                result={'native_evidence': evidence},
                error=receipt.get('reason', 'Provider verification did not complete'))
            return
        validate_receipt(receipt, provider)
        text = json.dumps(receipt, ensure_ascii=False, indent=2) + '\n'
        workspace.write('account-verification.json', text)
        title = PROVIDERS[provider][0]
        workspace.write('README.md',
            f'# {title} account verification\n\n'
            f'Provider status: {receipt["status"]}.\n'
            f'Authenticated check: GET {receipt.get("profile_url") or CHECK_ENDPOINTS[provider]}.\n'
            f'Registration attempted: {str(receipt["registration_attempted"]).lower()}.\n\n' +
            ('The website profile was authenticated through the private browser session.\n' if receipt['status'] == 'verified_profile'
             else 'The native provider API confirmed the configured credential. The credential remains private on the server.\n') +
            'Validation uses account_workflow.validate_receipt in the application source; '
            'no extra language-model planning or certification loop was used.\n')
        restored = json.loads(workspace.read('account-verification.json')['content'])
        validate_receipt(restored, provider)
        if restored != receipt:
            raise ValueError('Delivered receipt differs from provider evidence')
        check = {'command': 'account_workflow.validate_receipt (native Python validation)',
                 'exit_code': 0, 'output': 'PASS: provider identity, verified credential, official authenticated endpoint, '
                 'public receipt fields, and exact downloaded-file round trip.', 'step': 3}
        worker.store.finish(ident, worker.owner, 'completed', result={
            'summary': f'{title}: {receipt["status"]}. The authenticated provider check passed. '
                       'Download the verification receipt and README. No extra model planning/review loop was used.',
            'files': workspace.manifest(), 'checks': [check], 'native_evidence': evidence,
            'review': {'accepted': True, 'method': 'deterministic_native_receipt_validation', 'issues': []}})
    except asyncio.CancelledError:
        worker.store.release(ident, worker.owner)
        raise
    except TimeoutError:
        worker.store.finish(ident, worker.owner, 'blocked',
            error='Provider operation exceeded its 90-second bound; inspect the saved provider receipt before retrying.')
    except Exception as exc:
        worker.store.finish(ident, worker.owner, 'failed', error='Account workflow failed: ' + type(exc).__name__)
