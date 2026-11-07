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
from typing import Any, Dict, List

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


async def composio_list_connected_accounts() -> List[Dict[str, Any]]:
    """List accounts connected to Composio (Gmail appears as GMAIL)."""
    client = httpx.AsyncClient(timeout=30)
    try:
        resp = await client.get(
            f"{composio_base()}/api/v3.1/accounts",
            headers=await _composio_headers(),
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        accounts = data.get("items") or data.get("accounts") or []
        return [a for a in accounts if isinstance(a, dict)]
    finally:
        await client.aclose()


async def composio_gmail_status() -> Dict[str, Any]:
    """Status of Composio Gmail integration."""
    if not composio_key():
        return {"provider": "composio", "connected": False, "reason": "COMPOSIO_API_KEY missing"}
    try:
        accounts = await composio_list_connected_accounts()
        gmail = [a for a in accounts if "gmail" in str(a.get("appUniqueId") or a.get("app") or a.get("provider") or "").lower()]
        return {
            "provider": "composio",
            "connected": bool(gmail),
            "gmail_accounts": len(gmail),
            "total_accounts": len(accounts),
        }
    except Exception as exc:
        return {"provider": "composio", "connected": False, "reason": type(exc).__name__}


async def composio_execute_tool(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a Composio tool (e.g. GMAIL_SEND_EMAIL)."""
    if not composio_key():
        raise RuntimeError("COMPOSIO_API_KEY is required for Composio mail")
    client = httpx.AsyncClient(timeout=60)
    try:
        resp = await client.post(
            f"{composio_base()}/api/v3.1/tools/execute/{tool}",
            headers=await _composio_headers(),
            json={"arguments": arguments},
        )
        body = resp.json() if resp.content else {}
        return {"http_status": resp.status_code, "successful": body.get("successful"), "response_data": body.get("response_data", body)}
    finally:
        await client.aclose()


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
            "to": to, "subject": subject, "body": body,
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
        return await composio_execute_tool("GMAIL_GET_MESSAGES", {"limit": limit})
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