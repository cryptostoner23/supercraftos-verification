"""Read Bitrise build status and publish deduplicated updates through Lark."""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Awaitable

import httpx

from token_optimizer import ROOT

API_ROOT = "https://api.bitrise.io/v0.1"
STATE_PATH = ROOT / "data" / "bitrise-build-states.json"
SLUG = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class BitriseMonitor:
    def __init__(self, token: str, app_slug: str, notify: Callable[[str], Awaitable[Any]],
                 state_path: Path = STATE_PATH, client: httpx.AsyncClient | None = None):
        if not token or not SLUG.fullmatch(app_slug):
            raise ValueError("Bitrise token and valid app slug are required")
        self.token = token
        self.app_slug = app_slug
        self.notify = notify
        self.state_path = state_path
        self.client = client

    async def list_builds(self) -> list[dict[str, Any]]:
        own_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=15)
        try:
            response = await client.get(
                f"{API_ROOT}/apps/{self.app_slug}/builds",
                headers={"Authorization": self.token, "Accept": "application/json"},
                params={"limit": 20},
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("data")
            if not isinstance(rows, list):
                raise ValueError("Bitrise build response has no data list")
            return [row for row in rows if isinstance(row, dict)]
        finally:
            if own_client:
                await client.aclose()

    async def poll_once(self) -> int:
        builds = await self.list_builds()
        try:
            seen = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        except (OSError, json.JSONDecodeError):
            seen = {}
        if not isinstance(seen, dict):
            seen = {}
        sent = 0
        for build in reversed(builds):
            slug, status = build.get("slug"), build.get("status_text")
            if not isinstance(slug, str) or not SLUG.fullmatch(slug) or not isinstance(status, str):
                continue
            if seen.get(slug) == status:
                continue
            number = build.get("build_number")
            workflow = str(build.get("triggered_workflow") or "workflow")[:80]
            label = f"#{number}" if isinstance(number, int) else slug[:12]
            await self.notify(f"Bitrise {workflow} build {label}: {status}. Build slug: {slug}")
            seen[slug] = status
            sent += 1
        if sent:
            self.state_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = self.state_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(dict(list(seen.items())[-200:]), separators=(",", ":")))
            temporary.chmod(0o600)
            temporary.replace(self.state_path)
        return sent

    async def run(self, stop: asyncio.Event, interval: float = 120.0,
                  report: Callable[[str], Any] | None = None) -> None:
        while not stop.is_set():
            try:
                await self.poll_once()
            except (httpx.HTTPError, ValueError, OSError) as exc:
                if report:
                    report(f"Bitrise polling failed: {type(exc).__name__}")
            try:
                await asyncio.wait_for(stop.wait(), timeout=max(30.0, interval))
            except asyncio.TimeoutError:
                pass


def configured() -> bool:
    return all(bool(os.getenv(key)) for key in (
        "BITRISE_API_TOKEN", "BITRISE_APP_SLUG", "LARK_NOTIFY_CHAT_ID", "LARK_APP_ID", "LARK_APP_SECRET"
    ))
