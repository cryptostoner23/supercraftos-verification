#!/usr/bin/env python3
"""Package an unsigned iOS app bundle as an .ipa.

An .ipa is a zip with the app inside a `Payload` directory. Sideloading tools
such as AltStore and Sideloadly expect that layout.

Usage:
    python3 scripts/package_ipa.py path/to/SuperCraftOS.app path/to/SuperCraftOS.ipa
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path


def package(app: Path, output: Path) -> dict:
    if not (app / "Info.plist").exists():
        raise SystemExit(f"{app} does not look like an app bundle")
    staging = output.parent / f".{output.stem}-staging"
    if staging.exists():
        shutil.rmtree(staging)
    payload = staging / "Payload"
    payload.mkdir(parents=True)
    shutil.copytree(app, payload / app.name, symlinks=True)

    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.rglob("*")):
            archive.write(path, str(path.relative_to(staging)))
    shutil.rmtree(staging, ignore_errors=True)

    with zipfile.ZipFile(output) as verification:
        if verification.testzip() is not None:
            raise RuntimeError("the generated ipa failed verification")
        names = verification.namelist()

    extensions = set()
    for name in names:
        parts = name.split("/")
        if "PlugIns" in parts:
            after = parts[parts.index("PlugIns") + 1:]
            if after and after[0].endswith(".appex"):
                extensions.add(after[0])

    return {
        "ipa": str(output),
        "bytes": output.stat().st_size,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "entries": len(names),
        "payload": f"Payload/{app.name}/",
        "embedded_extensions": sorted(extensions),
    }


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    app = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps(package(app, output), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
