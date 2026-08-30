import json
import hashlib
import os
import subprocess
import sys
import unittest
import shutil
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "pre_tool_use.py"


class PreToolUseTests(unittest.TestCase):
    def temporary_directory(self):
        temp_root = ROOT / ".test-tmp"
        temp_root.mkdir(exist_ok=True)
        path = temp_root / f"hook-{uuid.uuid4().hex}"
        path.mkdir()
        self.addCleanup(shutil.rmtree, path, True)
        return path

    def run_hook(self, tool_name, tool_input, data_dir=None):
        payload = {"hook_event_name": "PreToolUse", "tool_name": tool_name,
                   "tool_input": tool_input}
        env = os.environ.copy()
        if data_dir:
            env["PLUGIN_DATA"] = str(data_dir)
        result = subprocess.run(
            [sys.executable, str(HOOK)], input=json.dumps(payload), env=env,
            capture_output=True, text=True, check=False,
        )
        return result, json.loads(result.stdout or "{}")

    def authorize(self, directory, action, tool_input):
        canonical = json.dumps(tool_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        authorization = {
            "action": action,
            "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "expires_at": "2099-01-01T00:00:00Z"
        }
        (directory / "active_authorization.json").write_text(
            json.dumps(authorization), encoding="utf-8")

    def test_email_send_is_always_denied(self):
        result, output = self.run_hook("mcp__codex_apps__gmail_send_email", {"to": "x@example.com"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_application_submission_tool_is_denied(self):
        _, output = self.run_hook("browser_submit_application", {"confirm": True})
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_generic_browser_apply_now_action_is_denied(self):
        _, output = self.run_hook(
            "mcp__browser__click", {"element": "Apply now", "ref": "button-7"})
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_ordinary_browser_navigation_is_allowed(self):
        _, output = self.run_hook(
            "mcp__browser__navigate", {"url": "https://example.com/careers"})
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_google_doc_write_without_authorization_is_denied(self):
        temp = self.temporary_directory()
        _, output = self.run_hook(
            "mcp__codex_apps__google_drive_batch_update_document",
            {"document_id": "doc-123", "requests": [],
             "write_control": {"requiredRevisionId": "rev-1"}}, temp)
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_google_doc_write_is_denied_even_with_legacy_authorization(self):
        temp = self.temporary_directory()
        tool_input = {"document_id": "doc-123", "requests": [{"insertText": {}}],
                      "write_control": {"requiredRevisionId": "rev-1"}}
        self.authorize(temp, "google_doc_update", tool_input)
        _, output = self.run_hook(
            "mcp__codex_apps__google_drive_batch_update_document", tool_input, temp)
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("manual", reason.lower())

    def test_gmail_draft_with_placeholder_is_denied_before_authorization(self):
        temp = self.temporary_directory()
        _, output = self.run_hook(
            "mcp__codex_apps__gmail_create_draft",
            {"to": "recruiter@example.com", "subject": "Application",
             "body": "I improved efficiency by [X%]."}, temp)
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("placeholder", reason.lower())

    def test_authorized_gmail_draft_is_allowed_once(self):
        temp = self.temporary_directory()
        tool_input = {"to": "recruiter@example.com", "subject": "Application",
                      "body": "Please find my application attached."}
        self.authorize(temp, "gmail_draft", tool_input)
        _, first = self.run_hook(
            "mcp__codex_apps__gmail_create_draft", tool_input, temp)
        _, second = self.run_hook(
            "mcp__codex_apps__gmail_create_draft", tool_input, temp)
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertEqual(second["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_document_write_without_revision_is_still_disabled(self):
        temp = self.temporary_directory()
        tool_input = {"document_id": "doc-123", "requests": []}
        self.authorize(temp, "google_doc_update", tool_input)
        _, output = self.run_hook(
            "mcp__codex_apps__google_drive_batch_update_document", tool_input, temp)
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("disabled", reason.lower())


if __name__ == "__main__":
    unittest.main()
