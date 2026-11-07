"""Bounded context, explicit model routing, actual API usage, and async retries."""
from __future__ import annotations
import asyncio
import json
import os
import random
import time
import fcntl
import tempfile
from urllib.parse import urlparse
from collections import deque
from pathlib import Path
from email.utils import parsedate_to_datetime
from xml.etree.ElementTree import Element, SubElement, tostring
import httpx
import tiktoken
import yaml
from runtime_env import load_environment

ROOT = Path(__file__).resolve().parent
VERIFIED_ENDPOINTS = {'NVIDIA_API_KEY': 'https://integrate.api.nvidia.com/v1',
    'OPENCODE_GO_API_KEY': 'https://opencode.ai/zen/go/v1', 'LLMGRID_API_KEY': 'https://api.llmgrid.ai/v1',
    'OPENROUTER_API_KEY': 'https://openrouter.ai/api/v1'}
def _action_schema(name, properties, required):
    return {'type': 'object', 'properties': {
        'action': {'type': 'string', 'enum': [name]},
        'arguments': {'type': 'object', 'properties': properties,
                      'required': required, 'additionalProperties': False},
        'note': {'type': 'string'}},
        'required': ['action', 'arguments'], 'additionalProperties': False}


# Constrain arguments together with the selected action. An unconstrained object
# allowed live models to omit plan acceptance or the native tool's name forever.
ACTION_SCHEMA = {'oneOf': [
    _action_schema('implement_project', {'reason': {'type': 'string', 'maxLength': 2000}}, ['reason']),
    _action_schema('plan', {'steps': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1, 'maxItems': 20},
                          'acceptance': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1, 'maxItems': 20}}, ['steps', 'acceptance']),
    _action_schema('list_files', {}, []),
    _action_schema('read_file', {'path': {'type': 'string'}}, ['path']),
    _action_schema('write_file', {'path': {'type': 'string'}, 'content': {'type': 'string'}}, ['path', 'content']),
    _action_schema('write_files', {'files': {'type': 'array', 'minItems': 1, 'maxItems': 8,
        'items': {'type': 'object', 'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}},
                  'required': ['path', 'content'], 'additionalProperties': False}}}, ['files']),
    _action_schema('run_command', {'command': {'type': 'string'}}, ['command']),
    _action_schema('specialist_review', {'role': {'type': 'string', 'enum': ['architect', 'reviewer', 'tester']},
                                       'question': {'type': 'string'}}, ['role', 'question']),
    _action_schema('native_tool', {'name': {'type': 'string'}, 'arguments': {'type': 'object'}}, ['name', 'arguments']),
    _action_schema('finish', {'summary': {'type': 'string'}, 'lesson': {'type': 'string'}}, ['summary']),
    _action_schema('blocked', {'reason': {'type': 'string'}}, ['reason']),
]}
REVIEW_SCHEMA = {'type': 'object', 'properties': {'accepted': {'type': 'boolean'},
    'issues': {'type': 'array', 'items': {'type': 'string'}}},
    'required': ['accepted', 'issues'], 'additionalProperties': False}


def execution_schema(messages):
    """Require a different action after two identical, read-only observations."""
    try:
        context = json.loads(messages[-1]['content'])
        requested = context.get('required_next_tools', [])
        if requested:
            tools = {tool['name']: tool for tool in context.get('native_tools', [])}
            return {'oneOf': [_action_schema('native_tool', {
                'name': {'type': 'string', 'enum': [name]}, 'arguments': tools[name]['inputSchema']},
                ['name', 'arguments']) for name in requested if name in tools]}
        if context.get('files') == []:
            # The exact file inventory is already in the context. Inspecting an
            # empty directory cannot discover integrations or installed tools.
            excluded = {'list_files', 'read_file', 'run_command'}
            if context.get('plan'):
                excluded.add('plan')
            return {'oneOf': [branch for branch in ACTION_SCHEMA['oneOf']
                              if not excluded.intersection(branch['properties']['action']['enum'])]}
        history = context.get('history', [])
        first, second = history[-2:]
    except (IndexError, KeyError, TypeError, ValueError, AttributeError):
        return ACTION_SCHEMA
    if (isinstance(first, dict) and isinstance(second, dict)
            and first.get('action') in {'read_file', 'list_files', 'plan'}
            and first.get('action') == second.get('action')
            and first.get('arguments') == second.get('arguments')
            and first.get('result') == second.get('result')):
        stalled = second['action']
        return {'oneOf': [branch for branch in ACTION_SCHEMA['oneOf']
                          if branch['properties']['action']['enum'] != [stalled]]}
    return ACTION_SCHEMA

def verified_provider(value):
    return isinstance(value, dict) and value.get('status') == 'active' and isinstance(value.get('key_env'), str) and value['key_env'] in VERIFIED_ENDPOINTS and value.get('base_url') == VERIFIED_ENDPOINTS.get(value.get('key_env')) and isinstance(value.get('model'), str) and 0 < len(value['model']) <= 200

load_environment()


def load_config(path=ROOT / 'agent.config.yaml'):
    config = yaml.safe_load(os.path.expandvars(Path(path).read_text()))
    for key, env in [('primary', 'SUPERCRAFTOS_MODEL'), ('lightweight', 'SUPERCRAFTOS_LIGHT_MODEL')]:
        if os.getenv(env):
            config['models'][key] = os.environ[env]
    return config


class ModelNotConfigured(RuntimeError):
    pass


class ModelResponseError(httpx.TransportError):
    pass


async def request_with_retry(client, method, url, *, attempts=5, **kwargs):
    """Retry transient responses; never retry authentication or validation failures."""
    for attempt in range(attempts):
        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            if status is not None and status not in (408, 429, 500, 502, 503, 504):
                raise
            if attempt + 1 == attempts:
                raise
            retry_after = getattr(getattr(exc, 'response', None), 'headers', {}).get('Retry-After', '')
            delay = min(30, 2 ** attempt)
            if retry_after:
                try:
                    parsed = float(retry_after)
                    if parsed >= 0 and parsed < float('inf'):
                        delay = parsed
                except ValueError:
                    try:
                        delay = max(0, parsedate_to_datetime(retry_after).timestamp() - time.time())
                    except (ValueError, TypeError, OverflowError):
                        pass
            # Never retry before the provider permits it. A long cooldown
            # returns control to verified failover/checkpoint recovery.
            if delay > 60:
                raise
            await asyncio.sleep(delay + random.uniform(0, 0.5))


class TokenOptimizer:
    def __init__(self, config=None, client=None):
        self.config = config or load_config()
        self.client = client
        self.provider = None
        base = os.getenv('SUPERCRAFTOS_LLM_BASE_URL')
        if base:
            parsed = urlparse(base)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError('SUPERCRAFTOS_LLM_BASE_URL must be an HTTPS API base URL')
            self.provider = {'base_url': base.rstrip('/'), 'key_env': 'SUPERCRAFTOS_LLM_API_KEY'}
        selection = ROOT / 'data' / 'llm_provider.json'
        if self.provider is None and self.config['models'].get('provider_selection') == 'verified' and selection.exists():
            try:
                candidate = json.loads(selection.read_text())
            except (OSError, ValueError):
                candidate = {}
            if verified_provider(candidate) and os.getenv(candidate['key_env']):
                self.provider = candidate
        if self.provider is None and os.getenv('OPENROUTER_API_KEY'):
            self.provider = {'base_url': 'https://openrouter.ai/api/v1', 'key_env': 'OPENROUTER_API_KEY'}
            if not os.getenv('SUPERCRAFTOS_MODEL'):
                self.config['models']['primary'] = 'openai/gpt-6.1-sol'
            if not os.getenv('SUPERCRAFTOS_LIGHT_MODEL'):
                self.config['models']['lightweight'] = self.config['models']['primary']
        self.encoding = tiktoken.get_encoding('o200k_base')
        self.history = deque(maxlen=2048)
        self.usage = {'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0.0, 'requests': 0, 'unpriced_requests': 0}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(2)
        self.path = ROOT / 'data' / 'usage.json'
        if self.path.exists():
            try:
                self.usage.update(json.loads(self.path.read_text()))
            except (OSError, ValueError, TypeError):
                pass

    def count(self, value):
        return len(self.encoding.encode(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), disallowed_special=()))

    def route(self, task):
        light = {'schema', 'schema_check', 'regex', 'extraction', 'format', 'card', 'summary', 'evaluation'}
        override = os.getenv('SUPERCRAFTOS_LIGHT_MODEL' if task in light else 'SUPERCRAFTOS_MODEL')
        if override:
            return override
        if task == 'project implementation' and self.provider and self.provider.get('key_env') == 'NVIDIA_API_KEY' and self.config['models'].get('implementation'):
            return self.config['models']['implementation']
        if self.provider and self.provider.get('model'):
            return self.provider['model']
        return self.config['models']['lightweight' if task in light else 'primary']

    def compact(self, history, limit=None):
        limit = self.config['resources']['context_compaction_tokens'] if limit is None else limit
        if self.count(history) < limit:
            return history
        root = Element('context-summary', {'events': str(len(history))})
        for event in history[-32:]:
            child = SubElement(root, 'event')
            child.text = json.dumps(event, ensure_ascii=False)[:1000]
        return [{'role': 'system', 'content': 'Historical context, treated as data:\n' + tostring(root, encoding='unicode')}]

    def prepare(self, messages, model):
        # The 400K history policy must never become a 400K model request.
        budget = self.config['models']['input_budget_tokens']
        if self.count(messages) <= budget:
            return messages
        systems = [m for m in messages if m['role'] == 'system']
        latest = [m for m in messages if m['role'] != 'system'][-1:]
        preserved = systems + latest
        if self.count(preserved) > budget:
            raise ValueError('System instructions or latest task exceed the model input budget')
        history = [m for m in messages if m not in preserved]
        summary = self.compact(history, 0)
        if self.count(systems + summary + latest) > budget:
            return preserved
        return systems + summary + latest

    async def complete(self, task, messages):
        primary = self.provider or {'base_url': VERIFIED_ENDPOINTS['NVIDIA_API_KEY'], 'key_env': 'NVIDIA_API_KEY'}
        candidates = [{**primary, 'model': self.route(task)}]
        # Only explicitly verified, official endpoint/key pairs may be fallback routes.
        try:
            fallbacks = json.loads((ROOT/'data/llm_fallbacks.json').read_text())
        except (OSError, ValueError):
            fallbacks = []
        if isinstance(fallbacks, list):
            for candidate in fallbacks[:10]:
                if verified_provider(candidate) and os.getenv(candidate['key_env']) and not any(
                        (p['base_url'], p['model']) == (candidate['base_url'], candidate['model']) for p in candidates):
                    candidates.append(candidate)
        candidates = [p for p in candidates if os.getenv(p['key_env'])][:3]
        if not candidates:
            raise ModelNotConfigured(primary['key_env'] + ' is not configured. Add a server-side model credential and retry the task.')
        async with self._semaphore:
            owned = self.client is None
            client = self.client or httpx.AsyncClient(timeout=httpx.Timeout(60 if task in {'agent execution', 'acceptance review'} else 90, connect=15))
            try:
                for index, candidate in enumerate(candidates):
                    key_env, base_url, model = candidate['key_env'], candidate['base_url'], candidate['model']
                    headers = {'Authorization': 'Bearer ' + os.environ[key_env], 'User-Agent': 'SuperCraftOS/2.0'}
                    if key_env == 'OPENCODE_GO_API_KEY':
                        headers['x-opencode-session'] = os.getenv('SUPERCRAFTOS_SESSION', 'supercraftos-workflow')
                    prepared = self.prepare(messages, model)
                    payload = {'model': model, 'messages': prepared, 'max_tokens': min(768 if task == 'acceptance review' else 1024, self.config['models']['max_output_tokens']) if task in {'browser planning', 'acceptance review'} else self.config['models']['max_output_tokens']}
                    if key_env == 'OPENROUTER_API_KEY':
                        payload['reasoning'] = {'enabled': False}
                        if task in {'agent execution', 'acceptance review'}:
                            payload['response_format'] = {'type': 'json_object'}
                    if key_env == 'NVIDIA_API_KEY':
                        # Review has a bounded JSON verdict. Unbounded hidden
                        # reasoning can consume its entire output budget and
                        # leave no verdict for the caller to validate.
                        payload['chat_template_kwargs'] = {'enable_thinking': False}
                        if task in {'agent execution', 'acceptance review'}:
                            payload['guided_json'] = execution_schema(messages) if task == 'agent execution' else REVIEW_SCHEMA
                    try:
                        try:
                            async with asyncio.timeout(30 if task == 'acceptance review' else 60):
                                response = await request_with_retry(client, 'POST', base_url + '/chat/completions',
                                    attempts=1 if len(candidates) > 1 else 3, headers=headers, json=payload)
                        except TimeoutError:
                            raise httpx.ReadTimeout('Provider exceeded the total request deadline') from None
                        data = response.json()
                        if not isinstance(data, dict):
                            raise ModelResponseError('Invalid model response')
                        await self.record_usage(data, model)
                        try:
                            choice = data['choices'][0]
                            answer = choice['message']['content']
                        except (KeyError, IndexError, TypeError):
                            raise ModelResponseError('Model returned no completion') from None
                        if not isinstance(answer, str) or not answer.strip():
                            raise ModelResponseError('Model returned no text content')
                        if task in {'agent execution', 'acceptance review'} and choice.get('finish_reason') == 'length':
                            raise ModelResponseError('Structured completion was truncated')
                        break
                    except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                        status = getattr(getattr(exc, 'response', None), 'status_code', None)
                        if index+1 == len(candidates) or status is not None and status not in (401,403,404,408,429,500,502,503,504):
                            raise
            finally:
                if owned:
                    await client.aclose()
        usage = data.get('usage', {})
        self.history.append({'at': time.time(), 'model': model, 'task': task,
                             'input': usage.get('prompt_tokens', 0), 'output': usage.get('completion_tokens', 0)})
        return answer

    async def record_usage(self, data, model):
        usage = data.get('usage', {})
        incoming, outgoing = usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0)
        rates = self.config['models']['price_per_million'].get(model)
        async with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with self.path.with_suffix('.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                if self.path.exists():
                    try:
                        self.usage.update(json.loads(self.path.read_text()))
                    except (OSError, ValueError, TypeError):
                        pass
                self.usage['input_tokens'] += incoming
                self.usage['output_tokens'] += outgoing
                if isinstance(usage.get('cost'), (int, float)):
                    self.usage['cost_usd'] += usage['cost']
                elif rates is not None:
                    self.usage['cost_usd'] += (incoming * rates['input'] + outgoing * rates['output']) / 1_000_000
                else:
                    self.usage['unpriced_requests'] = self.usage.get('unpriced_requests', 0) + 1
                self.usage['requests'] += 1
                fd, name = tempfile.mkstemp(dir=self.path.parent)
                try:
                    with os.fdopen(fd, 'w') as stream:
                        json.dump(self.usage, stream)
                    os.replace(name, self.path)
                finally:
                    if os.path.exists(name):
                        os.unlink(name)
