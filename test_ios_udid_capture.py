"""Tests for the UDID capture profile and the service that receives the UDIDs."""
from __future__ import annotations

import importlib.util
import json
import plistlib
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


udid_capture = _load("udid_capture", ROOT / "scripts" / "udid_capture.py")
service = _load("ios_udid_service", ROOT / "scripts" / "ios_udid_service.py")

LEGACY_UDID = "b59769e6c28b73b1195009d4b21c0123456789ab"
MODERN_UDID = "00008110-001965E62213801E"


class ProfileTests(unittest.TestCase):
    def test_profile_carries_both_payloads(self):
        profile = udid_capture.build_profile()
        types = [payload["PayloadType"] for payload in profile["PayloadContent"]]
        self.assertEqual(types, ["Profile Service", "com.apple.webClip.managed"])
        self.assertEqual(profile["PayloadType"], "Configuration")

    def test_profile_service_payload_shape(self):
        payload = udid_capture.profile_service_payload()
        # iOS wants a dict here, not an array, and the literal payload type.
        self.assertIsInstance(payload["PayloadContent"], dict)
        self.assertEqual(payload["PayloadContent"]["URL"],
                         "https://agent.commetai.ca/ios/udid")
        self.assertIn("UDID", payload["PayloadContent"]["DeviceAttributes"])

    def test_web_clip_url_carries_the_udid_placeholder(self):
        payload = udid_capture.web_clip_payload()
        self.assertEqual(payload["PayloadType"], "com.apple.webClip.managed")
        self.assertEqual(
            payload["PayloadURL"],
            "https://agent.commetai.ca/ios/udid?src=webclip&udid=$(UDID)")
        self.assertIn("Label", payload)
        self.assertIn("Icon", payload)

    def test_web_clip_icon_is_a_png(self):
        icon = udid_capture.png_icon()
        self.assertTrue(icon.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn(b"IHDR", icon[:32])
        self.assertTrue(icon.endswith(b"IEND\xaeB`\x82"))

    def test_profile_renders_as_a_plist(self):
        raw = udid_capture.profile_bytes()
        parsed = plistlib.loads(raw)
        self.assertEqual(parsed["PayloadType"], "Configuration")
        self.assertEqual(len(parsed["PayloadContent"]), 2)

    def test_variants(self):
        self.assertEqual(len(udid_capture.build_profile(variant="service")["PayloadContent"]), 1)
        self.assertEqual(len(udid_capture.build_profile(variant="webclip")["PayloadContent"]), 1)
        with self.assertRaises(ValueError):
            udid_capture.build_profile(variant="nope")


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Path(self.tmp.name) / "ios-devices.json"
        self._old_store = service.STORE
        self._old_base = service.BASE_URL
        service.STORE = self.store
        service.BASE_URL = "https://agent.commetai.ca"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        # The redirects after a capture point at the public base url, so point
        # it at the test server instead.
        service.BASE_URL = self.base
        self._old_log = service.Handler.log_message
        service.Handler.log_message = lambda *args, **kwargs: None

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        service.Handler.log_message = self._old_log
        service.STORE = self._old_store
        service.BASE_URL = self._old_base
        self.tmp.cleanup()

    # -- helpers ---------------------------------------------------------
    def get(self, path: str):
        with urllib.request.urlopen(self.base + path) as response:
            return response.status, response.read(), response.headers

    def post(self, path: str, body: bytes, content_type: str):
        request = urllib.request.Request(self.base + path, data=body,
                                         method="POST")
        request.add_header("Content-Type", content_type)
        with urllib.request.urlopen(request) as response:
            return response.status, response.read(), response.headers

    def devices(self) -> list:
        return json.loads(self.store.read_text())["devices"]

    # -- tests -----------------------------------------------------------
    def test_page_renders_without_a_device(self):
        status, body, headers = self.get("/udid")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"VPN &amp; Device Management", body)
        self.assertIn(b"Nothing captured yet", body)

    def test_ios_prefix_is_accepted(self):
        status, _, _ = self.get("/ios/udid")
        self.assertEqual(status, 200)

    def test_get_with_a_udid_records_it_and_shows_it(self):
        status, body, _ = self.get(f"/udid?udid={LEGACY_UDID}&name=Test+iPhone")
        self.assertEqual(status, 200)
        self.assertIn(LEGACY_UDID.encode(), body)
        devices = self.devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["udid"], LEGACY_UDID)
        self.assertEqual(devices[0]["name"], "Test iPhone")

    def test_modern_udid_format_is_accepted(self):
        self.get(f"/udid?udid={MODERN_UDID}")
        self.assertEqual(self.devices()[0]["udid"], MODERN_UDID)

    def test_invalid_udid_is_rejected(self):
        status, body, _ = self.get("/udid?udid=not-a-udid")
        self.assertEqual(status, 200)
        self.assertIn(b"does not look like a UDID", body)
        self.assertFalse(self.store.exists())

    def test_profile_service_post_records_the_device(self):
        payload = plistlib.dumps({
            "UDID": LEGACY_UDID,
            "DEVICE_NAME": "Test iPad",
            "PRODUCT": "iPad14,1",
            "VERSION": "26.0",
            "SERIAL": "ABC123",
        })
        status, body, headers = self.post("/udid", payload, "application/pkcs7-signature")
        self.assertEqual(status, 200)  # urllib follows the redirect
        devices = self.devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["udid"], LEGACY_UDID)
        self.assertEqual(devices[0]["name"], "Test iPad")
        self.assertEqual(devices[0]["product"], "iPad14,1")
        self.assertEqual(devices[0]["source"], "profile-service")

    def test_profile_service_post_inside_a_cms_blob_is_parsed(self):
        payload = plistlib.dumps({"UDID": LEGACY_UDID, "PRODUCT": "iPhone17,1"})
        blob = b"\x30\x82\x0a\x00" + b"\x00" * 64 + payload + b"\x00" * 32
        self.post("/udid", blob, "application/pkcs7-signature")
        devices = self.devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["udid"], LEGACY_UDID)

    def test_profile_service_post_with_nested_keys_is_parsed(self):
        payload = plistlib.dumps({"Payload": {"UDID": LEGACY_UDID, "SERIAL": "XYZ"}})
        self.post("/udid", payload, "application/pkcs7-signature")
        self.assertEqual(self.devices()[0]["udid"], LEGACY_UDID)

    def test_manual_form_post_records_the_device(self):
        body = f"udid={LEGACY_UDID}&name=Typed+by+hand".encode()
        self.post("/udid", body, "application/x-www-form-urlencoded")
        devices = self.devices()
        self.assertEqual(devices[0]["udid"], LEGACY_UDID)
        self.assertEqual(devices[0]["name"], "Typed by hand")
        self.assertEqual(devices[0]["source"], "manual")

    def test_manual_form_post_rejects_a_bad_udid(self):
        self.post("/udid", b"udid=nope", "application/x-www-form-urlencoded")
        self.assertFalse(self.store.exists())

    def test_the_profile_is_withdrawn(self):
        # The configuration profile has been withdrawn. It was never doing
        # anything but reporting the identifier, but a profile still asks the
        # operating system to change its state, and the one command installer
        # does not need one. The endpoint now answers with an explanation.
        for route in ("/udid.mobileconfig", "/udid.webclip.mobileconfig", "/udid.service.mobileconfig"):
            try:
                status, body, headers = self.get(route)
                self.fail(f"{route} still serves a profile")
            except urllib.error.HTTPError as error:
                self.assertEqual(error.code, 404, route)
                self.assertIn("withdrawn", error.read().decode("utf-8", "replace"))

    def test_the_page_offers_the_installer_and_no_profile(self):
        status, body, _ = self.get("/udid")
        self.assertEqual(status, 200)
        text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
        self.assertIn("supercraftos-install.sh", text)
        self.assertNotIn(".mobileconfig", text)

    def test_health(self):
        status, body, _ = self.get("/health")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])

    def test_unknown_route_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/nope")
        self.assertEqual(caught.exception.code, 404)

    def test_other_devices_are_masked_on_the_page(self):
        self.get(f"/udid?udid={LEGACY_UDID}")
        self.get(f"/udid?udid={MODERN_UDID}")
        _, body, _ = self.get(f"/udid?udid={MODERN_UDID}")
        self.assertIn(MODERN_UDID.encode(), body)
        self.assertNotIn(LEGACY_UDID.encode(), body)


if __name__ == "__main__":
    unittest.main()
