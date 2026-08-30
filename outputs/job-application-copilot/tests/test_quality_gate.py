import hashlib
import json
import subprocess
import sys
import unittest
import shutil
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "quality_gate.py"


def approval_hash(change_set):
    content = {
        "change_set_id": change_set["change_set_id"],
        "artifact": change_set["artifact"],
        "target": change_set["target"],
        "changes": change_set["changes"],
    }
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_json(directory: Path, name: str, value: dict) -> Path:
    path = directory / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


class QualityGateTests(unittest.TestCase):
    def setUp(self):
        temp_root = ROOT / ".test-tmp"
        temp_root.mkdir(exist_ok=True)
        self.directory = temp_root / f"quality-{uuid.uuid4().hex}"
        self.directory.mkdir()
        self.fact_bank = {
            "schema_version": "1.0",
            "candidate_id": "candidate-local",
            "facts": [{
                "fact_id": "FACT-WQ-001",
                "category": "employment",
                "organization": "WorldQuant",
                "context": "Research",
                "claim": "Built reproducible alpha research workflows.",
                "skills": ["Python", "out-of-sample validation"],
                "metrics": [],
                "evidence": [{"type": "candidate_confirmation", "reference": "interview-1"}],
                "verification_status": "verified",
                "allowed_uses": ["resume", "cover_letter", "email", "job_fit"],
                "last_verified": "2026-08-11"
            }]
        }

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def run_gate(self, change_set, mode="prewrite"):
        fact_path = write_json(self.directory, "facts.json", self.fact_bank)
        change_path = write_json(self.directory, "change.json", change_set)
        return subprocess.run(
            [sys.executable, str(SCRIPT), mode, "--fact-bank", str(fact_path),
             "--change-set", str(change_path)],
            capture_output=True, text=True, check=False,
        )

    def valid_change_set(self):
        change_set = {
            "schema_version": "1.0",
            "change_set_id": "CHANGE-MILLENNIUM-001",
            "case_id": "CASE-MILLENNIUM-2027",
            "artifact": "resume",
            "status": "approved",
            "target": {"document_id": "doc-123", "required_revision_id": "rev-1"},
            "changes": [{
                "location": "WorldQuant bullet 1",
                "before": "Built research workflows.",
                "after": "Built reproducible alpha research workflows.",
                "fact_ids": ["FACT-WQ-001"]
            }],
            "approvals": [],
            "qa": {"fact_check": "pass", "placeholders_resolved": "pass", "tone": "pass",
                   "layout": "pending", "page_count": None},
            "created_at": "2026-08-11T09:00:00Z"
        }
        change_set["approvals"] = [{
            "approved_by": "candidate",
            "approved_at": "2026-08-11T10:00:00Z",
            "change_set_id": change_set["change_set_id"],
            "approved_content_sha256": approval_hash(change_set),
        }]
        return change_set

    def test_approved_grounded_change_passes(self):
        result = self.run_gate(self.valid_change_set())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unverified_fact_is_blocked(self):
        self.fact_bank["facts"][0]["verification_status"] = "unverified"
        result = self.run_gate(self.valid_change_set())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not verified", result.stderr)

    def test_bracketed_placeholder_is_blocked(self):
        change = self.valid_change_set()
        change["changes"][0]["after"] += " [improving efficiency by X%]"
        result = self.run_gate(change)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("placeholder", result.stderr.lower())

    def test_unapproved_change_is_blocked(self):
        change = self.valid_change_set()
        change["status"] = "proposed"
        change["approvals"] = []
        result = self.run_gate(change)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("approved", result.stderr.lower())

    def test_changed_wording_after_approval_is_blocked(self):
        change = self.valid_change_set()
        change["changes"][0]["after"] = "Built a different validated workflow."
        result = self.run_gate(change)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact change-set", result.stderr.lower())

    def test_unsupported_percentage_claim_is_blocked(self):
        change = self.valid_change_set()
        change["changes"][0]["after"] += " Improved research efficiency by 40%."
        change["approvals"][0]["approved_content_sha256"] = approval_hash(change)
        result = self.run_gate(change)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a verified metric", result.stderr.lower())

    def test_verified_percentage_claim_passes(self):
        self.fact_bank["facts"][0]["metrics"] = [{
            "label": "research efficiency improvement",
            "value": 40,
            "unit": "%",
            "verification_status": "verified",
        }]
        change = self.valid_change_set()
        change["changes"][0]["after"] += " Improved research efficiency by 40%."
        change["approvals"][0]["approved_content_sha256"] = approval_hash(change)
        result = self.run_gate(change)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_final_copy_ready_resume_can_leave_layout_unverified(self):
        change = self.valid_change_set()
        change["status"] = "final"
        change["qa"]["layout"] = "not_applicable"
        change["approvals"][0]["approved_content_sha256"] = approval_hash(change)
        result = self.run_gate(change, mode="final")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_final_copy_ready_resume_cannot_claim_page_count(self):
        change = self.valid_change_set()
        change["status"] = "final"
        change["qa"]["layout"] = "not_applicable"
        change["qa"]["page_count"] = 1
        change["approvals"][0]["approved_content_sha256"] = approval_hash(change)
        result = self.run_gate(change, mode="final")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not claim", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
