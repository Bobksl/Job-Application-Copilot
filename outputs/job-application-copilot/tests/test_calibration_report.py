import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "calibration_report.py"
FIXTURE = ROOT / "tests" / "fixtures" / "application_outcomes.json"


class CalibrationReportTests(unittest.TestCase):
    def setUp(self):
        root = ROOT / ".test-tmp"
        root.mkdir(exist_ok=True)
        self.directory = root / f"calibration-{uuid.uuid4().hex}"
        outcomes = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for index, outcome in enumerate(outcomes):
            case_directory = self.directory / "cases" / f"case-{index}"
            case_directory.mkdir(parents=True)
            (case_directory / "application_outcome.json").write_text(
                json.dumps(outcome, indent=2) + "\n", encoding="utf-8"
            )

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def test_report_has_required_sections_and_refuses_small_sample_conclusion(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--data-dir", str(self.directory)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("COUNT BY STATUS", result.stdout)
        self.assertIn("drafted: 1", result.stdout)
        self.assertIn("rejected: 1", result.stdout)
        self.assertIn("PREDICTED FIT SCORE AGAINST OUTCOME", result.stdout)
        self.assertIn("score=84 outcome=rejected", result.stdout)
        self.assertIn("GATE VERDICTS AGAINST OUTCOMES", result.stdout)
        self.assertIn("eligibility_gate=UNVERIFIED", result.stdout)
        self.assertIn("MOST FREQUENTLY RECORDED GAPS", result.stdout)
        self.assertIn("2 - No direct sector experience", result.stdout)
        self.assertIn(
            "Fewer than 5 resolved cases: no conclusion is supportable.",
            result.stdout,
        )
        self.assertNotIn("%", result.stdout)


if __name__ == "__main__":
    unittest.main()
