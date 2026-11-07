#!/usr/bin/env python3
"""Audit delivery endpoints and signing metadata; this does not prove installation.

This checks the whole chain from the outside, the way a device would meet it,
and it audits every address the delivery points at, so nothing can send a
device somewhere unexpected.

    scripts/verify_delivery.py

It checks:

1. every public address answers, with the right kind of answer
2. the install manifest is a valid plist, names a bundle that can be
   downloaded, and carries the bundle identifier and version the signed app
   has
3. the bundle carries signing metadata and unexpired device profiles, points
   at the configured backend, and declares its actual minimum system
4. each device's page knows its account, its install link and its renewal
   state
5. every address the pages and the code point at is either this server, or
   Apple's own site, or a named project, and it answers
6. legacy signer-service plumbing works with a stub in a temporary directory;
   this does not test Apple signing or the local free-account installation
7. the credential store is encrypted, and the files are mode 600
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import io
import json
import os
import plistlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get("SUPERCRAFTOS_BASE", "https://agent.commetai.ca")

PASSED: list[str] = []
FAILED: list[str] = []


def check(ok: bool, what: str, detail: str = "") -> bool:
    if ok:
        PASSED.append(what)
    else:
        FAILED.append(f"{what}{(': ' + detail) if detail else ''}")
    return ok


def get(path: str, timeout: int = 30) -> tuple[int, bytes, str]:
    request = urllib.request.Request(BASE + path, headers={
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers.get("Content-Type", "")
    except Exception as error:  # noqa: BLE001
        return 0, str(error).encode(), ""


def curl_status(url: str) -> int:
    """The status an outside host answers with, through curl, which is what
    this server's proxy is set up for."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-L",
             "--max-time", "25", "-A", "Mozilla/5.0", url],
            capture_output=True, text=True, timeout=40)
        return int(result.stdout.strip() or 0)
    except Exception:
        return 0


def head(path: str, timeout: int = 20) -> tuple[int, str]:
    try:
        request = urllib.request.Request(BASE + path, method="HEAD",
                                         headers={"User-Agent": "SuperCraftOS verifier"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get("Content-Type", "")
    except Exception:
        return 0, ""


# ------------------------------------------------------------- 1. the surface

ROUTES = [
    ("/", "text/html"),
    ("/ios/install.html", "text/html"),
    ("/ios/plan.txt", "text/plain"),
    ("/ios/install.png", "image/png"),
    ("/ios/udid", "text/html"),
    ("/ios/sign", "text/html"),
    ("/ios/devices", "text/html"),
    ("/ios/sideinstaller.plist", "application/xml"),
    ("/ios/SuperCraftOS-iOS-Device-unsigned.ipa", ""),
    ("/ios/SuperCraftOS-iOS-Device-WithKeyboard-unsigned.ipa", ""),
]


def access_key() -> str:
    """The private gateway's own access key, for the routes behind it."""
    for candidate in (ROOT / "data" / "access.key", Path("/var/lib/supercraftos/access.key")):
        try:
            key = candidate.read_text().strip()
        except OSError:
            continue
        if key:
            return key
    return ""


def check_surface() -> None:
    for path, content_type in ROUTES:
        status, body, kind = get(path)
        ok = status == 200
        if content_type:
            ok = ok and content_type.split(";")[0].strip() in kind
        check(ok, f"{path} answers 200", f"got {status} {kind}")

    # The agent API sits behind the private gateway, so it answers only to the
    # holder of the access key. Checking it the way a browser would proves the
    # gateway refuses an anonymous caller; checking it with the key proves the
    # agent itself is alive behind it.
    status, body, kind = get("/api/status")
    check(status == 401 and "application/json" in kind,
          "/api/status refuses an anonymous caller", f"got {status} {kind}")
    key = access_key()
    if key:
        request = urllib.request.Request(
            BASE + "/api/status", headers={"Authorization": f"Bearer {key}",
                                           "Accept": "application/json",
                                           "User-Agent": "SuperCraftOS verifier"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = response.status
                body = response.read()
                kind = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            status, body, kind = error.code, error.read(), error.headers.get("Content-Type", "")
        except Exception as error:  # noqa: BLE001
            status, body, kind = 0, str(error).encode(), ""
        check(status == 200 and "application/json" in kind,
              "/api/status answers 200 for the access key", f"got {status} {kind}")
        if status == 200:
            try:
                parsed = json.loads(body)
            except ValueError:
                parsed = {}
            check(isinstance(parsed, dict) and parsed.get("runtime") is not None,
                  "/api/status reports the runtime", "no runtime field")
    else:
        check(False, "/api/status answers 200 for the access key", "no access key was found")


# ---------------------------------------------------- 2. the install manifest

def profile_metadata(raw: bytes) -> dict:
    """Read diagnostic plist fields, not a cryptographic signature verification."""
    start, end = raw.find(b"<?xml"), raw.rfind(b"</plist>")
    if start < 0 or end < start:
        raise ValueError("provisioning profile has no readable plist")
    value = plistlib.loads(raw[start:end + len(b"</plist>")])
    if not isinstance(value, dict):
        raise ValueError("provisioning profile must contain a dictionary")
    return value


def version_parts(value: str) -> tuple[int, ...]:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,2}", value):
        raise ValueError("invalid MinimumOSVersion")
    return tuple(int(part) for part in value.split("."))


def check_package(bundle: bytes, udid: str, metadata: dict) -> None:
    """Check signing metadata while the ZIP is open; device installation is separate."""
    label = udid[-6:]
    try:
        with zipfile.ZipFile(io.BytesIO(bundle)) as package:
            names = package.namelist()
            roots = [name[:-len("Info.plist")] for name in names
                     if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist", name)]
            if len(roots) != 1:
                raise ValueError("IPA must contain exactly one main app Info.plist")
            root = roots[0]
            info = plistlib.loads(package.read(root + "Info.plist"))
            check(info.get("CFBundleIdentifier") == metadata.get("bundle-identifier"),
                  f"the bundle for {label} matches the manifest identifier")
            check(str(info.get("CFBundleVersion", "")) == str(metadata.get("bundle-version", ""))
                  and bool(info.get("CFBundleVersion")),
                  f"the bundle for {label} matches the manifest version")
            check(info.get("SUPERCRAFTOSBackendURL") == BASE,
                  f"the bundle for {label} is pointed at the live control centre")
            minimum = info.get("MinimumOSVersion", "")
            version_parts(minimum)
            check(True, f"the app for {label} declares minimum iOS {minimum}")
            check(info.get("CFBundleSupportedPlatforms") == ["iPhoneOS"],
                  f"the bundle for {label} is a physical-device build")
            bundles = [root] + [name[:-len("Info.plist")] for name in names
                if re.fullmatch(re.escape(root) + r"PlugIns/[^/]+\.appex/Info\.plist", name)]
            for prefix in bundles:
                component = plistlib.loads(package.read(prefix + "Info.plist"))
                component_min = component.get("MinimumOSVersion", "")
                version_parts(component_min)
                check(True, f"{prefix} declares minimum iOS {component_min}")
                check(prefix + "_CodeSignature/CodeResources" in names,
                      f"{prefix} has signature metadata (not cryptographic proof)")
                profile_path = prefix + "embedded.mobileprovision"
                if not check(profile_path in names, f"{prefix} carries a provisioning profile"):
                    continue
                profile = profile_metadata(package.read(profile_path))
                check(udid in profile.get("ProvisionedDevices", []),
                      f"the profile in {prefix} covers device {label}")
                expiry = profile.get("ExpirationDate")
                if isinstance(expiry, datetime):
                    expiry = expiry.replace(tzinfo=timezone.utc) if expiry.tzinfo is None else expiry
                check(isinstance(expiry, datetime) and expiry > datetime.now(timezone.utc),
                      f"the profile in {prefix} is unexpired")
    except (ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile,
            plistlib.InvalidFileException) as error:
        check(False, f"the bundle for {label} has readable delivery metadata", str(error))


def check_manifest() -> None:
    try:
        devices = json.loads((ROOT / "data/ios-device-accounts.json").read_text())
        if not isinstance(devices, dict) or not devices:
            raise ValueError("no device delivery records; installation is not verified")
    except (OSError, ValueError) as error:
        check(False, "device delivery records are available", str(error))
        return
    for udid in devices:
        status, body, kind = get(f"/ios/device/{udid}/manifest.plist")
        if not check(status == 200, f"the manifest for {udid[-6:]} answers"):
            continue
        if not check(any(value in kind for value in ("application/xml", "text/xml", "application/x-plist")),
                     f"the manifest for {udid[-6:]} has a plist content type", kind):
            continue
        try:
            parsed = plistlib.loads(body)
            items = parsed.get("items") if isinstance(parsed, dict) else None
            if not isinstance(items, list) or len(items) != 1:
                raise ValueError("no unique installable item; a signed bundle is not ready")
            item = items[0]
            assets = [a for a in item["assets"] if isinstance(a, dict) and a.get("kind") == "software-package"]
            if len(assets) != 1:
                raise ValueError("manifest must name exactly one software package")
            metadata = item["metadata"]
            if metadata.get("bundle-identifier") != "com.supercraftos.control" or not metadata.get("bundle-version"):
                raise ValueError("manifest must include the app identifier and bundle version")
            url = urlsplit(assets[0]["url"])
            base = urlsplit(BASE)
            if (url.scheme != "https" or url.netloc != base.netloc or url.username or url.password
                    or url.query or url.fragment or not url.path.startswith("/ios/signed/")
                    or ".." in unquote(url.path).split("/")):
                raise ValueError("package URL must stay under this HTTPS server's /ios/signed/")
        except (ValueError, KeyError, TypeError, AttributeError, plistlib.InvalidFileException) as error:
            check(False, f"the manifest for {udid[-6:]} names a signed delivery candidate", str(error))
            continue
        status, bundle, _ = get(url.path, timeout=60)
        if not check(status == 200, "the bundle the manifest names can be downloaded", str(status)):
            continue
        check_package(bundle, udid, metadata)


# ------------------------------------------------------- 3. the device pages

def check_devices() -> None:
    accounts = json.loads((ROOT / "data/ios-device-accounts.json").read_text())
    for udid, account in accounts.items():
        status, body, _ = get(f"/ios/device/{udid}")
        if not check(status == 200, f"the page for {udid[-6:]} answers"):
            continue
        text = body.decode("utf-8", "replace")
        check(account in text, f"the page for {udid[-6:]} names its account", account)
        check("itms-services://" in text or "Nothing is signed" in text,
              f"the page for {udid[-6:]} offers the install or says it is not signed")


# ------------------------------------------------ 4. where everything points

# Every address the delivery is allowed to point a device at. Anything not
# listed here and not on this server is a finding.
ALLOWED_EXTERNAL = {
    "https://www.icloud.com": "Apple, iCloud",
    "https://www.icloud.com/signin": "Apple, iCloud sign in",
    "https://www.icloud.com/find": "Apple, Find My",
    "https://account.apple.com": "Apple, the Apple Account page",
    "https://idmsa.apple.com": "Apple, the sign in service",
    "https://support.apple.com/en-us/102654": "Apple, app specific passwords",
    "https://sideinstaller.net/": "SideStore, the official site",
    "https://github.com/SideStore/SideStore/releases": "SideStore, the releases",
    "https://raw.githubusercontent.com/FrizzleM/SideInstaller/": "SideStore, the official package",
    "https://sideloadly.io/": "Sideloadly, the official site",
    "https://developer.apple.com/help/account/basics/about-your-developer-account": "Apple, the account limits",
    "https://docs.sidestore.io/docs/installation/prerequisites": "SideStore, the official setup guide",
}


def check_destinations() -> None:
    pages = ["/", "/ios/install.html", "/ios/plan.txt", "/ios/devices"]
    found: set[str] = set()
    for page in pages:
        _, body, _ = get(page)
        text = body.decode("utf-8", "replace")
        for link in re.findall(r'href="([^"]+)"', text):
            if link.startswith("#") or link.startswith("itms-services://") \
                    or link.startswith("sidestore://"):
                continue
            if link.startswith("/"):
                link = BASE + link
            elif not link.startswith("http"):
                link = BASE + "/ios/" + link
            found.add(link)
        for link in re.findall(r'https?://[^\s"\'<>]+', text):
            if link.startswith(BASE):
                continue
            found.add(link.rstrip(".,)"))

    for link in sorted(found):
        if link.startswith(BASE):
            continue
        if "127.0.0.1" in link or "192.168.x.x" in link or "localhost" in link:
            continue  # an example of an address, not somewhere a device is sent
        if link in ALLOWED_EXTERNAL:
            status = curl_status(link.split("#")[0])
            check(status > 0, f"{link} answers and is {ALLOWED_EXTERNAL[link]}", str(status))
            continue
        # Anything else has to be justified. Check what it actually is.
        status, kind = head(link.split("#")[0])
        check(False, f"an address the delivery points at is not on the allowed list: {link}",
              f"status {status} {kind}")


# ------------------------------------------- 5. legacy signer-service fixture

def check_signing_flow() -> None:
    """Exercise legacy signer-service plumbing in a temporary directory.

    Nothing here touches the real service, the real credentials or the real
    bundles. A stub process cannot prove Apple signing, a valid IPA, provisioning
    compatibility, or installation. Free-account signing now happens on the Mac.
    """
    import importlib.util

    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        signer = root / "fake-signer"
        signer.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib, sys\n"
            "print('Enter the two factor code sent to your devices:', flush=True)\n"
            "sys.stdin.readline()\n"
            "out = pathlib.Path(sys.argv[-1])\n"
            "out.parent.mkdir(parents=True, exist_ok=True)\n"
            "out.write_bytes(b'PK\\x03\\x04 signed')\n")
        signer.chmod(0o755)
        app = root / "app.ipa"
        app.write_bytes(b"PK\x03\x04 unsigned")
        devices = root / "devices.json"
        devices.write_text(json.dumps({"devices": [
            {"udid": "00008030-001A2B3C4D5E6F70", "name": "Test iPhone"}]}))
        accounts = root / "accounts.json"
        accounts.write_text(json.dumps({
            "00008030-001A2B3C4D5E6F70": "fixture@example.invalid"}))
        credentials_file = root / "credentials.json"
        token_file = root / "token.key"

        os.environ["SUPERCRAFTOS_CREDENTIALS"] = str(credentials_file)
        os.environ["SUPERCRAFTOS_CREDENTIAL_KEY"] = str(root / "credentials.key")
        os.environ["SUPERCRAFTOS_TOKEN_KEY"] = str(token_file)
        os.environ["SUPERCRAFTOS_OUT"] = str(root / "signed")
        os.environ["SUPERCRAFTOS_PUBLISH"] = str(root / "published")

        spec = importlib.util.spec_from_file_location(
            "ios_sign_service", ROOT / "scripts/ios_sign_service.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.SIGNER = signer
        module.APP = app
        module.DEVICES_FILE = devices
        module.ACCOUNTS_FILE = accounts
        module.PUBLISH_DIR = root / "published"

        account = module.account_for_device("00008030-001A2B3C4D5E6F70")
        check(account == "fixture@example.invalid",
              "the device resolves to its account", account)

        session = module.Session(account, ["00008030-001A2B3C4D5E6F70"], "app",
                                 "the-app-specific-password")
        session.spawn("the-app-specific-password")
        line = session.read_until(lambda text: module.TWO_FACTOR_PROMPT in text, timeout=60)
        check(module.TWO_FACTOR_PROMPT in line, "the stub signer asks for a fixture code")
        session.send("123456")
        deadline = time.time() + 60
        while not session.done and time.time() < deadline:
            time.sleep(0.2)
        check(session.out_path.exists(), "the stub signer produced its fixture file")
        module.publish(session.out_path)
        check((root / "published" / session.out_path.name).exists(),
              "the fixture file is copied to the temporary publish directory")

        # The password is kept, encrypted, and the file is private.
        module.credentials.remember_password(session.apple_id, session.password)
        check(credentials_file.exists(), "the password is kept for the account")
        check(not credentials_file.exists() or "the-app-specific-password" not in
              credentials_file.read_text(),
              "the password is not readable in the file")
        check(oct(credentials_file.stat().st_mode & 0o777) == "0o600",
              "the credential store is mode 600",
              oct(credentials_file.stat().st_mode & 0o777))
        check(module.credentials.passwords_for(account) == ["the-app-specific-password"],
              "the password can be read back by the server")

        # The token, and what it proves.
        token = module.credentials.make_token(account, "00008030-001A2B3C4D5E6F70", "app")
        claims = module.credentials.read_token(token)
        check(claims is not None and claims.get("sub") == account,
              "the token proves which account it is for")
        check(claims is not None and claims.get("device") == "00008030-001A2B3C4D5E6F70",
              "the token is scoped to the device")
        forged = module.credentials.read_token(token[:-4] + "AAAA")
        check(forged is None, "a changed token is refused")


def main() -> int:
    print(f"checking the delivery at {BASE}\n")
    print("Metadata checks do not prove a valid code signature, free-profile OTA support, or a physical installation.\n")
    check_surface()
    check_manifest()
    check_devices()
    check_destinations()
    check_signing_flow()

    for line in PASSED:
        print(f"  ok    {line}")
    for line in FAILED:
        print(f"  FAIL  {line}")
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
