"""Ingestion is only offered when a provider can actually answer."""
import os
import asyncio
import json
import unittest
from unittest.mock import patch

from dynamic_mcp_server import DynamicMCPServer
from ecosystem_ingestion import _providers, available_providers, ingest


class IngestionTests(unittest.TestCase):
    def test_no_tool_without_a_credential(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(available_providers(), [])

    def test_a_configured_provider_is_offered_with_a_bound_handler(self):
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fixture-key"}, clear=True):
            rows = available_providers()
            self.assertEqual([row["name"] for row in rows], ["ingest_firecrawl"])
            server = DynamicMCPServer("data/tools-test.json")
            self.assertIn("ingest_firecrawl", server.tools)
            self.assertIn("ingest_firecrawl", server.handlers)

    def test_ingest_reports_a_missing_credential(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                ingest({"target": "https://example.test"})

    def test_ingest_requires_a_target(self):
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fixture-key"}, clear=True):
            with self.assertRaises(ValueError):
                ingest({})

    def test_every_configured_provider_names_its_credential_and_https_url(self):
        providers = _providers()
        self.assertTrue(providers)
        for name, spec in providers.items():
            self.assertIn("env", spec, name)
            self.assertIn("url", spec, name)
            self.assertTrue(spec["url"].startswith("https://"), name)

    def test_selected_provider_is_used_when_multiple_credentials_exist(self):
        credentials = {'FIRECRAWL_API_KEY': 'fc-fixture', 'TAVILY_API_KEY': 'tv-fixture', 'BROWSERLESS_TOKEN': 'bl-fixture'}
        with patch.dict(os.environ, credentials, clear=True), patch('ecosystem_ingestion.ProtocolIngestion.http', return_value={'data': 'fixture'}) as call:
            server = DynamicMCPServer('data/tools-test.json')
            for name, target, host in [('tavily', 'agent tools', 'api.tavily.com'),
                                       ('browserless', 'https://example.com', 'production-sfo.browserless.io'),
                                       ('firecrawl', 'https://example.com', 'api.firecrawl.dev')]:
                response = asyncio.run(server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                    'params': {'name': 'ingest_'+name, 'arguments': {'target': target}}}))
                self.assertNotIn('error', response)
                self.assertEqual(json.loads(response['result']['content'][0]['text'])['provider'], name)
                self.assertIn(host, call.call_args.args[0])

    def test_url_input_cannot_embed_credentials_or_non_https(self):
        with patch.dict(os.environ, {'FIRECRAWL_API_KEY': 'fixture'}, clear=True), patch('ecosystem_ingestion.ProtocolIngestion.http') as call:
            for url in ['http://example.com', 'https://user:password@example.com']:
                with self.assertRaises(ValueError): ingest({'target': url}, provider='firecrawl')
            call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
