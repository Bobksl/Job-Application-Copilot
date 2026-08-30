# Job Application Copilot

A quality-first, fact-grounded AI copilot for job applications. It reads a job
description, checks whether you are actually eligible, maps every requirement to
a **verified** fact about you, and returns one reviewable table of proposed
résumé changes plus a researched cover letter — as copy-ready text you paste in
yourself.

The distinguishing property is not the writing. It is that **the safety rules are
code, not instructions.** A pre-tool-use hook denies direct document writes,
email sending and application submission regardless of what the model decides,
and fails closed on malformed input. A quality gate refuses to release a draft
whose claims do not trace to verified fact IDs, or whose approval hash does not
match the exact wording being approved.

> **Status:** version 0.2.0, single-user, one completed pilot. Not yet packaged
> for other people to install — see the roadmap below.

---

## What it does

1. **Eligibility and language gates.** Hard filters that run *before* any
   scoring. A posting silent on citizenship is marked unverified, not passed —
   graduate programmes routinely gate eligibility on their website, not the ad.
2. **Fit diagnostic.** Parses the JD, scores fit, selects a résumé track, and
   names the gaps and unknowns explicitly.
3. **Fact bank.** A one-question-at-a-time interview that records facts with
   provenance, metrics, allowed uses, and a verification state — verified,
   unverified, pending, rejected, or superseded.
4. **Consolidated redline.** Every proposed résumé change in one table, each row
   traced to a fact ID, approved in a single response.
5. **Cover letter.** Company-specific, built from official sources first, with
   reported facts kept separate from reasonable inference.
6. **Quality gate.** Blocks unknown or unverified fact IDs, unverified
   percentages, unresolved placeholders, and stale approvals.

## What it will not do

By design, and enforced in code rather than in prompt text:

- Invent, infer, round, or "improve" a fact or metric about the candidate.
- Edit, rewrite, reformat, or overwrite a résumé or cover-letter document.
- Send an email or submit an application.
- Read a broad email inbox.
- Store credentials, candidate documents, or fact-bank content in version control.

A Gmail *draft* may be created only when email is the genuine application route,
the exact recipient, subject and body have been approved, no placeholders remain,
and a valid one-time authorization matches that exact payload. Sending stays
prohibited.

## Why direct document editing was removed

An early pilot experimented with writing directly into Google Docs. It produced
incorrect fonts and bullet styling, spread formatting changes into unrelated
sections, and caused page overflow — each repair consuming more effort than the
original edit saved. The product boundary moved: the copilot now returns exact,
fact-linked replacement text, and the document write is mechanically blocked.

Formatting targets remain as writing discipline (single spacing, existing margins,
one page). Overflow is solved by more concise wording or a specifically approved
removal — never by shrinking fonts or margins. Layout is not claimed as verified
until the text has been pasted into the real template.

---

## Repository layout

```
outputs/job-application-copilot/    implementation: skills, schemas, scripts, hooks, tests
workspace-skill-source/             the user-facing reusable skill
distribution/plugins/               packaged distribution
tools/                              repository guards
.githooks/                          pre-commit guard (see Setup)
```

Private state — the fact bank, application cases, candidate documents, the
company longlist — lives outside version control and is enumerated in
`.gitignore`. `tools/security_guards.py` fails if any of those rules is weakened,
if an un-allowlisted hook event appears, if a deny rule disappears from the hook,
or if a private file is tracked.

## Setup

```bash
git config core.hooksPath .githooks   # once per clone — installs the pre-commit guard
python tools/security_guards.py       # should print OK
```

Run the regression suite:

```bash
cd outputs/job-application-copilot
python -m unittest discover -s tests -v
```

---

## Roadmap

- **Now** — repository hardening and the two pre-scoring gates.
- **Next** — three further application pilots, with outcome recording built
  *before* they run so the pipeline produces measurable data rather than
  anecdotes. ATS text-layer verification of pasted-back documents.
- **Then** — a career roadmap builder: weighted skill-gap aggregation across all
  evaluated roles. Meaningless at one case, which is why it follows the pilots.
- **Later** — generalization as a personalized template that a student clones and
  onboards into, with versioned methodology files and an upstream update checker.
  Deliberately not a hosted application: that would mean custody of other
  people's career data and moving enforcement server-side, giving up the
  guarantees above.

## Credits

Adapted in part from [ai-job-search](https://github.com/MadsLorentzen/ai-job-search)
by Mads Lorentzen (MIT). See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for
what was taken and how it was changed.

Independent project; not affiliated with or endorsed by Anthropic, OpenAI or
Notion Labs.
