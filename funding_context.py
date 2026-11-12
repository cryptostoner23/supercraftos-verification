"""Local funding context for execution; no network calls or credential discovery."""
import json
import re

from grant_workflow import STORE, grant_catalog


def positive_goal(goal):
    # Exclusions and lists such as 'No grants, RPCs or network' are constraints,
    # not funding requests. Keep positively requested clauses only.
    return re.sub(r"\b(?:no|without|do not|don't|not using|not require)\b[^.!?;\n]*", '', goal, flags=re.I)


def is_funding_goal(goal):
    return bool(re.search(r'\bgrants?\b', positive_goal(goal), re.I))


def requires_project(goal):
    return bool(is_funding_goal(goal) and
                re.search(r'\b(?:coding|build|create|implement|develop|software)\b', positive_goal(goal), re.I))


def next_source_tools(goal, evidence, tools):
    if not is_funding_goal(goal) or not re.search(r'\b(?:current|open|available|find|discover|possible)\b', goal, re.I):
        return []
    attempted = set()
    for item in evidence:
        if item.get('name') not in {'ingest_tavily', 'ingest_firecrawl', 'ingest_browserless'}:
            continue
        attempted.add(item['name'])
        result = item.get('result', {})
        body = result.get('result') if isinstance(result, dict) else None
        if isinstance(body, dict) and not body.get('error') and body.get('success') is not False and any(body.get(key) for key in ('results', 'data', 'html')):
            return []
    return [name for name in ('ingest_tavily', 'ingest_firecrawl', 'ingest_browserless') if name in tools and name not in attempted][:1]


def applicant_arguments(name, arguments):
    """Resolve applicant contact on the server instead of inventing an email."""
    if name not in {'screen_blockchain_grants', 'draft_grant_application'} or not isinstance(arguments.get('profile'), dict):
        return arguments
    from runtime_env import ROOT
    try:
        preferences = json.loads((ROOT / 'data/applicant-profile.json').read_text())
    except (OSError, ValueError):
        return arguments
    contact = preferences.get('contact_email')
    if not isinstance(contact, str) or '@' not in contact:
        return arguments
    profile = {**arguments['profile'], 'contact_email': contact}
    if not profile.get('team'):
        profile['team'] = preferences.get('public_name', 'HSK')
    return {**arguments, 'profile': profile}


def context_for_goal(goal, *, store=None):
    if not is_funding_goal(goal):
        return None
    records = []
    directory = STORE if store is None else store
    for path in sorted(directory.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
        try:
            if path.stat().st_size > 100000:
                continue
            package = json.loads(path.read_text())
            if not isinstance(package, dict) or not isinstance(package.get('draft'), dict):
                continue
            draft = package['draft']
            # Do not copy applicant identities, contacts, credentials or upstream
            # raw responses into model context. The server owns those defaults.
            records.append({'package_id': package.get('id'), 'program_id': package.get('program_id'),
                'status': package.get('status'), 'project_scope': {key: draft[key] for key in
                    ('title', 'problem', 'proposed_solution', 'delivery_plan', 'success_metrics', 'repository_url') if key in draft}})
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return {'official_catalogue': grant_catalog(), 'existing_applications': records,
        'required_delivery': 'Implement the selected grant project with runnable source, installation/start instructions, and tests. A grant tracker is not the funded project.',
        'freshness': 'Catalogue entries are leads. Fetch the current official page through an installed ingestion tool before calling an opportunity open.',
        'submission': 'Never duplicate an existing submitted application. Refer to its recorded package ID.',
        'funding': 'Application submitted, project delivered, award approved and payment received are distinct states. Only actual provider/payment evidence establishes the latter two.'}
