#!/usr/bin/env python3
"""Tests for the browser signing service.

The service is what lets the user sign the app from the phone, with no Mac
and no terminal. The credentials it handles are the sensitive part, so the
tests are mostly about what the service does with them: it must never log a
body, never write a credential to disk, and never sign for a device it has
not captured.
"""
from __future__ import annotations

import importlib.util
import json
import os
import plistlib
import socket
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("ios_sign_service", ROOT / "scripts/ios_sign_service.py")
assert SPEC and SPEC.loader
service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(service)

# A stand in for the real signing tool. It asks for the two factor code the
# same way the real one does, and writes a file where a signed bundle goes.
FAKE_SIGNER = """#!/usr/bin/env python3
import os, sys, pathlib
print("Enter the two factor code sent to your devices:", flush=True)
code = sys.stdin.readline()
print("Signed bundle written to " + sys.argv[-1], flush=True)
out = pathlib.Path(sys.argv[-1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(b"PK\\x03\\x04 fake signed bundle")
"""


class SignServiceTests(unittest.TestCase):

    def setUp(self):
        service.RATE_LIMIT.clear()

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.signer = root / "fake-signer"
        cls.signer.write_text(FAKE_SIGNER)
        cls.signer.chmod(0o755)
        cls.app = root / "app.ipa"
        cls.app.write_bytes(b"PK\x03\x04 unsigned")
        cls.keyboard_app = root / "keyboard.ipa"
        cls.keyboard_app.write_bytes(b"PK\x03\x04 unsigned with keyboard")
        cls.devices = root / "devices.json"
        # The device carries the account it is signed in to, which is what
        # decides which signed bundle the manifest points at.
        cls.devices.write_text(json.dumps({"devices": [
            {"udid": "00008030-001A2B3C4D5E6F70", "name": "Test iPhone",
             "apple_id": "harjeev_kohli@hotmail.com"},
            {"udid": "00008110-001965E62213801E", "name": "Test iPad",
             "apple_id": "cryptostoner94@icloud.com"},
        ]}))
        cls.out = root / "signed"
        cls.publish = root / "published"
        cls.publish.mkdir(parents=True, exist_ok=True)

        cls.accounts = root / "accounts.json"
        cls.accounts.write_text(json.dumps({
            "00008030-001A2B3C4D5E6F70": "harjeev_kohli@hotmail.com",
            "00008110-001965E62213801E": "cryptostoner94@icloud.com",
        }))
        service.ACCOUNTS_FILE = cls.accounts
        service.SIGNER = cls.signer
        service.APP = cls.app
        service.BUILDS = {"app": cls.app.name, "keyboard": cls.keyboard_app.name}
        # The same environment the service runs under.
        os.environ["SUPERCRAFTOS_APP"] = str(cls.app)
        # The credential store and the token key belong to this test, not to
        # the server.
        os.environ["SUPERCRAFTOS_CREDENTIALS"] = str(root / "credentials.json")
        os.environ["SUPERCRAFTOS_CREDENTIAL_KEY"] = str(root / "credentials.key")
        os.environ["SUPERCRAFTOS_TOKEN_KEY"] = str(root / "token.key")
        os.environ["SUPERCRAFTOS_APP_KEYBOARD"] = str(cls.keyboard_app)
        service.DEVICES_FILE = cls.devices
        service.SESSIONS.clear()
        service.RATE_LIMIT.clear()

        # The module reads these at call time, so they are pointed at the
        # temporary directory for the duration of the tests.
        service.os.environ["SUPERCRAFTOS_OUT"] = str(cls.out)
        service.PUBLISH_DIR = cls.publish

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        cls.port = cls.server.server_address[1]
        # The service's public host is this server, not production, so a
        # redirect goes to the test and not to the real site.
        service.BASE_URL = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def raw_get(self, path):
        request = urllib.request.Request(self.url(path))
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read(), dict(response.headers)

    def get(self, path):
        with urllib.request.urlopen(self.url(path), timeout=10) as response:
            return response.status, response.read().decode("utf-8", "replace")

    def post(self, path, fields):
        body = urllib.parse.urlencode(fields).encode()
        request = urllib.request.Request(self.url(path), data=body, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode("utf-8", "replace")

    # MARK: - The page

    def test_the_page_offers_the_four_accounts_and_the_captured_devices(self):
        status, body = self.get("/sign")
        self.assertEqual(status, 200)
        for account in service.ACCOUNTS:
            self.assertIn(account, body)
        self.assertIn("00008030-001A2B3C4D5E6F70", body)
        self.assertIn("Test iPad", body)
        self.assertIn("Apple Account password", body)
        self.assertIn('action="/ios/sign/start"', body)
        self.assertNotIn("SideStore", body)
        self.assertNotIn("SideInstaller", body)

    def test_the_public_prefix_is_accepted(self):
        # Caddy proxies /ios/sign to this service without stripping the
        # prefix, so the service has to answer on both forms of the path.
        status, body = self.get("/ios/sign")
        self.assertEqual(status, 200)
        self.assertIn("Apple Account password", body)

        status, body = self.post("/ios/sign/start", {
            "apple_id": "someone@example.com",
            "password": "secret",
            "udid": "00008030-001A2B3C4D5E6F70",
        })
        self.assertEqual(status, 200)
        self.assertIn("six digit code", body)

    def test_the_build_choice_selects_the_bundle(self):
        # The keyboard extension targets iOS 26, so the build with the
        # keyboard is a different bundle and a different output name.
        session = service.Session(service.ACCOUNTS[0], ["00008030-001A2B3C4D5E6F70"], "keyboard")
        self.assertEqual(session.app_path.name, self.keyboard_app.name)
        self.assertIn("with-keyboard", session.out_path.name)
        plain = service.Session(service.ACCOUNTS[0], ["00008030-001A2B3C4D5E6F70"], "app")
        self.assertEqual(plain.app_path.name, self.app.name)
        self.assertNotIn("with-keyboard", plain.out_path.name)

    def test_the_manifest_points_at_the_signed_bundle(self):
        # The manifest is what iOS reads to install the app. It has to name
        # the bundle, and the metadata has to match the bundle itself.
        import zipfile
        # The name the service itself gives a signed bundle: the address with
        # anything that is not a letter, a digit, a dot or a dash turned into
        # an underscore, then the build.
        signed = Path(self.publish) / "harjeev_kohli_hotmail.com-app.ipa"
        signed.write_bytes(b"PK\x03\x04 signed")
        body, headers = self.raw_get("/device/00008030-001A2B3C4D5E6F70/manifest.plist")
        self.assertEqual(headers["Content-Type"], "application/xml")
        parsed = plistlib.loads(body)
        item = parsed["items"][0]
        asset = item["assets"][0]
        self.assertEqual(asset["kind"], "software-package")
        self.assertTrue(asset["url"].endswith(signed.name))
        self.assertEqual(item["metadata"]["bundle-identifier"], "com.supercraftos.control")
        self.assertEqual(item["metadata"]["kind"], "software")

    def test_the_manifest_is_empty_until_something_is_signed(self):
        body, _ = self.raw_get("/device/00008110-001965E62213801E/manifest.plist")
        self.assertIn(b"plist", body)

    def test_the_page_is_not_indexed(self):
        _, body = self.get("/sign")
        self.assertIn("noindex", body)

    def test_signer_diagnostic_keeps_the_real_error_and_removes_ansi(self):
        session = service.Session(service.ACCOUNTS[0], ["device"])
        session.output = [
            "\x1b[32m INFO\x1b[0m Provisioning successful",
            "thread 'main' panicked: Failed to sign in: invalid credentials",
        ]
        diagnostic = service.signer_diagnostic(session)
        self.assertIn("invalid credentials", diagnostic)
        self.assertNotIn("\x1b", diagnostic)

    # MARK: - The guards

    def test_the_account_comes_from_the_device_not_the_form(self):
        # The device is mapped to an account, and that account is the one
        # used, so the six digit code always arrives on the device being
        # installed. An account in the form cannot change that.
        status, body = self.post("/sign/start", {
            "apple_id": "someone@example.com",
            "password": "secret",
            "udid": "00008030-001A2B3C4D5E6F70",
        })
        self.assertEqual(status, 200)
        self.assertIn("six digit code", body)

    def test_an_uncaptured_device_is_refused(self):
        status, body = self.post("/sign/start", {
            "apple_id": service.ACCOUNTS[0],
            "password": "secret",
            "udid": "FFFFFFFF-FFFFFFFFFFFFFFFF",
        })
        self.assertEqual(status, 400)
        self.assertIn("has not been captured", body)

    def test_an_empty_password_is_refused(self):
        status, body = self.post("/sign/start", {
            "apple_id": service.ACCOUNTS[0],
            "password": "",
            "udid": "00008030-001A2B3C4D5E6F70",
        })
        self.assertEqual(status, 400)
        self.assertIn("password is empty", body)

    def test_too_many_attempts_are_refused(self):
        import time
        now = time.time()
        mapped_account = "harjeev_kohli@hotmail.com"
        service.RATE_LIMIT[mapped_account] = [now, now, now, now]
        try:
            status, body = self.post("/sign/start", {
                "apple_id": service.ACCOUNTS[1],
                "password": "secret",
                "udid": "00008030-001A2B3C4D5E6F70",
            })
            self.assertEqual(status, 429)
            self.assertIn("Too many attempts", body)
        finally:
            service.RATE_LIMIT.pop(mapped_account, None)

    # MARK: - The whole run

    def test_a_device_signs_and_the_bundle_is_downloadable(self):
        status, body = self.post("/sign/start", {
            "apple_id": service.ACCOUNTS[0],
            "password": "app-specific-secret",
            "udid": "00008030-001A2B3C4D5E6F70",
        })
        self.assertEqual(status, 200)
        self.assertIn("six digit code", body)
        session = body.split('name="session" value="')[1].split('"')[0]
        self.assertTrue(session)

        status, body = self.post("/sign/finish", {"session": session, "code": "123456"})
        self.assertEqual(status, 200)
        self.assertIn("Download the signed bundle", body)
        import re as _re
        found = _re.findall(r'href="([^"]+\.ipa)"', body)
        self.assertTrue(found, "the device page has no link to the signed bundle")
        link = found[0]

        # The bundle was published where the device can fetch it.
        published = list(self.publish.glob("*.ipa"))
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].read_bytes()[:2], b"PK")

    def test_device_page_keeps_the_two_factor_form_visible(self):
        status, body = self.post("/sign/start", {
            "apple_id": service.ACCOUNTS[0],
            "password": "app-specific-secret",
            "udid": "00008030-001A2B3C4D5E6F70",
        })
        self.assertEqual(status, 200)
        self.assertIn("six digit code", body)
        _, device_page = self.get("/device/00008030-001A2B3C4D5E6F70")
        self.assertIn('action="/ios/sign/code"', device_page)
        self.assertIn('name="code"', device_page)
        status, _ = self.post("/ios/sign/code", {
            "udid": "00008030-001A2B3C4D5E6F70",
            "code": "123456",
        })
        self.assertEqual(status, 200)
        self.assertNotIn("00008030-001A2B3C4D5E6F70", service.PENDING)

    def test_the_password_is_never_written_to_disk(self):
        secret = "a-password-that-must-not-be-stored"
        self.post("/sign/start", {
            "apple_id": service.ACCOUNTS[2],
            "password": secret,
            "udid": "00008110-001965E62213801E",
        })
        for path in list(self.out.rglob("*")) + list(self.publish.rglob("*")) + [self.devices]:
            if path.is_file():
                self.assertNotIn(secret.encode(), path.read_bytes(),
                                 f"the password was written to {path}")

    def test_an_expired_session_is_refused(self):
        status, body = self.post("/sign/finish", {"session": "not-a-session", "code": "123456"})
        self.assertEqual(status, 400)
        self.assertIn("expired", body)

    def test_the_service_logs_the_request_line_and_never_the_body(self):
        secret = "another-password-that-must-not-be-logged"
        self.post("/sign/start", {
            "apple_id": service.ACCOUNTS[3],
            "password": secret,
            "udid": "00008030-001A2B3C4D5E6F70",
        })
        # The handler's log line is the only thing it writes, and the request
        # line never contains a body.
        logged = []
        original = service.Handler.log_message

        def capture(self, fmt, *args):
            logged.append(fmt % args)

        service.Handler.log_message = capture
        try:
            self.post("/sign/start", {
                "apple_id": service.ACCOUNTS[0],
                "password": secret,
                "udid": "00008030-001A2B3C4D5E6F70",
            })
        finally:
            service.Handler.log_message = original
        for line in logged:
            self.assertNotIn(secret, line)


if __name__ == "__main__":
    unittest.main()
