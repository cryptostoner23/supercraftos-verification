"""Reusable execution practices and concise, evidence-linked public explanations.

This is retrieval memory, not model-weight training. It stores no private reasoning.
"""
from __future__ import annotations
import re

PLAYBOOKS = [
    {'id': 'repair-verify', 'title': 'Repair with evidence',
     'when': 'Fixing software, tests, failures, or regressions',
     'steps': ['Reproduce the observed failure with a focused check.',
               'Change the smallest complete unit that fixes the cause.',
               'Rerun the failed check, then the affected integration checks.',
               'Report the changed behavior, evidence, and remaining limits.'],
     'evidence': ['test_autonomous.py', 'test_sandbox_integration.py']},
    {'id': 'recover-execution', 'title': 'Recover interrupted work',
     'when': 'Background tasks, cancellation, retries, and worker restarts',
     'steps': ['Persist intent before launching an operation.',
               'Reconcile the previous operation before reusing its workspace.',
               'Wait for cleanup before releasing ownership.',
               'Invalidate old verification whenever files or execution change.'],
     'evidence': ['agent_runtime.py', 'test_sandbox_integration.py']},
    {'id': 'portable-release', 'title': 'Deliver a reproducible release',
     'when': 'Packaging, deployment, Swift apps, or a fresh installation',
     'steps': ['Build from tracked source with declared dependencies.',
               'Separate server credentials and runtime data from release files.',
               'Test the actual archive and installation path.',
               'Distinguish compilation, runtime checks, and untested platforms.'],
     'evidence': ['scripts/package_ipad.py', '.github/ci/offline_checks.py', 'DEPLOYMENT.md']},
    {'id': 'provider-evidence', 'title': 'Report external results accurately',
     'when': 'Provider APIs, grants, quests, payment, or remote services',
     'steps': ['Use the configured official endpoint and preserve the operation identifier.',
               'Record an uncertain response as uncertain; reconcile before retrying.',
               'Require a provider receipt before claiming external completion.',
               'Keep credentials out of explanations and reusable lessons.'],
     'evidence': ['quest_workflow.py', 'grant_workflow.py']},
]


def public_text(value, limit=1500):
    """Remove common credential forms before retaining a public explanation."""
    if not isinstance(value, str):
        return ''
    value = re.sub(r'(?is)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', '[redacted private key]', value)
    value = re.sub(r'(?i)\b(?:Bearer|Basic)\s+[A-Za-z0-9_./+=-]+', '[redacted authorization]', value)
    value = re.sub(r'(?i)(\b(?:[\w-]*(?:api[_-]?key|token|password|secret)[\w-]*)\s*[:=]\s*)[^\s,;]+', r'\1[redacted]', value)
    value = re.sub(r'https?://[^\s<>]+', lambda m: m.group(0).split('?')[0].split('#')[0], value)
    value = re.sub(r'\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,})\b', '[redacted credential]', value)
    return value.strip()[:limit]


def practices(goal):
    words = set(re.findall(r'[a-z]{3,}', goal.lower()))
    return sorted(PLAYBOOKS, key=lambda p: len(words & set(re.findall(r'[a-z]{3,}', (p['title']+' '+p['when']).lower()))), reverse=True)[:3]


def memory_view(store):
    return {'mode': 'retrieval_memory', 'model_weights_trained': False,
            'description': 'Original execution playbooks and lessons linked to verified completed tasks. No private reasoning is collected.',
            'playbooks': PLAYBOOKS, 'lessons': store.lesson_records()}
