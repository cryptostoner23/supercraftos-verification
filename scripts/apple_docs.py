#!/usr/bin/env python3
"""Ingest Apple's official developer documentation into this repository.

The source of truth is Apple. Every page is fetched from Apple's own
documentation service, kept with the exact URL it came from, the date it was
fetched, and the hash of the bytes, so any statement in this repository can
be traced back to the page it came from. Nothing here is paraphrased from
memory.

    scripts/apple_docs.py fetch swiftui/view/table uikit/uiinputviewcontroller
    scripts/apple_docs.py ingest docs/apple-manifest.txt
    scripts/apple_docs.py show uikit/uiinputviewcontroller
    scripts/apple_docs.py grep "RequestsOpenAccess"

The service is the same one Apple's own documentation clients use:
    https://developer.apple.com/tutorials/data/documentation/<path>.json
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/apple"
RAW = ROOT / "data/apple-docs/raw"
MANIFEST = ROOT / "docs/apple-manifest.json"
BASE = "https://developer.apple.com"
JSON_API = BASE + "/tutorials/data/documentation/{path}.json"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"


def slug(path: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")


def fetch(path: str) -> tuple[bytes, str]:
    url = JSON_API.format(path=path)
    response = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                         timeout=60, follow_redirects=True)
    if response.status_code != 200:
        raise RuntimeError(f"{url} -> HTTP {response.status_code}")
    return response.content, url


def render(node, out: list[str], depth: int = 0) -> None:
    """Turn Apple's documentation JSON into plain text."""
    if isinstance(node, dict):
        kind = node.get("type")
        if kind == "text":
            out.append(node.get("text", ""))
            return
        if kind == "codeVoice":
            out.append(node.get("code", ""))
            return
        if kind == "reference":
            out.append(node.get("identifier", node.get("url", "")))
            return
        if kind == "emphasis":
            render(node.get("inlineContent", []), out, depth)
            return
        if kind == "strong":
            render(node.get("inlineContent", []), out, depth)
            return
        if kind in ("paragraph", "heading"):
            if node.get("text"):
                out.append(node["text"])
            render(node.get("inlineContent", []), out, depth)
            out.append("\n\n" if kind == "paragraph" else "\n")
            return
        if kind == "listItem":
            out.append("- ")
            render(node.get("content", []), out, depth)
            return
        if kind in ("unorderedList", "orderedList"):
            render(node.get("items", []), out, depth)
            out.append("\n")
            return
        if kind == "codeListing":
            out.append("\n```\n")
            out.append("\n".join(node.get("code", [])))
            out.append("\n```\n")
            return
        if kind == "aside":
            out.append("\n[")
            render(node.get("content", []), out, depth)
            out.append("]\n")
            return
        if kind == "table":
            for row in node.get("rows", []):
                cells = []
                for cell in row:
                    cells.append("".join(render_to_text(cell.get("content", []))))
                out.append(" | ".join(cells) + "\n")
            return
        for value in node.values():
            render(value, out, depth)
        return
    if isinstance(node, list):
        for item in node:
            render(item, out, depth)
        return
    if isinstance(node, str):
        out.append(node)


def render_to_text(node) -> list[str]:
    out: list[str] = []
    render(node, out)
    return out


def ingest(path: str) -> dict:
    raw, url = fetch(path)
    digest = hashlib.sha256(raw).hexdigest()
    document = json.loads(raw)
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{slug(path)}.json").write_bytes(raw)

    out: list[str] = []
    render(document.get("primaryContentSections", []), out)
    for section in document.get("topicSections", []) or []:
        out.append("\n## " + section.get("title", "") + "\n")
        for identifier in section.get("identifiers", []):
            out.append(f"- {identifier}\n")

    body = "".join(out)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    title = (document.get("metadata", {}).get("title")
             or document.get("abstract", [{}])[0].get("text", path))

    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"{slug(path)}.md"
    header = (
        f"<!-- Apple official documentation. Source of truth. -->\n"
        f"<!-- url: {url} -->\n"
        f"<!-- fetched: {datetime.now(timezone.utc).isoformat(timespec='seconds')} -->\n"
        f"<!-- sha256: {digest} -->\n"
        f"<!-- title: {title} -->\n\n"
        f"# {title}\n\n"
        f"Official page: <{BASE}/documentation/{path}>\n\n"
    )
    target.write_text(header + body + "\n")

    entry = {"path": path, "url": url, "title": title, "sha256": digest,
             "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "file": str(target.relative_to(ROOT))}
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []
    manifest = [item for item in manifest if item["path"] != path]
    manifest.append(entry)
    manifest.sort(key=lambda item: item["path"])
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    return entry


def ingest_html(url: str, name: str | None = None) -> dict:
    """Ingest a guide page. The technical notes and the archived guides are
    not in the documentation service, so they are fetched from Apple and
    stored with the same provenance."""
    response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True)
    if response.status_code != 200:
        raise RuntimeError(f"{url} -> HTTP {response.status_code}")
    raw = response.content
    digest = hashlib.sha256(raw).hexdigest()
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw.decode("utf-8", "replace"))
    text = re.sub(r"(?s)<!--.*?-->", " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h[1-6]>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    key = name or slug(re.sub(r"^https?://", "", url).rstrip("/").replace("/", "-")) or "page"
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{slug(key)}.html").write_bytes(raw)
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"{slug(key)}.md"
    header = (
        f"<!-- Apple official documentation. Source of truth. -->\n"
        f"<!-- url: {url} -->\n"
        f"<!-- fetched: {datetime.now(timezone.utc).isoformat(timespec='seconds')} -->\n"
        f"<!-- sha256: {digest} -->\n\n"
    )
    target.write_text(header + text + "\n")
    entry = {"path": key, "url": url, "title": key, "sha256": digest,
             "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "file": str(target.relative_to(ROOT))}
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []
    manifest = [item for item in manifest if item["path"] != key]
    manifest.append(entry)
    manifest.sort(key=lambda item: item["path"])
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    return entry


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    command = sys.argv[1]

    if command == "fetch":
        for path in sys.argv[2:]:
            try:
                entry = ingest(path)
                print(f"  {entry['path']:<60} {entry['sha256'][:12]}  {entry['file']}")
            except Exception as error:  # noqa: BLE001
                print(f"  {path:<60} FAILED {error}")
        return 0

    if command == "ingest":
        for line in Path(sys.argv[2]).read_text().splitlines():
            path = line.strip()
            if not path or path.startswith("#"):
                continue
            try:
                entry = ingest(path)
                print(f"  {entry['path']:<60} {entry['sha256'][:12]}")
            except Exception as error:  # noqa: BLE001
                print(f"  {path:<60} FAILED {error}")
            time.sleep(0.3)
        return 0

    if command == "fetch-html":
        for url in sys.argv[2:]:
            try:
                entry = ingest_html(url)
                print(f"  {entry['url']:<70} {entry['sha256'][:12]}")
            except Exception as error:  # noqa: BLE001
                print(f"  {url:<70} FAILED {error}")
        return 0

    if command == "show":
        manifest = json.loads(MANIFEST.read_text())
        for entry in manifest:
            if entry["path"] == sys.argv[2]:
                print((ROOT / entry["file"]).read_text())
                return 0
        print("not in the manifest", file=sys.stderr)
        return 1

    if command == "grep":
        pattern = re.compile(sys.argv[2], re.I)
        manifest = json.loads(MANIFEST.read_text())
        for entry in manifest:
            for number, line in enumerate((ROOT / entry["file"]).read_text().splitlines(), 1):
                if pattern.search(line):
                    print(f"{entry['file']}:{number}: {line.strip()[:200]}")
        return 0

    if command == "list":
        manifest = json.loads(MANIFEST.read_text())
        for entry in manifest:
            print(f"  {entry['path']:<62} {entry['fetched']}  {entry['sha256'][:12]}")
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
