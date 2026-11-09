import unittest

from grant_registry import draft_application, load_registry, screen_opportunities


class GrantRegistryTests(unittest.TestCase):
    def test_official_registry_has_source_and_application_for_every_program(self):
        programs = load_registry()["programs"]
        self.assertGreaterEqual(len(programs), 4)
        for program in programs:
            self.assertTrue(program["official_url"].startswith("https://"))
            self.assertTrue(program["application_url"].startswith("https://"))
            self.assertTrue(program["source_url"].startswith("https://"))

    def test_screening_is_deterministic_and_ranks_public_goods(self):
        rows = screen_opportunities({"name": "SuperCraftOS", "description": "open-source Ethereum developer tooling and public goods", "network": "Ethereum", "license": "MIT", "category": "infrastructure"})
        self.assertEqual(rows[0]["program_id"], "ethereum-esp")
        self.assertTrue(all(row["requires_live_verification"] for row in rows))
        self.assertTrue(any(row["program_id"] == "circle-developer-grants" for row in rows))

    def test_draft_exposes_readiness_without_unconditional_gate(self):
        draft = draft_application("gitcoin-grants", {"name": "x"})
        self.assertFalse(draft["ready_for_submission"])
        self.assertTrue(draft["missing_fields"])
        complete = draft_application("gitcoin-grants", {"name": "x", "description": "y", "deliverables": ["z"], "milestones": ["m"], "budget": 1000})
        self.assertTrue(complete["ready_for_submission"])
        self.assertEqual(complete["submission_surface"], "allo_protocol")


if __name__ == "__main__":
    unittest.main()
