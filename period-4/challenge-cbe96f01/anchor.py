"""Index supplied documents and replay case-sensitive, whitespace-normalized anchors."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def normalized(text):
    return " ".join(text.split())


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_pages(path, data):
    if path.suffix.lower() == ".pdf":
        if shutil.which("pdftotext") is None:
            try:
                import fitz
            except ImportError:
                raise ValueError("PDF extraction needs pdftotext or PyMuPDF; use manual page review")
            with fitz.open(stream=data, filetype="pdf") as doc:
                if doc.needs_pass:
                    raise ValueError("encrypted PDF; request a readable copy")
                return [normalized(page.get_text("text", sort=True)) for page in doc]
        run = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"],
            capture_output=True, timeout=90,
        )
        if run.returncode:
            raise ValueError(f"pdftotext failed on {path}: {run.stderr.decode(errors='replace')[:500]}")
        data = run.stdout
    elif path.suffix.lower() not in {".txt", ".md", ".tsv", ".csv"}:
        raise ValueError(f"unsupported file type: {path}")
    pages = data.decode("utf-8-sig").split("\f")
    if len(pages) > 1 and not pages[-1].strip():
        pages.pop()
    return [normalized(page) for page in pages]


def index(args):
    documents = {}
    for entry in args.documents:
        key, sep, filename = entry.partition("=")
        if not sep or not key or key in documents:
            raise ValueError(f"expected unique ID=PATH: {entry}")
        path = Path(filename).resolve(strict=True)
        data = path.read_bytes()
        documents[key] = {"path": str(path), "sha256": digest(data), "pages": read_pages(path, data)}
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.index.parent,
                                     delete=False) as target:
        json.dump(documents, target, ensure_ascii=False)
    os.replace(target.name, args.index)
    return {"pages": {k: len(v["pages"]) for k, v in documents.items()},
            "empty_pages": {k: [i for i, p in enumerate(v["pages"], 1) if not p]
                            for k, v in documents.items()}}, True


def hits(page, query):
    if not query:
        raise ValueError("empty quote or query")
    start = page.find(query)
    while start >= 0:
        yield start
        start = page.find(query, start + 1)


def find(args):
    doc = load(args.index)[args.doc]
    query = normalized(args.query)
    rows = []
    for number, page in enumerate(doc["pages"], 1):
        for offset in hits(page, query):
            rows.append({"page": number, "offset": offset,
                         "context": page[max(0, offset - 45):offset + len(query) + 45]})
    return rows, True


def check(args):
    docs = load(args.index)
    anchors = load(args.anchors)
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("expected a nonempty array of text anchors")
    verified_files = {}
    ids = set()
    result = []
    for a in anchors:
        key = a["id"]
        idx = a["page"]
        if not isinstance(key, str) or not key.strip() or key in ids:
            raise ValueError(f"empty or duplicate anchor id: {key}")
        ids.add(key)
        doc = docs[a["doc"]]
        if type(idx) is not int or not 1 <= idx <= len(doc["pages"]):
            raise ValueError(f"page out of range: {key}")
        if a["doc"] not in verified_files:
            verified_files[a["doc"]] = digest(Path(doc["path"]).read_bytes()) == doc["sha256"]
        offsets = list(hits(doc["pages"][idx - 1], normalized(a["quote"])))
        result.append({"id": key, "doc": a["doc"], "page": idx, "source_sha256": doc["sha256"],
                       "offsets": offsets, "current_source": verified_files[a["doc"]],
                       "ok": len(offsets) == 1 and verified_files[a["doc"]]})
    return result, all(row["ok"] for row in result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    for name, operation in [("index", index), ("find", find), ("check", check)]:
        sub = subs.add_parser(name)
        sub.set_defaults(operation=operation)
        sub.add_argument("index", type=Path)
        if name == "index":
            sub.add_argument("documents", nargs="+", metavar="ID=PATH")
        elif name == "find":
            sub.add_argument("doc")
            sub.add_argument("query")
        else:
            sub.add_argument("anchors", type=Path)
    args = parser.parse_args()
    try:
        response, ok = args.operation(args)
        print(json.dumps(response, ensure_ascii=True))
        return 0 if ok else 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, subprocess.TimeoutExpired) as err:
        print(json.dumps({"error": str(err)}, ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
