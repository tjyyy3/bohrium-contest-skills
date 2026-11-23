"""Local, copy-based library repair. Python 3.9+, standard library."""
import argparse
import collections
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unicodedata
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    os.replace(f.name, path)


def separate(a, b):
    if a == b or a in b.parents or b in a.parents:
        raise ValueError(f"select disjoint directories: {a} and {b}")


def inside(root, name):
    path = root / name
    if Path(name).is_absolute() or ".." in Path(name).parts or root not in path.resolve().parents:
        raise ValueError(f"path outside tree or not a file: {name}")
    return path


def extract(path):
    if path.suffix.lower() == ".pdf":
        tool = shutil.which("pdftotext")
        if not tool:
            return [], "pdftotext unavailable"
        try:
            p = subprocess.run([tool, "-enc", "UTF-8", "-layout", str(path), "-"],
                               capture_output=True, timeout=45)
        except subprocess.TimeoutExpired:
            return [], "pdftotext timeout"
        if p.returncode:
            return [], "pdftotext error: " + p.stderr.decode("utf-8", "replace")[:240]
        pages = p.stdout.decode("utf-8").split("\f")
        lines = [(f"p{n}:L{i}", t.strip()) for n, page in enumerate(pages, 1)
                 for i, t in enumerate(page.splitlines(), 1) if t.strip()]
        return lines, "PDF text layer" if lines else "no extractable PDF text; inspect pages"
    if path.suffix.lower() not in {".md", ".txt", ".csv", ".tsv", ".json", ".jsonl",
                                   ".yaml", ".yml", ".ris", ".bib", ".log", ".xml", ".tex"}:
        return [], "unindexed format; inspect with native reader"
    raw = path.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    try:
        value = raw.decode(encoding)
    except UnicodeError:
        return [], "undecodable text; determine encoding before use"
    if "\x00" in value:
        return [], "binary-like text; inspect encoding"
    return [(f"L{i}", t.strip()) for i, t in enumerate(value.splitlines(), 1) if t.strip()], encoding


def scan(root, work):
    separate(root, work)
    if not root.is_dir():
        raise ValueError(f"missing source directory: {root}")
    records, problems, passages = [], [], {}
    def record_error(exc):
        problems.append({"path": os.path.relpath(exc.filename, root), "error": str(exc)})
    for parent, dirs, files in os.walk(root, onerror=record_error):
        dirs.sort()
        for name in list(dirs):
            p = Path(parent) / name
            if p.is_symlink():
                dirs.remove(name)
                problems.append({"path": p.relative_to(root).as_posix(), "error": "directory symlink skipped"})
        for name in sorted(files):
            p = Path(parent) / name
            key = p.relative_to(root).as_posix()
            row = {"source": key}
            records.append(row)
            try:
                mode = p.lstat().st_mode
                row["mode"] = stat.filemode(mode)
                if not stat.S_ISREG(mode):
                    row["issue"] = "not a regular file"
                    continue
                row.update(bytes=p.stat().st_size, sha256=digest(p))
                lines, row["extraction"] = extract(p)
                passages[key] = dict(lines)
            except (OSError, UnicodeError) as exc:
                row["issue"] = str(exc)
    put(work / "inventory.json", {"files": records, "walk_errors": problems})
    put(work / "passages.json", passages)
    print(f"scanned {len(records)} paths; {len(problems)} directory issues")


def component(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", unicodedata.normalize("NFC", value))
    value = value.strip(" .") or "unknown"
    if re.fullmatch(r"(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?", value, re.I):
        value = "_" + value
    return value.encode("utf-8")[:80].decode("utf-8", "ignore").rstrip(" .") or "unknown"


def copy_verified(src, dst, expected):
    if digest(src) != expected:
        raise ValueError("source changed since inventory")
    if dst.exists():
        if digest(dst) == expected:
            return "verified_existing"
        raise ValueError("destination collision: different bytes")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dst.parent, delete=False) as f:
        temp = Path(f.name)
    try:
        shutil.copyfile(src, temp)
        if digest(temp) != expected:
            raise ValueError("copy hash mismatch")
        os.replace(temp, dst)
    finally:
        temp.unlink(missing_ok=True)
    return "copied"


def check_evidence(refs, passages):
    for ref in refs:
        quote = ref.get("quote")
        line = passages.get(ref.get("source"), {}).get(ref.get("locator"), "")
        if not isinstance(quote, str) or not quote.strip() or quote not in line:
            raise ValueError(f"unmatched evidence: {ref}")


def build(root, work, plan_path, output):
    separate(root, output)
    separate(root, work)
    separate(work, output)
    inventory = load(work / "inventory.json")
    passages = load(work / "passages.json")
    plan = load(plan_path)
    files = {row["source"]: row for row in inventory["files"]}
    decisions = plan["records"]
    if set(decisions) - set(files):
        raise ValueError("plan contains paths absent from inventory")
    for obs in plan.get("observations", []):
        key = obs["source"]
        if (key not in files or not files[key].get("sha256") or obs["sha256"] != files[key]["sha256"]
                or not obs["method"].strip() or not obs["locator"].strip() or not obs["text"].strip()):
            raise ValueError(f"unbound external observation: {key}")
        loc = "observed:" + obs["locator"]
        bucket = passages.setdefault(key, {})
        if loc in bucket:
            raise ValueError(f"repeated observation locator: {key} {loc}")
        bucket[loc] = obs["text"]
    for key, decision in decisions.items():
        refs = decision.get("evidence", [])
        if not refs and any(decision.get(k) for k in ("folder", "stem", "metadata", "tags")):
            raise ValueError(f"classification without evidence: {key}")
        check_evidence(refs, passages)
        folder = decision.get("folder", ["Review"])
        if not isinstance(folder, list) or not folder or not all(isinstance(x, str) and x for x in folder):
            raise ValueError(f"invalid folder: {key}")
        meta = decision.get("metadata", {})
        authors = meta.get("authors", [])
        if not isinstance(authors, list) or any(not isinstance(x, str) or not x for x in authors):
            raise ValueError(f"authors must be an array of names: {key}")
    relations = plan.get("relations", [])
    for edge in relations:
        if edge.get("from") not in files or edge.get("to") not in files or not edge.get("evidence"):
            raise ValueError(f"unresolved relation: {edge}")
        check_evidence(edge["evidence"], passages)
    policy = {"inventory_sha256": digest(work / "inventory.json"), "plan_sha256": digest(plan_path),
              "passages_sha256": digest(work / "passages.json")}
    stamp = output / "run.json"
    if stamp.exists() and load(stamp) != policy:
        raise ValueError("changed inventory or plan: use a fresh output directory")
    if not stamp.exists() and output.exists() and any(output.iterdir()):
        raise ValueError("choose a clean subdirectory for the bundle")
    put(stamp, policy)
    groups = collections.defaultdict(list)
    for key, row in files.items():
        if "sha256" in row:
            groups[row["sha256"]].append(key)
    entries, index, targets = [], [], {}
    issues = list(inventory["walk_errors"])
    for sha, members in sorted(groups.items()):
        canonical = min(members, key=lambda k: (not decisions.get(k, {}).get("preferred", False),
                                                not bool(decisions.get(k, {}).get("evidence")), k))
        decision = decisions.get(canonical) or {"uncertainty": "No classification decision supplied."}
        folder = decision.get("folder", ["Review"])
        meta = decision.get("metadata", {})
        title = meta.get("title") or Path(canonical).stem
        author = (meta.get("authors") or ["unknown-author"])[0]
        stem = decision.get("stem") or f"{author}-{meta.get('year') or 'undated'}-{title}"
        suffix = component(Path(canonical).suffix.lstrip(".")) if Path(canonical).suffix else ""
        filename = component(stem) + (("." + suffix) if suffix else "")
        directory = Path("files", *(component(x) for x in folder))
        target = (directory / filename).as_posix()
        if target.casefold() in targets:
            target = (directory / (component(stem) + "--" + sha + (("." + suffix) if suffix else ""))).as_posix()
        if target.casefold() in targets:
            raise ValueError(f"unresolved target collision: {target}")
        targets[target.casefold()] = sha
        for key in [canonical] + sorted(set(members) - {canonical}):
            row = dict(files[key], canonical_source=canonical, destination=target, decision=decision,
                       byte_role="representative" if key == canonical else "exact_alias")
            if key != canonical and key in decisions:
                row["alias_note"] = decisions[key]
            try:
                action = copy_verified(inside(root, key), inside(output, target), sha)
                row["action"] = action
            except (OSError, ValueError) as exc:
                row["error"] = str(exc)
                issues.append({"source": key, "error": str(exc)})
            entries.append(row)
            if "error" not in row:
                for loc, line in passages.get(key, {}).items():
                    index.append({"source": key, "location": loc, "text": line, "destination": target})
    for key, row in files.items():
        if "sha256" not in row:
            entries.append(dict(row, action="skipped"))
            issues.append({"source": key, "error": row.get("issue", "no hash")})
    put(output / "catalog.json", {"files": entries, "relations": relations, "issues": issues,
                                  "observations": plan.get("observations", [])})
    put(output / "index.json", index)
    print(f"{len(entries)} catalog rows, {len(groups)} byte groups, {len(index)} passages, {len(issues)} operational issues")
    return not issues


def search(bundle, words):
    terms = [t.casefold() for t in words]
    rows = load(bundle / "index.json")
    hits = [r for r in rows if all(t in r["text"].casefold() for t in terms)]
    return {"terms": words, "unit": "one source line; case-insensitive AND substrings", "count": len(hits), "hits": hits}


def restore(bundle, destination):
    separate(bundle, destination)
    rows = []
    for row in load(bundle / "catalog.json")["files"]:
        item = {"source": row["source"]}
        try:
            if "error" in row or not row.get("destination"):
                raise ValueError("unavailable catalog entry")
            item["action"] = copy_verified(inside(bundle, row["destination"]),
                                           inside(destination, row["source"]), row["sha256"])
        except (ValueError, OSError) as exc:
            item["error"] = str(exc)
        rows.append(item)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    subs = ap.add_subparsers(dest="command", required=True)
    for name, args in {"scan": ["source", "work"], "build": ["source","work","plan","bundle"],
                       "restore": ["bundle","destination","receipt"], "search": ["bundle","receipt"]}.items():
        sp = subs.add_parser(name)
        for arg in args:
            sp.add_argument(arg, type=lambda s: Path(s).resolve())
        if name == "search":
            sp.add_argument("terms", nargs="+")
    a = ap.parse_args()
    if a.command == "scan":
        scan(a.source, a.work)
    elif a.command == "build":
        if not build(a.source, a.work, a.plan, a.bundle):
            raise SystemExit(2)
    elif a.command == "search":
        put(a.receipt, search(a.bundle, a.terms))
    else:
        rows = restore(a.bundle, a.destination)
        put(a.receipt, rows)
        if any("error" in r for r in rows):
            raise SystemExit(2)


if __name__ == "__main__":
    main()
