#!/usr/bin/env python3
"""Supply-chain and private-data guards for the Job Application Copilot.

Run from anywhere:  python tools/security_guards.py
Exit 0 on success, 1 with a failure list otherwise. Stdlib only.

Adapted from tools/security_guards.py in MadsLorentzen/ai-job-search
(MIT License, Copyright (c) 2026 Mads Lorentzen). The allowlist-and-fail-loudly
pattern is theirs; the checks below are specific to this workspace.

WHY THIS EXISTS
---------------
Two things in this workspace are load-bearing and quietly breakable:

  1. The .gitignore rules that keep the fact bank, case folders and candidate
     documents out of version control. Weakening one of them does not fail
     anything -- it just silently starts committing someone's career history.

  2. The pre-tool-use hook that denies direct Google Docs writes, Gmail sends
     and application submission. That hook IS the product's safety guarantee.
     A deletion or a loosened predicate looks like an ordinary diff.

These guards make both changes LOUD, not impossible. A commit that
legitimately needs one must edit the allowlists in this file in the same diff,
so the widening is explicit and reviewable rather than buried.

CHECKS
------
  1. .gitignore  -- every required private-data rule is present, and no
                    un-allowlisted negation (!pattern) re-includes one.
  2. hooks       -- hooks.json registers only allowlisted events, and
                    pre_tool_use.py still contains every required deny rule.
  3. tracked     -- `git ls-files` lists nothing under a private path.
                    Catches files added before an ignore rule existed:
                    .gitignore does not apply to already-tracked files.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors: list[str] = []


# ---------------------------------------------------------------------------
# Allowlists. Widening any of these is the reviewable act.
# ---------------------------------------------------------------------------

# Private-data ignore rules that must never disappear from .gitignore.
REQUIRED_IGNORE_RULES = [
    "work/",
    "**/job-application-copilot-data/",
    "**/fact_bank.json",
    "**/cases/**",
    "**/change_sets/**",
    "**/authorizations/**",
    ".env",
    ".env.*",
    "secrets/",
    "**/notion_sync.json",
    "documents/",
    "*.xlsx",
    "tmp/",
    "outputs/showcase/",
]

# Negations the workspace legitimately ships. .gitignore is order-sensitive:
# a later `!pattern` re-includes a path an earlier rule excluded, so a rule can
# be physically present in REQUIRED_IGNORE_RULES yet no longer ignored.
# Set membership alone cannot see that.
ALLOWED_IGNORE_NEGATIONS = {
    "!schemas/*.json",
    "!**/schemas/*.json",
    "!tests/fixtures/**",
    "!**/tests/fixtures/**",
}

# Hook events this workspace legitimately registers. A hook runs automatically
# when its event fires, with no prompt and no model decision in between, so it
# is strictly more dangerous than a pre-approved permission. Cloning the repo
# and opening it is enough to execute one.
ALLOWED_HOOK_EVENTS = {"PreToolUse"}

# Substrings that must still appear in the hook implementation. These are
# deliberately coarse -- the point is to catch a deletion or a rename, not to
# re-implement the hook's logic here. Keep them in sync with the hook, and
# treat a failure as "read the hook diff", never as "loosen this list".
REQUIRED_HOOK_DENIALS = [
    "mcp__codex_apps__google_drive_batch_update_document",  # direct Google Docs write denial
    "gmail",                 # Gmail send denial / draft authorization
    "send",                  # sending remains prohibited
    "submit",                # application submission denial
]

# Paths that must never contain a tracked file.
PRIVATE_TRACKED_PREFIXES = (
    "work/",
    "documents/",
    "secrets/",
)
PRIVATE_TRACKED_NAMES = (
    "fact_bank.json",
    ".env",
    "credentials.json",
    "token.json",
    "notion_sync.json",
)

HOOKS_DIR_CANDIDATES = [
    ROOT / "outputs" / "job-application-copilot" / "hooks",
    ROOT / "hooks",
]


# ---------------------------------------------------------------------------
# 1. .gitignore
# ---------------------------------------------------------------------------

def check_gitignore() -> None:
    path = ROOT / ".gitignore"
    if not path.is_file():
        errors.append(".gitignore: missing at the workspace root")
        return

    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    present = {ln for ln in lines if ln and not ln.startswith("#")}

    for rule in REQUIRED_IGNORE_RULES:
        if rule not in present:
            errors.append(
                f".gitignore: required private-data rule is missing: {rule!r}"
            )

    for rule in present:
        if rule.startswith("!") and rule not in ALLOWED_IGNORE_NEGATIONS:
            errors.append(
                f".gitignore: un-allowlisted negation re-includes ignored content: {rule!r} "
                f"(add it to ALLOWED_IGNORE_NEGATIONS in the same commit if intended)"
            )


# ---------------------------------------------------------------------------
# 2. hooks
# ---------------------------------------------------------------------------

def _find_hooks_dir() -> Path | None:
    for candidate in HOOKS_DIR_CANDIDATES:
        if candidate.is_dir():
            return candidate
    return None


def check_hooks() -> None:
    hooks_dir = _find_hooks_dir()
    if hooks_dir is None:
        errors.append(
            "hooks/: directory not found -- the deny layer is the product's safety "
            "guarantee and must exist (looked in: "
            + ", ".join(str(c.relative_to(ROOT)) for c in HOOKS_DIR_CANDIDATES)
            + ")"
        )
        return

    manifest = hooks_dir / "hooks.json"
    if not manifest.is_file():
        errors.append(f"{manifest.relative_to(ROOT)}: missing")
    else:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{manifest.relative_to(ROOT)}: invalid JSON: {exc}")
            data = None

        if isinstance(data, dict):
            registered = data.get("hooks", data)
            if isinstance(registered, dict):
                for event in registered:
                    if event not in ALLOWED_HOOK_EVENTS:
                        errors.append(
                            f"{manifest.relative_to(ROOT)}: un-allowlisted hook event "
                            f"{event!r} -- a hook runs with no prompt; add it to "
                            f"ALLOWED_HOOK_EVENTS in the same commit if intended"
                        )

    impl = hooks_dir / "pre_tool_use.py"
    if not impl.is_file():
        errors.append(f"{impl.relative_to(ROOT)}: missing -- the deny rules live here")
        return

    body = impl.read_text(encoding="utf-8").lower()
    for needle in REQUIRED_HOOK_DENIALS:
        if needle.lower() not in body:
            errors.append(
                f"{impl.relative_to(ROOT)}: expected deny rule referencing {needle!r} "
                f"is gone -- read the hook diff before touching this list"
            )

    # Fail-closed posture: the hook must not have a bare "allow everything on
    # error" path. A malformed payload has to deny, not pass through.
    if not re.search(r"(fail[_ ]?clos|except[\s\S]{0,400}?deny)", body):
        errors.append(
            f"{impl.relative_to(ROOT)}: no fail-closed error path found -- "
            f"malformed hook input must deny, never pass through"
        )


# ---------------------------------------------------------------------------
# 3. tracked files
# ---------------------------------------------------------------------------

def check_tracked_files() -> None:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"git ls-files: could not run ({type(exc).__name__}) -- skipping tracked-file check")
        return

    if result.returncode != 0:
        # Not a git repository yet. That is the state this kit exists to fix,
        # so say so plainly rather than failing the whole run.
        print("security_guards: not a git repository yet -- tracked-file check skipped")
        return

    for line in result.stdout.splitlines():
        rel = line.strip().replace("\\", "/")
        if not rel:
            continue
        if rel.startswith(PRIVATE_TRACKED_PREFIXES) or rel.rsplit("/", 1)[-1] in PRIVATE_TRACKED_NAMES:
            errors.append(
                f"tracked private file: {rel} -- .gitignore does not apply to files "
                f"already tracked; run `git rm --cached {rel}` and commit"
            )


# ---------------------------------------------------------------------------

def main() -> int:
    check_gitignore()
    check_hooks()
    check_tracked_files()

    if errors:
        print(f"security_guards: {len(errors)} failure(s)")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("security_guards: OK (gitignore rules, hook allowlist, tracked files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
