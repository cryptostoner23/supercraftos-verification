import json
import tempfile
import unittest
from pathlib import Path

from grant_submission import SubmissionError, is_official_url, submit_package, submission_history


PROGRAM = {
    "id": "ethereum-esp",
    "official_url": "https://esp.ethereum.foundation/applicants",
    "application_url": "https://esp.ethereum.foundation/applicants",
}
PACKAGE = {"id": "pkg-1", "program_id": "ethereum-esp", "draft": {"title": "Resolver"}, "evidence": []}


class Response:
    status = 201
    def geturl(self): return "https://esp.ethereum.foundation/api/applications"
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit=-1): return json.dumps({"receipt": "accepted", "application_id": "a-1"}).encode()


class GrantSubmissionTests(unittest.TestCase):
    def test_allowlist_rejects_subdomain_and_query_credentials(self):
        self.assertTrue(is_official_url("https://esp.ethereum.foundation/applicants", PROGRAM))
        self.assertFalse(is_official_url("https://evil.example/submit", PROGRAM))
        self.assertFalse(is_official_url("https://esp.ethereum.foundation@evil.example/submit", PROGRAM))
        self.assertFalse(is_official_url("http://esp.ethereum.foundation/applicants", PROGRAM))

    def test_unsupported_surface_is_durable_and_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            result = submit_package(PACKAGE, PROGRAM, store_root=Path(directory), environ={})
            self.assertEqual(result["status"], "unsupported")
            history = submission_history("pkg-1", store_root=Path(directory))
            self.assertEqual(history[0]["status"], "unsupported")

    def test_configured_official_endpoint_submits_and_keeps_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {"SUPERCRAFTOS_GRANT_ENDPOINT_ETHEREUM_ESP": "https://esp.ethereum.foundation/api/applications"}
            result = submit_package(PACKAGE, PROGRAM, store_root=Path(directory), environ=env, opener=lambda request, timeout: Response())
            self.assertEqual(result["status"], "submitted")
            self.assertEqual(result["receipt"]["application_id"], "a-1")
            self.assertEqual(submission_history("pkg-1", store_root=Path(directory))[0]["status"], "submitted")

    def test_duplicate_submission_reuses_first_receipt_without_second_post(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {"SUPERCRAFTOS_GRANT_ENDPOINT_ETHEREUM_ESP": "https://esp.ethereum.foundation/api/applications"}
            calls = []
            def send(request, timeout):
                calls.append(request)
                return Response()
            first = submit_package(PACKAGE, PROGRAM, store_root=Path(directory), environ=env, opener=send)
            second = submit_package(PACKAGE, PROGRAM, store_root=Path(directory), environ=env, opener=send)
            self.assertEqual(first["status"], "submitted")
            self.assertEqual(second["status"], "already_attempted")
            self.assertEqual(second["previous_status"], "submitted")
            self.assertEqual(second["attempt_id"], first["attempt_id"])
            self.assertEqual(len(calls), 1)

    def test_http_success_without_provider_receipt_is_not_submission(self):
        class Empty(Response):
            def read(self, limit=-1): return b'{}'
        with tempfile.TemporaryDirectory() as directory:
            env = {"SUPERCRAFTOS_GRANT_ENDPOINT_ETHEREUM_ESP": "https://esp.ethereum.foundation/api/applications"}
            calls = []
            def send(request, timeout):
                calls.append(request)
                return Empty()
            first = submit_package(PACKAGE, PROGRAM, store_root=Path(directory), environ=env, opener=send)
            second = submit_package(PACKAGE, PROGRAM, store_root=Path(directory), environ=env, opener=send)
            self.assertEqual(first["status"], "verification_required")
            self.assertEqual(second["status"], "already_attempted")
            self.assertEqual(len(calls), 1)

    def test_incomplete_packet_is_not_sent_to_configured_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {"SUPERCRAFTOS_GRANT_ENDPOINT_ETHEREUM_ESP": "https://esp.ethereum.foundation/api/applications"}
            package = {**PACKAGE, "missing_information": ["contact_email", "use_of_funds"]}
            calls = []
            result = submit_package(package, PROGRAM, store_root=Path(directory), environ=env,
                                    opener=lambda request, timeout: calls.append(request))
            self.assertEqual(result["status"], "needs_information")
            self.assertIn("contact_email", result["reason"])
            self.assertEqual(calls, [])

    def test_untrusted_response_and_endpoint_query_are_rejected(self):
        self.assertFalse(is_official_url("https://esp.ethereum.foundation/api?token=private", PROGRAM))
        self.assertFalse(is_official_url("https://esp.ethereum.foundation:444/api", PROGRAM))
        self.assertFalse(is_official_url("https://esp.ethereum.foundation/api#fragment", PROGRAM))
        class Invalid(Response):
            def read(self, limit=-1): return b'{"status":"submitted","status":"failed","application_id":"x"}'
        with tempfile.TemporaryDirectory() as directory:
            env = {"SUPERCRAFTOS_GRANT_ENDPOINT_ETHEREUM_ESP": "https://esp.ethereum.foundation/api/applications"}
            result = submit_package(PACKAGE, PROGRAM, store_root=Path(directory), environ=env,
                                    opener=lambda request, timeout: Invalid())
            self.assertEqual(result["status"], "verification_required")

    def test_configured_non_official_endpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SubmissionError):
                submit_package(PACKAGE, PROGRAM, store_root=Path(directory), environ={"SUPERCRAFTOS_GRANT_ENDPOINT_ETHEREUM_ESP": "https://evil.example/submit"})


if __name__ == "__main__":
    unittest.main()
