"""Core release checks. Run in a disposable checkout with networking disabled.

CAD generation is skipped in the core image; installation-state checks still run.
Pass --with-cad after installing requirements-cad.lock into .cad-venv to enable it.
Real Docker sandbox tests separately require SUPERCRAFTOS_TEST_DOCKER=1.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
CAD_TESTS = {
    "test_product_api.ProductAPITests.test_all_three_templates_generate_real_files",
}


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-cad", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    os.umask(0o077)
    sys.path.insert(0, str(ROOT))
    (ROOT / "data").mkdir(exist_ok=True, mode=0o700)

    # Compile sources without writing bytecode or importing optional components.
    paths = [*ROOT.glob("*.py"), *ROOT.glob("scripts/*.py"), Path(__file__)]
    for path in paths:
        compile(path.read_text(encoding="utf-8"), str(path), "exec", dont_inherit=True)
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    subprocess.run([sys.executable, "main.py", "doctor"], check=True)

    suite = unittest.defaultTestLoader.discover(str(ROOT), pattern="test*.py")
    if not args.with_cad:
        for case in cases(suite):
            if case.id() in CAD_TESTS:
                method = getattr(type(case), case._testMethodName)
                setattr(type(case), case._testMethodName, unittest.skip(
                    "Optional CAD installation: rerun with --with-cad and .cad-venv"
                )(method))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
