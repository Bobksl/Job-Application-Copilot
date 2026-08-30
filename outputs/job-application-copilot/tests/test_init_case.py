import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "init_case.py"
SCHEMA = ROOT / "schemas" / "application_case.schema.json"


class InitCaseTests(unittest.TestCase):
    def setUp(self):
        root = ROOT / ".test-tmp"
        root.mkdir(exist_ok=True)
        self.directory = root / f"case-{uuid.uuid4().hex}"
        self.directory.mkdir()

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def run_init(self):
        return subprocess.run([
            sys.executable, str(SCRIPT), "--company", "Millennium Management",
            "--role", "2027 Summer Internship", "--date", "2026-08-11",
            "--data-dir", str(self.directory)
        ], capture_output=True, text=True, check=False)

    def test_creates_isolated_schema_valid_case_and_private_fact_bank(self):
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        case_path = Path(output["case_path"])
        fact_path = Path(output["fact_bank_path"])
        case = json.loads(case_path.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(case))
        self.assertEqual(errors, [])
        self.assertEqual(case["case_id"], "CASE-MILLENNIUM-MANAGEMENT-2027-SUMMER-INTERNSHIP-20260811")
        self.assertTrue(fact_path.exists())

    def test_refuses_to_overwrite_existing_case(self):
        self.assertEqual(self.run_init().returncode, 0)
        second = self.run_init()
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("already exists", second.stderr.lower())


if __name__ == "__main__":
    unittest.main()
