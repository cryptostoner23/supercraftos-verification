#!/usr/bin/env python3
"""SuperCraftOS operator CLI and authenticated local control center."""
from __future__ import annotations

import ipaddress
import argparse, asyncio, json, os, secrets, signal, socket, subprocess, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, unquote, parse_qs
from platform_registry import catalog, refresh as refresh_platforms
import digital_me
from capability_engine import refresh_policy
from product_design import build_product, screen_product, product_file, interpret_idea, product_tools
from grant_workflow import grant_catalog, screen_grants, draft_grant_application, approve_grant_application, submit_grant_application, grant_submission_history, grant_tools, saved_grant_applications

ROOT = Path(__file__).resolve().parent
REGISTRY, DASHBOARD = ROOT / "data/tools.json", ROOT / "dashboard.html"
WORKFLOWS = ROOT / "data/ui_workflows.json"


def job_store():
    from job_store import JobStore
    return JobStore(ROOT / 'data/jobs.sqlite3')


def private_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n"); temporary.chmod(0o600); temporary.replace(path)


def read_json(path: Path, default: Any) -> Any:
    try: return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError): return default


def read_tools() -> list[dict[str, Any]]:
    from dynamic_mcp_server import DynamicMCPServer
    server = DynamicMCPServer(REGISTRY)
    return sorted(server.tools.values(), key=lambda item: item['name'])


def integration_rows() -> list[dict[str, Any]]:
    rows = []
    for report in (read_json(ROOT / "data/service_health.json", {}), read_json(ROOT / "data/new-provider-health.json", {})):
        for name, value in report.items():
            if name in {"checked_at", "scope", "routing", "secret_handling"} or not isinstance(value, dict): continue
            rows.append({"name": name, "status": str(value.get("status", "unknown")),
                         "latency_ms": value.get("latency_ms") or value.get("elapsed_ms"),
                         "detail": value.get("reason") or value.get("error_code") or value.get("scope") or ""})
    unique = {row["name"]: row for row in rows}
    from account_tools import account_catalog
    for account in account_catalog().get('providers', []):
        unique[account['id']] = {'name': account['id'], 'status': account['status'], 'detail': account.get('reason', '')}
    from provider_recovery import recovery_options
    for name, row in unique.items():
        recovery = read_json(ROOT / 'data' / f'{name}.recovery.json', {})
        if recovery:
            row.update({key: recovery[key] for key in ('status', 'checked_at', 'http_status') if key in recovery})
            row['detail'] = 'Latest authenticated reconnection result'
        row.update(recovery_options(name))
    return sorted(unique.values(), key=lambda row: row["name"].lower())


def registration_rows() -> list[dict[str, Any]]:
    report = read_json(ROOT / "data/autonomous/registration-outcome.json", {})
    fresh = read_json(ROOT / "data/autonomous/firecrawl-new-account.json", {})
    if fresh: report["firecrawl"] = fresh
    return sorted([{"name": name, "status": value.get("status", "unknown"),
                    "detail": value.get("reason") or value.get("registration_status") or ""}
                   for name, value in report.items()
                   if name not in {"cloud_runtime", "verification"} and isinstance(value, dict)], key=lambda row: row["name"])


def workflow_rows() -> list[dict[str, Any]]:
    value = read_json(WORKFLOWS, [])
    return value if isinstance(value, list) else []


class AppState:
    def __init__(self):
        self.token, self.runtime = secrets.token_urlsafe(32), None
        self.lock, self.workflow_lock = threading.Lock(), threading.Lock()

    def runtime_status(self) -> str:
        if self.runtime is not None and self.runtime.poll() is None: return "running"
        snapshot = read_json(ROOT / "data/runtime.json", {})
        pid = snapshot.get("pid")
        if snapshot.get("status") == "stopped" or not pid: return "stopped"
        return "running" if self.owns_runtime(pid) else "stopped"

    @staticmethod
    def owns_runtime(pid) -> bool:
        try:
            if int(pid) <= 1: return False
            argv = Path(f"/proc/{int(pid)}/cmdline").read_bytes().split(b"\0")
            return len(argv) > 2 and argv[1] == str(ROOT / "main.py").encode() and argv[2] == b"run"
        except (OSError, TypeError, ValueError): return False

    def start_runtime(self) -> dict[str, Any]:
        with self.lock:
            if self.runtime is not None and self.runtime.poll() is None: return {"status": "running", "pid": self.runtime.pid}
            snapshot = read_json(ROOT / "data/runtime.json", {})
            if self.owns_runtime(snapshot.get("pid")): return {"status": "running", "pid": snapshot["pid"]}
            self.runtime = subprocess.Popen([sys.executable, str(ROOT / "main.py"), "run", "--headless"], cwd=ROOT,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return {"status": "running", "pid": self.runtime.pid}

    def stop_runtime(self) -> dict[str, Any]:
        with self.lock:
            process = self.runtime
            pid = process.pid if process is not None and process.poll() is None else read_json(ROOT / "data/runtime.json", {}).get("pid")
            if not pid: return {"status": "stopped"}
            try:
                if not self.owns_runtime(pid): return {"status": "stopped"}
                os.kill(int(pid), signal.SIGTERM)
            except (OSError, TypeError, ValueError): return {"status": "stopped"}
            if process is None: return {"status": "stopping", "pid": int(pid)}
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired: return {"status": "stopping", "pid": process.pid}
            return {"status": "stopped"}


STATE = AppState()


def overview() -> dict[str, Any]:
    runtime = read_json(ROOT / "data/runtime.json", {})
    usage = read_json(ROOT / "data/usage.json", runtime.get("usage", {}))
    integrations, workflows = integration_rows(), workflow_rows()
    good = {"active", "authenticated", "reachable", "verified", "passed", "ready", "verified_existing", "verified_new", "verified_profile"}
    return {"project": "SuperCraftOS", "root": str(ROOT), "timestamp": time.time(), "runtime": STATE.runtime_status(),
            "runtime_snapshot": runtime, "usage": usage, "memory_mb": runtime.get("rss_mb", 0), "memory_limit_mb": 512,
            "tools": len(read_tools()), "integrations": len(integrations),
            "healthy_integrations": sum(row["status"] in good for row in integrations), "workflows": len(workflows),
            "awaiting_approval": sum(row.get("status") == "awaiting_approval" for row in workflows),
            "agent_brain": (ROOT / "agent-brain/.git").exists()}


def rpc(request: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    proc = subprocess.run([sys.executable, str(ROOT / "dynamic_mcp_server.py")], input=json.dumps(request) + "\n",
                          text=True, capture_output=True, cwd=ROOT, timeout=timeout)
    responses = [json.loads(line) for line in proc.stdout.splitlines() if line.lstrip().startswith("{")]
    if not responses: raise RuntimeError("MCP server returned no response")
    return next((item for item in reversed(responses) if "id" in item), responses[-1])


def run_workflow(query: str, thread_id: str | None = None, decision: str | None = None) -> dict[str, Any]:
    thread_id = thread_id or str(uuid.uuid4())
    command = [sys.executable, str(ROOT / "main.py"), decision or "task"]
    command.extend([thread_id] if decision else [query, "--thread", thread_id])
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180)
    if proc.returncode: return {"thread_id": thread_id, "query": query, "status": "failed", "error": "workflow_process_failed"}
    try: result = json.loads(proc.stdout)
    except json.JSONDecodeError: return {"thread_id": thread_id, "query": query, "status": "failed", "error": "invalid_workflow_response"}
    result["thread_id"] = thread_id; result.setdefault("query", query)
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "SuperCraftOS/2"
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *_): pass

    def end_headers(self):
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def local_host(self) -> bool:
        # The server only ever binds to loopback, so it is reached through a
        # local proxy. That proxy may present the loopback name, or the
        # private address of the machine on the local network, so the phone can
        # reach the agent on a LAN with no internet, no VPN and no mesh tunnel.
        try:
            hostname = urlparse("//" + self.headers.get("Host", "")).hostname
            if hostname is None: return False
            if hostname in {"127.0.0.1", "localhost", "::1"}: return True
            return self.is_private_host(hostname)
        except ValueError: return False

    @staticmethod
    def is_private_host(hostname: str) -> bool:
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return hostname.lower().endswith(".local")
        return address.is_private or address.is_loopback or address.is_link_local

    def send_json(self, value: Any, code: int = 200):
        body = json.dumps(value, default=str).encode(); self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def authorized(self) -> bool:
        origin = self.headers.get("Origin")
        try:
            return (self.local_host() and
                    (not origin or origin == 'http://' + self.headers.get('Host', '')) and
                    secrets.compare_digest(self.headers.get("X-SuperCraftOS-Token", ""), STATE.token))
        except (ValueError, TypeError): return False

    def payload(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 <= length <= 65536: raise ValueError
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict): raise ValueError
        return value

    def do_GET(self):
        if not self.local_host():
            return self.send_json({"error": "invalid_host"}, 403)
        path = urlparse(self.path).path
        if path in {'/api/quests/sources', '/api/quests/leads'}:
            from quest_workflow import quest_sources, QuestStore
            try:
                return self.send_json(quest_sources() if path.endswith('/sources') else {'leads': QuestStore().leads()})
            except (ValueError, OSError):
                return self.send_json({'error': 'state_unavailable'}, 503)
        if path == '/api/accounts':
            from account_tools import account_catalog
            return self.send_json(account_catalog())
        if path == '/api/agent/memory':
            from execution_learning import memory_view
            return self.send_json(memory_view(job_store()))
        if path == '/api/agent/status':
            import shutil
            return self.send_json({'workers': job_store().worker_count(),
                'model_configured': any(os.getenv(k) for k in ('SUPERCRAFTOS_LLM_API_KEY', 'OPENROUTER_API_KEY', 'NVIDIA_API_KEY', 'OPENCODE_GO_API_KEY')),
                'sandbox_cli_available': shutil.which('docker') is not None,
                'lessons': len(job_store().lessons())})
        if path == '/api/jobs':
            from agent_runtime import public_job
            return self.send_json({'jobs': [public_job(job) for job in job_store().list()]})
        if path.startswith('/api/jobs/'):
            from agent_runtime import public_job
            from agent_tools import Workspace
            parts = path.strip('/').split('/')
            if len(parts) < 3:
                return self.send_json({'error': 'not_found'}, 404)
            store = job_store()
            job = store.get(parts[2])
            if job is None:
                return self.send_json({'error': 'job_not_found'}, 404)
            if len(parts) == 3:
                return self.send_json(public_job(job))
            if len(parts) == 4 and parts[3] == 'events':
                try:
                    after = int(parse_qs(urlparse(self.path).query).get('after', ['0'])[0])
                    if not 0 <= after <= 9223372036854775807:
                        raise ValueError('invalid cursor')
                except ValueError:
                    return self.send_json({'error': 'invalid_cursor'}, 400)
                return self.send_json({'events': store.events(parts[2], max(0, after))})
            if len(parts) == 4 and parts[3] == 'trace':
                from agent_trace import task_trace
                try:
                    after = int(parse_qs(urlparse(self.path).query).get('after', ['0'])[0])
                    if not 0 <= after <= 9223372036854775807:
                        raise ValueError('invalid cursor')
                except ValueError:
                    return self.send_json({'error': 'invalid_cursor'}, 400)
                return self.send_json(task_trace(job, store.events(parts[2], max(0, after))))
            if len(parts) >= 5 and parts[3] == 'files':
                if job['status'] != 'completed':
                    return self.send_json({'error': 'task_files_not_final'}, 409)
                try:
                    file = Workspace(parts[2], ROOT / 'data/workspaces').path(unquote('/'.join(parts[4:])), existing=True)
                    if file.stat().st_size > 50_000_000:
                        raise ValueError('file too large')
                    body = file.read_bytes()
                    expected = next((entry for entry in job['result'].get('files', []) if entry['path'] == unquote('/'.join(parts[4:]))), None)
                    if expected is None or expected['bytes'] != len(body) or expected['sha256'] != __import__('hashlib').sha256(body).hexdigest():
                        return self.send_json({'error': 'artifact_changed_since_verification'}, 409)
                except (ValueError, OSError):
                    return self.send_json({'error': 'file_not_found'}, 404)
                self.send_response(200); self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + __import__('urllib.parse', fromlist=['quote']).quote(file.name))
                self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
                return
            return self.send_json({'error': 'not_found'}, 404)
        if path == '/api/notes':
            from apple_notes import list_notes
            try:
                query = parse_qs(urlparse(self.path).query).get('q', [''])[0]
                return self.send_json({'notes': list_notes(query)})
            except (OSError, ValueError):
                return self.send_json({'error': 'state_unavailable'}, 503)
        if path == '/api/notes/notebooks':
            from apple_notes import list_notebooks
            try:
                return self.send_json({'notebooks': list_notebooks()})
            except (OSError, ValueError):
                return self.send_json({'error': 'state_unavailable'}, 503)
        if path.startswith('/api/notes/'):
            parts = path.strip('/').split('/')
            if len(parts) == 3:
                from apple_notes import get_note
                try:
                    note = get_note(parts[2])
                except (OSError, ValueError):
                    return self.send_json({'error': 'state_unavailable'}, 503)
                if note is None:
                    return self.send_json({'error': 'not_found'}, 404)
                return self.send_json(note)
            return self.send_json({'error': 'not_found'}, 404)
        routes = {"/api/session": lambda: {"token": STATE.token},
                  "/api/status": overview, "/api/tools": lambda: {"tools": read_tools()},
                  "/api/platforms": catalog,
                  "/api/capabilities": refresh_policy,
                  "/api/grants/catalog": lambda: grant_catalog({}),
                  '/api/grants/packages': saved_grant_applications,
                  "/api/integrations": lambda: {"integrations": integration_rows()},
                  "/api/registrations": lambda: {"registrations": registration_rows()},
                  "/api/workflows": lambda: {"workflows": workflow_rows()},
                  "/api/digital_me/profile": lambda: (lambda dm: dm.api_profile_get())(__import__('digital_me')),
                  "/api/digital_me/memory": lambda: (lambda dm: dm.api_memory_get())(__import__('digital_me')),
                  "/api/digital_me/reasoning": lambda: {"status": "ready"}}
        if path in routes:
            try: value = routes[path]()
            except (OSError, ValueError, TypeError, AttributeError): return self.send_json({"error": "state_unavailable"}, 503)
            return self.send_json(value)
        if path in {"/", "/index.html", "/agents"}:
            page = ROOT / 'agents.html' if path == '/agents' else DASHBOARD
            body = page.read_text().replace("__SUPERCRAFTOS_TOKEN__", STATE.token).encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if path.startswith('/api/products/'):
            parts = path.strip('/').split('/')
            if len(parts) != 5 or parts[3] != 'files': return self.send_json({'error': 'not_found'}, 404)
            try: artifact = product_file(parts[2], parts[4])
            except (ValueError, FileNotFoundError): return self.send_json({'error': 'not_found'}, 404)
            body = artifact.read_bytes()
            self.send_response(200); self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{artifact.name}"')
            self.send_header('Content-Length', str(len(body))); self.send_header('Cache-Control', 'no-store')
            self.end_headers(); self.wfile.write(body); return
        self.send_json({"error": "not_found"}, 404)

    def do_POST(self):
        if not self.authorized(): return self.send_json({"error": "unauthorized"}, 403)
        path = urlparse(self.path).path
        try:
            payload = self.payload()
            if path == '/api/build-log':
                text = payload.get('text', '')
                if isinstance(text, str) and text:
                    d = ROOT / 'data' / 'build-logs'; d.mkdir(parents=True, exist_ok=True)
                    (d / f"{int(time.time())}.txt").write_text(text)
                    return self.send_json({'ok': True}, 201)
                return self.send_json({'error': 'empty'}, 400)
            if path == '/api/integrations/reconnect':
                from provider_recovery import reconnect
                return self.send_json(asyncio.run(reconnect(payload)))
            if path == '/api/tools/call':
                name, arguments = payload.get('name'), payload.get('arguments', {})
                if (set(payload) - {'name', 'arguments'} or not isinstance(name, str)
                        or not 1 <= len(name) <= 128 or not isinstance(arguments, dict)):
                    return self.send_json({'error': 'invalid_tool_request'}, 400)
                response = rpc({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                                'params': {'name': name, 'arguments': arguments}}, timeout=180)
                if len(json.dumps(response).encode()) > 2_000_000:
                    return self.send_json({'error': 'tool_response_too_large'}, 502)
                return self.send_json(response, 400 if 'error' in response else 200)
            if path == '/api/accounts/register':
                from autonomous_registration import PROVIDERS
                from agent_runtime import public_job
                from job_store import Conflict
                provider = payload.get('provider')
                if not isinstance(provider, str) or provider not in PROVIDERS or set(payload) != {'provider'}:
                    return self.send_json({'error': 'invalid_provider'}, 400)
                query = (f'Use register_developer_account to verify the existing {provider} account or create a free developer account and obtain its API credential. '
                    'Do not duplicate a pending signup. Keep all keys, passwords and private page content on the server. '
                    'If the tool verifies the credential, write a concise account-verification.json receipt and README explaining the actual result, '
                    'then run a check that the receipt has no credentials and matches the actual provider status. '
                    'If verification cannot finish, report the exact blocker instead of claiming an account or working key.')
                try:
                    job = job_store().submit(query, max_steps=18, idempotency_key=self.headers.get('Idempotency-Key'),
                        initial_state={'workflow': 'developer_account', 'account_provider': provider,
                            'required_native': [{'name': 'register_developer_account', 'provider': provider}]})
                except Conflict as exc:
                    return self.send_json({'error': str(exc)}, 409)
                return self.send_json(public_job(job), 202)
            if path == '/api/digital_me/memory':
                if 'entry' in payload:
                    return self.send_json(digital_me.api_memory_post(payload['entry']))
                return self.send_json({'error': 'missing entry in payload'})
            if path == '/api/agent/memory/forget':
                return self.send_json({'forgotten': job_store().forget_lesson(payload.get('id'))})
            if path.startswith('/api/quests/'):
                from quest_workflow import discover_quests, screen_quests, run_quests, quest_receipts
                handlers = {'/api/quests/discover': discover_quests, '/api/quests/screen': screen_quests,
                    '/api/quests/run': run_quests, '/api/quests/receipts': quest_receipts}
                if path not in handlers:
                    return self.send_json({'error': 'not_found'}, 404)
                return self.send_json(handlers[path](payload))
            if path == '/api/jobs':
                from agent_runtime import public_job
                from job_store import Conflict
                try:
                    result = job_store().submit(payload.get('query'), max_steps=payload.get('max_steps', 24),
                        run_at=payload.get('run_at'), idempotency_key=self.headers.get('Idempotency-Key'))
                except Conflict as exc:
                    return self.send_json({'error': str(exc)}, 409)
                return self.send_json(public_job(result), 202)
            if path.startswith('/api/jobs/'):
                from agent_runtime import public_job
                from job_store import Conflict
                parts = path.strip('/').split('/')
                if len(parts) != 4 or parts[3] not in {'cancel', 'retry'}:
                    return self.send_json({'error': 'not_found'}, 404)
                store = job_store()
                if store.get(parts[2]) is None:
                    return self.send_json({'error': 'job_not_found'}, 404)
                try:
                    result = store.cancel(parts[2]) if parts[3] == 'cancel' else store.retry(parts[2])
                except Conflict as exc:
                    return self.send_json({'error': str(exc)}, 409)
                return self.send_json(public_job(result))
            if path == '/api/products/screen':
                try: return self.send_json(screen_product(payload))
                except ValueError as exc:
                    return self.send_json({'error': 'invalid_request', 'detail': str(exc)}, 400)
            if path == '/api/products/interpret':
                try: result = asyncio.run(interpret_idea(payload.get('idea')))
                except ValueError as exc:
                    return self.send_json({'error': 'unsupported_or_invalid_design_brief', 'detail': str(exc)}, 400)
                except Exception: return self.send_json({'error': 'design_model_unavailable'}, 503)
                return self.send_json(result)
            if path == '/api/products/build':
                try: result = build_product(payload)
                except RuntimeError: return self.send_json({'error': 'cad_unavailable_or_resource_limit'}, 503)
                except ValueError as exc:
                    return self.send_json({'error': 'invalid_request', 'detail': str(exc)}, 400)
                return self.send_json(result, 201)
            if path == '/api/grants/catalog':
                try: return self.send_json(grant_catalog(payload))
                except ValueError as exc: return self.send_json({'error': 'invalid_request', 'detail': str(exc)}, 400)
            if path == '/api/grants/screen': return self.send_json(screen_grants(payload))
            if path == '/api/grants/draft':
                try: return self.send_json(draft_grant_application(payload), 201)
                except ValueError as exc: return self.send_json({'error': 'invalid_grant_request', 'detail': str(exc)}, 400)
            if path == '/api/grants/approve':
                try: return self.send_json(approve_grant_application(payload))
                except ValueError as exc: return self.send_json({'error': 'grant_approval_failed', 'detail': str(exc)}, 400)
            if path == '/api/grants/submit':
                try: return self.send_json(submit_grant_application(payload))
                except ValueError as exc: return self.send_json({'error': 'grant_submission_failed', 'detail': str(exc)}, 400)
            if path == '/api/grants/submission-history':
                try: return self.send_json(grant_submission_history(payload))
                except ValueError as exc: return self.send_json({'error': 'grant_history_failed', 'detail': str(exc)}, 400)
            if path == "/api/digital_me/profile": return self.send_json(digital_me.api_profile_get())
            if path == "/api/digital_me/memory":
                if "entry" in payload:
                    return self.send_json(digital_me.api_memory_post(payload["entry"]))
                return self.send_json({"error": "missing entry in payload"})
            if path == "/api/digital_me/reasoning":
                return self.send_json(digital_me.api_reasoning_post(payload))
            if path == "/api/digital_me/planning":
                return self.send_json(digital_me.api_planning_post(payload))
            if path == "/api/digital_me/planning/{}":
                parts = path.strip("/").split("/")
                if len(parts) == 5 and parts[3] == "planning" and len(parts) == 5:
                    return self.send_json(digital_me.api_planning_get(parts[4]))
                return self.send_json({"error": "not_found"}, 404)
            if path == '/api/notes':
                from apple_notes import create_note
                note = create_note(payload.get('title', ''), payload.get('body', ''),
                                   payload.get('notebook', 'Default'), payload.get('tags'))
                return self.send_json(note, 201)
            if path == '/api/notes/ingest':
                from apple_notes import create_note
                body = payload.get('body') or ''
                if not isinstance(body, str):
                    return self.send_json({'error': 'invalid_request'}, 400)
                raw_title = (payload.get('title') or '').strip() or next(
                    (line.strip() for line in body.splitlines() if line.strip()), '')
                title = raw_title[:200] or 'Imported Apple Note'
                fmt = str(payload.get('format') or 'text').lower()
                if fmt not in {'text', 'rtf', 'html'}:
                    fmt = 'text'
                source = str(payload.get('source') or 'apple_notes')[:64]
                notebook = str(payload.get('notebook') or 'Apple Notes')[:60]
                note = create_note(title, body, notebook=notebook, tags=['apple_notes'])
                try:
                    from digital_me import add_memory_entry
                    digest = ' '.join(body.split())[:500]
                    add_memory_entry({'note': f"Imported {source} '{note['title']}': {digest}",
                                      'source': source, 'format': fmt})
                except Exception:
                    pass
                return self.send_json({**note, 'source': source, 'format': fmt}, 201)
            if path.startswith('/api/notes/'):
                from apple_notes import (add_checklist_item, delete_note, pin_note,
                                         toggle_checklist_item, update_note)
                parts = path.strip('/').split('/')
                if len(parts) == 4 and parts[3] in {'update', 'delete', 'pin'}:
                    note_id, action = parts[2], parts[3]
                    try:
                        if action == 'update':
                            return self.send_json(update_note(note_id, payload))
                        if action == 'delete':
                            return self.send_json(delete_note(note_id))
                        return self.send_json(pin_note(note_id))
                    except KeyError:
                        return self.send_json({'error': 'note_not_found'}, 404)
                if len(parts) == 5 and parts[3] == 'checklist' and parts[4] in {'add', 'toggle'}:
                    note_id, op = parts[2], parts[4]
                    try:
                        if op == 'add':
                            return self.send_json(add_checklist_item(note_id, payload.get('text', '')))
                        return self.send_json(toggle_checklist_item(note_id, payload.get('index')))
                    except KeyError:
                        return self.send_json({'error': 'note_not_found'}, 404)
                return self.send_json({"error": "not_found"}, 404)
            if path == "/api/runtime/start": return self.send_json(STATE.start_runtime())
            if path == "/api/runtime/stop": return self.send_json(STATE.stop_runtime())
            if path == "/api/workflows":
                if not isinstance(payload.get("query"), str): return self.send_json({"error": "query_type"}, 400)
                query = payload["query"].strip()
                if not 3 <= len(query) <= 4000: return self.send_json({"error": "query_length"}, 400)
                with STATE.workflow_lock:
                    result, rows = run_workflow(query), workflow_rows()
                    rows.insert(0, {k: result.get(k) for k in ("thread_id", "query", "status", "plan", "artifact", "error")})
                    private_json(WORKFLOWS, rows[:100])
                return self.send_json(result, 201)
            if path.startswith("/api/workflows/"):
                parts = path.strip("/").split("/")
                if len(parts) != 4 or parts[3] not in {"approve", "deny"}: return self.send_json({"error": "not_found"}, 404)
                thread_id, decision = parts[2], parts[3]
                with STATE.workflow_lock:
                    rows = workflow_rows()
                    existing = next((row for row in rows if row.get("thread_id") == thread_id), None)
                    if not existing: return self.send_json({"error": "workflow_not_found"}, 404)
                    if existing.get("status") != "awaiting_approval": return self.send_json({"error": "workflow_not_pending"}, 409)
                    result = run_workflow(existing.get("query", ""), thread_id, decision)
                    existing.update({k: result.get(k) for k in ("status", "artifact", "error")}); private_json(WORKFLOWS, rows)
                return self.send_json(result)
            return self.send_json({"error": "not_found"}, 404)
        except (ValueError, json.JSONDecodeError): return self.send_json({"error": "invalid_request"}, 400)
        except subprocess.TimeoutExpired: return self.send_json({"error": "workflow_timeout"}, 504)
        except (OSError, RuntimeError): return self.send_json({"error": "local_service_unavailable"}, 503)


class BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler):
        self.slots = threading.BoundedSemaphore(16)
        if ":" in address[0]: self.address_family = socket.AF_INET6
        super().__init__(address, handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            try: request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError: pass
            self.shutdown_request(request)
            return
        try: super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try: super().process_request_thread(request, address)
        finally: self.slots.release()


def doctor() -> int:
    for command, cwd in [([sys.executable, "-m", "unittest", "discover", "-q"], ROOT), (["cargo", "check", "--quiet"], ROOT / "agent-core")]:
        result = subprocess.run(command, cwd=cwd)
        if result.returncode: return result.returncode
    print(json.dumps(overview(), indent=2)); return 0


def serve_dashboard(host: str = "127.0.0.1", port: int = 8787) -> int:
    if host not in {"127.0.0.1", "localhost", "::1"}: raise SystemExit("Dashboard binds to loopback only")
    server = BoundedHTTPServer((host, port), Handler); print(f"SuperCraftOS: http://{host}:{port}")
    stop_updates = threading.Event()
    if os.getenv('SUPERCRAFTOS_EMBEDDED_WORKER', '1') == '1':
        from agent_runtime import AgentWorker
        threading.Thread(target=lambda: asyncio.run(AgentWorker().run(stop_updates)), name='autonomous-worker', daemon=True).start()
    def updates():
        while not stop_updates.is_set():
            try: refresh_policy()
            except (OSError, ValueError): pass
            if time.time() - (catalog().get('checked_at') or 0) >= 86400:
                try: asyncio.run(refresh_platforms())
                except (OSError, ValueError): pass
            stop_updates.wait(60)
    threading.Thread(target=updates, name='platform-release-monitor', daemon=True).start()
    try: server.serve_forever()
    except KeyboardInterrupt: return 0
    finally: stop_updates.set(); STATE.stop_runtime(); server.server_close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="supercraftos", description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status"); sub.add_parser("doctor"); sub.add_parser("mcp-list")
    call = sub.add_parser("mcp-call"); call.add_argument("name"); call.add_argument("--arguments", default="{}")
    dash = sub.add_parser("dashboard"); dash.add_argument("--host", default="127.0.0.1"); dash.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    if args.command == "status": print(json.dumps(overview(), indent=2)); return 0
    if args.command == "doctor": return doctor()
    if args.command == "mcp-list": print(json.dumps(rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}), indent=2)); return 0
    if args.command == "mcp-call":
        print(json.dumps(rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": args.name, "arguments": json.loads(args.arguments)}}), indent=2)); return 0
    return serve_dashboard(args.host, args.port)


if __name__ == "__main__": raise SystemExit(main())
