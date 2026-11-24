"""Original passage readers. All public locators are one-based source coordinates."""
import csv
import io
import posixpath
import re
import shutil
import subprocess
import zipfile
from html.parser import HTMLParser
from xml.etree import ElementTree as ET


def block(locator, text, section=""):
    return {"locator": locator, "section": section, "text": text.strip()}


def decode(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    return data.decode("utf-8-sig")


def lines(text):
    headings = {}
    pending = []
    start = 1
    for n, line in enumerate(text.splitlines() + [""], 1):
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if (heading or not line.strip() or len(pending) >= 6) and pending:
            yield block(f"L{start}-L{n-1}", "\n".join(pending), " / ".join(headings.values()))
            pending = []
        if heading:
            depth = len(heading[1])
            headings = {k: v for k, v in headings.items() if k < depth}
            headings[depth] = heading[2]
        if line.strip():
            if not pending:
                start = n
            pending.append(line)


class HTMLBlocks(HTMLParser):
    tags = {"p", "li", "tr", "figcaption", "caption", "pre", "div", "section", "article", "body", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records, self.buf, self.headings = [], [], {}
        self.heading = self.hidden = 0

    def flush(self):
        value = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        self.buf = []
        if value:
            if self.heading:
                self.headings = {k: v for k, v in self.headings.items() if k < self.heading}
                self.headings[self.heading] = value
            self.records.append(block(f"HTML:block={len(self.records)+1}", value, " / ".join(self.headings.values())))

    def handle_starttag(self, tag, attrs):
        if tag in {"style", "script", "head"}:
            self.hidden += 1
        if self.hidden:
            return
        if tag in self.tags or re.fullmatch("h[1-6]", tag):
            self.flush()
            self.heading = int(tag[1]) if re.fullmatch("h[1-6]", tag) else 0
        if tag in {"br", "td", "th"}:
            self.buf.append(" ")

    def handle_endtag(self, tag):
        if tag in {"style", "script", "head"}:
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden and (tag in self.tags or re.fullmatch("h[1-6]", tag)):
            self.flush()
            self.heading = 0

    def handle_data(self, data):
        if not self.hidden:
            self.buf.append(data)


def local(tag):
    return tag.rsplit("}", 1)[-1]


def text_runs(node):
    return "".join(e.text or "" for e in node.iter() if local(e.tag) == "t")


def office(path, ext):
    with zipfile.ZipFile(path) as z:
        def read(name):
            return ET.fromstring(z.read(name))
        if ext == "docx":
            headings = {}
            for i, p in enumerate(read("word/document.xml").iterfind(".//{*}p"), 1):
                style = p.find("./{*}pPr/{*}pStyle")
                value = text_runs(p)
                if style is not None:
                    match = re.search(r"(?:Heading|标题)\s*([1-9])", next(iter(style.attrib.values()), ""), re.I)
                    if match:
                        level = int(match[1])
                        headings = {k: v for k, v in headings.items() if k < level}
                        headings[level] = value
                yield block(f"Word:paragraph={i}", value, " / ".join(headings.values()))
            return
        main = "ppt/presentation.xml" if ext == "pptx" else "xl/workbook.xml"
        base = posixpath.dirname(main)
        rels = read(f"{base}/_rels/{posixpath.basename(main)}.rels")
        links = {r.get("Id"): posixpath.normpath(posixpath.join(base, r.get("Target"))).lstrip("/") for r in rels}
        doc = read(main)
        rid = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        if ext == "pptx":
            for slide_no, slide in enumerate(doc.iterfind(".//{*}sldId"), 1):
                tree = read(links[slide.get(rid)])
                for pno, paragraph in enumerate(tree.iterfind(".//{*}p"), 1):
                    yield block(f"Slide={slide_no}:paragraph={pno}", text_runs(paragraph))
            return
        strings = [text_runs(x) for x in read("xl/sharedStrings.xml")] if "xl/sharedStrings.xml" in z.namelist() else []
        for sheet in doc.iterfind(".//{*}sheet"):
            for row in read(links[sheet.get(rid)]).iterfind(".//{*}row"):
                cells = []
                for cell in row.findall("./{*}c"):
                    value = cell.findtext("./{*}v", "")
                    if cell.get("t") == "s":
                        value = strings[int(value)]
                    elif cell.get("t") == "inlineStr":
                        value = text_runs(cell)
                    formula = cell.findtext("./{*}f")
                    if formula and not value:
                        value = "=" + formula
                    if value:
                        cells.append(f"{cell.get('r')}={value}")
                if cells:
                    yield block(f"Sheet={sheet.get('name')}:row={row.get('r')}", " | ".join(cells), sheet.get("name"))


def pdf(path, issues):
    try:
        import fitz
    except ImportError:
        fitz = None
    if fitz is not None:
        with fitz.open(path) as doc:
            if doc.needs_pass:
                raise PermissionError("encrypted PDF; obtain an authorized readable copy")
            outline = {}
            for depth, title, target in doc.get_toc():
                outline.setdefault(target, []).append((depth, title))
            headings = {}
            for n, page in enumerate(doc, 1):
                words = [b for b in page.get_text("blocks", sort=True) if b[6] == 0 and b[4].strip()]
                if not words:
                    issues.append(f"physical page {n}: no extractable text; render and inspect or OCR")
                for i, b in enumerate(words, 1):
                    for depth, title in outline.get(n, []):
                        if " ".join(title.casefold().split()) == " ".join(b[4].casefold().split()):
                            headings = {k: v for k, v in headings.items() if k < depth}
                            headings[depth] = title
                    passage = block(f"PDF:page={n}:block={i}", b[4], " / ".join(headings.values()))
                    passage["bbox_points"] = list(b[:4])
                    label = page.get_label() if hasattr(page, "get_label") else ""
                    if label:
                        passage["pdf_page_label"] = label
                    yield passage
        return
    if not shutil.which("pdftotext"):
        raise RuntimeError("PDF reader missing: use installed PyMuPDF or Poppler pdftotext")
    run = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"], capture_output=True, timeout=90)
    if run.returncode:
        raise ValueError(run.stderr.decode("utf-8", "replace").strip())
    pages = run.stdout.decode("utf-8").split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    for n, page in enumerate(pages, 1):
        if not page.strip():
            issues.append(f"physical page {n}: no extractable text; render and inspect or OCR")
        for p in lines(page):
            p["locator"] = f"PDF:page={n}:" + p["locator"]
            yield p


def extract(path):
    ext = path.suffix.lower().lstrip(".")
    issues = []
    if ext == "pdf":
        records = pdf(path, issues)
    elif ext in {"docx", "pptx", "xlsx"}:
        records = office(path, ext)
    elif ext in {"html", "htm", "xhtml"}:
        parser = HTMLBlocks()
        parser.feed(decode(path.read_bytes()))
        parser.close()
        parser.flush()
        records = parser.records
    elif ext in {"csv", "tsv"}:
        rows = csv.reader(io.StringIO(decode(path.read_bytes())), delimiter="," if ext == "csv" else "\t")
        records = [block(f"record={n}", " | ".join(row)) for n, row in enumerate(rows, 1)]
    elif ext in {"txt", "md", "rst", "tex", "json", "jsonl", "bib", "ris", "yaml", "yml", "log", "xml"}:
        records = lines(decode(path.read_bytes()))
    else:
        raise NotImplementedError(f"unsupported .{ext}; inspect original with local authorized reader")
    return [r for r in records if r["text"]], issues
