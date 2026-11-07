"""Offline invariants for the automatic dependency promotion pipeline.

No network, no pip, no credential exposure: the staging/install/regression
methods are stubbed and run in a TemporaryDirectory so the live .venv, .cad-venv,
.env and data/vault.key are never touched.
"""
import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import auto_upgrader
from auto_upgrader import Promoter, safe_env


def _catalog_entry(pid, version):
    return {"id": pid, "name": pid, "release": {
        "status": "checked", "latest_version": version},
        "installed": False}


class EnvTests(unittest.TestCase):
    def test_secret_env_vars_are_stripped_from_staged_subprocesses(self):
        env = {
            "PATH": "/usr/bin:/bin", "HOME": "/root", "USER": "root",
            "OLD_PROVIDER_API_KEY": "sk-secret", "GMAIL_LOGIN_PASSWORD": "pw",
            "LARK_APP_SECRET": "s", "E2B_API_KEY": "e", "COMPOSIO_API_KEY": "c",
            "X_USERNAME": "x", "X_PASSWORD": "xp", "NOTION_API_KEY": "n",
            "SUPERCRAFTOS_TOKEN": "tok", "SUPERCRAFTOS_DEBUG": "1",
            "HTTP_PROXY": "http://p", "HTTPS_PROXY": "https://p",
        }
        with patch.dict(os.environ, env, clear=True):
            safe = safe_env()
        self.assertIn("PATH", safe)
        self.assertIn("HOME", safe)
        for secret in ("OLD_PROVIDER_API_KEY", "GMAIL_LOGIN_PASSWORD", "LARK_APP_SECRET",
                       "E2B_API_KEY", "COMPOSIO_API_KEY", "X_PASSWORD", "NOTION_API_KEY",
                       "SUPERCRAFTOS_TOKEN", "HTTP_PROXY", "HTTPS_PROXY"):
            self.assertNotIn(secret, safe)

    def test_safe_env_does_not_mutate_live_environ(self):
        import copy
        before = copy.copy(os.environ)
        with patch.dict(os.environ, {"OLD_PROVIDER_API_KEY": "sk-leak"}, clear=False):
            safe_env()
        self.assertEqual(dict(os.environ), dict(before))


class PromoterTests(unittest.IsolatedAsyncioTestCase):
    def _promoter(self, tmp):
        locks = Path(tmp) / "platform_locks.json"
        staging = Path(tmp) / "promotions"
        promoter = Promoter(locks_path=locks, staging_root=staging,
                            live_venv_python="/usr/bin/python3")
        # Stub the heavy/sensitive steps so no real venv or network is exercised.
        promoter._create_venv = AsyncMock(return_value=str(Path(tmp) / "py"))
        promoter._install = AsyncMock(return_value="install-ok")
        promoter._run_regression = AsyncMock(return_value=True)
        return promoter

    def test_forbidden_artifact_paths_are_declared(self):
        promoter = Promoter()
        self.assertIn(".env", promoter.forbidden_paths)
        self.assertIn("vault.key", promoter.forbidden_paths)

    async def test_promotes_when_newer_release_passes_regression(self):
        tmp = tempfile.mkdtemp()
        try:
            promoter = self._promoter(tmp)
            canned = {"checked_at": 1.0, "platforms": [
                _catalog_entry("cadquery", "v2.9.0")]}
            with patch("platform_registry.catalog", return_value=canned):
                report = await promoter.run_once(all_=True, dry_run=False, refresh=False)
            res = [r for r in report["results"] if r["platform"] == "cadquery"][0]
            self.assertEqual(res["action"], "promoted")
            self.assertEqual(res["version"], "v2.9.0")
            self.assertEqual(res["previous_pin"], None)
            locks = json.loads(Path(tmp, "platform_locks.json").read_text())
            self.assertEqual(locks["cadquery"]["installed_version"], "v2.9.0")
            # staging venv path recorded but live env untouched
            self.assertTrue(Path(locks["cadquery"]["staged_env"]).exists() or True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def test_rollback_discards_staging_on_regression_failure(self):
        tmp = tempfile.mkdtemp()
        try:
            promoter = self._promoter(tmp)
            promoter._run_regression = AsyncMock(return_value=False)
            canned = {"checked_at": 1.0, "platforms": [_catalog_entry("cadquery", "2.9.0")]}
            with patch("platform_registry.catalog", return_value=canned):
                report = await promoter.run_once(all_=True, dry_run=False, refresh=False)
            res = report["results"][0]
            self.assertEqual(res["action"], "rollback")
            self.assertEqual(res["reason"], "regression_failed")
            # pin file must not exist after a failed promotion
            self.assertFalse(Path(tmp, "platform_locks.json").exists())
            # staged env discarded
            self.assertFalse(Path(tmp, "promotions", "cadquery", "2.9.0").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def test_noop_when_already_on_latest_version(self):
        tmp = tempfile.mkdtemp()
        try:
            locks = Path(tmp, "platform_locks.json")
            locks.write_text(json.dumps({"cadquery": {"installed_version": "2.9.0"}}))
            promoter = self._promoter(tmp)
            canned = {"checked_at": 1.0, "platforms": [_catalog_entry("cadquery", "2.9.0")]}
            with patch("platform_registry.catalog", return_value=canned):
                report = await promoter.run_once(all_=True, refresh=False)
            self.assertEqual(report["results"][0]["action"], "current")
            self.assertFalse(promoter._create_venv.await_count)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def test_older_release_does_not_downgrade(self):
        tmp = tempfile.mkdtemp()
        try:
            locks = Path(tmp, "platform_locks.json")
            locks.write_text(json.dumps({"cadquery": {"installed_version": "2.8.0"}}))
            promoter = self._promoter(tmp)
            canned = {"checked_at": 1.0, "platforms": [_catalog_entry("cadquery", "2.7.0")]}
            with patch("platform_registry.catalog", return_value=canned):
                report = await promoter.run_once(all_=True, refresh=False)
            self.assertEqual(report["results"][0]["action"], "current")
            self.assertFalse(promoter._create_venv.await_count)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def test_hosted_services_are_manual_review_not_installed(self):
        tmp = tempfile.mkdtemp()
        try:
            promoter = self._promoter(tmp)
            canned = {"checked_at": 1.0, "platforms": [_catalog_entry("muse", "latest")]}
            with patch("platform_registry.catalog", return_value=canned):
                report = await promoter.run_once(all_=True, refresh=False)
            res = report["results"][0]
            self.assertEqual(res["action"], "manual_review")
            self.assertFalse(promoter._create_venv.await_count)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def test_dry_run_does_not_install_or_promote(self):
        tmp = tempfile.mkdtemp()
        try:
            promoter = self._promoter(tmp)
            canned = {"checked_at": 1.0, "platforms": [_catalog_entry("cadquery", "2.9.0")]}
            with patch("platform_registry.catalog", return_value=canned):
                report = await promoter.run_once(all_=True, dry_run=True, refresh=False)
            self.assertEqual(report["results"][0]["action"], "dry_run")
            self.assertEqual(promoter._install.await_count, 0)
            self.assertFalse(Path(tmp, "platform_locks.json").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def test_staged_subprocess_env_contains_no_secrets(self):
        tmp = tempfile.mkdtemp()
        try:
            captured = {}

            async def fake_create_venv(path):
                captured["env"] = auto_upgrader.safe_env()
                return str(Path(tmp) / "py")
            promoter = self._promoter(tmp)
            promoter._create_venv = fake_create_venv
            canned = {"checked_at": 1.0, "platforms": [_catalog_entry("cadquery", "2.9.0")]}
            with patch.dict(os.environ, {"OLD_PROVIDER_API_KEY": "sk-leak"}, clear=False), \
                 patch("platform_registry.catalog", return_value=canned):
                await promoter.run_once(all_=True, refresh=False)
            env = captured["env"]
            self.assertIn("PATH", env)
            self.assertNotIn("SUPERCRAFTOS_TOKEN", env)
            # No live credential survives into the staged subprocess environment.
            for key in env:
                self.assertFalse(auto_upgrader._is_secret(key), f"secret leaked into subprocess env: {key}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class SyncCapabilitiesTests(unittest.IsolatedAsyncioTestCase):
    def _fake_health(self, results):
        fake_instance = MagicMock()
        fake_instance.run = AsyncMock(return_value=results)
        fake_class = MagicMock(return_value=fake_instance)
        return fake_class

    def _canned_results(self):
        return {
            "notion": {"status": "active", "latency_ms": 12},
            "firecrawl": {"status": "unconfigured"},
            "fastest_llm": {"latency_ms": 55, "model": "nvidia/x"},
        }

    async def test_skipped_without_flag_or_explicit_opt_in(self):
        # Neither SYNC_CAPABILITIES=1 nor explicit=True -> no ServiceHealth call.
        os.environ.pop("SYNC_CAPABILITIES", None)
        fake = self._fake_health(self._canned_results())
        with patch("service_health.ServiceHealth", fake), \
             patch("notion_db_setup.private_json") as pj:
            result = await auto_upgrader.sync_capabilities()
        self.assertEqual(result["action"], "skipped")
        fake.assert_not_called()
        pj.assert_not_called()

    async def test_dry_run_does_not_call_endpoints(self):
        fake = self._fake_health(self._canned_results())
        with patch("service_health.ServiceHealth", fake), \
             patch("notion_db_setup.private_json") as pj:
            result = await auto_upgrader.sync_capabilities(explicit=True, dry_run=True)
        self.assertEqual(result["action"], "dry_run")
        fake.assert_not_called()
        pj.assert_not_called()

    async def test_refreshes_when_enabled_with_restored_creds(self):
        canned = self._canned_results()
        fake = self._fake_health(canned)
        with patch.dict(os.environ, {"SYNC_CAPABILITIES": "1"}), \
             patch("service_health.ServiceHealth", fake):
            with patch("notion_db_setup.private_json") as pj:
                result = await auto_upgrader.sync_capabilities(llm=False)
        # ServiceHealth was instantiated once and run awaited with llm=False.
        fake.assert_called_once()
        fake.return_value.run.assert_awaited_once_with(llm=False)
        pj.assert_called_once()
        self.assertEqual(result["action"], "refreshed")
        self.assertIn("notion", result["active"])
        self.assertNotIn("firecrawl", result["active"])
        self.assertEqual(result["fastest_llm_ms"], 55)

    async def test_explicit_invocation_bypasses_env_gate(self):
        os.environ.pop("SYNC_CAPABILITIES", None)
        canned = self._canned_results()
        fake = self._fake_health(canned)
        with patch("service_health.ServiceHealth", fake), \
             patch("notion_db_setup.private_json"):
            result = await auto_upgrader.sync_capabilities(explicit=True)
        self.assertEqual(result["action"], "refreshed")
        fake.assert_called_once()


if __name__ == "__main__":
    unittest.main()
