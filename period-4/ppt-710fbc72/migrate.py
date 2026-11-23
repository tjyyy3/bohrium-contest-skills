"""Migrate mapped text and self-contained native charts to real template slots."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from lxml import etree
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.opc.constants import CONTENT_TYPE as CT, RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from pptx.oxml.shapes.graphfrm import CT_GraphicalObjectFrame
from pptx.parts.chart import ChartPart
from pptx.parts.embeddedpackage import EmbeddedXlsxPart


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paragraphs(source, target, use_theme):
    """Copy native paragraphs including fields, breaks, list levels and math runs."""
    copied = [deepcopy(p._p) for p in source.paragraphs]
    for para in copied:
        for node in para.iter():
            if any(key.startswith("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}")
                   for key in node.attrib):
                raise ValueError("linked paragraph requires separate relationship migration")
        if use_theme:
            for run in para.xpath(".//a:rPr | .//a:defRPr | .//a:endParaRPr"):
                run.attrib.pop("sz", None)
                for child in list(run):
                    if etree.QName(child).localname in {
                        "latin", "ea", "cs", "solidFill", "gradFill", "noFill", "pattFill"
                    }:
                        run.remove(child)
    body = target._txBody
    for para in list(target.paragraphs):
        body.remove(para._p)
    for para in copied:
        body.append(para)


def native_chart(shape, slot, slide):
    original = shape.chart.part
    rels = list(original.rels.values())
    if len(rels) != 1 or rels[0].is_external or rels[0].reltype != RT.PACKAGE:
        raise ValueError("requires an embedded XLSX without additional chart dependencies")
    workbook = original.chart_workbook.xlsx_part
    if workbook is None or workbook.content_type != CT.SML_SHEET or workbook.rels:
        raise ValueError("expected a self-contained embedded XLSX part")
    package = slide.part.package
    chart = ChartPart.load(package.next_partname(ChartPart.partname_template),
                           original.content_type, package, original.blob)
    chart.chart_workbook.xlsx_part = EmbeddedXlsxPart.new(workbook.blob, package)
    rid = slide.part.relate_to(chart, RT.CHART)
    frame = CT_GraphicalObjectFrame.new_chart_graphicFrame(
        slot.shape_id, shape.name, rid, slot.left, slot.top, slot.width, slot.height
    )
    # Bind the native chart frame to the destination placeholder by its real index.
    nvpr = frame.find(qn("p:nvGraphicFramePr")).find(qn("p:nvPr"))
    nvpr.append(deepcopy(slot._element.xpath(".//p:ph")[0]))
    slot._element.getparent().replace(slot._element, frame)


def migrate(args):
    inputs = [args.start, args.template, args.plan]
    if len({p.resolve() for p in [*inputs, args.deck, args.map]}) != 5:
        raise ValueError("use distinct input and output paths")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    source, out = Presentation(args.start), Presentation(args.template)
    layouts = {str(layout.part.partname).lstrip("/"): layout
               for master in out.slide_masters for layout in master.slide_layouts}
    pages = plan["slides"]
    if sorted(p["source_slide"] for p in pages) != list(range(1, len(source.slides) + 1)):
        raise ValueError("plan must account for every source slide exactly once")
    if len(out.slides) and plan.get("replace_template_examples") is not True:
        raise ValueError("confirm replace_template_examples for a populated template copy")
    for sid in list(out.slides._sldIdLst):
        out.part.drop_rel(sid.rId)
        out.slides._sldIdLst.remove(sid)
    records = []
    for page_no, page in enumerate(pages, 1):
        src = source.slides[page["source_slide"] - 1]
        slide = out.slides.add_slide(layouts[page["layout"].lstrip("/")])
        show = src._element.get("show")
        if show is not None:
            slide._element.set("show", show)
        shapes = {s.shape_id: s for s in src.shapes}
        items = page["slots"]
        if sorted(i["shape"] for i in items) != sorted(shapes):
            raise ValueError(f"slide {page_no}: map every source shape exactly once")
        if len({i["idx"] for i in items}) != len(items):
            raise ValueError(f"slide {page_no}: duplicate destination slot")
        mapped = []
        for item in items:
            shape = shapes[item["shape"]]
            slot = slide.placeholders[item["idx"]]
            if not isinstance(item["source"], str) or not item["source"].strip():
                raise ValueError(f"slide {page_no}: source locator required")
            row = {**item, "target_shape": slot.shape_id}
            if shape.has_chart:
                if slot.placeholder_format.type.name not in {"CHART", "OBJECT", "BODY"}:
                    raise ValueError(f"slide {page_no}: chart needs chart/content/body slot")
                native_chart(shape, slot, slide)
                row["kind"] = "chart"
            elif shape.has_text_frame and shape.shape_type in (MSO_SHAPE_TYPE.PLACEHOLDER, MSO_SHAPE_TYPE.TEXT_BOX):
                if not slot.has_text_frame:
                    raise ValueError(f"slide {page_no}: destination has no text frame")
                paragraphs(shape.text_frame, slot.text_frame, True)
                row["kind"] = "text"
            else:
                raise ValueError(f"slide {page_no}, shape {shape.shape_id}: unsupported object")
            mapped.append(row)
        notes = src.notes_slide.notes_text_frame if src.has_notes_slide else None
        if notes is not None:
            destination = slide.notes_slide.notes_text_frame
            if destination is None:
                raise ValueError(f"slide {page_no}: target has no notes body")
            paragraphs(notes, destination, False)
        records.append({"output_slide": page_no, "source_slide": page["source_slide"],
                        "shown_in_normal_sequence": show not in ("0", "false"),
                        "layout": page["layout"], "slots": mapped, "notes_body_copied": notes is not None})
    args.deck.parent.mkdir(parents=True, exist_ok=True)
    args.map.parent.mkdir(parents=True, exist_ok=True)
    out.save(args.deck)
    result = {"status": "needs_review", "inputs": {
                  role: {"file": p.name, "sha256": sha(p)}
                  for role, p in zip(("starting_deck", "template", "plan"), inputs)},
              "deck_sha256": sha(args.deck), "slides": records}
    args.map.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("start", "template", "plan", "deck", "map"):
        parser.add_argument(name, type=Path)
    try:
        migrate(parser.parse_args())
    except (ValueError, KeyError, IndexError, TypeError, OSError) as error:
        print(f"Migration stopped: {error}", file=sys.stderr)
        sys.exit(2)
