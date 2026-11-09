"""End-to-end suite (25 journeys) against the live SuperCraftOS backend over HTTPS.

Each journey maps to a product surface / user story from REVYL_TESTING.md.
All tests use the real signed-in API (session token) and are idempotent:
notes/memory created here are minimized, reads are non-mutating, and no
external side effects (email send, funding submission, CAD) are triggered.
"""
from __future__ import annotations

import os
import uuid
import unittest

import httpx

BASE = os.getenv("SUPERCRAFTOS_E2E_BASE", "https://agent.commetai.ca")
# The gateway key is a live credential: it is never committed. Rotate it by
# deleting data/access.key on the server and restarting private_gateway.py.
ACCESS_KEY = os.getenv("SUPERCRAFTOS_E2E_KEY", "")
TIMEOUT = 60.0


def _token() -> str:
    r = httpx.get(f"{BASE}/api/session", headers={"Authorization": f"Bearer {ACCESS_KEY}"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {ACCESS_KEY}", "X-SuperCraftOS-Token": token}


def _tool(token, name, args):
    r = httpx.post(f"{BASE}/api/tools/call",
                   json={"name": name, "arguments": args}, headers=_h(token), timeout=90)
    return r.json()["result"]["content"][0]["text"]


class TestE2E25(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ACCESS_KEY:
            raise unittest.SkipTest(
                "Set SUPERCRAFTOS_E2E_KEY (live gateway access key from data/access.key) to run this suite.")
        cls.token = _token()
        cls.c = httpx.Client(timeout=TIMEOUT, headers=_h(cls.token))

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    # 01 auth session
    def test_01_auth_session(self):
        self.assertTrue(self.token)

    # 02 status / runtime
    def test_02_status(self):
        r = self.c.get(f"{BASE}/api/status")
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertIn("tools", d)
        self.assertIn("integrations", d)

    # 03 tool inventory
    def test_03_tools(self):
        r = self.c.get(f"{BASE}/api/tools")
        self.assertEqual(r.status_code, 200)
        names = [t["name"] for t in r.json()["tools"]]
        self.assertGreaterEqual(len(names), 25)
        self.assertIn("gmail_read", names)

    # 04 integrations health
    def test_04_integrations(self):
        r = self.c.get(f"{BASE}/api/integrations")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json()["integrations"], list)

    # 05 registrations / accounts
    def test_05_registrations(self):
        r = self.c.get(f"{BASE}/api/registrations")
        self.assertEqual(r.status_code, 200)
        r2 = self.c.get(f"{BASE}/api/accounts")
        self.assertIn(r2.status_code, (200, 503))

    # 06 workflows list
    def test_06_workflows(self):
        r = self.c.get(f"{BASE}/api/workflows")
        self.assertEqual(r.status_code, 200)
        self.assertIn("workflows", r.json())

    # 07 platforms / capabilities
    def test_07_platforms(self):
        r = self.c.get(f"{BASE}/api/capabilities")
        self.assertIn(r.status_code, (200, 503))
        r2 = self.c.get(f"{BASE}/api/platforms")
        self.assertIn(r2.status_code, (200, 503))

    # 08 quests sources + leads
    def test_08_quests(self):
        for path in ("/api/quests/sources", "/api/quests/leads"):
            r = self.c.get(f"{BASE}{path}")
            self.assertIn(r.status_code, (200, 503))

    # 09 jobs inventory
    def test_09_jobs(self):
        r = self.c.get(f"{BASE}/api/jobs")
        self.assertEqual(r.status_code, 200)
        self.assertIn("jobs", r.json())

    # 10 agent status
    def test_10_agent_status(self):
        r = self.c.get(f"{BASE}/api/agent/status")
        self.assertEqual(r.status_code, 200)
        self.assertIn("workers", r.json())

    # 11 agent execution memory
    def test_11_agent_memory(self):
        r = self.c.get(f"{BASE}/api/agent/memory")
        self.assertEqual(r.status_code, 200)
        self.assertIn("playbooks", r.json())

    # 12 Digital Me profile / identity
    def test_12_digitalme_profile(self):
        r = self.c.get(f"{BASE}/api/digital_me/profile")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("identity", d)
        self.assertIn("memory_entries", d)

    # 13 Digital Me memory add + retrieve
    def test_13_digitalme_memory(self):
        marker = f"e2e-mem-{uuid.uuid4().hex[:8]}"
        r = self.c.post(f"{BASE}/api/digital_me/memory", json={"entry": {"note": marker}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json().get("status"), "ok")
        r = self.c.get(f"{BASE}/api/digital_me/memory")
        self.assertTrue(any(e["note"] == marker for e in r.json().get("entries", [])))

    # 14 Digital Me reasoning
    def test_14_digitalme_reasoning(self):
        r = self.c.post(f"{BASE}/api/digital_me/reasoning", json={"query": "e2e", "context": {}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("summary", r.json())

    # 15 Digital Me planning endpoint
    def test_15_digitalme_planning(self):
        r = self.c.post(f"{BASE}/api/digital_me/planning",
                        json={"playbook_id": "missing", "context": {}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(("playbook_id" in r.json()) or ("error" in r.json()))

    # 16 notes create + encrypted + list
    def test_16_notes_create(self):
        title = f"E2E {uuid.uuid4().hex[:8]}"
        r = self.c.post(f"{BASE}/api/notes", json={"title": title, "body": "secret body"})
        self.assertIn(r.status_code, (200, 201), r.text)
        nid = r.json()["id"]
        self.assertTrue(nid)
        r = self.c.get(f"{BASE}/api/notes")
        self.assertTrue(any(n.get("id") == nid for n in r.json().get("notes", [])))
        self.c.post(f"{BASE}/api/notes/{nid}/delete", json={})

    # 17 notes update
    def test_17_notes_update(self):
        r = self.c.post(f"{BASE}/api/notes", json={"title": "upd", "body": "a"})
        nid = r.json()["id"]
        r = self.c.post(f"{BASE}/api/notes/{nid}/update", json={"body": "changed"})
        self.assertEqual(r.status_code, 200, r.text)
        r = self.c.get(f"{BASE}/api/notes/{nid}")
        self.assertEqual(r.json().get("body"), "changed")
        self.c.post(f"{BASE}/api/notes/{nid}/delete", json={})

    # 18 notes pin/unpin
    def test_18_notes_pin(self):
        r = self.c.post(f"{BASE}/api/notes", json={"title": "pin", "body": "x"})
        nid = r.json()["id"]
        self.c.post(f"{BASE}/api/notes/{nid}/pin", json={})
        r = self.c.get(f"{BASE}/api/notes/{nid}")
        self.assertTrue(r.json().get("pinned"))
        self.c.post(f"{BASE}/api/notes/{nid}/delete", json={})

    # 19 notes notebook listing
    def test_19_notes_notebooks(self):
        r = self.c.get(f"{BASE}/api/notes/notebooks")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsInstance(r.json().get("notebooks", []), list)

    # 20 notes checklist add/toggle
    def test_20_notes_checklist(self):
        r = self.c.post(f"{BASE}/api/notes", json={"title": "cl", "body": ""})
        nid = r.json()["id"]
        r = self.c.post(f"{BASE}/api/notes/{nid}/checklist/add", json={"text": "step1"})
        self.assertEqual(r.status_code, 200, r.text)
        idx = r.json().get("added") if "added" in r.json() else 0
        self.c.post(f"{BASE}/api/notes/{nid}/checklist/toggle", json={"index": idx})
        self.c.post(f"{BASE}/api/notes/{nid}/delete", json={})

    # 21 notes ingest feeds Digital Me memory
    def test_21_notes_ingest(self):
        marker = f"e2e-ingest-{uuid.uuid4().hex[:8]}"
        r = self.c.post(f"{BASE}/api/notes/ingest",
                        json={"title": marker, "body": "imported",
                              "source": "apple_notes"})
        self.assertIn(r.status_code, (200, 201), r.text)
        r = self.c.get(f"{BASE}/api/digital_me/memory")
        self.assertTrue(any(marker in e.get("note", "") for e in r.json().get("entries", [])))

    # 22 Gmail connection status
    def test_22_gmail_status(self):
        text = _tool(self.token, "gmail_status", {})
        self.assertIn('"connected": true', text)
        self.assertIn("gmail_accounts", text)

    # 23 Gmail real read
    def test_23_gmail_read(self):
        text = _tool(self.token, "gmail_read", {"limit": 5})
        self.assertIn('"successful": true', text)
        self.assertIn("messages", text)

    # 24 grant catalog
    def test_24_grants_catalog(self):
        r = self.c.get(f"{BASE}/api/grants/catalog")
        self.assertIn(r.status_code, (200, 503))

    # 25 product design interpret/screen
    def test_25_product_design(self):
        r = self.c.post(f"{BASE}/api/products/interpret", json={"idea": "a small desk lamp"})
        self.assertIn(r.status_code, (200, 400, 503))


if __name__ == "__main__":
    unittest.main(verbosity=2)
