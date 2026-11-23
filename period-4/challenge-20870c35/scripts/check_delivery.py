"""Check actual PPTX content, ownership, source versions and preview freshness."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from pptx import Presentation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    deck_path = args.out / "deck.pptx"
    deck = Presentation(deck_path)
    evidence = json.loads((args.out / "evidence-map.json").read_text(encoding="utf-8"))
    timing = json.loads((args.out / "timing.json").read_text(encoding="utf-8"))
    questions = json.loads((args.out / "qa.json").read_text(encoding="utf-8"))
    issues = []
    if len(deck.slides) != plan["slide_count"]:
        issues.append("Actual slide count differs from plan")
    if evidence["case_id"] != plan["case_id"] or timing["case_id"] != plan["case_id"]:
        issues.append("Case identifiers differ")
    if questions["case_id"] != plan["case_id"] or questions["questions"] != plan["qa"]:
        issues.append("Q&A differs from the evidence-bound plan")
    locators = {item["id"]: item["locator"] for item in evidence["evidence"]}
    for item in evidence["evidence"]:
        if hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            issues.append(f"Source changed: {item['id']}")
    pages = []
    for number, (slide, item) in enumerate(zip(deck.slides, plan["slides"]), 1):
        owned = [shape for shape in slide.shapes if shape.name.startswith("etalk:")]
        names = [shape.name for shape in owned]
        expected = {"etalk:footer"}
        if item["kind"] in ("table", "image"):
            expected.add("etalk:" + item["kind"])
        expected.update("etalk:" + role for role in ("caption", "caveat") if item.get(role))
        if len(names) != len(set(names)) or set(names) != expected:
            issues.append(f"Slide {number}: owned object count/names differ")
        if slide.placeholders[item["title_idx"]].text != item["title"]:
            issues.append(f"Slide {number}: title differs")
        if item["kind"] == "text" and slide.placeholders[item["body_idx"]].text != "\n".join(item["body"]):
            issues.append(f"Slide {number}: body differs")
        for shape in owned:
            role = shape.name.removeprefix("etalk:")
            if role == "table" and (not shape.has_table or [[cell.text for cell in row.cells] for row in shape.table.rows] != [[str(value) for value in row] for row in item["table"]]):
                issues.append(f"Slide {number}: native table differs")
            if role in ("caption", "caveat") and shape.text != item[role]:
                issues.append(f"Slide {number}: {role} differs")
            if role == "footer":
                expected_footer = "  |  ".join(f"{eid}: {locators[eid]}" for eid in item["evidence_ids"]) + f"  |  {number}/{plan['slide_count']}"
                if shape.text != expected_footer:
                    issues.append(f"Slide {number}: visible source footer differs")
            if role == "image" and hashlib.sha256(shape.image.blob).hexdigest() != hashlib.sha256((args.plan.resolve().parent / item["image"]).read_bytes()).hexdigest():
                issues.append(f"Slide {number}: source image bytes differ")
        notes = slide.notes_slide.notes_text_frame.text
        if item["notes"] not in notes or f"Transition: {item['transition']}" not in notes or f"Estimated seconds: {item['seconds']}" not in notes:
            issues.append(f"Slide {number}: notes/timing differ")
        if evidence["pages"][number - 1]["bindings"] != item["bindings"]:
            issues.append(f"Slide {number}: bindings differ")
        if timing["slides"][number - 1]["seconds"] != item["seconds"]:
            issues.append(f"Slide {number}: timing artifact differs")
        pages.append({"slide": number, "shape_count": len(slide.shapes), "owned_names": names,
                      "native_tables": sum(shape.has_table for shape in slide.shapes)})
    if timing["planned_seconds"] != sum(item["seconds"] for item in plan["slides"]) or timing["planned_seconds"] > plan["talk_seconds"]:
        issues.append("Timing total differs or exceeds budget")
    with zipfile.ZipFile(args.plan.resolve().parent / plan["template"]) as source, zipfile.ZipFile(deck_path) as output:
        design_parts = [name for name in source.namelist() if name.startswith(("ppt/slideMasters/", "ppt/slideLayouts/", "ppt/theme/"))]
        if any(name not in output.namelist() or source.read(name) != output.read(name) for name in design_parts):
            issues.append("Template master/layout/theme parts changed")
    if args.preview:
        import fitz
        receipt = json.loads((args.preview / "render-record.json").read_text(encoding="utf-8"))
        if receipt["input_sha256"] != hashlib.sha256(deck_path.read_bytes()).hexdigest():
            issues.append("Preview came from different PPTX bytes")
        with fitz.open(args.preview / "deck.pdf") as pdf:
            if len(pdf) != len(deck.slides):
                issues.append("Rendered page count differs")
            for number, page in enumerate(pdf, 1):
                if not page.get_text().strip() or not (args.preview / f"slide-{number:02d}.png").is_file():
                    issues.append(f"Slide {number}: rendered text or PNG absent")
    report = {"status": "pass" if not issues else "fail", "issues": issues, "pages": pages,
              "template_parts_checked": len(design_parts), "pacing_warnings": [item["slide"] for item in timing["slides"] if item.get("pacing_warning")],
              "limits": "Structural/content freshness check only. Inspect every PNG and assess evidence entailment separately."}
    (args.out / "delivery-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(bool(issues))


if __name__ == "__main__":
    main()
