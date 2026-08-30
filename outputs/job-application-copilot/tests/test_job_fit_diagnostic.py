import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "job-fit-diagnostic" / "SKILL.md"
FIXTURES = ROOT / "tests" / "fixtures" / "job_gate_cases.json"


class JobFitDiagnosticGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL.read_text(encoding="utf-8")
        cases = json.loads(FIXTURES.read_text(encoding="utf-8"))
        cls.cases = {case["name"]: case for case in cases}

    def verdict_cell(self, case_name):
        case = self.cases[case_name]
        matching_rows = [
            line for line in self.skill.splitlines()
            if line.startswith("|") and case["row_marker"] in line
        ]
        self.assertEqual(
            len(matching_rows), 1,
            f"Expected one classification row for fixture: {case['posting_quote']}",
        )
        return matching_rows[0].split("|")[-2]

    def test_citizenship_or_permanent_residency_requirement_is_fail(self):
        verdict = self.verdict_cell("citizenship_requirement")
        self.assertIn("FAIL", verdict)

    def test_citizenship_silence_is_unverified_and_not_pass(self):
        verdict = self.verdict_cell("citizenship_silence")
        self.assertIn("UNVERIFIED", verdict)
        self.assertNotRegex(verdict, re.compile(r"\bPASS\b"))

    def test_required_language_absent_from_fact_bank_is_fail(self):
        verdict = self.verdict_cell("undeclared_required_language")
        self.assertIn("FAIL", verdict)

    def test_higher_language_bar_is_flag_not_fail_or_pass(self):
        verdict = self.verdict_cell("language_bar_above_declared_level")
        self.assertIn("FLAG", verdict)
        self.assertNotRegex(verdict, re.compile(r"\b(?:FAIL|PASS)\b"))

    def test_easy_to_get_wrong_eligibility_rules_are_explicit(self):
        self.assertIn("**Silence is not permission.**", self.skill)
        self.assertIn(
            '**A company-wide "international applicants welcome" statement is not '
            "role-level permission.**",
            self.skill,
        )


if __name__ == "__main__":
    unittest.main()
