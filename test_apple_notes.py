"""Offline invariants for the Apple Notes-style encrypted notes store.

No live secrets are read or written: a throwaway key and note files are created
inside a TemporaryDirectory with apple_notes.ROOT patched. The tests exercise the
full store API used by the HTTP routes without touching the real data directory.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import apple_notes


class AppleNotesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(apple_notes, "ROOT", Path(self._tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_key_is_created_with_0400_permissions(self):
        key_path = Path(self._tmp.name) / "data" / "notes.key"
        self.assertFalse(key_path.exists())
        apple_notes.create_note("First", "body")
        self.assertTrue(key_path.exists())
        self.assertEqual(key_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(key_path.read_bytes()), 32)

    def test_create_list_get_roundtrip(self):
        note = apple_notes.create_note("Groceries", "Milk, eggs", notebook="Home", tags=["errand"])
        self.assertTrue(note["id"])
        self.assertEqual(note["title"], "Groceries")
        self.assertEqual(note["body"], "Milk, eggs")
        self.assertEqual(note["notebook"], "Home")
        self.assertEqual(note["tags"], ["errand"])
        self.assertFalse(note["pinned"])

        notes = apple_notes.list_notes()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["title"], "Groceries")
        self.assertEqual(notes[0]["checklist_items"], 0)
        # list metadata never includes body
        self.assertNotIn("body", notes[0])

        fetched = apple_notes.get_note(note["id"])
        self.assertEqual(fetched["body"], "Milk, eggs")

    def test_list_query_filters(self):
        apple_notes.create_note("Alpha", "one", notebook="Home", tags=["work"])
        apple_notes.create_note("Beta", "two", notebook="Ideas", tags=["fun"])
        self.assertEqual(len(apple_notes.list_notes("alpha")), 1)
        self.assertEqual(len(apple_notes.list_notes("ideas")), 1)  # notebook match
        self.assertEqual(len(apple_notes.list_notes("fun")), 1)      # tag match
        self.assertEqual(len(apple_notes.list_notes("mkdir")), 0)

    def test_update_patches_fields(self):
        note = apple_notes.create_note("Title", "body")
        updated = apple_notes.update_note(note["id"], {"title": "Renamed", "tags": ["a", "b"]})
        self.assertEqual(updated["title"], "Renamed")
        self.assertEqual(updated["tags"], ["a", "b"])
        self.assertEqual(updated["body"], "body")
        self.assertIsInstance(updated["updated_at"], int)

    def test_checklist_add_and_toggle(self):
        note = apple_notes.create_note("List", "")
        with_item = apple_notes.add_checklist_item(note["id"], "Buy milk")
        self.assertEqual(len(with_item["checklist"]), 1)
        self.assertEqual(with_item["checklist"][0]["text"], "Buy milk")
        self.assertFalse(with_item["checklist"][0]["checked"])
        toggled = apple_notes.toggle_checklist_item(note["id"], 0)
        self.assertTrue(toggled["checklist"][0]["checked"])
        with self.assertRaises(ValueError):
            apple_notes.toggle_checklist_item(note["id"], 5)

    def test_pin_toggles_and_sorts_first(self):
        a = apple_notes.create_note("first")
        apple_notes.create_note("second")
        pinned = apple_notes.pin_note(a["id"])
        self.assertTrue(pinned["pinned"])
        notes = apple_notes.list_notes()
        self.assertEqual(notes[0]["id"], a["id"])
        self.assertTrue(notes[0]["pinned"])

    def test_notebooks_and_delete(self):
        apple_notes.create_note("A", notebook="Work")
        apple_notes.create_note("B", notebook="Work")
        apple_notes.create_note("C", notebook="Personal")
        notebooks = apple_notes.list_notebooks()
        by_name = {nb["notebook"]: nb for nb in notebooks}
        self.assertEqual(by_name["Work"]["count"], 2)
        self.assertEqual(by_name["Personal"]["count"], 1)

        note = apple_notes.create_note("doomed")
        deleted = apple_notes.delete_note(note["id"])
        self.assertTrue(deleted["deleted"])
        self.assertIsNone(apple_notes.get_note(note["id"]))
        with self.assertRaises(KeyError):
            apple_notes.delete_note(note["id"])

    def test_validation(self):
        with self.assertRaises(ValueError):
            apple_notes.create_note("")
        with self.assertRaises(ValueError):
            apple_notes.create_note("x" * 201)
        with self.assertRaises(KeyError):
            apple_notes.update_note("missing", {"title": "x"})


if __name__ == "__main__":
    unittest.main()
