"""Version 1.0. Index a supplied source and replay short quotations by page and line."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unicodedata


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def index(source, destination):
    raw = source.read_bytes()
    if source.suffix.lower() == ".pdf":
        if shutil.which("pdftotext"):
            result = subprocess.run(
                ["pdftotext", "-enc", "UTF-8", "-layout", str(source), "-"],
                capture_output=True, check=True
            )
            content = result.stdout.decode("utf-8")
            pages = content.split("\f")
            if pages[-1] == "":
                pages.pop()
            method = "Poppler layout"
        else:
            try:
                import pymupdf
            except ImportError as exc:
                raise ValueError("PDF indexing requires pdftotext or PyMuPDF; inspect rendered pages if available") from exc
            with pymupdf.open(source) as document:
                pages = [page.get_text(sort=True) for page in document]
            method = "PyMuPDF sorted text"
    elif source.suffix.lower() in {".md", ".txt", ".tex", ".csv", ".tsv"}:
        pages = raw.decode("utf-8-sig").split("\f")
        method = "UTF-8 form-feed pages"
    else:
        raise ValueError("Use a PDF or a supported UTF-8 text source")
    pages = [page.splitlines() for page in pages]
    data = {"source": source.name, "sha256": hashlib.sha256(raw).hexdigest(), "method": method, "pages": pages}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    blank = [i for i, page in enumerate(pages, 1) if not any(line.strip() for line in page)]
    print(json.dumps({"pages": len(pages), "blank_pages": blank, "sha256": data["sha256"]}))


def normalize(value):
    return " ".join(unicodedata.normalize("NFC", value).split())


def check(ledger, paths):
    indices = {}
    for path in paths:
        item = read_json(path)
        if item["source"] in indices:
            raise ValueError("Ambiguous source basename: " + item["source"])
        indices[item["source"]] = item
    failures = []
    count = 0
    for row in read_json(ledger):
        count += 1
        try:
            item = indices[row["source"]]
            page, first, last = (row[key] for key in ("page", "first", "last"))
            if any(type(x) is not int for x in (page, first, last)):
                raise ValueError("page and line references require integers")
            if not 1 <= page <= len(item["pages"]):
                raise ValueError("page out of range")
            lines = item["pages"][page - 1]
            if not 1 <= first <= last <= len(lines) or last - first > 5:
                raise ValueError("use a tight span of one to six real lines")
            quote = normalize(row["quote"])
            if not quote or quote not in normalize(" ".join(lines[first - 1:last])):
                raise ValueError("quote absent from span")
            if "sha256" in row and row["sha256"] != item["sha256"]:
                raise ValueError("source version mismatch")
        except (KeyError, ValueError, TypeError) as exc:
            failures.append({"row": count, "issue": str(exc)})
    if not count:
        raise ValueError("empty anchor list; record an unavailable-source status separately")
    print(json.dumps({"anchors": count, "failures": failures}, ensure_ascii=False))
    return int(bool(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cmds = parser.add_subparsers(dest="action", required=True)
    build = cmds.add_parser("index")
    build.add_argument("source", type=Path)
    build.add_argument("destination", type=Path)
    view = cmds.add_parser("show")
    view.add_argument("index")
    view.add_argument("page", type=int)
    verify = cmds.add_parser("check")
    verify.add_argument("ledger")
    verify.add_argument("indices", nargs="+")
    args = parser.parse_args()
    if args.action == "check":
        return check(args.ledger, args.indices)
    if args.action == "index":
        index(args.source, args.destination)
        return 0
    data = read_json(args.index)
    if not 1 <= args.page <= len(data["pages"]):
        raise ValueError("page out of range")
    for i, line in enumerate(data["pages"][args.page - 1], 1):
        print(f"{args.page}.{i}\t{line}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Anchor check failed: {exc}", file=sys.stderr)
        sys.exit(2)
