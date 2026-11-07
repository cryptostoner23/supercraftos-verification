#!/usr/bin/env python3
"""Receive a signed iOS bundle from the Mac build client and publish it.

The Mac build client posts the ipa it produced to this service. The service
stores it in the public release directory with a timestamped name and answers
with the public url, so the build server can publish the artifact without ever
dialling into the Mac.

    POST /upload?name=SuperCraftOS.ipa   body: the raw ipa bytes
    GET  /health                          body: {"ok": true}
"""
from __future__ import annotations

import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEST = Path(os.environ.get("IOS_UPLOAD_DIR", "/srv/ios-releases"))
MAX_BYTES = 200 * 1024 * 1024
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class Handler(BaseHTTPRequestHandler):
    server_version = "SuperCraftOSUpload/1.0"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        print(f"{self.address_string()} {fmt % args}", flush=True)

    def _reply(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/health") or self.path.startswith("/ios/health"):
            self._reply(200, {"ok": True, "dest": str(DEST)})
            return
        self._reply(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if not (self.path.startswith("/upload") or self.path.startswith("/ios/upload")):
            self._reply(404, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > MAX_BYTES:
            self._reply(400, {"error": "bad_length", "length": length})
            return
        query = self.path.partition("?")[2]
        raw = query.partition("name=")[2]
        name = SAFE_NAME.sub("-", raw or "upload.ipa")
        if not name.endswith(".ipa"):
            name += ".ipa"
        DEST.mkdir(parents=True, exist_ok=True)
        target = DEST / f"{int(time.time())}-{name}"
        remaining = length
        with target.open("wb") as handle:
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 1 << 20))
                if not chunk:
                    break
                handle.write(chunk)
                remaining -= len(chunk)
        if remaining > 0:
            target.unlink(missing_ok=True)
            self._reply(400, {"error": "truncated"})
            return
        target.chmod(0o644)
        self._reply(200, {
            "ok": True,
            "file": target.name,
            "bytes": target.stat().st_size,
            "url": f"https://agent.commetai.ca/ios/{target.name}",
        })


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("IOS_UPLOAD_PORT", "8799"))), Handler)
    server.daemon_threads = True
    print(f"listening on 127.0.0.1:{server.server_address[1]}, storing in {DEST}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
