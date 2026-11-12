import json
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from grant_workflow import grant_catalog, screen_grants, draft_grant_application, approve_grant_application
from dynamic_mcp_server import DynamicMCPServer


PROFILE = {
    "project_name": "Open Resolver",
    "summary": "Open source Ethereum infrastructure and public goods developer tooling.",
    "topics": ["infrastructure", "public goods"],
    "chains": ["Ethereum"],
    "repository_url": "https://github.com/example/resolver",
    "milestones": ["Publish threat model", "Release testnet integration"],
    "budget_usd": 25000,
}


class GrantWorkflowTests(unittest.TestCase):
    def test_catalog_is_official_and_requires_refresh(self):
        result = grant_catalog()
        self.assertTrue(result["requires_live_verification"])
        self.assertGreaterEqual(len(result["programs"]), 4)
        for row in result["programs"]:
            self.assertTrue(row["official_url"].startswith("https://"))
            self.assertNotIn("source_checked_at", row)
            self.assertIn("funding_type", row)

    def test_non_grant_benefits_are_not_described_as_grants(self):
        result = screen_grants({"profile": PROFILE, "program_ids": ["aws-activate", "base-ecosystem-fund", "nvidia-inception", "arbitrum-arbifuel"]})
        rows = {row["program"]["id"]: row for row in result["results"]}
        self.assertEqual(rows["aws-activate"]["program"]["funding_type"], "infrastructure_credits")
        self.assertIn("not cash revenue", rows["aws-activate"]["monetization"]["caveat"])
        self.assertEqual(rows["base-ecosystem-fund"]["program"]["funding_type"], "equity_investment")
        self.assertIn("not a grant", rows["base-ecosystem-fund"]["monetization"]["caveat"])
        self.assertEqual(rows["nvidia-inception"]["program"]["funding_type"], "startup_benefits")
        self.assertEqual(rows["arbitrum-arbifuel"]["program"]["funding_type"], "usage_subsidy")

    def test_screen_has_evidence_and_monetization(self):
        result = screen_grants({"profile": PROFILE})
        self.assertEqual(result["results"][0]["program"]["id"], "ethereum-esp")
        self.assertTrue(result["results"][0]["evidence"])
        self.assertTrue(result["results"][0]["monetization"]["paths"])

    def test_draft_and_readiness_preserve_adapter_status(self):
        with tempfile.TemporaryDirectory() as directory, patch("grant_workflow.STORE", Path(directory)):
            package = draft_grant_application({"profile": PROFILE, "program_id": "ethereum-esp"})
            self.assertEqual(package["status"], "draft")
            self.assertFalse(package["submission"]["enabled"])
            self.assertIn("contact_email", package["missing_information"])
            self.assertEqual(package["draft"]["public_goods_case"], "")
            self.assertEqual(package["draft"]["project_summary"], PROFILE["summary"])
            approved = approve_grant_application({"package_id": package["id"]})
            self.assertEqual(approved["status"], "ready_for_submission")
            self.assertFalse(approved["submission"]["enabled"])

    def test_draft_uses_provided_application_evidence(self):
        complete = dict(PROFILE, problem="High resolver integration cost",
                        solution="Publish a resolver reference implementation",
                        public_goods_case="Open source contracts and reproducible tests",
                        use_of_funds="Developer time and independent audit",
                        contact_email="team@example.org", success_metrics=["Two independent integrations"])
        with tempfile.TemporaryDirectory() as directory, patch("grant_workflow.STORE", Path(directory)):
            package = draft_grant_application({"profile": complete, "program_id": "ethereum-esp"})
            self.assertEqual(package["missing_information"], [])
            self.assertEqual(package["draft"]["use_of_funds"], complete["use_of_funds"])
            self.assertEqual(package["draft"]["success_metrics"], complete["success_metrics"])

    def test_mcp_tools_and_schema_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            server = DynamicMCPServer(Path(directory) / "tools.json")
            names = {row["name"] for row in server.tools.values()}
            self.assertTrue({"list_blockchain_grants", "screen_blockchain_grants", "draft_grant_application", "approve_grant_application"} <= names)
            response = asyncio.run(server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "screen_blockchain_grants", "arguments": {"profile": PROFILE}}}))
            self.assertIn("content", response["result"])


if __name__ == "__main__":
    unittest.main()
