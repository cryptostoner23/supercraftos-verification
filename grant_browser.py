"""Bounded submission through the current official Uniswap Notion form.

Uses visible form controls and requires the provider's confirmation screen.
There is no model call, invented endpoint, or fabricated provider receipt ID.
"""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse

FORM_URL = 'https://uniswap.notion.site/bdb023b007ec444f8616d38b554163fa'


def form_answers(package, environ=None, preferences=None):
    env = os.environ if environ is None else environ
    draft = package.get('draft', {})
    preferences = preferences or {}
    public_name = preferences.get('public_name', '')
    email = preferences.get('contact_email') or draft.get('contact_email') or env.get('GMAIL_ADDRESS', '')
    repository = draft.get('repository_url', '')
    owner = urlparse(repository).path.strip('/').split('/')[0] if urlparse(repository).hostname == 'github.com' else ''
    budget = draft.get('budget_usd', 0)
    breakdown = draft.get('budget_breakdown_usd', {})
    missing = []
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or email.endswith(('.example', '.invalid')):
        missing.append('contact_email')
    for field in ('title', 'proposed_solution', 'public_goods_case', 'team', 'delivery_plan'):
        if not draft.get(field): missing.append(field)
    if not public_name and not owner and not draft.get('contact_first_name'): missing.append('applicant_public_name')
    if (not isinstance(budget, (int, float)) or isinstance(budget, bool) or not math.isfinite(budget) or budget <= 0
            or not isinstance(breakdown, dict) or not breakdown
            or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v < 0 for v in breakdown.values())
            or abs(sum(breakdown.values()) - budget) > .01):
        missing.append('itemized_budget_matching_total')
    if missing: return {}, missing
    handle = env.get('X_USERNAME', '').lstrip('@')
    account_x = 'https://x.com/' + handle if re.fullmatch(r'[A-Za-z0-9_]{1,30}', handle) else ''
    # A public pseudonym is identified as such, rather than inventing a legal name.
    notes = ('This is a pre-launch proposal, not a claim of an already deployed Uniswap product. '
             'Applicant identity is the public repository maintainer; no unprovided legal identity is asserted. '
             'The prior-grants answer refers to this SuperCraftOS project, for which no grant award is recorded. '
             'No TVL, revenue, existing Uniswap deployment, trading execution, or profitability is claimed. '
             'An existing maintainer X account, if linked, is not represented as project traction.')
    answers = {
        'Project Name': draft['title'],
        'First Name': public_name or draft.get('contact_first_name') or owner,
        'Last Name': 'Not supplied — public pseudonym' if public_name else draft.get('contact_last_name') or 'Not supplied — public pseudonym',
        'Email': email,
        'Telegram Handle': draft.get('telegram_handle') or 'Not supplied; please contact the project by email.',
        'Website URL': draft.get('website_url') or repository,
        'Project X (Twitter)': draft.get('project_x') or account_x or 'No project-specific X account is claimed.',
        'GitHub Repo or Codebase': repository,
        'What are you building, and who is it for?': draft['proposed_solution'],
        'How does your project contribute to the Uniswap Ecosystem?': draft['public_goods_case'],
        'What are your most relevant metrics? (TVL, volume, users, revenue — whatever applies)':
            'Pre-launch proposal; no live TVL, volume, users or revenue is claimed. Target acceptance evidence: '
            + '; '.join(draft.get('success_metrics', [])),
        'What will you use the grant for, and what are your milestones?':
            '\n'.join(f'{i+1}. {value}' for i, value in enumerate(draft['delivery_plan'])),
        'Requested Grant Amount': str(budget),
        'Please provide a breakdown of how you arrived at this amount (e.g. number of hours × hourly rate, itemized costs by milestone, vendor quotes, etc.). The more detail you provide, the faster we can process your request.':
            '\n'.join(f'{name.replace("_", " ")}: USD {amount}' for name, amount in breakdown.items())
            + '\nThese are requested milestone allocations, not vendor quotes or incurred costs.',
        'Tell us about your team? What skills do you have?': draft['team']
            + '. The repository demonstrates Python, durable agent workflows, isolated execution, artifact verification, and Swift companion development. No additional personnel or qualifications are asserted.',
        "Anything else you'd like to share?": notes,
    }
    return answers, []


def browser_submit(answers, *, dispatch=False):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.goto(FORM_URL, wait_until='domcontentloaded', timeout=25000)
            page.locator('input[type=text]').first.wait_for(timeout=20000)
            if page.url != FORM_URL:
                return {'status': 'verification_required', 'dispatch_started': False, 'reason': 'Official form location changed.'}
            fields = page.locator('input[type=text],textarea')
            missing = []
            normalize = lambda value: re.sub(r'\s+', ' ', value).strip().rstrip('*').strip()
            values = {normalize(k): v for k, v in answers.items()}
            for field in fields.all():
                label = field.evaluate('(e)=>(e.getAttribute("aria-labelledby")||"").split(" ").map(id=>document.getElementById(id)?.innerText||"").join(" ")')
                label = normalize(label)
                if label in values:
                    field.fill(str(values[label]))
                elif field.get_attribute('required') is not None:
                    missing.append(label or 'Unrecognized required field')
            if missing:
                return {'status': 'needs_information', 'dispatch_started': False,
                        'reason': 'Current form needs unmapped fields: ' + '; '.join(missing)}
            for text in ['Research & Implementation', 'Pre-launch', 'Technical Mentorship', 'No']:
                page.get_by_text(text, exact=True).click()
            invalid = fields.evaluate_all('(xs)=>xs.filter(x=>!x.checkValidity()).map(x=>x.getAttribute("aria-labelledby"))')
            if invalid:
                return {'status': 'needs_information', 'dispatch_started': False, 'reason': 'The provider form rejected one or more field values.'}
            if not dispatch:
                return {'status': 'prepared', 'dispatch_started': False, 'filled_fields': fields.count(),
                        'reason': 'Current official form loaded and filled; no submission was sent.'}
            page.get_by_role('button', name='Submit', exact=True).click()
            try:
                page.wait_for_function('''() => {
                    const text=document.body.innerText;
                    return /your response (has been|was) (recorded|submitted)|thanks for (filling|submitting)|thank you for (filling|submitting)|submission (received|successful)/i.test(text)
                        && document.querySelectorAll('input[type=text]').length===0;
                }''', timeout=20000)
            except Exception:
                return {'status': 'verification_required', 'dispatch_started': True,
                        'reason': 'Submit was clicked but no explicit provider confirmation was observed. Do not replay.'}
            confirmation = page.locator('body').inner_text()[:2000]
            return {'status': 'submitted', 'dispatch_started': True,
                    'receipt': {'provider_confirmation': confirmation, 'provider_receipt_id': None,
                                'receipt_type': 'visible_provider_confirmation', 'form_url': FORM_URL}}
        finally:
            browser.close()


class OfficialNotionGrantAdapter:
    provider = 'official_notion_form'
    endpoint = FORM_URL

    def __init__(self, environ=None, preferences_path=None):
        self.environ = os.environ if environ is None else environ
        self.preferences = {}
        if preferences_path is not None:
            try:
                path = Path(preferences_path)
                if path.stat().st_size > 16384: raise ValueError('Profile exceeds size limit')
                profile = json.loads(path.read_text())
                self.preferences = {key: profile[key] for key in ('public_name', 'contact_email')
                                    if isinstance(profile.get(key), str) and profile[key]}
            except FileNotFoundError:
                pass

    def missing_fields(self, package):
        return form_answers(package, self.environ, self.preferences)[1]

    def submit(self, package, program, attempt_id):
        from grant_submission import SubmissionResult
        answers, missing = form_answers(package, self.environ, self.preferences)
        if missing:
            return SubmissionResult('needs_information', self.provider, package['id'], attempt_id, self.endpoint,
                reason='Application fields required: ' + ', '.join(missing))
        env = {k: v for k, v in os.environ.items() if k in {'PATH', 'HOME', 'TMPDIR', 'LANG', 'PLAYWRIGHT_BROWSERS_PATH'}}
        env.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(Path(__file__).resolve().parent / 'data/browser'))
        try:
            result = subprocess.run([sys.executable, str(Path(__file__).resolve())],
                input=json.dumps({'answers': answers, 'dispatch': True}), text=True, capture_output=True,
                timeout=80, env=env, cwd=str(Path(__file__).resolve().parent))
            response = json.loads(result.stdout)
            if response.get('status') not in {'submitted', 'needs_information', 'verification_required'}:
                raise ValueError('Unexpected browser outcome')
            if response['status'] == 'submitted':
                receipt = response.get('receipt', {})
                if (receipt.get('receipt_type') != 'visible_provider_confirmation'
                        or receipt.get('form_url') != FORM_URL
                        or not re.search(r'your response (?:has been|was) (?:recorded|submitted)|thanks for (?:filling|submitting)|thank you for (?:filling|submitting)|submission (?:received|successful)',
                                         receipt.get('provider_confirmation', ''), re.I)):
                    raise ValueError('Explicit provider confirmation missing')
            return SubmissionResult(response['status'], self.provider, package['id'], attempt_id, self.endpoint,
                                    receipt=response.get('receipt'), reason=response.get('reason'))
        except Exception as exc:
            return SubmissionResult('verification_required', self.provider, package['id'], attempt_id, self.endpoint,
                                    reason='Browser outcome requires reconciliation: ' + type(exc).__name__)


if __name__ == '__main__':
    try:
        request = json.loads(sys.stdin.read(100_001))
        print(json.dumps(browser_submit(request['answers'], dispatch=request.get('dispatch') is True)))
    except Exception as exc:
        print(json.dumps({'status': 'verification_required', 'reason': 'Browser form error: ' + type(exc).__name__}))
