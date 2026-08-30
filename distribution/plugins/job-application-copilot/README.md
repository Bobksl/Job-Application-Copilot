# Job Application Copilot

Private, quality-first Codex plugin for fact-grounded job applications. Version 1 supports JD fit analysis, copy-ready resume redlines, cover letters, and optional unsent Gmail drafts.

## Start the Millennium pilot

Provide:

1. The full Millennium 2027 Summer Internship JD or its official URL.
2. The exact Google Docs URLs or pasted text for the quant CV, fundamental resume, and cover-letter template.
3. Permission to read those named files. The plugin does not rewrite them.

The pipeline then creates an isolated case, interviews the candidate one question at a time, and produces the diagnostic before returning copy-ready resume and cover-letter proposals.

## Safety contract

- Candidate facts and metrics must be verified and cited by fact ID.
- Resume changes are summarized in one approval table and returned for manual paste-back.
- Direct resume and cover-letter Google Docs writes are mechanically denied.
- Drafts target one page; formatting compression is prohibited, and final fit is confirmed by the candidate after paste-back.
- Email sending and application submission are denied in version 1.
- Private cases, documents, exports, credentials, and fact banks are excluded from Git.
- Research and QA subagents are read-only. Only the main agent may create an approved Gmail draft.

## Included skills

- `application-pipeline`
- `career-fact-bank`
- `job-fit-diagnostic`
- `application-writer`
- `application-quality-gate`

Tracker-driven discovery and supervised submissions are documented as a future phase and remain disabled.

## Local verification

Install the pinned dependencies from `requirements.txt`, then run:

```text
python -m unittest discover -s tests -v
```

The plugin also includes schema validation, a PDF page-count verifier, and a pre-tool-use enforcement hook.

## Install for new chats

Run `tools/install_job_application_plugin.ps1` from the workspace root, then start a new Codex chat. Invoke `$application-pipeline` or ask to tailor an application from a JD.
