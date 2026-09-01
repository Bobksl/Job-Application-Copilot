import json
import re
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export_projection.py"
FIXTURES = ROOT / "tests" / "fixtures"
DISTINCTIVE_TEXT = "DISTINCTIVE_DOCUMENT_TEXT_8f4d32c1"
OUTCOME_FIELDS = {
    "status",
    "predicted_fit_score",
    "eligibility_gate",
    "language_gate",
    "provenance",
    "applied_on",
    "resolved_at",
    "stages",
}


class ExportProjectionTests(unittest.TestCase):
    def setUp(self):
        root = ROOT / ".test-tmp"
        root.mkdir(exist_ok=True)
        self.directory = root / f"projection-{uuid.uuid4().hex}"
        self.cases_directory = self.directory / "cases"
        self.cases_directory.mkdir(parents=True)

        first = self.cases_directory / "example-analyst"
        first.mkdir()
        shutil.copyfile(
            FIXTURES / "projection_case_with_outcome.json",
            first / "application_case.json",
        )
        shutil.copyfile(
            FIXTURES / "projection_outcome.json",
            first / "application_outcome.json",
        )

        second = self.cases_directory / "second-researcher"
        second.mkdir()
        shutil.copyfile(
            FIXTURES / "projection_case_without_outcome.json",
            second / "application_case.json",
        )

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def run_exporter(self, *args):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--data-dir",
                str(self.directory),
                *args,
            ],
            capture_output=True,
            check=False,
        )

    @staticmethod
    def without_generated_at(payload: bytes) -> bytes:
        return re.sub(
            rb'"generated_at": "[^"]+"',
            b'"generated_at": "<ignored>"',
            payload,
            count=1,
        )

    def test_round_trip_emits_one_row_per_case_with_expected_keys(self):
        output_path = self.directory / "projection.json"
        result = self.run_exporter("--out", str(output_path))

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, b"")
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertRegex(payload["generated_at"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertEqual(len(payload["rows"]), 2)
        self.assertEqual(
            [row["key"] for row in payload["rows"]],
            [
                "CASE-EXAMPLE-ANALYST-20260831",
                "CASE-SECOND-RESEARCHER-20260901",
            ],
        )
        self.assertEqual(
            set(payload["rows"][0]),
            {
                "key",
                "company",
                "role",
                "status",
                "predicted_fit_score",
                "eligibility_gate",
                "language_gate",
                "provenance",
                "deadline",
                "channel",
                "applied_on",
                "resolved_at",
                "stages",
                "documents",
                "url",
            },
        )
        self.assertEqual(
            payload["rows"][0]["documents"],
            ["candidate-fundamental.pdf", "projection_document.txt"],
        )

    def test_document_content_never_appears_in_payload(self):
        self.assertIn(
            DISTINCTIVE_TEXT,
            (FIXTURES / "projection_document.txt").read_text(encoding="utf-8"),
        )

        result = self.run_exporter()

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertNotIn(DISTINCTIVE_TEXT.encode(), result.stdout)
        self.assertNotIn(b"never-export-this", result.stdout)

    def test_case_without_outcome_omits_outcome_fields(self):
        result = self.run_exporter()

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        payload = json.loads(result.stdout)
        row = next(
            item
            for item in payload["rows"]
            if item["key"] == "CASE-SECOND-RESEARCHER-20260901"
        )
        self.assertEqual(set(row), {"key", "company", "role", "documents"})
        self.assertTrue(OUTCOME_FIELDS.isdisjoint(row))
        self.assertNotIn(None, row.values())

    def test_redact_removes_url_and_documents(self):
        result = self.run_exporter("--redact")

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        payload = json.loads(result.stdout)
        for row in payload["rows"]:
            self.assertNotIn("url", row)
            self.assertNotIn("documents", row)

    def test_payload_is_deterministic_apart_from_generated_at(self):
        first = self.run_exporter()
        second = self.run_exporter()

        self.assertEqual(first.returncode, 0, first.stderr.decode())
        self.assertEqual(second.returncode, 0, second.stderr.decode())
        self.assertEqual(
            self.without_generated_at(first.stdout),
            self.without_generated_at(second.stdout),
        )


if __name__ == "__main__":
    unittest.main()
