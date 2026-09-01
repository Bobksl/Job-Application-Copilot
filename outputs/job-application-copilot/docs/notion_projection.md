# Notion projection contract

Local case folders, the fact bank, and application outcome records are authoritative. Notion is a one-way, disposable view that can be rebuilt from those local records. Nothing in this repository may import Notion state into local application data.

## Offline export

`scripts/export_projection.py` reads `cases/*/application_case.json` and any adjacent `application_outcome.json`. It performs no network calls and writes one JSON payload to stdout or `--out <path>`:

```text
python scripts/export_projection.py --data-dir <local-data-directory>
python scripts/export_projection.py --data-dir <local-data-directory> --out projection.json
```

Document references are reduced to filenames. Document URLs and document content are never exported. Use `--redact` to omit both `url` and `documents` from every row.

## Separate uploader requirements

The uploader is a separate, externally authorized step and is not implemented here. It must obey all of these rules:

1. Upsert only by the row's stable `key` (`case_id`). Never fuzzy-match company or role.
2. Refresh page properties from the payload on every successful run.
3. Write a page body only when creating the page. Never rewrite an existing page body, because it may contain user-authored notes.
4. Never delete or archive projected rows. Represent changes through refreshed status properties.
5. If Notion is unreachable, print one concise failure line, exit without modifying local state, and do not affect any other workflow step.

The uploader must never:

- read a Notion page or database value and write it into a local case, fact bank, or outcome record;
- upload résumé or cover-letter content, rendered text, or document URLs;
- treat company and role as an identity key; or
- make projection availability a prerequisite for local application work.
