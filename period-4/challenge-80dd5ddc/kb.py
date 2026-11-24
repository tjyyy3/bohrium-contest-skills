"""Offline evidence index for read-authorized research libraries. Python 3.9+."""
import argparse
import csv
import hashlib
import io
import json
import math
import posixpath
import re
import shutil
import stat
import subprocess
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".writing")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def clean(value):
    return " ".join(value.split())


def relname(value):
    p = PurePosixPath(value)
    if not p.parts or p.is_absolute() or ".." in p.parts or "\\" in value or ":" in value:
        raise ValueError(f"expected relative POSIX path: {value!r}")
    return p.as_posix()


def within(path, prefix):
    return path == prefix or path.startswith(prefix + "/")


def located(root, relative):
    current = root
    for part in PurePosixPath(relname(relative)).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("symbolic link in path")
    return current


class HtmlBlocks(HTMLParser):
    """Stable source line and block ordinal; omit scripts, styles and templates."""
    blocks = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "title", "br", "section"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.rows, self.hidden, self.start = [], [], 0, 1

    def flush(self):
        text = clean("".join(self.parts))
        if text:
            self.rows.append((f"html:L{self.start}:block{len(self.rows)+1}", text))
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.hidden += 1
        if tag in self.blocks:
            self.flush()

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in self.blocks:
            self.flush()
        if tag in {"td", "th"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden and data.strip():
            if not self.parts:
                self.start = self.getpos()[0]
            self.parts.append(data)
        elif not self.hidden and self.parts:
            self.parts.append(" ")


def parttext(node):
    return "".join(e.text or "" for e in node.iter() if e.tag.rsplit("}", 1)[-1] == "t")


def pdf_pages(data):
    if shutil.which("pdftotext"):
        proc = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", "-", "-"],
                              input=data, capture_output=True, timeout=90)
        if proc.returncode:
            raise ValueError(proc.stderr.decode("utf-8", "replace").strip()[:500])
        pages = proc.stdout.decode("utf-8").split("\f")
        return pages[:-1] if pages and pages[-1] == "" else pages
    for name in ("pypdf", "PyPDF2"):
        try:
            module = __import__(name)
        except ImportError:
            continue
        return [(page.extract_text() or "") for page in module.PdfReader(io.BytesIO(data)).pages]
    raise ImportError("PDF parser unavailable: supply pdftotext or pypdf")


TEXT = {".txt", ".md", ".rst", ".log", ".bib", ".ris", ".yaml", ".yml", ".tex", ".xml", ".jsonl", ".ndjson"}


def extract(path, data):
    suffix = path.suffix.lower()
    rows, gaps = [], []
    if suffix == ".docx":
        with zipfile.ZipFile(io.BytesIO(data)) as doc:
            body = ET.fromstring(doc.read("word/document.xml")).find("{*}body")
            for i, node in enumerate(body, 1):
                if node.tag.endswith("}p"):
                    rows.append((f"body:{i}/p", parttext(node)))
                elif node.tag.endswith("}tbl"):
                    for r, tr in enumerate(node.findall("{*}tr"), 1):
                        for c, tc in enumerate(tr.findall("{*}tc"), 1):
                            for j, para in enumerate(tc.findall("{*}p"), 1):
                                rows.append((f"body:{i}/table:r{r}c{c}/p:{j}", parttext(para)))
    elif suffix == ".xlsx":
        with zipfile.ZipFile(io.BytesIO(data)) as doc:
            strings = []
            if "xl/sharedStrings.xml" in doc.namelist():
                strings = [parttext(si) for si in ET.fromstring(doc.read("xl/sharedStrings.xml"))]
            rels = {e.get("Id"): e.get("Target") for e in ET.fromstring(doc.read("xl/_rels/workbook.xml.rels"))
                    if e.get("TargetMode") != "External"}
            for sheet in ET.fromstring(doc.read("xl/workbook.xml")).findall(".//{*}sheet"):
                rid = next(v for k, v in sheet.attrib.items() if k.endswith("}id"))
                name = rels[rid]
                member = name.lstrip("/") if name.startswith("/") else posixpath.normpath(posixpath.join("xl", name))
                for cell in ET.fromstring(doc.read(member)).findall(".//{*}sheetData/{*}row/{*}c"):
                    locator = f"sheet:{sheet.get('name')}/cell:{cell.get('r')}"
                    value = cell.findtext("{*}v") or ""
                    if cell.get("t") == "s":
                        value = strings[int(value)]
                    elif cell.get("t") == "inlineStr":
                        value = parttext(cell)
                    formula = cell.findtext("{*}f")
                    if formula:
                        rows.append((locator + "/formula", "=" + formula))
                        if not value:
                            gaps.append(locator + " formula has no cached value")
                    rows.append((locator, value))
    elif suffix == ".pdf":
        for p, page in enumerate(pdf_pages(data), 1):
            if not page.strip():
                gaps.append(f"page:{p} no extracted text; render and inspect or OCR if authorized")
            for b, block in enumerate(re.split(r"\n\s*\n", page), 1):
                rows.append((f"page:{p}/block:{b}", block))
    elif suffix in TEXT | {".html", ".htm", ".json", ".csv", ".tsv"}:
        content = data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
        if "\0" in content:
            raise ValueError("NUL in text; inspect encoding")
        if suffix in {".html", ".htm"}:
            html = HtmlBlocks()
            html.feed(content)
            html.close()
            html.flush()
            rows = html.rows
        elif suffix in {".csv", ".tsv"}:
            reader = csv.reader(io.StringIO(content, newline=""), delimiter="," if suffix == ".csv" else "\t")
            header = next(reader, [])
            rows.extend((f"record:1/column:{j}", h) for j, h in enumerate(header, 1))
            for i, record in enumerate(reader, 2):
                rows.extend((f"record:{i}/column:{j+1}({header[j] if j < len(header) else ''})", v)
                            for j, v in enumerate(record))
        elif suffix == ".json":
            def flatten(obj, pointer):
                if isinstance(obj, (list, dict)):
                    for k, v in (obj.items() if isinstance(obj, dict) else enumerate(obj)):
                        flatten(v, pointer + "/" + str(k).replace("~", "~0").replace("/", "~1"))
                else:
                    rows.append(("json:" + pointer, obj if isinstance(obj, str) else json.dumps(obj)))
            flatten(json.loads(content), "")
        else:
            rows = [(f"L{i}", line) for i, line in enumerate(content.splitlines(), 1)]
    else:
        raise NotImplementedError(f"no text reader for {suffix or 'extensionless file'}")
    return [(loc, clean(t)) for loc, t in rows if clean(t)], gaps


def index(args):
    root = Path(args.root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("root must be a library directory")
    if Path(args.out).resolve().is_relative_to(root):
        raise ValueError("choose an index location outside the library")
    scope = load(args.scope) if args.scope else {}
    if not isinstance(scope, dict) or set(scope) - {"allow", "deny"}:
        raise ValueError("scope supports allow and deny arrays of paths")
    for items in scope.values():
        if not isinstance(items, list) or not all(isinstance(s, str) for s in items):
            raise ValueError("scope values must be arrays of relative paths")
    allow = [relname(v) for v in scope["allow"]] if "allow" in scope else None
    deny = [relname(v) for v in scope.get("deny", [])]
    files, directories, notices, chunks, by_hash = [], [], [], {}, {}

    def visit(folder):
        try:
            children = sorted(folder.iterdir(), key=lambda e: e.name)
        except OSError as err:
            notices.append({"path": folder.relative_to(root).as_posix(), "status": "listing_error", "detail": str(err)})
            return
        for path in children:
            rel = path.relative_to(root).as_posix()
            row = {"path": rel, "parent": path.parent.relative_to(root).as_posix(), "type": path.suffix.lower()}
            if any(within(rel, p) for p in deny) or (allow is not None and
                    not any(within(rel, p) or within(p, rel) for p in allow)):
                notices.append({"path": rel, "status": "excluded_by_scope"})
                continue
            try:
                mode = path.lstat().st_mode
                row["mode"] = stat.filemode(mode)
                if stat.S_ISLNK(mode):
                    notices.append({"path": rel, "status": "symlink_skipped"})
                    continue
                if stat.S_ISDIR(mode):
                    directories.append(rel)
                    visit(path)
                    continue
                if not stat.S_ISREG(mode):
                    notices.append({"path": rel, "status": "nonregular_skipped"})
                    continue
                if allow is not None and not any(within(rel, p) for p in allow):
                    continue
                data = path.read_bytes()
                digest = sha(data)
                row.update(bytes=len(data), sha256=digest, access="read_succeeded")
                row["same_bytes_as"] = by_hash.get(digest)
                by_hash.setdefault(digest, rel)
                # Same bytes under a different suffix may require a different parser.
                key = digest + ":" + row["type"]
                if key not in chunks:
                    blocks, issues = extract(path, data)
                    chunks[key] = {"blocks": blocks, "gaps": issues}
                entry = chunks[key]
                row.update(chunk_key=key, blocks=len(entry["blocks"]), gaps=entry["gaps"],
                           status=("partial" if entry["gaps"] else "indexed") if entry["blocks"] else "no_text")
            except Exception as err:
                row["status"] = ("permission_denied" if isinstance(err, PermissionError) else
                                 "unsupported" if isinstance(err, (NotImplementedError, ImportError)) else "read_or_parse_error")
                row["detail"] = f"{type(err).__name__}: {err}"
            files.append(row)

    visit(root)
    known = {row["path"] for row in files + notices} | set(directories)
    for p in allow or []:
        if p not in known and not any(within(p, row["path"]) for row in notices):
            notices.append({"path": p, "status": "declared_path_unobserved"})
    save(args.out, {"format": 1, "scope": scope, "directories": directories, "files": files,
                    "notices": notices, "chunks": chunks})
    return {"files": len(files), "unique_byte_streams": len(by_hash), "notices": len(notices),
            "states": dict(Counter(row["status"] for row in files))}


def tokens(text):
    norm = unicodedata.normalize("NFKC", text).casefold()
    words = re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)*|[\u3400-\u9fff]+", norm)
    keys = set()
    for word in words:
        if "\u3400" <= word[0] <= "\u9fff" and len(word) > 1:
            keys.update(word[i:i+2] for i in range(len(word) - 1))
        else:
            keys.add(word)
    return keys


def search(args):
    idx = load(args.index)
    q = tokens(args.query)
    available = defaultdict(list)
    for f in idx["files"]:
        if f.get("blocks") and (not args.path or any(within(f["path"], p) for p in args.path)):
            available[f["chunk_key"]].append(f["path"])
    hits, freq = [], Counter()
    total = 0
    for key, paths in available.items():
        for loc, text in idx["chunks"][key]["blocks"]:
            total += 1
            matched = q & tokens(text + " " + loc)
            if matched:
                hits.append((key, paths, loc, text, matched))
                freq.update(matched)
    ranked = []
    for key, paths, loc, text, matched in hits:
        score = sum(math.log(1 + total / freq[t]) for t in sorted(matched))
        start = 0
        if len(text) > 900:
            positions = [text.casefold().find(t) for t in matched]
            first = min((pos for pos in positions if pos >= 0), default=0)
            start = max(0, min(len(text) - 900, first - 170))
        ranked.append((score, {"path": paths[0], "aliases": paths[1:], "sha256": key.split(":")[0],
                               "locator": loc, "text": text[start:start+900], "excerpt_start": start,
                               "block_length": len(text), "matched": sorted(matched)}))
    ranked.sort(key=lambda h: (-h[0], h[1]["path"], h[1]["locator"]))
    return {"query": args.query, "path_filters": args.path, "files_scanned": sum(map(len, available.values())),
            "blocks_scanned": total, "matching_blocks": len(ranked), "hits": [h for _, h in ranked[:args.limit]]}


def verify(args):
    root = Path(args.root).resolve(strict=True)
    files = {f["path"]: f for f in load(args.index)["files"]}
    checks, cache = [], {}
    for c in load(args.citations):
        result = {"claim_id": c.get("claim_id"), "path": c.get("path"), "locator": c.get("locator")}
        try:
            rel = relname(c["path"])
            f = files.get(rel, {})
            if f.get("status") not in {"indexed", "partial"} or f.get("sha256") != c["sha256"]:
                raise ValueError("file/version outside indexed evidence")
            if rel not in cache:
                path = located(root, rel)
                data = path.read_bytes()
                if sha(data) != f["sha256"]:
                    raise ValueError("source bytes changed: reindex and reassess")
                cache[rel] = dict(extract(path, data)[0])
            block = cache[rel].get(c["locator"], "")
            if not isinstance(c["quote"], str) or not clean(c["quote"]) or clean(c["quote"]) not in block:
                raise ValueError("quote absent at cited locator")
            result["status"] = "verified"
        except Exception as err:
            result.update(status="failed", detail=str(err))
        checks.append(result)
    return {"checked": len(checks), "failed": sum(c["status"] == "failed" for c in checks), "checks": checks}


def restore(args):
    root = Path(args.root).resolve(strict=True)
    dest = Path(args.dest).resolve()
    if dest.is_relative_to(root) or root.is_relative_to(dest):
        raise ValueError("destination and inputs must be separate trees")
    files = {f["path"]: f for f in load(args.index)["files"]}
    changes = []
    for entry in load(args.plan):
        rec = {k: entry.get(k) for k in ("source", "target", "reason")}
        try:
            if not entry.get("reason"):
                raise ValueError("record the workorder justification")
            row = files.get(entry["source"], {})
            if not row.get("sha256") or row.get("access") != "read_succeeded":
                raise ValueError("source outside readable inventory")
            data = located(root, entry["source"]).read_bytes()
            if sha(data) != row["sha256"] or entry["sha256"] != row["sha256"]:
                raise ValueError("source hash changed or chosen version mismatches plan")
            target = located(dest, entry["target"])
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if sha(target.read_bytes()) != row["sha256"]:
                    raise ValueError("destination conflict; compare and choose an authorized separate path")
                state = "already_present"
            else:
                with target.open("xb") as out:
                    out.write(data)
                state = "copied"
            if sha(target.read_bytes()) != row["sha256"]:
                raise ValueError("destination readback mismatch; inspect incomplete copy")
            rec.update(status=state, sha256=row["sha256"])
        except Exception as err:
            rec.update(status="failed", detail=str(err))
        changes.append(rec)
    return {"changes": changes, "failed": sum(c["status"] == "failed" for c in changes)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("index")
    p.add_argument("root")
    p.add_argument("out")
    p.add_argument("--scope")
    p = commands.add_parser("search")
    p.add_argument("index")
    p.add_argument("query")
    p.add_argument("--path", action="append", default=[])
    p.add_argument("--limit", type=int, default=15)
    p = commands.add_parser("verify")
    for arg in ("root", "index", "citations"):
        p.add_argument(arg)
    p = commands.add_parser("restore")
    for arg in ("root", "index", "plan", "dest"):
        p.add_argument(arg)
    for name in ("search", "verify", "restore"):
        commands.choices[name].add_argument("--out")
    args = parser.parse_args()
    if args.command == "search" and args.limit < 1:
        parser.error("--limit must be positive")
    obj = {"index": index, "search": search, "verify": verify, "restore": restore}[args.command](args)
    if args.command != "index" and args.out:
        save(args.out, obj)
        print(json.dumps({k: v for k, v in obj.items() if k not in {"hits", "changes", "checks"}}, ensure_ascii=False))
    else:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    return 1 if obj.get("failed") else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError, KeyError) as error:
        sys.exit(f"{type(error).__name__}: {error}")
