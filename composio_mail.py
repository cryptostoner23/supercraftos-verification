"""Gmail/notes integration via Composio (preferred) with IMAP fallback.

This module exposes durable, real integrations:

  * Composio — when COMPOSIO_API_KEY is set and a Gmail account is connected
    through Composio's auth flow, it uses Composio's Gmail tools to send and
    read mail.
  * IMAP fallback — when GMAIL_ADDRESS + GMAIL_APP_PASSWORD (or OAuth token)
    are set, it reads the inbox directly over IMAP.

All operations either succeed with real evidence or return a clear, honest
status (e.g. authentic_required). Nothing is simulated.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

import httpx


# ── Composio helpers ─────────────────────────────────────────────────────────

def composio_key() -> str:
    return os.getenv("COMPOSIO_API_KEY") or ""


def composio_base() -> str:
    return os.getenv("COMPOSIO_BASE_URL", "https://backend.composio.dev")


async def _composio_headers() -> Dict[str, str]:
    key = composio_key()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["x-api-key"] = key
    return headers


def _find_composio_cli() -> str:
    """Locate the composio CLI binary."""
    for candidate in (
        os.getenv("COMPOSIO_CLI") or "",
        "composio",
        "/root/.local/bin/composio",
        "/var/lib/supercraftos/autonomous/bin/composio",
        "/var/lib/supercraftos/autonomous/composio-cli/composio",
    ):
        if candidate and (os.path.exists(candidate) or candidate == "composio"):
            return candidate
    return "composio"


async def composio_list_connected_accounts() -> List[Dict[str, Any]]:
    """List accounts connected to Composio via the CLI (REST account API is not public).

    Returns a flat list of connection records with keys: app, status,
    display_name/alias, id.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            _find_composio_cli(), "connections", "list",
            env={**os.environ, "COMPOSIO_QUIET": "1"},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        data = json.loads(stdout.decode())
    except Exception:
        return []
    accounts: List[Dict[str, Any]] = []
    if isinstance(data, dict):
        for app, conns in data.items():
            for c in conns if isinstance(conns, list) else []:
                if isinstance(c, dict):
                    accounts.append({**c, "app": app})
    return accounts


async def composio_gmail_status() -> Dict[str, Any]:
    """Status of Composio Gmail integration."""
    if not composio_key():
        return {"provider": "composio", "connected": False, "reason": "COMPOSIO_API_KEY missing"}
    try:
        accounts = await composio_list_connected_accounts()
        gmail = [a for a in accounts
                 if a.get("app", "").lower() == "gmail" and a.get("status") == "ACTIVE"]
        return {
            "provider": "composio",
            "connected": bool(gmail),
            "gmail_accounts": len(gmail),
            "total_accounts": len(accounts),
            "gmail_addresses": [a.get("display_name") or a.get("alias") for a in gmail if a.get("display_name") or a.get("alias")],
        }
    except Exception as exc:
        return {"provider": "composio", "connected": False, "reason": type(exc).__name__}


async def _first_active_gmail_account() -> Optional[Dict[str, Any]]:
    """Return the first ACTIVE Composio Gmail connection (for account selection)."""
    for account in await composio_list_connected_accounts():
        if account.get("app", "").lower() == "gmail" and account.get("status") == "ACTIVE":
            return account
    return None


async def composio_execute_tool(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a Composio tool via the CLI (reliable account resolution)."""
    if not composio_key():
        raise RuntimeError("COMPOSIO_API_KEY is required for Composio mail")
    account = await _first_active_gmail_account()
    if account is None:
        return {"successful": False, "reason": "No active Gmail connection in Composio"}
    cli = _find_composio_cli()
    try:
        proc = await asyncio.create_subprocess_exec(
            cli, "execute", tool, "--account", account.get("word_id") or account.get("id"),
            "-d", json.dumps(arguments),
            env={**os.environ, "COMPOSIO_QUIET": "1"},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=90)
        body = json.loads(stdout.decode())
    except Exception as exc:
        return {"successful": False, "reason": f"cli_error: {type(exc).__name__}"}
    return {
        "successful": bool(body.get("successful")),
        "response_data": body.get("data"),
        "error": body.get("error"),
    }


# ── IMAP fallback ────────────────────────────────────────────────────────────

async def imap_read_mail(limit: int = 10) -> List[Dict[str, Any]]:
    from gmail_mailbox import GmailMailbox
    try:
        messages = await asyncio.to_thread(GmailMailbox().search, phrase="", limit=limit)
    except RuntimeError as exc:
        raise RuntimeError(f"IMAP unavailable: {exc}") from exc
    return messages


# ── High-level tools (bound to MCP handlers) ────────────────────────────────

async def gmail_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Report Gmail integration status across Composio and IMAP."""
    composio = await composio_gmail_status()
    imap_configured = bool(os.getenv("GMAIL_ADDRESS") and (os.getenv("GMAIL_APP_PASSWORD") or os.getenv("GMAIL_OAUTH_ACCESS_TOKEN")))
    return {
        "composio": composio,
        "imap_configured": imap_configured,
        "provider": "composio" if composio.get("connected") else ("imap" if imap_configured else "not_connected"),
        "connected": bool(composio.get("connected") or imap_configured),
    }


async def gmail_send(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Send an email. Uses Composio Gmail if a Gmail account is connected; otherwise reports the blocker."""
    to = arguments.get("to", "")
    subject = arguments.get("subject", "")
    body = arguments.get("body", "")
    if not (to and subject and body):
        return {"accepted": False, "reason": "to, subject and body are all required"}

    # Prefer Composio when a Gmail account is connected.
    status = await composio_gmail_status()
    if status.get("connected"):
        return await composio_execute_tool("GMAIL_SEND_EMAIL", {
            "recipient_email": to, "subject": subject, "body": body,
        })

    # No live sender available without credentials.
    return {
        "accepted": False,
        "reason": "No connected Gmail account. Connect one through Composio, or set GMAIL_ADDRESS/GMAIL_APP_PASSWORD for read-only IMAP (sending still needs a provider).",
    }


async def gmail_read(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Read recent Gmail messages. Uses Composio if connected, else IMAP."""
    limit = int(arguments.get("limit", 10))
    limit = max(1, min(limit, 50))
    status = await composio_gmail_status()
    if status.get("connected"):
        # Composio read: fetch recent messages.
        return await composio_execute_tool("GMAIL_LIST_MESSAGES", {"user_id": "me", "max_results": limit})
    if os.getenv("GMAIL_ADDRESS"):
        return {"messages": await imap_read_mail(limit=limit)}
    return {"reason": "No Gmail credentials. Connect a Gmail account through Composio or set GMAIL_ADDRESS."}


def gmail_tools() -> List[Dict[str, Any]]:
    """Tool schemas registered into the MCP registry."""
    return [
        {
            "name": "gmail_status",
            "description": "Check whether Gmail integration is available (Composio connected account or IMAP credentials). Returns the active provider.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "gmail_send",
            "description": "Send an email through the connected Gmail integration. Uses Composio Gmail. Returns real delivery evidence or the exact blocker (never simulates sending).",
            "inputSchema": {"type": "object", "properties": {
                "to": {"type": "string", "minLength": 3},
                "subject": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
            }, "required": ["to", "subject", "body"], "additionalProperties": False},
        },
        {
            "name": "gmail_read",
            "description": "Read recent Gmail inbox messages via Composio or IMAP. Returns message subjects, senders and dates.",
            "inputSchema": {"type": "object", "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            }, "additionalProperties": False},
        },
    ]