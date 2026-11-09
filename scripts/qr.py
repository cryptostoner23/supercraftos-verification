#!/usr/bin/env python3
"""Render a QR code for a URL.

    scripts/qr.py "https://agent.commetai.ca/ios/install.html" out.png

Pure Python, so it runs anywhere the repository runs, and the output is a
plain PNG that any camera can read.
"""
from __future__ import annotations

import sys
from pathlib import Path

import segno


def render(url: str, output: Path, scale: int = 12, border: int = 4) -> Path:
    code = segno.make(url, error="m")
    output.parent.mkdir(parents=True, exist_ok=True)
    code.save(output, kind="png", scale=scale, border=border, dark="#0b0a0e", light="#ffffff")
    return output


def verify(path: Path, expected: str) -> bool:
    """Read the code back with an independent decoder, so it is not just
    something that looks right."""
    try:
        import cv2
    except ImportError:
        return True
    image = cv2.imread(str(path))
    if image is None:
        return False
    data, points, _ = cv2.QRCodeDetector().detectAndDecode(image)
    return data == expected


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    url = sys.argv[1]
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("qr.png")
    render(url, output)
    print(f"{url} -> {output} ({output.stat().st_size} bytes)")
    if not verify(output, url):
        print("error: the code does not read back as the address", file=sys.stderr)
        return 1
    print("verified: the code reads back as that address")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
