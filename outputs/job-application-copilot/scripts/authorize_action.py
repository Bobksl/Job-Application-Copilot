#!/usr/bin/env python3
"""Create a short-lived, one-time authorization for an exact tool payload."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from quality_gate import GateError, load_json, validate_prewrite


def canonical_hash(value: dict) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_google_docs_request_order(requests: list[dict]) -> None:
    """Require direct typography to be the final phase of a Docs mutation batch."""
    structural_keys = {
        "insertText", "deleteContentRange", "replaceAllText",
        "createParagraphBullets", "deleteParagraphBullets",
        "updateParagraphStyle", "insertTable", "insertTableRow",
        "insertTableColumn", "deleteTableRow", "deleteTableColumn",
    }
    first_text_style = next(
        (index for index, request in enumerate(requests) if "updateTextStyle" in request),
        None,
    )
    if first_text_style is None:
        return
    for index, request in enumerate(requests[first_text_style + 1 :], first_text_style + 1):
        if structural_keys.intersection(request):
            raise GateError(
                "Google Docs payload applies text styling before a structural operation "
                f"at request {index}; apply all updateTextStyle requests last."
            )


def validate_target(action: str, payload: dict, change_set: dict) -> None:
    if action == "google_doc_update":
        raise GateError(
            "Direct resume and cover-letter Google Docs rewrites are disabled; "
            "return copy-ready text for manual paste-back."
        )
    elif action == "gmail_draft":
        if change_set["artifact"] != "email":
            raise GateError("Gmail draft authorization requires an email change set.")
        if not payload.get("to") or not payload.get("subject"):
            raise GateError("Gmail draft payload requires a recipient and subject.")
    else:
        raise GateError(f"Unsupported action: {action}.")


def write_authorization(data_dir: Path, authorization: dict) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    destination = data_dir / "active_authorization.json"
    temporary = data_dir / "active_authorization.json.tmp"
    temporary.write_text(json.dumps(authorization, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=["google_doc_update", "gmail_draft"], required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--change-set", type=Path, required=True)
    parser.add_argument("--fact-bank", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--ttl-seconds", type=int, default=300)
    args = parser.parse_args(argv)

    try:
        if not 30 <= args.ttl_seconds <= 600:
            raise GateError("Authorization lifetime must be between 30 and 600 seconds.")
        payload = load_json(args.payload)
        change_set = load_json(args.change_set)
        fact_bank = load_json(args.fact_bank)
        validate_prewrite(fact_bank, change_set)
        validate_target(args.action, payload, change_set)
        now = datetime.now(timezone.utc)
        authorization = {
            "schema_version": "1.0",
            "action": args.action,
            "case_id": change_set["case_id"],
            "change_set_id": change_set["change_set_id"],
            "payload_sha256": canonical_hash(payload),
            "issued_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(seconds=args.ttl_seconds)).isoformat().replace("+00:00", "Z"),
        }
        destination = write_authorization(args.data_dir, authorization)
    except (GateError, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({"result": "authorized", "path": str(destination),
                      "change_set_id": change_set["change_set_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
