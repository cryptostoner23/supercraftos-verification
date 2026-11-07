#!/usr/bin/env python3
"""Assemble the iOS release assets from the latest successful Bitrise build.

Downloads the published artifacts, converts the unsigned device app bundles
into .ipa files for sideloading, verifies every bundle, and writes a manifest.

Usage:
    python3 scripts/build_release_assets.py --out release/ios
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.package_ipa import package as package_ipa  # noqa: E402
from scripts.verify_ios_artifacts import verify_app, verify_keyboard  # noqa: E402

BITRISE = ROOT / "scripts" / "bitrise_build.py"
PYTHON = sys.executable

# The device app bundles that become .ipa files for sideloading.
DEVICE_BUNDLES = {
    "SuperCraftOS-iOS-Device-unsigned.app.zip": "SuperCraftOS-iOS-Device-unsigned.ipa",
    "SuperCraftOS-iOS-Device-WithKeyboard-unsigned.app.zip": "SuperCraftOS-iOS-Device-WithKeyboard-unsigned.ipa",
}


def download(target: Path, build: str) -> None:
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run([PYTHON, str(BITRISE), "artifacts", build, "--download", str(target)],
                   check=True, cwd=str(ROOT), stdout=subprocess.DEVNULL)


def to_ipa(archive: Path, output: Path) -> dict:
    staging = output.parent / f".{archive.stem}-unpack"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(staging)
    bundles = sorted(staging.rglob("*.app"))
    if not bundles:
        raise SystemExit(f"no .app inside {archive}")
    result = package_ipa(bundles[0], output)
    shutil.rmtree(staging, ignore_errors=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="release/ios")
    parser.add_argument("--build", default="latest")
    args = parser.parse_args()

    out = (ROOT / args.out).resolve()
    info = json.loads(subprocess.check_output(
        [PYTHON, str(BITRISE), "status", args.build], cwd=ROOT))
    if info.get("status") != "success" or not info.get("commit") or not info.get("build_slug"):
        raise SystemExit("Release requires a successful build with a recorded source commit")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ios-release-", dir=out.parent) as temporary:
        stage = Path(temporary)
        download(stage, info["build_slug"])
        manifest = assemble(stage, info)
        out.mkdir(parents=True, exist_ok=True)
        # Leave existing signed IPAs, profiles and renewal state untouched.
        # Publish the manifest last, after every verified artifact is in place.
        for path in stage.iterdir():
            if path.is_file() and path.name != "manifest.json":
                path.replace(out / path.name)
        (stage / "manifest.json").replace(out / "manifest.json")
    print(json.dumps({"out": str(out), "verified": manifest["verified"],
                      "build": info["build_slug"], "commit": info["commit"],
                      "signing": manifest["signing"]}, indent=2))
    return 0


def assemble(out: Path, build: dict) -> dict:
    required = {"SuperCraftOS-iOS-Simulator.app.zip",
                "SuperCraftOS-iOS-Device-unsigned.app.zip",
                "SuperCraftOSKeyboard.appex.zip"}
    missing = required - {p.name for p in out.iterdir() if p.is_file()}
    if missing:
        raise ValueError("Missing release artifacts: " + ", ".join(sorted(missing)))

    ipas = []
    for archive_name, ipa_name in DEVICE_BUNDLES.items():
        archive = out / archive_name
        if not archive.exists():
            continue
        ipas.append(to_ipa(archive, out / ipa_name))

    verifications = {}
    for name, verifier in (("SuperCraftOS-iOS-Simulator.app.zip", verify_app),
                           ("SuperCraftOS-iOS-Device-unsigned.app.zip", verify_app),
                           ("SuperCraftOSKeyboard.appex.zip", verify_keyboard)):
        archive = out / name
        if not archive.exists():
            continue
        staging = out / f".verify-{name}"
        staging.mkdir()
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(staging)
        bundles = sorted(staging.rglob("*.app")) + sorted(staging.rglob("*.appex"))
        if bundles:
            verifications[name] = verifier(bundles[0])
        shutil.rmtree(staging, ignore_errors=True)

    manifest = {
        "build": build,
        "signing": "unsigned; requires personal provisioning and device installation",
        "artifacts": sorted(p.name for p in out.iterdir() if p.is_file()),
        "ipas": ipas,
        "verification": verifications,
        "verified": all(v.get("ok") for v in verifications.values()) if verifications else False,
    }
    if not manifest["verified"]:
        raise ValueError("iOS bundle verification failed; previous release is unchanged")
    manifest["sha256"] = {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                          for name in manifest["artifacts"]}
    (out / "SHA256SUMS").write_text("".join(
        f"{digest}  {name}\n" for name, digest in sorted(manifest["sha256"].items())))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    sys.exit(main())
