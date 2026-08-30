#!/usr/bin/env python3
"""Validate application artifacts before external writes or finalization."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
PLACEHOLDER = re.compile(r"\[[^\[\]\n]{1,200}\]")
PERCENTAGE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*%")


class GateError(ValueError):
    pass


def change_content_hash(change_set: dict) -> str:
    """Fingerprint the exact approved target and wording, excluding approval metadata."""
    approved_content = {
        "change_set_id": change_set["change_set_id"],
        "artifact": change_set["artifact"],
        "target": change_set["target"],
        "changes": change_set["changes"],
    }
    encoded = json.dumps(
        approved_content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalized_number(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip().removesuffix("%").strip()
    try:
        return format(float(text), ".15g")
    except ValueError:
        return None


def verified_percentages(facts: list[dict]) -> set[str]:
    values: set[str] = set()
    for fact in facts:
        for metric in fact["metrics"]:
            if metric["verification_status"] != "verified":
                continue
            unit = (metric["unit"] or "").strip().lower()
            value_text = str(metric["value"] or "").strip()
            if unit in {"%", "percent", "percentage"} or value_text.endswith("%"):
                normalized = normalized_number(metric["value"])
                if normalized is not None:
                    values.add(normalized)
    return values


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"Cannot read valid JSON from {path}: {exc}") from exc


def validate_schema(value: dict, schema_name: str) -> None:
    schema = load_json(SCHEMAS / schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(
            f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise GateError(f"Schema validation failed: {details}")


def validate_case_gates(application_case: dict, change_set: dict) -> None:
    validate_schema(application_case, "application_case.schema.json")
    if application_case["case_id"] != change_set["case_id"]:
        raise GateError("Application case does not match the change set case_id.")
    for gate_name in ("eligibility_gate", "language_gate"):
        if application_case.get(gate_name) == "FAIL":
            note_name = gate_name.replace("_gate", "_note")
            note = application_case.get(note_name)
            if not note:
                raise GateError(
                    f"Application case {gate_name} is FAIL but {note_name} is missing; "
                    "the verbatim posting quote and source are required."
                )
            raise GateError(
                f"Application case {gate_name} is FAIL; a vetoed role cannot advance to "
                f"approval. Trigger: {note}"
            )


def validate_prewrite(
    fact_bank: dict, change_set: dict, application_case: dict | None = None
) -> None:
    validate_schema(fact_bank, "fact_bank.schema.json")
    validate_schema(change_set, "change_set.schema.json")
    if application_case is not None:
        validate_case_gates(application_case, change_set)

    if change_set["status"] not in {"approved", "applied", "final"}:
        raise GateError("Change set is not approved for writing.")
    if not change_set["approvals"]:
        raise GateError("Change set has no explicit candidate approval.")

    for check in ("fact_check", "placeholders_resolved", "tone"):
        if change_set["qa"][check] != "pass":
            raise GateError(f"Pre-write QA check '{check}' has not passed.")

    usage = change_set["artifact"]
    facts = {fact["fact_id"]: fact for fact in fact_bank["facts"]}
    for change in change_set["changes"]:
        if PLACEHOLDER.search(change["after"]):
            raise GateError(f"Unresolved placeholder in {change['location']}.")
        cited_facts = []
        for fact_id in change["fact_ids"]:
            fact = facts.get(fact_id)
            if fact is None:
                raise GateError(f"Unknown fact id: {fact_id}.")
            if fact["verification_status"] != "verified":
                raise GateError(f"Fact {fact_id} is not verified.")
            if usage not in fact["allowed_uses"]:
                raise GateError(f"Fact {fact_id} is not approved for {usage} use.")
            cited_facts.append(fact)
            for metric in fact["metrics"]:
                if metric["value"] is not None and metric["verification_status"] != "verified":
                    raise GateError(f"Metric '{metric['label']}' in {fact_id} is not verified.")
        supported_percentages = verified_percentages(cited_facts)
        for match in PERCENTAGE.finditer(change["after"]):
            claimed = normalized_number(match.group(1))
            if claimed not in supported_percentages:
                raise GateError(
                    f"Percentage '{match.group(0)}' in {change['location']} is not a verified "
                    "metric in its cited facts."
                )

    approved_hash = change_content_hash(change_set)
    if not any(
        approval["change_set_id"] == change_set["change_set_id"]
        and approval["approved_content_sha256"] == approved_hash
        for approval in change_set["approvals"]
    ):
        raise GateError("No approval matches the exact change-set ID, target, and wording.")


def validate_final(
    fact_bank: dict, change_set: dict, application_case: dict | None = None
) -> None:
    validate_prewrite(fact_bank, change_set, application_case)
    if change_set["status"] != "final":
        raise GateError("Finalization requires change-set status 'final'.")
    qa = change_set["qa"]
    if change_set["artifact"] in {"resume", "cover_letter"}:
        if qa["layout"] not in {"pass", "not_applicable"}:
            raise GateError(
                "Draft-first resume and cover-letter handoff requires layout 'not_applicable' "
                "unless the candidate separately confirms a one-page manual paste-back."
            )
        if qa["layout"] == "pass" and qa["page_count"] != 1:
            raise GateError("A claimed layout pass requires exactly one page.")
        if qa["layout"] == "not_applicable" and qa["page_count"] is not None:
            raise GateError("Draft-first layout must not claim a page count.")
    elif qa["layout"] != "not_applicable":
        raise GateError("Email layout must be marked not_applicable.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prewrite", "final"])
    parser.add_argument("--fact-bank", required=True, type=Path)
    parser.add_argument("--change-set", required=True, type=Path)
    parser.add_argument("--application-case", type=Path)
    args = parser.parse_args(argv)
    try:
        facts = load_json(args.fact_bank)
        changes = load_json(args.change_set)
        application_case = load_json(args.application_case) if args.application_case else None
        (validate_prewrite if args.mode == "prewrite" else validate_final)(
            facts, changes, application_case
        )
    except GateError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"result": "pass", "mode": args.mode, "change_set_id": changes["change_set_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
