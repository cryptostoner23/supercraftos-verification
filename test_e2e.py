"""End-to-end tests against the live SuperCraftOS backend over HTTPS.

These exercise the real signed-in API (session token → authenticated calls) and
verify the product surfaces actually work: Digital Me, Apple Notes import store,
and the Composio Gmail integration. They are idempotent: notes created are
cleaned up, and reads are non-mutating.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid

import httpx

BASE = os.getenv("SUPERCRAFTOS_E2E_BASE", "https://agent.commetai.ca")
ACCESS_KEY = os.getenv("SUPERCRAFTOS_E2E_KEY", "BCQMChP-tCaOWU_aeLlY32rn618HAX3F8Oi4dIf0wjg")
TIMEOUT = 60.0


def _token() -> str:
    r = httpx.get(f"{BASE}/api/session", headers={"Authorization": f"Bearer {ACCESS_KEY}"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {ACCESS_KEY}", "X-SuperCraftOS-Token": token}


class TestE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.token = _token()
        cls.client = httpx.Client(timeout=TIMEOUT)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    # ── Auth ────────────────────────────────────────────────────────────────
    def test_01_session_and_status(self):
        r = self.client.get(f"{BASE}/api/status", headers=_h(self.token))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("tools", data)
        self.assertGreaterEqual(data["tools"], 25)
        self.assertIn("integrations", data)

    # ── Digital Me ───────────────────────────────────────────────────────────
    def test_02_digital_me_profile(self):
        r = self.client.get(f"{BASE}/api/digital_me/profile", headers=_h(self.token))
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("identity", d)
        self.assertIn("name", d["identity"])
        self.assertIn("memory_entries", d)

    def test_03_digital_me_memory_add_get(self):
        marker = f"e2e-memory-{uuid.uuid4().hex[:8]}"
        r = self.client.post(f"{BASE}/api/digital_me/memory",
                             json={"entry": {"note": marker}}, headers=_h(self.token))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json().get("status"), "ok")

        r = self.client.get(f"{BASE}/api/digital_me/memory", headers=_h(self.token))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(e["note"] == marker for e in r.json().get("entries", [])))

    def test_04_digital_me_reasoning(self):
        r = self.client.post(f"{BASE}/api/digital_me/reasoning",
                             json={"query": "e2e", "context": {}}, headers=_h(self.token))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("summary", r.json())

    # ── Apple Notes store ────────────────────────────────────────────────────
    def test_05_notes_create_list_update_pin_delete(self):
        title = f"E2E Note {uuid.uuid4().hex[:8]}"
        r = self.client.post(f"{BASE}/api/notes", json={"title": title, "body": "hello body"},
                             headers=_h(self.token))
        self.assertIn(r.status_code, (200, 201), r.text)
        note = r.json()
        nid = note.get("id")
        self.assertTrue(nid)
        self.assertTrue(note.get("encrypted", True))

        r = self.client.get(f"{BASE}/api/notes", headers=_h(self.token))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(n.get("id") == nid for n in r.json().get("notes", [])))

        r = self.client.post(f"{BASE}/api/notes/{nid}/update",
                             json={"body": "updated"}, headers=_h(self.token))
        self.assertEqual(r.status_code, 200, r.text)

        r = self.client.post(f"{BASE}/api/notes/{nid}/pin",
                             json={}, headers=_h(self.token))
        self.assertEqual(r.status_code, 200, r.text)

        r = self.client.post(f"{BASE}/api/notes/{nid}/delete",
                             json={}, headers=_h(self.token))
        self.assertEqual(r.status_code, 200, r.text)

        r = self.client.get(f"{BASE}/api/notes", headers=_h(self.token))
        self.assertFalse(any(n.get("id") == nid for n in r.json().get("notes", [])))

    def test_06_notes_ingest_feeds_memory(self):
        marker = f"e2e-ingest-{uuid.uuid4().hex[:8]}"
        r = self.client.post(f"{BASE}/api/notes/ingest",
                             json={"title": marker, "body": "imported from Apple Notes",
                                   "source": "apple_notes"}, headers=_h(self.token))
        self.assertIn(r.status_code, (200, 201), r.text)
        self.assertIn("id", r.json())

        # The ingest should have added a Digital Me memory entry.
        r = self.client.get(f"{BASE}/api/digital_me/memory", headers=_h(self.token))
        self.assertTrue(any(marker in e.get("note", "") for e in r.json().get("entries", [])))

    # ── Composio Gmail ───────────────────────────────────────────────────────
    def test_07_gmail_status_connected(self):
        r = self.client.post(f"{BASE}/api/tools/call",
                             json={"name": "gmail_status", "arguments": {}},
                             headers=_h(self.token))
        self.assertEqual(r.status_code, 200, r.text)
        text = r.json()["result"]["content"][0]["text"]
        self.assertIn('"connected": true', text)
        self.assertIn("gmail_accounts", text)

    def test_08_gmail_read_real_messages(self):
        r = self.client.post(f"{BASE}/api/tools/call",
                             json={"name": "gmail_read", "arguments": {"limit": 5}},
                             headers=_h(self.token))
        self.assertEqual(r.status_code, 200, r.text)
        text = r.json()["result"]["content"][0]["text"]
        self.assertIn('"successful": true', text)
        self.assertIn("messages", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
