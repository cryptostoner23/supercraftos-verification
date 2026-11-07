#!/usr/bin/env python3
"""Fetch a Bitrise build log and print the interesting lines."""
import os
import re
import sys

import httpx

TOKEN = os.environ.get("BITRISE_API_TOKEN")
APP = os.environ.get("BITRISE_APP_SLUG", "0150bf6e-006f-4263-b1ce-680875b745b4")
HEADERS = {"Authorization": TOKEN, "Accept": "application/json"}


def build(number=None):
    listing = httpx.get(f"https://api.bitrise.io/v0.1/apps/{APP}/builds", headers=HEADERS,
                        params={"limit": 20}, timeout=30).json()["data"]
    if number:
        for entry in listing:
            if entry["build_number"] == int(number):
                return entry
        raise SystemExit(f"build {number} is not in the last 20")
    return listing[0]


def log_text(slug):
    base = f"https://api.bitrise.io/v0.1/apps/{APP}/builds/{slug}/log"
    chunks = []
    params = {}
    for _ in range(40):
        response = httpx.get(base, headers={"Authorization": TOKEN}, params=params,
                             timeout=90, follow_redirects=True)
        try:
            payload = response.json()
        except ValueError:
            chunks.append(response.text)
            break
        for item in payload.get("log_chunks", []):
            chunks.append(item.get("chunk", ""))
        marker = payload.get("next_after_timestamp")
        if not marker or marker == params.get("next_after_timestamp"):
            break
        params = {"next_after_timestamp": marker}
    return "".join(chunks)


def main():
    number = sys.argv[1] if len(sys.argv) > 1 else None
    entry = build(number)
    print(f"build #{entry['build_number']} {entry['status_text']}")
    text = log_text(entry["slug"])
    pattern = re.compile(r"(==>|error:|warning: .*(deprecat|unused)|Test Case|Executed|BUILD (SUCCEEDED|FAILED)|failed|FAILED|XCTAssert)", re.I)
    for line in text.splitlines():
        if pattern.search(line):
            print("  ", line.strip()[-190:])


if __name__ == "__main__":
    main()
