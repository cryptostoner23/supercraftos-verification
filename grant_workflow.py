"""Official-source blockchain grant discovery and application drafting.

Programme URLs and requirements are advisory metadata refreshed from official
programme pages. The workflow never invents eligibility, deadlines, or award
outcomes; callers must use the linked programme entry point for the current
submission fields.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
STORE = ROOT / "data" / "grants"
MAX_TEXT = 12000

# Official programme pages only. Availability and deadlines are treated as
# live claims and must be rechecked before an application is sent.
OFFICIAL_PROGRAMS = [
    {"id": "ethereum-esp", "name": "Ethereum Ecosystem Support Program", "chain": "Ethereum", "official_url": "https://esp.ethereum.foundation/applicants", "application_url": "https://esp.ethereum.foundation/applicants", "payment": "ETH on-chain by default; milestone-based grant structure", "cadence": "Wishlist, RFP and open rounds vary", "topics": ["infrastructure", "developer tooling", "public goods", "research", "security", "privacy"], "requirements": ["Match a current Wishlist or RFP item", "Provide methodology, timeline, deliverables, budget, and relevant experience", "Grant-funded outputs must be open source and freely available", "Be able to receive and manage ETH"], "evidence": "Official Ethereum Foundation ESP applicant process"},
    {"id": "optimism-grants", "name": "Optimism Grant Missions", "chain": "Optimism", "official_url": "https://gov.optimism.io/c/grants/87", "application_url": "https://gov.optimism.io/c/grants/87", "submission_surface": "governance_forum", "status": "round_specific", "payment": "OP reward determined by the relevant mission and governance process", "cadence": "Mission-specific windows; former Atlas route was discontinued", "topics": ["public goods", "impact", "governance", "infrastructure"], "requirements": ["Select a currently open mission", "Demonstrate measurable contribution against that mission", "Provide evidence and impact metrics requested by the mission"], "evidence": "Official Optimism governance grants forum"},
    {"id": "arbitrum-audit", "name": "Arbitrum Audit Program", "chain": "Arbitrum", "official_url": "https://arbitrum.foundation/grants", "application_url": "https://tally.so/r/3xzEzv?program=aap&ref=blog.arbitrum.foundation", "submission_surface": "tally_form", "payment": "ARB subsidy subject to programme terms", "cadence": "Programme status and intake are shown on the official grants page", "topics": ["security", "smart contracts", "infrastructure"], "requirements": ["Be an eligible Arbitrum project seeking a third-party audit", "Meet the active programme's product and growth criteria", "Use the Apply now entry point shown on the official page"], "evidence": "Official Arbitrum grants page"},
    {"id": "arbitrum-arbifuel", "name": "ArbiFuel gas sponsorship", "chain": "Arbitrum", "official_url": "https://arbitrum.foundation/grants", "application_url": "https://airtable.com/appzb4GfqGfrnDXjW/shrulGIIp6l6ezAlt", "submission_surface": "airtable_form", "payment": "Gas sponsorship subject to eligibility", "cadence": "Programme status and intake are shown on the official grants page", "topics": ["dapps", "infrastructure", "developer tooling"], "requirements": ["Be an eligible early-stage Arbitrum team", "Show a valid use case for gas sponsorship", "Use the Apply now entry point shown on the official page"], "evidence": "Official Arbitrum grants page"},
    {"id": "arbitrum-alchemy", "name": "Alchemy-Arbitrum Grant Program", "chain": "Arbitrum", "official_url": "https://arbitrum.foundation/grants", "application_url": "https://alchemyapi.typeform.com/to/CijtV0Oe", "submission_surface": "typeform", "payment": "Grant terms set by the active programme", "cadence": "Programme status and intake are shown on the official grants page", "topics": ["infrastructure", "developer tooling", "dapps"], "requirements": ["Meet the active programme criteria", "Provide a complete technical and team application", "Use the Apply now entry point shown on the official page"], "evidence": "Official Arbitrum grants page"},
    {"id": "gitcoin", "name": "Gitcoin Grants", "chain": "Multi-chain", "official_url": "https://gitcoin.co/program", "application_url": "https://grants.gitcoin.co/", "submission_surface": "allo_protocol", "integration_url": "https://github.com/gitcoinco/allo-starter-kit", "payment": "Round-specific matching and direct grants after review and anti-Sybil checks", "cadence": "Seasonal rounds; active dates are shown in Grants Builder", "topics": ["public goods", "open source", "climate", "community"], "requirements": ["Create or use a Grants Builder project profile", "Meet the selected round's eligibility and category criteria", "Complete onboarding and provide truthful project information", "Maintain evidence for anti-Sybil and distribution checks"], "evidence": "Official Gitcoin Grants Program, Grants Builder, and Allo starter kit"},
    {"id": "polygon-grants", "name": "Polygon ecosystem funding", "chain": "Polygon", "official_url": "https://polygon.technology/community-grants", "application_url": "https://polygon.technology/community-grants", "payment": "Programme terms vary", "cadence": "Verify current programme status", "topics": ["infrastructure", "consumer", "developer tooling", "zero knowledge"], "requirements": ["Match an active Polygon programme or round", "Provide a defined technical plan, milestones, budget, and team evidence", "Use the programme's current official intake route"], "evidence": "Official Polygon site"},
    {"id": "circle-developer-grants", "name": "Circle Developer Grants", "chain": "Arc / Multi-chain", "official_url": "https://www.circle.com/grant", "application_url": "https://circle.questbook.app/", "submission_surface": "questbook", "status": "application_link_published", "funding_type": "grant", "payment": "Milestone-based USDC grants; amount depends on evaluation", "cadence": "Program-specific intake", "topics": ["agentic payments", "liquidity", "stablecoin", "developer tooling", "infrastructure"], "requirements": ["Show a meaningful Arc and Circle product integration", "Provide shipped work or credible roadmap, traction, team, and milestones", "Use Circle's linked grant portal"], "evidence": "Circle Developer Grants page"},
    {"id": "virtuals-builder-credits", "name": "Virtuals EconomyOS Developer Credits", "chain": "Base / Multi-chain", "official_url": "https://os.virtuals.io/community", "application_url": "https://virtualsprotocol.typeform.com/to/BwtdGEAL", "submission_surface": "typeform", "status": "application_link_published", "funding_type": "infrastructure_credits", "payment": "Weekly inference and compute credits; tier depends on repository signals or review", "cadence": "Two-week baseline with possible extension", "topics": ["AI agents", "agent commerce", "compute", "payments", "developer tooling"], "requirements": ["Build with EconomyOS or tokenize through Virtuals", "Provide GitHub repository and project details", "Link GitHub to the EconomyOS agent workspace for automatic eligibility where available"], "evidence": "Virtuals EconomyOS community credits program"},
    {"id": "base-ecosystem-fund", "name": "Base Ecosystem Fund", "chain": "Base", "official_url": "https://www.base.org/ecosystem-fund", "application_url": "https://www.base.org/ecosystem-fund/apply", "submission_surface": "web_form", "status": "application_link_published", "funding_type": "equity_investment", "payment": "Pre-seed or seed investment terms determined by Base Ecosystem Fund", "cadence": "Application route published", "topics": ["AI agents", "payments", "trading", "onchain business", "infrastructure"], "requirements": ["Build a venture-scale onchain company with Base as its home", "Provide company, team, product, funding, and Base-alignment details"], "evidence": "Base Ecosystem Fund application"},
    {"id": "uniswap-foundation-grants", "name": "Uniswap Foundation Grants", "chain": "Ethereum / Unichain", "official_url": "https://www.uniswapfoundation.org/build", "application_url": "https://uniswap.notion.site/bdb023b007ec444f8616d38b554163fa", "submission_surface": "notion_form", "status": "application_link_published", "funding_type": "grant", "payment": "Grant amount and milestones determined by the foundation", "cadence": "Application link published", "topics": ["liquidity", "DeFi", "developer tooling", "research", "governance"], "requirements": ["Advance the Uniswap ecosystem", "Provide a concrete project, delivery plan, and team evidence"], "evidence": "Uniswap Foundation Build page"},
    {"id": "unichain-builder-grants", "name": "Unichain Builder Grants", "chain": "Unichain", "official_url": "https://www.uniswapfoundation.org/build", "application_url": "https://share.hsforms.com/18Kv3hTvDSt-x1wK9va0OYwsdca9", "submission_surface": "hubspot_form", "status": "application_link_published", "funding_type": "grant", "payment": "Up to $7,500 for qualifying Unichain projects per current foundation page", "cadence": "Application link published", "topics": ["liquidity", "DeFi", "infrastructure", "developer tooling"], "requirements": ["Build on Unichain", "Meet the published DeFi TVL or infrastructure eligibility criteria"], "evidence": "Uniswap Foundation Build page"},
    {"id": "uniswap-router-subsidies", "name": "Uniswap Router Subsidies", "chain": "Ethereum / Unichain", "official_url": "https://www.uniswapfoundation.org/build", "application_url": "https://sdca9.share.hsforms.com/2usOunBjQSZqrsVypvYdtQQ?1=", "submission_surface": "hubspot_form", "status": "application_link_published", "funding_type": "usage_subsidy", "payment": "Daily subsidies for qualifying hooked-pool routing flow", "cadence": "Application link published", "topics": ["liquidity", "router", "solver", "aggregator", "DeFi"], "requirements": ["Route qualifying flow to hooked pools", "Provide verifiable router, solver, or aggregator activity"], "evidence": "Uniswap Foundation Build page"},
    {"id": "1inch-foundation", "name": "1inch Foundation Support", "chain": "Ethereum / Multi-chain", "official_url": "https://1inch.network/foundation", "application_url": "https://gov.1inch.network/", "submission_surface": "governance_forum", "status": "proposal_route_published", "funding_type": "grant", "payment": "1INCH or agreed currency; milestone terms vary", "cadence": "Foundation and DAO initiative-specific", "topics": ["Fusion resolver", "liquidity", "DeFi", "protocol integration", "research", "analytics"], "requirements": ["Demonstrate benefit to the 1inch ecosystem", "Publish a concrete open-source initiative and milestones", "Follow the current foundation or DAO proposal process"], "evidence": "1inch Foundation and governance forum"},
    {"id": "aws-activate", "name": "AWS Activate Credits", "chain": "Multi-chain / AI", "official_url": "https://aws.amazon.com/startups/credits", "application_url": "https://aws.amazon.com/startups/credits", "submission_surface": "startup_portal", "status": "application_link_published", "funding_type": "infrastructure_credits", "payment": "AWS promotional credits according to the eligible tier", "cadence": "Rolling applications", "topics": ["AI agents", "cloud", "infrastructure", "developer tooling"], "requirements": ["Meet startup age and funding-stage criteria", "Use an AWS Builder ID and linked AWS account", "Provide startup profile and required tier information"], "evidence": "AWS Activate Credits official page"},
    {"id": "google-startups-cloud", "name": "Google for Startups Cloud Program", "chain": "Multi-chain / AI", "official_url": "https://cloud.google.com/startup", "application_url": "https://cloud.google.com/startup", "submission_surface": "startup_portal", "status": "application_link_published", "funding_type": "infrastructure_credits", "payment": "Google Cloud credits according to eligible program tier", "cadence": "Rolling applications", "topics": ["AI agents", "web3", "cloud", "infrastructure"], "requirements": ["Meet the chosen startup tier criteria", "Provide a Google Cloud billing account ID", "Submit a business email matching the startup website domain where required"], "evidence": "Google for Startups Cloud Program and FAQ"},
    {"id": "microsoft-startups", "name": "Microsoft for Startups", "chain": "Multi-chain / AI", "official_url": "https://learn.microsoft.com/en-us/startups/overview", "application_url": "https://startups.microsoft.com/", "submission_surface": "startup_portal", "status": "application_link_published", "funding_type": "infrastructure_credits", "payment": "Azure startup credits according to eligible offer", "cadence": "Rolling applications", "topics": ["AI agents", "cloud", "developer tooling", "infrastructure"], "requirements": ["Own a software product and meet Microsoft startup eligibility", "Set up a Microsoft and Azure account", "Provide a company profile and billing information"], "evidence": "Microsoft for Startups overview"},
    {"id": "cloudflare-startups", "name": "Cloudflare for Startups", "chain": "Multi-chain / AI", "official_url": "https://www.cloudflare.com/startups/", "application_url": "https://www.cloudflare.com/startups/", "submission_surface": "startup_portal", "status": "application_link_published", "funding_type": "infrastructure_credits", "payment": "Cloudflare platform credits according to eligible tier", "cadence": "Rolling applications", "topics": ["AI agents", "edge compute", "security", "infrastructure"], "requirements": ["Meet startup-stage and fundraising criteria", "Provide company details and Cloudflare account information"], "evidence": "Cloudflare for Startups official page"},
    {"id": "nvidia-inception", "name": "NVIDIA Inception", "chain": "AI / Multi-chain", "official_url": "https://www.nvidia.com/en-us/startups/", "application_url": "https://www.nvidia.com/en-us/startups/", "submission_surface": "startup_portal", "status": "application_link_published", "funding_type": "startup_benefits", "payment": "Developer benefits and partner offers; no cash grant stated", "cadence": "Rolling applications", "topics": ["AI agents", "compute", "research", "developer tooling"], "requirements": ["Be an eligible incorporated startup with a working website and developer", "Provide business and product details"], "evidence": "NVIDIA Inception official page"},
    {"id": "alchemy-solana-credits", "name": "Alchemy Solana Fund", "chain": "Solana", "official_url": "https://www.alchemy.com/solana-20m-fund", "application_url": "https://www.alchemy.com/solana-20m-fund", "submission_surface": "web_form", "status": "application_link_published", "funding_type": "infrastructure_credits", "payment": "Up to $25,000 in Alchemy Solana infrastructure credits by tier", "cadence": "90-day credit evaluation period", "topics": ["RPC", "Solana", "infrastructure", "AI agents"], "requirements": ["Build on Solana", "Provide project, contact, and infrastructure usage details"], "evidence": "Alchemy Solana Fund application"},
]


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected text")
    value = value.strip()
    if not value or len(value) > limit:
        raise ValueError("Text is empty or exceeds its limit")
    return value


def _profile(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Profile must be an object")
    name = _text(value.get("project_name", "Project"), 160)
    summary = _text(value.get("summary", ""), 4000)
    topics = value.get("topics", [])
    chains = value.get("chains", [])
    if not isinstance(topics, list) or not all(isinstance(x, str) and 1 <= len(x) <= 80 for x in topics[:30]):
        raise ValueError("topics must be a list of short strings")
    if not isinstance(chains, list) or not all(isinstance(x, str) and 1 <= len(x) <= 80 for x in chains[:20]):
        raise ValueError("chains must be a list of short strings")
    optional_text = {}
    for field, limit in (("problem", 4000), ("solution", 4000), ("public_goods_case", 4000),
                         ("use_of_funds", 4000), ("contact_email", 320)):
        item = value.get(field, "")
        if not isinstance(item, str) or len(item) > limit:
            raise ValueError(f"{field} must be a string of at most {limit} characters")
        optional_text[field] = item.strip()
    metrics = value.get("success_metrics", [])
    if not isinstance(metrics, list) or len(metrics) > 12 or not all(
            isinstance(item, str) and 1 <= len(item.strip()) <= 300 for item in metrics):
        raise ValueError("success_metrics must contain at most 12 short strings")
    breakdown = value.get('budget_breakdown_usd', {})
    if (not isinstance(breakdown, dict) or len(breakdown) > 30
            or any(not isinstance(k, str) or not 1 <= len(k) <= 160
                   or isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) or v < 0 for k, v in breakdown.items())):
        raise ValueError('budget_breakdown_usd must map short item names to finite nonnegative amounts')
    return {"project_name": name, "summary": summary, "topics": topics[:30], "chains": chains[:20],
            "repository_url": value.get("repository_url", ""), "team": value.get("team", ""),
            "budget_usd": value.get("budget_usd", 0), "milestones": value.get("milestones", []),
            "success_metrics": [item.strip() for item in metrics], 'budget_breakdown_usd': breakdown, **optional_text}


def _url(value: Any) -> str:
    if not isinstance(value, str) or not re.match(r"^https://[A-Za-z0-9.-]+(?:/[^\s]*)?$", value):
        raise ValueError("Only HTTPS evidence URLs are accepted")
    return value


def grant_catalog(value: dict[str, Any] | None = None) -> dict[str, Any]:
    """The official programmes, optionally narrowed to the ones that were asked for.

    A caller that names programmes gets exactly those. A body that is ignored
    and a body that is honoured are not the same answer, so the filter is
    applied rather than discarded.
    """
    now = int(time.time())
    programs = OFFICIAL_PROGRAMS
    requested = (value or {}).get("program_ids")
    if requested is not None:
        if not isinstance(requested, list) or not all(isinstance(x, str) for x in requested):
            raise ValueError("program_ids must be a list of strings")
        wanted = set(requested)
        programs = [program for program in OFFICIAL_PROGRAMS if program["id"] in wanted]
    return {"generated_at": now, "source_policy": "official_provider_pages_only", "requires_live_verification": True,
            "programs": [_program_for_output(item) for item in programs]}


def _funding_type(program: dict[str, Any]) -> str:
    """Classify the benefit without presenting credits or equity as cash grants."""
    if program["id"] in {"arbitrum-audit", "arbitrum-arbifuel"}:
        return "usage_subsidy"
    if program["id"] == "gitcoin":
        return "matching_funding"
    return program.get("funding_type", "grant")


def _program_for_output(program: dict[str, Any]) -> dict[str, Any]:
    # A catalog read is not a source check. Never attach the current time to
    # source_checked_at unless an actual verification request took place.
    return dict(program, funding_type=_funding_type(program))


def _monetization(funding_type: str) -> dict[str, Any]:
    options = {
        "grant": (["Fund approved milestones", "Offer paid implementation and support where programme terms allow"],
                  "An application does not guarantee a grant or commercial revenue."),
        "matching_funding": (["Fund eligible public goods through donations and matching", "Offer related paid services where round rules allow"],
                             "Matching depends on donations, round rules, and review."),
        "infrastructure_credits": (["Reduce eligible infrastructure spend", "Run and sell a product using the supported infrastructure"],
                                   "Credits offset eligible bills; they are not cash revenue."),
        "equity_investment": (["Finance company development under agreed investment terms", "Earn product revenue from customers"],
                              "Investment is negotiated capital, not a grant or guaranteed revenue."),
        "startup_benefits": (["Reduce eligible development costs through partner benefits", "Earn product revenue from customers"],
                             "Partner benefits are not cash funding."),
        "usage_subsidy": (["Offset eligible audit, gas, or protocol usage costs", "Earn revenue from a separate product or service"],
                          "Subsidies apply only to eligible use and are not cash revenue."),
    }
    paths, caveat = options[funding_type]
    return {"paths": paths, "caveat": caveat}


def _chain_matches(program_chain: str, profile_chains: set[str]) -> bool:
    if not profile_chains:
        return False
    parts = {part.strip().lower() for part in program_chain.split("/")}
    if "multi-chain" in parts or "multi-chain" in profile_chains:
        return True
    return bool(parts & profile_chains)


def screen_grants(value: dict[str, Any]) -> dict[str, Any]:
    profile = _profile(value.get("profile"))
    requested = value.get("program_ids")
    if requested is not None and (not isinstance(requested, list) or not all(isinstance(x, str) for x in requested)):
        raise ValueError("program_ids must be a list of strings")
    topic_text = " ".join(profile["topics"] + [profile["summary"]]).lower()
    chains = {x.lower() for x in profile["chains"]}
    rows = []
    for program in OFFICIAL_PROGRAMS:
        if requested is not None and program["id"] not in requested:
            continue
        hits = [topic for topic in program["topics"] if topic.lower() in topic_text]
        chain_match = _chain_matches(program["chain"], chains)
        score = min(100, 25 + len(hits) * 12 + (20 if chain_match else 0) + (10 if profile.get("repository_url") else 0))
        funding_type = _funding_type(program)
        rows.append({"program": _program_for_output(program), "score": score, "fit": "strong" if score >= 65 else "possible" if score >= 45 else "weak",
                     "matched_topics": hits, "chain_match": chain_match,
                     "evidence": [{"url": program["official_url"], "kind": "official_programme_page"}, {"url": program["application_url"], "kind": "application_entrypoint"}],
                     "monetization": _monetization(funding_type),
                     "next_action": "Verify current eligibility, application window, and benefit terms on the official page."})
    return {"profile": profile, "results": sorted(rows, key=lambda row: row["score"], reverse=True), "disclaimer": "Scores are a prioritization aid, not an award prediction."}


def draft_grant_application(value: dict[str, Any]) -> dict[str, Any]:
    profile = _profile(value.get("profile"))
    program_id = _text(value.get("program_id", ""), 80)
    program = next((x for x in OFFICIAL_PROGRAMS if x["id"] == program_id), None)
    if not program:
        raise ValueError("Unknown grant programme")
    milestones = value.get("milestones", profile.get("milestones", []))
    if not isinstance(milestones, list) or not all(isinstance(x, str) and 1 <= len(x) <= 300 for x in milestones[:12]):
        raise ValueError("milestones must be short strings")
    missing = [field for field in ("problem", "solution", "public_goods_case", "use_of_funds", "contact_email")
               if not profile[field]]
    if not profile["success_metrics"]:
        missing.append("success_metrics")
    if not milestones:
        missing.append("milestones")
    draft = {"title": profile["project_name"], "programme": program["name"], "chain": program["chain"],
             "project_summary": profile["summary"], "problem": profile["problem"],
             "proposed_solution": profile["solution"], "public_goods_case": profile["public_goods_case"],
             "delivery_plan": milestones[:12], "budget_usd": profile.get("budget_usd", 0), "team": profile.get("team", ""), "repository_url": profile.get("repository_url", ""),
             "contact_email": profile["contact_email"], "use_of_funds": profile["use_of_funds"],
             'budget_breakdown_usd': profile['budget_breakdown_usd'],
             "success_metrics": profile["success_metrics"],
             "payment_and_monetization": {"requested_terms": program["payment"], "sustainable_paths": ["implementation services", "support subscriptions", "ecosystem integrations"], "disclosure": "Do not represent grant money as guaranteed revenue."}}
    package = {"id": str(uuid.uuid4()), "created_at": int(time.time()), "status": "draft", "program_id": program_id, "draft": draft,
               "missing_information": missing,
               "evidence": [{"url": program["official_url"], "kind": "official_programme_page"}, {"url": program["application_url"], "kind": "application_entrypoint"}],
               "submission": {"enabled": False, "status": "not_attempted", "reason": "Use the provider adapter; the official catalogue currently documents web intake pages."}}
    STORE.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = STORE / f"{package['id']}.json"
    path.write_text(json.dumps(package, indent=2) + "\n"); path.chmod(0o600)
    return package


def approve_grant_application(value: dict[str, Any]) -> dict[str, Any]:
    ident = _text(value.get("package_id", ""), 80)
    try:
        uuid.UUID(ident)
    except ValueError as exc:
        raise ValueError("Invalid package id") from exc
    path = STORE / f"{ident}.json"
    if not path.is_file():
        raise ValueError("Grant package not found")
    package = json.loads(path.read_text())
    if package.get("status") != "draft":
        raise ValueError("Only draft packages can be approved")
    package["status"] = "ready_for_submission"
    package["approval"] = {"approved_at": int(time.time()), "approval_id": hashlib.sha256(f"{ident}:{time.time_ns()}".encode()).hexdigest()[:24], "submission_mode": "provider_adapter"}
    missing = package.get("missing_information", [])
    reason = ("The packet still needs: " + ", ".join(missing) if missing else
              "The packet contains all general profile fields; a provider adapter must validate its current form.")
    package["submission"] = {"enabled": False, "status": "approved", "reason": reason}
    path.write_text(json.dumps(package, indent=2) + "\n"); path.chmod(0o600)
    return package


def submit_grant_application(value: dict[str, Any]) -> dict[str, Any]:
    """Execute the configured programme adapter and persist its receipt/status."""
    from grant_submission import submit_package
    ident = _text(value.get("package_id", ""), 80)
    try:
        uuid.UUID(ident)
    except ValueError as exc:
        raise ValueError("Invalid package id") from exc
    path = STORE / f"{ident}.json"
    if not path.is_file():
        raise ValueError("Grant package not found")
    package = json.loads(path.read_text())
    program = next((x for x in OFFICIAL_PROGRAMS if x["id"] == package.get("program_id")), None)
    if program is None:
        raise ValueError("Grant programme is not recorded in the package")
    result = submit_package(package, program, store_root=STORE)
    package["submission"] = result
    package["status"] = ("submitted" if result["status"] == "submitted" or
                         (result["status"] == "already_attempted" and result.get("previous_status") == "submitted") else
                         "draft" if result["status"] == "needs_information" else "submission_attempted")
    path.write_text(json.dumps(package, indent=2) + "\n"); path.chmod(0o600)
    return package


def grant_submission_history(value: dict[str, Any]) -> dict[str, Any]:
    from grant_submission import submission_history
    ident = _text(value.get("package_id", ""), 80)
    return {"package_id": ident, "attempts": submission_history(ident, store_root=STORE)}


def saved_grant_applications():
    rows = []
    for path in sorted(STORE.glob('*.json'), key=lambda item: item.stat().st_mtime, reverse=True)[:100]:
        try:
            uuid.UUID(path.stem)
            if path.stat().st_size > 100_000: continue
            package = json.loads(path.read_text())
            draft, submission = package.get('draft', {}), package.get('submission', {})
            if not isinstance(draft, dict) or not isinstance(submission, dict): continue
            rows.append({'id': path.stem, 'title': draft.get('title', 'Application'),
                         'programme': draft.get('programme', package.get('program_id', '')),
                         'budget_usd': draft.get('budget_usd', 0), 'status': package.get('status', 'draft'),
                         'submission': submission})
        except (ValueError, OSError, AttributeError):
            continue
    return {'packages': rows}


def grant_tools() -> list[dict[str, Any]]:
    profile = {"type": "object", "required": ["project_name", "summary"], "properties": {"project_name": {"type": "string", "minLength": 1, "maxLength": 160}, "summary": {"type": "string", "minLength": 1, "maxLength": 4000}, "topics": {"type": "array", "items": {"type": "string"}, "maxItems": 30}, "chains": {"type": "array", "items": {"type": "string"}, "maxItems": 20}, "repository_url": {"type": "string"}, "team": {"type": "string"}, "budget_usd": {"type": "number", "minimum": 0}, "milestones": {"type": "array", "items": {"type": "string"}}, "problem": {"type": "string", "maxLength": 4000}, "solution": {"type": "string", "maxLength": 4000}, "public_goods_case": {"type": "string", "maxLength": 4000}, "use_of_funds": {"type": "string", "maxLength": 4000}, "contact_email": {"type": "string", "maxLength": 320}, "success_metrics": {"type": "array", "maxItems": 12, "items": {"type": "string", "minLength": 1, "maxLength": 300}}}, "additionalProperties": False}
    profile['properties']['budget_breakdown_usd'] = {'type': 'object', 'maxProperties': 30,
        'additionalProperties': {'type': 'number', 'minimum': 0}}
    return [
        {"name": "list_blockchain_grants", "description": "List official blockchain grant sources with evidence URLs; current availability must be verified.", "inputSchema": {"type": "object", "additionalProperties": False}},
        {"name": "screen_blockchain_grants", "description": "Score official grant programmes against a project profile and return evidence and monetization paths.", "inputSchema": {"type": "object", "required": ["profile"], "properties": {"profile": profile, "program_ids": {"type": "array", "items": {"type": "string"}}}, "additionalProperties": False}},
        {"name": "draft_grant_application", "description": "Create a structured, evidence-linked grant application packet.", "inputSchema": {"type": "object", "required": ["profile", "program_id"], "properties": {"profile": profile, "program_id": {"type": "string"}, "milestones": {"type": "array", "items": {"type": "string"}}}, "additionalProperties": False}},
        {"name": "approve_grant_application", "description": "Mark a complete packet ready for its provider adapter.", "inputSchema": {"type": "object", "required": ["package_id"], "properties": {"package_id": {"type": "string", "format": "uuid"}}, "additionalProperties": False}},
        {"name": "submit_grant_application", "description": "Execute the configured official programme adapter and persist the provider receipt or exact unsupported status.", "inputSchema": {"type": "object", "required": ["package_id"], "properties": {"package_id": {"type": "string", "format": "uuid"}}, "additionalProperties": False}},
        {"name": "grant_submission_history", "description": "Return durable submission attempts and provider receipts for a grant packet.", "inputSchema": {"type": "object", "required": ["package_id"], "properties": {"package_id": {"type": "string", "format": "uuid"}}, "additionalProperties": False}},
    ]
