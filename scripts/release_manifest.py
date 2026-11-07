#!/usr/bin/env python3
"""Build a release manifest for the downloaded iOS artifacts and verify them.

Usage:
    python3 scripts/release_manifest.py data/release/ios --build <build-slug>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_ios_artifacts import verify_app, verify_keyboard  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(path: Path) -> dict:
    entry = {
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            entry["entries"] = len(archive.namelist())
            entry["contains"] = sorted({name.split("/")[0] for name in archive.namelist()})[:8]
    return entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--build", default=None)
    parser.add_argument("--app", default="SuperCraftOS-iOS-Simulator.app.zip")
    parser.add_argument("--keyboard", default="SuperCraftOSKeyboard.appex.zip")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    directory = Path(args.directory)
    artifacts = [describe(path) for path in sorted(directory.iterdir()) if path.is_file()]

    verification = None
    keyboard_verification = None
    app = directory / args.app
    if app.exists():
        import shutil
        import tempfile

        temporary = Path(tempfile.mkdtemp(prefix="supercraftos-manifest-"))
        try:
            with zipfile.ZipFile(app) as archive:
                archive.extractall(temporary)
            bundles = list(temporary.rglob("*.app"))
            if bundles:
                verification = verify_app(bundles[0])
        finally:
            shutil.rmtree(temporary, ignore_errors=True)

    keyboard = directory / args.keyboard
    if keyboard.exists():
        import shutil
        import tempfile

        temporary = Path(tempfile.mkdtemp(prefix="supercraftos-manifest-"))
        try:
            with zipfile.ZipFile(keyboard) as archive:
                archive.extractall(temporary)
            bundles = list(temporary.rglob("*.appex"))
            if bundles:
                keyboard_verification = verify_keyboard(bundles[0])
        finally:
            shutil.rmtree(temporary, ignore_errors=True)

    manifest = {
        "build_slug": args.build,
        "artifacts": artifacts,
        "app_verification": verification,
        "keyboard_verification": keyboard_verification,
        "verified": bool(verification and verification.get("ok")
                         and keyboard_verification and keyboard_verification.get("ok")),
    }
    text = json.dumps(manifest, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text)
    return 0 if manifest["verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
