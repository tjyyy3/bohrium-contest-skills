"""Read-only passage and native annotation adapters. Offsets are Unicode code points."""
import csv
import hashlib
import json
import re
import subprocess
import shutil
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET


def unit(locator, text, **metadata):
    return {"locator": locator, "text": text, **metadata}


def mark(kind, locator, text, start, end, **metadata):
    return {"kind": kind, "locator": locator, "quote": text[start:end],
            "start": start, "end": end, **metadata}


def textfile(path):
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    return data.decode("utf-8-sig")


def lines(text):
    return [unit(f"line:{n}", line) for n, line in enumerate(text.splitlines(), 1) if line.strip()]


class Clipping(HTMLParser):
    blocks = {"p", "li", "h1", "h2", "h3", "h4", "blockquote", "td", "th", "pre", "div", "section", "article", "body"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.units, self.marks, self.issues, self.open_marks = [], [], [], []
        self.raw, self.anchor, self.ignore = "", "", 0

    def flush(self):
        if self.open_marks:
            self.issues.append("HTML annotation crosses block boundary; inspect DOM or rendered source")
            self.open_marks.clear()
        if self.raw.strip():
            self.units.append(unit(f"block:{len(self.units)+1}", self.raw, html_id=self.anchor))
        self.raw, self.anchor = "", ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "head"}:
            self.ignore += 1
        if self.ignore:
            return
        if tag in self.blocks:
            self.flush()
            self.anchor = attrs.get("id", "")
        if tag == "br":
            self.raw += "\n"
        if tag in {"u", "mark"} or "data-annotation-type" in attrs:
            self.open_marks.append((tag, len(self.raw), attrs))

    def handle_endtag(self, tag):
        if tag in {"script", "style", "head"}:
            self.ignore = max(0, self.ignore-1)
            return
        if self.ignore:
            return
        for i in range(len(self.open_marks)-1, -1, -1):
            name, start, attrs = self.open_marks[i]
            if name == tag:
                self.open_marks.pop(i)
                if self.raw[start:].strip():
                    self.marks.append(mark(attrs.get("data-annotation-type", {"u":"underline","mark":"highlight"}.get(tag,tag)),
                        f"block:{len(self.units)+1}", self.raw, start, len(self.raw),
                        attributes=attrs, comment=attrs.get("data-note", ""), color=attrs.get("data-color", "")))
                break
        if tag in self.blocks:
            self.flush()

    def handle_data(self, data):
        if not self.ignore:
            self.raw += data


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def word(path):
    units, marks, issues, active = [], [], [], {}
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        comments = {}
        if "word/comments.xml" in z.namelist():
            for c in ET.fromstring(z.read("word/comments.xml")).iter(W+"comment"):
                comments[c.get(W+"id")] = {
                    "comment": "".join(t.text or "" for t in c.iter(W+"t")),
                    "author": c.get(W+"author", ""), "date": c.get(W+"date", "")}
        for pno, p in enumerate(root.iter(W+"p"), 1):
            loc, text, pending = f"paragraph:{pno}", "", []
            active = {key: 0 for key in active}
            for e in p.iter():
                if e.tag == W+"commentRangeStart":
                    active[e.get(W+"id")] = len(text)
                elif e.tag == W+"commentRangeEnd":
                    key = e.get(W+"id")
                    if key in active:
                        pending.append(("comment", active.pop(key), len(text), {"native_id": key, **comments.get(key,{})}))
                    else:
                        issues.append(f"comment {key}: unmatched end at {loc}")
                elif e.tag == W+"r":
                    start = len(text)
                    text += "".join((s.text or "") if s.tag == W+"t" else "\t" if s.tag == W+"tab" else "\n"
                                    for s in e if s.tag in {W+"t", W+"tab", W+"br", W+"cr"})
                    for style in ("highlight", "u"):
                        el = e.find(W+"rPr/"+W+style)
                        if el is not None and el.get(W+"val") not in {"none", "0", "false"}:
                            pending.append(("highlight" if style=="highlight" else "underline", start, len(text),
                                            {"style": dict(el.attrib), "color": el.get(W+("val" if style=="highlight" else "color"), "")}))
            pending.extend(("comment", start, len(text), {"native_id": key, **comments.get(key,{})}) for key,start in active.items())
            if text:
                units.append(unit(loc, text))
            for kind, start, end, meta in pending:
                if text[start:end].strip():
                    marks.append(mark(kind, loc, text, start, end, **meta))
                elif kind == "comment":
                    issues.append(f"comment {meta['native_id']}: empty range at {loc}; inspect source")
    if active:
        issues.append("Unclosed Word comment range; verify affected comments")
    anchored = {m.get("native_id") for m in marks if m["kind"]=="comment"}
    issues.extend(f"unanchored Word comment {k}: {v['comment']}" for k,v in comments.items() if k not in anchored)
    return units, marks, issues


def inside_quad(quad, x, y):
    vertices = [quad.ul, quad.ur, quad.lr, quad.ll]
    signs = [(b.x-a.x)*(y-a.y)-(b.y-a.y)*(x-a.x)
             for a,b in zip(vertices, vertices[1:]+vertices[:1])]
    return max(signs) > 0 and min(signs) >= -1e-6 or min(signs) < 0 and max(signs) <= 1e-6


def pdf(path):
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            if not shutil.which("pdftotext"):
                raise ValueError("PDF adapter missing; use installed PDF renderer or authorized local parser")
            p = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"],
                               capture_output=True, timeout=90, check=True)
            pages = p.stdout.decode("utf-8").split("\f")
            return [unit(f"page:{n}/line:{i}", s) for n,page in enumerate(pages,1)
                    for i,s in enumerate(page.splitlines(),1) if s.strip()], [], [
                "pdftotext layout fallback: native annotations not inspected; inspect rendered PDF or installed annotation reader"]
    units, marks, issues = [], [], []
    with fitz.open(path) as doc:
        if doc.needs_pass:
            raise ValueError("encrypted PDF: obtain authorized decrypted copy")
        for pg in doc:
            page = pg.number+1
            words = pg.get_text("words", sort=False)
            for b in pg.get_text("blocks", sort=False):
                if b[6]==0 and b[4].strip():
                    units.append(unit(f"page:{page}/block:{b[5]}", b[4], page=page, bbox=list(b[:4])))
            if not words:
                issues.append(f"page {page}: no words; inspect rendered crop and OCR separately")
            for a in pg.annots() or ():
                kind = a.type[1]
                loc = f"page:{page}/annotation:{a.xref}"
                info = a.info or {}
                meta = {"page":page,"xref":a.xref,"bbox":list(a.rect),"color":a.colors,
                        "comment":info.get("content",""),"author":info.get("title",""),
                        "native_id":info.get("id",""),"date":info.get("modDate","") or info.get("creationDate","")}
                quads = a.vertices or [] if kind in {"Highlight","Underline","StrikeOut","Squiggly"} else []
                chunks, boxes, selected = [], [], set()
                for i in range(0, len(quads)-3, 4):
                    quad = fitz.Quad(quads[i:i+4])
                    boxes.append([list(pt) for pt in quad])
                    hit=[]
                    for w in words:
                        key = tuple(w[5:8])
                        if key not in selected and inside_quad(quad, (w[0]+w[2])/2, (w[1]+w[3])/2):
                            selected.add(key)
                            hit.append(w)
                    chunks.extend(w[4] for w in sorted(hit,key=lambda w:w[5:8]))
                quote = " ".join(chunks)
                meta["quads"] = boxes
                units.append(unit(loc, quote, **meta))
                marks.append(mark(kind, loc, quote, 0, len(quote), **meta,
                                  anchor_status="geometry_word_centres" if quote else "position_only"))
                if not quote:
                    issues.append(f"{loc}: position only; inspect rendered annotation; do not attribute adjacent text")
    return units, marks, issues


def extract(path):
    ext = path.suffix.lower()
    if ext == ".pdf":
        return pdf(path)
    if ext == ".docx":
        return word(path)
    if ext in {".html",".htm",".xhtml"}:
        html = Clipping()
        html.feed(textfile(path))
        html.close()
        html.flush()
        return html.units, html.marks, html.issues
    if ext in {".json",".jsonl",".ndjson"}:
        units = []
        def visit(value, pointer):
            if isinstance(value, (dict,list)):
                for key,item in (value.items() if isinstance(value,dict) else enumerate(value)):
                    visit(item,pointer+"/"+str(key).replace("~","~0").replace("/","~1"))
            elif value is not None:
                units.append(unit(pointer, value if isinstance(value,str) else json.dumps(value)))
        raw = textfile(path)
        if ext==".json":
            visit(json.loads(raw),"json:")
        else:
            for i,s in enumerate(raw.splitlines(),1):
                if s.strip():
                    visit(json.loads(s),f"line:{i}/json:")
        return units, [], []
    if ext in {".csv",".tsv"}:
        import io
        rows = csv.reader(io.StringIO(textfile(path), newline=""), delimiter="," if ext==".csv" else "\t")
        return [unit(f"row:{r}/col:{c}", v) for r,row in enumerate(rows,1) for c,v in enumerate(row,1) if v], [], []
    if ext in {".txt",".md",".rst",".bib",".ris",".yaml",".yml",".org",".log",".tex"}:
        units = lines(textfile(path))
        marks = []
        if ext==".md":
            for p in units:
                for m in re.finditer(r"(?<![=])==([^=\n]+?)==(?![=])", p["text"]):
                    marks.append(mark("highlight",p["locator"],p["text"],m.start(1),m.end(1),syntax="==...=="))
        return units, marks, []
    raise ValueError(f"unsupported format {ext or '(no extension)'}; use an available case-specific reader and retain the original")


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest() if hasattr(hashlib,"file_digest") else _hash_chunks(f)


def _hash_chunks(f):
    h = hashlib.sha256()
    for chunk in iter(lambda:f.read(1048576),b""):
        h.update(chunk)
    return h.hexdigest()
