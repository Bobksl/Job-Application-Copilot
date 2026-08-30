#!/usr/bin/env python3
"""Fail-closed guardrail for external application actions."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLACEHOLDER = re.compile(r"\[[^\[\]\n]{1,200}\]")
DOC_WRITE = "mcp__codex_apps__google_drive_batch_update_document"
GMAIL_DRAFT = "mcp__codex_apps__gmail_create_draft"
GMAIL_SEND = {
    "mcp__codex_apps__gmail_send_email",
    "mcp__codex_apps__gmail_send_draft",
}


def response(decision: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return bool(PLACEHOLDER.search(value))
    if isinstance(value, dict):
        return any(contains_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_placeholder(item) for item in value)
    return False


def consume_authorization(action: str, tool_input: dict) -> tuple[bool, str]:
    data_root = os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data_root:
        return False, "Plugin data directory is unavailable; explicit authorization cannot be verified."
    path = Path(data_root) / "active_authorization.json"
    try:
        authorization = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "No valid one-time authorization exists for this action."

    if authorization.get("action") != action:
        return False, "The active authorization is for a different action."
    if authorization.get("payload_sha256") != canonical_hash(tool_input):
        return False, "The tool payload differs from the approved payload."
    try:
        expires = datetime.fromisoformat(authorization["expires_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return False, "The active authorization has an invalid expiry."
    if expires <= datetime.now(timezone.utc):
        return False, "The one-time authorization has expired."

    try:
        path.unlink()
    except OSError:
        return False, "The one-time authorization could not be consumed safely."
    return True, "Approved one-time action matched exactly."


def evaluate(tool_name: str, tool_input: dict) -> dict:
    lowered = tool_name.lower()
    input_text = json.dumps(tool_input, ensure_ascii=False).lower()
    if tool_name in GMAIL_SEND:
        return response("deny", "Version 1 never sends email; create an approved draft instead.")
    if "submit" in lowered and "application" in lowered:
        return response("deny", "Version 1 never submits job applications.")
    interactive_surface = any(
        token in lowered for token in ("browser", "playwright", "computer", "node_repl")
    )
    submission_phrases = ("apply now", "submit application", "send application", "final submit")
    if interactive_surface and any(phrase in input_text for phrase in submission_phrases):
        return response("deny", "Version 1 blocks browser or computer application submission actions.")

    if tool_name == GMAIL_DRAFT:
        if contains_placeholder(tool_input):
            return response("deny", "Gmail draft contains an unresolved bracketed placeholder.")
        allowed, reason = consume_authorization("gmail_draft", tool_input)
        return response("allow" if allowed else "deny", reason)

    if tool_name == DOC_WRITE:
        return response(
            "deny",
            "Direct resume and cover-letter Google Docs rewrites are disabled; "
            "return a copy-ready change table and let the candidate apply edits manually.",
        )

    return response("allow", "No restricted application action detected.")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input") or {}
        output = evaluate(tool_name, tool_input)
    except Exception:
        output = response("deny", "Guardrail input was invalid; action blocked fail-closed.")
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
