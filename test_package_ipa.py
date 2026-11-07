"""Tests for the ipa packager."""
from __future__ import annotations

import importlib.util
import plistlib
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("package_ipa", ROOT / "scripts" / "package_ipa.py")
packager = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(packager)


def build_app(root: Path, *, with_extension: bool = False) -> Path:
    app = root / "SuperCraftOS.app"
    app.mkdir(parents=True, exist_ok=True)
    with (app / "Info.plist").open("wb") as handle:
        plistlib.dump({"CFBundleIdentifier": "com.supercraftos.control"}, handle)
    (app / "SuperCraftOS").write_bytes(b"\xcf\xfa\xed\xfe" + b"\x00" * 32)
    if with_extension:
        extension = app / "PlugIns" / "SuperCraftOSKeyboard.appex"
        extension.mkdir(parents=True)
        with (extension / "Info.plist").open("wb") as handle:
            plistlib.dump({"CFBundleIdentifier": "com.supercraftos.control.keyboard"}, handle)
        (extension / "SuperCraftOSKeyboard").write_bytes(b"\xcf\xfa\xed\xfe" + b"\x00" * 32)
    return app


class PackageIpaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp(prefix="supercraftos-ipa-test-"))
        self.addCleanup(shutil.rmtree, self.directory, True)

    def test_ipa_uses_the_payload_layout(self) -> None:
        app = build_app(self.directory)
        output = self.directory / "SuperCraftOS.ipa"
        result = packager.package(app, output)
        self.assertTrue(output.exists())
        self.assertEqual(result["payload"], "Payload/SuperCraftOS.app/")
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
        self.assertIn("Payload/SuperCraftOS.app/Info.plist", names)
        self.assertIn("Payload/SuperCraftOS.app/SuperCraftOS", names)

    def test_ipa_carries_embedded_extensions(self) -> None:
        app = build_app(self.directory, with_extension=True)
        output = self.directory / "SuperCraftOS.ipa"
        result = packager.package(app, output)
        self.assertEqual(result["embedded_extensions"], ["SuperCraftOSKeyboard.appex"])
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
        self.assertIn("Payload/SuperCraftOS.app/PlugIns/SuperCraftOSKeyboard.appex/Info.plist", names)

    def test_result_reports_a_digest(self) -> None:
        app = build_app(self.directory)
        output = self.directory / "SuperCraftOS.ipa"
        result = packager.package(app, output)
        self.assertEqual(len(result["sha256"]), 64)
        self.assertGreater(result["bytes"], 0)

    def test_a_non_bundle_is_rejected(self) -> None:
        plain = self.directory / "not-an-app"
        plain.mkdir()
        with self.assertRaises(SystemExit):
            packager.package(plain, self.directory / "x.ipa")

    def test_no_staging_directory_is_left_behind(self) -> None:
        app = build_app(self.directory)
        output = self.directory / "SuperCraftOS.ipa"
        packager.package(app, output)
        leftovers = [p.name for p in self.directory.iterdir() if p.name.endswith("-staging")]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
