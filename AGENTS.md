# Job Application Workspace Rules

When a user asks for job-fit analysis, resume tailoring, cover-letter drafting, or application email writing, use the installed `job-application-copilot` plugin when available and always follow these workspace rules.

- Return resume and cover-letter wording as copy-ready text for manual paste-back.
- Never edit, rewrite, format, highlight, restore, or overwrite a resume or cover-letter Google Doc.
- Put every proposed resume change into one consolidated table so the user can approve once and give one feedback response.
- Trace every candidate claim and metric to verified facts; never invent or improve metrics.
- Target concise one-page wording, but do not claim layout verification until the user pastes it into the template.
- Never send email or submit an application. Gmail integration, when requested and available, is draft-only after exact approval.
- This workspace is a Git repository with origin `https://github.com/Bobksl/Job-Application-Copilot.git`. Private candidate state under `work/` is excluded by `.gitignore` and enforced by `tools/security_guards.py` and `.githooks/pre-commit`; credentials, private cases, candidate documents, and fact-bank content remain prohibited from Git.

## Local authority and Notion projection

- Local case folders, the local fact bank, and local outcome records are the system of record.
- Notion is a one-way projection that must be rebuildable from local state at any time.
- No process may read or sync Notion content back into a case, fact bank, or outcome record.
