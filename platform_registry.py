"""Evidence-backed platform catalog and cached official release monitoring."""
import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'data/platform-releases.json'

CATALOG = [
    {'id': 'muse', 'name': 'Meta Muse', 'url': 'https://muse.ai', 'license': 'Hosted proprietary service', 'cost': 'Free tier and paid plans; availability depends on region/account', 'features': 'Persistent personal context, dedicated browser computer, app connections, approvals', 'access': 'provider_signin'},
    {'id': 'grok', 'name': 'Grok Bot', 'url': 'https://x.ai/bot', 'license': 'Hosted proprietary service', 'cost': 'Provider account and applicable plan required', 'features': 'Persistent cloud computer, specialist bots, shared login context', 'access': 'provider_signin'},
    {'id': 'manus', 'name': 'Manus', 'url': 'https://manus.im', 'license': 'Hosted proprietary service', 'cost': 'Provider credits/plans; no unlimited-free claim', 'features': 'General task execution, research, MCP and app connectors', 'access': 'provider_signin'},
    {'id': 'openmanus', 'name': 'OpenManus', 'url': 'https://github.com/FoundationAgents/OpenManus', 'repo': 'FoundationAgents/OpenManus', 'license': 'MIT', 'cost': 'Self-host software; model/browser compute may cost', 'features': 'Agent loop, browser tools, configurable models, MCP', 'access': 'source_available'},
    {'id': 'openhands', 'name': 'OpenHands', 'url': 'https://github.com/OpenHands/OpenHands', 'repo': 'OpenHands/OpenHands', 'license': 'MIT core; inspect component-specific terms', 'cost': 'Self-host compute and models; hosted plans separate', 'features': 'Developer agent control center, ACP agents, sandboxes and automations', 'access': 'source_available'},
    {'id': 'librechat', 'name': 'LibreChat', 'url': 'https://github.com/LibreChat-AI/LibreChat', 'repo': 'LibreChat-AI/LibreChat', 'license': 'MIT', 'cost': 'Self-host software; inference and storage separate', 'features': 'Multi-user sign-in, multi-provider chat, agents, MCP and artifacts', 'access': 'source_available'},
    {'id': 'hermes', 'name': 'Hermes Agent', 'url': 'https://github.com/NousResearch/hermes-agent', 'repo': 'NousResearch/hermes-agent', 'license': 'MIT; verify current repository license on updates', 'cost': 'Self-host software; local/cloud model costs separate', 'features': 'Persistent memory, reusable skills, tools and messaging integrations', 'access': 'source_available'},
    {'id': 'muse-research', 'name': 'MUSE research framework', 'url': 'https://github.com/KnowledgeXLab/MUSE', 'repo': 'KnowledgeXLab/MUSE', 'license': 'MIT', 'cost': 'Research setup; model/browser resources required', 'features': 'Hierarchical experience memory and task reflection; distinct from Meta Muse', 'access': 'research_reference'},
    {'id': 'dify', 'name': 'Dify', 'url': 'https://github.com/langgenius/dify', 'repo': 'langgenius/dify', 'license': 'Dify license, Apache-derived with additional conditions', 'cost': 'Self-host compute; tenancy/branding restrictions must be checked', 'features': 'Visual agent workflows, RAG, model/tool catalog, observability', 'access': 'source_available'},
    {'id': 'flowise', 'name': 'Flowise', 'url': 'https://github.com/FlowiseAI/Flowise', 'repo': 'FlowiseAI/Flowise', 'license': 'Component-specific; inspect current license', 'cost': 'Self-host compute and inference', 'features': 'Visual agent flows; repository maintenance status must be checked', 'access': 'source_available'},
    {'id': 'cadquery', 'name': 'CadQuery', 'url': 'https://cadquery.readthedocs.io', 'repo': 'CadQuery/cadquery', 'license': 'Apache-2.0; CAD kernel has separate dependency terms', 'cost': 'No per-export API charge; runs on this VPS', 'features': 'Parametric solids, STEP/STL/DXF export and geometry validation', 'access': 'native_product_lab'},
    {'id': 'autocad', 'name': 'Autodesk AutoCAD Web', 'url': 'https://web.autocad.com', 'license': 'Proprietary Autodesk software', 'cost': 'Autodesk subscription/entitlement required', 'features': 'Official Autodesk web editor; separate service from the native CAD engine', 'access': 'provider_signin'},
]


def catalog():
    try: evidence = json.loads(STATE.read_text())
    except (OSError, ValueError): evidence = {}
    rows = []
    for item in CATALOG:
        row = dict(item)
        row['release'] = evidence.get('platforms', {}).get(item['id'], {})
        row['installed'] = item['id'] == 'cadquery' and (ROOT / '.cad-venv/bin/python').exists()
        rows.append(row)
    return {'platforms': rows, 'checked_at': evidence.get('checked_at'),
            'update_policy': 'Daily official release/maintenance checks while runtime runs; no source or package is silently replaced.',
            'scope': 'Provider sign-in opens their official service. Catalog entries do not imply local installation, connected accounts, or model availability.'}


async def refresh():
    semaphore = asyncio.Semaphore(3)
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, headers={'User-Agent': 'SuperCraftOS-release-monitor', 'Accept': 'application/vnd.github+json'}) as client:
        async def check(item):
            async with semaphore:
                try:
                    metadata = await client.get('https://api.github.com/repos/' + item['repo'])
                    metadata.raise_for_status()
                    repository = metadata.json()
                    release = await client.get('https://api.github.com/repos/' + item['repo'] + '/releases/latest')
                    if release.status_code == 404: latest = {}
                    else: release.raise_for_status(); latest = release.json()
                    return item['id'], {'status': 'archived' if repository.get('archived') else 'checked',
                                        'latest_version': latest.get('tag_name'), 'release_url': latest.get('html_url'),
                                        'published_at': latest.get('published_at'), 'pushed_at': repository.get('pushed_at'),
                                        'license_spdx': (repository.get('license') or {}).get('spdx_id')}
                except (httpx.HTTPError, ValueError): return item['id'], {'status': 'check_failed'}
        result = {'checked_at': time.time(), 'platforms': dict(await asyncio.gather(*(check(item) for item in CATALOG if item.get('repo'))))}
    STATE.parent.mkdir(exist_ok=True)
    temporary = STATE.with_suffix('.' + uuid.uuid4().hex + '.tmp'); temporary.write_text(json.dumps(result, indent=2)); temporary.chmod(0o600); temporary.replace(STATE)
    return result


async def watch_releases(stop):
    while not stop.is_set():
        if time.time() - (catalog().get('checked_at') or 0) >= 86400:
            await refresh()
        try: await asyncio.wait_for(stop.wait(), timeout=3600)
        except asyncio.TimeoutError: pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['list', 'refresh'])
    args = parser.parse_args()
    print(json.dumps(asyncio.run(refresh()) if args.operation == 'refresh' else catalog(), indent=2))
