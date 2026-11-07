"""Durable, provider-specific grant submission execution.

The grant catalogue contains programme pages, not invented APIs.  This module
keeps that distinction explicit: an adapter is usable only when a documented
JSON endpoint is configured for the programme and its host is in the official
allowlist.  Every attempt is idempotent, persisted, and returns the provider's
receipt or a precise unsupported status.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


ROOT = Path(__file__).resolve().parent
DEFAULT_STORE = ROOT / "data" / "grants"
MAX_BODY = 100_000
MAX_RESPONSE = 50_000


class SubmissionError(ValueError):
    """A submission request is invalid or cannot be executed safely."""


def _program_slug(program_id: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in program_id.upper())


def official_hosts(program: dict[str, Any]) -> set[str]:
    hosts: set[str] = set()
    for key in ("official_url", "application_url"):
        value = program.get(key)
        if isinstance(value, str):
            parsed = urllib.parse.urlparse(value)
            if parsed.scheme == "https" and parsed.hostname:
                hosts.add(parsed.hostname.lower().rstrip("."))
    return hosts


def is_official_url(url: str, program: dict[str, Any]) -> bool:
    """Require HTTPS and an exact official host from the programme metadata."""
    try:
        if not url.isascii() or re.search(r"[\s\x00-\x1f\x7f\\]", url):
            return False
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
        query = urllib.parse.parse_qsl(parsed.query, max_num_fields=32)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    return (parsed.scheme == "https" and parsed.username is None and parsed.password is None
            and port in (None, 443) and not parsed.fragment and host in official_hosts(program)
            and not any(re.search(r"token|secret|password|api.?key|signature|credential", key, re.I)
                        for key, _ in query))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _receipt_status(receipt: Any) -> bool:
    """A transport success is not proof that a provider accepted an application."""
    if not isinstance(receipt, dict):
        return False
    state = receipt.get("status", receipt.get("receipt"))
    ident = receipt.get("application_id", receipt.get("receipt_id"))
    return (isinstance(state, str) and state in {"accepted", "submitted", "completed"} and isinstance(ident, str)
            and 1 <= len(ident.strip()) <= 200 and not re.search(r"[\x00-\x1f\x7f]", ident))


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("non-finite JSON value")


@dataclass(frozen=True)
class SubmissionResult:
    status: str
    provider: str
    package_id: str
    attempt_id: str
    endpoint: str
    receipt: dict[str, Any] | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        value = {
            "status": self.status,
            "provider": self.provider,
            "package_id": self.package_id,
            "attempt_id": self.attempt_id,
            "endpoint": self.endpoint,
        }
        if self.receipt is not None:
            value["receipt"] = self.receipt
        if self.reason is not None:
            value["reason"] = self.reason
        return value


class GrantAdapter(Protocol):
    provider: str

    def submit(self, package: dict[str, Any], program: dict[str, Any], attempt_id: str) -> SubmissionResult:
        ...


class JsonEndpointAdapter:
    """POST a complete packet to a programme-owned JSON endpoint.

    The endpoint is opt-in through an environment variable because the
    reviewed catalogue currently documents web forms, not universal APIs.
    This adapter is therefore immediately usable by any programme that
    publishes an approved JSON intake endpoint, without changing code.
    """

    provider = "official_json_endpoint"

    def __init__(self, endpoint: str, opener=None, timeout: float = 30.0):
        self.endpoint = endpoint
        self.opener = opener or urllib.request.build_opener(_NoRedirect()).open
        self.timeout = timeout

    def submit(self, package: dict[str, Any], program: dict[str, Any], attempt_id: str) -> SubmissionResult:
        package_id = str(package["id"])
        body = json.dumps({
            "application": package.get("draft", {}),
            "evidence": package.get("evidence", []),
            "programme_id": package.get("program_id"),
            "idempotency_key": attempt_id,
        }, separators=(",", ":")).encode("utf-8")
        if len(body) > MAX_BODY:
            raise SubmissionError("application packet exceeds the submission size limit")
        request = urllib.request.Request(self.endpoint, data=body, method="POST", headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Idempotency-Key": attempt_id,
            "User-Agent": "SuperCraftOS-grant-agent/1.0",
        })
        try:
            with self.opener(request, timeout=self.timeout) as response:
                status = int(response.status)
                if response.geturl() != self.endpoint:
                    return SubmissionResult("verification_required", self.provider, package_id, attempt_id,
                                            self.endpoint, reason="Provider response location changed; reconcile before retry.")
                raw = response.read(MAX_RESPONSE + 1)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            return SubmissionResult("verification_required", self.provider, package_id, attempt_id,
                                    self.endpoint, reason=f"Provider HTTP {code}; reconcile before retry.")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return SubmissionResult("verification_required", self.provider, package_id, attempt_id,
                                    self.endpoint, reason=f"Transport {type(exc).__name__}; outcome requires reconciliation.")
        if len(raw) > MAX_RESPONSE:
            return SubmissionResult("verification_required", self.provider, package_id, attempt_id,
                                    self.endpoint, reason="Provider response exceeded size limit; reconcile before retry.")
        try:
            receipt = json.loads(raw.decode("utf-8"), object_pairs_hook=_json_object,
                                 parse_constant=_invalid_constant) if raw else {}
        except (UnicodeDecodeError, ValueError, RecursionError):
            receipt = {}
        if status < 200 or status >= 300:
            return SubmissionResult("verification_required", self.provider, package_id, attempt_id,
                                    self.endpoint, reason=f"Provider HTTP {status}; reconcile before retry.")
        if not _receipt_status(receipt):
            return SubmissionResult("verification_required", self.provider, package_id, attempt_id,
                                    self.endpoint, reason="Provider returned no explicit accepted status and application receipt.")
        evidence = {key: receipt[key] for key in ("status", "receipt", "application_id", "receipt_id") if key in receipt}
        return SubmissionResult("submitted", self.provider, package_id, attempt_id, self.endpoint, receipt=evidence)


class SubmissionStore:
    def __init__(self, root: Path = DEFAULT_STORE):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "submissions.sqlite3"
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS attempts (
                attempt_id TEXT PRIMARY KEY, package_id TEXT NOT NULL, program_id TEXT NOT NULL,
                status TEXT NOT NULL, provider TEXT NOT NULL, endpoint TEXT NOT NULL,
                result_json TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS attempts_package ON attempts(package_id, updated_at DESC)")
            db.execute("""CREATE TABLE IF NOT EXISTS executions (
                package_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL UNIQUE
            )""")

    def save(self, result: SubmissionResult, program_id: str) -> None:
        now = int(time.time())
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                result.attempt_id, result.package_id, program_id, result.status, result.provider,
                result.endpoint, json.dumps(result.as_dict(), separators=(",", ":")), now, now))

    def history(self, package_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT result_json FROM attempts WHERE package_id=? ORDER BY updated_at DESC LIMIT ?", (package_id, limit)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def reserve(self, package_id: str, program_id: str, endpoint: str) -> tuple[SubmissionResult | None, dict[str, Any] | None]:
        """Commit one external intent before sending; retries must reconcile first."""
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT a.result_json FROM executions e JOIN attempts a ON a.attempt_id=e.attempt_id WHERE e.package_id=?", (package_id,)).fetchone()
            if row is None:
                row = db.execute("SELECT result_json FROM attempts WHERE package_id=? AND status IN ('submitted','verification_required','in_progress') ORDER BY created_at DESC LIMIT 1", (package_id,)).fetchone()
            if row is not None:
                return None, json.loads(row[0])
            attempt_id = _attempt_id(package_id)
            result = SubmissionResult("in_progress", "official_json_endpoint", package_id, attempt_id, endpoint,
                                      reason="Submission reserved; reconcile with provider if interrupted.")
            now = int(time.time())
            db.execute("INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (attempt_id, package_id, program_id, result.status, result.provider, endpoint,
                        json.dumps(result.as_dict(), separators=(",", ":")), now, now))
            db.execute("INSERT INTO executions VALUES (?, ?)", (package_id, attempt_id))
        return result, None


def adapter_for(program: dict[str, Any], environ: dict[str, str] | None = None, opener=None) -> GrantAdapter | None:
    env = os.environ if environ is None else environ
    endpoint = env.get(f"SUPERCRAFTOS_GRANT_ENDPOINT_{_program_slug(str(program.get('id', '')))}", "").strip()
    if not endpoint:
        from grant_browser import FORM_URL, OfficialNotionGrantAdapter
        if program.get('id') == 'uniswap-foundation-grants' and program.get('application_url') == FORM_URL:
            return OfficialNotionGrantAdapter(env, preferences_path=ROOT / 'data/applicant-profile.json' if environ is None else None)
        return None
    if not is_official_url(endpoint, program):
        raise SubmissionError("configured endpoint is outside the programme's official HTTPS hosts")
    return JsonEndpointAdapter(endpoint, opener=opener)


def _attempt_id(package_id: str) -> str:
    return hashlib.sha256(f"{package_id}:{time.time_ns()}".encode()).hexdigest()[:32]


def submit_package(package: dict[str, Any], program: dict[str, Any], *, store_root: Path = DEFAULT_STORE,
                   environ: dict[str, str] | None = None, opener=None) -> dict[str, Any]:
    """Submit once through a configured official adapter and persist outcome."""
    package_id = package.get("id")
    if not isinstance(package_id, str):
        raise SubmissionError("package has no valid id")
    adapter = adapter_for(program, environ=environ, opener=opener)
    missing = package.get("missing_information", []) or []
    if adapter is not None and hasattr(adapter, 'missing_fields'):
        missing = list(missing) + adapter.missing_fields(package)
    if adapter is not None and isinstance(missing, list) and missing:
        result = SubmissionResult("needs_information", adapter.provider, package_id,
                                  _attempt_id(package_id), adapter.endpoint,
                                  reason="Complete the application packet before sending: " + ", ".join(str(item) for item in missing[:12]))
        SubmissionStore(store_root).save(result, str(program.get("id", "")))
        return result.as_dict()
    if adapter is None:
        attempt_id = _attempt_id(package_id)
        surface = str(program.get("submission_surface", "web_form"))
        reason = (f"official {surface} intake is available at the recorded application URL; "
                  "this runtime has no authenticated submission session for that interface")
        result = SubmissionResult("unsupported", surface, package_id, attempt_id, str(program.get("application_url", "")), reason=reason)
    else:
        store = SubmissionStore(store_root)
        reservation, previous = store.reserve(package_id, str(program.get("id", "")), adapter.endpoint)
        if previous is not None:
            return {"status": "already_attempted", "provider": previous["provider"],
                    "package_id": package_id, "attempt_id": previous["attempt_id"],
                    "endpoint": previous["endpoint"], "previous_status": previous["status"],
                    "receipt": previous.get("receipt"),
                    "reason": "A submission intent already exists; reconcile its provider receipt before retry."}
        assert reservation is not None
        result = adapter.submit(package, program, reservation.attempt_id)
        store.save(result, str(program.get("id", "")))
        # This adapter only returns needs_information before clicking Submit.
        # A corrected packet can therefore retry without replaying a dispatch.
        if result.status == 'needs_information' and adapter.provider == 'official_notion_form':
            with sqlite3.connect(store.path) as db:
                db.execute('DELETE FROM executions WHERE package_id=? AND attempt_id=?',
                           (package_id, reservation.attempt_id))
        return result.as_dict()
    SubmissionStore(store_root).save(result, str(program.get("id", "")))
    return result.as_dict()


def submission_history(package_id: str, *, store_root: Path = DEFAULT_STORE) -> list[dict[str, Any]]:
    if not isinstance(package_id, str) or not package_id:
        raise SubmissionError("package_id is required")
    return SubmissionStore(store_root).history(package_id)
