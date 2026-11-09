"""Compatibility view over the canonical funding catalogue."""
from __future__ import annotations

import re
from typing import Any

from grant_workflow import OFFICIAL_PROGRAMS, _funding_type

ALIASES = {"gitcoin-grants": "gitcoin", "arbitrum-foundation-grants": "arbitrum-audit", "optimism-retro-funding": "optimism-grants"}


def load_registry() -> dict[str, Any]:
    """Return the same sourced opportunities used by the runtime and iPad app."""
    programs = []
    for item in OFFICIAL_PROGRAMS:
        programs.append({**item, "funding_type": _funding_type(item), "network": item["chain"],
                         "status": item.get("status", "round_specific"),
                         "fit": item["topics"], "source_url": item["official_url"]})
    return {"schema_version": 2, "catalog_updated_at": "2026-10-19", "requires_live_verification": True, "programs": programs}


def screen_opportunities(project: dict[str, Any]) -> list[dict[str, Any]]:
    """Return deterministic fit scores; no network calls and no application writes."""
    text = " ".join(str(project.get(key, "")) for key in ("name", "description", "category", "network", "license")).lower()
    open_source = bool(re.search(r"open[- ]source|public good|public goods|mit|apache|gpl", text))
    results: list[dict[str, Any]] = []
    for program in load_registry()["programs"]:
        score = 0
        reasons: list[str] = []
        network = str(project.get("network", "")).lower()
        if network and network in program["network"].lower():
            score += 35; reasons.append("network match")
        if open_source and any("open-source" in item or "public good" in item for item in program["fit"]):
            score += 30; reasons.append("public-goods alignment")
        if any(token in text for fit in program["fit"] for token in fit.lower().split() if len(token) > 4):
            score += 20; reasons.append("category overlap")
        if program["status"] in {"application_link_published", "proposal_route_published"}:
            score += 15
        results.append({"program_id": program["id"], "name": program["name"], "score": min(score, 100),
                        "reasons": reasons, "application_url": program["application_url"],
                        "official_url": program["official_url"], "status": program["status"],
                        "funding_type": program.get("funding_type", "grant"),
                        "requirements": program.get("requirements", []),
                        "source_url": program["source_url"], "requires_live_verification": True})
    return sorted(results, key=lambda item: item["score"], reverse=True)


def draft_application(program_id: str, project: dict[str, Any]) -> dict[str, Any]:
    """Create a complete editable packet without claiming eligibility or submitting it."""
    program_id = ALIASES.get(program_id, program_id)
    program = next((item for item in load_registry()["programs"] if item["id"] == program_id), None)
    if program is None:
        raise KeyError(f"unknown grant program: {program_id}")
    required = ("name", "description", "deliverables", "milestones", "budget")
    missing = [key for key in required if not project.get(key)]
    return {"program": program, "project": project, "missing_fields": missing,
            "ready_for_submission": not missing,
            "submission_surface": program.get("submission_surface", "web_form"),
            "generated_by": "SuperCraftOS funding screener", "source_url": program["source_url"]}
