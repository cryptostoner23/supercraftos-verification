#!/usr/bin/env python3
"""Generate the Xcode project from the single XcodeGen spec.

The spec carries a marked block for the keyboard extension dependency. The
block is inactive by default, so the app ships standalone. Passing
`--embed-keyboard` activates it, which produces the full app with the custom
keyboard embedded.

Keeping one spec means the two configurations cannot drift apart.

Usage:
    python3 scripts/xcode_project.py                      # standalone app
    python3 scripts/xcode_project.py --embed-keyboard     # app with the keyboard
    python3 scripts/xcode_project.py --embed-keyboard --spec ios_app_dist/ci_xcode/project.yml
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = ROOT / "ios_app_dist" / "ci_xcode" / "project.yml"

BEGIN = "# BEGIN KEYBOARD DEPENDENCY"
END = "# END KEYBOARD DEPENDENCY"

ACTIVE_BLOCK = """    dependencies:
      - target: SuperCraftOSKeyboard
        embed: true
        codeSign: false
"""

APP_DEPLOYMENT = '    deploymentTarget: "17.0"'
EMBEDDED_APP_DEPLOYMENT = '    deploymentTarget: "26.0"'


def activate(text: str) -> str:
    """Turn the marked keyboard dependency block on."""
    pattern = re.compile(
        re.escape(BEGIN) + r".*?" + re.escape(END),
        re.S,
    )
    if not pattern.search(text):
        raise SystemExit(
            f"the spec {DEFAULT_SPEC} has no {BEGIN} ... {END} block; "
            "the keyboard dependency cannot be activated"
        )
    block = "\n".join([
        BEGIN,
        "    # Activated by scripts/xcode_project.py --embed-keyboard.",
        ACTIVE_BLOCK.rstrip(),
        END,
    ])
    activated = pattern.sub(lambda _: block, text, count=1)
    app, separator, remainder = activated.partition("  SuperCraftOSKeyboard:")
    if not separator:
        raise SystemExit("the app target cannot be separated from the keyboard target")
    if APP_DEPLOYMENT in app:
        app = app.replace(APP_DEPLOYMENT, EMBEDDED_APP_DEPLOYMENT, 1)
    elif EMBEDDED_APP_DEPLOYMENT not in app:
        raise SystemExit("the app target has no supported deployment target for the embedded keyboard")
    return app + separator + remainder


def generate(spec: Path, embed_keyboard: bool, output: Path | None) -> Path:
    text = spec.read_text()
    if embed_keyboard:
        text = activate(text)
    if output is None:
        output = spec.with_suffix(".resolved.yml")
    output.write_text(text)
    if not shutil_which("xcodegen"):
        raise SystemExit("xcodegen is not installed: brew install xcodegen")
    subprocess.run(["xcodegen", "generate", "--spec", str(output)], check=True, cwd=str(spec.parent))
    return spec.parent / "SuperCraftOS.xcodeproj"


def shutil_which(command: str) -> str | None:
    import shutil
    return shutil.which(command)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", default=str(DEFAULT_SPEC))
    parser.add_argument("--embed-keyboard", action="store_true",
                        help="embed the custom keyboard extension in the app")
    parser.add_argument("--keep-spec", action="store_true",
                        help="keep the resolved spec file next to the original")
    args = parser.parse_args()

    spec = Path(args.spec).resolve()
    output = None if args.keep_spec else spec.with_suffix(".resolved.yml")
    project = generate(spec, args.embed_keyboard, output)
    print(f"generated {project} (keyboard embedded: {args.embed_keyboard})")
    if output is not None and output.exists():
        output.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
