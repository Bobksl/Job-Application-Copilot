#!/usr/bin/env python3
"""Build an offline, one-way projection payload from local application records."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


OUTCOME_FIELDS = (
    "status",
    "predicted_fit_score",
    "eligibility_gate",
    "language_gate",
    "provenance",
    "resolved_at",
)
LOCAL_METADATA_FIELDS = ("deadline", "channel")
URI_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


def load_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def require_text(record: dict, field: str, path: Path) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} is missing {field}")
    return value


def filename_from_reference(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    reference = value.strip()
    if not reference or URI_PATTERN.match(reference) or reference.lower().startswith("file:"):
        return None
    filename = reference.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if filename in {"", ".", ".."} or "\n" in filename or "\r" in filename:
        return None
    return filename


def filename_from_document_id(value: object) -> str | None:
    filename = filename_from_reference(value)
    if filename is None or not isinstance(value, str):
        return None
    reference = value.strip()
    is_path = "/" in reference or "\\" in reference
    has_extension = (
        "." in filename
        and not filename.startswith(".")
        and not filename.endswith(".")
    )
    return filename if is_path or has_extension else None


def document_filenames(case: dict) -> list[str]:
    documents = case.get("documents", {})
    if not isinstance(documents, dict):
        raise ValueError("case documents must be a JSON object")

    filenames = set()
    for record in documents.values():
        if not isinstance(record, dict):
            continue
        reference = record.get("filename")
        filename = filename_from_reference(reference)
        if filename is None:
            filename = filename_from_document_id(record.get("document_id"))
        if filename is not None:
            filenames.add(filename)
    return sorted(filenames)


def posting_url(case: dict) -> str | None:
    jd = case.get("jd")
    if not isinstance(jd, dict) or jd.get("source_type") != "url":
        return None
    source = jd.get("source")
    return source if isinstance(source, str) and source.strip() else None


def projected_stages(outcome: dict) -> list[dict]:
    stages = outcome.get("stages", [])
    if not isinstance(stages, list):
        raise ValueError("outcome stages must be a JSON array")

    projected = []
    for stage in stages:
        if not isinstance(stage, dict):
            raise ValueError("each outcome stage must be a JSON object")
        name = stage.get("stage")
        event_date = stage.get("date")
        if not isinstance(name, str) or not isinstance(event_date, str):
            raise ValueError("each outcome stage requires string stage and date fields")
        projected.append({"stage": name, "date": event_date})
    return projected


def build_row(case_path: Path, redact: bool) -> dict:
    case = load_object(case_path)
    case_id = require_text(case, "case_id", case_path)
    row = {
        "key": case_id,
        "company": require_text(case, "company", case_path),
        "role": require_text(case, "role", case_path),
    }

    outcome_path = case_path.parent / "application_outcome.json"
    outcome = None
    if outcome_path.exists():
        outcome = load_object(outcome_path)
        if require_text(outcome, "case_id", outcome_path) != case_id:
            raise ValueError(f"{outcome_path} does not match {case_id}")
        for field in OUTCOME_FIELDS:
            if field in outcome and outcome[field] is not None:
                row[field] = outcome[field]
        stages = projected_stages(outcome)
        row["stages"] = stages
        applied_dates = [
            stage["date"]
            for stage in stages
            if stage["stage"].strip().lower().replace(" ", "_") == "applied"
        ]
        if applied_dates:
            row["applied_on"] = min(applied_dates)

    for field in LOCAL_METADATA_FIELDS:
        if outcome is not None and field in outcome and outcome[field] is not None:
            row[field] = outcome[field]
        elif field in case and case[field] is not None:
            row[field] = case[field]

    if not redact:
        row["documents"] = document_filenames(case)
        url = posting_url(case)
        if url is not None:
            row["url"] = url
    return row


def build_payload(data_dir: Path, redact: bool) -> dict:
    case_paths = sorted((data_dir.resolve() / "cases").glob("*/application_case.json"))
    rows = []
    case_ids = set()
    for case_path in case_paths:
        row = build_row(case_path, redact)
        if row["key"] in case_ids:
            raise ValueError(f"duplicate case_id: {row['key']}")
        case_ids.add(row["key"])
        rows.append(row)
    rows.sort(key=lambda row: row["key"])
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {"generated_at": generated_at.replace("+00:00", "Z"), "rows": rows}


def render_payload(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export local application state as a one-way projection payload."
    )
    parser.add_argument("--data-dir", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path)
    parser.add_argument("--redact", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rendered = render_payload(build_payload(args.data_dir, args.redact))
        if args.out is None:
            sys.stdout.write(rendered)
        else:
            args.out.write_text(rendered, encoding="utf-8", newline="\n")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        message = str(exc).replace("\r", " ").replace("\n", " ")
        print(f"BLOCKED: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
