"""Official-source quest and launch lead discovery with durable execution receipts.

Discovery and execution are separate: a public quest listing does not imply an
authenticated participation API or an award. Provider actions run only through
an explicitly configured, same-host HTTPS endpoint and record its response.
"""
from __future__ import annotations

import hashlib
import html.parser
import http.client
import json
import os
import re
import sqlite3
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
STORE = ROOT / "data" / "quests" / "quests.sqlite3"
MAX_PAGE_BYTES = 1_000_000
MAX_RESPONSE_BYTES = 50_000
MAX_URL_LENGTH = 2048
MAX_LEADS = 200
MAX_FEED_ITEMS = 2000
MAX_REDIRECTS = 3
BLOCKING_STATUSES = ("completed", "accepted_pending_verification", "in_progress", "verification_required")
SOURCES = (
    {"id": "galxe", "name": "Galxe Quest Explore", "url": "https://app.galxe.com/quest/explore/all", "provider": "galxe", "kind": "quest_html", "allowed_hosts": ("app.galxe.com",)},
    {"id": "zealy", "name": "Zealy Explore", "url": "https://zealy.io/explore", "provider": "zealy", "kind": "quest_html", "allowed_hosts": ("zealy.io", "www.zealy.io")},
    {"id": "bloomberg_crypto", "name": "Bloomberg Crypto RSS", "url": "https://www.bloomberg.com/feeds/crypto/news.rss", "provider": "bloomberg", "kind": "news_rss", "allowed_hosts": ("www.bloomberg.com", "bloomberg.com")},
)
SOURCE_BY_ID = {source["id"]: source for source in SOURCES}
_RENDER_CACHE: dict[str, tuple[float, str, bytes]] = {}
_RENDER_LOCK = threading.Lock()
SIGNALS = {"testnet": 20, "airdrop": 20, "mainnet": 12, "launch": 10, "new chain": 18,
           "pre-launch": 14, "prelaunch": 14, "quest": 7, "reward": 7, "points": 5}


class QuestError(ValueError):
    pass


class SourceUnavailable(QuestError):
    """The response cannot establish whether the source has matching leads."""


def _sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return any(word in normalized for word in (
        "token", "authorization", "apikey", "secret", "password", "credential",
        "privatekey", "cookie", "signature", "mnemonic", "seedphrase"))


def _https_url(url: str, hosts: tuple[str, ...]) -> bool:
    if (not isinstance(url, str) or not 1 <= len(url) <= MAX_URL_LENGTH or
            not url.isascii() or re.search(r"[\s\x00-\x1f\x7f\\]", url)):
        return False
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
        query = urllib.parse.parse_qsl(parsed.query, max_num_fields=32)
    except ValueError:
        return False
    return (parsed.scheme == "https" and parsed.hostname in hosts and
            port in (None, 443) and parsed.username is None and parsed.password is None and
            not parsed.fragment and not any(_sensitive_key(key) for key, _ in query))


def _canonical_url(url: str, source: dict[str, Any]) -> str | None:
    if not url or url.startswith("#"):
        return None
    try:
        url = urllib.parse.urljoin(source["url"], url).split("#", 1)[0]
        if not _https_url(url, source["allowed_hosts"]):
            return None
        parts = urllib.parse.urlsplit(url)
        query = [(key, value) for key, value in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
                 if not key.lower().startswith("utm_") and key.lower() not in {"gclid", "fbclid"}]
        return urllib.parse.urlunsplit(("https", parts.hostname, parts.path or "/",
                                       urllib.parse.urlencode(sorted(query)), ""))
    except ValueError:
        return None


def _lead_id(provider: str, url: str) -> str:
    return hashlib.sha256(f"{provider}\0{url}".encode()).hexdigest()[:32]


class _Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []
        self._length = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            self._href = href if href and len(href) <= MAX_URL_LENGTH and len(self.links) < MAX_FEED_ITEMS else None
            self._parts = []
            self._length = 0

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._length += len(data)
            if self._length <= 300:
                self._parts.append(data)
            else:
                self._href = None
                self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join(self._parts).strip()))
            self._href = None
            self._parts = []


def _score(text: str) -> tuple[int, list[str]]:
    lower = text.lower()
    hits = [key for key in SIGNALS if key in lower]
    return min(100, 20 + sum(SIGNALS[hit] for hit in hits)), hits


def _parse_html(body: bytes, source: dict[str, Any], now: int) -> list[dict[str, Any]]:
    if len(body) > MAX_PAGE_BYTES:
        raise QuestError("source response exceeds size limit")
    parser = _Links()
    parser.feed(body.decode("utf-8", "replace"))
    leads = []
    for href, title in parser.links:
        url = _canonical_url(href, source)
        if url is None:
            continue
        path = urllib.parse.urlsplit(url).path.lower()
        if source["provider"] == "galxe" and not re.search(r"/quest/[^/]+/gc[a-z0-9]+", path):
            continue
        if source["provider"] == "zealy" and not any(x in path for x in ("/quest", "/campaign", "/explore/")):
            continue
        if not title or len(title) > 300:
            continue
        score, signals = _score(title)
        leads.append({"id": _lead_id(source["provider"], url), "provider": source["provider"],
                      "kind": "quest", "title": title, "url": url, "source_url": source["url"],
                      "discovered_at": now, "score": score, "signals": signals})
        if len(leads) >= MAX_LEADS:
            break
    return leads


class _BoundedXML(ET.TreeBuilder):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.nodes = 0

    def start(self, tag, attrs):
        self.depth += 1
        self.nodes += 1
        if self.depth > 32 or self.nodes > MAX_FEED_ITEMS * 6:
            raise QuestError("news feed exceeds structure limit")
        return super().start(tag, attrs)

    def end(self, tag):
        self.depth -= 1
        return super().end(tag)


def _parse_rss(body: bytes, source: dict[str, Any], now: int, *,
               diagnostics: dict[str, int] | None = None) -> list[dict[str, Any]]:
    if len(body) > MAX_PAGE_BYTES:
        raise QuestError("source response exceeds size limit")
    try:
        text = body.decode("utf-8-sig")
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.IGNORECASE):
            raise QuestError("news feed declarations are not allowed")
        root = ET.fromstring(text, parser=ET.XMLParser(target=_BoundedXML()))
    except (UnicodeDecodeError, ET.ParseError) as exc:
        raise QuestError("news feed is not valid XML") from exc
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise SourceUnavailable("The source did not return a supported RSS feed. Check the official feed URL or publisher access requirements.")
    leads = []
    items_seen = articles_checked = 0
    for index, item in enumerate(channel.findall("item")):
        if index >= MAX_FEED_ITEMS:
            break
        items_seen += 1
        title = (item.findtext("title") or "").strip()
        url = _canonical_url((item.findtext("link") or "").strip(), source)
        if not title or len(title) > 300 or url is None:
            continue
        articles_checked += 1
        score, signals = _score(title + " " + (item.findtext("description") or "")[:4000])
        if not signals:
            continue
        leads.append({"id": _lead_id(source["provider"], url), "provider": source["provider"],
                      "kind": "news_lead", "title": title[:300], "url": url,
                      "source_url": source["url"], "discovered_at": now,
                      "score": score, "signals": signals})
        if len(leads) >= MAX_LEADS:
            break
    if items_seen and not articles_checked:
        raise SourceUnavailable("The feed contains entries, but none has a supported title and official article link. Check the publisher's feed format.")
    if diagnostics is not None:
        diagnostics.update(items_seen=items_seen, articles_checked=articles_checked)
    return leads


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open(request, *, timeout):
    # Never use urlopen's automatic redirect handler with a provider credential.
    return urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout)


def _fetch(url: str, hosts: tuple[str, ...], opener=None) -> bytes:
    # Injected transports must also be one-hop; production uses _NoRedirect.
    open_one = _open if opener is None else opener
    for hop in range(MAX_REDIRECTS + 1):
        if not _https_url(url, hosts):
            raise QuestError("source URL is not an official HTTPS location")
        request = urllib.request.Request(url, headers={"User-Agent": "SuperCraftOS-quest-research/1.0", "Accept": "text/html,application/rss+xml,application/xml"})
        try:
            response = open_one(request, timeout=12)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            status = response.status
            if not _https_url(response.geturl(), hosts):
                raise QuestError("source returned an unofficial location")
            if status in (301, 302, 303, 307, 308):
                target = response.headers.get("Location", "")
                if not target or hop == MAX_REDIRECTS:
                    raise QuestError("source redirect limit or missing location")
                try:
                    url = urllib.parse.urljoin(url, target)
                except ValueError as exc:
                    raise QuestError("invalid source redirect") from exc
                continue
            if not 200 <= status < 300:
                raise QuestError(f"source returned HTTP {status}")
            body = response.read(MAX_PAGE_BYTES + 1)
        if len(body) > MAX_PAGE_BYTES:
            raise QuestError("source response exceeds size limit")
        return body
    raise QuestError("source redirect limit")


def _redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    """Bound provider-controlled structures and strip credentials at every level."""
    secret_forms = {form for secret in secrets if secret for form in
                    (secret, urllib.parse.quote(secret, safe=""), urllib.parse.quote_plus(secret))}
    remaining = 200

    def text_safe(text: str) -> str:
        for secret in sorted(secret_forms, key=len, reverse=True):
            text = text.replace(secret, "[REDACTED]")
        text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [REDACTED]", text)
        text = re.sub(r"(?i)\b(token|access[_-]?token|refresh[_-]?token|api[_-]?key|authorization|secret|password|signature)\s*[:=]\s*[\"']?[^\s&\"',;}]+",
                      r"\1=[REDACTED]", text)
        return text[:2000]

    def visit(item: Any, depth: int) -> Any:
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 6:
            return "[TRUNCATED]"
        if isinstance(item, str):
            return text_safe(item)
        if item is None or isinstance(item, (bool, int)):
            return item
        if isinstance(item, float):
            return item if float("-inf") < item < float("inf") else None
        if isinstance(item, dict):
            result = {}
            for key, child in list(item.items())[:30]:
                if remaining <= 0:
                    break
                if isinstance(key, str):
                    result[text_safe(key)[:100]] = "[REDACTED]" if _sensitive_key(key) else visit(child, depth + 1)
            return result
        if isinstance(item, list):
            return [visit(child, depth + 1) for child in item[:30] if remaining > 0]
        return "[UNSUPPORTED]"

    return visit(value, 0)


def _input(value: Any, keys: set[str]) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict) or any(key not in keys for key in value):
        raise QuestError("input must be an object with supported fields")
    return value


def _limit(value: Any, maximum: int, name: str) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise QuestError(f"{name} must be 1..{maximum}")
    return value


def _safe_result(result: dict[str, Any]) -> dict[str, Any]:
    # A large receipt must not consume the redaction budget for attempt metadata.
    return {key: _redact(result[key]) for key in ("lead_id", "status", "reason", "receipt",
            "attempt_id", "idempotency_key", "checked_at") if key in result}


class QuestStore:
    def __init__(self, path: Path = STORE):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # SQLite inherits this mode for its WAL; existing stores are tightened too.
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        self.path.chmod(0o600)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS leads (id TEXT PRIMARY KEY, provider TEXT NOT NULL, kind TEXT NOT NULL, url TEXT NOT NULL, score INTEGER NOT NULL, payload TEXT NOT NULL, first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, lead_id TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL, created_at INTEGER NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS attempts_lead ON attempts(lead_id, created_at DESC)")
            db.execute("CREATE TABLE IF NOT EXISTS executions (lead_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL UNIQUE, idempotency_key TEXT NOT NULL)")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def upsert(self, leads: list[dict[str, Any]]) -> int:
        if len(leads) > MAX_LEADS:
            raise QuestError("too many leads")
        with self._connect() as db:
            for lead in leads:
                db.execute("INSERT INTO leads VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET score=excluded.score,payload=excluded.payload,last_seen=excluded.last_seen",
                           (lead["id"], lead["provider"], lead["kind"], lead["url"], lead["score"], json.dumps(lead), lead["discovered_at"], lead["discovered_at"]))
        return len(leads)

    def leads(self, ids: list[str] | None = None, limit: int = 100) -> list[dict[str, Any]]:
        _ids({"lead_ids": ids})
        _limit(limit, MAX_LEADS, "limit")
        with self._connect() as db:
            if ids is None:
                rows = db.execute("SELECT payload FROM leads ORDER BY score DESC,last_seen DESC,id LIMIT ?", (limit,)).fetchall()
            elif not ids:
                rows = []
            else:
                marks = ",".join("?" for _ in ids)
                rows = db.execute(f"SELECT payload FROM leads WHERE id IN ({marks}) ORDER BY score DESC,last_seen DESC,id LIMIT ?", (*ids, limit)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def attempt(self, lead_id: str, result: dict[str, Any]) -> dict[str, Any]:
        ident = hashlib.sha256(f"{lead_id}:{time.time_ns()}".encode()).hexdigest()[:32]
        result = dict(_safe_result(result), attempt_id=ident, checked_at=int(time.time()))
        with self._connect() as db:
            db.execute("INSERT INTO attempts VALUES (?, ?, ?, ?, ?)", (ident, lead_id, result["status"], json.dumps(result), result["checked_at"]))
        return result

    @staticmethod
    def _blocking(db, lead_id: str) -> dict[str, Any] | None:
        row = db.execute("SELECT a.payload FROM executions e JOIN attempts a ON a.id=e.attempt_id WHERE e.lead_id=?", (lead_id,)).fetchone()
        if row is None:
            # Old databases had no reservation table. Any prior successful or
            # uncertain action blocks replay, even if a later failure exists.
            marks = ",".join("?" for _ in BLOCKING_STATUSES)
            row = db.execute(f"SELECT payload FROM attempts WHERE lead_id=? AND status IN ({marks}) ORDER BY created_at DESC,rowid DESC LIMIT 1",
                             (lead_id, *BLOCKING_STATUSES)).fetchone()
        return _safe_result(json.loads(row[0])) if row else None

    def blocking(self, lead_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            return self._blocking(db, lead_id)

    def reserve(self, lead_id: str, key: str) -> tuple[bool, dict[str, Any]]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = self._blocking(db, lead_id)
            if previous is not None:
                return False, previous
            ident = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
            result = {"lead_id": lead_id, "status": "in_progress", "attempt_id": ident,
                      "idempotency_key": key, "checked_at": int(time.time()),
                      "reason": "Action reserved. If interrupted, reconcile with the provider before any retry."}
            db.execute("INSERT INTO attempts VALUES (?, ?, ?, ?, ?)",
                       (ident, lead_id, result["status"], json.dumps(result), result["checked_at"]))
            db.execute("INSERT INTO executions VALUES (?, ?, ?)", (lead_id, ident, key))
        # The reservation is committed before the caller can send a request.
        return True, result

    def finish(self, reservation: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        result = dict(_safe_result(result), attempt_id=reservation["attempt_id"],
                      idempotency_key=reservation["idempotency_key"], checked_at=int(time.time()))
        with self._connect() as db:
            db.execute("UPDATE attempts SET status=?,payload=? WHERE id=?",
                       (result["status"], json.dumps(result), reservation["attempt_id"]))
        return result

    def history(self, lead_id: str, limit: int = 20) -> list[dict[str, Any]]:
        _limit(limit, 100, "limit")
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM attempts WHERE lead_id=? ORDER BY created_at DESC,rowid DESC LIMIT ?", (lead_id, limit)).fetchall()
        return [_safe_result(json.loads(row[0])) for row in rows]


def quest_sources(value: dict[str, Any] | None = None) -> dict[str, Any]:
    _input(value, set())
    return {"sources": [{k: source[k] for k in ("id", "name", "url", "provider", "kind")} for source in SOURCES],
            "note": "Public discovery only. Publisher access and page availability can vary."}


def _rendered_page(source: dict[str, Any], key: str) -> tuple[bytes, bool]:
    """Render a fixed public registry URL; never forward the service key to it."""
    if source.get("id") not in SOURCE_BY_ID or source["url"] != SOURCE_BY_ID[source["id"]]["url"]:
        raise QuestError("Only registered public pages can use the rendering adapter")
    fingerprint = hashlib.sha256(key.encode()).hexdigest()
    with _RENDER_LOCK:
        cached = _RENDER_CACHE.get(source["id"])
        if cached and time.monotonic() - cached[0] < 300 and cached[1] == fingerprint:
            return cached[2], True
        request = urllib.request.Request(
            "https://production-sfo.browserless.io/content?" + urllib.parse.urlencode({"token": key}),
            data=json.dumps({"url": source["url"], "gotoOptions": {"waitUntil": "networkidle2", "timeout": 45000}}).encode(),
            headers={"Content-Type": "application/json", "Accept": "text/html"}, method="POST")
        try:
            with _open(request, timeout=65) as response:
                if response.status != 200 or urllib.parse.urlsplit(response.geturl()).hostname != "production-sfo.browserless.io":
                    raise SourceUnavailable("Configured browser service rejected the render request.")
                body = response.read(MAX_PAGE_BYTES + 1)
            if len(body) > MAX_PAGE_BYTES:
                raise SourceUnavailable("Rendered source exceeds the discovery size limit.")
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
            # Browser provider exceptions may contain the credential-bearing URL.
            raise SourceUnavailable("Configured browser service is unavailable; check its credential, quota and connectivity.") from None
        _RENDER_CACHE[source["id"]] = (time.monotonic(), fingerprint, body)
        return body, False


def discover_quests(value: dict[str, Any] | None = None, *, store_path: Path = STORE, opener=None) -> dict[str, Any]:
    value = _input(value, {"source_ids", "limit"})
    selected = value.get("source_ids", list(SOURCE_BY_ID))
    limit = value.get("limit", 50)
    if not isinstance(selected, list) or len(selected) > len(SOURCES) or not all(isinstance(x, str) and x in SOURCE_BY_ID for x in selected):
        raise QuestError("source_ids must contain known source IDs")
    _limit(limit, MAX_LEADS, "limit")
    now = int(time.time())
    discovered: dict[str, dict[str, Any]] = {}
    errors = []
    source_results = []
    empty_notes = []
    for source_id in dict.fromkeys(selected):
        source = SOURCE_BY_ID[source_id]
        try:
            body = _fetch(source["url"], source["allowed_hosts"], opener)
            diagnostics: dict[str, Any] = {}
            if source["kind"] == "news_rss":
                parsed = _parse_rss(body, source, now, diagnostics=diagnostics)
            else:
                parsed = _parse_html(body, source, now)
                key = os.getenv("BROWSERLESS_API_KEY", "")
                if not parsed and key and opener is None:
                    rendered, cached = _rendered_page(source, key)
                    parsed = _parse_html(rendered, source, now)
                    diagnostics.update(transport="configured_browser", cached=cached)
                    if not parsed:
                        raise SourceUnavailable("The official page was rendered but exposed no supported campaign links. Open its Explore page or configure an official data adapter; availability is undetermined.")
                if not parsed:
                    raise SourceUnavailable(
                        "The official page returned no readable campaign links. No configured rendering adapter is available. "
                        "Configure BROWSERLESS_API_KEY, open the official Explore page in a browser, or add a supported official data adapter. "
                        "Quest availability could not be determined.")
            for lead in parsed:
                discovered[lead["id"]] = lead
            result = {"source_id": source_id, "status": "available" if parsed else "no_matching_leads",
                      "lead_count": len({lead["id"] for lead in parsed}), **diagnostics}
            if not parsed:
                result["detail"] = (f"{source['name']}: {diagnostics['articles_checked']} articles checked; "
                                    "no launch, testnet, airdrop or quest discovery keywords matched.")
                if not diagnostics["items_seen"]:
                    result["status"] = "empty_feed"
                    result["detail"] = f"{source['name']}: the RSS feed returned no articles."
                empty_notes.append(result["detail"])
            source_results.append(result)
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException, QuestError) as exc:
            error = {"source_id": source_id, "reason": type(exc).__name__,
                     "detail": str(exc) if isinstance(exc, QuestError) else "Source request failed."}
            errors.append(error)
            source_results.append({**error, "status": "unavailable", "lead_count": 0})
    leads = sorted(discovered.values(), key=lambda lead: (-lead["score"], lead["title"]))[:limit]
    QuestStore(store_path).upsert(leads)
    return {"leads": leads, "errors": errors, "source_results": source_results, "checked_at": now,
            "note": " ".join(empty_notes + ["A listing or headline is a lead, not proof of eligibility, an airdrop, or a reward."])}


def _profile(value: dict[str, Any]) -> dict[str, Any]:
    profile = value.get("profile", {})
    if not isinstance(profile, dict) or any(key not in {"chains", "topics", "wallet_connected", "allow_gas_spend"} for key in profile):
        raise QuestError("profile must be an object with supported fields")
    chains = profile.get("chains", [])
    topics = profile.get("topics", [])
    for field, terms in (("chains", chains), ("topics", topics)):
        if not isinstance(terms, list) or len(terms) > 30 or not all(
                isinstance(x, str) and 1 <= len(x) <= 80 and x.strip() and
                not re.search(r"[\x00-\x1f\x7f]", x) for x in terms):
            raise QuestError(f"profile.{field} must contain at most 30 nonempty strings of at most 80 characters")
    for field in ("wallet_connected", "allow_gas_spend"):
        if field in profile and type(profile[field]) is not bool:
            raise QuestError(f"profile.{field} must be a boolean")
    return {"chains": [x.strip() for x in chains], "topics": [x.strip() for x in topics], "wallet_connected": profile.get("wallet_connected") is True,
            "allow_gas_spend": profile.get("allow_gas_spend") is True}


def _ids(value: dict[str, Any]) -> list[str] | None:
    ids = value.get("lead_ids")
    if ids is not None and (not isinstance(ids, list) or len(ids) > 50 or not all(isinstance(x, str) and re.fullmatch(r"[0-9a-f]{32}", x) for x in ids)):
        raise QuestError("lead_ids must contain at most 50 valid lead IDs")
    return list(dict.fromkeys(ids)) if ids is not None else None


def screen_quests(value: dict[str, Any] | None = None, *, store_path: Path = STORE) -> dict[str, Any]:
    value = _input(value, {"profile", "lead_ids"})
    profile = _profile(value)
    leads = QuestStore(store_path).leads(_ids(value))
    terms = {x.lower() for x in profile["chains"] + profile["topics"]}
    results = []
    for lead in leads:
        matches = [term for term in terms if term in lead["title"].lower()]
        eligibility = "unknown" if lead["kind"] == "quest" else "research_only"
        results.append({"lead": lead, "score": min(100, lead["score"] + 10 * len(matches)),
                        "matched_interests": sorted(matches), "eligibility": eligibility,
                        "reason": "Task requirements and account state must be fetched from the provider before participation." if eligibility == "unknown" else "News is evidence for investigation, not a reward claim."})
    return {"results": sorted(results, key=lambda row: -row["score"]), "checked_at": int(time.time())}


def _prepare_action(lead: dict[str, Any], profile: dict[str, Any], env: dict[str, str]):
    if lead["kind"] != "quest":
        return {"lead_id": lead["id"], "status": "research_only", "reason": "News cannot be executed as a quest."}
    provider = lead["provider"]
    source = SOURCE_BY_ID.get(provider)
    if source is None:
        return {"lead_id": lead["id"], "status": "unsupported", "reason": "Provider is not registered."}
    endpoint = env.get(f"SUPERCRAFTOS_QUEST_EXEC_ENDPOINT_{provider.upper()}", "")
    token = env.get(f"SUPERCRAFTOS_QUEST_TOKEN_{provider.upper()}", "")
    if not isinstance(endpoint, str) or not isinstance(token, str):
        return {"lead_id": lead["id"], "status": "configuration_error", "reason": "Adapter configuration must be strings."}
    endpoint, token = endpoint.strip(), token.strip()
    if not endpoint or not token:
        return {"lead_id": lead["id"], "status": "adapter_unavailable", "reason": "No official authenticated participation endpoint and token are configured."}
    if not _https_url(endpoint, source["allowed_hosts"]):
        return {"lead_id": lead["id"], "status": "configuration_error", "reason": "Execution endpoint must use an official provider HTTPS host."}
    if len(token) > 4096 or re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token) is None:
        return {"lead_id": lead["id"], "status": "configuration_error", "reason": "Provider token is not a valid Bearer credential."}
    if (not _https_url(lead["url"], source["allowed_hosts"]) or
            lead["id"] != _lead_id(provider, lead["url"])):
        return {"lead_id": lead["id"], "status": "configuration_error", "reason": "Stored lead has an invalid provider URL or identity."}
    if not profile["wallet_connected"]:
        return {"lead_id": lead["id"], "status": "ineligible", "reason": "A connected wallet is required by the configured execution policy."}
    key = hashlib.sha256(f"{lead['id']}:{endpoint}".encode()).hexdigest()
    body = json.dumps({"quest_url": lead["url"], "idempotency_key": key,
                       "allow_gas_spend": profile["allow_gas_spend"]}, separators=(",", ":")).encode()
    request = urllib.request.Request(endpoint, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json",
        "Idempotency-Key": key, "User-Agent": "SuperCraftOS-quest-agent/1.0"})
    return request, key, token


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("non-finite JSON value")


def _execute_one(lead: dict[str, Any], prepared, opener=None) -> dict[str, Any]:
    request, _, token = prepared
    uncertain = {"lead_id": lead["id"], "status": "verification_required"}
    open_one = _open if opener is None else opener
    try:
        with open_one(request, timeout=20) as response:
            status_code = int(response.status)
            if response.geturl() != request.full_url:
                return dict(uncertain, reason="Execution response location changed; redirects are forbidden.")
            if 300 <= status_code < 400:
                return dict(uncertain, reason="Execution redirects are forbidden.")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # Never read error bodies (which can echo headers) or follow Location.
        code = exc.code
        exc.close()
        return dict(uncertain, reason=f"Provider HTTP {code}; action outcome requires reconciliation.")
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException, ValueError) as exc:
        return dict(uncertain, reason=f"Transport {type(exc).__name__}; action outcome is unknown.")
    if len(raw) > MAX_RESPONSE_BYTES:
        return dict(uncertain, reason="Provider response exceeded size limit.")
    try:
        receipt = json.loads(raw.decode("utf-8"), object_pairs_hook=_json_object, parse_constant=_invalid_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return dict(uncertain, reason="Provider response was not valid bounded JSON.")
    if not isinstance(receipt, dict):
        return dict(uncertain, reason="Provider receipt was not an object.")
    # Keep evidence fields even when unrelated provider metadata hits the cap.
    evidence = {key: receipt[key] for key in ("status", "receipt_id") if key in receipt}
    safe_receipt = _redact(evidence | receipt, (token,))
    if not 200 <= status_code < 300:
        return dict(uncertain, reason=f"Provider HTTP {status_code}; action outcome requires reconciliation.", receipt=safe_receipt)
    if receipt.get("status") in ("failed", "rejected", "error", "cancelled"):
        return {"lead_id": lead["id"], "status": "failed", "reason": "Provider explicitly reported failure; automatic replay is disabled.", "receipt": safe_receipt}
    receipt_id = receipt.get("receipt_id")
    confirmed = (receipt.get("status") in ("completed", "verified") and isinstance(receipt_id, str) and
                 1 <= len(receipt_id) <= 200 and bool(receipt_id.strip()) and
                 not re.search(r"[\x00-\x1f\x7f]", receipt_id))
    return {"lead_id": lead["id"], "status": "completed" if confirmed else "accepted_pending_verification",
            "reason": "Provider reported completion; this is not proof of a paid reward." if confirmed else "Provider accepted the request without a verifiable completion receipt.",
            "receipt": safe_receipt}


def _already_attempted(lead_id: str, previous: dict[str, Any]) -> dict[str, Any]:
    return {"lead_id": lead_id, "status": "already_attempted", "attempt_id": previous.get("attempt_id"),
            "previous_status": previous["status"], "receipt": previous.get("receipt"),
            "reason": "A durable attempt already exists. Reconcile its outcome with the provider; automatic replay is disabled."}


def run_quests(value: dict[str, Any] | None = None, *, store_path: Path = STORE,
               environ: dict[str, str] | None = None, opener=None) -> dict[str, Any]:
    value = _input(value, {"profile", "lead_ids", "max_actions"})
    profile = _profile(value)
    max_actions = value.get("max_actions", 10)
    _limit(max_actions, 50, "max_actions")
    ids = _ids(value)
    store = QuestStore(store_path)
    leads = store.leads(ids, limit=max_actions)
    env = os.environ if environ is None else environ
    results = []
    for lead in leads:
        previous = store.blocking(lead["id"])
        if previous is not None:
            results.append(_already_attempted(lead["id"], previous))
            continue
        prepared = _prepare_action(lead, profile, env)
        if isinstance(prepared, dict):
            results.append(store.attempt(lead["id"], prepared))
            continue
        reserved, reservation = store.reserve(lead["id"], prepared[1])
        if not reserved:
            results.append(_already_attempted(lead["id"], reservation))
            continue
        result = _execute_one(lead, prepared, opener)
        results.append(store.finish(reservation, result))
    return {"results": results, "checked_at": int(time.time())}


def quest_receipts(value: dict[str, Any], *, store_path: Path = STORE) -> dict[str, Any]:
    value = _input(value, {"lead_id"})
    ident = value.get("lead_id")
    if not isinstance(ident, str) or not re.fullmatch(r"[0-9a-f]{32}", ident):
        raise QuestError("lead_id must be a valid lead ID")
    return {"lead_id": ident, "attempts": QuestStore(store_path).history(ident)}


def quest_tools() -> list[dict[str, Any]]:
    ids = {"type": "array", "items": {"type": "string", "pattern": "^[0-9a-f]{32}$"}, "maxItems": 50}
    terms = {"type": "array", "maxItems": 30, "items": {"type": "string", "minLength": 1, "maxLength": 80}}
    profile = {"type": "object", "properties": {"chains": terms, "topics": terms, "wallet_connected": {"type": "boolean"}, "allow_gas_spend": {"type": "boolean"}}, "additionalProperties": False}
    return [
        {"name": "list_quest_sources", "description": "List official quest listings and Bloomberg Crypto feed.", "inputSchema": {"type": "object", "additionalProperties": False}},
        {"name": "discover_quest_leads", "description": "Fetch public quest and launch leads from official sources; records source failures.", "inputSchema": {"type": "object", "properties": {"source_ids": {"type": "array", "maxItems": len(SOURCES), "items": {"type": "string", "enum": list(SOURCE_BY_ID)}}, "limit": {"type": "integer", "minimum": 1, "maximum": 200}}, "additionalProperties": False}},
        {"name": "screen_quest_leads", "description": "Rank persisted leads; eligibility remains unknown until provider requirements are confirmed.", "inputSchema": {"type": "object", "properties": {"profile": profile, "lead_ids": ids}, "additionalProperties": False}},
        {"name": "run_quest_actions", "description": "Attempt configured official quest adapters once; persist redacted receipts. Uncertain outcomes require provider reconciliation, never blind replay.", "inputSchema": {"type": "object", "properties": {"profile": profile, "lead_ids": ids, "max_actions": {"type": "integer", "minimum": 1, "maximum": 50}}, "additionalProperties": False}},
        {"name": "quest_action_receipts", "description": "Read durable quest action statuses and provider receipts.", "inputSchema": {"type": "object", "required": ["lead_id"], "properties": {"lead_id": {"type": "string", "pattern": "^[0-9a-f]{32}$"}}, "additionalProperties": False}},
    ]
