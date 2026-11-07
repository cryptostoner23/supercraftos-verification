"""Tests for the iOS artifact verifier using synthetic bundles."""
from __future__ import annotations

import importlib.util
import plistlib
import shutil
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("verify_ios_artifacts", ROOT / "scripts" / "verify_ios_artifacts.py")
verifier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verifier)

APP_ID = "com.supercraftos.control"
KEYBOARD_ID = "com.supercraftos.control.keyboard"


def binary(arch: str = "arm64") -> bytes:
    """A Mach-O header slice good enough for the `file` based architecture probe."""
    magic = 0xFEEDFACF
    cputype = 0x0100000C if arch == "arm64" else 0x01000007
    header = struct.pack("<IiiIIII", magic, cputype, 3, 0, 0, 0, 0)
    return b"\xcf\xfa\xed\xfe" + header[4:] + b"\x00" * 64


def write_plist(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(payload, handle)


def build_app(root: Path, *, app_id: str = APP_ID, with_icon: bool = True,
              embed_keyboard: bool = False,
              supported_platform: str = "iPhoneSimulator") -> Path:
    app = root / "SuperCraftOS.app"
    app.mkdir(parents=True, exist_ok=True)
    write_plist(app / "Info.plist", {
        "CFBundleIdentifier": app_id,
        "CFBundleName": "SuperCraftOS",
        "CFBundleIconName": "AppIcon" if with_icon else "",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1",
        "CFBundleSupportedPlatforms": [supported_platform],
        "MinimumOSVersion": "17.0",
        "UIDeviceFamily": [1, 2],
        "UILaunchScreen": {},
        "ITSAppUsesNonExemptEncryption": False,
        "DTPlatformVersion": "27.0",
        "DTSDKName": "iphonesimulator27.0",
        "DTXcode": "2700",
    })
    (app / "SuperCraftOS").write_bytes(binary("arm64"))
    (app / "PrivacyInfo.xcprivacy").write_bytes(b"<plist/>")
    if with_icon:
        (app / "AppIcon60x60@2x.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    if embed_keyboard:
        build_keyboard(app / "PlugIns")
    return app


def build_keyboard(root: Path, *, extension_point: str = "com.apple.keyboard-service",
                   principal: str = "SuperCraftOSKeyboard.KeyboardViewController",
                   keyboard_id: str = KEYBOARD_ID, with_strings: bool = True) -> Path:
    extension = root / "SuperCraftOSKeyboard.appex"
    extension.mkdir(parents=True, exist_ok=True)
    write_plist(extension / "Info.plist", {
        "CFBundleIdentifier": keyboard_id,
        "CFBundlePackageType": "XPC!",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1",
        "CFBundleSupportedPlatforms": ["iPhoneSimulator"],
        "MinimumOSVersion": "26.0",
        "DTPlatformVersion": "27.0",
        "DTSDKName": "iphonesimulator27.0",
        "DTXcode": "2700",
        "NSExtension": {
            "NSExtensionAttributes": {
                "IsASCIICapable": True,
                "PrefersRightToLeft": False,
                "PrimaryLanguage": "en-US",
                "RequestsOpenAccess": True,
            },
            "NSExtensionPointIdentifier": extension_point,
            "NSExtensionPrincipalClass": principal,
        },
    })
    (extension / "PrivacyInfo.xcprivacy").write_bytes(b"<plist/>")
    payload = binary("arm64")
    if with_strings:
        vocabulary = " ".join(verifier.REQUIRED_STRINGS + verifier.REQUIRED_RUNTIME_STRINGS)
        payload += vocabulary.encode("utf-8")
    (extension / "SuperCraftOSKeyboard").write_bytes(payload)
    return extension


class VerifyIOSArtifactsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp(prefix="supercraftos-artifact-test-"))
        self.addCleanup(shutil.rmtree, self.directory, True)

    def test_complete_app_passes_every_check(self) -> None:
        app = build_app(self.directory)
        result = verifier.verify_app(app)
        self.assertTrue(result["ok"], result["checks"])
        self.assertTrue(all(check["ok"] for check in result["checks"]))

    def test_physical_device_app_is_an_ios_app(self) -> None:
        app = build_app(self.directory, supported_platform="iPhoneOS")
        result = verifier.verify_app(app)
        failed = [check["check"] for check in result["checks"] if not check["ok"]]
        self.assertNotIn("app targets iOS", failed)

    def test_app_must_ship_standalone(self) -> None:
        app = build_app(self.directory, embed_keyboard=True)
        result = verifier.verify_app(app)
        self.assertFalse(result["ok"])
        failed = [check["check"] for check in result["checks"] if not check["ok"]]
        self.assertIn("app ships standalone with no embedded app extension", failed)

    def test_missing_app_icon_fails(self) -> None:
        app = build_app(self.directory, with_icon=False)
        result = verifier.verify_app(app)
        failed = [check["check"] for check in result["checks"] if not check["ok"]]
        self.assertIn("app declares an app icon", failed)
        self.assertIn("app icon is compiled into the bundle", failed)

    def test_missing_privacy_manifest_fails(self) -> None:
        app = build_app(self.directory)
        (app / "PrivacyInfo.xcprivacy").unlink()
        result = verifier.verify_app(app)
        failed = [check["check"] for check in result["checks"] if not check["ok"]]
        self.assertIn("app ships a privacy manifest", failed)

    def test_wrong_app_bundle_identifier_fails(self) -> None:
        app = build_app(self.directory, app_id="com.example.wrong")
        result = verifier.verify_app(app)
        failed = [check["check"] for check in result["checks"] if not check["ok"]]
        self.assertIn("app bundle identifier", failed)

    def test_complete_keyboard_passes_every_check(self) -> None:
        extension = build_keyboard(self.directory)
        result = verifier.verify_keyboard(extension)
        self.assertTrue(result["ok"], result["checks"])
        self.assertTrue(all(check["ok"] for check in result["checks"]))

    def test_wrong_extension_point_fails(self) -> None:
        extension = build_keyboard(self.directory, extension_point="com.apple.share-services")
        result = verifier.verify_keyboard(extension)
        failed = [check["check"] for check in result["checks"] if not check["ok"]]
        self.assertIn("keyboard extension point", failed)

    def test_wrong_principal_class_fails(self) -> None:
        extension = build_keyboard(self.directory, principal="SomeOtherModule.OtherController")
        result = verifier.verify_keyboard(extension)
        failed = [check["check"] for check in result["checks"] if not check["ok"]]
        self.assertIn("keyboard principal class", failed)

    def test_wrong_keyboard_bundle_identifier_fails(self) -> None:
        extension = build_keyboard(self.directory, keyboard_id="com.example.wrong.keyboard")
        result = verifier.verify_keyboard(extension)
        failed = [check["check"] for check in result["checks"] if not check["ok"]]
        self.assertIn("keyboard bundle identifier", failed)

    def test_missing_keyboard_strings_fail(self) -> None:
        extension = build_keyboard(self.directory, with_strings=False)
        result = verifier.verify_keyboard(extension)
        failed = [check["check"] for check in result["checks"] if not check["ok"]]
        self.assertIn("keyboard binary carries the specified vocabulary and runtime contract", failed)

    def test_keyboard_strings_are_checked_against_the_code_binary(self) -> None:
        extension = build_keyboard(self.directory)
        payload = " ".join(verifier.REQUIRED_STRINGS + verifier.REQUIRED_RUNTIME_STRINGS).encode("utf-8")
        (extension / "SuperCraftOSKeyboard.debug.dylib").write_bytes(payload)
        result = verifier.verify_keyboard(extension)
        failed = [check["check"] for check in result["checks"] if not check["ok"]]
        self.assertNotIn("keyboard binary carries the specified vocabulary and runtime contract", failed)

    def test_missing_keyboard_privacy_manifest_fails(self) -> None:
        extension = build_keyboard(self.directory)
        (extension / "PrivacyInfo.xcprivacy").unlink()
        result = verifier.verify_keyboard(extension)
        failed = [check["check"] for check in result["checks"] if not check["ok"]]
        self.assertIn("keyboard ships a privacy manifest", failed)

    def test_archive_is_extracted_and_verified(self) -> None:
        app = build_app(self.directory)
        archive = self.directory / "SuperCraftOS.app.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            for path in sorted(app.rglob("*")):
                if path.is_file():
                    output.write(path, str(Path("SuperCraftOS.app") / path.relative_to(app)))
        bundle = verifier.locate(archive)
        try:
            result = verifier.verify_app(bundle)
            self.assertTrue(result["ok"], result["checks"])
        finally:
            shutil.rmtree(bundle.parent, ignore_errors=True)

    def test_keyboard_archive_is_routed_to_the_keyboard_verifier(self) -> None:
        extension = build_keyboard(self.directory)
        archive = self.directory / "SuperCraftOSKeyboard.appex.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            for path in sorted(extension.rglob("*")):
                if path.is_file():
                    output.write(path, str(Path("SuperCraftOSKeyboard.appex") / path.relative_to(extension)))
        bundle = verifier.locate(archive)
        try:
            self.assertEqual(bundle.suffix, ".appex")
            result = verifier.verify_keyboard(bundle)
            self.assertTrue(result["ok"], result["checks"])
        finally:
            shutil.rmtree(bundle.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
