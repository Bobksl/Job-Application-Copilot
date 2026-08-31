#!/usr/bin/env python3
"""Record local application outcomes without overwriting prior evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "application_outcome.schema.json"
FINAL_STATUSES = {"hired", "rejected", "no_response", "offer_declined", "withdrawn"}
OPEN_STATUSES = {"drafted", "applied", "interview", "offer"}
LEGACY_STATUSES = {"no response": "no_response", "offer declined": "offer_declined"}


def normalize_status(value: str) -> str:
    return LEGACY_STATUSES.get(value, value)


def schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_record(record: dict) -> None:
    errors = sorted(schema_validator().iter_errors(record), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ValueError(f"outcome record failed schema validation: {details}")


def load_record(path: Path) -> dict:
    record = json.loads(path.read_text(encoding="utf-8"))
    record["status"] = normalize_status(record.get("status", ""))
    validate_record(record)
    return record


def atomic_write(path: Path, record: dict) -> None:
    validate_record(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(record, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def outcome_path_for_case(case_path: Path) -> Path:
    return case_path.resolve().parent / "application_outcome.json"


def find_outcome(data_dir: Path, case_id: str) -> Path:
    matches = []
    for path in (data_dir.resolve() / "cases").glob("*/application_outcome.json"):
        try:
            if load_record(path)["case_id"] == case_id:
                matches.append(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    if not matches:
        raise FileNotFoundError(f"no outcome record found for {case_id}")
    if len(matches) > 1:
        raise ValueError(f"multiple outcome records found for {case_id}")
    return matches[0]


def require_open(record: dict) -> None:
    if record["status"] in FINAL_STATUSES:
        raise ValueError(f"{record['case_id']} is already resolved")


def init_outcome(case_path: Path) -> Path:
    case_path = case_path.resolve()
    case = json.loads(case_path.read_text(encoding="utf-8"))
    outcome_path = outcome_path_for_case(case_path)
    if outcome_path.exists():
        raise FileExistsError(f"{outcome_path} already exists")

    missing = [
        field
        for field in ("case_id", "fit_score", "predicted_at", "eligibility_gate",
                      "language_gate", "recorded_gaps")
        if case.get(field) is None
    ]
    if missing:
        raise ValueError(f"application case is missing diagnostic evidence: {', '.join(missing)}")

    record = {
        "schema_version": "1.0",
        "case_id": case["case_id"],
        "status": "drafted",
        "predicted_fit_score": case["fit_score"],
        "predicted_at": case["predicted_at"],
        "eligibility_gate": case["eligibility_gate"],
        "language_gate": case["language_gate"],
        "stages": [],
        "recorded_gaps": case["recorded_gaps"],
        "follow_ups": [],
    }
    for optional_field in ("deadline", "channel"):
        if optional_field in case:
            record[optional_field] = case[optional_field]
    atomic_write(outcome_path, record)
    return outcome_path


def stage_status(stage: str) -> str:
    normalized = stage.strip().lower().replace(" ", "_")
    if normalized in FINAL_STATUSES:
        raise ValueError("final stages must be recorded with resolve")
    if normalized in {"drafted", "applied", "offer"}:
        return normalized
    return "interview"


def append_stage(path: Path, stage: str, event_date: date, notes: str | None) -> None:
    record = load_record(path)
    require_open(record)
    event = {"stage": stage, "date": event_date.isoformat()}
    if notes is not None:
        event["notes"] = notes
    record["stages"].append(event)
    record["status"] = stage_status(stage)
    atomic_write(path, record)


def resolve(path: Path, status: str, resolved_date: date) -> None:
    record = load_record(path)
    require_open(record)
    canonical = normalize_status(status)
    if canonical not in FINAL_STATUSES:
        raise ValueError(f"{status!r} is not a final status")
    record["stages"].append({"stage": canonical, "date": resolved_date.isoformat()})
    record["status"] = canonical
    record["resolved_at"] = resolved_date.isoformat()
    atomic_write(path, record)


def append_followup(path: Path, followup_date: date) -> None:
    record = load_record(path)
    require_open(record)
    if record["status"] == "drafted":
        raise ValueError("drafted cases cannot receive follow-ups")
    record["follow_ups"].append(followup_date.isoformat())
    atomic_write(path, record)


def activity_date(record: dict) -> date:
    values = [record["predicted_at"], *record["follow_ups"]]
    values.extend(event["date"] for event in record["stages"])
    return max(date.fromisoformat(value) for value in values)


def list_outcomes(data_dir: Path, open_only: bool, quiet_days: int | None) -> None:
    today = date.today()
    records = []
    for path in sorted((data_dir.resolve() / "cases").glob("*/application_outcome.json")):
        records.append(load_record(path))

    for record in sorted(records, key=lambda item: item["case_id"]):
        is_open = record["status"] in OPEN_STATUSES
        if open_only and not is_open:
            continue
        overdue = "deadline" in record and date.fromisoformat(record["deadline"]) < today
        quiet_for = (today - activity_date(record)).days
        if quiet_days is not None:
            if not is_open or record["status"] == "drafted" or quiet_for < quiet_days:
                continue
        fields = [record["case_id"], f"status={record['status']}"]
        if quiet_days is not None:
            fields.append(f"quiet_days={quiet_for}")
        if overdue:
            fields.extend((f"deadline={record['deadline']}", "DEADLINE_PASSED"))
        print(" ".join(fields))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--case", type=Path, required=True)

    stage_parser = subparsers.add_parser("stage")
    stage_parser.add_argument("--case-id", required=True)
    stage_parser.add_argument("--stage", required=True)
    stage_parser.add_argument("--date", type=date.fromisoformat, required=True)
    stage_parser.add_argument("--notes")
    stage_parser.add_argument("--data-dir", type=Path, default=Path.cwd())

    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("--case-id", required=True)
    resolve_parser.add_argument("--status", required=True)
    resolve_parser.add_argument("--date", type=date.fromisoformat, required=True)
    resolve_parser.add_argument("--data-dir", type=Path, default=Path.cwd())

    followup_parser = subparsers.add_parser("followup")
    followup_parser.add_argument("--case-id", required=True)
    followup_parser.add_argument("--date", type=date.fromisoformat, required=True)
    followup_parser.add_argument("--data-dir", type=Path, default=Path.cwd())

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--open", action="store_true")
    list_parser.add_argument("--quiet-days", type=int, nargs="?", const=10)
    list_parser.add_argument("--data-dir", type=Path, default=Path.cwd())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            path = init_outcome(args.case)
            print(json.dumps({"case_id": load_record(path)["case_id"], "outcome_path": str(path)}))
        else:
            if args.command == "list":
                if args.quiet_days is not None and args.quiet_days < 0:
                    raise ValueError("quiet days must be non-negative")
                list_outcomes(args.data_dir, args.open, args.quiet_days)
                return 0
            path = find_outcome(args.data_dir, args.case_id)
            if args.command == "stage":
                append_stage(path, args.stage, args.date, args.notes)
            elif args.command == "resolve":
                resolve(path, args.status, args.date)
            elif args.command == "followup":
                append_followup(path, args.date)
            print(json.dumps({"case_id": args.case_id, "outcome_path": str(path)}))
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
