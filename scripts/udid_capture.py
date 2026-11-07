#!/usr/bin/env python3
"""Generate the configuration profile that captures an iOS device UDID.

The profile carries two payloads, because only one of the two is documented by
Apple and the other one was asked for explicitly.

1. "Profile Service" - Apple's documented OTA profile service payload.  The
   literal payload type is "Profile Service" and it carries a PayloadContent
   dict with the URL the device must call and the device attributes it must
   report.  When the user installs the profile the device POSTs a PKCS#7
   signed plist with the UDID to that URL, and iOS then opens the page the
   server redirects to.  This is the mechanism described in Apple's archived
   "Over-the-Air Profile Delivery and Configuration" guide, and it is what the
   public UDID finder services (udid.tools, getudid.co, the Capgo and
   Capawesome tools) run in production.

2. com.apple.webClip.managed - the web clip payload.  Its PayloadURL points
   at the same server and carries the $(UDID) placeholder, which iOS is asked
   to substitute with the device UDID when it creates the web clip.

   Apple does not document any substitution of $(UDID) into a web clip
   PayloadURL.  The WebClip payload reference (developer.apple.com,
   documentation/devicemanagement/webclip) and the "Web Clips payload
   settings" page in Apple's Platform Deployment guide describe the URL key
   as a plain URL, and the only payload variables Apple documents are the
   macOS only %HardwareUUID% and friends for VPN payloads.  So the $(UDID)
   placeholder is carried because it was asked for and because it is harmless
   if it is not substituted, but the capture does not depend on it: the
   web clip only opens the capture page.

Usage:
    scripts/udid_capture.py --output udid.mobileconfig
    scripts/udid_capture.py --variant webclip --output webclip.mobileconfig
    scripts/udid_capture.py --print
"""
from __future__ import annotations

import argparse
import plistlib
import struct
import sys
import uuid
import zlib
from pathlib import Path

DEFAULT_BASE_URL = "https://agent.commetai.ca"
PROFILE_IDENTIFIER = "ca.commetai.supercraftos.udid-capture"
SERVICE_IDENTIFIER = "ca.commetai.supercraftos.profile-service"
WEB_CLIP_IDENTIFIER = "ca.commetai.supercraftos.udid-webclip"

# What the device reports back. UDID is the one that matters, the rest is free
# context that helps the user tell the iPhone from the iPad.  Apple's OTA
# guide lists UDID, VERSION, PRODUCT, SERIAL, MEID, IMEI and ICCID; the
# public UDID finder services also ask for DEVICE_NAME.  Attributes a device
# cannot report are simply left out of the answer, they do not fail it.
DEVICE_ATTRIBUTES = ["UDID", "DEVICE_NAME", "PRODUCT", "VERSION", "SERIAL"]

VARIANTS = ("full", "service", "webclip")


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def png_icon(size: int = 144) -> bytes:
    """A small square PNG for the web clip icon.

    Written by hand so the generator needs no image library.  A dark tile with
    a pink disc, which is what the SuperCraftOS pages look like.
    """
    background = (0x12, 0x10, 0x16, 0xFF)
    accent = (0xF5, 0x42, 0x8C, 0xFF)
    centre = (size - 1) / 2.0
    radius = size * 0.30
    rows = bytearray()
    for y in range(size):
        rows.append(0)  # PNG filter type 0 for every scanline
        for x in range(size):
            distance = ((x - centre) ** 2 + (y - centre) ** 2) ** 0.5
            rows.extend(accent if distance <= radius else background)
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR", header)
            + _png_chunk(b"IDAT", zlib.compress(bytes(rows), 9))
            + _png_chunk(b"IEND", b""))


def profile_service_payload(base_url: str = DEFAULT_BASE_URL) -> dict:
    """The Apple "Profile Service" payload.

    PayloadContent is a dict, not an array, and the payload type is the
    literal string "Profile Service".  Both are required by iOS.
    """
    return {
        "PayloadType": "Profile Service",
        "PayloadIdentifier": SERVICE_IDENTIFIER,
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadVersion": 1,
        "PayloadDisplayName": "SuperCraftOS device identification",
        "PayloadDescription": "Reports this device's UDID to the SuperCraftOS server so it can be registered for signing.",
        "PayloadOrganization": "SuperCraftOS",
        "PayloadContent": {
            "URL": f"{base_url.rstrip('/')}/ios/udid",
            "DeviceAttributes": list(DEVICE_ATTRIBUTES),
        },
    }


def web_clip_payload(base_url: str = DEFAULT_BASE_URL) -> dict:
    """The com.apple.webClip.managed payload.

    The PayloadURL carries the $(UDID) placeholder.  Apple documents no
    substitution for it, see the module docstring.
    """
    return {
        "PayloadType": "com.apple.webClip.managed",
        "PayloadIdentifier": WEB_CLIP_IDENTIFIER,
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadVersion": 1,
        "PayloadDisplayName": "SuperCraftOS UDID",
        "PayloadDescription": "Opens the SuperCraftOS device page on this device.",
        "Label": "SuperCraftOS",
        "PayloadURL": f"{base_url.rstrip('/')}/ios/udid?src=webclip&udid=$(UDID)",
        "Icon": png_icon(),
        "IsRemovable": True,
        "Precomposed": False,
        "FullScreen": False,
        "IgnoreManifestScope": False,
    }


def build_profile(base_url: str = DEFAULT_BASE_URL, variant: str = "full") -> dict:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}, use one of {', '.join(VARIANTS)}")
    payloads = []
    if variant in ("full", "service"):
        payloads.append(profile_service_payload(base_url))
    if variant in ("full", "webclip"):
        payloads.append(web_clip_payload(base_url))
    return {
        "PayloadContent": payloads,
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": PROFILE_IDENTIFIER,
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadDisplayName": "SuperCraftOS device UDID",
        "PayloadDescription": "Temporary profile that reports this device's UDID to the SuperCraftOS server. It changes no settings and can be removed right after use.",
        "PayloadOrganization": "SuperCraftOS",
    }


def render_profile(profile: dict) -> bytes:
    return plistlib.dumps(profile, fmt=plistlib.FMT_XML, sort_keys=True)


def profile_bytes(base_url: str = DEFAULT_BASE_URL, variant: str = "full") -> bytes:
    return render_profile(build_profile(base_url, variant))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help="public base url of the capture server")
    parser.add_argument("--variant", default="full", choices=VARIANTS,
                        help="full: both payloads, service: only the Profile Service payload, webclip: only the web clip payload")
    parser.add_argument("--output", type=Path, help="write the profile here instead of stdout")
    parser.add_argument("--print", action="store_true", help="print the profile to stdout")
    args = parser.parse_args(argv)

    payload = profile_bytes(args.base_url, args.variant)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
        print(f"wrote {args.output} ({len(payload)} bytes, variant {args.variant})")
        return 0
    if args.print or not sys.stdout.isatty():
        sys.stdout.buffer.write(payload)
        return 0
    parser.error("give --output or --print")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
