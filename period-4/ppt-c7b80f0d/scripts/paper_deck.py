"""Local PDF evidence, template inventory and editable deck builder. See references/runbook.md."""
import argparse
import hashlib
import io
import json
import math
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from pathlib import Path

import fitz
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.dml import MSO_THEME_COLOR
from pptx.enum.text import MSO_ANCHOR
from pptx.util import Pt

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def compact(text):
    return "".join(text.split()).casefold()

def index(pdf, directory):
    dest = Path(directory)
    dest.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf) as doc:
        if doc.needs_pass:
            raise ValueError("PDF needs an authorized password or a readable copy.")
        pages = []
        for n, page in enumerate(doc, 1):
            blocks = [{"rect": [round(x, 2) for x in block[:4]], "text": block[4]}
                      for block in page.get_text("blocks", sort=True) if block[6] == 0]
            pages.append({"page": n, "label": page.get_label(), "rotation": page.rotation,
                          "unrotated_size_pt": [page.cropbox.width, page.cropbox.height], "blocks": blocks})
        save(dest / "pages.json", {"file": Path(pdf).name, "sha256": sha(pdf), "pages": pages})

def layouts(template, output):
    deck = Presentation(template)
    masters = []
    for master in deck.slide_masters:
        group = []
        for layout in master.slide_layouts:
            group.append({"name": layout.name, "slots": [
                {"idx": s.placeholder_format.idx, "name": s.name,
                 "rect_in": [round(getattr(s, k) / 914400, 3) for k in ("left","top","width","height")]}
                for s in layout.placeholders]})
        masters.append(group)
    save(output, {"slides": len(deck.slides), "masters": masters,
                  "canvas_in": [deck.slide_width/914400, deck.slide_height/914400]})

def crop_rect(page, values):
    rect = fitz.Rect(values)
    bounds = fitz.Rect(0, 0, page.cropbox.width, page.cropbox.height)
    if rect.is_empty or rect.is_infinite or not bounds.contains(rect):
        raise ValueError(f"Invalid crop {values} on {bounds}")
    return rect * page.rotation_matrix

def check_anchor(anchor, page):
    if not anchor["locator"].strip():
        raise ValueError("An evidence locator must identify the section/figure/table.")
    quote = anchor.get("quote", "")
    texts = [page.get_text(sort=order) for order in (False, True)]
    if "quote_rect" in anchor:
        crop_rect(page, anchor["quote_rect"])
        if "rect" in anchor and not fitz.Rect(anchor["rect"]).contains(fitz.Rect(anchor["quote_rect"])):
            raise ValueError(f"Anchored panel text lies outside its image crop: {anchor['locator']}")
        texts = [page.get_textbox(fitz.Rect(anchor["quote_rect"]))]
    if quote and any(compact(quote) in compact(t) for t in texts):
        return "region_text_matched" if "quote_rect" in anchor else "page_text_matched"
    if quote:
        raise ValueError(f"Exact quote missing at {anchor['locator']}: {quote}")
    if anchor.get("reading") and anchor.get("rect"):
        crop_rect(page, anchor["rect"])
        return "agent_visual_transcription"
    raise ValueError("Use a verifiable quote or a reviewed rectangular visual anchor.")

def frame(slot, rect):
    x, y, w, h = rect
    if not (0 <= x < 1 and 0 <= y < 1 and w > 0 and h > 0 and x+w <= 1.000001 and y+h <= 1.000001):
        raise ValueError(f"Object exceeds its template slot: {rect}")
    return (int(slot.left + x*slot.width), int(slot.top + y*slot.height),
            int(w*slot.width), int(h*slot.height))

def add_text(slide, slot, box, spec):
    target = slot if spec.get("in_placeholder") else slide.shapes.add_textbox(*box)
    if spec.get("in_placeholder") and tuple(box) != (slot.left,slot.top,slot.width,slot.height):
        raise ValueError("Writing into a placeholder uses its entire area.")
    tf = target.text_frame
    tf.clear()
    tf.word_wrap = True
    for k, line in enumerate(spec["lines"]):
        par = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
        par.text = line
        if "pt" in spec:
            par.font.size = Pt(spec["pt"])
        if "space_after" in spec:
            par.space_after = Pt(spec["space_after"])
        if spec.get("bold"):
            par.font.bold = True
        if spec.get("accent"):
            par.font.color.theme_color = MSO_THEME_COLOR.ACCENT_1

def add_chart(slide, box, spec):
    data = CategoryChartData()
    data.categories = spec["categories"]
    for name, vals in spec["series"].items():
        if len(vals) != len(data.categories) or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in vals):
            raise ValueError(f"Invalid chart values: {name}")
        data.add_series(name, vals)
    kind = {"column": XL_CHART_TYPE.COLUMN_CLUSTERED, "line": XL_CHART_TYPE.LINE_MARKERS}[spec["chart_type"]]
    chart = slide.shapes.add_chart(kind, *box, data).chart
    chart.has_title = False
    chart.has_legend = len(spec["series"]) > 1
    chart.value_axis.has_title = True
    chart.value_axis.axis_title.text_frame.text = spec["unit"]
    if "min" in spec:
        chart.value_axis.minimum_scale = spec["min"]
    if "max" in spec:
        chart.value_axis.maximum_scale = spec["max"]
    chart.chart_style = 10
    if spec.get("labels"):
        plot = chart.plots[0]
        plot.has_data_labels = True
        plot.data_labels.show_value = True
        plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END if spec["chart_type"] == "column" else XL_LABEL_POSITION.ABOVE
        plot.data_labels.font.size = Pt(13)
    return chart

def add_table(slide, box, spec):
    rows = spec["rows"]
    cols = len(rows[0])
    if not cols or any(len(row) != cols for row in rows):
        raise ValueError("A native table needs a rectangular matrix.")
    table = slide.shapes.add_table(len(rows),cols,*box).table
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            cell = table.cell(r,c)
            cell.text = str(value)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            if "pt" in spec:
                cell.text_frame.paragraphs[0].font.size = Pt(spec["pt"])

def build(plan_file, deck_file, map_file):
    plan = read(plan_file)
    base = Path(plan_file).resolve().parent
    template = base / plan["template"]
    if template.resolve() == Path(deck_file).resolve():
        raise ValueError("Choose an output path separate from the original.")
    deck = Presentation(template)
    if len(deck.slides) and plan.get("discard_exemplar_slides") is not True:
        raise ValueError("Template has existing slides. Inspect them. For edits, preserve content using the edit workflow.")
    for item in list(deck.slides._sldIdLst):
        deck.part.drop_rel(item.rId)
        deck.slides._sldIdLst.remove(item)
    documents, sources, anchors = {}, {}, {}
    for key, filename in plan["pdfs"].items():
        path = base / filename
        documents[key] = fitz.open(path)
        if documents[key].needs_pass:
            raise ValueError(f"Encrypted PDF: {path.name}")
        sources[key] = {"file": path.name, "sha256": sha(path), "pages": len(documents[key])}
    def page_for(anchor):
        n = anchor["page"]
        doc = documents[anchor["pdf"]]
        if not 1 <= n <= len(doc):
            raise ValueError(f"Physical page out of range: {n}")
        return doc[n-1]
    for key, anchor in plan["anchors"].items():
        anchors[key] = {**anchor, "check": check_anchor(anchor, page_for(anchor))}
    mapped = []
    for number, s in enumerate(plan["slides"], 1):
        layout = deck.slide_masters[s["master"]].slide_layouts[s["layout"]]
        slide = deck.slides.add_slide(layout)
        if slide.shapes.title is None:
            raise ValueError(f"Layout {layout.name} has no title. Choose the actual approved layout or adapt the helper.")
        slide.shapes.title.text = s["claim"]
        if not s["notes"].strip():
            raise ValueError(f"Slide {number} needs speaker notes.")
        slide.notes_slide.notes_text_frame.text = s["notes"]
        assigned = list(s["refs"])
        if not assigned:
            raise ValueError("Every claim needs page evidence.")
        for item in s["objects"]:
            if not item["refs"]:
                raise ValueError("Attach evidence to each object.")
            assigned.extend(item["refs"])
            slot = slide.placeholders[item["slot"]]
            box = frame(slot, item.get("box",[0,0,1,1]))
            kind = item["kind"]
            if kind == "text":
                add_text(slide, slot, box, item)
            elif kind == "table":
                add_table(slide, box, item)
            elif kind == "chart":
                add_chart(slide, box, item)
            elif kind == "crop":
                anchor = anchors[item["anchor"]]
                if item["anchor"] not in item["refs"]:
                    raise ValueError("Include the crop's source in the object's refs.")
                page = page_for(anchor)
                pix = page.get_pixmap(clip=crop_rect(page, anchor["rect"]), dpi=item.get("dpi",180), alpha=False)
                scale = min(box[2]/pix.width, box[3]/pix.height)
                w, h = int(pix.width*scale), int(pix.height*scale)
                slide.shapes.add_picture(io.BytesIO(pix.tobytes("png")), box[0]+(box[2]-w)//2,box[1]+(box[3]-h)//2,w,h)
            else:
                raise ValueError(f"Unsupported object: {kind}")
        mapped.append({"slide": number,"layout": layout.name, "claim": s["claim"], "refs": s["refs"],
                       "objects": s["objects"], "notes":s["notes"], "limits":s.get("limits",[]),
                       "evidence": {ref: anchors[ref] for ref in dict.fromkeys(assigned)}})
    Path(deck_file).parent.mkdir(parents=True,exist_ok=True)
    deck.save(deck_file)
    save(map_file, {"case_id":plan["case_id"], "template_sha256":sha(template), "deck_sha256":sha(deck_file),
                    "sources":sources, "slides":mapped})
    for doc in documents.values():
        doc.close()

def workbook_rows(chart):
    """Read the single data sheet emitted by the native category-chart writer."""
    with ZipFile(io.BytesIO(chart.part.chart_workbook.xlsx_part.blob)) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in si.iterfind(".//{*}t")) for si in sst]
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        result = {}
        for cell in sheet.findall(".//{*}sheetData/{*}row/{*}c"):
            v = cell.findtext("{*}v")
            if cell.get("t") == "s":
                v = strings[int(v)]
            elif cell.get("t") == "inlineStr":
                v = "".join(t.text or "" for t in cell.iterfind(".//{*}t"))
            elif v is not None:
                v = float(v)
            result[cell.get("r")] = v
        return result

def col_letter(number):
    name = ""
    while number:
        number, rest = divmod(number-1,26)
        name = chr(65+rest) + name
    return name

def check(deck_file, map_file, preview, directory):
    dest = Path(directory)
    dest.mkdir(parents=True, exist_ok=True)
    receipt = read(map_file)
    if sha(deck_file) != receipt["deck_sha256"]:
        raise ValueError("Deck and evidence map hashes differ.")
    deck = Presentation(deck_file)
    report = []
    with fitz.open(preview) as pdf:
        if len(pdf) != len(deck.slides) or len(pdf) != len(receipt["slides"]):
            raise ValueError("Evidence/deck/preview slide counts differ.")
        for n, (slide, entry, pg) in enumerate(zip(deck.slides, receipt["slides"], pdf),1):
            if slide.shapes.title.text != entry["claim"] or compact(entry["claim"]) not in compact(pg.get_text()):
                raise ValueError(f"Slide {n} title mismatch. Inspect render, fonts and extracted text.")
            if slide.notes_slide.notes_text_frame.text != entry["notes"] or slide.slide_layout.name != entry["layout"]:
                raise ValueError(f"Slide {n} notes/layout mismatch.")
            charts = [s.chart for s in slide.shapes if s.has_chart]
            tables = [s.table for s in slide.shapes if s.has_table]
            chart_specs = [o for o in entry["objects"] if o["kind"] == "chart"]
            table_specs = [o for o in entry["objects"] if o["kind"] == "table"]
            if len(charts) != len(chart_specs) or len(tables) != len(table_specs):
                raise ValueError(f"Slide {n} editable chart/table count mismatch.")
            for chart, obj in zip(charts,chart_specs):
                values = {series.name:list(series.values) for series in chart.series}
                categories = [c.label for c in chart.plots[0].categories]
                if values != obj["series"] or categories != obj["categories"] or chart.value_axis.axis_title.text_frame.text != obj["unit"]:
                    raise ValueError(f"Slide {n} native chart differs from its ledger.")
                cells = workbook_rows(chart)
                for ri, category in enumerate(categories,2):
                    if str(cells.get(f"A{ri}")) != str(category):
                        raise ValueError(f"Slide {n} workbook category A{ri} differs.")
                for ci, (name, vals) in enumerate(obj["series"].items(),2):
                    column = col_letter(ci)
                    if cells.get(column+"1") != name or [cells.get(column+str(i)) for i in range(2,2+len(vals))] != vals:
                        raise ValueError(f"Slide {n} embedded workbook series {name} differs.")
            for table, obj in zip(tables,table_specs):
                actual = [[cell.text for cell in row.cells] for row in table.rows]
                if actual != [[str(v) for v in row] for row in obj["rows"]]:
                    raise ValueError(f"Slide {n} native table differs from its ledger.")
            image = f"slide-{n:02}.png"
            pg.get_pixmap(dpi=125, alpha=False).save(dest/image)
            report.append({"slide":n,"snapshot":image,"editable_charts":len(charts),"editable_tables":len(tables)})
    save(dest/"checks.json", {"deck_sha256":sha(deck_file),"preview_sha256":sha(preview),"slides":report,
         "remaining":"Inspect each image against the actual source, template, case and notes. Record visual results separately."})

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd",required=True)
    for fn, args in [(index,["pdf","directory"]),(layouts,["template","output"]),
                     (build,["plan_file","deck_file","map_file"]),(check,["deck_file","map_file","preview","directory"])]:
        p = sub.add_parser(fn.__name__)
        for key in args:
            p.add_argument(key)
        p.set_defaults(run=fn)
    opts = vars(parser.parse_args())
    func = opts.pop("run")
    opts.pop("cmd")
    func(**opts)
