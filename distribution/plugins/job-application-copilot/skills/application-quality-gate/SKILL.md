---
name: application-quality-gate
description: Independently audit a resume redline table, cover-letter draft, email, change set, or Gmail payload for verified facts, resolved placeholders, approval, tone, ATS balance, and concise one-page awareness. Use before final copy-ready handoff and before or after Gmail draft creation. Google Docs writes are prohibited.
---

# Application Quality Gate

Act as an independent, read-only critic. Do not repair text silently and do not perform external writes.

## Draft Gate

1. Validate the fact bank and change set against root schemas when structured artifacts exist.
2. Trace every candidate claim and metric to verified fact IDs allowed for that artifact; every percentage must exactly match a verified metric in its cited facts.
3. Block unresolved square-bracket placeholders from final copy-ready text.
4. Check direct human tone, active voice, repetition, and restrained ATS usage.
5. For resume changes, check that the candidate received one complete table rather than fragmented approvals.
6. Check length awareness, but do not claim layout or page-count verification before manual paste-back.

When a structured change set is used, run:

```text
python <plugin-root>/scripts/quality_gate.py prewrite --fact-bank <facts> --change-set <changes>
```

Only a clean pass may proceed to copy-ready handoff or Gmail authorization.

## Gmail Payload Authorization

For Gmail only, the main agent saves the final tool arguments as JSON, then runs:

```text
python <plugin-root>/scripts/authorize_action.py --action gmail_draft --payload <payload> --change-set <changes> --fact-bank <facts> --data-dir <plugin-data>
```

Authorization expires within ten minutes, matches the payload hash exactly, and is consumed once. Any payload change requires a new quality pass and authorization. Never authorize `google_doc_update`.

## Final Draft Gate

For resume and cover letter, verify factual traceability, resolved placeholders, direct tone, natural ATS use, and concise length. Mark layout as unverified until the candidate manually pastes the text into the template and confirms one-page fit. Do not claim formatting or PDF validation from draft text alone.

Read [qa-checklist.md](references/qa-checklist.md) for the complete acceptance checklist.
