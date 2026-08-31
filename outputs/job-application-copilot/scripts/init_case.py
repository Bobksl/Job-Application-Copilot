#!/usr/bin/env python3
"""Create a private, isolated application case without overwriting prior work."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:120]


def document_record() -> dict:
    return {
        "document_id": None,
        "url": None,
        "baseline_revision_id": None,
        "baseline_page_count": None,
        "style": {
            "font_family": "Times New Roman",
            "bullet_font_size_pt": 11,
            "line_spacing": "single",
            "page_limit": 1,
            "preserve_margins": True,
        },
    }


def write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    company_slug = slugify(args.company)
    role_slug = slugify(args.role)
    if not company_slug or not role_slug:
        print("BLOCKED: company and role must contain letters or digits.", file=sys.stderr)
        return 1
    compact_date = args.date.strftime("%Y%m%d")
    case_id = f"CASE-{company_slug}-{role_slug}-{compact_date}".upper()
    case_directory = args.data_dir / "cases" / f"{company_slug}-{role_slug}-{compact_date}"
    case_path = case_directory / "application_case.json"
    fact_path = args.data_dir / "fact_bank.json"

    try:
        if not fact_path.exists():
            write_new(fact_path, {"schema_version": "1.0", "candidate_id": "candidate-local", "facts": []})
        case = {
            "schema_version": "1.0",
            "case_id": case_id,
            "company": args.company.strip(),
            "role": args.role.strip(),
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "intake",
            "jd": {"source_type": "pending", "source": None, "captured_at": None, "sha256": None},
            "documents": {
                "quant_cv": document_record(),
                "fundamental_resume": document_record(),
                "cover_letter": document_record(),
            },
            "selected_track": None,
            "fit_score": None,
            "eligibility_gate": "UNVERIFIED",
            "eligibility_note": "Eligibility gate has not been evaluated at intake.",
            "language_gate": "FLAG",
            "language_note": "Language gate has not been evaluated at intake.",
            "score_weights": {
                "core_responsibilities": 35,
                "hard_skills": 30,
                "domain_experience": 20,
                "soft_skills": 10,
                "ats_terms": 5,
            },
            "research_sources": [],
            "change_sets": [],
            "approvals": [],
        }
        write_new(case_path, case)
    except (OSError, FileExistsError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({"case_id": case_id, "case_path": str(case_path),
                      "fact_bank_path": str(fact_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
