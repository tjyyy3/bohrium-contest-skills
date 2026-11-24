"""Research library ledger 1.0. Python 3.9+, standard library."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
import xml.etree.ElementTree as ET


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8",
                                     delete=False) as stream:
        tmp = Path(stream.name)
        try:
            stream.write(dump(value) + "\n")
            stream.flush()
        except BaseException:
            stream.close()
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def log(root, **event):
    with (root / "operations.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                     **event), ensure_ascii=False) + "\n")


def safe(root, name):
    """Accept a portable relative path without crossing a link."""
    if not isinstance(name, str) or not name or "\\" in name or PureWindowsPath(name).drive:
        raise ValueError(f"invalid relative path: {name!r}")
    parts = name.split("/")
    if any(p in {"", ".", ".."} or ":" in p for p in parts):
        raise ValueError(f"invalid component in {name!r}")
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError(f"linked path: {name}")
    return current


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(root, excluded=None):
    if not root.is_dir():
        raise ValueError(f"source directory unavailable: {root}")
    rows, directories = [], []

    def visit(p):
        name = p.relative_to(root).as_posix()
        row = {"source": name}
        if excluded and name in excluded:
            rows.append(dict(row, status="excluded", reason=excluded[name]))
            return
        try:
            s = p.lstat()
            row.update(mode=stat.filemode(s.st_mode), mtime_ns=s.st_mtime_ns)
            if stat.S_ISLNK(s.st_mode) or (hasattr(p, "is_junction") and p.is_junction()):
                rows.append(dict(row, status="skipped_link"))
            elif stat.S_ISDIR(s.st_mode):
                directories.append(row)
                entries = sorted(p.iterdir(), key=lambda e: e.name)
                for entry in entries:
                    visit(entry)
            elif stat.S_ISREG(s.st_mode):
                rows.append(dict(row, bytes=s.st_size, sha256=digest(p), status="read"))
            else:
                rows.append(dict(row, status="skipped_special"))
        except (OSError, RecursionError) as exc:
            rows.append(dict(row, status="read_failed", error=str(exc)))

    visit(root)
    return {"directories": directories, "entries": rows}


def transfer(source, target, expected):
    """Publish a verified copy. Caller handles any existing destination."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        tmp = Path(stream.name)
    try:
        shutil.copyfile(source, tmp)
        if digest(tmp) != expected:
            raise ValueError("copy digest mismatch; input changed or recovery source differs")
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


TEXT = {".txt", ".md", ".csv", ".tsv", ".json", ".jsonl", ".bib", ".ris",
        ".xml", ".html", ".htm", ".yaml", ".yml", ".tex", ".log", ".rst"}
TEXT_LIMIT = 8 * 1024 * 1024


def passages(path):
    ext = path.suffix.lower()
    if ext in TEXT:
        if path.stat().st_size > TEXT_LIMIT:
            return [], "text_above_8MiB; use a targeted reader"
        raw = path.read_bytes()
        encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        lines = raw.decode(encoding).splitlines()
        return [(f"L{i}", line) for i, line in enumerate(lines, 1) if line.strip()], "lines"
    if ext == ".docx":
        with zipfile.ZipFile(path) as archive:
            main = archive.getinfo("word/document.xml")
            if main.file_size > TEXT_LIMIT:
                return [], "document XML above 8MiB; extract selected sections"
            doc = ET.fromstring(archive.read(main))
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs = [(f"body/para{i}", "".join(t.text or "" for t in p.iter(ns + "t")))
                      for i, p in enumerate(doc.iter(ns + "p"), 1)]
        return [(loc, s) for loc, s in paragraphs if s.strip()], "docx_body"
    if ext == ".pdf" and shutil.which("pdftotext"):
        with tempfile.TemporaryFile() as target:
            run = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"],
                                 stdout=target, stderr=subprocess.PIPE, timeout=45)
            if run.returncode:
                raise ValueError("pdftotext: " + run.stderr.decode(errors="replace")[:180])
            if target.tell() > TEXT_LIMIT:
                return [], "PDF text above 8MiB; extract selected pages"
            target.seek(0)
            pages = target.read().decode("utf-8-sig").split("\f")
        return [(f"p{i}", page) for i, page in enumerate(pages, 1) if page.strip()], "pdf_pages"
    return [], "metadata_only; supply targeted extraction if content is required"


def load_plan(path):
    plan = read(path)
    rows = plan.get("files", {})
    if not isinstance(rows, dict):
        raise ValueError("plan.files must map source-relative paths to rules")
    for name, rule in rows.items():
        if not isinstance(rule, dict):
            raise ValueError(f"invalid rule for {name}")
        if "skip" in rule and not isinstance(rule["skip"], str):
            raise ValueError(f"invalid skip reason for {name}")
        for key, field in rule.get("metadata", {}).items():
            if not isinstance(field, dict) or "value" not in field or not field.get("evidence"):
                raise ValueError(f"{name} field {key} needs value and evidence")
    return plan


def ingest(source, root, plan, excluded):
    if source == root or source in root.parents or root in source.parents:
        raise ValueError("choose disjoint source and library paths")
    rules = plan.get("files", {})
    excluded.update({n: r["skip"] for n, r in rules.items() if r.get("skip")})
    snapshot = scan(source, excluded)
    store = safe(root, "files")
    root.mkdir(parents=True, exist_ok=True)
    for internal in ["operations.jsonl", "catalog.json", "index.json", "plan.json"]:
        safe(root, internal)
    rows = snapshot["entries"]
    present = {r["source"] for r in rows}
    rows += [dict(source=n, status="missing") for n in sorted(rules.keys() - present)]
    groups, events = {}, []
    for row in rows:
        name = row["source"]
        rule = rules.get(name, {})
        row["metadata"] = rule.get("metadata", {})
        if "id" in rule:
            row["id"] = rule["id"]
        recovery = rule.get("restore_from")
        if row["status"] in {"missing", "read_failed", "read"} and recovery:
            row["original_status"] = row["status"]
            row["original_sha256"] = row.get("sha256")
            expected = rule.get("expected_sha256")
            if not expected or not rule.get("recovery_evidence"):
                row.update(status="failed", error="recovery needs expected_sha256 and recovery_evidence")
            elif row.get("sha256") != expected:
                try:
                    if any(recovery == n or recovery.startswith(n + "/") for n in excluded):
                        raise ValueError("backup is in an excluded scope")
                    backup = safe(source, recovery)
                    if digest(backup) != expected:
                        raise ValueError("candidate backup differs from expected checksum")
                    row.update(status="read", sha256=expected, bytes=backup.stat().st_size,
                               recovered_from=recovery, recovery_evidence=rule["recovery_evidence"])
                except (OSError, ValueError) as exc:
                    row.update(status="failed", error=str(exc))
        if row["status"] == "read":
            try:
                if rule.get("skip"):
                    row.update(status="excluded", reason=rule["skip"])
                else:
                    sha = row["sha256"]
                    if rule.get("expected_sha256", sha) != sha:
                        raise ValueError("input digest disagrees with supplied inventory")
                    dest = rule.get("dest", name)
                    target = safe(store, dest)
                    if target.exists() and digest(target) != sha:
                        preferred = dest
                        target = target.with_name(target.stem + "~" + sha[:12] + target.suffix)
                        dest = target.relative_to(store).as_posix()
                        target = safe(store, dest)
                        row["collision"] = {"requested": preferred, "retained_as": dest}
                    existing = target.exists()
                    if existing and digest(target) != sha:
                        raise ValueError("alternate destination also occupied by different bytes")
                    if not existing:
                        transfer(safe(source, row.get("recovered_from", name)), target, sha)
                    row.update(status="verified_existing" if existing else "copied", dest=dest)
                    if "recovered_from" not in row:
                        groups.setdefault(sha, []).append(name)
            except (OSError, ValueError) as exc:
                row.update(status="failed", error=str(exc))
        log(root, op="ingest", **{k: v for k, v in row.items() if k != "metadata"})

    by_source = {r["source"]: r for r in rows}
    for relation in plan.get("relations", []):
        a = by_source.get(relation.get("from"), {})
        b = by_source.get(relation.get("to"), {})
        edge = dict(relation)
        if (not a.get("dest") or not b.get("dest") or not edge.get("evidence")
                or not edge.get("kind")):
            edge["status"] = "unresolved"
        else:
            edge.update(status="documented", same_bytes=a["sha256"] == b["sha256"],
                        from_sha256=a["sha256"], to_sha256=b["sha256"],
                        size_delta=b["bytes"]-a["bytes"])
            try:
                if all(Path(r["dest"]).suffix.lower() in TEXT and r["bytes"] < 100000
                       for r in [a, b]) and not edge["same_bytes"]:
                    lines = [safe(store, r["dest"]).read_text(encoding="utf-8-sig").splitlines()
                             for r in [a, b]]
                    diff = list(difflib.unified_diff(*lines, n=1, lineterm=""))
                    edge.update(diff_excerpt=diff[:30], diff_truncated=len(diff) > 30)
            except (OSError, UnicodeError) as exc:
                edge["diff_error"] = str(exc)
        events.append(edge)
    catalog = dict(directories=snapshot["directories"], entries=rows, relations=events,
                   exact_duplicates={k: v for k, v in groups.items() if len(v) > 1})
    save(root / "catalog.json", catalog)
    save(root / "plan.json", plan)
    return catalog


def build_index(root):
    catalog = read(safe(root, "catalog.json"))
    records = []
    for row in catalog["entries"]:
        if "dest" not in row:
            continue
        record = dict(source=row["source"], dest=row["dest"], sha256=row["sha256"],
                      id=row.get("id", ""), passages=[])
        try:
            target = safe(safe(root, "files"), row["dest"])
            if digest(target) != row["sha256"]:
                raise ValueError("stored digest mismatch")
            contents, mode = passages(target)
            if not contents and mode in {"lines", "pdf_pages"}:
                mode += "_empty"
            record.update(mode=mode, passages=contents)
            record["metadata"] = row["metadata"]
        except (OSError, ValueError, subprocess.TimeoutExpired, zipfile.BadZipFile, KeyError,
                ET.ParseError, RuntimeError) as exc:
            record.update(mode="index_failed", error=str(exc))
        records.append(record)
    save(safe(root, "index.json"), records)
    log(root, op="index", rows=len(records), failed=sum(r["mode"]=="index_failed" for r in records))
    return records


def search(root, query):
    if not query or not query.strip():
        raise ValueError("supply a non-empty term or exact phrase")
    records = read(safe(root, "index.json"))
    hits = []
    for record in records:
        if record["mode"] == "index_failed":
            continue
        values = [("source", record["source"]), ("id", record["id"]), ("dest", record["dest"])]
        for k, v in record["metadata"].items():
            values.append(("metadata." + k + " @ " + str(v["evidence"]), str(v["value"])))
        for where, value in [*values, *record["passages"]]:
            value = str(value)
            p = value.casefold().find(query.casefold())
            if p >= 0:
                hits.append(dict(source=record["source"], dest=record["dest"], id=record["id"],
                                 sha256=record["sha256"], locator=where,
                                 excerpt=value[max(0, p-70):p+len(query)+110]))
    return dict(query=query, match="literal case-insensitive", hits=hits, hit_count=len(hits),
                coverage=[dict(source=r["source"], mode=r["mode"]) for r in records])


def verify(root, recovery=None):
    catalog = read(safe(root, "catalog.json"))
    store = safe(root, "files")
    results = []
    for row in catalog["entries"]:
        if "dest" not in row:
            continue
        item = {"source": row["source"], "dest": row["dest"], "expected": row["sha256"]}
        try:
            target = safe(store, row["dest"])
            actual = digest(target) if target.exists() else None
            item.update(before=actual, status="verified" if actual == item["expected"] else
                        ("missing" if actual is None else "mismatch"))
            if recovery and actual != item["expected"]:
                candidates = [row.get("recovered_from", row["source"]), row["source"],
                              *catalog["exact_duplicates"].get(item["expected"], [])]
                chosen = None
                for name in dict.fromkeys(candidates):
                    try:
                        src = safe(recovery, name)
                        if src.is_file() and digest(src) == item["expected"]:
                            chosen = src
                            break
                    except (OSError, ValueError):
                        continue
                if chosen is None:
                    raise ValueError("no readable source or source alias matches expected digest")
                if actual is not None:
                    saved = safe(root, "quarantine/" + actual)
                    if saved.exists() and digest(saved) != actual:
                        raise ValueError("quarantine conflict")
                    if not saved.exists():
                        transfer(target, saved, actual)
                    item["quarantine"] = saved.relative_to(root).as_posix()
                transfer(chosen, target, item["expected"])
                item.update(status="restored", recovery_source=chosen.relative_to(recovery).as_posix(),
                            after=digest(target))
        except (OSError, ValueError) as exc:
            item.update(status="failed", error=str(exc))
        results.append(item)
        if recovery:
            log(root, op="recover", **item)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for name, fields in {"scan": ["source"], "ingest": ["source", "library", "plan"],
                         "index": ["library"], "search": ["library", "query"],
                         "verify": ["library"], "recover": ["library", "source"]}.items():
        sub = subs.add_parser(name)
        for field in fields:
            sub.add_argument(field, type=str if field == "query" else Path)
        if name in {"ingest", "scan"}:
            sub.add_argument("--exclude", action="append", default=[],
                             help="skip exact source-relative file or directory before opening it")
        sub.add_argument("--receipt", type=Path, help="write the full output to this JSON file")
    args = parser.parse_args()
    root = args.library.resolve() if hasattr(args, "library") else None
    partial = False
    excluded = {n: "excluded by caller" for n in getattr(args, "exclude", [])}
    if args.command == "scan":
        result = scan(args.source.resolve(), excluded)
        partial = any(r["status"] not in {"read", "excluded"} for r in result["entries"])
    elif args.command == "ingest":
        result = ingest(args.source.resolve(), root, load_plan(args.plan), excluded)
        partial = (any(r["status"] not in {"verified_existing", "copied", "excluded"}
                       for r in result["entries"]) or any(r["status"] == "unresolved" for r in result["relations"]))
    elif args.command == "index":
        result = build_index(root)
        partial = any(r["mode"] == "index_failed" for r in result)
        result = [dict(source=r["source"], mode=r["mode"], count=len(r["passages"]),
                       error=r.get("error")) for r in result]
    elif args.command == "search":
        result = search(root, args.query)
    else:
        result = verify(root, args.source.resolve() if args.command == "recover" else None)
        partial = any(r["status"] not in {"verified", "restored"} for r in result)
    if args.receipt:
        save(args.receipt, result)
        print(dump(dict(receipt=str(args.receipt), partial=partial)))
    else:
        print(dump(result))
    return 2 if partial else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as err:
        print(f"library operation failed: {err}", file=sys.stderr)
        sys.exit(1)
