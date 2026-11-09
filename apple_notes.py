"""Apple Notes-style notes store — encrypted, local, API-backed.

Each note is stored as its own JSON file under data/notes/. The free-form
content (title, body, tags, checklist) is encrypted at rest with AES-256-GCM
using a server-only key in data/notes.key (chmod 600, gitignored). Structural
metadata needed to render the list (id, notebook, pinned, timestamps) stays in
plaintext so the list endpoint can sort and filter without decrypting every
body; the sensitive text is only decrypted on the server when requested.

The module mirrors the vault key pattern in notion_db_setup: the key is derived
from a 32-byte file under data/, and code recomputes paths from ROOT so tests
can patch `apple_notes.ROOT` with a TemporaryDirectory.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

_TITLE_MAX = 200
_BODY_MAX = 200_000
_NOTEBOK_MAX = 60
_NOTES_MAX = 100_000

# Serialize writes to note files. The server is threaded, so two requests may
# race on the same note without this lock. RLock lets helper functions that
# already hold the write lock re-acquire it safely.
_write_lock = threading.RLock()


def _notes_dir() -> Path:
    path = ROOT / "data" / "notes"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _key_path() -> Path:
    return ROOT / "data" / "notes.key"


def _load_key() -> bytes:
    """Return the 32-byte notes key, creating it on first use."""
    path = _key_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists():
        key = path.read_bytes()
        if len(key) == 32:
            return key
    key = os.urandom(32)
    path.write_bytes(key)
    path.chmod(0o600)
    return key


def _encrypt_text(text: str) -> tuple[str, str]:
    """Encrypt a string. Returns (nonce_b64, ciphertext_b64)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    ciphertext = AESGCM(_load_key()).encrypt(nonce, text.encode("utf-8"), None)
    return base64.b64encode(nonce).decode(), base64.b64encode(ciphertext).decode()


def _decrypt_payload(nonce_b64: str, ciphertext_b64: str) -> dict[str, Any]:
    """Decrypt a stored payload envelope back into a dict."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = base64.b64decode(nonce_b64)
    ciphertext = base64.b64decode(ciphertext_b64)
    plain = AESGCM(_load_key()).decrypt(nonce, ciphertext, None)
    value = json.loads(plain.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("note_payload_not_object")
    return value


def _path(note_id: str) -> Path:
    return _notes_dir() / f"{note_id}.json"


def _read_raw(note_id: str) -> dict[str, Any] | None:
    path = _path(note_id)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or not raw.get("id") or not raw.get("nonce") or raw.get("payload") is None:
        return None
    return raw


def _write_raw(note_id: str, raw: dict[str, Any]) -> None:
    directory = _notes_dir()
    temporary = directory / f".{note_id}.tmp"
    temporary.write_text(json.dumps(raw, separators=(",", ":")))
    temporary.chmod(0o600)
    temporary.replace(_path(note_id))


def _decrypt(raw: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return _decrypt_payload(raw["nonce"], raw["payload"])
    except Exception:
        return None


def create_note(title: str = "", body: str = "", notebook: str = "Default",
                tags: list[str] | None = None) -> dict[str, Any]:
    """Create a note and return its full decrypted representation."""
    title = (title or "").strip()
    notebook = (notebook or "Default").strip() or "Default"
    if not title:
        raise ValueError("title_required")
    if len(title) > _TITLE_MAX:
        raise ValueError("title_too_long")
    if len(body) > _BODY_MAX:
        raise ValueError("body_too_long")
    if len(notebook) > _NOTEBOK_MAX:
        raise ValueError("notebook_too_long")

    tags = [str(t).strip() for t in (tags or []) if str(t).strip()]
    payload = {"title": title, "body": body or "", "tags": tags, "checklist": []}
    nonce, ciphertext = _encrypt_text(json.dumps(payload))
    now = int(time.time())
    note_id = uuid.uuid4().hex
    raw = {
        "id": note_id,
        "created_at": now,
        "updated_at": now,
        "pinned": False,
        "notebook": notebook,
        "nonce": nonce,
        "payload": ciphertext,
    }
    with _write_lock:
        _write_raw(note_id, raw)
    return get_note(note_id)


def get_note(note_id: str) -> dict[str, Any] | None:
    """Return a full decrypted note, or None if it does not exist."""
    raw = _read_raw(note_id)
    if raw is None:
        return None
    payload = _decrypt(raw)
    if payload is None:
        return None
    return {
        "id": raw["id"],
        "title": payload.get("title", ""),
        "body": payload.get("body", ""),
        "notebook": raw.get("notebook", "Default"),
        "tags": payload.get("tags", []),
        "checklist": payload.get("checklist", []),
        "pinned": bool(raw.get("pinned")),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
    }


def list_notes(query: str = "") -> list[dict[str, Any]]:
    """Metadata list for the notes screen. Titles are decrypted, bodies are not."""
    q = (query or "").strip().lower()
    notes: list[dict[str, Any]] = []
    for path in _notes_dir().glob("*.json"):
        if path.name.startswith("."):
            continue
        raw = _read_raw(path.stem)
        if raw is None:
            continue
        payload = _decrypt(raw)
        if payload is None:
            continue
        title = payload.get("title", "")
        if q:
            haystack = " ".join([title, raw.get("notebook", ""), *payload.get("tags", [])]).lower()
            if q not in haystack:
                continue
        notes.append({
            "id": raw["id"],
            "title": title,
            "notebook": raw.get("notebook", "Default"),
            "tags": payload.get("tags", []),
            "pinned": bool(raw.get("pinned")),
            "created_at": raw.get("created_at"),
            "updated_at": raw.get("updated_at"),
            "checklist_items": len(payload.get("checklist", [])),
        })
    notes.sort(key=lambda n: (not n["pinned"], -(n["updated_at"] or 0)))
    return notes


def _load_for_update(note_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = _read_raw(note_id)
    if raw is None:
        raise KeyError(note_id)
    payload = _decrypt(raw)
    if payload is None:
        raise KeyError(note_id)
    return raw, payload


def _persist_payload(note_id: str, raw: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    nonce, ciphertext = _encrypt_text(json.dumps(payload))
    raw["nonce"] = nonce
    raw["payload"] = ciphertext
    raw["updated_at"] = int(time.time())
    with _write_lock:
        _write_raw(note_id, raw)
    return raw


def update_note(note_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a partial patch to a note and return the updated note."""
    if not isinstance(patch, dict):
        raise ValueError("patch_not_object")
    with _write_lock:
        raw, payload = _load_for_update(note_id)
        if "title" in patch:
            title = str(patch["title"]).strip()
            if not title:
                raise ValueError("title_required")
            if len(title) > _TITLE_MAX:
                raise ValueError("title_too_long")
            payload["title"] = title
        if "body" in patch:
            body = str(patch["body"])
            if len(body) > _BODY_MAX:
                raise ValueError("body_too_long")
            payload["body"] = body
        if "notebook" in patch:
            notebook = str(patch["notebook"]).strip() or "Default"
            if len(notebook) > _NOTEBOK_MAX:
                raise ValueError("notebook_too_long")
            raw["notebook"] = notebook
        if "tags" in patch:
            tags = patch["tags"]
            if not isinstance(tags, list):
                raise ValueError("tags_not_list")
            payload["tags"] = [str(t).strip() for t in tags if str(t).strip()]
        if "checklist" in patch:
            checklist = patch["checklist"]
            if not isinstance(checklist, list):
                raise ValueError("checklist_not_list")
            payload["checklist"] = [
                {"text": str(item.get("text", "")), "checked": bool(item.get("checked", False)),
                 "id": item.get("id") or uuid.uuid4().hex}
                for item in checklist if isinstance(item, dict)
            ]
        _persist_payload(note_id, raw, payload)
    return get_note(note_id)


def delete_note(note_id: str) -> dict[str, Any]:
    """Delete a note. Raises KeyError if it does not exist."""
    with _write_lock:
        if _path(note_id).exists():
            _path(note_id).unlink()
        else:
            raise KeyError(note_id)
    return {"id": note_id, "deleted": True}


def pin_note(note_id: str) -> dict[str, Any]:
    """Toggle the pinned state of a note."""
    with _write_lock:
        raw, _ = _load_for_update(note_id)
        raw["pinned"] = not bool(raw.get("pinned"))
        raw["updated_at"] = int(time.time())
        with _write_lock:
            _write_raw(note_id, raw)
    return {"id": note_id, "pinned": raw["pinned"]}


def add_checklist_item(note_id: str, text: str) -> dict[str, Any]:
    """Append a checklist item to a note."""
    text = (text or "").strip()
    if not text:
        raise ValueError("checklist_text_required")
    with _write_lock:
        raw, payload = _load_for_update(note_id)
        payload.setdefault("checklist", [])
        payload["checklist"].append({"id": uuid.uuid4().hex, "text": text, "checked": False})
        _persist_payload(note_id, raw, payload)
    return get_note(note_id)


def toggle_checklist_item(note_id: str, index: int) -> dict[str, Any]:
    """Flip the checked state of a checklist item by index."""
    if not isinstance(index, int):
        raise ValueError("checklist_index_invalid")
    with _write_lock:
        raw, payload = _load_for_update(note_id)
        checklist = payload.get("checklist", [])
        if index < 0 or index >= len(checklist):
            raise ValueError("checklist_index_out_of_range")
        item = checklist[index]
        item["checked"] = not item.get("checked", False)
        _persist_payload(note_id, raw, payload)
    return get_note(note_id)


def list_notebooks() -> list[dict[str, Any]]:
    """Distinct notebooks with note counts, most recently used first."""
    counts: dict[str, int] = {}
    last_updated: dict[str, int] = {}
    for path in _notes_dir().glob("*.json"):
        if path.name.startswith("."):
            continue
        raw = _read_raw(path.stem)
        if raw is None:
            continue
        notebook = raw.get("notebook", "Default")
        counts[notebook] = counts.get(notebook, 0) + 1
        last_updated[notebook] = max(last_updated.get(notebook, 0), raw.get("updated_at") or 0)
    return [
        {"notebook": name, "count": counts[name], "updated_at": last_updated.get(name, 0)}
        for name in sorted(counts, key=lambda n: (-last_updated.get(n, 0), n.lower()))
    ]
