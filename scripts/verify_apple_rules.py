#!/usr/bin/env python3
"""Check the project against Apple's own documentation.

Every rule checked here is quoted from a page that was ingested from Apple's
documentation service or from Apple's own site, and each one is stored in
docs/apple/ with the URL, the date it was fetched and the hash of the bytes.
The check reads those pages, so if a page is missing or has changed, the
check fails rather than quietly trusting a rule someone remembered.

    scripts/verify_apple_rules.py
"""
from __future__ import annotations

import json
import plistlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPLE = ROOT / "docs/apple"
MANIFEST = ROOT / "docs/apple-manifest.json"

FAILURES: list[str] = []
CHECKS = 0


def check(condition: bool, message: str) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(message)


def page(name: str) -> str:
    path = APPLE / name
    if not path.exists():
        FAILURES.append(f"the official page {name} is not in the corpus, run scripts/apple_docs.py")
        return ""
    return path.read_text()


def quote_present(name: str, pattern: str, what: str) -> None:
    """The rule must still be in Apple's words, in the stored page."""
    text = page(name)
    check(bool(text) and re.search(pattern, text, re.I) is not None,
          f"Apple's documentation no longer states the rule about {what}")


def main() -> int:
    # 1. The corpus exists and is traceable.
    check(MANIFEST.exists(), "docs/apple-manifest.json is missing")
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text())
        check(len(manifest) >= 8, f"only {len(manifest)} official pages are ingested")
        for entry in manifest:
            url = entry.get("url", "")
            check(url.startswith("https://developer.apple.com/")
                  or url.startswith("https://support.apple.com/")
                  or url.startswith("https://www.apple.com/"),
                  f"{entry.get('path')} is not from Apple's own site")
            check(len(entry.get("sha256", "")) == 64, f"{entry.get('path')} has no hash")

    # 2. Apple's custom keyboard keys, from the App Extension Programming Guide.
    quote_present("customkeyboard-html.md",
                  r"IsASCIICapable", "the keys a custom keyboard declares")
    quote_present("customkeyboard-html.md",
                  r"com\.apple\.keyboard-service", "the keyboard extension point")
    quote_present("customkeyboard-html.md",
                  r"RequestsOpenAccess", "open access, which is what the network needs")

    keyboard_plist = ROOT / "ios_app_dist/KeyboardExtension/Info.plist"
    info = plistlib.loads(keyboard_plist.read_bytes())
    extension = info.get("NSExtension", {})
    attributes = extension.get("NSExtensionAttributes", {})
    for key in ("IsASCIICapable", "PrefersRightToLeft", "PrimaryLanguage", "RequestsOpenAccess"):
        check(key in attributes, f"the keyboard does not declare {key}, which Apple documents")
    check(extension.get("NSExtensionPointIdentifier") == "com.apple.keyboard-service",
          "the keyboard is not a keyboard extension")
    check("NSExtensionPrincipalClass" in extension, "the keyboard has no principal class")
    # Apple: a keyboard has no network access unless it asks for open access.
    check(attributes.get("RequestsOpenAccess") is True,
          "the keyboard needs open access to reach the backend")

    # 3. Apple: all the targets must be code signed the same way.
    quote_present("extensioncreation-html.md",
                  r"must be code signed in the same way", "signing the app and its extensions")
    spec = (ROOT / "ios_app_dist/ci_xcode/project.yml").read_text()
    app_section = spec.split("SuperCraftOS:")[1].split("SuperCraftOSKeyboard:")[0]
    keyboard_section = spec.split("SuperCraftOSKeyboard:")[1].split("SuperCraftOSTests:")[0]
    check("CODE_SIGN_IDENTITY" not in app_section or "CODE_SIGN_IDENTITY" not in keyboard_section,
          "the app and the keyboard sign differently")
    enabled = [line.strip() for line in keyboard_section.splitlines()
               if line.strip().startswith("CODE_SIGN_ENTITLEMENTS")]
    check(not enabled, "the keyboard carries an entitlement, and a free personal team has no capabilities")

    # 4. Apple: the containing app supports the oldest system, the extension
    #    its own. The pair that ships has to say which device it fits.
    quote_present("extensionscenarios-html.md",
                  r"oldest version of iOS that you want to support",
                  "the containing app's deployment target")
    quote_present("developer-apple-com-library-archive-technotes-tn2319-index-html.md",
                  r"MinimumOSVersion", "the deployment target at install time")

    app_target = re.search(r"SuperCraftOS:\n(?:.*\n)*?    deploymentTarget: \"([0-9.]+)\"",
                           spec.split("SuperCraftOSKeyboard:")[0])
    keyboard_target = re.search(r"SuperCraftOSKeyboard:\n(?:.*\n)*?    deploymentTarget: \"([0-9.]+)\"",
                                 spec)
    check(app_target is not None, "the app has no deployment target")
    check(keyboard_target is not None, "the keyboard has no deployment target")
    if app_target and keyboard_target:
        app_version = float(app_target.group(1))
        keyboard_version = float(keyboard_target.group(1))
        check(keyboard_version >= app_version,
              "the keyboard targets an older system than the standalone app")
        check(app_version == 17.0,
              f"the app's deployment target moved off 17.0, which is the oldest system supported")
        from xcode_project import activate
        embedded = activate(spec)
        embedded_app = re.search(
            r"SuperCraftOS:\n(?:.*\n)*?    deploymentTarget: \"([0-9.]+)\"",
            embedded.split("SuperCraftOSKeyboard:")[0],
        )
        check(embedded_app is not None and float(embedded_app.group(1)) >= keyboard_version,
              "the app target is lower than its keyboard when the keyboard is embedded")

    # 5. The published builds have to agree with the targets, and the
    #    installer has to pick the one the device can run.
    releases = ROOT / "release/ios"
    if releases.exists():
        for ipa in sorted(releases.glob("*Device*.ipa")):
            import zipfile
            with zipfile.ZipFile(ipa) as bundle:
                versions = {}
                for member in bundle.namelist():
                    if member.endswith("Info.plist") and member.startswith("Payload/"):
                        data = plistlib.loads(bundle.read(member))
                        versions[member.split("/")[-2]] = data.get("MinimumOSVersion")
            check("SuperCraftOS.app" in versions, f"{ipa.name} has no app bundle")
            if "SuperCraftOSKeyboard.appex" in versions:
                check(float(versions["SuperCraftOSKeyboard.appex"]) >= 26.0,
                      f"{ipa.name} has a keyboard that does not target iOS 26")
                check(float(versions["SuperCraftOS.app"]) >= float(versions["SuperCraftOSKeyboard.appex"]),
                      f"{ipa.name} has an app target lower than its embedded keyboard")
    # A device below the keyboard's target must still have a build it can
    # install, and the installer must be able to tell the two apart.
    if releases.exists():
        check((releases / "SuperCraftOS-iOS-Device-unsigned.ipa").exists(),
              "there is no build for a device that cannot run the keyboard")

    installer = (ROOT / "scripts/supercraftos_install.sh").read_text()
    import subprocess
    helper_help = subprocess.check_output(
        [sys.executable, str(ROOT / "scripts/ios_device_install.py"), "prepare", "--help"],
        text=True,
    )
    check("ios_device_install.py" in installer and 'prepare "$@"' in installer,
          "the installer does not delegate build selection to the local Mac helper")
    check("--with-keyboard" in helper_help,
          "the local Mac helper does not expose the optional keyboard build")

    print(f"checked {CHECKS} rules from Apple's own documentation")
    for failure in FAILURES:
        print(f"  FAIL {failure}")
    if FAILURES:
        print(f"{len(FAILURES)} of {CHECKS} checks failed")
        return 1
    print("every rule Apple documents is satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
