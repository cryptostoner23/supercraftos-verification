"""Offline regressions for the merged native client's reproducible source archive."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('package_ipad', ROOT / 'scripts/package_ipad.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class PlaygroundPackageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.dist = self.root / 'ios_app_dist'
        self.bundle = self.dist / 'YourApp.swiftpm'
        self.bundle.mkdir(parents=True)
        self.catalog = self.root / 'swift-verification/Sources/ControlCore/KeyboardCatalog.swift'
        self.catalog.parent.mkdir(parents=True)
        shutil.copyfile(packager.CATALOG, self.catalog)
        for source in (ROOT / 'ios_app_dist').glob('*.swift'):
            shutil.copyfile(source, self.dist / source.name)
        for name in ('App.swift', 'Package.swift'):
            shutil.copyfile(ROOT / 'ios_app_dist/YourApp.swiftpm' / name, self.bundle / name)
        self.patcher = patch.multiple(packager, ROOT=self.root, DIST=self.dist, BUNDLE=self.bundle, CATALOG=self.catalog)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def package(self):
        with contextlib.redirect_stdout(io.StringIO()):
            packager.main()
        return (self.dist / 'YourApp.swiftpm.zip').read_bytes()

    def test_all_native_sources_and_shared_catalog_are_packaged_identically(self):
        self.package()
        with zipfile.ZipFile(self.dist / 'YourApp.swiftpm.zip') as archive:
            for source in self.dist.glob('*.swift'):
                self.assertEqual(archive.read('YourApp.swiftpm/' + source.name), source.read_bytes())
            self.assertEqual(archive.read('YourApp.swiftpm/KeyboardCatalog.swift'), self.catalog.read_bytes())
            for name in packager.CORE:
                self.assertEqual((self.catalog.parent / name).read_bytes(), (self.dist / name).read_bytes())

    def test_archive_ignores_source_mtime_and_permissions(self):
        before = self.package()
        for source in self.bundle.glob('*.swift'):
            os.utime(source, (1, 1)); source.chmod(0o600)
        self.assertEqual(before, self.package())

    def test_removed_source_is_not_left_in_the_playground_target(self):
        stale = self.bundle / 'RemovedFeature.swift'
        stale.write_text('struct RemovedFeature {}\n')
        self.package()
        self.assertFalse(stale.exists())

    def test_invalid_catalog_does_not_replace_the_delivered_archive(self):
        before = self.package()
        self.catalog.write_bytes(b'invalid\r\n')
        with self.assertRaises(ValueError):
            self.package()
        self.assertEqual((self.dist / 'YourApp.swiftpm.zip').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
