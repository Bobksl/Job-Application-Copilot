# Third-party notices

This project incorporates ideas and adapted code from the open-source projects
listed below. Their licence terms are reproduced in full where required.

---

## ai-job-search

- **Source:** https://github.com/MadsLorentzen/ai-job-search
- **Reviewed at commit:** `becdc5d` (22 August 2026, v1.6.0)
- **Licence:** MIT

### What was adapted

| This repository | Derived from | Nature of the adaptation |
|---|---|---|
| `tools/security_guards.py` | `tools/security_guards.py` | The allowlist-and-fail-loudly pattern, the reasoning about `.gitignore` negations being order-sensitive, and the argument that a hook is more dangerous than a permission. The checks themselves were rewritten for this workspace (private-path rules, hook deny-rule integrity, tracked-file scan). |
| `.gitignore` | `.gitignore` + `REQUIRED_IGNORE_RULES` | The principle that private-data ignore rules must be enumerated somewhere a test can read them, and the depth-independent `**/` pattern technique. Rules rewritten for this layout. |
| Eligibility Gate and Language Gate (in `job-fit-diagnostic`) | `.claude/skills/job-application-assistant/04-job-evaluation.md` | Gate structure, the PASS / FLAG / FAIL classification tables, and the two "easy to get wrong" rules ("silence is not permission"; a company-wide welcome is not role-level permission). Fact-ID binding, case-state recording and the Hong Kong examples are additions. |
| `.github/workflows/ci.yml` | `.github/workflows/ci.yml` | The job structure and the stated honest limit that a pull request can edit the workflow itself. |

Individual files carry an attribution note in their header where the adaptation
is substantial enough to warrant one.

### MIT Licence

```
MIT License

Copyright (c) 2026 Mads Lorentzen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Note on unrelated tooling

Claude Code, Codex and the Notion API are referenced as part of this project's
toolchain. This project is independent and is not affiliated with, endorsed by,
or sponsored by Anthropic, OpenAI or Notion Labs.
