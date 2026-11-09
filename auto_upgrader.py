"""Automatic dependency promotion for SuperCraftOS.

This closes the gap called out in docs/research/PLATFORMS_AND_PRODUCT_LAB.md
(lines 55-59): official-release *discovery* already lives in ``platform_registry``,
but "unattended source self-modification and automatic dependency promotion" was
intentionally left unimplemented. This module adds the promotion half, under the
strict safety contract the spec mandates:

  * upgrades never run in the live environment (.venv / .cad-venv are untouched);
    each candidate is staged in a throwaway virtualenv under data/promotions/.
  * every staged subprocess runs with all secret environment variables stripped
    (API keys, passwords, tokens, lark/notion/gmail/x/credential names) and with
    no path to .env or data/vault.key handed to it; credential files are never
    copied, imported or logged.
  * a regression gate (the project's offline unittest battery + a candidate import
    smoke test) must pass before promotion; on any failure the staging venv is
    discarded, leaving the live pin unchanged (rollback by isolation).
  * promotion is an atomic, chmod 0600 write to data/platform_locks.json with a
    .bak backup for manual rollback. The live .cad-venv is never silently
    replaced; promotion records the new pin and leaves the staged venv available
    for an explicit `promote --activate` admin action.

Auto-upgrade of the running service is opt-in via the AUTO_UPGRADE=1 env flag; it
is off by default so "no package or source is silently replaced."
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from runtime_env import ROOT

LOCKS = ROOT / "data" / "platform_locks.json"
STAGING = ROOT / "data" / "promotions"
REGRESSION = [sys.executable, "-m", "unittest", "discover", "-q"]

# Platforms whose pinned local dependency can be promoted from an official release.
# Anything else (hosted provider_signin services, self-hostable source apps,
# research references, archived/null) is treated as manual_review and is never
# installed by this module, matching "Installing every listed platform has not
# been done."
PIP_PACKAGES = {"cadquery": "cadquery"}

# Env vars a staged subprocess is allowed to inherit. Anything not in this set —
# including API keys, tokens, passwords, proxy tunables and the loopback auth token
# — is dropped so a staged pip/venv/install can never leak or be redirected by a
# credential held in the live process environment.
SAFE_ENV_BASE = (
    "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "PWD", "SHLVL",
    "_", "SHELL", "TERM", "XDG_RUNTIME_DIR", "COMMAND_CODE_RIPGREP_PATH",
    "COMMANDCODE_SCRATCHPAD", "SUPERCRAFTOS_AUTO_UPGRADE",
)

# Env var name tokens that signal a secret if present alongside a live value.
SECRET_TOKENS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "PROXY")


def _is_secret(name: str) -> bool:
    uppercased = name.upper()
    if uppercased in ("SUPERCRAFTOS_TOKEN", "SUPERCRAFTOS_DEBUG"):
        return True
    return any(token in uppercased for token in SECRET_TOKENS)


def safe_env() -> dict[str, str]:
    """Return a minimal, secret-free environment for staged subprocesses.

    Uses a whitelist so no API key, password, proxy or the loopback auth token can
    ever reach a venv/pip/regression subprocess. The live os.environ is never mutated.
    """
    env = {"SUPERCRAFTOS_AUTO_UPGRADE": "1"}
    for key in SAFE_ENV_BASE:
        if key in os.environ:
            env[key] = os.environ[key]
    env.setdefault("HOME", os.path.expanduser("~"))
    env.setdefault("PATH", os.defpath)
    return env


def _strip_v(version: str) -> tuple[int, ...]:
    cleaned = (version or "").lstrip("vV").replace("-", ".").split(".")
    parts = []
    for piece in cleaned:
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def version_gt(a: str, b: str) -> bool:
    return _strip_v(a) > _strip_v(b)


class Promoter:
    """Stage, test and promote official releases for registered platforms."""

    def __init__(self, locks_path: Path | None = None, staging_root: Path | None = None,
                 live_venv_python: str | Path | None = None):
        self.locks_path = locks_path or LOCKS
        self.staging_root = Path(staging_root or STAGING)
        self.live_py = str(live_venv_python or (ROOT / ".venv" / "bin" / "python"))
        # Credential artefacts are never exposed to staged installs.
        self.forbidden_paths: tuple[str, ...] = (".env", "vault.key")

    # ---- locks persistence (atomic, 0600) ----

    def _read_locks(self) -> dict[str, Any]:
        try:
            return json.loads(self.locks_path.read_text())
        except (OSError, ValueError):
            return {}

    def _write_locks(self, locks: dict[str, Any]) -> None:
        self.locks_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(locks, indent=2, sort_keys=True)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        backup = self.locks_path.with_suffix(self.locks_path.suffix + ".bak")
        if self.locks_path.exists():
            shutil.copy2(self.locks_path, backup)
        tmp = self.locks_path.with_name(self.locks_path.name + "." + digest[:8] + ".tmp")
        tmp.write_text(payload)
        tmp.chmod(0o600)
        os.replace(tmp, self.locks_path)

    # ---- staging ----

    def _stage_dir(self, platform_id: str, version: str) -> Path:
        return self.staging_root / platform_id / version

    async def _create_venv(self, path: Path) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            shutil.rmtree(path)
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "venv", str(path),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=safe_env(),
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"venv creation failed: {out.decode(errors='replace').strip()}")
        return str(path / "bin" / "python")

    async def _install(self, python: str, package: str, version: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            python, "-m", "pip", "install", "--no-input", f"{package}=={version}",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=safe_env(),
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(f"staged install failed: {out.decode(errors='replace').strip()}")
        return out.decode(errors="replace")

    async def _run_regression(self, staging_py: str, candidate: dict[str, Any]) -> bool:
        # 1) candidate import smoke test (proves the staged package boots).
        smoke = await asyncio.create_subprocess_exec(
            staging_py, "-c", f"import {candidate['import']}; "
            f"v=getattr(__import__(candidate['import']),'__version__',''); "
            f"assert v == '{candidate['version']}' or not v, v",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=safe_env(),
        )
        await asyncio.wait_for(smoke.communicate(), timeout=120)
        if smoke.returncode != 0:
            return False
        # 2) project offline regression battery against the live environment.
        proc = await asyncio.create_subprocess_exec(
            *REGRESSION, cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=safe_env(),
        )
        await asyncio.wait_for(proc.communicate(), timeout=600)
        return proc.returncode == 0

    # ---- discovery / candidate selection ----

    def _candidates(self, catalog_entry: dict[str, Any], pinned: str | None) -> dict[str, Any] | None:
        release = catalog_entry.get("release") or {}
        if release.get("status") != "checked":
            return None
        latest = release.get("latest_version")
        if not latest:
            return None
        if pinned == latest:
            return None
        if pinned and not version_gt(latest, pinned):
            return None
        package = PIP_PACKAGES.get(catalog_entry["id"])
        if not package:
            return None
        return {"id": catalog_entry["id"], "package": package,
                "import": catalog_entry["id"], "version": latest,
                "pinned": pinned, "latest": latest}

    def classify(self) -> dict[str, list[str]]:
        """Return a classification for every catalog entry (for --dry-run reporting)."""
        import platform_registry as pr
        catalog = pr.catalog()
        locks = self._read_locks()
        promote: list[str] = []
        manual: list[str] = []
        current: list[str] = []
        for row in catalog["platforms"]:
            if row["id"] not in PIP_PACKAGES:
                manual.append(row["id"])
                continue
            cand = self._candidates(row, locks.get(row["id"], {}).get("installed_version"))
            (promote if cand else current).append(row["id"])
        return {"promote": promote, "manual_review": manual, "current": current}

    # ---- orchestration ----

    async def _promote_one(self, candidate: dict[str, Any], dry_run: bool) -> dict[str, Any]:
        cid = candidate["id"]
        stage_dir = self._stage_dir(cid, candidate["version"])
        report: dict[str, Any] = {
            "platform": cid, "package": candidate["package"],
            "version": candidate["version"], "previous_pin": candidate["pinned"],
            "staged_env": str(stage_dir), "action": "promote",
        }
        if dry_run:
            report["action"] = "dry_run"; return report
        try:
            staging_py = await self._create_venv(stage_dir)
            report["install_log"] = await self._install(staging_py, candidate["package"], candidate["version"])
            if not await self._run_regression(staging_py, candidate):
                report["action"] = "rollback"; report["reason"] = "regression_failed"
                shutil.rmtree(stage_dir, ignore_errors=True)
                return report
            locks = self._read_locks()
            locks[cid] = {
                "installed_version": candidate["version"],
                "staged_env": str(stage_dir),
                "promoted_at": __import__("time").time(),
                "evidence": "data/platform-releases.json",
            }
            self._write_locks(locks)
            report["action"] = "promoted"
            report["lock_hash"] = hashlib.sha256(
                self.locks_path.read_text().encode()).hexdigest()
        except Exception as exc:  # rollback by isolation: never write the pin on error
            report["action"] = "rollback"; report["reason"] = type(exc).__name__
            shutil.rmtree(stage_dir, ignore_errors=True)
        return report

    async def run_once(self, only: str | None = None, all_: bool = False,
                       dry_run: bool = False, refresh: bool = True) -> dict[str, Any]:
        import platform_registry as pr
        if refresh:
            await pr.refresh()
        catalog = pr.catalog()
        locks = self._read_locks()
        reports: list[dict[str, Any]] = []
        for row in catalog["platforms"]:
            if only and row["id"] != only:
                continue
            if not (all_ or only):
                continue
            if row["id"] not in PIP_PACKAGES:
                reports.append({"platform": row["id"], "action": "manual_review",
                                "reason": "hosted_or_self_hosted_source_not_auto_installable"})
                continue
            cand = self._candidates(row, locks.get(row["id"], {}).get("installed_version"))
            if not cand:
                reports.append({"platform": row["id"], "action": "current"})
                continue
            reports.append(await self._promote_one(cand, dry_run=dry_run))
        return {"checked_at": catalog.get("checked_at"), "results": reports}


async def sync_capabilities(*, explicit: bool = False, dry_run: bool = False, llm: bool = True) -> dict[str, Any]:
    """Refresh live integration capabilities using restored provider credentials.

    Reuses service_health.ServiceHealth, whose probe()/benchmark() read env via
    load_environment() -- which itself decrypts vault-stored credentials on startup,
    so the operator's already-retrieved keys repopulate the live env and are exercised
    here. This is the keep-current half of the upgrade system: daily release discovery
    (platform_registry) + restored credentials + capability re-verification.

    The daily auto_upgrade_loop runs this gated behind SYNC_CAPABILITIES=1 (off by
    default) because LLM benchmarks spend credits. An explicit `main.py capabilities`
    invocation is itself an opt-in, so `explicit=True` bypasses the env gate; pass
    --no-llm to skip benchmarks. It never registers new accounts or creates
    credentials -- registration stays the consent-gated job of autonomous_registration.
    """
    if not explicit and os.getenv("SYNC_CAPABILITIES") != "1":
        return {"action": "skipped", "reason": "SYNC_CAPABILITIES not set"}
    if dry_run:
        return {"action": "dry_run"}
    import time
    from notion_db_setup import private_json
    from service_health import ServiceHealth
    results = await ServiceHealth().run(llm=llm)
    summary = {name: {"status": value.get("status"), "latency_ms": value.get("latency_ms")}
               for name, value in results.items() if isinstance(value, dict)}
    private_json(STAGING.parent / "capabilities_summary.json", summary)
    active = [name for name, value in summary.items()
              if value.get("status") in ("active", "authenticated", "catalog_reachable")]
    return {"action": "refreshed", "capabilities": len(summary),
            "active": active, "fastest_llm_ms": results.get("fastest_llm", {}).get("latency_ms")}


async def auto_upgrade_loop(stop: asyncio.Event) -> None:
    """Daily self-upgrade plus capability re-verification. Off by default; enable
    promotion with AUTO_UPGRADE=1 and capability refresh with SYNC_CAPABILITIES=1.
    Reuses platform_registry's release cache (refreshed by watch_releases) and only
    promotes fully-isolated, regression-gated candidates; capability refresh only
    re-verifies services whose credentials the operator already retrieved/authorized.
    """
    if os.getenv("AUTO_UPGRADE") != "1" and os.getenv("SYNC_CAPABILITIES") != "1":
        return
    promoter = Promoter()
    while not stop.is_set():
        try:
            if os.getenv("AUTO_UPGRADE") == "1":
                await promoter.run_once(all_=True, refresh=False)
            if os.getenv("SYNC_CAPABILITIES") == "1":
                await sync_capabilities()
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=86400)
        except asyncio.TimeoutError:
            pass


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", default=None)
    parser.add_argument("--all", dest="all_", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true", default=True)
    args = parser.parse_args()
    if not (args.all_ or args.platform):
        parser.error("specify --platform <name> or --all")
    print(json.dumps(asyncio.run(Promoter().run_once(
        only=args.platform, all_=args.all_, dry_run=args.dry_run, refresh=args.refresh)),
        indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
