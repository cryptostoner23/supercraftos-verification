"""Tests for the repository secret scanner (scripts/audit_repository.py).

These verify the scanner is both precise and strict: it must flag real
committed credentials (hardcoded provider keys, the previously leaked gateway
key pattern, opaque credential values) while ignoring the benign code, test
fixtures and documentation that previously produced false positives.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_audit():
    path = ROOT / "scripts" / "audit_repository.py"
    spec = importlib.util.spec_from_file_location("audit_repository", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = _load_audit()


def _scan(text: str):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "sample.py"
        path.write_text(text)
        return AUDIT.scan_for_secrets(path, text)


class AuditPrecisionTests(unittest.TestCase):
    def test_detects_hardcoded_provider_key(self):
        # The victim literal is assembled at runtime so the test file itself does
        # not contain a contiguous credential value for the scanner to flag.
        key = "sk-ant-" + "abcdefghijklmnopqrstuvwxyz1234567890"
        issues = _scan(f'OPENROUTER_API_KEY="{key}"\n')
        checks = [i["check"] for i in issues]
        self.assertIn("potential_secret_hardcoded_provider_key", checks)

    def test_detects_leaked_gateway_key_pattern(self):
        banned = "BCQM" + "ChP" + "A" * 30
        issues = _scan(f'TOKEN="{banned}"\n')
        checks = [i["check"] for i in issues]
        self.assertIn("potential_secret_leaked_gateway_key", checks)

    def test_detects_opaque_credential_value(self):
        # 56-character mixed-alphanumeric opaque value (>= 40-char threshold).
        value = "aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5zA7B8cD9eF0gH1"
        issues = _scan(f'BEARER_TOKEN = "{value}"\n')
        checks = [i["check"] for i in issues]
        self.assertIn("potential_secret_opaque_token", checks)

    def test_ignores_benign_code_and_fixtures(self):
        source = (
            'reason = "hosted_or_self_hosted_source_not_auto_installable"\n'
            'url = "https://gateway.thegraph.com/api/subgraphs/id/'
            '5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"\n'
            'name = "SuperCraftOS-iOS-Device-WithKeyboard-unsigned.ipa"\n'
            'doc = "REVYL_API_KEY=\'<key>\'"\n'
            'environ={"SUPERCRAFTOS_GRANT_ENDPOINT_ETHEREUM_ESP": '
            '"https://evil.example/submit"}\n'
            'secret = "another-password-that-must-not-be-logged"\n'
        )
        self.assertEqual(_scan(source), [])

    def test_ignores_bad_placeholder_and_interpolation_keys(self):
        # A placeholder or ${...} interpolation is not a committed credential.
        self.assertEqual(_scan('REVYL_API_KEY=\'<key>\'\n'), [])
        self.assertEqual(_scan('FIRECRAWL_API_KEY=\'${OTHER_TOKEN}\'\n'), [])


if __name__ == "__main__":
    unittest.main()
