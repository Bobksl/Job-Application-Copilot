import hashlib
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "authorize_action.py"
CASE_FIXTURE = ROOT / "tests" / "fixtures" / "application_case.json"


def approval_hash(change_set):
    content = {
        "change_set_id": change_set["change_set_id"],
        "artifact": change_set["artifact"],
        "target": change_set["target"],
        "changes": change_set["changes"],
    }
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AuthorizeActionTests(unittest.TestCase):
    def setUp(self):
        root = ROOT / ".test-tmp"
        root.mkdir(exist_ok=True)
        self.directory = root / f"authorize-{uuid.uuid4().hex}"
        self.directory.mkdir()
        self.facts = {
            "schema_version": "1.0", "candidate_id": "candidate-local",
            "facts": [{
                "fact_id": "FACT-A-001", "category": "project", "organization": "Local",
                "context": "Research", "claim": "Built a validated workflow.",
                "skills": ["validation"], "metrics": [],
                "evidence": [{"type": "candidate_confirmation", "reference": "interview"}],
                "verification_status": "verified",
                "allowed_uses": ["resume", "cover_letter", "email", "job_fit"],
                "last_verified": "2026-08-11"
            }]
        }
        self.change = {
            "schema_version": "1.0", "change_set_id": "CHANGE-A-001",
            "case_id": "CASE-A-001", "artifact": "resume", "status": "approved",
            "target": {"document_id": "doc-123", "required_revision_id": "rev-1"},
            "changes": [{"location": "Project bullet", "before": "Built a workflow.",
                         "after": "Built a validated workflow.", "fact_ids": ["FACT-A-001"]}],
            "approvals": [],
            "qa": {"fact_check": "pass", "placeholders_resolved": "pass", "tone": "pass",
                   "layout": "pending", "page_count": None},
            "created_at": "2026-08-11T09:00:00Z"
        }
        self.change["approvals"] = [{
            "approved_by": "candidate",
            "approved_at": "2026-08-11T10:00:00Z",
            "change_set_id": self.change["change_set_id"],
            "approved_content_sha256": approval_hash(self.change),
        }]
        self.application_case = json.loads(CASE_FIXTURE.read_text(encoding="utf-8"))
        self.application_case["case_id"] = self.change["case_id"]
        self.payload = {"document_id": "doc-123", "requests": [{"insertText": {}}],
                        "write_control": {"requiredRevisionId": "rev-1"}}

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def write(self, name, value):
        path = self.directory / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def run_authorize(self):
        return subprocess.run([
            sys.executable, str(SCRIPT), "--action", "google_doc_update",
            "--payload", str(self.write("payload.json", self.payload)),
            "--change-set", str(self.write("change.json", self.change)),
            "--fact-bank", str(self.write("facts.json", self.facts)),
            "--application-case", str(self.write("case.json", self.application_case)),
            "--data-dir", str(self.directory / "data"), "--ttl-seconds", "120"
        ], capture_output=True, text=True, check=False)

    def test_google_doc_update_authorization_is_disabled(self):
        result = self.run_authorize()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("disabled", result.stderr.lower())
        self.assertFalse((self.directory / "data" / "active_authorization.json").exists())

    def test_payload_revision_must_match_approved_change_set(self):
        self.payload["write_control"]["requiredRevisionId"] = "rev-other"
        result = self.run_authorize()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("disabled", result.stderr.lower())
        self.assertFalse((self.directory / "data" / "active_authorization.json").exists())

    def test_text_style_before_structural_operation_is_blocked(self):
        self.payload["requests"] = [
            {"updateTextStyle": {"range": {"startIndex": 1, "endIndex": 2}}},
            {"createParagraphBullets": {"range": {"startIndex": 1, "endIndex": 2}}},
        ]
        result = self.run_authorize()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("disabled", result.stderr.lower())
        self.assertFalse((self.directory / "data" / "active_authorization.json").exists())

    def test_structural_operation_before_text_style_is_still_disabled(self):
        self.payload["requests"] = [
            {"createParagraphBullets": {"range": {"startIndex": 1, "endIndex": 2}}},
            {"updateTextStyle": {"range": {"startIndex": 1, "endIndex": 2}}},
        ]
        result = self.run_authorize()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("disabled", result.stderr.lower())

    def test_authorization_write_error_fails_closed_without_traceback(self):
        blocked_data_path = self.directory / "not-a-directory"
        blocked_data_path.write_text("occupied", encoding="utf-8")
        result = subprocess.run([
            sys.executable, str(SCRIPT), "--action", "google_doc_update",
            "--payload", str(self.write("payload.json", self.payload)),
            "--change-set", str(self.write("change.json", self.change)),
            "--fact-bank", str(self.write("facts.json", self.facts)),
            "--application-case", str(self.write("case.json", self.application_case)),
            "--data-dir", str(blocked_data_path), "--ttl-seconds", "120"
        ], capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
