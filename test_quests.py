"""Quest contracts using local fixtures only; no provider requests or credentials."""
from __future__ import annotations

import concurrent.futures
import email.message
import io
import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from pathlib import Path
from unittest import mock

import quest_workflow as quests


TOKEN = "fixture-credential+/=="
ENDPOINT = "https://app.galxe.com/participate"
ENV = {"SUPERCRAFTOS_QUEST_EXEC_ENDPOINT_GALXE": ENDPOINT,
       "SUPERCRAFTOS_QUEST_TOKEN_GALXE": TOKEN}
PROFILE = {"wallet_connected": True}


class Response(io.BytesIO):
    def __init__(self, body=b"", *, url=ENDPOINT, status=200, headers=None):
        super().__init__(body)
        self.url, self.status, self.code, self.msg = url, status, status, "fixture"
        self.headers = email.message.Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value

    def geturl(self):
        return self.url

    def info(self):
        return self.headers


def lead(provider="galxe", suffix="gca123", kind="quest"):
    source = quests.SOURCE_BY_ID[provider]
    path = f"/quest/community/{suffix}" if provider == "galxe" else "/news/testnet"
    url = urllib.parse.urljoin(source["url"], path)
    return {"id": quests._lead_id(source["provider"], url), "provider": source["provider"],
            "kind": kind, "url": url, "title": "New chain testnet quest", "score": 80,
            "source_url": source["url"], "signals": ["testnet"], "discovered_at": 123}


class QuestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "quests.sqlite3"
        self.store = quests.QuestStore(self.path)
        self.lead = lead()
        self.store.upsert([self.lead])
        self.calls = []
        for target in ("socket.create_connection", "socket.getaddrinfo"):
            patch = mock.patch(target, side_effect=AssertionError("Network forbidden in quest tests"))
            patch.start()
            self.addCleanup(patch.stop)

    def opener(self, request, *, timeout):
        self.calls.append(request)
        return Response(json.dumps({"status": "verified", "receipt_id": "receipt-123"}).encode(), url=request.full_url)

    def run_actions(self, *, opener=None, environ=None, value=None):
        return quests.run_quests(value if value is not None else {"profile": PROFILE},
                                 store_path=self.path, environ=ENV if environ is None else environ,
                                 opener=self.opener if opener is None else opener)["results"]

    def test_url_boundary_rejects_credentials_ports_and_ambiguous_authorities(self):
        hosts = ("app.galxe.com",)
        for url in ("http://app.galxe.com/path", "https://app.galxe.com.evil.test/x",
                    "https://user:pass@app.galxe.com/x", "https://app.galxe.com:444/x",
                    "https://app.galxe.com:invalid/x", "https://app.galxe.com./x",
                    "https://app.galxe.com\\@evil.test/x", " https://app.galxe.com/x",
                    "https://app.galxe.com/\nx", "https://app.galxe.com/x#fragment",
                    "https://app.galxe.com/x?access_token=hidden", "https://app.galxe.com/x?api%5Fkey=hidden",
                    "https://app.galxe.com/" + "x" * 2048, None, 123):
            with self.subTest(url=url):
                self.assertFalse(quests._https_url(url, hosts))
        self.assertTrue(quests._https_url("https://APP.GALXE.COM:443/path?q=public", hosts))

    def test_discovery_deduplicates_tracking_urls_and_ignores_external_links(self):
        body = b'''<a href="/quest/community/gca123?utm_source=a#top">Testnet quest</a>
        <a href="https://app.galxe.com:443/quest/community/gca123?utm_source=b">Testnet quest</a>
        <a href="https://evil.test/quest/community/gcb456">Reward</a>
        <a href="https://app.galxe.com/quest/community/gcb456?token=hidden">Reward</a>'''
        def fetch(request, *, timeout):
            self.calls.append(request)
            self.assertIsNone(request.get_header("Authorization"))
            return Response(body, url=request.full_url)
        result = quests.discover_quests({"source_ids": ["galxe"]}, store_path=self.path, opener=fetch)
        self.assertEqual(result["errors"], [])
        self.assertEqual([row["id"] for row in result["leads"]], [self.lead["id"]])
        self.assertEqual(len(self.store.leads()), 1)

    def test_discovery_follows_only_validated_official_redirects(self):
        def fetch(request, *, timeout):
            self.calls.append(request.full_url)
            if len(self.calls) == 1:
                return Response(url=request.full_url, status=302, headers={"Location": "/explore/new"})
            return Response(b'<a href="/quest/community/gca123">Testnet</a>', url=request.full_url)
        result = quests.discover_quests({"source_ids": ["galxe"]}, store_path=self.path, opener=fetch)
        self.assertEqual(result["errors"], [])
        self.assertEqual(self.calls[-1], "https://app.galxe.com/explore/new")
        self.assertEqual(len(result["leads"]), 1)

    def test_discovery_rejects_external_and_http_redirect_without_opening_target(self):
        for location in ("https://evil.test/steal", "http://app.galxe.com/path", "https://app.galxe.com:8443/path"):
            with self.subTest(location=location):
                calls = []
                def fetch(request, *, timeout):
                    calls.append(request.full_url)
                    return Response(url=request.full_url, status=302, headers={"Location": location})
                result = quests.discover_quests({"source_ids": ["galxe"]}, store_path=self.path, opener=fetch)
                self.assertEqual(len(calls), 1)
                self.assertEqual(len(result["errors"]), 1)
                self.assertEqual(result["leads"], [])

    def test_discovery_redirect_loop_is_bounded(self):
        def fetch(request, *, timeout):
            self.calls.append(request)
            return Response(url=request.full_url, status=307, headers={"Location": "/loop"})
        result = quests.discover_quests({"source_ids": ["galxe"]}, store_path=self.path, opener=fetch)
        self.assertEqual(len(self.calls), quests.MAX_REDIRECTS + 1)
        self.assertEqual(len(result["errors"]), 1)

    def test_default_transport_does_not_forward_authorization_on_any_redirect(self):
        for location in ("https://evil.test/steal", "https://app.galxe.com/other"):
            for status in (301, 302, 303, 307, 308):
                with self.subTest(location=location, status=status):
                    path = Path(self.temp.name) / f"redirect-{status}-{len(location)}.sqlite3"
                    quests.QuestStore(path).upsert([self.lead])
                    calls = []
                    def https_open(handler, request):
                        calls.append(request)
                        return Response(url=request.full_url, status=status, headers={"Location": location})
                    with mock.patch.object(urllib.request.HTTPSHandler, "https_open", https_open):
                        result = quests.run_quests({"profile": PROFILE}, store_path=path, environ=ENV)
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(calls[0].get_header("Authorization"), "Bearer " + TOKEN)
                    self.assertEqual(result["results"][0]["status"], "verification_required")

    def test_default_transport_manual_discovery_redirect(self):
        calls = []
        def https_open(handler, request):
            calls.append(request)
            if len(calls) == 1:
                return Response(url=request.full_url, status=302, headers={"Location": "/new"})
            return Response(b'<a href="/quest/community/gca123">Testnet</a>', url=request.full_url)
        with mock.patch.object(urllib.request.HTTPSHandler, "https_open", https_open):
            result = quests.discover_quests({"source_ids": ["galxe"]}, store_path=self.path)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["errors"], [])

    def test_discovery_transport_errors_do_not_echo_secrets(self):
        def fetch(request, *, timeout):
            raise urllib.error.URLError("token=" + TOKEN)
        result = quests.discover_quests({"source_ids": ["galxe"]}, store_path=self.path, opener=fetch)
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertEqual(result["errors"][0]["reason"], "URLError")

    def test_bounded_html_and_rss_and_malformed_xml(self):
        source = quests.SOURCE_BY_ID["bloomberg_crypto"]
        for body in (b"<rss>", b'<!DOCTYPE rss [<!ENTITY x "secret">]><rss>&x;</rss>',
                     b"<rss>" + b"<x>" * 40 + b"</x>" * 40 + b"</rss>",
                     b"x" * (quests.MAX_PAGE_BYTES + 1), b"\xff\xfe<rss>"):
            with self.subTest(body=body[:60]):
                with self.assertRaises(quests.QuestError):
                    quests._parse_rss(body, source, 1)
        with self.assertRaises(quests.QuestError):
            quests._parse_html(b"x" * (quests.MAX_PAGE_BYTES + 1), quests.SOURCE_BY_ID["galxe"], 1)
        body = b"".join(f'<a href="/quest/community/gc{i}">Testnet</a>'.encode() for i in range(1000))
        self.assertLessEqual(len(quests._parse_html(body, quests.SOURCE_BY_ID["galxe"], 1)), quests.MAX_LEADS)
        body = b"<rss><channel>" + b"".join(f'<item><title>Testnet launch</title><link>https://www.bloomberg.com/news/{i}</link></item>'.encode() for i in range(1000)) + b"</channel></rss>"
        self.assertLessEqual(len(quests._parse_rss(body, source, 1)), quests.MAX_LEADS)

    def test_rss_requires_actual_official_link_and_signals(self):
        body = b'''<rss><channel>
        <item><title>Testnet launch</title><link>https://www.bloomberg.com/news/testnet</link></item>
        <item><title>Testnet</title><link>https://evil.test/news</link></item>
        <item><title>Testnet</title></item><item><title>Weather</title><link>https://www.bloomberg.com/weather</link></item>
        </channel></rss>'''
        result = quests._parse_rss(body, quests.SOURCE_BY_ID["bloomberg_crypto"], 1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["kind"], "news_lead")

    def test_current_dynamic_pages_and_nonmatching_news_report_distinct_outcomes(self):
        # Current Explore responses contain navigation and Next app bootstrap,
        # not campaign anchors. Embedded translations are not actual quests.
        pages = {
            "galxe": b'<html><a href="/quest/explore/all">Quests</a><a href="/quest/spaces">Spaces</a><script>self.__next_f.push([1,"app bootstrap"])</script></html>',
            "zealy": b'<html><h1>All communities</h1><a href="/login">Log in</a><script>self.__next_f.push([1,"questboard placeholder and translations"])</script></html>',
            "bloomberg_crypto": b'<rss><channel><item><title>Market prices rebound</title><link>https://www.bloomberg.com/news/prices</link></item><item><title>Funds use digital assets</title><link>https://www.bloomberg.com/news/funds</link></item></channel></rss>',
        }
        by_url = {quests.SOURCE_BY_ID[key]["url"]: body for key, body in pages.items()}
        def fetch(request, *, timeout):
            self.assertIsNone(request.get_header("Authorization"))
            return Response(by_url[request.full_url], url=request.full_url)
        for _ in range(3):
            result = quests.discover_quests(store_path=self.path, opener=fetch)
            self.assertEqual(result["leads"], [])
            self.assertEqual([e["source_id"] for e in result["errors"]], ["galxe", "zealy"])
            self.assertTrue(all(e["reason"] == "SourceUnavailable" for e in result["errors"]))
            self.assertTrue(all("browser" in e["detail"] and "could not be determined" in e["detail"] for e in result["errors"]))
            states = {row["source_id"]: row for row in result["source_results"]}
            self.assertEqual(states["galxe"]["status"], "unavailable")
            self.assertEqual(states["bloomberg_crypto"]["status"], "no_matching_leads")
            self.assertEqual(states["bloomberg_crypto"]["articles_checked"], 2)
            self.assertIn("2 articles checked", result["note"])
        self.assertEqual(len(self.store.leads()), 1)  # Prior leads are preserved.

    def test_partial_discovery_keeps_actual_leads_with_source_warning(self):
        def fetch(request, *, timeout):
            body = (b'<a href="/quest/community/gca123">Testnet quest</a>'
                    if "galxe.com" in request.full_url else b'<html><main>Loading</main></html>')
            return Response(body, url=request.full_url)
        result = quests.discover_quests({"source_ids": ["galxe", "zealy"]}, store_path=self.path, opener=fetch)
        self.assertEqual([row["id"] for row in result["leads"]], [self.lead["id"]])
        self.assertEqual(result["errors"][0]["source_id"], "zealy")
        self.assertEqual(result["source_results"][0]["status"], "available")
        self.assertEqual(result["source_results"][0]["lead_count"], 1)

    def test_xml_error_page_is_not_a_successful_empty_feed(self):
        for body in (b'<html><body>Access restricted</body></html>', b'<error>Unavailable</error>',
                     b'<rss/>', b'<feed xmlns="http://www.w3.org/2005/Atom"/>'):
            with self.subTest(body=body):
                result = quests.discover_quests({"source_ids": ["bloomberg_crypto"]}, store_path=self.path,
                    opener=lambda request, **kw: Response(body, url=request.full_url))
                self.assertEqual(result["errors"][0]["reason"], "SourceUnavailable")
                self.assertEqual(result["source_results"][0]["status"], "unavailable")
                self.assertIn("supported RSS feed", result["errors"][0]["detail"])

    def test_valid_empty_feed_is_explained_without_false_access_error(self):
        result = quests.discover_quests({"source_ids": ["bloomberg_crypto"]}, store_path=self.path,
            opener=lambda request, **kw: Response(b'<rss><channel/></rss>', url=request.full_url))
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["source_results"][0]["status"], "empty_feed")
        self.assertIn("returned no articles", result["note"])

    def test_feed_with_only_unusable_articles_reports_format_problem(self):
        body = b'<rss><channel><item><title>Testnet</title></item><item><title>Launch</title><link>https://evil.test/news</link></item></channel></rss>'
        result = quests.discover_quests({"source_ids": ["bloomberg_crypto"]}, store_path=self.path,
            opener=lambda request, **kw: Response(body, url=request.full_url))
        self.assertEqual(result["leads"], [])
        self.assertEqual(result["errors"][0]["reason"], "SourceUnavailable")
        self.assertIn("official article link", result["errors"][0]["detail"])

    def test_source_diagnostics_never_echo_untrusted_page_content(self):
        body = ('<html><script>token=' + TOKEN + '</script><a href="/login">Sign in</a></html>').encode()
        result = quests.discover_quests({"source_ids": ["galxe"]}, store_path=self.path,
            opener=lambda request, **kw: Response(body, url=request.full_url))
        self.assertEqual(len(result["errors"]), 1)
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_bounded_source_body(self):
        response = Response(b"x" * (quests.MAX_PAGE_BYTES + 1), url=quests.SOURCE_BY_ID["galxe"]["url"])
        result = quests.discover_quests({"source_ids": ["galxe"]}, store_path=self.path,
                                       opener=lambda *a, **k: response)
        self.assertEqual(len(result["errors"]), 1)
        self.assertTrue(response.closed)

    def test_input_bounds_and_types_are_checked_before_network(self):
        inputs = [[], "value", False, {"unknown": True}, {"max_actions": True}, {"max_actions": 51},
                  {"lead_ids": ["0" * 32] * 51}, {"lead_ids": ["bad"]},
                  {"profile": {"chains": ["x"] * 31}}, {"profile": {"topics": ["x" * 81]}},
                  {"profile": {"wallet_connected": "true"}}, {"profile": {"allow_gas_spend": 1}},
                  {"profile": {"topics": [" "]}}, {"profile": {"private_key": "forbidden"}}]
        for value in inputs:
            with self.subTest(value=value), self.assertRaises(quests.QuestError):
                self.run_actions(value=value)
        for value in ({"source_ids": ["galxe"] * 4}, {"source_ids": ["unknown"]}, {"limit": False}):
            with self.subTest(value=value), self.assertRaises(quests.QuestError):
                quests.discover_quests(value, store_path=self.path, opener=self.opener)
        self.assertEqual(self.calls, [])

    def test_preconditions_do_not_reserve_or_make_requests(self):
        cases = [({}, {"profile": PROFILE}, "adapter_unavailable"),
                 (ENV, {}, "ineligible"),
                 (dict(ENV, SUPERCRAFTOS_QUEST_TOKEN_GALXE="x\nAuthorization: injected"), {"profile": PROFILE}, "configuration_error"),
                 (dict(ENV, SUPERCRAFTOS_QUEST_EXEC_ENDPOINT_GALXE="https://evil.test/x"), {"profile": PROFILE}, "configuration_error")]
        for env, value, status in cases:
            with self.subTest(status=status):
                self.assertEqual(self.run_actions(environ=env, value=value)[0]["status"], status)
                self.assertIsNone(self.store.blocking(self.lead["id"]))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.run_actions()[0]["status"], "completed")

    def test_news_remains_research_only(self):
        news = lead("bloomberg_crypto", kind="news_lead")
        self.store.upsert([news])
        result = self.run_actions(value={"lead_ids": [news["id"]], "profile": PROFILE})
        self.assertEqual(result[0]["status"], "research_only")
        self.assertEqual(self.calls, [])

    def test_provider_completion_and_receipt_persist_across_reopen(self):
        result = self.run_actions()[0]
        self.assertEqual(result["status"], "completed")
        body = json.loads(self.calls[0].data)
        self.assertFalse(body["allow_gas_spend"])
        self.assertEqual(body["idempotency_key"], result["idempotency_key"])
        self.assertEqual(self.calls[0].get_header("Idempotency-key"), result["idempotency_key"])
        duplicate = self.run_actions()[0]
        self.assertEqual(duplicate["status"], "already_attempted")
        self.assertEqual(duplicate["attempt_id"], result["attempt_id"])
        self.assertEqual(len(self.calls), 1)
        history = quests.quest_receipts({"lead_id": self.lead["id"]}, store_path=self.path)["attempts"]
        self.assertEqual(history, [result])
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_concurrent_workers_send_once(self):
        entered, release = threading.Event(), threading.Event()
        def blocking(request, *, timeout):
            self.calls.append(request)
            entered.set()
            if not release.wait(5):
                raise AssertionError("Fixture worker was not released")
            return Response(b'{"status":"completed","receipt_id":"once"}', url=request.full_url)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.run_actions, opener=blocking)
            self.assertTrue(entered.wait(5))
            try:
                duplicate = pool.submit(self.run_actions, opener=blocking).result(timeout=5)[0]
                self.assertEqual(duplicate["status"], "already_attempted")
                self.assertEqual(duplicate["previous_status"], "in_progress")
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5)[0]["status"], "completed")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.store.history(self.lead["id"])), 1)

    def test_simultaneous_reservation_uses_one_committed_intent(self):
        barrier = threading.Barrier(2)
        original = quests._prepare_action
        def prepare(*args):
            result = original(*args)
            barrier.wait(timeout=5)
            return result
        with mock.patch.object(quests, "_prepare_action", side_effect=prepare):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.run_actions) for _ in range(2)]
                results = [future.result(timeout=5)[0] for future in futures]
        self.assertEqual(sorted(result["status"] for result in results), ["already_attempted", "completed"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.store.history(self.lead["id"])), 1)

    def test_reservation_is_committed_before_post_and_survives_process_interruption(self):
        class Interrupted(BaseException):
            pass
        def interrupted(request, *, timeout):
            persisted = quests.QuestStore(self.path).history(self.lead["id"])
            self.assertEqual(persisted[0]["status"], "in_progress")
            self.assertEqual(persisted[0]["idempotency_key"], request.get_header("Idempotency-key"))
            raise Interrupted()
        with self.assertRaises(Interrupted):
            self.run_actions(opener=interrupted)
        self.assertEqual(self.run_actions()[0]["status"], "already_attempted")
        self.assertEqual(self.calls, [])

    def test_timeout_is_uncertain_and_not_retried(self):
        def timeout(request, **kwargs):
            self.calls.append(request)
            raise TimeoutError(TOKEN)
        result = self.run_actions(opener=timeout)[0]
        self.assertEqual(result["status"], "verification_required")
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertEqual(self.run_actions()[0]["status"], "already_attempted")
        self.assertEqual(len(self.calls), 1)

    def test_legacy_completed_attempt_is_not_hidden_by_later_failure(self):
        old = self.store.attempt(self.lead["id"], {"lead_id": self.lead["id"], "status": "completed", "receipt": {"receipt_id": "legacy"}})
        self.store.attempt(self.lead["id"], {"lead_id": self.lead["id"], "status": "failed"})
        result = self.run_actions()[0]
        self.assertEqual(result["status"], "already_attempted")
        self.assertEqual(result["attempt_id"], old["attempt_id"])
        self.assertEqual(self.calls, [])

    def test_malformed_or_oversized_receipts_do_not_claim_completion_or_replay(self):
        bodies = [b"not json", b"[]", b"\xff", b'{"status":"completed","receipt_id":"x","n":NaN}',
                  b'{"status":"completed","status":"failed","receipt_id":"x"}',
                  b"[" * 2000 + b"]" * 2000, b"x" * (quests.MAX_RESPONSE_BYTES + 1)]
        for index, body in enumerate(bodies):
            with self.subTest(body=body[:60]):
                path = Path(self.temp.name) / f"malformed-{index}.sqlite3"
                quests.QuestStore(path).upsert([self.lead])
                result = quests.run_quests({"profile": PROFILE}, store_path=path, environ=ENV,
                                          opener=lambda *a, **k: Response(body))["results"][0]
                self.assertEqual(result["status"], "verification_required")
                result = quests.run_quests({"profile": PROFILE}, store_path=path, environ=ENV,
                                          opener=self.opener)["results"][0]
                self.assertEqual(result["status"], "already_attempted")
        self.assertEqual(self.calls, [])

    def test_receipt_requires_explicit_completion_and_string_identity(self):
        for status, identity in (("queued", "receipt"), ("completed", True), ("completed", {}),
                                 ("completed", " "), ("completed", "x" * 201)):
            with self.subTest(status=status, identity=identity):
                prepared = quests._prepare_action(self.lead, quests._profile({"profile": PROFILE}), ENV)
                result = quests._execute_one(self.lead, prepared,
                    lambda *a, **k: Response(json.dumps({"status": status, "receipt_id": identity}).encode()))
                self.assertEqual(result["status"], "accepted_pending_verification")

    def test_explicit_provider_failure_is_reported_and_not_replayed(self):
        result = self.run_actions(opener=lambda *a, **k: Response(b'{"status":"failed","receipt_id":"error"}'))[0]
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.run_actions()[0]["status"], "already_attempted")
        self.assertEqual(self.calls, [])

    def test_nested_receipt_redaction_and_bounds_apply_to_disk_and_response(self):
        receipt = {"status": "completed", "receipt_id": "receipt",
                   "nested": {"accessToken": "secondary-secret", "API-Key": "another-secret",
                              "items": [{"note": TOKEN}, {"note": urllib.parse.quote(TOKEN, safe="")},
                                        {"note": "Bearer unrelated-token"}, {"note": "https://example.test/?token=third-secret"}],
                              "private_key": "key-material"},
                   "many": ["a" * 2500] * 12}
        result = self.run_actions(opener=lambda *a, **k: Response(json.dumps(receipt).encode()))[0]
        self.assertEqual(result["status"], "completed")
        with closing(sqlite3.connect(self.path)) as db:
            disk = db.execute("SELECT payload FROM attempts").fetchone()[0]
        for secret in (TOKEN, urllib.parse.quote(TOKEN, safe=""), "secondary-secret", "another-secret", "unrelated-token", "third-secret", "key-material"):
            self.assertNotIn(secret, json.dumps(result))
            self.assertNotIn(secret, disk)
        self.assertLessEqual(len(result["receipt"]["many"][0]), 2000)
        self.assertEqual(self.store.history(self.lead["id"])[0]["attempt_id"], result["attempt_id"])

    def test_rendering_uses_fixed_provider_and_caches_without_forwarding_key(self):
        quests._RENDER_CACHE.clear()
        key = "private-browser-test-key"
        calls = []
        def render(request, *, timeout):
            calls.append(request)
            self.assertEqual(urllib.parse.urlsplit(request.full_url).hostname, "production-sfo.browserless.io")
            payload = json.loads(request.data)
            self.assertEqual(payload["url"], quests.SOURCE_BY_ID["galxe"]["url"])
            self.assertNotIn(key, json.dumps(payload))
            self.assertIsNone(request.get_header("Authorization"))
            return Response(b'<a href="/quest/community/gca123">Testnet quest</a>', url=request.full_url)
        with mock.patch.object(quests, "_open", side_effect=render):
            body, cached = quests._rendered_page(quests.SOURCE_BY_ID["galxe"], key)
            self.assertFalse(cached)
            self.assertEqual(quests._rendered_page(quests.SOURCE_BY_ID["galxe"], key), (body, True))
        self.assertEqual(len(calls), 1)
        quests._RENDER_CACHE.clear()

    def test_render_provider_errors_do_not_expose_credentials(self):
        quests._RENDER_CACHE.clear()
        key = "private-browser-test-key"
        with mock.patch.object(quests, "_open", side_effect=urllib.error.URLError("https://provider/?token=" + key)):
            with self.assertRaises(quests.SourceUnavailable) as raised:
                quests._rendered_page(quests.SOURCE_BY_ID["galxe"], key)
        self.assertNotIn(key, str(raised.exception))
        self.assertNotIn("token=", str(raised.exception))

    def test_rendered_fallback_supplies_real_links_to_discovery(self):
        with mock.patch.dict(os.environ, {"BROWSERLESS_API_KEY": "fixture-key"}), mock.patch.object(quests, "_fetch", return_value=b"<html>application shell</html>"), mock.patch.object(quests, "_rendered_page", return_value=(b'<a href="/quest/community/gca123">Testnet quest</a>', False)):
            result = quests.discover_quests({"source_ids": ["galxe"]}, store_path=self.path)
        self.assertEqual(len(result["leads"]), 1)
        self.assertEqual(result["source_results"][0]["transport"], "configured_browser")
        self.assertEqual(result["errors"], [])

    def test_renderer_rejects_redirects_oversize_and_unregistered_sources(self):
        for response in (Response(b"", url="https://production-sfo.browserless.io/content", status=302),
                         Response(b"x" * (quests.MAX_PAGE_BYTES + 1), url="https://production-sfo.browserless.io/content")):
            quests._RENDER_CACHE.clear()
            with mock.patch.object(quests, "_open", return_value=response):
                with self.assertRaises(quests.SourceUnavailable):
                    quests._rendered_page(quests.SOURCE_BY_ID["galxe"], "fixture-key")
        with self.assertRaises(quests.QuestError):
            quests._rendered_page({"id": "galxe", "url": "https://example.test/private"}, "fixture-key")

    def test_screen_and_tool_contracts_remain_offline(self):
        result = quests.screen_quests({"profile": {"topics": ["testnet"]}}, store_path=self.path)
        self.assertEqual(result["results"][0]["eligibility"], "unknown")
        self.assertEqual(result["results"][0]["matched_interests"], ["testnet"])
        self.assertEqual(len(quests.quest_tools()), 5)
        self.assertEqual(len(quests.quest_sources()["sources"]), 3)
        with self.assertRaises(quests.QuestError):
            quests.quest_receipts({"lead_id": "bad"}, store_path=self.path)


if __name__ == "__main__":
    unittest.main()
