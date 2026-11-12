"""Small, credential-safe task timeline for the mobile control surface."""
from __future__ import annotations

import json
import re

from execution_learning import public_text


LABELS = {
    'queued': 'Queued', 'started': 'Agent started', 'recovered': 'Agent resumed',
    'provider_wait': 'Provider cooldown · automatic resume scheduled',
    'retry': 'Retry queued', 'thinking': 'Planning next step',
    'invalid_model_action': 'Repairing agent action', 'action': 'Using a tool',
    'command_started': 'Running a check', 'observation': 'Tool completed',
    'completed': 'Completed', 'blocked': 'Needs attention',
    'failed': 'Failed', 'cancelled': 'Cancelled', 'execution_repaired': 'Execution repaired',
}
SAFE_ACTIONS = {
    'implement_project', 'plan', 'list_files', 'read_file', 'write_file', 'write_files', 'run_command',
    'specialist_review', 'native_tool', 'finish', 'blocked',
}


def task_trace(job: dict, events: list[dict]) -> dict:
    """Return observable milestones without commands, tool output or credentials."""
    timeline = []
    for event in events[:500]:
        kind = event.get('kind', '')
        if kind not in LABELS:
            continue
        detail = event.get('detail') or {}
        if not isinstance(detail, dict):
            detail = {}
        item = {'id': event['id'], 'at': event['at'], 'kind': kind,
                'label': LABELS[kind]}
        if kind == 'provider_wait':
            item['message'] = 'Saved progress is retained; the worker will resume after the provider cooldown.'
        if kind in {'action', 'observation'}:
            action = detail.get('action')
            if action in SAFE_ACTIONS:
                item['action'] = action
                if kind == 'action':
                    item['label'] = {'implement_project': 'Building project source and tests', 'write_file': 'Writing a file', 'write_files': 'Writing project files',
                                     'read_file': 'Inspecting a file', 'run_command': 'Executing a check',
                                     'native_tool': 'Calling an integration', 'specialist_review': 'Specialist review',
                                     'plan': 'Plan saved'}.get(action, item['label'])
                    note = public_text(detail.get('note', ''), 240)
                    if note:
                        item['message'] = note
            tool_name = detail.get('tool_name')
            if isinstance(tool_name, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,95}', tool_name):
                item['tool_name'] = tool_name
        if kind == 'observation':
            raw = detail.get('result')
            try:
                result = json.loads(raw) if isinstance(raw, str) and len(raw) <= 16000 else raw
            except (ValueError, TypeError):
                result = None
            if isinstance(result, dict):
                if result.get('error'):
                    item.update(outcome='error', message='The tool reported an error; the agent is evaluating the next step.')
                elif type(result.get('exit_code')) is int:
                    code = result['exit_code']
                    item.update(outcome='success' if code == 0 else 'error', message=f'Check exited with code {code}.')
                else:
                    item.update(outcome='returned', message='Tool response recorded.')
                status = result.get('status')
                if isinstance(status, str) and status in {'completed', 'queued', 'running', 'blocked', 'failed', 'verified_existing', 'verified_new', 'verification_required', 'submitted', 'pending', 'adapter_unavailable'}:
                    item['message'] = 'Tool status: ' + status.replace('_', ' ') + '.'
            elif isinstance(result, list):
                item.update(outcome='returned', message=f'Tool returned {len(result)} items.')
        if kind in {'thinking', 'invalid_model_action', 'action'}:
            step = detail.get('step')
            if type(step) is int and step >= 0:
                item['step'] = step
        timeline.append(item)
    result = job.get('result') or {}
    summary = public_text(result.get('summary', ''), 600) if isinstance(result, dict) else ''
    return {'job_id': job['id'], 'status': job['status'],
            'steps': job['steps'], 'max_steps': job['max_steps'],
            'updated': job['updated'], 'summary': summary,
            'error': public_text(job.get('error') or '', 400),
            'timeline': timeline, 'next_cursor': events[min(500, len(events))-1]['id'] if events else None}
