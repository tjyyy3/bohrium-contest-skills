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


def owned_shape(slide, role, item, number):
    name = f"etalk:{role}"
    legacy = {"table": f"evidence-table-{number}", "footer": "narrative-source-footer"}
    requested = item.get("shape_ids", {}).get(role)
    matches = [shape for shape in slide.shapes if shape.name == name
               or (requested is None and shape.name == legacy.get(role))
               or (requested is not None and shape.shape_id == requested)]
    if len(matches) > 1:
        raise ValueError(f"Slide {number}: ambiguous {role} ownership; inspect shape IDs")
    if requested is not None and not any(shape.shape_id == requested for shape in matches):
        raise ValueError(f"Slide {number}: requested {role} shape ID {requested} is absent")
    if matches:
        shape = matches[0]
        if shape.is_placeholder or (shape.name.startswith("etalk:") and shape.name != name):
            raise ValueError(f"Slide {number}: cannot claim {role} ownership of {shape.name}")
        shape.name = name
        return shape
    return None


def set_text(shape, text, font, size):
    shape.text = text
    shape.text_frame.word_wrap = True
    for paragraph in shape.text_frame.paragraphs:
        paragraph.font.name = font
        paragraph.font.size = Pt(size)


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
    source_text = {}
    for item in plan["evidence"]:
        if item["id"] in evidence:
            raise ValueError(f"Duplicate evidence ID: {item['id']}")
        if not item["locator"] or not item["excerpt"]:
            raise ValueError("Evidence requires locator and excerpt")
        source = (root / item["path"]).resolve()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if item.get("source_sha256") and item["source_sha256"] != digest:
            raise ValueError(f"Evidence {item['id']}: source version changed")
        verification = item.get("verification", "text")
        if verification == "text":
            if source not in source_text:
                source_text[source] = source.read_text(encoding="utf-8-sig")
            haystack = source_text[source]
        elif verification == "pdf":
            import fitz
            if not item.get("pages"):
                raise ValueError(f"Evidence {item['id']}: PDF evidence requires one-based pages")
            with fitz.open(source) as document:
                if any(not isinstance(p, int) or p < 1 or p > len(document) for p in item["pages"]):
                    raise ValueError(f"Evidence {item['id']}: invalid PDF page")
                haystack = "\n".join(document[p - 1].get_text() for p in item["pages"])
        elif verification == "visual":
            if not item.get("review_note", "").strip():
                raise ValueError(f"Evidence {item['id']}: visual evidence requires a review note")
            haystack = None
        else:
            raise ValueError(f"Evidence {item['id']}: unsupported verification mode")
        if haystack is not None and " ".join(item["excerpt"].split()) not in " ".join(haystack.split()):
            raise ValueError(f"Evidence {item['id']}: excerpt not found in the selected source/pages")
        evidence[item["id"]] = {**item, "path": str(source),
                                "sha256": digest, "quote_check": "matched" if haystack is not None else "manual_visual_only"}
    total = 0
    schedule = []
    pacing = {"english_wpm": 130, "cjk_cpm": 220, "english_ceiling_wpm": 180, "cjk_ceiling_cpm": 320, **plan.get("pacing", {})}
    if any(not isinstance(value, (int, float)) or value <= 0 for value in pacing.values()):
        raise ValueError("Pacing rates must be positive numbers")
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
        if item.get("caveat"):
            anchors.add("caveat")
        bindings = item.get("bindings", [])
        if len(bindings) != len(anchors) or {binding["anchor"] for binding in bindings} != anchors:
            raise ValueError(f"Slide {number} requires one evidence binding for each content anchor: {sorted(anchors)}")
        if any(not binding["evidence_ids"] or not set(binding["evidence_ids"]) <= set(item["evidence_ids"]) for binding in bindings):
            raise ValueError(f"Slide {number} item binding has missing or off-page evidence IDs")
        total += item["seconds"]
        spoken = item["notes"] + " " + item["transition"]
        english = len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:\.\d+)?", spoken))
        cjk = len(re.findall(r"[\u4e00-\u9fff]", spoken))
        pauses = item.get("pause_seconds", 5)
        if not isinstance(pauses, (int, float)) or pauses < 0:
            raise ValueError(f"Slide {number}: pause_seconds must be nonnegative")
        nominal = english / pacing["english_wpm"] * 60 + cjk / pacing["cjk_cpm"] * 60 + pauses
        minimum = english / pacing["english_ceiling_wpm"] * 60 + cjk / pacing["cjk_ceiling_cpm"] * 60 + pauses
        if item["role"] != "backup" and minimum > item["seconds"]:
            raise ValueError(f"Slide {number}: script_too_long; minimum estimated {minimum:.1f}s exceeds allocated {item['seconds']}s")
        schedule.append({"slide": number, "seconds": item["seconds"], "role": item["role"], "english_words_and_numbers": english,
                         "cjk_characters": cjk, "pause_seconds": pauses, "nominal_seconds": nominal,
                         "ceiling_rate_minimum_seconds": minimum, "pacing_warning": nominal > item["seconds"] and item["role"] != "backup"})
    if total > plan["talk_seconds"]:
        raise ValueError(f"Talk schedule exceeds budget: {total} > {plan['talk_seconds']}")
    for item in plan["qa"]:
        if not item["evidence_ids"] or not set(item["evidence_ids"]) <= evidence.keys():
            raise ValueError("Q&A has missing/unknown evidence IDs")
        if not item["slides"] or any(n < 1 or n > plan["slide_count"] for n in item["slides"]):
            raise ValueError("Q&A references a nonexistent slide")
    args.out.mkdir(parents=True, exist_ok=True)
    page_map = []
    ownership = []
    for number, item in enumerate(plan["slides"], 1):
        slide = deck.slides.add_slide(deck.slide_layouts[item["layout_index"]]) if plan["mode"] == "create" else deck.slides[number - 1]
        title = slide.placeholders[item["title_idx"]]
        body = slide.placeholders[item["body_idx"]]
        if title == body:
            raise ValueError("Title and body must use distinct placeholders")
        objects = {role: owned_shape(slide, role, item, number) for role in ("table", "image", "caption", "caveat", "footer")}
        active = {"footer", item["kind"]} | ({"caption"} if item.get("caption") else set()) | ({"caveat"} if item.get("caveat") else set())
        for role, shape in objects.items():
            if shape is not None and role not in active:
                slide.shapes._spTree.remove(shape._element)
                objects[role] = None
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
            content_height = body.height - Inches(0.75 if item.get("caption") else 0) - Inches(0.8 if item.get("caveat") else 0)
            if item["kind"] == "table":
                rows = item["table"]
                content_height = min(content_height, Inches(item.get("table_height_inches", 0.9 * len(rows))))
                if content_height <= 0:
                    raise ValueError(f"Slide {number}: no available table height")
                shape = objects["table"]
                if shape is not None and (not shape.has_table or len(shape.table.rows) != len(rows) or len(shape.table.columns) != len(rows[0])):
                    slide.shapes._spTree.remove(shape._element)
                    shape = None
                if shape is None:
                    shape = slide.shapes.add_table(len(rows), len(rows[0]), body.left, body.top, body.width, content_height)
                shape.name = "etalk:table"
                shape.left, shape.top, shape.width, shape.height = body.left, body.top, body.width, content_height
                for row in shape.table.rows:
                    row.height = int(content_height / len(rows))
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
                if objects["image"] is not None:
                    slide.shapes._spTree.remove(objects["image"]._element)
                source_image = (root / item["image"]).resolve()
                with Image.open(source_image) as im:
                    width, height = im.size
                ratio = min(body.width / width, content_height / height)
                shape = slide.shapes.add_picture(str(source_image), int(body.left + (body.width - width * ratio) / 2),
                                                body.top, width=int(width * ratio), height=int(height * ratio))
                shape.name = "etalk:image"
            if item.get("caption"):
                caption = objects["caption"]
                if caption is None:
                    caption = slide.shapes.add_textbox(body.left, body.top, body.width, Inches(0.6))
                caption.name = "etalk:caption"
                caption.left, caption.top, caption.width, caption.height = body.left, body.top + content_height + Inches(0.1), body.width, Inches(0.6)
                set_text(caption, item["caption"], plan["font"], plan["caption_pt"] + 2)
        if item.get("caveat"):
            caveat = objects["caveat"]
            if caveat is None:
                caveat = slide.shapes.add_textbox(body.left, body.top, body.width, Inches(0.7))
            caveat.name = "etalk:caveat"
            caveat.left, caveat.top, caveat.width, caveat.height = body.left, body.top + body.height - Inches(0.7), body.width, Inches(0.7)
            set_text(caveat, item["caveat"], plan["font"], plan["body_pt"])
        footer = objects["footer"]
        if footer is None:
            footer = slide.shapes.add_textbox(*[Inches(v) for v in plan["footer_box"]])
        footer.name = "etalk:footer"
        footer.left, footer.top, footer.width, footer.height = [Inches(v) for v in plan["footer_box"]]
        set_text(footer, "  |  ".join(f"{eid}: {evidence[eid]['locator']}" for eid in item["evidence_ids"]) + f"  |  {number}/{plan['slide_count']}", plan["font"], plan["caption_pt"])
        for paragraph in footer.text_frame.paragraphs:
            paragraph.font.name = plan["font"]
            paragraph.font.size = Pt(plan["caption_pt"])
            paragraph.font.color.rgb = RGBColor.from_string("555555")
        citations = "\n".join(f"{eid}: {evidence[eid]['path']} :: {evidence[eid]['locator']}\n{evidence[eid]['excerpt']}\nSHA256 {evidence[eid]['sha256']}" for eid in item["evidence_ids"])
        slide.notes_slide.notes_text_frame.text = (f"Estimated seconds: {item['seconds']}\nRole: {item['role']}\n\n"
            f"{item['notes']}\n\nTransition: {item['transition']}\nClaim limit: {item['limits']}\n\nSources:\n{citations}")
        ownership.append({"slide": number, "objects": [{"name": shape.name, "shape_id": shape.shape_id} for shape in slide.shapes if shape.name.startswith("etalk:")]})
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
        "timing.json": {"case_id": plan["case_id"], "estimated": True, "rates_are_author_assumptions": True, "pacing": pacing, "includes_transitions_and_numbers": True, "budget_seconds": plan["talk_seconds"], "planned_seconds": total, "margin_seconds": plan["talk_seconds"] - total, "slides": schedule},
        "owned-objects.json": {"case_id": plan["case_id"], "pages": ownership},
        "build-record.json": {"case_id": plan["case_id"], "status": "built_pending_visual_and_semantic_review", "template": str(template), "template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(), "plan_sha256": hashlib.sha256(args.plan.read_bytes()).hexdigest(), "deck_sha256": hashlib.sha256((args.out / "deck.pptx").read_bytes()).hexdigest(), "python": platform.python_version(), "python_pptx": pptx.__version__, "font_requested": plan["font"], "slide_count": len(reopened.slides), "native_tables": sum(shape.has_table for slide in reopened.slides for shape in slide.shapes), "bounds_warnings": warnings}}
    for name, value in outputs.items():
        (args.out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(outputs["build-record.json"], ensure_ascii=False))


if __name__ == "__main__":
    main()
