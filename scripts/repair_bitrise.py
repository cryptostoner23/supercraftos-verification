"""Activate the repository CI config for the connected Bitrise app and run it."""
from __future__ import annotations

import getpass
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import set_key

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.bitrise.io/v0.1"
REPOSITORY = "cryptostoner94/supercraftos"


def main() -> int:
    token = os.getenv("BITRISE_API_TOKEN") or getpass.getpass("Bitrise API token: ")
    if not token:
        raise RuntimeError("Bitrise API token is required")
    headers = {"Authorization": token, "Accept": "application/json"}
    with httpx.Client(base_url=API, headers=headers, timeout=20) as client:
        response = client.get("/apps")
        response.raise_for_status()
        apps = response.json().get("data", [])
        candidates = [app for app in apps if isinstance(app, dict) and
                      REPOSITORY in str(app.get("repo_url", "")).lower().replace(".git", "")]
        if len(candidates) != 1:
            print(json.dumps({"status": "app_lookup_failed", "matches": len(candidates),
                              "visible_apps": [{"title": app.get("title"), "slug": app.get("slug")} for app in apps if isinstance(app, dict)]}, indent=2))
            return 2
        app = candidates[0]
        slug = str(app["slug"])
        config_response = client.get(f"/apps/{slug}/bitrise.yml/config")
        config_response.raise_for_status()
        config = config_response.json()
        location = config.get("data", config).get("location")
        if location != "repository":
            change = client.put(f"/apps/{slug}/bitrise.yml/config",
                                json={"location": "repository"},
                                headers={**headers, "Content-Type": "application/json"})
            change.raise_for_status()
            location = "repository"
        env_path = ROOT / ".env"
        env_path.touch(mode=0o600, exist_ok=True)
        set_key(str(env_path), "BITRISE_API_TOKEN", token)
        set_key(str(env_path), "BITRISE_APP_SLUG", slug)
        env_path.chmod(0o600)
        trigger = client.post(f"/apps/{slug}/builds", json={
            "hook_info": {"type": "bitrise"},
            "build_params": {"branch": "master", "workflow_id": "run_tests"},
        }, headers={**headers, "Content-Type": "application/json"})
        trigger.raise_for_status()
        payload = trigger.json()
        build = payload.get("data", payload)
        print(json.dumps({"status": "triggered", "app_slug": slug,
                          "config_location": location,
                          "build_slug": build.get("build_slug") or build.get("slug"),
                          "build_number": build.get("build_number"),
                          "build_url": build.get("build_url")}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPStatusError as exc:
        print(json.dumps({"status": "bitrise_api_error", "http_status": exc.response.status_code,
                          "endpoint": exc.request.url.path,
                          "detail": exc.response.text[:350].replace(token if (token := exc.request.headers.get("Authorization", "")) else "\0", "[redacted]")}), file=sys.stderr)
        raise SystemExit(1)
