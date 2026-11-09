#!/usr/bin/env python3
"""Verify a built SuperCraftOS iOS app bundle or its custom keyboard extension.

Usage:
    python3 scripts/verify_ios_artifacts.py path/to/SuperCraftOS.app
    python3 scripts/verify_ios_artifacts.py path/to/SuperCraftOS.app.zip
    python3 scripts/verify_ios_artifacts.py path/to/SuperCraftOSKeyboard.appex.zip
"""
from __future__ import annotations

import json
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

EXPECTED_APP_ID = "com.supercraftos.control"
EXPECTED_KEYBOARD_ID = "com.supercraftos.control.keyboard"
EXPECTED_EXTENSION_POINT = "com.apple.keyboard-service"
EXPECTED_PRINCIPAL_CLASS_SUFFIX = "KeyboardViewController"
# The app supports iOS 17 and later. The keyboard extension targets iOS 26,
# the floor for Apple's on-device model, which it uses as the offline fallback.
MINIMUM_IOS = "17.0"
KEYBOARD_MINIMUM_IOS = "26.0"

# The exact vocabulary of the keyboard specification. These strings must be
# present in the compiled keyboard binary for the delivered bundle to match the
# specified UI.
REQUIRED_STRINGS = (
    "Recents", "AI Actions", "Voice / Audio", "Lighting / Execution",
    "Presets / Sliders", "GIFs", "Search",
    "Ask AI", "Ask About Webpage", "Change Tone to Casual", "Rephrase as",
    "Rephrase as Tweet", "Explain Code by Step", "Fix Spelling and Grammar",
    "Improve Writing", "Translate", "Maps", "YouTube", "Google",
    "Shift + Control + C", "Cmd + Shift + P", "Cmd + Option + V", "Cmd + S", "Cmd + N",
    "Copy Code", "Command Palette", "Paste Plain", "Save Document", "New Window",
    "space",
)

# The runtime contract of the agent backed keyboard.
REQUIRED_RUNTIME_STRINGS = (
    "X-SuperCraftOS-Token", "/api/workflows", "group.com.supercraftos.control",
)


def binary_bytes(bundle: Path) -> bytes:
    """The raw bytes of every binary that holds the executable code of a bundle.

    An Xcode Debug build puts the implementation in a `<name>.debug.dylib` and
    leaves a small launcher in the main executable, so both are inspected.
    """
    found = []
    main = bundle / bundle.stem
    if main.exists():
        found.append(main)
    for dylib in sorted(bundle.glob("*.debug.dylib")):
        found.append(dylib)
    blob = b""
    for binary in found:
        try:
            blob += binary.read_bytes()
        except OSError:
            continue
    return blob


def load_plist(path: Path) -> dict:
    with path.open("rb") as handle:
        return plistlib.load(handle)


def architectures(binary: Path) -> list[str]:
    if not binary.exists():
        return []
    try:
        output = subprocess.run(["file", "-b", str(binary)], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    found = []
    for name in ("arm64", "x86_64", "arm64e"):
        if name in output:
            found.append(name)
    return found


def verify_app(app: Path) -> dict:
    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    app_plist_path = app / "Info.plist"
    record("app Info.plist present", app_plist_path.exists(), str(app_plist_path))
    if not app_plist_path.exists():
        return {"ok": False, "checks": checks}
    app_plist = load_plist(app_plist_path)

    record("app bundle identifier", app_plist.get("CFBundleIdentifier") == EXPECTED_APP_ID,
           str(app_plist.get("CFBundleIdentifier")))
    display_name = app_plist.get("CFBundleDisplayName") or app_plist.get("CFBundleName")
    record("app display name", display_name == "SuperCraftOS", str(display_name))
    record("app version", bool(app_plist.get("CFBundleShortVersionString")),
           f"{app_plist.get('CFBundleShortVersionString')} ({app_plist.get('CFBundleVersion')})")
    minimum = app_plist.get("MinimumOSVersion", "")
    record("app minimum iOS", minimum == MINIMUM_IOS, str(minimum))
    supported = app_plist.get("CFBundleSupportedPlatforms", [])
    record("app targets iOS",
           any(platform in supported for platform in ("iPhoneOS", "iPhoneSimulator")),
           str(supported))
    record("app device family", app_plist.get("UIDeviceFamily") == [1, 2],
           str(app_plist.get("UIDeviceFamily")))
    record("app built with the iOS 27 SDK", str(app_plist.get("DTPlatformVersion", "")).startswith("27"),
           f"Xcode {app_plist.get('DTXcode')} / {app_plist.get('DTSDKName')}")
    record("app binary architectures", bool(architectures(app / "SuperCraftOS")),
           ",".join(architectures(app / "SuperCraftOS")) or "unknown")

    # Installability requirements.
    record("app declares an app icon", app_plist.get("CFBundleIconName") == "AppIcon"
           or bool(app_plist.get("CFBundleIcons")),
           str(app_plist.get("CFBundleIconName") or app_plist.get("CFBundleIcons")))
    compiled_icons = sorted(p.name for p in app.glob("AppIcon*.png"))
    record("app icon is compiled into the bundle", bool(compiled_icons),
           ", ".join(compiled_icons) if compiled_icons else "no AppIcon*.png in the bundle root")
    record("app declares a launch screen", "UILaunchScreen" in app_plist,
           str(app_plist.get("UILaunchScreen", "missing")))
    record("app declares export compliance", app_plist.get("ITSAppUsesNonExemptEncryption") is False,
           str(app_plist.get("ITSAppUsesNonExemptEncryption")))
    record("app ships a privacy manifest", (app / "PrivacyInfo.xcprivacy").exists(),
           "PrivacyInfo.xcprivacy")

    # The app ships standalone: no app extensions, so it needs a single App ID
    # and no App Group on its provisioning profile.
    plugins = app / "PlugIns"
    embedded = sorted(p.name for p in plugins.glob("*.appex")) if plugins.is_dir() else []
    record("app ships standalone with no embedded app extension", not embedded,
           ", ".join(embedded) if embedded else "no PlugIns directory")

    return {"ok": all(item["ok"] for item in checks), "checks": checks}


def verify_keyboard(extension: Path) -> dict:
    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    extension_plist_path = extension / "Info.plist"
    record("keyboard Info.plist present", extension_plist_path.exists(), str(extension_plist_path))
    if not extension_plist_path.exists():
        return {"ok": False, "checks": checks}
    extension_plist = load_plist(extension_plist_path)

    record("keyboard bundle identifier", extension_plist.get("CFBundleIdentifier") == EXPECTED_KEYBOARD_ID,
           str(extension_plist.get("CFBundleIdentifier")))
    extension_point = extension_plist.get("NSExtension", {}).get("NSExtensionPointIdentifier")
    record("keyboard extension point", extension_point == EXPECTED_EXTENSION_POINT, str(extension_point))
    principal = str(extension_plist.get("NSExtension", {}).get("NSExtensionPrincipalClass", ""))
    record("keyboard principal class", principal.endswith(EXPECTED_PRINCIPAL_CLASS_SUFFIX), principal)
    attributes = extension_plist.get("NSExtension", {}).get("NSExtensionAttributes", {})
    record("keyboard requests open access", attributes.get("RequestsOpenAccess") is True,
           str(attributes.get("RequestsOpenAccess")))
    record("keyboard package type", extension_plist.get("CFBundlePackageType") == "XPC!",
           str(extension_plist.get("CFBundlePackageType")))
    record("keyboard minimum iOS", extension_plist.get("MinimumOSVersion") == KEYBOARD_MINIMUM_IOS,
           str(extension_plist.get("MinimumOSVersion")))
    record("keyboard built with the iOS 27 SDK",
           str(extension_plist.get("DTPlatformVersion", "")).startswith("27"),
           f"Xcode {extension_plist.get('DTXcode')} / {extension_plist.get('DTSDKName')}")
    record("keyboard ships a privacy manifest", (extension / "PrivacyInfo.xcprivacy").exists(),
           "PrivacyInfo.xcprivacy")
    record("keyboard binary architectures",
           bool(architectures(extension / "SuperCraftOSKeyboard")),
           ",".join(architectures(extension / "SuperCraftOSKeyboard")) or "unknown")

    # The specified vocabulary and the runtime contract must be compiled in.
    blob = binary_bytes(extension)
    if not blob:
        record("keyboard binary is readable", False, "no code binary could be read")
    else:
        required = REQUIRED_STRINGS + REQUIRED_RUNTIME_STRINGS
        missing = [value for value in required if value.encode("utf-8") not in blob]
        record("keyboard binary carries the specified vocabulary and runtime contract",
               not missing,
               "all %d strings present" % len(required)
               if not missing else "missing: " + ", ".join(missing))

    return {"ok": all(item["ok"] for item in checks), "checks": checks}


def locate(path: Path) -> Path:
    """Return the bundle directory for an archive or a directory on disk."""
    if path.is_dir():
        return path
    if not (path.is_file() and zipfile.is_zipfile(path)):
        raise FileNotFoundError(str(path))
    temporary = Path(tempfile.mkdtemp(prefix="supercraftos-verify-"))
    with zipfile.ZipFile(path) as archive:
        archive.extractall(temporary)
    bundles = sorted(temporary.rglob("*.app")) + sorted(temporary.rglob("*.appex"))
    if not bundles:
        shutil.rmtree(temporary, ignore_errors=True)
        raise FileNotFoundError(f"no .app or .appex bundle inside {path}")
    # The extraction directory is returned so the caller can clean it up.
    extracted = bundles[0]
    shutil.move(str(extracted), str(path.with_suffix("") / extracted.name))
    shutil.rmtree(temporary, ignore_errors=True)
    return path.with_suffix("") / extracted.name


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    target = Path(sys.argv[1]).resolve()
    try:
        bundle = locate(target)
    except FileNotFoundError as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2))
        return 1
    try:
        if bundle.suffix == ".appex":
            result = verify_keyboard(bundle)
        else:
            result = verify_app(bundle)
        result["bundle"] = bundle.name
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    finally:
        if bundle.parent != target.parent:
            shutil.rmtree(bundle.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
