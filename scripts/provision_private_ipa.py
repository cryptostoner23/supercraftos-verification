#!/usr/bin/env python3
"""Turn an unsigned Bitrise app ZIP into a private, gateway-provisioned IPA.

The access key is read from a local file and never passed on the command line,
printed, or written to the repository. The resulting IPA is itself a secret.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import plistlib
import tempfile
import zipfile


def provision(source: Path, key_file: Path, output: Path, origin: str) -> dict:
    key = key_file.read_text().strip()
    if not (32 <= len(key.encode()) <= 512 and all(33 <= ord(c) <= 126 for c in key)):
        raise ValueError("Gateway key has an invalid format")
    if not origin.startswith("https://") or origin.endswith("/"):
        raise ValueError("Expected a canonical HTTPS origin")
    output.parent.mkdir(parents=True, exist_ok=True)
    os.umask(0o077)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".ipa", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(source) as original, zipfile.ZipFile(temporary_path, "w") as result:
            names = original.namelist()
            if "SuperCraftOS.app/Info.plist" not in names or "SuperCraftOS.app/SuperCraftOS" not in names:
                raise ValueError("Source ZIP does not contain the expected iOS app")
            for info in original.infolist():
                name = PurePosixPath(info.filename)
                if name.is_absolute() or ".." in name.parts or name.parts[0] != "SuperCraftOS.app":
                    raise ValueError("Unexpected path in app ZIP")
                content = original.read(info)
                if info.filename == "SuperCraftOS.app/Info.plist":
                    plist = plistlib.loads(content)
                    if plist.get("SUPERCRAFTOSBackendURL") != origin:
                        raise ValueError("Built app targets a different server")
                    plist["SUPERCRAFTOSAccessKey"] = key
                    content = plistlib.dumps(plist, fmt=plistlib.FMT_BINARY)
                info.filename = "Payload/" + info.filename
                result.writestr(info, content)
        with zipfile.ZipFile(temporary_path) as check:
            if check.testzip() is not None:
                raise ValueError("Provisioned IPA failed ZIP verification")
            plist = plistlib.loads(check.read("Payload/SuperCraftOS.app/Info.plist"))
            if plist.get("SUPERCRAFTOSAccessKey") != key or plist.get("SUPERCRAFTOSBackendURL") != origin:
                raise ValueError("Provisioned IPA has incorrect connection settings")
        temporary_path.replace(output)
        output.chmod(0o600)
        return {"path": str(output), "bytes": output.stat().st_size,
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "gateway_provisioned": True, "server": origin}
    finally:
        temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app_zip", type=Path)
    parser.add_argument("key_file", type=Path)
    parser.add_argument("output_ipa", type=Path)
    parser.add_argument("--origin", default="https://agent.commetai.ca")
    args = parser.parse_args()
    print(provision(args.app_zip, args.key_file, args.output_ipa, args.origin))
