"""Index authorized files, rank passages, reopen citations, and repair verified links."""
import argparse
import collections
import hashlib
import html
import json
import math
import os
import re
import shutil
import sys
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree.ElementTree import ParseError

from extract import extract


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def source(root, rel):
    parts = PurePosixPath(rel).parts
    if not parts or rel.startswith("/") or ".." in parts or "\\" in rel or ":" in parts[0]:
        raise ValueError("expected library-relative POSIX path")
    node = root
    for part in parts:
        node = node / part
        if node.is_symlink() or (hasattr(node, "is_junction") and node.is_junction()):
            raise ValueError("link target outside verified selection; resolve authorization first")
    if not node.resolve().is_relative_to(root):
        raise ValueError("path escapes library")
    return node


def enumerate_files(root, problems):
    def inaccessible(err):
        problems.append({"path": os.path.relpath(err.filename, root), "status": "listing_failed", "reason": str(err)})
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=inaccessible):
        for d in sorted(dirs.copy()):
            child = Path(directory) / d
            if child.is_symlink() or (hasattr(child, "is_junction") and child.is_junction()):
                dirs.remove(d)
                problems.append({"path": child.relative_to(root).as_posix(), "status": "skipped_link"})
        dirs.sort()
        for name in sorted(files):
            yield (Path(directory) / name).relative_to(root).as_posix()


def index(args):
    root = Path(args.root).resolve(strict=True)
    if not root.is_dir() or Path(args.out).resolve().is_relative_to(root):
        raise ValueError("root must be a directory and index must be outside it")
    manifest = load(args.manifest) if args.manifest else None
    problems, inventory, contents = [], [], {}
    paths = manifest.keys() if manifest is not None else enumerate_files(root, problems)
    for rel in sorted(paths):
        spec = manifest[rel] if manifest is not None else {"allow": True}
        info = {"path": rel, "meta": spec.get("meta", {}), "provenance": spec.get("provenance", {}),
                "expected_sha256": spec.get("expected_sha256"), "type": Path(rel).suffix.lower().lstrip("."),
                "access": "manifest" if manifest is not None else "authorized_root"}
        inventory.append(info)
        if spec.get("allow") is not True:
            info["status"] = "denied"
            continue
        try:
            path = source(root, rel)
            if not path.is_file():
                info["status"] = "missing" if not path.exists() else "not_regular"
                continue
            sig = digest(path)
            info.update(sha256=sig, size=path.stat().st_size)
            if info["expected_sha256"] and sig != info["expected_sha256"]:
                info["status"] = "identity_conflict"
                continue
            # Extension selects decoder. A mislabeled alias cannot poison its readable twin.
            key = sig + ":" + info["type"]
            if key not in contents:
                passages, issues = extract(path)
                contents[key] = {"passages": passages, "issues": issues}
            data = contents[key]
            info.update(content_key=key, status=("partial" if data["issues"] else "indexed") if data["passages"] else "no_text")
        except (OSError, ValueError, KeyError, IndexError, RuntimeError, ParseError, zipfile.BadZipFile, TimeoutError) as err:
            info.update(status="unreadable" if isinstance(err, PermissionError) else "extract_failed", reason=str(err))
        except Exception as err:
            # Third-party PDF readers raise backend-specific exception classes.
            info.update(status="extract_failed", reason=f"{type(err).__name__}: {err}")
    by_hash = collections.defaultdict(list)
    for f in inventory:
        if f.get("sha256") and f["status"] != "identity_conflict":
            by_hash[f["sha256"]].append(f["path"])
    save(args.out, {"schema": 1, "root": str(root), "files": inventory, "contents": contents,
                    "exact_copies": {k: v for k, v in by_hash.items() if len(v) > 1}, "listing_issues": problems})
    print(json.dumps({"files": len(inventory), "status": dict(collections.Counter(f["status"] for f in inventory)),
                      "passages": sum(len(v["passages"]) for v in contents.values()), "listing_issues": len(problems)}))


def norm(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def match_term(term, text):
    t = norm(term)
    if not t:
        return False
    if re.fullmatch(r"[a-z0-9][a-z0-9 ._/-]*", t):
        return re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", text) is not None
    return t in text


def allowed(f, filters):
    for field, xs in filters.items():
        actual = f[field] if field in {"path", "type", "sha256"} and field in f else f["meta"].get(field)
        actuals = actual if isinstance(actual, list) else [actual]
        expected = xs if isinstance(xs, list) else [xs]
        if not any(norm(v) == norm(x) for v in actuals if v is not None for x in expected if x is not None):
            return False
    return True


def excerpt(body, matched):
    if len(body) <= 850:
        return body
    # Preserve original characters, including line breaks. Metadata is never a quote.
    offsets = [m.start() for t in matched if (m := re.search(re.escape(t), body, re.I))]
    start = max(0, min(offsets, default=0) - 150)
    return body[start:start + 850]


def search(args):
    idx, q = load(args.index), load(args.query)
    groups = q["groups"]
    if not isinstance(groups, list) or not groups or not all(isinstance(g, list) and g and
            all(isinstance(t, str) and t.strip() for t in g) for g in groups):
        raise ValueError("supply nonempty groups of alternative terms")
    minimum = q.get("min_groups", len(groups))
    if type(minimum) is not int or not 1 <= minimum <= len(groups):
        raise ValueError("min_groups must be 1..number of groups")
    filters = q.get("filters", {})
    eligible = [f for f in idx["files"] if "content_key" in f and allowed(f, filters)]
    aliases = collections.defaultdict(list)
    for f in eligible:
        aliases[f["content_key"]].append(f)
    hits, freq, count = [], collections.Counter(), 0
    for key, files in aliases.items():
        for p in idx["contents"][key]["passages"]:
            body, section = norm(p["text"]), norm(p["section"])
            matches = [[t for t in g if match_term(t, body) or match_term(t, section)] for g in groups]
            seen = [i for i, m in enumerate(matches) if m]
            freq.update(seen)
            count += 1
            if len(seen) < minimum:
                continue
            f = files[0]
            quote_text = excerpt(p["text"], [t for i in seen for t in matches[i]])
            hits.append({"path": f["path"], "aliases": [x["path"] for x in files[1:]], "sha256": f["sha256"],
                         "type": f["type"], "meta": f["meta"], "provenance": f["provenance"],
                         **{k: v for k, v in p.items() if k != "text"}, "quote": quote_text,
                         "start": p["text"][:110], "matched_terms": matches,
                         "groups_in_body": [i for i in seen if any(match_term(t, body) for t in matches[i])]})
    for h in hits:
        h["score"] = sum((1.5 if i in h["groups_in_body"] else 1) * math.log1p((count + 1) / (freq[i] + 1))
                         for i, m in enumerate(h["matched_terms"]) if m)
    hits.sort(key=lambda h: (-sum(bool(x) for x in h["matched_terms"]), -h["score"], h["path"], h["locator"]))
    n = q.get("limit", 30)
    if type(n) is not int or n < 1:
        raise ValueError("limit must be a positive integer")
    skipped = [{"path": f["path"], "reason": f["status"]} for f in idx["files"] if f["status"] not in {"indexed", "partial"}]
    report = {"question": q.get("question", ""), "query": q, "eligible_paths": [f["path"] for f in eligible],
              "filtered_paths": [f["path"] for f in idx["files"] if f.get("content_key") and not allowed(f, filters)],
              "unsearched": skipped, "coverage_issues": idx["listing_issues"] +
              [{"path": f["path"], "issues": idx["contents"][f["content_key"]]["issues"]} for f in eligible
               if idx["contents"][f["content_key"]]["issues"]], "hit_count": len(hits), "hits": hits[:n]}
    save(args.out, report)
    print(json.dumps({"eligible": len(eligible), "hit_count": len(hits), "returned": len(hits[:n])}))


def verify(args):
    idx, report = load(args.index), load(args.hits)
    root = Path(idx["root"]).resolve()
    entries = {f["path"]: f for f in idx["files"]}
    opened, results = {}, []
    for h in report["hits"]:
        rel = h["path"]
        row = {"path": rel, "locator": h["locator"], "status": "failed"}
        try:
            f = entries[rel]
            if f["status"] not in {"indexed", "partial"} or not allowed(f, report["query"].get("filters", {})):
                raise ValueError("permission or eligibility mismatch")
            path = source(root, rel)
            if rel not in opened:
                sig = digest(path)
                if sig != f["sha256"]:
                    raise ValueError("source changed since indexing")
                opened[rel] = (sig, {p["locator"]: p for p in extract(path)[0]})
            sig, records = opened[rel]
            p = records[h["locator"]]
            if sig != h["sha256"] or not h["quote"] or h["quote"] not in p["text"] or h["section"] != p["section"]:
                raise ValueError("digest, locator, section or literal excerpt mismatch")
            page = re.match(r"PDF:page=(\d+):", h["locator"])
            row.update(status="verified", sha256=sig, uri=path.as_uri() + (f"#page={page[1]}" if page else ""))
        except Exception as err:
            row["reason"] = str(err)
        results.append(row)
    save(args.out, {"checked": len(results), "failures": sum(r["status"] == "failed" for r in results), "records": results})
    if args.html:
        out = Path(args.html)
        out.parent.mkdir(parents=True, exist_ok=True)
        parts = ['<!doctype html><meta charset=utf-8><title>Passage evidence</title><h1>Passage evidence</h1>']
        for i, (h, r) in enumerate(zip(report["hits"], results), 1):
            if r["status"] != "verified":
                continue
            e = html.escape
            parts.append(f'<article id="E{i}"><h2>E{i} · {e(h["section"] or h["locator"])}</h2>'
                         f'<a href="{e(r["uri"], quote=True)}">{e(h["path"])}</a> · {e(h["locator"])}'
                         f'<blockquote style="white-space:pre-wrap">{e(h["quote"])}</blockquote>'
                         f'<small>SHA-256 {r["sha256"]}</small></article>')
        out.write_text("\n".join(parts), encoding="utf-8")
    return 2 if any(r["status"] == "failed" for r in results) else 0


def recover(args):
    idx = load(args.index)
    root, dest = Path(idx["root"]).resolve(), Path(args.dest).resolve()
    if dest.is_relative_to(root):
        raise ValueError("recovery directory must be outside input")
    results = []
    for f in idx["files"]:
        if f["status"] != "missing":
            continue
        row = {"original": f["path"], "status": "unresolved", "expected_sha256": f["expected_sha256"]}
        matches = [x for x in idx["files"] if x.get("sha256") == f["expected_sha256"] and
                   f["expected_sha256"] and x["status"] in {"indexed", "partial", "no_text"}]
        try:
            if not matches:
                raise ValueError("no authorized byte-identical copy tied to an expected digest")
            src = source(root, matches[0]["path"])
            target = source(dest, f["path"])
            if digest(src) != f["expected_sha256"]:
                raise ValueError("recovery source changed")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and digest(target) != f["expected_sha256"]:
                raise ValueError("recovery destination has conflicting bytes")
            if not target.exists():
                with src.open("rb") as inp, target.open("xb") as out:
                    shutil.copyfileobj(inp, out)
            if digest(target) != f["expected_sha256"]:
                raise ValueError("recovered copy failed digest verification")
            row.update(status="verified_copy", source=matches[0]["path"], destination=str(target),
                       sha256=f["expected_sha256"])
        except (OSError, ValueError) as err:
            row["reason"] = str(err)
        results.append(row)
    save(args.out, {"actions": results})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for_command = parser.add_subparsers(dest="cmd", required=True)
    for name, func, required, optional in [
        ("index", index, ("root", "out"), ("manifest",)), ("search", search, ("index", "query", "out"), ()),
        ("verify", verify, ("index", "hits", "out"), ("html",)), ("recover", recover, ("index", "dest", "out"), ())]:
        command = for_command.add_parser(name)
        command.set_defaults(func=func)
        for field in required:
            command.add_argument("--" + field, required=True)
        for field in optional:
            command.add_argument("--" + field)
    opts = parser.parse_args()
    sys.exit(opts.func(opts) or 0)
