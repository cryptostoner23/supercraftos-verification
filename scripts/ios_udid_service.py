#!/usr/bin/env python3
"""Receive iOS device UDIDs from a configuration profile and show them back.

The device installs the configuration profile that scripts/udid_capture.py
writes.  The profile carries Apple's documented "Profile Service" payload, so
the moment the profile is installed the device POSTs a PKCS#7 signed plist
with its UDID to the URL in the payload.  This service stores what it receives
in data/ios-devices.json and serves the page the device lands on.

    GET  /udid                     the capture page
    GET  /udid?udid=...&name=...   record a UDID, then show the capture page
    POST /udid                     the Profile Service callback from the device
    GET  /udid.mobileconfig        withdrawn, answers with an explanation
    GET  /health

The same routes answer with or without the /ios prefix, the way the sibling
upload service does, so the Caddy route can proxy the path unchanged.
"""
from __future__ import annotations

import html
import json
import os
import plistlib
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import udid_capture  # noqa: E402

STORE = Path(os.environ.get("IOS_UDID_STORE", "/root/SuperCraftOS/data/ios-devices.json"))
BASE_URL = os.environ.get("IOS_UDID_BASE_URL", "https://agent.commetai.ca").rstrip("/")
PORT = int(os.environ.get("IOS_UDID_PORT", "8798"))

# The legacy 40 character UDID, and the 25 character form Apple uses since 2018
# on A12 and later ("00008110-001965E62213801E").
UDID_PATTERN = re.compile(r"\b([0-9a-fA-F]{40}|[0-9a-fA-F]{8}-[0-9a-fA-F]{16})\b")
UDID_KEYS = ("UDID", "DEVICEUDID", "UNIQUEIDENTIFIER", "UNIQUEIDENTIFIERFORVENDOR")
LOCK = threading.Lock()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_udid(value: str) -> str:
    """The UDID inside a string, as the device reported it.

    The case is kept, because the 2018 style UDID is shown in upper case by
    the Apple developer portal, and a device is matched on the case folded
    value.
    """
    match = UDID_PATTERN.search(value or "")
    return match.group(1) if match else ""


def same_udid(left: str, right: str) -> bool:
    return (left or "").lower() == (right or "").lower()


def load_store() -> dict:
    try:
        raw = STORE.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return {"devices": []}
    try:
        data = json.loads(raw)
    except ValueError:
        return {"devices": []}
    if not isinstance(data, dict) or not isinstance(data.get("devices"), list):
        return {"devices": []}
    return data


def save_store(data: dict) -> None:
    data["updated_at"] = now()
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(STORE)


def record_device(udid: str, *, name: str = "", product: str = "", version: str = "",
                  serial: str = "", source: str = "") -> dict:
    """Add the device to the store, or refresh the record we already have."""
    with LOCK:
        data = load_store()
        devices = data["devices"]
        entry = next((d for d in devices if same_udid(d.get("udid", ""), udid)), None)
        if entry is None:
            entry = {"udid": udid, "first_seen": now()}
            devices.append(entry)
        entry["last_seen"] = now()
        for key, value in (("name", name), ("product", product),
                           ("os_version", version), ("serial", serial)):
            if value:
                entry[key] = value
        if source:
            # The strongest capture path wins: a report from the device
            # itself outranks a number the user typed, which outranks a page
            # reload that carried the identifier in the query.
            rank = {"query": 0, "manual": 1, "profile-service": 2}
            if rank.get(source, 0) >= rank.get(entry.get("source", ""), 0):
                entry["source"] = source
        devices.sort(key=lambda d: d.get("first_seen", ""))
        save_store(data)
        return entry


def flatten_plist(parsed: object, depth: int = 0) -> dict:
    """Flatten a plist into a flat dict of string keys."""
    flat: dict = {}
    if not isinstance(parsed, dict) or depth > 4:
        return flat
    for key, value in parsed.items():
        name = str(key).upper()
        if isinstance(value, dict):
            for inner_key, inner_value in flatten_plist(value, depth + 1).items():
                flat.setdefault(inner_key, inner_value)
        elif isinstance(value, (str, int, float, bool)):
            flat.setdefault(name, value)
    return flat


def parse_profile_service_body(body: bytes) -> dict:
    """Pull the device attributes out of the body iOS posts.

    iOS posts a PKCS#7 signed plist.  The XML plist is embedded in the CMS
    blob, so slice it out and parse that.  A bare plist and a url encoded form
    are handled too, because that is what other iOS builds and the public
    UDID finder services have been seen to send.
    """
    text = body.decode("utf-8", "replace")
    start = text.find("<?xml")
    end = text.rfind("</plist>")
    if start == -1 or end == -1 or end < start:
        start = text.find("<plist")
        end = text.rfind("</plist>")
    if start != -1 and end != -1 and end > start:
        chunk = text[start:end + len("</plist>")].encode("utf-8", "replace")
        try:
            parsed = plistlib.loads(chunk)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return flatten_plist(parsed)
    if "=" in text and "UDID" in text.upper():
        fields = parse_qs(text, keep_blank_values=True)
        flat = {key.upper(): values[0] for key, values in fields.items() if values}
        if flat:
            return flat
    return {}


def attributes_from_body(body: bytes) -> dict:
    """The device attributes from a Profile Service post, as plain strings."""
    flat = parse_profile_service_body(body)
    if not flat:
        match = UDID_PATTERN.search(body.decode("utf-8", "replace"))
        if match:
            return {"UDID": match.group(1)}
        return {}
    clean = {key: value for key, value in flat.items() if isinstance(value, str)}
    for key in UDID_KEYS:
        if key in clean:
            clean["UDID"] = clean[key]
            break
    return clean


def masked(udid: str) -> str:
    if len(udid) <= 12:
        return udid
    return f"{udid[:8]}...{udid[-4:]}"


def render_page(current: dict | None, devices: list, notice: str = "", error: str = "",
                from_query: bool = False) -> bytes:
    """The page the user opens on the device."""
    rows = []
    for device in devices:
        udid = device.get("udid", "")
        is_current = bool(current and same_udid(current.get("udid", ""), udid))
        shown = udid if is_current else masked(udid)
        rows.append(
            "<tr><td><b>{name}</b><br><span class='mini'>{product} &middot; {version} &middot; {seen}</span></td>"
            "<td class='mono'>{udid}</td></tr>".format(
                name=html.escape(device.get("name") or "Unnamed device"),
                product=html.escape(device.get("product") or "unknown model"),
                version=html.escape(device.get("os_version") or "unknown version"),
                seen=html.escape((device.get("last_seen") or "")[:10]),
                udid=html.escape(shown),
            )
        )
    table = ("<table><tr><th>Device</th><th>UDID</th></tr>" + "".join(rows) + "</table>"
             if rows else "<p class='mini'>Nothing captured yet.</p>")

    if current:
        if from_query:
            heading = "The UDID the server received for this device"
        else:
            heading = "The most recent device the server received"
        captured = (
            "<p class='label'>{heading}</p>"
            "<p class='udid mono'>{udid}</p>"
            "<p class='mini'>Copy it into the Apple developer portal, under "
            "Certificates, Identifiers &amp; Profiles &rarr; Devices &rarr; +.</p>"
            "<p class='mini'>Name: {name} &middot; Model: {product} &middot; iOS: {version}</p>"
        ).format(
            heading=heading,
            udid=html.escape(current.get("udid", "")),
            name=html.escape(current.get("name") or "not reported"),
            product=html.escape(current.get("product") or "not reported"),
            version=html.escape(current.get("os_version") or "not reported"),
        )
    else:
        captured = ("<p class='label'>The UDID the server received for this device</p>"
                    "<p class='mini'>Nothing yet. Install the profile below on this device, "
                    "then come back to this page.</p>")

    banner = ""
    if notice:
        banner += f"<div class='note'>{html.escape(notice)}</div>"
    if error:
        banner += f"<div class='warn'><b>{html.escape(error)}</b></div>"

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>SuperCraftOS &mdash; device UDID</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#121016; color:#f2f2f7;
         font: 16px/1.55 -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
         padding: 20px 16px 60px; }}
  .wrap {{ max-width: 620px; margin: 0 auto; }}
  h1 {{ font-size: 26px; font-weight: 800; margin: 4px 0 2px; letter-spacing: -0.4px; }}
  .sub {{ color:#a0a0aa; font-size: 14px; margin: 0 0 22px; }}
  h2 {{ font-size: 13px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase;
       color:#f5428c; margin: 30px 0 10px; }}
  .card {{ background:#1e1b24; border:1px solid #2f2b38; border-radius:16px; padding:16px; margin-bottom:12px; }}
  .label {{ font-size: 13px; color:#a0a0aa; margin:0 0 6px; }}
  .udid {{ font-size: 17px; font-weight: 700; color:#38d1c7; word-break: break-all; margin:0 0 8px; }}
  .a {{ display:block; background:#f5428c; color:#121016; font-weight:700; text-decoration:none;
       border-radius:12px; padding:14px 16px; margin-top:12px; text-align:center; font-size:16px; }}
  .a.ghost {{ background:#2f2b38; color:#f2f2f7; font-weight:600; }}
  .note {{ background:#1a2620; border:1px solid #24402f; border-radius:12px; padding:12px 14px;
           font-size:14px; color:#b8d8c4; margin:14px 0; }}
  .warn {{ background:#2a1d1d; border:1px solid #4a2b2b; border-radius:12px; padding:14px;
           font-size:14px; color:#e8b8b8; margin:14px 0; }}
  .warn b {{ color:#ffb4b4; }}
  .steps {{ counter-reset: s; list-style:none; padding:0; margin:0; }}
  .steps li {{ counter-increment: s; position:relative; padding-left:38px; margin:0 0 14px; }}
  .steps li::before {{ content: counter(s); position:absolute; left:0; top:1px; width:26px; height:26px;
        border-radius:50%; background:#f5428c; color:#121016; font-weight:800; font-size:14px;
        display:flex; align-items:center; justify-content:center; }}
  .steps b {{ color:#fff; }}
  .path {{ display:block; background:#121016; border:1px solid #38d1c7; color:#38d1c7; border-radius:10px;
           padding:10px 12px; margin:6px 0 0; font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size:13px; }}
  ol.plain {{ margin:6px 0 0; padding-left:20px; }}
  ol.plain li {{ margin:0 0 8px; }}
  code, .mono {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 13px; }}
  .mini {{ font-size:13px; color:#8b8b95; margin:4px 0 0; }}
  input {{ width:100%; background:#121016; border:1px solid #2f2b38; color:#f2f2f7; border-radius:10px;
           padding:12px; font: 15px ui-monospace, "SF Mono", Menlo, monospace; margin:0 0 10px; }}
  button {{ width:100%; background:#38d1c7; color:#121016; border:0; border-radius:12px; padding:13px 16px;
            font-size:16px; font-weight:700; }}
  table {{ width:100%; border-collapse:collapse; margin:6px 0 0; }}
  th, td {{ text-align:left; padding:7px 8px; border-bottom:1px solid #2f2b38; font-size:14px; }}
  th {{ color:#38d1c7; font-weight:600; }}
  .sep {{ height:1px; background:#2f2b38; margin:26px 0; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>SuperCraftOS</h1>
  <p class="sub">Device UDID &middot; for the Apple developer portal</p>

  {banner}

  <div class="card">
    {captured}
  </div>

  <h2>How to get it</h2>
  <div class="card">
    <p class="mini">One command on a computer, with the device plugged in with a cable. It
      finds the device by itself, signs the app and installs it. Nothing to download, nothing
      to choose, and no profile.</p>
    <span class="path" style="font-size:13px;line-height:1.8">curl -fsSL {html.escape(BASE_URL)}/ios/supercraftos-install.sh | bash</span>
    <p class="mini">It asks for two things: the app specific password for your Apple ID, and
      the six digit code Apple sends to the device. Both are typed in your terminal, with the
      echo off, and the password goes straight to Apple.</p>
  </div>

  <h2>Or read it off the device</h2>
  <div class="card">
    <p class="mini">If you would rather not run the command, the identifier is in the USB
      serial number. On a Mac, with the device plugged in:</p>
    <span class="path">system_profiler SPUSBDataType | grep -i "Serial Number"</span>
    <p class="mini">The number it prints is the device identifier, in the
      00008110-XXXXXXXXXXXXXXXX form. Paste it into the form below.</p>
  </div>

  <h2>The profile is gone</h2>
  <div class="card">
    <p class="mini">This page used to offer a configuration profile that reported the
      identifier on its own. It was not doing anything but reporting the identifier, but a
      profile still asks the operating system to change its state, and the command above does
      not need one. So it has been withdrawn and the download now answers with an
      explanation instead of a file.</p>
  </div>

  <h2>Remove the profile, if one was installed</h2>
  <div class="card">
    <p class="mini">The profile only reports the device identifier once, but you can remove it
      as soon as the UDID is on this page.</p>
    <span class="path">Settings &rarr; General &rarr; VPN &amp; Device Management</span>
    <ol class="plain">
      <li>Tap <b>SuperCraftOS device UDID</b> under the profiles.</li>
      <li>Tap <b>Remove Profile</b>, then <b>Remove</b>.</li>
    </ol>
    <p class="mini">The Home Screen icon that came with the profile goes away with it.</p>
  </div>

  <h2>Or type the UDID yourself</h2>
  <div class="card">
    <p class="mini">If the profile did not report anything, and you can read the UDID from
      the device or from a computer, send it here instead. The UDID is 40 hex characters,
      or the newer 00008110-XXXXXXXXXXXXXXXX form.</p>
    <form method="post" action="{html.escape(BASE_URL)}/ios/udid">
      <input name="udid" placeholder="UDID" autocapitalize="none" autocorrect="off" spellcheck="false" required>
      <input name="name" placeholder="Device name (optional)">
      <button type="submit">Send the UDID</button>
    </form>
  </div>

  <h2>Devices captured so far</h2>
  <div class="card">
    {table}
    <p class="mini">Only the device you are holding is shown in full. The full list lives in
      the server's data directory.</p>
  </div>

  <p class="mini">The UDID is the identifier Apple uses to add a device to a development or
    ad hoc provisioning profile. It is not a secret and it changes nothing on the device.</p>
</div>
</body>
</html>
"""
    return page.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "SuperCraftOSUdid/1.0"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        print(f"{self.address_string()} {fmt % args}", flush=True)

    # -- helpers ---------------------------------------------------------
    def route(self) -> str:
        path = urlparse(self.path).path
        if path.startswith("/ios"):
            path = path[4:] or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        return path

    def query(self) -> dict:
        return parse_qs(urlparse(self.path).query, keep_blank_values=True)

    def send_bytes(self, code: int, body: bytes, content_type: str,
                   extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_bytes(code, body, "application/json")

    def redirect(self, location: str) -> None:
        body = b"<!DOCTYPE html><meta charset=\"utf-8\"><title>SuperCraftOS</title>"
        self.send_bytes(302, body, "text/html; charset=utf-8", {"Location": location})

    def current_device(self, udid: str) -> dict | None:
        data = load_store()
        devices = data["devices"]
        if udid:
            for device in devices:
                if same_udid(device.get("udid", ""), udid):
                    return device
        if not devices:
            return None
        return max(devices, key=lambda d: d.get("last_seen", ""))

    # -- routes ----------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        route = self.route()
        if route == "/health":
            self.send_json(200, {"ok": True, "store": str(STORE),
                                 "devices": len(load_store()["devices"])})
            return
        if route in ("/udid.mobileconfig", "/udid.webclip.mobileconfig", "/udid.service.mobileconfig"):
            # The configuration profile has been withdrawn.
            #
            # It was never malicious: one payload, one URL, this server, and
            # the device identifier as the only thing it asked for. But a
            # profile is still a profile that asks the operating system to
            # change its state, and the one command installer does not need
            # one, because it reads the identifier off the USB bus. So it is
            # gone rather than left on the server to be installed by mistake.
            self.send_bytes(404, b"The configuration profile has been withdrawn. "
                                 b"Run the one command installer instead: "
                                 b"curl -fsSL https://agent.commetai.ca/ios/supercraftos-install.sh | bash",
                            "text/plain; charset=utf-8")
            return
        if route == "/udid":
            fields = self.query()
            raw_udid = (fields.get("udid") or [""])[0]
            name = (fields.get("name") or [""])[0]
            notice = (fields.get("notice") or [""])[0]
            error = (fields.get("error") or [""])[0]
            udid = ""
            if raw_udid:
                udid = normalize_udid(raw_udid)
                if udid:
                    record_device(udid, name=name.strip()[:80], source="query")
                else:
                    error = ("That does not look like a UDID. It is 40 hex characters, "
                             "or the newer 00008110-XXXXXXXXXXXXXXXX form.")
            current = self.current_device(udid)
            body = render_page(current, load_store()["devices"], notice, error, bool(udid))
            self.send_bytes(200, body, "text/html; charset=utf-8")
            return
        self.send_json(404, {"error": "not_found"})

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self) -> None:  # noqa: N802
        route = self.route()
        if route != "/udid":
            self.send_json(404, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length > 0 else b""
        content_type = (self.headers.get("Content-Type", "") or "").lower()

        if content_type.startswith("application/x-www-form-urlencoded"):
            fields = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
            udid = normalize_udid((fields.get("udid") or [""])[0])
            name = (fields.get("name") or [""])[0].strip()[:80]
            if not udid:
                location = (f"{BASE_URL}/ios/udid?"
                            + "error=" + quote("That does not look like a UDID. It is 40 hex "
                                               "characters, or the newer 00008110-XXXXXXXXXXXXXXXX form."))
                self.redirect(location)
                return
            record_device(udid, name=name, source="manual")
            location = f"{BASE_URL}/ios/udid?udid={quote(udid)}&name={quote(name)}"
            self.redirect(location)
            return

        # The Profile Service callback. The device POSTs a signed plist with
        # the device attributes, and iOS then follows the redirect.
        attributes = attributes_from_body(body)
        udid = normalize_udid(str(attributes.get("UDID", "")))
        if not udid:
            self.redirect(f"{BASE_URL}/ios/udid?error=" + quote(
                "The device posted something, but no UDID was in it."))
            return
        record_device(
            udid,
            name=str(attributes.get("DEVICE_NAME", ""))[:80],
            product=str(attributes.get("PRODUCT", ""))[:40],
            version=str(attributes.get("VERSION", ""))[:40],
            serial=str(attributes.get("SERIAL", ""))[:40],
            source="profile-service",
        )
        location = (f"{BASE_URL}/ios/udid?udid={quote(udid)}"
                    f"&name={quote(str(attributes.get('DEVICE_NAME', '')))}")
        self.redirect(location)


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    print(f"listening on 127.0.0.1:{server.server_address[1]}, storing in {STORE}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
