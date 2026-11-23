"""Locate short quotes and inspect possible declaration headings in UTF-8 text."""

import argparse
import json
import re
from pathlib import Path


def inspect_text(path, args):
    raw = path.read_text(encoding="utf-8-sig")
    pages = raw.split("\f")
    if pages[-1] == "" and len(pages) > 1:
        pages.pop()  # pdftotext terminates each rendered page with a form feed.
    hits = []
    for number, page in enumerate(pages, 1):
        if args.mode == "quote":
            if args.page and number != args.page:
                continue
            # Normalize whitespace only. Preserve case, qualifiers and punctuation.
            pattern = r"\s+".join(re.escape(word) for word in args.text.split())
            matches = re.finditer(pattern, page)
            hits.extend({"page": number, "line": 1 + page.count("\n", 0, m.start()),
                         "end_line": 1 + page.count("\n", 0, m.end())}
                        for m in matches)
        else:
            for line_number, line in enumerate(page.splitlines(), 1):
                terms = [term for term in args.terms if term.casefold() in line.casefold()]
                if terms:
                    hits.append({"page": number, "line": line_number, "terms": terms})
    return {"file": str(path), "pages": len(pages), "hits": hits,
            "empty_pages": [i for i, pg in enumerate(pages, 1) if not pg.strip()]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    quote = modes.add_parser("quote", help="Confirm one quotation at a unique location")
    quote.add_argument("file", type=Path)
    quote.add_argument("text")
    quote.add_argument("--page", type=int)
    scan = modes.add_parser("scan", help="List candidate lines for literal terms")
    scan.add_argument("files", type=Path, nargs="+")
    scan.add_argument("--terms", nargs="+", required=True)
    args = parser.parse_args()
    if args.mode == "quote" and (not args.text.strip() or
                                 (args.page is not None and args.page < 1)):
        parser.error("Provide a nonempty quote and a positive page number.")
    if args.mode == "scan" and not all(term.strip() for term in args.terms):
        parser.error("Provide nonempty literal terms.")
    paths = [args.file] if args.mode == "quote" else args.files
    try:
        records = [inspect_text(path, args) for path in paths]
    except (OSError, UnicodeError) as exc:
        parser.exit(2, f"Unable to read source: {exc}\n")
    print(json.dumps(records, ensure_ascii=True, indent=2))
    return int(args.mode == "quote" and len(records[0]["hits"]) != 1)


if __name__ == "__main__":
    raise SystemExit(main())
