"""MCP stdio transport with atomic schema registration and remote E2B execution."""
from __future__ import annotations
import asyncio
import inspect
import json
import os
import sys
from pathlib import Path
from jsonschema import Draft202012Validator
from token_optimizer import ROOT, load_config


class RPCError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


class DynamicMCPServer:
    def __init__(self, registry_path='data/tools.json'):
        self.registry_path = Path(registry_path)
        self.tools = {}
        from product_design import build_product, screen_product
        from quest_workflow import quest_sources, discover_quests, screen_quests, run_quests, quest_receipts
        from grant_workflow import grant_catalog, screen_grants, draft_grant_application, approve_grant_application, submit_grant_application, grant_submission_history
        self.handlers = {'execute_python_sandbox': self.execute_python_sandbox, 'research_fusion_resolver': self.research_fusion_resolver,
                         'screen_product_design': screen_product, 'generate_product_cad': build_product,
                         'list_blockchain_grants': grant_catalog, 'screen_blockchain_grants': screen_grants,
                         'draft_grant_application': draft_grant_application, 'approve_grant_application': approve_grant_application,
                         'submit_grant_application': submit_grant_application, 'grant_submission_history': grant_submission_history,
                         'submit_autonomous_task': self.submit_task, 'inspect_autonomous_task': self.inspect_task,
                         'cancel_autonomous_task': self.cancel_task}
        self.handlers.update({'list_quest_sources': quest_sources, 'discover_quest_leads': discover_quests,
            'screen_quest_leads': screen_quests, 'run_quest_actions': run_quests, 'quest_action_receipts': quest_receipts})
        from account_tools import register_developer_account
        self.handlers['register_developer_account'] = register_developer_account
        from provider_recovery import skyfire_balance
        self.handlers['skyfire_wallet_balance'] = skyfire_balance
        from devhunt_profile import manage_devhunt_profile
        self.handlers['manage_devhunt_profile'] = manage_devhunt_profile
        from web3_specialist import consult
        self.handlers['consult_web3_specialist'] = consult
        self.notifications = asyncio.Queue(maxsize=32)
        self.initialized = False
        self._load()
        self._install_builtins()

    def submit_task(self, arguments):
        from job_store import JobStore
        from agent_runtime import public_job
        return public_job(JobStore().submit(arguments['query'], max_steps=arguments.get('max_steps', 24),
            run_at=arguments.get('run_at'), idempotency_key=arguments.get('idempotency_key')))

    def inspect_task(self, arguments):
        from job_store import JobStore
        from agent_runtime import public_job
        store = JobStore()
        job = store.get(arguments['job_id'])
        if job is None:
            raise ValueError('Task not found')
        return {'job': public_job(job), 'events': store.events(job['id'])}

    def cancel_task(self, arguments):
        from job_store import JobStore
        from agent_runtime import public_job
        result = JobStore().cancel(arguments['job_id'])
        if result is None:
            raise ValueError('Task not found')
        return public_job(result)

    @staticmethod
    def builtin():
        return {'name': 'execute_python_sandbox', 'description': 'Execute Python in a remote E2B sandbox; requires E2B_API_KEY.', 'inputSchema': {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object', 'properties': {'code': {'type': 'string', 'maxLength': 10000}}, 'required': ['code'], 'additionalProperties': False}}

    def _install_builtins(self):
        from web3_specialist import tool as specialist_tool
        self.tools['consult_web3_specialist'] = specialist_tool()
        from devhunt_profile import tool as devhunt_tool
        self.tools['manage_devhunt_profile'] = devhunt_tool()
        self.tools['skyfire_wallet_balance'] = {
            'name': 'skyfire_wallet_balance',
            'description': 'Read Skyfire available balance, held amounts, pending charges and deposits. No payment or token charge is performed.',
            'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}}
        from product_design import product_tools
        from grant_workflow import grant_tools
        from quest_workflow import quest_tools
        from ecosystem_ingestion import available_providers, ingest
        from composio_mail import gmail_tools, gmail_status, gmail_send, gmail_read
        for tool in product_tools(): self.tools[tool['name']] = tool
        for tool in grant_tools(): self.tools[tool['name']] = tool
        for tool in quest_tools(): self.tools[tool['name']] = tool
        for tool in gmail_tools():
            self.tools[tool['name']] = tool
            self.handlers[tool['name']] = {
                'gmail_status': gmail_status, 'gmail_send': gmail_send, 'gmail_read': gmail_read,
            }[tool['name']]
        # Ingestion is opt-in: the tool is only offered when a provider's
        # credential is present, and it is bound to a real implementation.
        for tool in available_providers():
            self.tools[tool['name']] = tool
            from functools import partial
            self.handlers[tool['name']] = partial(ingest, provider=tool['name'].removeprefix('ingest_'))
        self.tools['register_developer_account'] = {'name': 'register_developer_account',
            'description': 'Verify an existing developer credential or register a free account through the supported provider flow. Returns redacted evidence, never the API key; pending verification remains pending.',
            'inputSchema': {'type': 'object', 'properties': {'provider': {'type': 'string', 'enum': ['hyperbrowser','steel','firecrawl','peerpush','devhunt']}}, 'required': ['provider'], 'additionalProperties': False}}
        task_specs = [
            {'name': 'submit_autonomous_task', 'description': 'Queue an autonomous coding/artifact task; background worker persists progress, tests and files. Returns immediately.',
             'inputSchema': {'type': 'object', 'properties': {'query': {'type': 'string', 'minLength': 3, 'maxLength': 12000},
                'max_steps': {'type': 'integer', 'minimum': 2, 'maximum': 80}, 'run_at': {'type': 'number', 'minimum': 0},
                'idempotency_key': {'type': 'string', 'minLength': 1, 'maxLength': 128}}, 'required': ['query'], 'additionalProperties': False}},
            *[{'name': name, 'description': description, 'inputSchema': {'type': 'object', 'properties': {
                'job_id': {'type': 'string', 'pattern': '^[a-f0-9]{32}$'}}, 'required': ['job_id'], 'additionalProperties': False}}
              for name, description in [('inspect_autonomous_task', 'Read durable task status and evidence'),
                                        ('cancel_autonomous_task', 'Cancel a queued or running task and stop its sandbox')]],
        ]
        for tool in task_specs: self.tools[tool['name']] = tool
        self.tools['execute_python_sandbox'] = self.builtin()
        self.tools['research_fusion_resolver'] = {
            'name': 'research_fusion_resolver',
            'description': 'Fresh Context.dev source research for liquidity arbitrage and a 1inch Fusion resolver. Uses API credits; returns documents and metadata.',
            'inputSchema': {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object', 'properties': {'num_results': {'type': 'integer', 'minimum': 1, 'maximum': 10, 'default': 3}}, 'additionalProperties': False},
        }

    async def research_fusion_resolver(self, arguments):
        from resolver_research import ResolverResearch
        result = await ResolverResearch().collect(arguments.get('num_results', 3))
        # Keep retrieved evidence useful to tool callers while bounding context use.
        for source in result['sources']:
            markdown = source.get('markdown')
            if isinstance(markdown, str):
                source['markdown_truncated'] = len(markdown) > 12000
                source['markdown'] = markdown[:12000]
        return result

    def _load(self):
        if not self.registry_path.exists():
            return
        candidate = json.loads(self.registry_path.read_text())
        if not isinstance(candidate, dict):
            raise ValueError('MCP registry must be a mapping')
        for name, tool in candidate.items():
            if not isinstance(tool, dict) or tool.get('name') != name:
                raise ValueError('Registry tool name mismatch')
            if not isinstance(tool.get('inputSchema'), dict):
                raise ValueError('Registry tool requires an input schema')
            Draft202012Validator.check_schema(tool['inputSchema'])
        self.tools = candidate

    def register_new_tool(self, name, description, input_schema, handler=None):
        if (not isinstance(name, str) or not name or len(name) > 128 or
                not isinstance(description, str) or len(description) > 2000 or
                not isinstance(input_schema, dict) or input_schema.get('type') != 'object'):
            raise ValueError('Tool requires a name and object input schema')
        if input_schema.get('$schema', 'https://json-schema.org/draft/2020-12/schema') != 'https://json-schema.org/draft/2020-12/schema':
            raise ValueError('Only JSON Schema 2020-12 is supported')
        Draft202012Validator.check_schema(input_schema)
        self.tools[name] = {'name': name, 'description': description, 'inputSchema': input_schema}
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.registry_path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.tools, indent=2)); temp.replace(self.registry_path)
        if handler:
            self.handlers[name] = handler
        self.notify_changed()

    def notify_changed(self):
        if self.notifications.full():
            self.notifications.get_nowait()
        self.notifications.put_nowait({'jsonrpc': '2.0', 'method': 'notifications/tools/list_changed'})

    async def execute_python_sandbox(self, arguments):
        if not os.getenv('E2B_API_KEY'):
            raise RuntimeError('E2B_API_KEY is required; host execution is disabled')
        from e2b_code_interpreter import AsyncSandbox
        config = load_config()['e2b']
        if not config['enabled']:
            raise RuntimeError('E2B is disabled in configuration')
        if len(arguments['code'].encode()) > config['max_code_bytes']:
            raise ValueError('Code exceeds byte limit')
        sandbox = await AsyncSandbox.create(template=config['template'], timeout=config['timeout_seconds'], allow_internet_access=False)
        try:
            result = await sandbox.run_code(arguments['code'], timeout=config['timeout_seconds'])
            text = {'stdout': result.logs.stdout, 'stderr': result.logs.stderr, 'error': str(result.error) if result.error else None}
            return json.dumps(text)[:config['max_output_bytes']]
        finally:
            await sandbox.kill()

    def dispatch(self, request):
        if not isinstance(request, dict) or request.get('jsonrpc', '2.0') != '2.0' or not isinstance(request.get('method'), str):
            raise RPCError(-32600, 'Invalid Request')
        method = request['method']
        if 'id' not in request:
            if method == 'notifications/initialized':
                self.initialized = True
            return None
        if method == 'initialize':
            result = {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {'listChanged': True}}, 'serverInfo': {'name': 'SuperCraftOS', 'version': '2.0'}}
        elif method == 'ping':
            result = {}
        elif method == 'tools/list':
            result = {'tools': list(self.tools.values())}
        elif method == 'tools/call':
            params = request.get('params', {})
            if not isinstance(params, dict):
                raise RPCError(-32602, 'Invalid params')
            name = params.get('name')
            if not isinstance(name, str) or name not in self.tools:
                raise RPCError(-32602, 'Unknown tool')
            arguments = params.get('arguments', {})
            errors = list(Draft202012Validator(self.tools[name]['inputSchema']).iter_errors(arguments))
            if errors:
                raise RPCError(-32602, 'Arguments do not match the tool schema')
            return self._call(request['id'], name, arguments)
        else:
            raise RPCError(-32601, 'Method not found')
        return {'jsonrpc': '2.0', 'id': request['id'], 'result': result}

    async def _call(self, ident, name, arguments):
        try:
            handler = self.handlers.get(name)
            if handler is None:
                raise RuntimeError('Tool schema is registered but no implementation is bound')
            if inspect.iscoroutinefunction(handler):
                value = await handler(arguments)
            else:
                value = await asyncio.to_thread(handler, arguments)
                if inspect.isawaitable(value):
                    value = await value
            result = {'content': [{'type': 'text', 'text': value if isinstance(value, str) else json.dumps(value)}]}
        except Exception as exc:
            result = {'isError': True, 'content': [{'type': 'text', 'text': f'Tool execution failed ({type(exc).__name__})'}]}
        return {'jsonrpc': '2.0', 'id': ident, 'result': result}

    async def handle(self, request):
        try:
            result = self.dispatch(request)
            return await result if inspect.isawaitable(result) else result
        except RPCError as exc:
            return {'jsonrpc': '2.0', 'id': request.get('id') if isinstance(request, dict) else None, 'error': {'code': exc.code, 'message': exc.message}}

    async def watch_registry(self):
        stamp = self.registry_path.stat().st_mtime_ns if self.registry_path.exists() else 0
        while True:
            await asyncio.sleep(1)
            updated = self.registry_path.stat().st_mtime_ns if self.registry_path.exists() else 0
            if updated != stamp:
                try:
                    self._load(); self._install_builtins()
                    stamp = updated; self.notify_changed()
                except (ValueError, OSError):
                    print('Rejected invalid MCP registry update', file=sys.stderr)

    async def serve_async(self):
        lock = asyncio.Lock()
        async def send(value):
            async with lock:
                sys.stdout.write(json.dumps(value) + '\n'); sys.stdout.flush()
        async def notifications():
            while True:
                notice = await self.notifications.get()
                if self.initialized:
                    await send(notice)
        tasks = [asyncio.create_task(self.watch_registry()), asyncio.create_task(notifications())]
        try:
            while True:
                line = await asyncio.to_thread(sys.stdin.buffer.readline, 1048577)
                if not line:
                    break
                try:
                    if len(line) > 1048576:
                        raise ValueError('Input too large')
                    request = json.loads(line)
                    response = await self.handle(request)
                except (ValueError, UnicodeError):
                    response = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Parse error'}}
                if response:
                    await send(response)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def serve(self):
        asyncio.run(self.serve_async())


if __name__ == '__main__':
    os.chdir(ROOT)
    DynamicMCPServer().serve()
