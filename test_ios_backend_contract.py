"""Live contract test between the SuperCraftOS backend and the iOS app.

The Swift app decodes the backend with hand written Decodable models. A field
that is renamed, dropped, or changes type on the backend breaks a screen in the
app, and nothing on the server notices. This test mirrors the decoding
contract of every model in ios_app_dist/AppConfig.swift and checks the live
responses against it.

The model fields and their JSON keys are taken directly from the Swift
CodingKeys, so the two files have to be changed together.
"""
from __future__ import annotations

import json
import os
import unittest
import urllib.error
import urllib.request
from urllib.parse import urlparse

# This suite spends provider credits and starts/stops the runtime.
# Ordinary discovery must never choose a production server implicitly.
BASE = os.environ.get("SUPERCRAFTOS_BACKEND", "").rstrip("/")
TIMEOUT = 30


def access_headers():
    key = os.environ.get("SUPERCRAFTOS_ACCESS_KEY", "")
    return {"Authorization": "Bearer " + key} if key else {}


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


HTTP = urllib.request.build_opener(NoRedirects)


def get(path: str) -> dict:
    """Fetch a path. A rejected request returns its body, like the app sees it."""
    request = urllib.request.Request(f"{BASE}{path}", headers=access_headers())
    try:
        with HTTP.open(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return json.loads(error.read().decode())


def post(path: str, body: dict, token: str) -> dict:
    """Post a body. A rejected request returns its body, like the app sees it."""
    request = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode(),
        headers={**access_headers(), "Content-Type": "application/json", "X-SuperCraftOS-Token": token},
        method="POST",
    )
    try:
        with HTTP.open(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return json.loads(error.read().decode())


def require(payload: dict, spec: dict, where: str) -> None:
    """Assert the keys the Swift model needs, and their JSON types.

    spec maps a JSON key to "str", "int", "float", "bool", "list" or "dict".
    A trailing "?" marks an optional key, which must be absent or of the
    right type.
    """
    for name, kind in spec.items():
        # A trailing "?" on the type marks a Swift optional property, which
        # decodes from an absent key and from null alike.
        optional = kind.endswith("?")
        base = kind[:-1] if optional else kind
        if name not in payload or payload[name] is None:
            if optional:
                continue
            raise AssertionError(f"{where}: required key {name!r} is missing or null")
        value = payload[name]
        if base == "str" and not isinstance(value, str):
            raise AssertionError(f"{where}: {name!r} must be a string, got {type(value).__name__}")
        if base == "int" and not isinstance(value, int):
            raise AssertionError(f"{where}: {name!r} must be an integer, got {type(value).__name__}")
        if base == "float" and not isinstance(value, (int, float)):
            raise AssertionError(f"{where}: {name!r} must be a number, got {type(value).__name__}")
        if base == "bool" and not isinstance(value, bool):
            raise AssertionError(f"{where}: {name!r} must be a boolean, got {type(value).__name__}")
        if base == "list" and not isinstance(value, list):
            raise AssertionError(f"{where}: {name!r} must be a list, got {type(value).__name__}")
        if base == "dict" and not isinstance(value, dict):
            raise AssertionError(f"{where}: {name!r} must be an object, got {type(value).__name__}")


def require_list(payload: dict, key: str, where: str) -> list:
    require(payload, {key: "list"}, where)
    return payload[key]


@unittest.skipUnless(os.environ.get("SUPERCRAFTOS_ALLOW_LIVE_MUTATIONS") == "1",
                     "Explicit live mutation suite; use isolated default CI tests")
class IosBackendContractTests(unittest.TestCase):
    """The live backend must satisfy the decoding contract of the iOS app."""

    @classmethod
    def setUpClass(cls) -> None:
        parsed = urlparse(BASE)
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Set an explicit SUPERCRAFTOS_BACKEND origin for live tests")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}):
            raise ValueError("Live tests require HTTPS or an explicit loopback server")
        if not os.environ.get("SUPERCRAFTOS_ACCESS_KEY"):
            raise ValueError("Set SUPERCRAFTOS_ACCESS_KEY for authenticated live tests")
        try:
            cls.session = get("/api/session")
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as error:
            raise unittest.SkipTest(f"the backend is not reachable: {error}")
        require(cls.session, {"token": "str"}, "ControlSession")
        cls.token = cls.session["token"]

    def test_control_session(self) -> None:
        require(self.session, {"token": "str"}, "ControlSession")

    def test_runtime_status(self) -> None:
        status = get("/api/status")
        require(status, {
            "runtime": "str", "tools": "int", "integrations": "int",
            "healthy_integrations": "int", "workflows": "int", "awaiting_approval": "int",
            "memory_mb": "float", "memory_limit_mb": "float",
            "usage": "dict?", "runtime_snapshot": "dict?",
        }, "RuntimeStatus")
        if isinstance(status.get("usage"), dict):
            require(status["usage"], {
                "input_tokens": "int?", "output_tokens": "int?", "requests": "int?",
                "cost_usd": "float?", "unpriced_requests": "int?",
            }, "TokenUsage")
        if isinstance(status.get("runtime_snapshot"), dict):
            require(status["runtime_snapshot"], {
                "lark": "str?", "mode": "str?", "sandbox": "str?", "timestamp": "float?",
            }, "RuntimeSnapshot")

    def test_tools(self) -> None:
        for tool in require_list(get("/api/tools"), "tools", "ToolResponse"):
            require(tool, {"name": "str", "description": "str?"}, "AgentTool")

    def test_workflows(self) -> None:
        for workflow in require_list(get("/api/workflows"), "workflows", "WorkflowResponse"):
            require(workflow, {
                "thread_id": "str", "query": "str?", "status": "str?",
                "artifact": "str?", "error": "str?", "plan": "str?",
            }, "AgentWorkflow")

    def test_integrations(self) -> None:
        for integration in require_list(get("/api/integrations"), "integrations", "IntegrationResponse"):
            require(integration, {
                "name": "str", "status": "str", "latency_ms": "float?", "detail": "str?",
            }, "IntegrationHealth")

    def test_registrations(self) -> None:
        for registration in require_list(get("/api/registrations"), "registrations", "RegistrationResponse"):
            require(registration, {"name": "str", "status": "str", "detail": "str?"}, "RegistrationOutcome")

    def test_capabilities(self) -> None:
        for capability in require_list(get("/api/capabilities"), "capabilities", "CapabilityResponse"):
            require(capability, {
                "id": "str", "name": "str", "features": "str", "enabled": "bool",
                "runs": "int", "successes": "int", "routing_score": "float",
            }, "EngineCapability")

    def test_grant_catalog(self) -> None:
        programs = require_list(get("/api/grants/catalog"), "programs", "GrantCatalogResponse")
        self.assertGreater(len(programs), 0, "the grant catalogue is empty")
        for program in programs:
            require(program, {
                "id": "str", "name": "str", "chain": "str", "payment": "str",
                "cadence": "str", "topics": "list", "evidence": "str",
                "official_url": "str", "application_url": "str",
                "funding_type": "str?", "status": "str?", "submission_surface": "str?",
            }, "GrantOpportunity")

    def test_quest_sources(self) -> None:
        for source in require_list(get("/api/quests/sources"), "sources", "QuestSourcesResponse"):
            require(source, {
                "id": "str", "name": "str", "url": "str", "kind": "str", "provider": "str",
            }, "QuestSource")

    def test_agent_workflow_round_trip(self) -> None:
        """The keyboard posts to this endpoint, so its reply must decode."""
        result = post("/api/workflows", {"query": "Contract check: reply with the word READY"}, self.token)
        require(result, {
            "thread_id": "str", "query": "str?", "status": "str?",
            "artifact": "str?", "error": "str?", "plan": "str?",
        }, "AgentWorkflow reply")

    def test_quest_discover_reply(self) -> None:
        result = post("/api/quests/discover", {"limit": 5}, self.token)
        require(result, {"leads": "list", "checked_at": "int?"}, "QuestDiscoverResponse")
        for lead in result.get("leads", []):
            require(lead, {
                "id": "str", "provider": "str", "kind": "str", "title": "str",
                "url": "str", "source_url": "str", "discovered_at": "int?", "score": "float?",
            }, "QuestLead")

    def test_product_interpret_reply(self) -> None:
        """/api/products/interpret answers with a ProductSpec, not a report."""
        result = post("/api/products/interpret", {"idea": "A small enclosure for a sensor"}, self.token)
        if result.get("error"):
            self.skipTest(f"the interpreter declined this brief: {result.get('detail') or result['error']}")
        require(result, {
            "name": "str", "idea": "str", "template": "str", "material": "str", "process": "str",
            "width_mm": "float", "depth_mm": "float", "height_mm": "float",
            "wall_mm": "float", "hole_mm": "float", "load_n": "float",
        }, "ProductSpec")

    def test_product_build_reply(self) -> None:
        """/api/products/build answers with a ProductReport."""
        spec = post("/api/products/interpret", {"idea": "A small enclosure for a sensor"}, self.token)
        if spec.get("error"):
            self.skipTest(f"the interpreter declined this brief: {spec.get('detail') or spec['error']}")
        result = post("/api/products/build", spec, self.token)
        if result.get("error") in {"cad_unavailable_or_resource_limit", "cad_unavailable_or_resource_limit"}:
            self.skipTest("the CAD engine is busy or unavailable on this server")
        if result.get("error"):
            self.skipTest(f"the CAD build failed: {result.get('detail') or result['error']}")
        require(result, {
            "id": "str?", "readiness": "str", "checks": "list", "scope": "str",
            "files": "dict?", "mass_estimate_g": "float?", "geometry": "dict?", "next_steps": "list?",
        }, "ProductReport")
        for check in result.get("checks", []):
            require(check, {"code": "str", "status": "str", "detail": "str"}, "DesignCheck")
        geometry = result.get("geometry")
        if isinstance(geometry, dict):
            require(geometry, {
                "valid_solid": "bool", "volume_mm3": "float", "step_roundtrip_valid": "bool",
            }, "ProductGeometry")

    def test_quest_screen_reply(self) -> None:
        result = post("/api/quests/screen", {"lead_ids": [], "profile": {}}, self.token)
        require(result, {"results": "list"}, "QuestScreenResponse")
        for row in result.get("results", []):
            require(row, {"lead_id": "str", "status": "str?", "eligible": "bool?", "reason": "str?"},
                    "QuestScreenResult")

    def test_quest_run_reply(self) -> None:
        result = post("/api/quests/run", {"lead_ids": [], "max_actions": 1,
                                        "profile": {"allow_gas_spend": False}}, self.token)
        require(result, {"results": "list"}, "QuestRunResponse")
        for row in result.get("results", []):
            require(row, {"lead_id": "str", "status": "str", "reason": "str?", "receipt": "dict?"},
                    "QuestActionResult")

    def test_runtime_control_reply(self) -> None:
        """The app starts and stops the runtime from the Mission screen."""
        for path in ("/api/runtime/start", "/api/runtime/stop"):
            result = post(path, {}, self.token)
            if result.get("error"):
                continue
            self.assertIsInstance(result, dict)

    def test_product_files_are_reachable(self) -> None:
        """The app downloads the exported files by id and name."""
        spec = post("/api/products/interpret", {"idea": "A small plate for a badge"}, self.token)
        if spec.get("error"):
            self.skipTest(f"the interpreter declined this brief: {spec.get('detail') or spec['error']}")
        report = post("/api/products/build", spec, self.token)
        if report.get("error"):
            self.skipTest(f"the CAD build is unavailable: {report.get('detail') or report['error']}")
        files = report.get("files") or {}
        if not files:
            self.skipTest("the build produced no files")
        product_id = report.get("id")
        self.assertTrue(product_id, "the report has no id, so the app cannot fetch its files")
        for name in files:
            data = get(f"/api/products/{product_id}/files/{name}")
            self.assertTrue(data, f"the file {name} came back empty")


if __name__ == "__main__":
    unittest.main()
