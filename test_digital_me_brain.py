"""Digital Me brain tests: notes ingestion, synthesis, proactive action."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import digital_me_brain as brain


class BrainTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        # Redirect the brain + notes store into a temp dir.
        self._brain_orig = brain.ROOT
        brain.ROOT = self.root
        patch.object(brain, "ROOT", self.root).start()
        # Ensure the notes dir is fresh and keyed to the temp root.
        import apple_notes
        patch.object(apple_notes, "ROOT", self.root).start()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(patch.stopall)

    def test_ingest_is_idempotent(self):
        from apple_notes import create_note
        create_note(title="Lunch", body="Take client to Sushi next Tuesday", notebook="Work")
        result = brain._notes_data()
        self.assertEqual(len(result), 1)
        # run twice; second run should skip existing
        asyncio_local = __import__("asyncio")
        first = asyncio_local.run(brain.ingest_notes())
        second = asyncio_local.run(brain.ingest_notes())
        self.assertEqual(first["ingested"], 1)
        self.assertEqual(second["ingested"], 0)
        self.assertEqual(second["skipped_existing"], 1)

    def test_understanding_is_json_object(self):
        asyncio_local = __import__("asyncio")
        # Without a configured model, synthesis should degrade gracefully to {}.
        with patch.object(brain, "_llm", new=lambda *a, **k: "{}"):
            result = asyncio_local.run(brain.synthesize_understanding())
        self.assertIsInstance(result["understanding"], dict)

    def test_proactive_escalates_without_auto_intent(self):
        asyncio_local = __import__("asyncio")
        with patch.object(brain, "_llm", new=lambda *a, **k: '{"action": null, "confidence": 0.1}'):
            result = asyncio_local.run(brain.proactive_step())
        self.assertIn(result["status"], {"idle", "needs_attention"})


if __name__ == "__main__":
    unittest.main()
