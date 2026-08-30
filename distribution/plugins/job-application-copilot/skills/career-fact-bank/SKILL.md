---
name: career-fact-bank
description: Build and maintain a private, source-grounded career fact bank through one-question-at-a-time interviews. Use when a job application needs candidate history, responsibilities, achievements, skills, metrics, education, career breaks, or projects verified before writing.
---

# Career Fact Bank

Convert candidate history into small reusable claims without improving or inferring the facts.

## Interview

1. Read the existing fact bank and relevant resume sources first.
2. Ask one focused question at a time and attach the current best guess.
3. Focus each round on one role, project, activity, education period, exchange, or career break.
4. Separate responsibility, method, audience, result, and metric.
5. Ask how the user knows a metric and whether it can be publicly stated.
6. Restate the proposed fact and obtain an explicit verification decision.

Do not treat old resume wording or model-generated text as verified merely because it exists.

## Fact States

- `verified`: the candidate explicitly confirmed the claim and its evidence.
- `unverified`: plausible but awaiting confirmation; never usable in final materials.
- `rejected`: candidate denied or corrected it; retain only if needed to prevent recurrence.

Metrics are independently verified. A verified responsibility does not verify a number attached to it.

## Recording

Use the root `schemas/fact_bank.schema.json`. Give each claim a stable `FACT-...` ID. Record:

- Organization and context
- Atomic claim
- Skills actually demonstrated
- Metrics with separate status
- Evidence references
- Allowed uses
- Verification date

Run schema validation after each approved batch. Keep the file in the plugin data directory, never in Git.

## Unknown Metrics

In a proposal, preserve uncertainty visibly, for example:

`Designed an AI-assisted research workflow ..., [reducing research time by ...].`

Do not store the bracketed wording as a verified claim. Store the underlying responsibility and leave the metric null/unverified. The final-quality gate must remove the bracketed prompt or the entire unsupported clause.

Read [fact-policy.md](references/fact-policy.md) when resolving conflicts, version history, or metric provenance.
