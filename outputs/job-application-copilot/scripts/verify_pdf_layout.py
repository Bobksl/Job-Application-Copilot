#!/usr/bin/env python3
"""Verify the deterministic page-count gate for an exported application PDF."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pypdf import PdfReader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--expected-pages", type=int, default=1)
    args = parser.parse_args(argv)

    try:
        if args.expected_pages < 1:
            raise ValueError("expected page count must be positive")
        reader = PdfReader(args.pdf, strict=False)
        if reader.is_encrypted:
            raise ValueError("encrypted PDFs cannot be verified")
        page_count = len(reader.pages)
        sizes = [
            {
                "width_points": float(page.mediabox.width),
                "height_points": float(page.mediabox.height),
            }
            for page in reader.pages
        ]
    except (OSError, ValueError) as exc:
        print(f"BLOCKED: Cannot verify PDF: {exc}", file=sys.stderr)
        return 1

    if page_count != args.expected_pages:
        print(
            f"BLOCKED: PDF has {page_count} pages; expected {args.expected_pages}.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps({"result": "pass", "page_count": page_count, "page_sizes": sizes}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
