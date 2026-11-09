"""SuperCraftOS single-event-loop launcher, doctor, setup and workflow commands."""
from __future__ import annotations
import argparse
import asyncio
import importlib.metadata
import json
import os
import signal
import sys
import time
from pathlib import Path
from token_optimizer import ROOT, TokenOptimizer, load_config
from visual_cli import DashboardState, VisualCLI

CREDENTIALS = ('GMAIL_ADDRESS', 'GMAIL_APP_PASSWORD', 'GMAIL_LOGIN_PASSWORD', 'X_USERNAME', 'X_PASSWORD', 'NVIDIA_API_KEY', 'NOTION_API_KEY', 'NOTION_PARENT_PAGE_ID', 'LARK_APP_ID', 'LARK_APP_SECRET', 'LARK_NOTIFY_CHAT_ID', 'BITRISE_API_TOKEN', 'BITRISE_APP_SLUG', 'E2B_API_KEY')


def doctor():
    config = load_config()
    packages = ['httpx', 'rich', 'psutil', 'python-dotenv', 'PyYAML', 'tiktoken', 'jsonschema', 'cryptography', 'notion-client', 'langgraph', 'langgraph-checkpoint-sqlite', 'lark-oapi', 'e2b-code-interpreter']
    versions = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    report = {'root': str(ROOT), 'root_env_exists': Path('/.env').exists(), 'home_env_exists': (Path.home() / '.env').exists(),
              'credentials': {key: bool(os.getenv(key)) for key in CREDENTIALS},
              'libraries': versions, 'model_input_budget': config['models']['input_budget_tokens'],
              'memory_budget_mb': config['resources']['memory_limit_mb'],
              'agent_brain_available': (ROOT / 'agent-brain' / 'README.md').exists(),
              'external_integrations_verified': {k: v.get('status') for k, v in json.loads((ROOT / 'data' / 'service_health.json').read_text()).items() if isinstance(v, dict)} if (ROOT / 'data' / 'service_health.json').exists() else {}}
    print(json.dumps(report, indent=2))
    return 0 if all(versions.values()) else 1


async def initialize():
    from notion_db_setup import setup_from_env, sync_environment_vault
    from stealth_browser_registrar import run_registrations
    report = {}
    for name, function in [('notion', setup_from_env), ('registration', run_registrations)]:
        try:
            report[name] = await function()
            if name == 'notion' and report[name].get('status') == 'ready':
                report['vault_sync'] = await sync_environment_vault()
        except Exception as exc:
            report[name] = {'status': 'blocked', 'error_type': type(exc).__name__}
    target = ROOT / 'data' / 'initialization.json'
    target.parent.mkdir(exist_ok=True, mode=0o700)
    target.write_text(json.dumps(report, indent=2)); target.chmod(0o600)
    print(json.dumps(report, indent=2))


async def workflow(args):
    from langgraph_orchestrator import LangGraphOrchestrator
    optimizer = TokenOptimizer()
    async with LangGraphOrchestrator(optimizer) as graph:
        if args.command == 'task':
            result = await graph.start(args.query, args.thread)
        elif args.command == 'inspect':
            result = await graph.inspect(args.thread)
        else:
            result = await graph.resume(args.thread, args.command == 'approve')
        print(json.dumps(result, indent=2))


async def run(args):
    from platform_registry import watch_releases
    from dynamic_mcp_server import DynamicMCPServer
    from langgraph_orchestrator import LangGraphOrchestrator
    from lark_bot import LarkBot, build_card
    from bitrise_monitor import BitriseMonitor, configured as bitrise_configured
    from auto_upgrader import auto_upgrade_loop
    config = load_config(); optimizer = TokenOptimizer(config)
    state = DashboardState()
    state.sandbox = 'configured, unverified' if os.getenv('E2B_API_KEY') else 'unconfigured'
    dashboard = VisualCLI(state, optimizer, config['resources']['memory_limit_mb'])
    graph = LangGraphOrchestrator(optimizer)
    server = DynamicMCPServer(config['mcp']['registry_path'])
    stop = asyncio.Event()
    failures = []
    runtime_path = ROOT / 'data' / 'runtime.json'
    # Durable owner binding prevents another allowed user approving someone else's task.
    owners_path = ROOT / 'data' / 'workflow_owners.json'
    owners = json.loads(owners_path.read_text()) if owners_path.exists() else {}
    def save_owners():
        temporary = owners_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(owners)); temporary.chmod(0o600); temporary.replace(owners_path)

    async def message(text, chat_id, user):
        import uuid
        thread_id = str(uuid.uuid4())
        owners[thread_id] = {'user': user, 'chat': chat_id}; save_owners()
        state.mode = 'planning'; state.event(f'Workflow {thread_id} started')
        sent = await bot.send_card(chat_id, build_card('Planning and building the requested artifact.'))
        try:
            result = await graph.start(text, thread_id)
            state.mode = result['status']; state.event(f'Workflow {thread_id}: {result["status"]}')
            await bot.stream_card(sent['message_id'], result['artifact'], 'complete' if result['status'] == 'completed' else 'approval', result['thread_id'] if result['status'] != 'completed' else '')
        except Exception as exc:
            state.mode = 'error'; state.event(f'Workflow failed: {type(exc).__name__}')
            await bot.stream_card(sent['message_id'], f'Workflow failed ({type(exc).__name__}). Inspect local checkpoint for recovery.', 'error')

    async def approve(thread_id, approved, user):
        owner = owners.get(thread_id)
        if not owner or owner['user'] != user:
            state.event('Approval rejected: workflow owner mismatch'); return
        result = await graph.resume(thread_id, approved)
        state.mode = result['status']
        if approved:
            state.completed += 1
            directory = ROOT / 'data' / 'artifacts'; directory.mkdir(exist_ok=True, mode=0o700)
            path = directory / f'{thread_id}.md'; path.write_text(result['artifact']); path.chmod(0o600)
        state.event(f'Workflow {thread_id}: {result["status"]}')
        await bot.send_card(owner['chat'], build_card('Artifact saved locally.' if approved else 'Artifact denied; recorded in failure memory.', 'complete' if approved else 'denied'))

    bot = LarkBot(config['lark'], state, message, approve)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    state.event('Loaded agent-brain execution and evidence patterns')
    state.event('MCP catalog loaded; use main.py mcp for stdio transport')
    async def monitor():
        while not stop.is_set():
            rss = dashboard.sample()
            info = {'pid': os.getpid(), 'timestamp': time.time(), 'lark': state.lark, 'mode': state.mode, 'rss_mb': round(rss, 2), 'sandbox': state.sandbox, 'usage': optimizer.usage, 'tools': len(server.tools)}
            temporary = runtime_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(info)); temporary.chmod(0o600); temporary.replace(runtime_path)
            if rss > config['resources']['memory_limit_mb']:
                state.event('Measured memory budget exceeded; stopping runtime'); failures.append('memory budget'); stop.set()
            await asyncio.sleep(1)
    async def timer():
        await asyncio.sleep(args.seconds); stop.set()
    tasks = [asyncio.create_task(bot.run()), asyncio.create_task(dashboard.run(not args.headless and sys.stdout.isatty())), asyncio.create_task(server.watch_registry()), asyncio.create_task(monitor()), asyncio.create_task(watch_releases(stop)), asyncio.create_task(auto_upgrade_loop(stop))]
    if bitrise_configured():
        async def notify_bitrise(message):
            await bot.send_card(os.environ['LARK_NOTIFY_CHAT_ID'], build_card(message, 'complete'))
        bitrise = BitriseMonitor(os.environ['BITRISE_API_TOKEN'], os.environ['BITRISE_APP_SLUG'], notify_bitrise)
        tasks.append(asyncio.create_task(bitrise.run(stop, report=state.event)))
        state.event('Bitrise build monitoring connected to Lark notifications')
    core = None
    if args.rust_core:
        binary = ROOT / 'agent-core' / 'target' / 'release' / 'supercraftos-agent-core'
        core = await asyncio.create_subprocess_exec(str(binary), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        core.stdin.write(b'{"method":"telemetry","id":1}\n')
        await core.stdin.drain()
        acknowledgement = json.loads(await asyncio.wait_for(core.stdout.readline(), 5))
        if not acknowledgement.get('valid'):
            raise RuntimeError('Rust core protocol check failed')
        state.event('Tokio protocol worker connected')
    def supervise(task):
        if not task.cancelled() and task.exception() is not None:
            state.event(f'Background service failed: {type(task.exception()).__name__}')
            failures.append(type(task.exception()).__name__)
            stop.set()
    for task in tasks:
        task.add_done_callback(supervise)
    if args.seconds:
        tasks.append(asyncio.create_task(timer()))
    try:
        await stop.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await graph.close()
        if core is not None:
            core.stdin.close()
            try:
                await asyncio.wait_for(core.wait(), 3)
            except asyncio.TimeoutError:
                core.kill(); await core.wait()
        if runtime_path.exists():
            snapshot = json.loads(runtime_path.read_text())
            snapshot['status'] = 'stopped'
            runtime_path.write_text(json.dumps(snapshot))
    if failures:
        raise RuntimeError('Background service failure')
    print(json.dumps({'status': 'stopped', 'lark': state.lark, 'rss_mb': round(state.rss_mb, 2), 'usage': optimizer.usage}))


def main():
    os.chdir(ROOT); os.umask(0o077)
    (ROOT / 'data').mkdir(exist_ok=True, mode=0o700)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor'); sub.add_parser('setup'); sub.add_parser('mcp'); sub.add_parser('healthcheck'); sub.add_parser('research'); sub.add_parser('capabilities'); sub.add_parser('worker')
    job = sub.add_parser('submit'); job.add_argument('query'); job.add_argument('--max-steps', type=int, default=24)
    job.add_argument('--run-at', type=float)
    sub.add_parser('jobs')
    prom = sub.add_parser('promote')
    prom.add_argument('--platform', default=None)
    prom.add_argument('--all', dest='all_', action='store_true')
    prom.add_argument('--dry-run', action='store_true')
    prom.add_argument('--refresh', action=argparse.BooleanOptionalAction, default=True)
    app = sub.add_parser('app'); app.add_argument('--host', default='127.0.0.1'); app.add_argument('--port', type=int, default=8787)
    start = sub.add_parser('run'); start.add_argument('--headless', action='store_true'); start.add_argument('--seconds', type=float, default=0); start.add_argument('--rust-core', action='store_true')
    task = sub.add_parser('task'); task.add_argument('query'); task.add_argument('--thread')
    for name in ('inspect', 'approve', 'deny'):
        action = sub.add_parser(name); action.add_argument('thread')
    args = parser.parse_args()
    try:
        if args.command == 'worker':
            from agent_runtime import run_worker
            return run_worker()
        if args.command in {'submit', 'jobs'}:
            from job_store import JobStore
            from agent_runtime import public_job
            store = JobStore()
            result = public_job(store.submit(args.query, max_steps=args.max_steps, run_at=args.run_at)) if args.command == 'submit' else [public_job(job) for job in store.list()]
            print(json.dumps(result, indent=2)); return 0
        if args.command == 'doctor':
            return doctor()
        if args.command == 'research':
            from resolver_research import main as research_main
            return asyncio.run(research_main())
        if args.command == 'healthcheck':
            from service_health import ServiceHealth
            result = asyncio.run(ServiceHealth().run())
            print(json.dumps({k: {a:b for a,b in v.items() if a != 'models'} for k,v in result.items()}, indent=2)); return 0
        if args.command == 'capabilities':
            from auto_upgrader import sync_capabilities
            result = asyncio.run(sync_capabilities(explicit=True, dry_run=False, llm=True))
            print(json.dumps(result, indent=2, sort_keys=True)); return 0
        if args.command == 'mcp':
            from dynamic_mcp_server import DynamicMCPServer
            DynamicMCPServer().serve(); return 0
        if args.command == 'app':
            from supercraftos_cli import serve_dashboard
            return serve_dashboard(args.host, args.port)
        if args.command == 'promote':
            from auto_upgrader import Promoter
            print(json.dumps(asyncio.run(Promoter().run_once(
                only=args.platform, all_=args.all_, dry_run=args.dry_run, refresh=args.refresh)),
                indent=2, sort_keys=True))
            return 0
        asyncio.run(initialize() if args.command == 'setup' else run(args) if args.command == 'run' else workflow(args))
        return 0
    except Exception as exc:
        # Never write credential-bearing upstream exception text into terminal logs.
        print(f'SuperCraftOS failed: {type(exc).__name__}. Run doctor and inspect local state.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
