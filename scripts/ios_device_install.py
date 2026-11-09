#!/usr/bin/env python3
"""Prepare an IPA for local free-account signing, or USB-install a signed IPA.

No Apple credentials are accepted. Signing is interactive in Sideloadly on the
operator's Mac. See docs/FREE_APPLE_INSTALL.md. Requires Python 3.9 or newer.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fnmatch
import hashlib
import os
from pathlib import Path, PurePosixPath
import platform
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlsplit
import zipfile

MAX_BYTES = 512 * 1024 * 1024
BASE = "https://agent.commetai.ca/ios"


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d+){0,2}", value):
        raise ValueError("missing or invalid MinimumOSVersion")
    return tuple(map(int, value.split("."))) + (0,) * (3 - len(value.split(".")))


def inspect_ipa(path):
    """Structural inspection only; signature markers do not prove valid signing."""
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 20000 or sum(item.file_size for item in entries) > MAX_BYTES:
            raise ValueError("IPA exceeds the extraction limit")
        names = [item.filename for item in entries]
        if len(names) != len(set(names)):
            raise ValueError("IPA contains duplicate paths")
        for item in entries:
            parts = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (parts.is_absolute() or ".." in parts.parts or "\\" in item.filename
                    or stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise ValueError("IPA contains an unsafe or unsupported archive entry")
        roots = [name[:-10] for name in names
                 if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist", name)]
        if len(roots) != 1:
            raise ValueError("IPA must contain one Payload/*.app/Info.plist")
        root = roots[0]
        prefixes = [root] + [name[:-10] for name in names if re.fullmatch(
            re.escape(root) + r"PlugIns/[^/]+\.appex/Info\.plist", name)]
        bundles = []
        for prefix in prefixes:
            info = plistlib.loads(archive.read(prefix + "Info.plist"))
            if not isinstance(info, dict):
                raise ValueError("App Info.plist must be a dictionary")
            if info.get("CFBundleSupportedPlatforms") != ["iPhoneOS"]:
                raise ValueError("Use the physical-device IPA, not a simulator build")
            executable = info.get("CFBundleExecutable", "")
            if not executable or "/" in executable or prefix + executable not in names:
                raise ValueError("App executable is missing")
            version(info.get("MinimumOSVersion"))
            if not info.get("CFBundleIdentifier"):
                raise ValueError("App bundle identifier is missing")
            bundles.append({"prefix": prefix, "info": info})
        if archive.testzip() is not None:
            raise ValueError("IPA failed its ZIP integrity check")
    return bundles


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise ValueError("IPA download redirected away from credential-free HTTPS")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def download(url, target, expected_sha256=None):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("IPA download requires an HTTPS URL without embedded credentials")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".ipa-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as output, urllib.request.build_opener(HTTPSOnly()).open(url, timeout=60) as response:
            size = 0
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("IPA download exceeds 512 MiB")
                output.write(chunk)
        inspect_ipa(temporary)
        if expected_sha256 and sha256(temporary).lower() != expected_sha256.lower():
            raise ValueError("IPA SHA-256 does not match the expected build artifact")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def print_metadata(path, bundles, ios_version=None):
    minimum = max((entry["info"]["MinimumOSVersion"] for entry in bundles), key=version)
    print(f"IPA: {path}")
    print(f"SHA-256: {sha256(path)}")
    print(f"Required device OS: iOS/iPadOS {minimum} or later")
    print(f"Embedded extensions: {len(bundles) - 1}")
    if ios_version and version(ios_version) < version(minimum):
        raise ValueError(f"device iOS {ios_version} is below the bundle minimum {minimum}")


def prepare(args):
    if not args.no_open and platform.system() != "Darwin":
        raise ValueError("Run preparation on your Mac, or use --no-open to inspect/download only")
    filename = "SuperCraftOS-iOS-Device-" + ("WithKeyboard-" if args.with_keyboard else "") + "unsigned.ipa"
    path = Path(args.ipa).expanduser().resolve() if args.ipa else Path(
        args.output or str(Path.home() / "Downloads" / filename)).expanduser().resolve()
    if not args.ipa:
        download(args.url or BASE + "/" + filename, path, args.sha256)
    bundles = inspect_ipa(path)
    digest = sha256(path)
    if args.sha256 and digest.lower() != args.sha256.lower():
        raise ValueError("IPA SHA-256 does not match the expected build artifact")
    print_metadata(path, bundles, args.ios_version)
    print("\nPrepared for local signing; the app is NOT installed.")
    print("Connect and unlock the device by USB, and tap Trust.")
    print("Open Sideloadly from https://sideloadly.io on this Mac; drag this IPA into it.")
    print("Select this device and Apple ID Sideload mode; enter your free Apple Account there.")
    print("Press Start and complete Apple's password/2FA prompts inside that local app.")
    print("A free-account profile expires after 7 days. Re-sign/refresh before expiry.")
    print("Enable Developer Mode and trust the developer on the device when prompted.")
    print("Keep the same Apple Account and bundle ID when refreshing to preserve app data.")
    if len(bundles) > 1:
        print("This build includes extensions; each needs compatible signing. Start with the app-only IPA.")
    if not args.no_open:
        subprocess.run(["open", "-R", str(path)], check=True)
        opened = subprocess.run(["open", "-a", "Sideloadly"], capture_output=True)
        if opened.returncode:
            print("Install Sideloadly from its official site, then follow the steps above.")
    return 0


def extract_ipa(path, directory):
    inspect_ipa(path)
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            target = Path(directory) / item.filename
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                # ZipFile.extractall does not preserve executable permissions.
                target.chmod(0o755 if (item.external_attr >> 16) & 0o111 else 0o644)


def validate_profile(profile, info, udid):
    if not isinstance(profile, dict):
        raise ValueError("provisioning profile must be a dictionary")
    expiry = profile.get("ExpirationDate")
    if not isinstance(expiry, datetime):
        raise ValueError("provisioning profile has no expiry")
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= datetime.now(timezone.utc):
        raise ValueError("provisioning profile expired; re-sign locally")
    if udid not in profile.get("ProvisionedDevices", []):
        raise ValueError("provisioning profile does not include this device UDID")
    entitlements = profile.get("Entitlements", {})
    if not isinstance(entitlements, dict):
        raise ValueError("provisioning profile entitlements must be a dictionary")
    identifier = entitlements.get("application-identifier", "")
    if not isinstance(identifier, str):
        raise ValueError("profile application identifier is missing")
    pattern = identifier.partition(".")[2]
    if not pattern or not fnmatch.fnmatchcase(info["CFBundleIdentifier"], pattern):
        raise ValueError("profile application identifier does not match the bundle")
    return expiry


def install_signed(args):
    if platform.system() != "Darwin":
        raise ValueError("Signed-IPA verification/install requires this script on macOS")
    if not re.fullmatch(r"[A-Za-z0-9-]{16,80}", args.udid):
        raise ValueError("Pass the physical device's provisioning UDID, not its display name")
    path = Path(args.ipa).expanduser().resolve()
    bundles = inspect_ipa(path)
    print_metadata(path, bundles, args.ios_version)
    for tool in ("security", "codesign"):
        if not shutil.which(tool):
            raise ValueError(f"macOS {tool} is required")
    installer = shutil.which("ideviceinstaller")
    selected = args.tool
    if selected == "auto":
        selected = "ideviceinstaller" if installer else "devicectl"
    if selected == "ideviceinstaller" and not installer:
        raise ValueError("ideviceinstaller is unavailable; install that package separately or use devicectl")
    if selected == "devicectl":
        if not shutil.which("xcrun") or subprocess.run(
                ["xcrun", "--find", "devicectl"], capture_output=True).returncode:
            raise ValueError("This Xcode has no devicectl; use Sideloadly or ideviceinstaller on the older Mac")
    with tempfile.TemporaryDirectory(prefix="supercraftos-install-") as temporary:
        extract_ipa(path, temporary)
        for entry in bundles:
            app = Path(temporary) / entry["prefix"]
            profile = app / "embedded.mobileprovision"
            if not profile.is_file():
                raise ValueError("IPA is unsigned/unprovisioned; use the prepare/local-signing route")
            decoded = subprocess.run(["security", "cms", "-D", "-i", str(profile)],
                                     capture_output=True, check=True)
            expiry = validate_profile(plistlib.loads(decoded.stdout), entry["info"], args.udid)
            print(f"Profile for {entry['info']['CFBundleIdentifier']} expires {expiry.isoformat()}")
            subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
        if selected == "ideviceinstaller":
            help_text = subprocess.run([installer, "--help"], capture_output=True, text=True)
            usage = help_text.stdout + help_text.stderr
            if re.search(r"(?m)^\s*install\s+", usage):
                command = [installer, "-u", args.udid, "install", str(path)]
            elif "--install" in usage:
                command = [installer, "-u", args.udid, "-i", str(path)]
            else:
                raise ValueError("Unrecognized ideviceinstaller interface; inspect its --help")
        else:
            command = ["xcrun", "devicectl", "device", "install", "app", "--device",
                       args.udid, str(Path(temporary) / bundles[0]["prefix"])]
        subprocess.run(command, check=True)
    print("Installer reported success. Open the app on the device to verify launch and backend access.")
    print("Free-account profiles expire after 7 days; refresh/re-sign before expiry.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    prep = sub.add_parser("prepare", help="download/inspect IPA and open local signing UI")
    source = prep.add_mutually_exclusive_group()
    source.add_argument("--ipa")
    source.add_argument("--url")
    prep.add_argument("--output")
    prep.add_argument("--sha256")
    prep.add_argument("--with-keyboard", action="store_true")
    prep.add_argument("--no-open", action="store_true", help="prepare only; do not launch Mac GUI")
    prep.add_argument("--ios-version", help="optional connected-device OS version to check")
    signed = sub.add_parser("install-signed", help="verify existing signing and install by USB")
    signed.add_argument("--ipa", required=True)
    signed.add_argument("--udid", required=True)
    signed.add_argument("--ios-version")
    signed.add_argument("--tool", choices=("auto", "ideviceinstaller", "devicectl"), default="auto")
    args = parser.parse_args(argv)
    try:
        return prepare(args) if args.mode == "prepare" else install_signed(args)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile,
            plistlib.InvalidFileException, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
