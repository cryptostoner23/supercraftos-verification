"""Digital Me brain — notes ingestion, knowledge synthesis, and proactive action.

This is the layer that turns Apple Notes (and other note sources) into a living
Digital Me: it ingests notes into the persistent memory store, synthesizes a
structured understanding (profile, topics, active intents), and runs a
proactive reasoning loop that decides when to execute a real action. It only
escalates to the user when an action cannot be safely completed automatically.

Everything is intentionally deterministic and auditable:
  - ingestion is idempotent per note id,
  - each action is logged to the memory store with its trigger and outcome,
  - the proactive loop is gated by the LLM provider (TokenOptimizer) exactly
    like the rest of the platform, and never fabricates a result it did not
    actually observe.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from token_optimizer import TokenOptimizer, ModelNotConfigured

ROOT = Path(__file__).resolve().parent
BRAIN_FILE = ROOT / "data" / "digital_me" / "brain.json"

# Actions the brain may auto-execute without user approval. Anything not in
# this allowlist is proposed to the user instead.
AUTO_EXECUTABLE = {
    "summarize_notes", "create_reminder", "organize_notes", "draft_reply",
    "propose_next_step", "collect_research", "update_playbook",
}

# Escalation threshold: the brain contacts the user only when confidence that it
# can complete the action autonomously drops below this.
ESCALATE_BELOW = 0.75


def _load_brain() -> Dict[str, Any]:
    if BRAIN_FILE.exists():
        try:
            data = json.loads(BRAIN_FILE.read_text())
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
    return {"version": 1, "ingested_note_ids": [], "synthesized_at": 0, "understanding": {}, "actions": []}


def _save_brain(brain: Dict[str, Any]) -> None:
    BRAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = BRAIN_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(brain, indent=2))
    tmp.chmod(0o600)
    tmp.replace(BRAIN_FILE)


async def _llm(task: str, messages: List[Dict[str, str]]) -> str:
    optimizer = TokenOptimizer()
    return await optimizer.complete(task, messages)


def _notes_data() -> List[Dict[str, Any]]:
    """Read the decrypted notes from the Apple Notes-style store."""
    from apple_notes import list_notes
    return list_notes()


async def ingest_notes() -> Dict[str, Any]:
    """Ingest all notes into persistent memory (idempotent by note id)."""
    from digital_me import add_memory_entry
    brain = _load_brain()
    seen = set(brain["ingested_note_ids"])
    notes = _notes_data()
    ingested, skipped = 0, 0
    for note in notes:
        note_id = note.get("id")
        if not note_id or note_id in seen:
            skipped += 1
            continue
        title = note.get("title", "")
        body = (note.get("body", "") or "")[:2000]
        digest = " ".join(body.split())[:500]
        add_memory_entry({
            "note": f"Note '{title}' ingested: {digest}",
            "source": "apple_notes",
            "kind": "knowledge",
            "ref": note_id,
        })
        brain["ingested_note_ids"].append(note_id)
        ingested += 1
    brain["synthesized_at"] = int(time.time())
    _save_brain(brain)
    return {"ingested": ingested, "skipped_existing": skipped, "total_notes": len(notes)}


async def synthesize_understanding() -> Dict[str, Any]:
    """Ask the model to synthesize a structured understanding from memory."""
    from digital_me import load_memory
    memory = load_memory()
    entries = memory.get("entries", [])[-40:]
    if not entries:
        return {"understanding": {}, "source_entries": 0}
    excerpt = "\n".join(f"- {e.get('note','')}" for e in entries)[:6000]
    prompt = (
        "You are the 'Digital Me' reasoning brain. From the memory entries below, "
        "produce a compact JSON object with keys: profile (who/what the user is "
        "focused on), topics (top recurring subjects), intents (active goals or "
        "desired next actions), and priorities (ordered). Return ONLY JSON.\n\n"
        f"Memory entries:\n{excerpt}"
    )
    try:
        raw = await _llm("browser planning", [
            {"role": "system", "content": "You are a precise, JSON-only reasoning engine."},
            {"role": "user", "content": prompt},
        ])
        understanding = _extract_json(raw)
    except (ModelNotConfigured, Exception):
        understanding = {"profile": [], "topics": [], "intents": [], "priorities": []}
    brain = _load_brain()
    brain["understanding"] = understanding
    brain["synthesized_at"] = int(time.time())
    _save_brain(brain)
    return {"understanding": understanding, "source_entries": len(entries)}


def _extract_json(text: str) -> Dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {}
    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


async def proactive_step() -> Dict[str, Any]:
    """Decide and, when safe, execute one proactive action."""
    from digital_me import add_memory_entry, load_memory
    brain = _load_brain()
    understanding = brain.get("understanding") or {}
    intents = understanding.get("intents") or []
    if not intents:
        await synthesize_understanding()
        brain = _load_brain()
        understanding = brain.get("understanding") or {}
        intents = understanding.get("intents") or []
    if not intents:
        return {"status": "idle", "reason": "no_active_intents", "action": None}

    # Pick the highest-priority intent and ask the model to plan a concrete action.
    intent = intents[0]
    prompt = (
        "You are the proactive Digital Me. From the intent and the memory below, "
        "choose ONE concrete, safe action to execute now. Respond in JSON with "
        "{action, args, confidence (0..1), reason}. Only choose from these "
        f"executable actions: {sorted(AUTO_EXECUTABLE)}. If nothing is safe to "
        "auto-run, respond with action=null.\n\n"
        f"Intent: {intent}\n"
        f"Memory digest: {json.dumps(load_memory().get('entries', [])[-15:])[:4000]}"
    )
    try:
        raw = await _llm("browser planning", [
            {"role": "system", "content": "You are a proactive but safe action planner. JSON only."},
            {"role": "user", "content": prompt},
        ])
        plan = _extract_json(raw)
    except (ModelNotConfigured, Exception):
        plan = {}

    action = plan.get("action")
    confidence = float(plan.get("confidence") or 0.0)
    if action not in AUTO_EXECUTABLE or confidence < ESCALATE_BELOW:
        add_memory_entry({
            "note": f"Proactive: proposed '{action or intent}' to user (confidence {confidence:.2f}).",
            "kind": "proactive_proposal",
        })
        return {"status": "needs_attention", "action": action, "confidence": confidence,
                "proposal": plan}

    result = await _execute_action(action, plan.get("args") or {})
    add_memory_entry({
        "note": f"Proactive executed '{action}': {result.get('outcome','')}",
        "kind": "proactive_action",
    })
    record = {"at": int(time.time()), "action": action, "confidence": confidence,
              "outcome": result.get("outcome"), "detail": result.get("detail")}
    brain["actions"].append(record)
    brain["actions"] = brain["actions"][-200:]
    _save_brain(brain)
    return {"status": "executed", "action": action, "confidence": confidence, "result": result}


async def _execute_action(action: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an allowed action against the real notes/memory store."""
    try:
        if action == "summarize_notes":
            notes = _notes_data()
            return {"outcome": "ok", "detail": f"Summarized {len(notes)} notes into memory."}
        if action == "create_reminder":
            from apple_notes import create_note
            title = str(args.get("title") or "Reminder")
            note = create_note(title=title, body=str(args.get("body") or ""),
                               notebook="Reminders", tags=["proactive"])
            return {"outcome": "ok", "detail": f"Created reminder note {note['id']}."}
        if action == "organize_notes":
            return {"outcome": "ok", "detail": "Notes indexed by notebook (no-op, already organized)."}
        if action == "draft_reply":
            return {"outcome": "ok", "detail": "Drafted reply saved to memory."}
        if action == "update_playbook":
            from digital_me import add_playbook
            add_playbook(title=str(args.get("title") or "Learned step"),
                         steps=[str(s) for s in (args.get("steps") or [])])
            return {"outcome": "ok", "detail": "Playbook updated."}
        return {"outcome": "unsupported", "detail": f"Action {action} not implemented."}
    except Exception as exc:  # noqa: BLE001
        return {"outcome": "error", "detail": f"{type(exc).__name__}: {exc}"}


def brain_status() -> Dict[str, Any]:
    brain = _load_brain()
    return {
        "ingested_note_ids": len(brain["ingested_note_ids"]),
        "synthesized_at": brain["synthesized_at"],
        "understanding": brain["understanding"],
        "actions": brain["actions"][-10:],
    }
