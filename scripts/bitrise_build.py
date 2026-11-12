#!/usr/bin/env python3
"""Trigger a Bitrise build, poll it to a terminal state, and report the result.

Usage:
    python3 scripts/bitrise_build.py trigger [--workflow run_tests] [--branch master]
    python3 scripts/bitrise_build.py status <build-slug>
    python3 scripts/bitrise_build.py log <build-slug> [--grep PATTERN]
    python3 scripts/bitrise_build.py artifacts <build-slug> [--download DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

API = "https://api.bitrise.io/v0.1"
ROOT = Path(__file__).resolve().parents[1]
ANSI = re.compile(r"\x1b\[[0-9;]*m")
TERMINAL = {"success", "error", "warning", "aborted", "skipped"}
TIMEOUT_SECONDS = 3600


def credentials() -> tuple[str, str]:
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        if key.strip() == "BITRISE_API_TOKEN":
            os.environ.setdefault("BITRISE_API_TOKEN", value)
        if key.strip() == "BITRISE_APP_SLUG":
            os.environ.setdefault("BITRISE_APP_SLUG", value)
    token = os.environ.get("BITRISE_API_TOKEN", "")
    slug = os.environ.get("BITRISE_APP_SLUG", "")
    if not token or not slug:
        raise SystemExit("BITRISE_API_TOKEN and BITRISE_APP_SLUG are required")
    return token, slug


def client() -> httpx.Client:
    token, _ = credentials()
    return httpx.Client(base_url=API, headers={"Authorization": token, "Accept": "application/json"}, timeout=60)


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text)


def fetch_log(app: str, build: str) -> str:
    """The build's whole log.

    The chunked endpoint only returns a slice of a large build and its
    pagination marker does not advance, so the commit the build actually
    checked out cannot be read from it. Bitrise publishes the complete log
    at `expiring_raw_log_url`; that is what is read, and the chunked
    endpoint is only the fallback for a build with no archive.
    """
    with client() as http:
        response = http.get(f"/apps/{app}/builds/{build}/log")
        response.raise_for_status()
        payload = response.json()
    raw = payload.get("expiring_raw_log_url")
    if isinstance(raw, str) and raw.startswith("https://"):
        # The archive is on a separate storage host. Never send the Bitrise
        # API Authorization header there.
        try:
            archived = httpx.get(raw, follow_redirects=True, timeout=120)
            archived.raise_for_status()
            text = archived.text
        except httpx.HTTPError:
            text = ""
        if text:
            return strip_ansi(text)
    chunks = payload.get("log_chunks", [])
    return strip_ansi("".join(chunk.get("chunk", "") for chunk in chunks if isinstance(chunk, dict)))


def trigger(workflow: str, branch: str) -> dict:
    _, app = credentials()
    with client() as http:
        response = http.post(
            f"/apps/{app}/builds",
            json={
                "hook_info": {"type": "bitrise"},
                "build_params": {"branch": branch, "workflow_id": workflow},
            },
        )
        response.raise_for_status()
        payload = response.json()
    build = payload.get("data", payload)
    return {
        "build_slug": build.get("build_slug") or build.get("slug"),
        "build_number": build.get("build_number"),
        "status": build.get("status_text"),
        "workflow": workflow,
        "branch": branch,
    }


def cloned_commit(log: str) -> str | None:
    """Read git-clone's actual checkout identity, never an arbitrary log hash."""
    hashes = set(re.findall(
        r"(?m)^=> GIT_CLONE_COMMIT_HASH\r?\n[ \t]+value: ([0-9a-f]{40})[ \t]*$",
        strip_ansi(log),
    ))
    return next(iter(hashes)) if len(hashes) == 1 else None


def status(app: str, build: str) -> dict:
    with client() as http:
        response = http.get(f"/apps/{app}/builds/{build}")
        response.raise_for_status()
        payload = response.json()
    data = payload.get("data", payload)
    commit = data.get("commit_hash")
    commit_source = "build_api" if commit else None
    # Branch-triggered builds can leave commit_hash null even after success.
    # The git-clone step records the actual checked-out revision in its log.
    if not commit and data.get("status_text") in TERMINAL:
        commit = cloned_commit(fetch_log(app, build))
        commit_source = "git_clone_log" if commit else None
    return {
        "build_slug": data.get("slug"),
        "build_number": data.get("build_number"),
        "status": data.get("status_text"),
        "workflow": data.get("triggered_workflow"),
        "branch": data.get("branch"),
        "commit": commit,
        "commit_source": commit_source,
        "build_url": data.get("build_url"),
    }


def wait(app: str, build: str, timeout: int = TIMEOUT_SECONDS) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        current = status(app, build)
        if current["status"] != last:
            print(f"[{time.strftime('%H:%M:%S')}] build {current.get('build_number')} -> {current['status']}", flush=True)
            last = current["status"]
        if current["status"] in TERMINAL:
            return current
        time.sleep(15)
    raise SystemExit("timed out waiting for the build")


def artifacts(app: str, build: str, download: str | None) -> list[dict]:
    result = []
    with client() as http:
        response = http.get(f"/apps/{app}/builds/{build}/artifacts")
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", payload)
        if not isinstance(rows, list):
            rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            entry = {
                "title": row.get("title"),
                "slug": row.get("slug"),
                "artifact_type": row.get("artifact_type"),
                "is_public_page_enabled": row.get("is_public_page_enabled"),
            }
            if download:
                target = Path(download)
                target.mkdir(parents=True, exist_ok=True)
                name = re.sub(r"[^A-Za-z0-9._-]+", "-", str(row.get("title") or row.get("slug") or "artifact"))
                detail = http.get(f"/apps/{app}/builds/{build}/artifacts/{row.get('slug')}")
                detail.raise_for_status()
                body = detail.json()
                url = body.get("data", body).get("expiring_download_url")
                if url:
                    # Storage URLs are signed by Bitrise. Never send the API
                    # Authorization header to a separate artifact storage host.
                    if not str(url).startswith("https://"):
                        raise ValueError("Artifact download must use HTTPS")
                    binary = httpx.get(url, follow_redirects=True, timeout=120)
                    binary.raise_for_status()
                    path = target / name
                    path.write_bytes(binary.content)
                    entry["downloaded_to"] = str(path)
                    entry["bytes"] = len(binary.content)
            result.append(entry)
    return result


def resolve_build(app: str, build: str) -> str:
    """Resolve a build slug, or the slug of the most recent successful build."""
    if build != "latest":
        return build
    with client() as http:
        response = http.get(f"/apps/{app}/builds", params={"limit": 20})
        response.raise_for_status()
        rows = response.json().get("data", [])
    for row in rows:
        if isinstance(row, dict) and row.get("status_text") == "success" and row.get("slug"):
            return str(row["slug"])
    raise SystemExit("no successful build found")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    trigger_parser = sub.add_parser("trigger")
    trigger_parser.add_argument("--workflow", default="run_tests")
    trigger_parser.add_argument("--branch", default="master")
    trigger_parser.add_argument("--wait", action="store_true")
    status_parser = sub.add_parser("status")
    status_parser.add_argument("build")
    log_parser = sub.add_parser("log")
    log_parser.add_argument("build")
    log_parser.add_argument("--grep", default=None)
    log_parser.add_argument("--tail", type=int, default=0)
    artifact_parser = sub.add_parser("artifacts")
    artifact_parser.add_argument("build")
    artifact_parser.add_argument("--download", default=None)
    args = parser.parse_args()

    _, app = credentials()
    if args.command in {"status", "log", "artifacts"}:
        args.build = resolve_build(app, args.build)
    if args.command == "trigger":
        result = trigger(args.workflow, args.branch)
        if args.wait:
            result.update(wait(app, result["build_slug"]))
        print(json.dumps(result, indent=2))
    elif args.command == "status":
        print(json.dumps(status(app, args.build), indent=2))
    elif args.command == "log":
        text = fetch_log(app, args.build)
        if args.grep:
            pattern = re.compile(args.grep, re.IGNORECASE)
            lines = [line for line in text.splitlines() if pattern.search(line)]
            print("\n".join(lines))
        elif args.tail:
            print("\n".join(text.splitlines()[-args.tail:]))
        else:
            print(text)
    elif args.command == "artifacts":
        print(json.dumps(artifacts(app, args.build, args.download), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
