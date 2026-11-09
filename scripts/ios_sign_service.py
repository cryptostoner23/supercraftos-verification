#!/usr/bin/env python3
"""Sign the app for a device, from a browser on that device.

The user opens a page on the phone, picks one of the four Apple accounts,
types the Apple Account password, and then types the two factor code that
Apple sends to the device. The password goes from the browser to the signing
process over HTTPS and nowhere else: it is never written to a file, never
printed, never logged and never put on a command line.

Only devices that the server has already captured can be signed for, so a
stranger cannot use this page to sign for hardware that is not theirs.
"""
from __future__ import annotations

import html
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent.parent
import importlib.util as _importlib

_CREDENTIAL_SPEC = _importlib.spec_from_file_location(
    "ios_credentials", ROOT / "scripts/ios_credentials.py")
assert _CREDENTIAL_SPEC and _CREDENTIAL_SPEC.loader
credentials = _importlib.module_from_spec(_CREDENTIAL_SPEC)
_CREDENTIAL_SPEC.loader.exec_module(credentials)
SIGNER = Path(os.environ.get("SUPERCRAFTOS_SIGNER", ROOT / "tools/sign-for-devices"))
# The two builds. The keyboard extension targets iOS 26, because that is the
# release that introduced the on-device model it uses as its offline fallback.
# Apple's TN2319, "Deployment target related installation failures", is
# explicit that iOS will not install a bundle whose embedded extension needs a
# newer system than the device runs. So the app on its own is what installs
# everywhere, and the keyboard build is only for a device on iOS 26 or later.
BUILDS = {
    "app": "SuperCraftOS-iOS-Device-unsigned.ipa",
    "keyboard": "SuperCraftOS-iOS-Device-WithKeyboard-unsigned.ipa",
}
APP = Path(os.environ.get("SUPERCRAFTOS_APP", ROOT / "release/ios/SuperCraftOS-iOS-Device-unsigned.ipa"))
DEVICES_FILE = Path(os.environ.get("SUPERCRAFTOS_DEVICES", ROOT / "data/ios-devices.json"))
ACCOUNTS_FILE = Path(os.environ.get("SUPERCRAFTOS_DEVICE_ACCOUNTS",
                                     ROOT / "data/ios-device-accounts.json"))
PUBLISH_DIR = Path(os.environ.get("SUPERCRAFTOS_PUBLISH", "/srv/ios-releases/signed"))
BASE_URL = os.environ.get("IOS_SIGN_BASE_URL", "https://agent.commetai.ca").rstrip("/")

APP_BUNDLE_ID = "com.supercraftos.control"
APP_VERSION = "1"

ACCOUNTS = [
    "harjeev_kohli@hotmail.com",
    "cryptostoner94@icloud.com",
    "cryptostoner@iloud.com",
    "ngboy69@hotmail.com",
]

TWO_FACTOR_PROMPT = "Enter the two factor code sent to your devices:"
TEAM_PROMPT = "Select a team:"
CERT_PROMPT = "The certificate limit was reached"

PROMPT_TIMEOUT = 300
SESSION_TIMEOUT = 900

# One signing run per address per hour is plenty, and it stops the page from
# being used to burn through Apple's rate limits.
RATE_LIMIT: dict[str, list[float]] = {}
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def signer_diagnostic(session: "Session") -> str:
    """Return a useful, bounded signer failure without terminal formatting."""
    lines = [ANSI_ESCAPE.sub("", line).strip() for line in session.output]
    lines = [line for line in lines if line]
    preferred = [line for line in lines if re.search(
        r"(?i)(error|failed|panic|invalid|unauthor|password|verification|locked|denied)", line)]
    selected = preferred[-8:] if preferred else lines[-12:]
    detail = " | ".join(selected)[-1600:]
    return detail or session.failed or "the signing tool stopped without an error message"


def rate_limited(address: str) -> bool:
    now = time.time()
    hits = [stamp for stamp in RATE_LIMIT.get(address, []) if now - stamp < 3600]
    RATE_LIMIT[address] = hits
    return len(hits) >= 4


def note_rate(address: str) -> None:
    RATE_LIMIT.setdefault(address, []).append(time.time())


def device_accounts() -> dict:
    """Which account each device signs with."""
    try:
        data = json.loads(ACCOUNTS_FILE.read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def account_for_device(udid: str) -> str:
    """The account a device signs with, from its own file, or its record."""
    accounts = device_accounts()
    found = accounts.get(udid) or accounts.get(udid.lower())
    if found:
        return str(found)
    for device in captured_devices():
        if device["udid"].lower() == (udid or "").lower():
            return device.get("apple_id") or ""
    return ""


def captured_devices() -> list[dict]:
    """The devices the server has seen, read defensively."""
    try:
        data = json.loads(DEVICES_FILE.read_text())
    except Exception:
        return []
    records = data.get("devices", data) if isinstance(data, dict) else data
    if isinstance(records, dict):
        records = list(records.values())
    found = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        udid = (record.get("udid") or "").strip()
        if not udid:
            continue
        name = record.get("name") or record.get("device") or "device"
        found.append({"udid": udid, "name": str(name),
                      "apple_id": (record.get("apple_id") or "").strip()})
    return found


class Session:
    """One signing run, held between the password step and the code step."""

    def __init__(self, apple_id: str, udids: list[str], build: str = "app",
                 password: str = ""):
        self.id = uuid.uuid4().hex
        self.apple_id = apple_id
        self.udids = udids
        self.build = build if build in BUILDS else "app"
        # In memory only, and only for the run. It is never written anywhere.
        self.password = password
        self.process: subprocess.Popen | None = None
        self.lines: queue.Queue = queue.Queue()
        self.output: list[str] = []
        self.done = False
        self.failed = ""
        self.signed: str = ""
        self.started = time.time()

    def spawn(self, password: str) -> None:
        command = [str(SIGNER), "--apple-id", self.apple_id]
        for udid in self.udids:
            command += ["--udid", udid]
        command += ["--app", str(self.app_path), "--out", str(self.out_path)]
        storage = os.environ.get("SUPERCRAFTOS_STORAGE")
        if storage:
            command += ["--storage", storage]
        environment = dict(os.environ)
        # The password reaches the signer through the environment, for that
        # one process only. It is never in the command line, so it cannot end
        # up in a process listing or in the scrollback.
        environment["SUPERCRAFTOS_APPLE_PASSWORD"] = self.password
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=environment,
            text=True,
            bufsize=1,
        )
        threading.Thread(target=self._pump, daemon=True).start()

    @property
    def app_path(self) -> Path:
        if self.build == "keyboard":
            return Path(os.environ.get("SUPERCRAFTOS_APP_KEYBOARD",
                                       ROOT / "release/ios" / BUILDS["keyboard"]))
        return Path(os.environ.get("SUPERCRAFTOS_APP",
                                   ROOT / "release/ios" / BUILDS["app"]))

    @property
    def out_path(self) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", self.apple_id)
        suffix = "with-keyboard" if self.build == "keyboard" else "app"
        return Path(os.environ.get("SUPERCRAFTOS_OUT", ROOT / "release/ios/signed")) / f"{safe}-{suffix}.ipa"

    def _pump(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        for line in self.process.stdout:
            clean = line.rstrip("\n")
            self.output.append(clean)
            self.lines.put(clean)
        self.lines.put("")
        self.process.wait()
        for stream in (self.process.stdin, self.process.stdout):
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                pass
        self.done = True
        if self.process.returncode != 0 and not self.failed:
            self.failed = f"the signing tool exited with {self.process.returncode}"

    def send(self, line: str) -> None:
        assert self.process is not None and self.process.stdin is not None
        try:
            self.process.stdin.write(line + "\n")
            self.process.stdin.flush()
        except Exception:
            pass

    def read_until(self, predicate, timeout: int = PROMPT_TIMEOUT) -> str:
        """Read the signer's output until the predicate matches or it stops."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = self.lines.get(timeout=1)
            except queue.Empty:
                if self.done:
                    return ""
                continue
            if line == "":
                return ""
            if predicate(line):
                return line
        return ""

    def finish(self) -> None:
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.kill()
                self.process.wait(timeout=10)
            except Exception:
                pass
        if self.process is not None:
            for stream in (self.process.stdin, self.process.stdout):
                try:
                    if stream is not None:
                        stream.close()
                except Exception:
                    pass


SESSIONS: dict[str, Session] = {}
# A signing that is waiting for the six digit code Apple sent to the device.
PENDING: dict[str, Session] = {}


def renew_due() -> None:
    """Re-sign a bundle before its seven days are up.

    The encrypted Apple Account password kept for the account is used, so nothing has to
    be typed. If Apple asks for the six digit code, the signing waits for it
    and the device's page asks for it.
    """
    for device in captured_devices():
        udid = device["udid"]
        account = account_for_device(device["udid"])
        if not account or udid in PENDING:
            continue
        passwords = credentials.passwords_for(account)
        if not passwords:
            continue
        bundle = signed_bundle_path(account)
        if bundle is not None and not credentials.needs_renewal(bundle):
            continue
        for candidate in passwords:
            session = Session(account, [udid], "app", candidate)
            SESSIONS[session.id] = session
            session.spawn(candidate)
            line = session.read_until(
                lambda text: TWO_FACTOR_PROMPT in text or TEAM_PROMPT in text
                or CERT_PROMPT in text, timeout=120)
            if TWO_FACTOR_PROMPT in line:
                PENDING[udid] = session
                break
            if CERT_PROMPT in line:
                session.send("1")
                line = session.read_until(
                    lambda text: TWO_FACTOR_PROMPT in text or TEAM_PROMPT in text, timeout=60)
            if TEAM_PROMPT in line:
                session.send("1")
                line = session.read_until(
                    lambda text: TWO_FACTOR_PROMPT in text, timeout=60)
            if TWO_FACTOR_PROMPT in line:
                PENDING[udid] = session
                break
            if session.out_path.exists():
                publish(session.out_path)
                SESSIONS.pop(session.id, None)
                break
            SESSIONS.pop(session.id, None)


def renewal_worker() -> None:
    while True:
        time.sleep(1800)
        try:
            renew_due()
        except Exception:  # noqa: BLE001
            pass


def signed_bundle_path(account: str):
    """The published bundle for an account, if there is one."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", account)
    for directory in (PUBLISH_DIR,
                      Path(os.environ.get("SUPERCRAFTOS_OUT", ROOT / "release/ios/signed"))):
        if not directory.exists():
            continue
        for path in sorted(directory.glob(f"{safe}-*.ipa")):
            if directory == PUBLISH_DIR:
                return path
            published = PUBLISH_DIR / path.name
            if published.exists():
                return published
    return None


def sweep_sessions() -> None:
    now = time.time()
    for key, session in list(SESSIONS.items()):
        if now - session.started > SESSION_TIMEOUT:
            session.finish()
            SESSIONS.pop(key, None)


def publish(signed: Path) -> str:
    """Put the signed bundle where the device can download it."""
    PUBLISH_DIR.mkdir(parents=True, exist_ok=True)
    target = PUBLISH_DIR / signed.name
    shutil.copy2(signed, target)
    return f"{BASE_URL}/ios/signed/{target.name}"


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>SuperCraftOS &middot; sign</title>
<style>
 body {{ background:#0b0a0e; color:#f4f4f5; font:15px/1.5 -apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif; margin:0; padding:22px; }}
 .wrap {{ max-width:520px; margin:0 auto; }}
 h1 {{ font-size:19px; font-weight:800; letter-spacing:.02em; margin:0 0 4px; }}
 .sub {{ color:#a1a1aa; font-size:12px; margin:0 0 20px; }}
 label {{ display:block; font-size:11px; text-transform:uppercase; letter-spacing:.09em; color:#a1a1aa; margin:16px 0 5px; }}
 input, select, textarea {{ width:100%; box-sizing:border-box; background:#17161c; border:1px solid #2c2c2e; color:#f4f4f5; border-radius:10px; padding:12px; font-size:15px; }}
 button {{ width:100%; margin-top:18px; background:#f5428c; color:#0b0a0e; border:0; border-radius:10px; padding:14px; font-size:15px; font-weight:700; }}
 .note {{ background:#17161c; border:1px solid #2c2c2e; border-radius:12px; padding:14px; margin:16px 0; font-size:13px; color:#d4d4d8; }}
 .err {{ border-color:#7f1d1d; color:#fca5a5; }}
 .ok {{ border-color:#14532d; color:#86efac; }}
 a {{ color:#f5428c; }}
 code, .mono {{ font-family:ui-monospace,Menlo,monospace; font-size:12px; word-break:break-all; }}
 .dev {{ display:flex; gap:9px; align-items:center; padding:9px 0; border-bottom:1px solid #232227; font-size:14px; }}
 .dev input {{ width:auto; }}
 ol {{ padding-left:20px; color:#d4d4d8; font-size:13px; }}
 .small {{ font-size:12px; color:#a1a1aa; }}
</style></head><body><div class="wrap">
<h1>SUPERCRAFTOS &middot; SIGN</h1>
<p class="sub">Sign the app for this device. The password goes straight to Apple.</p>
{body}
</div></body></html>
"""


def page(body: str) -> bytes:
    return PAGE.format(body=body).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "SuperCraftOSSign/1.0"
    protocol_version = "HTTP/1.1"

    # Only the request line is logged. The body holds the password and the
    # two factor code, and they never reach a log.
    def log_message(self, fmt, *args):  # noqa: A003
        print(f"[sign] {self.address_string()} {fmt % args}", flush=True)

    def reply(self, body: bytes, status: int = 200, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def cookie(self) -> dict:
        """The cookies on this request."""
        raw = self.headers.get("Cookie") or ""
        out = {}
        for part in raw.split(";"):
            if "=" in part:
                name, value = part.split("=", 1)
                out[name.strip()] = value.strip()
        return out

    def session_token(self) -> dict | None:
        """The claims of the token on this request, if it is genuine."""
        token = self.cookie().get("sc_jwt")
        if not token:
            return None
        return credentials.read_token(token)

    def set_token(self, account: str, udid: str, build: str) -> None:
        token = credentials.make_token(account, udid, build)
        self.send_response(302)
        self.send_header("Location", f"{BASE_URL}/ios/device/{udid}")
        self.send_header("Set-Cookie",
                         f"sc_jwt={token}; HttpOnly; Secure; SameSite=Strict; "
                         f"Path=/ios; Max-Age={credentials.TOKEN_TTL}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def form(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8", "replace")
        return {key: values[0] for key, values in parse_qs(raw).items()}

    # GET ------------------------------------------------------------------

    def route(self) -> str:
        """The path, with the public prefix removed.

        Caddy proxies /ios/sign to this service as it is, so the service sees
        /ios/sign and /ios/sign/start as well as the bare paths.
        """
        path = self.path.split("?")[0]
        if path == "/ios":
            return "/"
        if path.startswith("/ios/"):
            return path[4:]
        return path

    def do_GET(self):  # noqa: N802
        sweep_sessions()
        path = self.route()
        if path in ("/sign", "/"):
            self.reply(page(self.sign_form()))
            return
        if path.endswith(".plist") and "/device/" in path:
            self.reply(self.device_manifest(path), content_type="application/xml")
            return
        if path == "/devices":
            self.reply(page(self.devices_page()))
            return
        if path.startswith("/device/"):
            parts = path.split("/")
            if len(parts) == 5 and parts[3] == "account":
                self.set_account(parts[2], self.form().get("apple_id", ""))
                self.redirect_to(f"{BASE_URL}/ios/device/{parts[2]}")
                return
            if len(parts) == 5 and parts[3] == "step":
                self.mark_step(parts[2], parts[4])
                self.redirect_to(f"{BASE_URL}/ios/device/{parts[2]}")
                return
            self.reply(page(self.device_page(path.split("/", 2)[-1])))
            return
        if path == "/health":
            self.reply(b'{"ok":true}', content_type="application/json")
            return
        self.reply(page("<div class='note err'>Nothing here.</div>"), status=404)

    def set_account(self, udid: str, apple_id: str) -> None:
        """Point a device at the account that signs for it."""
        apple_id = (apple_id or "").strip()
        if apple_id and apple_id not in ACCOUNTS:
            return
        accounts = device_accounts()
        if apple_id:
            accounts[udid] = apple_id
        else:
            accounts.pop(udid, None)
        ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = ACCOUNTS_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(accounts, indent=2) + "\n")
        os.chmod(temporary, 0o600)
        temporary.replace(ACCOUNTS_FILE)
        os.chmod(ACCOUNTS_FILE, 0o600)

    def mark_step(self, udid: str, step: str) -> None:
        """Record that a step was reached, so the server can see where a
        device got to instead of guessing."""
        if not re.fullmatch(r"[0-9A-Za-z-]{1,80}", udid or ""):
            return
        if not re.fullmatch(r"[0-9A-Za-z_-]{1,40}", step or ""):
            return
        try:
            data = json.loads(DEVICES_FILE.read_text())
        except Exception:
            return
        records = data.get("devices", data) if isinstance(data, dict) else data
        for record in records or []:
            if isinstance(record, dict) and (record.get("udid") or "").lower() == udid.lower():
                steps = record.setdefault("steps", {})
                steps[step] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                data["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                try:
                    DEVICES_FILE.write_text(json.dumps(data, indent=2) + "\n")
                except Exception:
                    pass
                return

    def redirect_to(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def device_manifest(self, path: str) -> bytes:
        """An install manifest for the bundle signed for a device.

        iOS reads this and installs the app. No sideloading tool, no
        computer, no profile: just a link on the device.
        """
        parts = [part for part in path.split("/") if part]
        udid = ""
        for index, part in enumerate(parts):
            if part == "device" and index + 1 < len(parts):
                udid = parts[index + 1]
        record = next((device for device in captured_devices()
                       if device["udid"].lower() == udid.lower()), None)
        empty = (b'<?xml version="1.0" encoding="UTF-8"?>\n'
                 b'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                 b'"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                 b'<plist version="1.0">\n<dict>\n</dict>\n</plist>\n')
        if record is None:
            return empty
        bundle = self.signed_bundle_for(record)
        if bundle is None:
            return empty
        url = f"{BASE_URL}/ios/signed/{bundle.name}"
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>items</key>
	<array>
		<dict>
			<key>assets</key>
			<array>
				<dict>
					<key>kind</key>
					<string>software-package</string>
					<key>url</key>
					<string>{url}</string>
				</dict>
			</array>
			<key>metadata</key>
			<dict>
				<key>bundle-identifier</key>
				<string>{APP_BUNDLE_ID}</string>
				<key>bundle-version</key>
				<string>{APP_VERSION}</string>
				<key>kind</key>
				<string>software</string>
				<key>title</key>
				<string>SuperCraftOS</string>
			</dict>
		</dict>
	</array>
</dict>
</plist>
"""
        return plist.encode("utf-8")

    def signed_bundle_for(self, record: dict):
        """The signed bundle made for this device's account, if there is one.

        The published copy is the one the device can download, so that is the
        one that is looked for.
        """
        account = account_for_device(record["udid"]) or record.get("apple_id") or ""
        if not account:
            return None
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", account)
        for directory in (PUBLISH_DIR,
                          Path(os.environ.get("SUPERCRAFTOS_OUT", ROOT / "release/ios/signed"))):
            if not directory.exists():
                continue
            for path in sorted(directory.glob(f"{safe}-*.ipa")):
                if directory == PUBLISH_DIR:
                    return path
                published = PUBLISH_DIR / path.name
                if published.exists():
                    return published
        return None

    def devices_page(self) -> str:
        """Every device the server knows, with its own page."""
        rows = []
        for record in captured_devices():
            link = f"{BASE_URL}/ios/device/{record['udid']}"
            account = account_for_device(record["udid"]) or record.get("apple_id") or ""
            mapping = (f'<br><span class="mono">signed in as {html.escape(account)}</span>'
                       if account else "")
            rows.append(
                f'<li><b>{html.escape(record["name"])}</b><br>'
                f'<span class="mono">{html.escape(record["udid"])}</span>{mapping}<br>'
                f'<a href="{html.escape(link)}">this device\'s page</a></li>')
        if not rows:
            rows = ["<li>No device has told the server its identifier yet.</li>"]
        return f"""
<h1>SuperCraftOS &middot; devices</h1>
<p class="sub">Every device registered for signing</p>
<div class="note">{''.join(rows)}</div>
<h2>iCloud</h2>
<p class="mini">iCloud access belongs to the Apple ID, not to a device. These are the devices
   on that account.</p>
<a class="a ghost" href="https://www.icloud.com">Sign in to iCloud</a>
<a class="a ghost" href="https://www.icloud.com/signin">iCloud sign in, on this device</a>
<a class="a ghost" href="https://www.icloud.com/find">Find My</a>
<a class="a ghost" href="https://account.apple.com">The Apple Account page</a>
"""

    def device_page(self, udid: str) -> str:
        """One page for one device."""
        import urllib.parse
        udid = (udid or "").strip()
        record = next((device for device in captured_devices()
                       if device["udid"].lower() == udid.lower()), None)
        if record is None:
            return ("<div class='note err'>This device is not registered. "
                    "Send its identifier to the server first.</div>")
        account = account_for_device(record["udid"]) or record.get("apple_id") or ""
        storage = Path(os.environ.get("SUPERCRAFTOS_STORAGE", ""))
        cached = False
        if account and storage.is_absolute() and storage.exists():
            cached = any(path.name.startswith(account) for path in storage.iterdir())
        session_note = (
            f'<br><br><b>Signing setup for this account is already done.</b><br>'
            f'<span class="small">The certificates and the anisette data are kept, so the '
            f'account is never set up twice. Each signing still needs the Apple Account '
            f'password, and a code if Apple asks for one, which arrives on this device.</span>'
            if cached else
            f'<br><br><b>No session for this account yet.</b><br>'
            f'<span class="small">The first sign in needs the Apple Account password and the '
            f'six digit code, which Apple sends to this device. The certificates and the '
            f'anisette data are kept afterwards, so the account is never set up twice.</span>')
        code_form = ""
        if record["udid"] in PENDING:
            code_form = (
                '<div class="note"><b>A renewal is waiting for the six digit code.</b><br>'
                'Apple sent it to this device. Type it below and the renewal finishes '
                'on its own.</div>'
                '<form method="post" action="/ios/sign/code">'
                f'<input type="hidden" name="udid" value="{html.escape(record["udid"])}">'
                '<label>Six digit code</label>'
                '<input name="code" inputmode="numeric" autocomplete="one-time-code" '
                'placeholder="123456" required>'
                '<button type="submit">Finish the renewal</button></form>')
        manifest = urllib.parse.quote(f"{BASE_URL}/ios/device/{record['udid']}/manifest.plist", safe="")
        bundle = self.signed_bundle_for(record)
        if bundle is not None:
            install_block = (
                '<p class="mini">Open this page in Safari on the registered device, then tap '
                'once. iOS reads the signed manifest and installs the app without a cable or a '
                'separate sideloading app.</p>'
                f'<a class="a" href="itms-services://?action=download-manifest&url={manifest}">'
                'Install the signed app on this device</a>'
                '<p class="mini">The same link every week. After the seven days are up, sign it '
                'again below and tap the link again.</p>'
                f'<a class="a ghost" href="{BASE_URL}/ios/signed/{html.escape(bundle.name)}">'
                'Download the signed bundle</a>')
        else:
            install_block = ('<p class="mini">Nothing is signed for this device yet. Sign it '
                             'below, and the install link appears here.</p>'
                             '<p class="mini">Or sign it on the device itself, where your Apple '
                             'password never leaves the phone:</p>'
                             f'<a class="a" href="{BASE_URL}/ios/install.html">Install on this '
                             'device without a password</a>')
        options = "".join(
            f'<option value="{html.escape(a)}"{" selected" if a == account else ""}>{html.escape(a)}</option>'
            for a in ACCOUNTS)
        mapping = ""
        if account:
            mapping = f"""
  <br><br><b>Signed in as</b> <span class="mono">{html.escape(account)}</span><br>
  <span class="small">The six digit code Apple sends for that account arrives on this
     device, so this is the account to use. Signing with a different one puts the code
     on the other device, or nowhere at all.</span>"""
        published = []
        for bundle in sorted(PUBLISH_DIR.glob("*.ipa")) if PUBLISH_DIR.exists() else []:
            published.append(f'<li><a href="{BASE_URL}/ios/signed/{bundle.name}">{bundle.name}</a></li>')
        udid = html.escape(record["udid"])
        return f"""
<h1>SuperCraftOS &middot; {html.escape(record['name'])}</h1>
<p class="sub">This device's page</p>
<div class="note">
  <b>{html.escape(record['name'])}</b><br>
  <span class="mono">{html.escape(record['udid'])}</span>{mapping}{session_note}
</div>
<h2>Which account signs for this device</h2>
<p class="mini">This private development signer requires the Apple Account password and Apple's
   two-factor challenge. An app-specific password cannot create signing certificates or
   provisioning profiles. Use the official Apple Developer links below if you do not want to
   provide the account password to this server.</p>
<form method="post" action="/ios/device/{udid}/account">
  <select name="apple_id">{options}</select>
  <button type="submit">Use this account</button>
</form>
<p class="mini">Official signing setup:
   <a href="https://developer.apple.com/account/">Apple Developer Account</a>,
   <a href="https://developer.apple.com/account/resources/certificates/list">certificates</a>, and
   <a href="https://developer.apple.com/account/resources/profiles/list">provisioning profiles</a>.</p>

<h2>Direct install</h2>
{install_block}
<h2>Sign in</h2>
<p class="mini">Open one of these in Safari on this device. Signing in to Apple here is what
   makes the six digit code arrive on this device, and that code is what finishes the
   signing below.</p>
<a class="a ghost" href="https://idmsa.apple.com">Sign in to Apple</a>
<a class="a ghost" href="https://www.icloud.com/signin">Sign in to iCloud</a>
<a class="a ghost" href="https://account.apple.com">Your Apple Account</a>
<p class="mini">Use Apple Developer Account for the official certificate/profile route.</p>

{code_form}
<h2>Create the install link</h2>
<p class="mini">The server signs the full app for this registered device. Enter the Apple Account
   password once. If Apple sends a six-digit code, enter it on the next page. You return here
   automatically and the direct install button appears.</p>
<form method="post" action="/ios/sign/start">
  <input type="hidden" name="udid" value="{html.escape(record['udid'])}">
  <label>Apple ID</label>
  <select name="apple_id">{options}</select>
  <label>What to build</label>
  <select name="build">
    <option value="app">The app on its own &middot; iOS 17 and later</option>
    <option value="keyboard">The app with the keyboard &middot; needs iOS 26 or later</option>
  </select>
  <label>Apple Account password (not an app-specific password)</label>
  <input name="password" type="password" autocomplete="current-password" autocapitalize="none" spellcheck="false" required>
  <button type="submit">Sign and create the install link</button>
</form>
<h2>iCloud for this account</h2>
<p class="mini">iCloud access belongs to the Apple ID, not to a device. This device is one of
   the devices on that account.</p>
<a class="a ghost" href="https://www.icloud.com">Sign in to iCloud</a>
<a class="a ghost" href="https://www.icloud.com/find">Find My, where this device appears</a>
<a class="a ghost" href="https://account.apple.com">The Apple Account page, and its device list</a>
<p class="mini">On the device itself, iCloud is under Settings, your name, then iCloud. The
   identifier on this page is not a login and cannot sign in to anything: Apple uses it to
   register a device for signing, and to show the device in your account.</p>
<h2>Signed bundles</h2>
<div class="note">{''.join(published) or "None yet."}</div>
"""

    def sign_form(self, message: str = "", error: bool = False, session_id: str = "",
                  account: str = "", needs_code: bool = False) -> str:
        devices = captured_devices()
        options = "\n".join(
            f'<option value="{html.escape(d["udid"])}"{" selected" if d["udid"] in html.escape(account) else ""}>'
            f'{html.escape(d["name"])} &middot; {html.escape(d["udid"][-8:])}</option>'
            for d in devices)
        accounts = "\n".join(
            f'<option value="{html.escape(a)}"{" selected" if a == account else ""}>{html.escape(a)}</option>'
            for a in ACCOUNTS)

        if not devices:
            return ("<div class='note err'>No device has been captured yet. Open "
                    f"<a href='{BASE_URL}/ios/udid'>the capture page</a> on this device first.</div>")

        if needs_code:
            return f"""
<div class="note">Apple has sent a six digit code to your device. Type it below.</div>
<form method="post" action="/ios/sign/finish">
  <input type="hidden" name="session" value="{html.escape(session_id)}">
  <label>Two factor code</label>
  <input name="code" inputmode="numeric" autocomplete="one-time-code" placeholder="123456" required>
  <button type="submit">Finish signing</button>
</form>"""

        note = f"<div class='note {'err' if error else ''}'>{message}</div>" if message else ""
        return f"""{note}
<div class="note"><b>Prefer not to hand over your Apple password?</b> The app can be
signed on the device itself instead, and the password never leaves the phone.
<a href="{BASE_URL}/ios/install.html">Open the device install page</a> for that route.
The form below is the other one: this server signs the bundle for you and hands back
one install link that never changes.</div>
<form method="post" action="/ios/sign/start">
  <label>Apple ID</label>
  <select name="apple_id">{accounts}</select>
  <label>Device</label>
  <select name="udid">{options}</select>
  <label>What to build</label>
  <select name="build">
    <option value="app">The app on its own &middot; iOS 17 and later &middot; recommended</option>
    <option value="keyboard">The app with the keyboard &middot; needs iOS 26 or later</option>
  </select>
  <label>Apple Account password (not an app-specific password)</label>
  <input name="password" type="password" autocomplete="current-password" autocapitalize="none" spellcheck="false" required>
  <button type="submit">Sign and create the install link</button>
</form>"""


    # POST -----------------------------------------------------------------

    def do_POST(self):  # noqa: N802
        sweep_sessions()
        fields = self.form()
        action = self.route()
        if action == "/sign/session":
            self.receive_session(fields)
            return
        if action == "/sign/code":
            self.finish_renewal(fields)
            return
        if action.startswith("/device/") and action.endswith("/account"):
            udid = action.split("/")[2]
            self.set_account(udid, fields.get("apple_id", ""))
            self.redirect_to(f"{BASE_URL}/ios/device/{udid}")
            return
        if action.startswith("/device/") and action.endswith("/step"):
            udid = action.split("/")[2]
            self.mark_step(udid, action.split("/")[4])
            self.redirect_to(f"{BASE_URL}/ios/device/{udid}")
            return
        if action == "/sign/start":
            self.start(fields)
            return
        if action == "/sign/finish":
            self.complete_signing(fields)
            return
        self.reply(page("<div class='note err'>Nothing here.</div>"), status=404)

    def receive_session(self, fields: dict) -> None:
        """Take over a cached Apple session, so the server can sign with it."""
        import base64

        name = (fields.get("name") or "").strip()
        data = fields.get("data") or ""
        if not name or not data:
            self.reply(b"The session is empty.", status=400,
                       content_type="text/plain; charset=utf-8")
            return
        if not re.fullmatch(r"[A-Za-z0-9._@-]{1,120}", name):
            self.reply(b"That session name is not acceptable.", status=400,
                       content_type="text/plain; charset=utf-8")
            return
        storage = Path(os.environ.get("SUPERCRAFTOS_STORAGE", ""))
        if not storage.is_absolute():
            self.reply(b"The server has no session store configured.", status=503,
                       content_type="text/plain; charset=utf-8")
            return
        try:
            raw = base64.b64decode(data, validate=True)
        except Exception:
            self.reply(b"That session is not readable.", status=400,
                       content_type="text/plain; charset=utf-8")
            return
        storage.mkdir(parents=True, exist_ok=True)
        os.chmod(storage, 0o700)
        target = storage / name
        target.write_bytes(raw)
        os.chmod(target, 0o600)
        self.reply(f"The session for {name} is stored. The server can sign with it now."
                   .encode("utf-8"), content_type="text/plain; charset=utf-8")

    def start(self, fields: dict) -> None:
        password = fields.get("password") or ""
        udid = (fields.get("udid") or "").strip()
        posted = (fields.get("apple_id") or "").strip()

        # The account comes from the device, not from the form. The device is
        # mapped to the account it is signed in to, so the six digit code
        # always arrives on the device being installed.
        apple_id = account_for_device(udid) or posted

        if apple_id not in ACCOUNTS:
            self.reply(page(self.sign_form("That account is not one of the four.", error=True)), status=400)
            return
        known = {device["udid"] for device in captured_devices()}
        if udid not in known:
            self.reply(page(self.sign_form("That device has not been captured.", error=True, account=apple_id)), status=400)
            return
        if rate_limited(apple_id):
            self.reply(page(self.sign_form("Too many attempts for this account. Try again in an hour.",
                                           error=True, account=apple_id)), status=429)
            return
        if not SIGNER.exists() or not APP.exists():
            self.reply(page(self.sign_form("The signing tool is not on the server yet.", error=True)), status=500)
            return

        note_rate(apple_id)
        build = (fields.get("build") or "app").strip()
        if build not in BUILDS:
            build = "app"
        # A password typed in, or one already kept for this account, tried in
        # turn, so a revoked one does not stop the others.
        tried: list[str] = []
        if password:
            tried.append(password)
        else:
            token = self.session_token()
            if token and token.get("device", "").lower() == udid.lower():
                tried = credentials.passwords_for(apple_id)

        session = None
        line = ""
        for candidate in tried:
            session = Session(apple_id, [udid], build, candidate)
            SESSIONS[session.id] = session
            session.spawn(candidate)
            password = ""
            line = session.read_until(
                lambda text: TWO_FACTOR_PROMPT in text or TEAM_PROMPT in text
                or CERT_PROMPT in text, timeout=120)
            if line != "" or session.done:
                break
            SESSIONS.pop(session.id, None)
        if session is None:
            if not password:
                self.reply(page(self.sign_form(
                    "The password is empty. Sign in once with the Apple Account "
                    "password, and it is kept for the next time.",
                    error=True, account=apple_id)), status=400)
            else:
                self.reply(page(self.sign_form(
                    "That account has no password kept, and none was given.",
                    error=True, account=apple_id)), status=400)
            return
        if line == "" and session.done and not session.out_path.exists():
            detail = signer_diagnostic(session)
            session.finish()
            SESSIONS.pop(session.id, None)
            self.reply(page(self.sign_form(
                "The signing tool stopped before it asked for the code.<br><span class='mono'>"
                + html.escape(detail) + "</span>", error=True, account=apple_id)), status=502)
            return
        if CERT_PROMPT in line:
            session.send("1")
            line = session.read_until(lambda text: TWO_FACTOR_PROMPT in text or TEAM_PROMPT in text, timeout=120)
        if TEAM_PROMPT in line:
            session.send("1")
            line = session.read_until(lambda text: TWO_FACTOR_PROMPT in text, timeout=120)
        if TWO_FACTOR_PROMPT in line:
            PENDING[udid] = session
            self.reply(page(self.sign_form(session_id=session.id, account=apple_id, needs_code=True)))
            return
        if line == "" and not session.done:
            # Some Apple authentication responses reach the callback without
            # the prompt text being flushed through the pipe. Keep the live
            # process reachable from the device page instead of hiding the
            # code field while it waits on stdin.
            PENDING[udid] = session
            self.reply(page(self.sign_form(session_id=session.id, account=apple_id, needs_code=True)))
            return
        self.complete(session)

    def finish_renewal(self, fields: dict) -> None:
        """Give a waiting renewal its code and let it finish."""
        udid = (fields.get("udid") or "").strip()
        code = (fields.get("code") or "").strip()
        session = PENDING.get(udid)
        if session is None:
            self.redirect_to(f"{BASE_URL}/ios/device/{udid}")
            return
        if code:
            session.send(code)
        deadline = time.time() + 240
        while not session.done and time.time() < deadline:
            line = session.read_until(
                lambda text: TEAM_PROMPT in text or CERT_PROMPT in text, timeout=5)
            if line == "":
                continue
            if TEAM_PROMPT in line:
                session.send("1")
            elif CERT_PROMPT in line:
                session.send("1")
        PENDING.pop(udid, None)
        if session.out_path.exists():
            publish(session.out_path)
        SESSIONS.pop(session.id, None)
        self.redirect_to(f"{BASE_URL}/ios/device/{udid}")

    def complete_signing(self, fields: dict) -> None:
        session = SESSIONS.get((fields.get("session") or "").strip())
        if session is None:
            self.reply(page(self.sign_form("That signing run has expired. Start again.", error=True)), status=400)
            return
        code = (fields.get("code") or "").strip()
        for udid, pending in list(PENDING.items()):
            if pending is session:
                PENDING.pop(udid, None)
        if code:
            session.send(code)
        # Answer whatever else the tool asks for until it finishes.
        deadline = time.time() + 300
        while not session.done and time.time() < deadline:
            line = session.read_until(
                lambda text: TEAM_PROMPT in text or CERT_PROMPT in text, timeout=5)
            if line == "":
                continue
            if TEAM_PROMPT in line:
                session.send("1")
            elif CERT_PROMPT in line:
                session.send("1")
        self.complete(session)

    def complete(self, session: Session) -> None:
        for _ in range(120):
            if session.done:
                break
            time.sleep(0.5)
        if session.out_path.exists():
            publish(session.out_path)
            if session.password:
                credentials.remember_password(session.apple_id, session.password)
            SESSIONS.pop(session.id, None)
            # The browser keeps a signed token, so the next renewal needs no
            # password at all, only the code if Apple asks for one.
            self.set_token(session.apple_id, session.udids[0], session.build)
            return
        detail = signer_diagnostic(session)
        session.finish()
        SESSIONS.pop(session.id, None)
        self.reply(page(self.sign_form(
            "The signing did not finish.<br><span class='mono'>" + html.escape(detail) + "</span>",
            error=True, account=session.apple_id)), status=502)


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("IOS_SIGN_PORT", "8797"))), Handler)
    print("[sign] listening on 127.0.0.1:8797", flush=True)
    threading.Thread(target=renewal_worker, daemon=True).start()
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
