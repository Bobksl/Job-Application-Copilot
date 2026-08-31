#!/usr/bin/env python3
"""Report descriptive calibration evidence from local outcome records."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from record_outcome import FINAL_STATUSES, load_record


STATUS_ORDER = (
    "drafted",
    "applied",
    "interview",
    "offer",
    "hired",
    "rejected",
    "no_response",
    "offer_declined",
    "withdrawn",
)


def read_outcomes(data_dir: Path) -> list[dict]:
    paths = sorted((data_dir.resolve() / "cases").glob("*/application_outcome.json"))
    return [load_record(path) for path in paths]


def print_report(records: list[dict]) -> None:
    status_counts = Counter(record["status"] for record in records)
    resolved_records = [record for record in records if record["status"] in FINAL_STATUSES]
    resolved_count = len(resolved_records)
    resolved_provenance = Counter(record["provenance"] for record in resolved_records)

    print("COUNT BY STATUS")
    for status in STATUS_ORDER:
        print(f"{status}: {status_counts[status]}")

    print("\nPREDICTED FIT SCORE AGAINST OUTCOME")
    provenance_headings = (
        ("recorded", "RECORDED BEFORE OUTCOME KNOWN"),
        ("backfilled", "BACKFILLED AFTER OUTCOME KNOWN"),
    )
    for provenance, heading in provenance_headings:
        population = sorted(
            (record for record in records if record["provenance"] == provenance),
            key=lambda item: item["case_id"],
        )
        print(f"\n{heading} ({len(population)})")
        if not population:
            print("No outcome records.")
        for record in population:
            print(
                f"{record['case_id']}: score={record['predicted_fit_score']} "
                f"outcome={record['status']}"
            )

    print("\nGATE VERDICTS AGAINST OUTCOMES")
    if not records:
        print("No gate verdicts.")
    for gate_name in ("eligibility_gate", "language_gate"):
        combinations = Counter(
            (record[gate_name], record["status"]) for record in records
        )
        for (verdict, status), count in sorted(combinations.items()):
            print(f"{gate_name}={verdict} outcome={status}: {count}")

    print("\nMOST FREQUENTLY RECORDED GAPS")
    gaps = Counter(gap for record in records for gap in record["recorded_gaps"])
    if not gaps:
        print("No recorded gaps.")
    for gap, count in sorted(gaps.items(), key=lambda item: (-item[1], item[0])):
        print(f"{count} - {gap}")

    print("\nSAMPLE ASSESSMENT")
    print(
        f"Resolved cases: {resolved_count} total "
        f"(recorded={resolved_provenance['recorded']}, "
        f"backfilled={resolved_provenance['backfilled']})."
    )
    if resolved_count < 5:
        print("Fewer than 5 resolved cases: no conclusion is supportable.")
    else:
        print(f"Resolved cases available for descriptive comparison: {resolved_count}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        print_report(read_outcomes(args.data_dir))
    except (OSError, ValueError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
