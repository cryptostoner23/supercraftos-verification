"""Tests for the XcodeGen spec toggler that activates the keyboard dependency."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("xcode_project", ROOT / "scripts" / "xcode_project.py")
toggler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(toggler)

SPEC = ROOT / "ios_app_dist" / "ci_xcode" / "project.yml"


class XcodeProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SPEC.read_text()

    def test_spec_carries_the_marker_block(self) -> None:
        self.assertIn(toggler.BEGIN, self.text)
        self.assertIn(toggler.END, self.text)

    def test_default_spec_does_not_embed_the_keyboard(self) -> None:
        self.assertIn('deploymentTarget: "17.0"', self.text.split("SuperCraftOSKeyboard:")[0])
        activated = toggler.activate(self.text)
        self.assertIn("target: SuperCraftOSKeyboard", activated)
        self.assertIn("embed: true", activated)
        # The dependency must sit on the app target, not the extension target.
        app_block = activated.split("SuperCraftOSKeyboard:")[0]
        self.assertIn("embed: true", app_block)
        self.assertIn('deploymentTarget: "26.0"', app_block)

    def test_activation_is_idempotent(self) -> None:
        once = toggler.activate(self.text)
        twice = toggler.activate(once)
        self.assertEqual(once, twice)

    def test_activation_does_not_touch_the_extension_target(self) -> None:
        activated = toggler.activate(self.text)
        extension_block = activated.split("SuperCraftOSKeyboard:")[1]
        self.assertNotIn("embed: true", extension_block)

    def test_marker_block_is_unique(self) -> None:
        self.assertEqual(self.text.count(toggler.BEGIN), 1)
        self.assertEqual(self.text.count(toggler.END), 1)

    def test_missing_marker_is_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            toggler.activate("name: X\n")


if __name__ == "__main__":
    unittest.main()
