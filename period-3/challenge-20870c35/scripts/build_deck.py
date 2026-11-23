"""Build an editable deck from an explicit, source-linked narrative plan."""
import argparse
import hashlib
import json
import platform
import re
from pathlib import Path

import pptx
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    root = args.plan.resolve().parent
    for key in ("case_id", "audience", "outcome", "template", "mode", "slide_count",
                "talk_seconds", "font", "title_pt", "body_pt", "caption_pt",
                "footer_box", "evidence", "slides", "qa"):
        if key not in plan:
            raise ValueError(f"Missing plan field: {key}")
    if plan["mode"] not in ("create", "edit"):
        raise ValueError("mode must be create or edit")
    if len(plan["slides"]) != plan["slide_count"]:
        raise ValueError("Plan slide count does not equal the requested count")
    template = (root / plan["template"]).resolve()
    deck = Presentation(template)
    if plan["mode"] == "create" and len(deck.slides):
        raise ValueError("Create requires an empty master/layout-based PPTX template. Use edit or a local template-aware script.")
    if plan["mode"] == "edit" and len(deck.slides) != plan["slide_count"]:
        raise ValueError("Edit requires one plan entry per existing slide")
    evidence = {}
    for item in plan["evidence"]:
        if item["id"] in evidence:
            raise ValueError(f"Duplicate evidence ID: {item['id']}")
        if not item["locator"] or not item["excerpt"]:
            raise ValueError("Evidence requires locator and excerpt")
        source = (root / item["path"]).resolve()
        evidence[item["id"]] = {**item, "path": str(source),
                                "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    total = 0
    for number, item in enumerate(plan["slides"], 1):
        if not item["evidence_ids"] or not set(item["evidence_ids"]) <= evidence.keys():
            raise ValueError(f"Slide {number} has missing/unknown evidence IDs")
        if not isinstance(item["seconds"], int) or item["seconds"] < 0 or (item["seconds"] == 0 and item["role"] != "backup"):
            raise ValueError(f"Slide {number} has invalid time allocation")
        if not item["notes"].strip() or not item["limits"].strip():
            raise ValueError(f"Slide {number} lacks notes or a claim limit")
        if item["kind"] not in ("text", "table", "image"):
            raise ValueError(f"Unsupported slide kind on slide {number}")
        if item["kind"] == "table" and (not item["table"] or len({len(row) for row in item["table"]}) != 1):
            raise ValueError(f"Slide {number} table is empty or ragged")
        anchors = {"title"}
        if item["kind"] == "text":
            anchors.update(f"body:{i}" for i in range(len(item["body"])))
        else:
            anchors.add(item["kind"])
        if item.get("caption"):
            anchors.add("caption")
        bindings = item.get("bindings", [])
        if len(bindings) != len(anchors) or {binding["anchor"] for binding in bindings} != anchors:
            raise ValueError(f"Slide {number} requires one evidence binding for each content anchor: {sorted(anchors)}")
        if any(not binding["evidence_ids"] or not set(binding["evidence_ids"]) <= set(item["evidence_ids"]) for binding in bindings):
            raise ValueError(f"Slide {number} item binding has missing or off-page evidence IDs")
        total += item["seconds"]
    if total > plan["talk_seconds"]:
        raise ValueError(f"Talk schedule exceeds budget: {total} > {plan['talk_seconds']}")
    for item in plan["qa"]:
        if not item["evidence_ids"] or not set(item["evidence_ids"]) <= evidence.keys():
            raise ValueError("Q&A has missing/unknown evidence IDs")
        if not item["slides"] or any(n < 1 or n > plan["slide_count"] for n in item["slides"]):
            raise ValueError("Q&A references a nonexistent slide")
    args.out.mkdir(parents=True, exist_ok=True)
    schedule = []
    page_map = []
    for number, item in enumerate(plan["slides"], 1):
        slide = deck.slides.add_slide(deck.slide_layouts[item["layout_index"]]) if plan["mode"] == "create" else deck.slides[number - 1]
        title = slide.placeholders[item["title_idx"]]
        body = slide.placeholders[item["body_idx"]]
        if title == body:
            raise ValueError("Title and body must use distinct placeholders")
        title.text = item["title"]
        for paragraph in title.text_frame.paragraphs:
            paragraph.font.size = Pt(plan["title_pt"])
            paragraph.font.name = plan["font"]
        body.text = ""
        body.text_frame.word_wrap = True
        if item["kind"] == "text":
            for index, line in enumerate(item["body"]):
                paragraph = body.text_frame.paragraphs[0] if index == 0 else body.text_frame.add_paragraph()
                paragraph.text = line
                paragraph.font.name = plan["font"]
                paragraph.font.size = Pt(plan["body_pt"])
                paragraph.space_after = Pt(20)
        else:
            content_height = body.height - Inches(0.75 if item.get("caption") else 0)
            if item["kind"] == "table":
                rows = item["table"]
                shape = slide.shapes.add_table(len(rows), len(rows[0]), body.left, body.top,
                                               body.width, content_height)
                shape.name = f"evidence-table-{number}"
                for r, row in enumerate(rows):
                    for c, value in enumerate(row):
                        cell = shape.table.cell(r, c)
                        cell.text = str(value)
                        cell.margin_left = Inches(0.12)
                        cell.margin_top = Inches(0.12)
                        for paragraph in cell.text_frame.paragraphs:
                            paragraph.font.name = plan["font"]
                            paragraph.font.size = Pt(plan["body_pt"])
                            paragraph.font.bold = r == 0
            else:
                source_image = (root / item["image"]).resolve()
                with Image.open(source_image) as im:
                    width, height = im.size
                ratio = min(body.width / width, content_height / height)
                slide.shapes.add_picture(str(source_image), int(body.left + (body.width - width * ratio) / 2),
                                         body.top, width=int(width * ratio), height=int(height * ratio))
            if item.get("caption"):
                caption = slide.shapes.add_textbox(body.left, body.top + content_height + Inches(0.1), body.width, Inches(0.6))
                caption.text = item["caption"]
                caption.text_frame.word_wrap = True
                for paragraph in caption.text_frame.paragraphs:
                    paragraph.font.name = plan["font"]
                    paragraph.font.size = Pt(plan["caption_pt"] + 2)
        footer = slide.shapes.add_textbox(*[Inches(v) for v in plan["footer_box"]])
        footer.name = "narrative-source-footer"
        footer.text = "  |  ".join(f"{eid}: {evidence[eid]['locator']}" for eid in item["evidence_ids"]) + f"  |  {number}/{plan['slide_count']}"
        for paragraph in footer.text_frame.paragraphs:
            paragraph.font.name = plan["font"]
            paragraph.font.size = Pt(plan["caption_pt"])
            paragraph.font.color.rgb = RGBColor.from_string("555555")
        citations = "\n".join(f"{eid}: {evidence[eid]['path']} :: {evidence[eid]['locator']}\n{evidence[eid]['excerpt']}\nSHA256 {evidence[eid]['sha256']}" for eid in item["evidence_ids"])
        slide.notes_slide.notes_text_frame.text = (f"Estimated seconds: {item['seconds']}\nRole: {item['role']}\n\n"
            f"{item['notes']}\n\nTransition: {item['transition']}\nClaim limit: {item['limits']}\n\nSources:\n{citations}")
        schedule.append({"slide": number, "seconds": item["seconds"], "role": item["role"],
                         "english_words": len(re.findall(r"\b[A-Za-z]+(?:'[A-Za-z]+)?\b", item["notes"])),
                         "cjk_characters": len(re.findall(r"[\u4e00-\u9fff]", item["notes"]))})
        page_map.append({"slide": number, "claim": item["title"], "evidence_ids": item["evidence_ids"], "bindings": item["bindings"], "limits": item["limits"]})
    deck.save(args.out / "deck.pptx")
    reopened = Presentation(args.out / "deck.pptx")
    warnings = []
    for number, slide in enumerate(reopened.slides, 1):
        for shape in slide.shapes:
            if shape.left < 0 or shape.top < 0 or shape.left + shape.width > reopened.slide_width + 100 or shape.top + shape.height > reopened.slide_height + 100:
                warnings.append(f"Slide {number}: shape outside canvas: {shape.name}")
    outputs = {
        "evidence-map.json": {"case_id": plan["case_id"], "evidence": list(evidence.values()), "pages": page_map},
        "qa.json": {"case_id": plan["case_id"], "questions": plan["qa"]},
        "timing.json": {"case_id": plan["case_id"], "estimated": True, "budget_seconds": plan["talk_seconds"], "planned_seconds": total, "margin_seconds": plan["talk_seconds"] - total, "slides": schedule},
        "build-record.json": {"case_id": plan["case_id"], "status": "built_pending_visual_and_semantic_review", "template": str(template), "template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(), "plan_sha256": hashlib.sha256(args.plan.read_bytes()).hexdigest(), "deck_sha256": hashlib.sha256((args.out / "deck.pptx").read_bytes()).hexdigest(), "python": platform.python_version(), "python_pptx": pptx.__version__, "font_requested": plan["font"], "slide_count": len(reopened.slides), "native_tables": sum(shape.has_table for slide in reopened.slides for shape in slide.shapes), "bounds_warnings": warnings}}
    for name, value in outputs.items():
        (args.out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(outputs["build-record.json"], ensure_ascii=False))


if __name__ == "__main__":
    main()
