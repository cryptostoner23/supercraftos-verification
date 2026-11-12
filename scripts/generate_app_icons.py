#!/usr/bin/env python3
"""Generate the SuperCraftOS app icon set.

The icon is drawn programmatically so it is reproducible and reviewable: a dark
console background with a keyboard grid in the product accent colours, which
matches the custom keyboard extension. PNG encoding is done with the standard
library only, so no image dependency is needed.
"""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "ios_app_dist" / "ci_xcode" / "Assets.xcassets"
APPICON = CATALOG / "AppIcon.appiconset"

BACKGROUND_TOP = (0x14, 0x12, 0x1A)
BACKGROUND_BOTTOM = (0x2A, 0x1E, 0x33)
PINK = (0xF5, 0x42, 0x8C)
CYAN = (0x38, 0xD1, 0xC7)
PURPLE = (0xA3, 0x6B, 0xFF)
WHITE = (0xF2, 0xF2, 0xF7)

# Supersampling factor for anti-aliasing.
SCALE = 4
CANVAS = 1024

# The keyboard grid, in 1024 point units.
KEY_SIZE = 168
KEY_GAP = 30
GRID_WIDTH = 3 * KEY_SIZE + 2 * KEY_GAP
GRID_LEFT = (CANVAS - GRID_WIDTH) / 2
GRID_TOP = 168
SPACE_TOP = 762
SPACE_HEIGHT = 100
GRID = [
    [PINK, CYAN, PURPLE],
    [PURPLE, PINK, CYAN],
    [CYAN, PURPLE, PINK],
]


def write_png(path: Path, width: int, height: int, pixels: bytes) -> None:
    """Write an 8 bit RGB PNG."""
    raw = b"".join(b"\x00" + pixels[y * width * 3:(y + 1) * width * 3] for y in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", header)
                     + chunk(b"IDAT", zlib.compress(raw, 9))
                     + chunk(b"IEND", b""))


def blend(base: tuple[int, int, int], top: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    return tuple(int(round(base[i] * (1 - alpha) + top[i] * alpha)) for i in range(3))


def render(size: int) -> bytes:
    """Render the icon at a given square size and return raw RGB bytes."""
    # Canvas units to output pixels.
    factor = size / CANVAS
    pixels = bytearray(size * size * 3)
    # Fixed supersampling in output pixel space, so every size gets the same
    # anti-aliasing quality.
    scale = SCALE

    # Background gradient, sampled per output pixel.
    for y in range(size):
        ratio = y / max(1, size - 1)
        row = blend(BACKGROUND_TOP, BACKGROUND_BOTTOM, ratio)
        for x in range(size):
            offset = (y * size + x) * 3
            pixels[offset:offset + 3] = bytes(row)

    def fill_rounded(left: float, top: float, right: float, bottom: float,
                     radius: float, colour: tuple[int, int, int]) -> None:
        """Fill a rounded rectangle with a supersampled, anti-aliased edge."""
        x0 = int(max(0, (left - 1) * factor))
        x1 = int(min(size, (right + 1) * factor))
        y0 = int(max(0, (top - 1) * factor))
        y1 = int(min(size, (bottom + 1) * factor))
        for py in range(y0, y1):
            for px in range(x0, x1):
                hits = 0
                for sy in range(scale):
                    for sx in range(scale):
                        ux = (px + (sx + 0.5) / scale) / factor
                        uy = (py + (sy + 0.5) / scale) / factor
                        if ux < left or ux > right or uy < top or uy > bottom:
                            continue
                        cx = min(max(ux, left + radius), right - radius)
                        cy = min(max(uy, top + radius), bottom - radius)
                        if (ux - cx) ** 2 + (uy - cy) ** 2 <= radius * radius:
                            hits += 1
                if not hits:
                    continue
                alpha = hits / (scale * scale)
                offset = (py * size + px) * 3
                current = (pixels[offset], pixels[offset + 1], pixels[offset + 2])
                pixels[offset:offset + 3] = bytes(blend(current, colour, alpha))

    for row, colours in enumerate(GRID):
        for column, colour in enumerate(colours):
            left = GRID_LEFT + column * (KEY_SIZE + KEY_GAP)
            top = GRID_TOP + row * (KEY_SIZE + KEY_GAP)
            fill_rounded(left, top, left + KEY_SIZE, top + KEY_SIZE, 42, colour)

    fill_rounded(GRID_LEFT, SPACE_TOP, GRID_LEFT + GRID_WIDTH,
                 SPACE_TOP + SPACE_HEIGHT, SPACE_HEIGHT / 2, WHITE)

    return bytes(pixels)


SIZES = [
    # iPhone slots.
    ("20x20", 20, 2, "iphone"), ("20x20", 20, 3, "iphone"),
    ("29x29", 29, 1, "iphone"), ("29x29", 29, 2, "iphone"), ("29x29", 29, 3, "iphone"),
    ("40x40", 40, 2, "iphone"), ("40x40", 40, 3, "iphone"),
    ("60x60", 60, 2, "iphone"), ("60x60", 60, 3, "iphone"),
    # iPad slots.
    ("20x20", 20, 1, "ipad"), ("20x20", 20, 2, "ipad"),
    ("29x29", 29, 1, "ipad"), ("29x29", 29, 2, "ipad"),
    ("40x40", 40, 1, "ipad"), ("40x40", 40, 2, "ipad"),
    ("76x76", 76, 1, "ipad"), ("76x76", 76, 2, "ipad"),
    ("83.5x83.5", 83.5, 2, "ipad"),
    # The App Store marketing icon.
    ("1024x1024", 1024, 1, "ios-marketing"),
]


def distinct_colours(pixels: bytes, size: int) -> set:
    seen = set()
    for index in range(0, len(pixels), 3):
        seen.add((pixels[index], pixels[index + 1], pixels[index + 2]))
    return seen


def check_rendered(pixels: bytes, size: int, name: str) -> None:
    """Refuse to ship a blank or flat icon.

    A flat render means the geometry was clipped out of the canvas, which is
    exactly the failure an inverted coordinate scale produces.
    """
    colours = distinct_colours(pixels, size)
    if len(colours) < 8:
        raise ValueError(f"{name} rendered flat with only {len(colours)} distinct colours")
    for accent in (PINK, CYAN, PURPLE, WHITE):
        if not any(abs(c[0] - accent[0]) < 24 and abs(c[1] - accent[1]) < 24 and abs(c[2] - accent[2]) < 24
                   for c in colours):
            raise ValueError(f"{name} is missing the accent colour {accent.hex() if hasattr(accent, 'hex') else accent}")


def main() -> int:
    CATALOG.mkdir(parents=True, exist_ok=True)
    APPICON.mkdir(parents=True, exist_ok=True)
    (CATALOG / "Contents.json").write_text(json.dumps({"info": {"author": "xcode", "version": 1}}, indent=2) + "\n")

    # The global accent colour, matching the console palette.
    accent = CATALOG / "AccentColor.colorset"
    accent.mkdir(parents=True, exist_ok=True)
    (accent / "Contents.json").write_text(json.dumps({
        "colors": [
            {"idiom": "universal",
             "appearances": [{"appearance": "luminosity", "value": "dark"}],
             "color": {"color-space": "srgb", "components": {"red": "0.961", "green": "0.259", "blue": "0.549", "alpha": "1.000"}}},
            {"idiom": "universal",
             "color": {"color-space": "srgb", "components": {"red": "0.961", "green": "0.259", "blue": "0.549", "alpha": "1.000"}}}
        ],
        "info": {"author": "xcode", "version": 1}
    }, indent=2) + "\n")

    images = []
    for idiom, points, scale, platform in SIZES:
        pixels = int(round(points * scale))
        name = f"AppIcon-{points:g}x{points:g}-{scale}x-{platform}.png"
        rendered = render(pixels)
        check_rendered(rendered, pixels, name)
        write_png(APPICON / name, pixels, pixels, rendered)
        images.append({
            "filename": name,
            "idiom": platform,
            "scale": f"{scale}x",
            "size": f"{points:g}x{points:g}",
        })

    (APPICON / "Contents.json").write_text(json.dumps(
        {"images": images, "info": {"author": "xcode", "version": 1}}, indent=2) + "\n")
    print(json.dumps({"catalog": str(CATALOG), "icons": len(images),
                      "bytes": sum((APPICON / image["filename"]).stat().st_size for image in images)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
