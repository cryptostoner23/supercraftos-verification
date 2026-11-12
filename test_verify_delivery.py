"""Offline regressions for delivery evidence; fixture metadata is not signing."""
import importlib.util
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

from test_supercraftos_installer import make_ipa, UDID

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("verify_delivery", ROOT / "scripts/verify_delivery.py")
delivery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(delivery)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "data").mkdir()
        self.accounts = self.root / "data/ios-device-accounts.json"
        self.accounts.write_text(json.dumps({UDID: "fixture@example.invalid"}))
        self.ipa = make_ipa(self.root / "fixture.ipa", signed=True)
        self.manifest = {"items": [{
            "assets": [{"kind": "display-image", "url": "https://example.invalid/icon.png"},
                       {"kind": "software-package",
                        "url": "https://agent.commetai.ca/ios/signed/fixture.ipa"}],
            "metadata": {"bundle-identifier": "com.supercraftos.control",
                         "bundle-version": "1"}}]}
        self.paths = []
        self.addCleanup(patch.stopall)
        patch.object(delivery, "ROOT", self.root).start()
        patch.object(delivery, "BASE", "https://agent.commetai.ca").start()
        patch.object(delivery, "PASSED", []).start()
        patch.object(delivery, "FAILED", []).start()
        patch.object(delivery, "get", side_effect=self.get).start()

    def get(self, path, **kwargs):
        self.paths.append(path)
        if path.endswith("manifest.plist"):
            return 200, plistlib.dumps(self.manifest), "application/xml"
        if path == "/ios/signed/fixture.ipa":
            return 200, self.ipa.read_bytes(), "application/octet-stream"
        raise AssertionError("unexpected request: " + path)

    def test_profile_ipa_does_not_read_a_closed_zip(self):
        delivery.check_manifest()
        self.assertEqual(delivery.FAILED, [])
        self.assertTrue(any("unexpired" in value for value in delivery.PASSED))
        self.assertTrue(any("not cryptographic proof" in value for value in delivery.PASSED))

    def test_extension_profile_is_read_while_zip_is_open(self):
        make_ipa(self.ipa, signed=True, extension=True)
        delivery.check_manifest()
        self.assertEqual(delivery.FAILED, [])
        self.assertEqual(sum("is unexpired" in value for value in delivery.PASSED), 2)

    def test_empty_manifest_is_not_readiness(self):
        self.manifest = {"items": []}
        delivery.check_manifest()
        self.assertTrue(delivery.FAILED)
        self.assertEqual(len(self.paths), 1, "must not attempt an absent IPA")

    def test_empty_or_missing_device_records_are_not_verified_installation(self):
        self.accounts.write_text("{}")
        delivery.check_manifest()
        self.assertTrue(delivery.FAILED)
        self.assertEqual(self.paths, [])
        delivery.FAILED.clear()
        self.accounts.unlink()
        delivery.check_manifest()
        self.assertTrue(delivery.FAILED)

    def test_expired_profile_fails(self):
        make_ipa(self.ipa, signed=True, expired=True)
        delivery.check_manifest()
        self.assertTrue(any("is unexpired" in value for value in delivery.FAILED))

    def test_wrong_device_profile_fails(self):
        make_ipa(self.ipa, signed=True, udid="other-device")
        delivery.check_manifest()
        self.assertTrue(any("covers device" in value for value in delivery.FAILED))

    def test_unsigned_bundle_and_extension_fail(self):
        for signed, extension in [(False, False), (True, True)]:
            with self.subTest(extension=extension):
                make_ipa(self.ipa, signed=signed, extension=extension, extension_signed=False)
                delivery.FAILED.clear()
                delivery.check_manifest()
                self.assertTrue(any("provisioning profile" in value for value in delivery.FAILED))

    def test_three_part_minimum_is_reported_without_float_conversion(self):
        make_ipa(self.ipa, signed=True, minimum="26.0.1")
        delivery.check_manifest()
        self.assertEqual(delivery.FAILED, [])
        self.assertTrue(any("minimum iOS 26.0.1" in value for value in delivery.PASSED))
        self.assertFalse(any("runs on iOS 17" in value for value in delivery.PASSED))

    def test_manifest_version_must_match_bundle(self):
        make_ipa(self.ipa, signed=True, bundle_version="2")
        delivery.check_manifest()
        self.assertTrue(any("manifest version" in value for value in delivery.FAILED))

    def test_foreign_or_escaping_package_url_is_never_fetched(self):
        for url in ["https://agent.commetai.ca.attacker.invalid/ios/signed/fixture.ipa",
                    "https://agent.commetai.ca/ios/signed/%2e%2e/fixture.ipa",
                    "https://agent.commetai.ca/ios/signed/fixture.ipa?other=1",
                    "http://agent.commetai.ca/ios/signed/fixture.ipa"]:
            with self.subTest(url=url):
                self.manifest["items"][0]["assets"][1]["url"] = url
                self.paths.clear()
                delivery.FAILED.clear()
                delivery.check_manifest()
                self.assertEqual(len(self.paths), 1)
                self.assertTrue(delivery.FAILED)

    def test_missing_software_package_does_not_use_icon(self):
        self.manifest["items"][0]["assets"].pop()
        delivery.check_manifest()
        self.assertEqual(len(self.paths), 1)
        self.assertTrue(delivery.FAILED)

    def test_malformed_manifest_is_a_failure_instead_of_exception(self):
        for value in [{"items": ["bad"]}, {"items": [{}]}, ["not-a-dictionary"]]:
            with self.subTest(value=value):
                self.manifest = value
                delivery.FAILED.clear()
                delivery.check_manifest()
                self.assertTrue(delivery.FAILED)

    def test_malformed_package_is_a_failure_instead_of_exception(self):
        self.ipa.write_bytes(b"PK fake-signer-success")
        delivery.check_manifest()
        self.assertTrue(delivery.FAILED)


if __name__ == "__main__":
    unittest.main()
