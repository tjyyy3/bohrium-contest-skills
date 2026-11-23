"""Make a numbered reading copy or verify quotations in a UTF-8 source.

Usage: python evidence.py index TEXT
       python evidence.py check TEXT ANCHORS.json
Pages are separated by form feeds. TEXT may be an inspected PDF extraction.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    modes.add_parser("index").add_argument("text", type=Path)
    check = modes.add_parser("check")
    check.add_argument("text", type=Path)
    check.add_argument("anchors", type=Path)
    args = parser.parse_args()
    raw = args.text.read_bytes()
    extracted = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    blocks = extracted.split("\f")
    if len(blocks) > 1 and not blocks[-1].strip():
        blocks.pop()  # pdftotext generally terminates the final page with FF.
    pages = [block.split("\n") for block in blocks]
    if args.mode == "index":
        for page, lines in enumerate(pages, 1):
            if not any(line.strip() for line in lines):
                print(f"p{page} [no extractable text]")
            for number, line in enumerate(lines, 1):
                if line.strip():
                    print(f"p{page}:L{number}\t{line}")
        return 0

    anchors = json.loads(args.anchors.read_text(encoding="utf-8-sig"))
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("provide a nonempty JSON array of quote anchors for one source")
    results = []
    for item in anchors:
        page, first, last = (item[key] for key in ("page", "first", "last"))
        quote = item["quote"]
        if not isinstance(quote, str) or not quote.strip():
            raise ValueError("quote must contain source text")
        if not all(type(n) is int for n in (page, first, last)):
            raise ValueError("page, first and last must be integers")
        in_range = 1 <= page <= len(pages) and 1 <= first <= last <= len(pages[page-1])
        lines = pages[page-1][first-1:last] if in_range else []
        normalized = " ".join(" ".join(lines).split())
        ok = in_range and " ".join(quote.split()) in normalized
        results.append({"anchor": item["id"], "matched": ok, "range_exists": in_range})
    print(json.dumps({"sha256": hashlib.sha256(raw).hexdigest(), "anchors": results},
                     ensure_ascii=False))
    return 0 if all(result["matched"] for result in results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeError, KeyError, TypeError, ValueError) as error:
        print(f"Cannot read evidence: {error}", file=sys.stderr)
        sys.exit(2)
