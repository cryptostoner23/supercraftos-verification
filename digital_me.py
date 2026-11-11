"""Digital Me module — identity, memory, reasoning, and planning for SuperCraftOS.

This module provides the "Digital Me" layer: a persistent identity with
retrieval‑augmented memory, deterministic reasoning over stored playbooks,
and actionable planning that the iOS app and backend can query via /api/digital_me/* routes.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "digital_me"
DATA.mkdir(parents=True, exist_ok=True)

IDENTITY_FILE = DATA / "identity.json"
MEMORY_FILE = DATA / "memory.json"
PLAYBOOKS_FILE = DATA / "playbooks.json"


# ── Identity ────────────────────────────────────────────────────────────────

def load_identity() -> Dict[str, Any]:
    """Load the persistent Digital Me identity, creating a fresh one if missing."""
    if IDENTITY_FILE.exists():
        return json.loads(IDENTITY_FILE.read_text())
    identity = {
        "id": str(uuid.uuid4()),
        "name": os.getenv("SUPERCRAFTOS_USER_NAME", "Digital Me"),
        "created_at": int(os.getenv("SUPERCRAFTOS_CREATED_AT", str(int(__import__('time').time())))),
        "metadata": {},
    }
    IDENTITY_FILE.write_text(json.dumps(identity, indent=2))
    return identity


def save_identity(identity: Dict[str, Any]) -> None:
    IDENTITY_FILE.write_text(json.dumps(identity, indent=2))


# ── Memory (retrieval‑augmented) ────────────────────────────────────────────

def load_memory() -> Dict[str, Any]:
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text())
    return {"entries": [], "checked_at": 0}


def save_memory(memory: Dict[str, Any]) -> None:
    MEMORY_FILE.write_text(json.dumps(memory, indent=2))


def add_memory_entry(entry: Dict[str, Any]) -> None:
    """Append a memory entry (timestamped observation, decision, or lesson)."""
    memory = load_memory()
    entry.setdefault("id", str(uuid.uuid4()))
    entry.setdefault("at", int(__import__('time').time()))
    memory["entries"].append(entry)
    # Keep only the last 500 entries to avoid unbounded growth
    if len(memory["entries"]) > 500:
        memory["entries"] = memory["entries"][-500:]
    memory["checked_at"] = int(__import__('time').time())
    save_memory(memory)


def retrieve_memory(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Return memory entries most relevant to the query.

    Relevance is scored by token overlap (query tokens found in the note) with
    a small recency tiebreak, so a query finds related memories even when it is
    not an exact substring of the note. Falls back to empty when the query is
    blank or nothing matches.
    """
    memory = load_memory()
    q = (query or "").lower()
    tokens = [t for t in q.split() if len(t) >= 2]
    if not tokens:
        return []
    scored = []
    for e in memory.get("entries", []):
        note = (e.get("note", "") or "").lower()
        if not note:
            continue
        overlap = sum(1 for t in tokens if t in note)
        if overlap == 0:
            continue
        # Normalize by query length; recency is a small tiebreak.
        score = overlap / len(tokens) + 0.01 * max(0.0, min(1.0, (e.get("at", 0) / max(1, _now()))))
        scored.append((score, e))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [e for _, e in scored[:max(1, min(limit, 500))]]


def _now() -> float:
    import time
    return time.time()


# ── Playbooks (reasoning patterns) ─────────────────────────────────────────

def load_playbooks() -> Dict[str, Any]:
    if PLAYBOOKS_FILE.exists():
        return json.loads(PLAYBOOKS_FILE.read_text())
    return {"playbooks": []}


def save_playbooks(playbooks: Dict[str, Any]) -> None:
    PLAYBOOKS_FILE.write_text(json.dumps(playbooks, indent=2))


def add_playbook(title: str, steps: List[str], description: str = "") -> None:
    """Add a new reasoning playbook (reusable execution pattern)."""
    playbooks = load_playbooks()
    pb = {
        "id": str(uuid.uuid4()),
        "title": title,
        "steps": steps,
        "description": description,
        "created_at": int(__import__('time').time()),
    }
    playbooks["playbooks"].append(pb)
    # Keep only the last 100 playbooks
    if len(playbooks["playbooks"]) > 100:
        playbooks["playbooks"] = playbooks["playbooks"][-100:]
    save_playbooks(playbooks)


def get_playbook(pb_id: str) -> Optional[Dict[str, Any]]:
    playbooks = load_playbooks()
    for pb in playbooks.get("playbooks", []):
        if pb["id"] == pb_id:
            return pb
    return None


def list_playbooks() -> List[Dict[str, Any]]:
    return load_playbooks().get("playbooks", [])


# ── Reasoning ───────────────────────────────────────────────────────────────

def reason_over_memory(query: str, context: str = "") -> Dict[str, Any]:
    """Run deterministic reasoning over relevant memory entries and return a summary."""
    entries = retrieve_memory(query, limit=5)
    if not entries:
        return {"summary": "No relevant memory found.", "actions": [], "confidence": 0.0}

    # Simple heuristic: count matching entries and summarize their notes
    notes = [e.get("note", "") for e in entries]
    combined = " ".join(notes)

    # Determine the most common action or theme
    action_keywords = ["fix", "create", "update", "delete", "review", "test", "deploy"]
    found_actions = [kw for kw in action_keywords if kw in combined.lower()]

    confidence = min(len(entries) / 5.0, 1.0)

    return {
        "summary": f"Found {len(entries)} relevant memory entry(s). "
        f"Common themes: {', '.join(set(found_actions)) or 'general observation'}.",
        "actions": found_actions or ["review"],
        "confidence": round(confidence, 2),
        "source_ids": [e.get("id") for e in entries[:3]],
    }


# ── Planning ────────────────────────────────────────────────────────────────

def plan_from_playbook(pb_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a plan by executing the steps of a named playbook with contextual overrides."""
    playbook = get_playbook(pb_id)
    if playbook is None:
        return {"error": f"Playbook {pb_id} not found", "plan": []}

    steps = playbook["steps"]
    # Apply simple contextual substitutions if the step contains {key}
    adapted: List[str] = []
    for step in steps:
        adapted_step = step
        for key, value in context.items():
            adapted_step = adapted_step.replace(f"{{{key}}}", str(value))
        adapted.append(adapted_step)

    return {
        "playbook_id": pb_id,
        "playbook_title": playbook["title"],
        "adapted_steps": adapted,
        "generated_at": int(__import__('time').time()),
    }


# ── API helper ──────────────────────────────────────────────────────────────

def api_profile_get() -> Dict[str, Any]:
    """GET /api/digital_me/profile → identity snapshot."""
    identity = load_identity()
    memory = load_memory()
    playbooks = list_playbooks()
    return {
        "identity": {k: v for k, v in identity.items() if k != "metadata"},
        "memory_entries": len(memory.get("entries", [])),
        "playbooks": len(playbooks),
        "memory_summary": retrieve_memory("recent", limit=3),
        "playbook_summaries": [
            {"id": p["id"], "title": p["title"]} for p in playbooks
        ],
    }


def api_memory_post(entry: Dict[str, Any]) -> Dict[str, Any]:
    """POST /api/digital_me/memory → add a memory entry."""
    add_memory_entry(entry)
    return {"status": "ok", "entry_id": entry.get("id")}


def api_memory_get(query: str = "", limit: int = 10) -> Dict[str, Any]:
    """GET /api/digital_me/memory → retrieved entries matching query."""
    return {"entries": retrieve_memory(query, limit=limit)}


def api_reasoning_post(request: Dict[str, Any]) -> Dict[str, Any]:
    """POST /api/digital_me/reasoning → reason over a query with optional context."""
    query = request.get("query", "")
    context = request.get("context", "")
    return reason_over_memory(query, context)


def api_planning_post(request: Dict[str, Any]) -> Dict[str, Any]:
    """POST /api/digital_me/planning → generate a plan from a playbook."""
    pb_id = request.get("playbook_id", "")
    context = request.get("context", {})
    return plan_from_playbook(pb_id, context)


def api_planning_get(playbook_id: str) -> Dict[str, Any]:
    """GET /api/digital_me/planning/{playbook_id} → get playbook details."""
    pb = get_playbook(playbook_id)
    if pb is None:
        return {"error": f"Playbook {playbook_id} not found"}
    return {
        "id": pb["id"],
        "title": pb["title"],
        "steps": pb["steps"],
        "description": pb["description"],
    }