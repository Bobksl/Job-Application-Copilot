import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "record_outcome.py"
FIXTURE = ROOT / "tests" / "fixtures" / "outcome_application_case.json"
SCHEMA = ROOT / "schemas" / "application_outcome.schema.json"


class RecordOutcomeTests(unittest.TestCase):
    def setUp(self):
        root = ROOT / ".test-tmp"
        root.mkdir(exist_ok=True)
        self.directory = root / f"outcome-{uuid.uuid4().hex}"
        self.case_directory = self.directory / "cases" / "example-analyst"
        self.case_directory.mkdir(parents=True)
        self.case_path = self.case_directory / "application_case.json"
        shutil.copyfile(FIXTURE, self.case_path)
        self.outcome_path = self.case_directory / "application_outcome.json"

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def run_recorder(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.directory,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_predicted_fit_score_cannot_change_after_init(self):
        first = self.run_recorder("init", "--case", str(self.case_path))
        self.assertEqual(first.returncode, 0, first.stderr)
        original = self.outcome_path.read_bytes()

        case = json.loads(self.case_path.read_text(encoding="utf-8"))
        case["fit_score"] = 99
        self.case_path.write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")

        second = self.run_recorder("init", "--case", str(self.case_path))
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("already exists", second.stderr.lower())
        self.assertEqual(self.outcome_path.read_bytes(), original)
        outcome = json.loads(original)
        self.assertEqual(outcome["predicted_fit_score"], 72)

    def test_init_copies_diagnostic_evidence_without_inference(self):
        result = self.run_recorder("init", "--case", str(self.case_path))
        self.assertEqual(result.returncode, 0, result.stderr)
        outcome = json.loads(self.outcome_path.read_text(encoding="utf-8"))
        self.assertEqual(outcome["predicted_fit_score"], 72)
        self.assertEqual(outcome["predicted_at"], "2026-08-31")
        self.assertEqual(outcome["eligibility_gate"], "UNVERIFIED")
        self.assertEqual(outcome["language_gate"], "FLAG")
        self.assertEqual(
            outcome["recorded_gaps"],
            ["No directly comparable transaction experience"],
        )
        self.assertEqual(outcome["deadline"], "2026-09-30")
        self.assertEqual(outcome["channel"], "portal")

    def test_init_refuses_missing_diagnostic_evidence(self):
        case = json.loads(self.case_path.read_text(encoding="utf-8"))
        case.pop("predicted_at")
        case.pop("recorded_gaps")
        self.case_path.write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")

        result = self.run_recorder("init", "--case", str(self.case_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing diagnostic evidence", result.stderr.lower())
        self.assertIn("predicted_at", result.stderr)
        self.assertIn("recorded_gaps", result.stderr)
        self.assertFalse(self.outcome_path.exists())

    def test_init_stage_resolve_round_trip_is_schema_valid(self):
        self.assertEqual(
            self.run_recorder("init", "--case", str(self.case_path)).returncode, 0
        )
        staged = self.run_recorder(
            "stage", "--case-id", "CASE-EXAMPLE-ANALYST-20260831",
            "--stage", "phone_screen", "--date", "2026-09-01",
            "--notes", "Recruiter screen completed.",
        )
        self.assertEqual(staged.returncode, 0, staged.stderr)
        resolved = self.run_recorder(
            "resolve", "--case-id", "CASE-EXAMPLE-ANALYST-20260831",
            "--status", "rejected", "--date", "2026-09-02",
        )
        self.assertEqual(resolved.returncode, 0, resolved.stderr)

        outcome = json.loads(self.outcome_path.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        errors = list(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(outcome)
        )
        self.assertEqual(errors, [])
        self.assertEqual(outcome["status"], "rejected")
        self.assertEqual(outcome["resolved_at"], "2026-09-02")
        self.assertEqual(
            [event["stage"] for event in outcome["stages"]],
            ["phone_screen", "rejected"],
        )

    def test_appending_a_stage_never_removes_an_earlier_stage(self):
        self.assertEqual(
            self.run_recorder("init", "--case", str(self.case_path)).returncode, 0
        )
        self.assertEqual(
            self.run_recorder(
                "stage", "--case-id", "CASE-EXAMPLE-ANALYST-20260831",
                "--stage", "applied", "--date", "2026-09-01",
            ).returncode,
            0,
        )
        self.assertEqual(
            self.run_recorder(
                "stage", "--case-id", "CASE-EXAMPLE-ANALYST-20260831",
                "--stage", "phone_screen", "--date", "2026-09-10",
            ).returncode,
            0,
        )
        outcome = json.loads(self.outcome_path.read_text(encoding="utf-8"))
        self.assertEqual(
            [event["stage"] for event in outcome["stages"]],
            ["applied", "phone_screen"],
        )
        self.assertEqual(outcome["status"], "interview")

    def test_resolve_refuses_non_final_status(self):
        self.assertEqual(
            self.run_recorder("init", "--case", str(self.case_path)).returncode, 0
        )
        original = self.outcome_path.read_bytes()
        result = self.run_recorder(
            "resolve", "--case-id", "CASE-EXAMPLE-ANALYST-20260831",
            "--status", "interview", "--date", "2026-09-02",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a final status", result.stderr.lower())
        self.assertEqual(self.outcome_path.read_bytes(), original)

    def test_drafted_case_is_excluded_from_quiet_open_list(self):
        case = json.loads(self.case_path.read_text(encoding="utf-8"))
        case["deadline"] = "2099-12-31"
        self.case_path.write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(
            self.run_recorder("init", "--case", str(self.case_path)).returncode, 0
        )
        listed = self.run_recorder("list", "--open", "--quiet-days", "1")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertNotIn("CASE-EXAMPLE-ANALYST-20260831", listed.stdout)

    def test_drafted_case_with_passed_deadline_is_flagged(self):
        case = json.loads(self.case_path.read_text(encoding="utf-8"))
        case["deadline"] = "2000-01-01"
        self.case_path.write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(
            self.run_recorder("init", "--case", str(self.case_path)).returncode, 0
        )
        listed = self.run_recorder("list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("CASE-EXAMPLE-ANALYST-20260831", listed.stdout)
        self.assertIn("DEADLINE_PASSED", listed.stdout)

    def test_legacy_no_response_reads_as_final_and_writes_canonical_status(self):
        self.assertEqual(
            self.run_recorder("init", "--case", str(self.case_path)).returncode, 0
        )
        legacy = json.loads(self.outcome_path.read_text(encoding="utf-8"))
        legacy["status"] = "no response"
        legacy["resolved_at"] = "2026-09-30"
        self.outcome_path.write_text(json.dumps(legacy, indent=2) + "\n", encoding="utf-8")

        listed = self.run_recorder("list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("status=no_response", listed.stdout)

        legacy["status"] = "drafted"
        legacy.pop("resolved_at")
        self.outcome_path.write_text(json.dumps(legacy, indent=2) + "\n", encoding="utf-8")
        resolved = self.run_recorder(
            "resolve", "--case-id", "CASE-EXAMPLE-ANALYST-20260831",
            "--status", "no response", "--date", "2026-09-30",
        )
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        written = self.outcome_path.read_text(encoding="utf-8")
        self.assertNotIn('"no response"', written)
        self.assertEqual(json.loads(written)["status"], "no_response")

    def test_invalid_write_leaves_previous_file_byte_identical(self):
        self.assertEqual(
            self.run_recorder("init", "--case", str(self.case_path)).returncode, 0
        )
        original = self.outcome_path.read_bytes()
        invalid = self.run_recorder(
            "stage", "--case-id", "CASE-EXAMPLE-ANALYST-20260831",
            "--stage", "interview", "--date", "2026-09-01",
            "--notes", "x" * 5001,
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("schema validation", invalid.stderr.lower())
        self.assertEqual(self.outcome_path.read_bytes(), original)

    def test_followup_requires_submission_and_appends_the_supplied_date(self):
        self.assertEqual(
            self.run_recorder("init", "--case", str(self.case_path)).returncode, 0
        )
        drafted = self.run_recorder(
            "followup", "--case-id", "CASE-EXAMPLE-ANALYST-20260831",
            "--date", "2026-09-05",
        )
        self.assertNotEqual(drafted.returncode, 0)
        self.assertIn("drafted cases", drafted.stderr.lower())
        self.assertEqual(
            self.run_recorder(
                "stage", "--case-id", "CASE-EXAMPLE-ANALYST-20260831",
                "--stage", "applied", "--date", "2026-09-01",
            ).returncode,
            0,
        )
        followed_up = self.run_recorder(
            "followup", "--case-id", "CASE-EXAMPLE-ANALYST-20260831",
            "--date", "2026-09-05",
        )
        self.assertEqual(followed_up.returncode, 0, followed_up.stderr)
        outcome = json.loads(self.outcome_path.read_text(encoding="utf-8"))
        self.assertEqual(outcome["follow_ups"], ["2026-09-05"])


if __name__ == "__main__":
    unittest.main()
