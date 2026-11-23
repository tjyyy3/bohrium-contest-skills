"""Inspect actual PPTX lineage; compare a saved output with its template.

Read-only. JSON goes to stdout. A check with findings exits 1.
This is not a schema validator or a rendered-text overflow detector.
Group children are inventoried recursively in group-local coordinates;
canvas-bound checks remain limited to top-level shapes.
"""
import argparse
import hashlib
import json
import posixpath
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "c": "http://schemas.openxmlformats.org/drawingml/2006/chart"}


def inventory(path):
    prs = Presentation(path)
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        relationships = {}
        missing = []
        for name in sorted(names):
            if not name.endswith(".rels"):
                continue
            directory, filename = posixpath.split(name)
            owner = posixpath.join(posixpath.dirname(directory), filename[:-5])
            if name == "_rels/.rels":
                owner = ""
            relationships[owner] = []
            for rel in ET.fromstring(archive.read(name)):
                external = rel.get("TargetMode") == "External"
                target = rel.get("Target", "")
                if not external:
                    target = posixpath.normpath(posixpath.join(posixpath.dirname(owner), target)).lstrip("/")
                    if target not in names:
                        missing.append({"owner": owner, "id": rel.get("Id"), "target": target})
                relationships[owner].append({"id": rel.get("Id"), "type": rel.get("Type", "").rsplit("/", 1)[-1], "target": target, "external": external})
        protected = {name: hashlib.sha256(archive.read(name)).hexdigest() for name in sorted(names)
                     if name.startswith(("ppt/slideMasters/", "ppt/slideLayouts/", "ppt/theme/"))}
        themes = []
        for name in sorted(names):
            if name.startswith("ppt/theme/") and name.endswith(".xml"):
                root = ET.fromstring(archive.read(name))
                themes.append({"part": name, "fonts": sorted({e.get("typeface") for e in root.iter() if e.get("typeface")}),
                               "colors": [{"role": e.tag.split("}")[-1], "value": list(e)[0].attrib} for e in root.findall("a:themeElements/a:clrScheme/*", NS)]})
        slides = []
        for index, slide in enumerate(prs.slides, 1):
            part = str(slide.part.partname).lstrip("/")
            layout = slide.slide_layout
            master = layout.slide_master
            master_part = str(master.part.partname).lstrip("/")
            theme = [r["target"] for r in relationships.get(master_part, []) if r["type"] == "theme"]
            shapes = []
            pending = [(slide.shapes, shapes)]
            for source_shapes, rows in pending:
                for shape in source_shapes:
                    row = {"id": shape.shape_id, "name": shape.name, "box": [shape.left, shape.top, shape.width, shape.height], "kind": "shape"}
                    if shape.has_text_frame:
                        row.update(kind="text", text=shape.text)
                    if shape.is_placeholder:
                        row["placeholder"] = {"idx": shape.placeholder_format.idx, "type": str(shape.placeholder_format.type)}
                    if shape.has_table:
                        row.update(kind="table", cells=[[cell.text for cell in r.cells] for r in shape.table.rows])
                    if shape.has_chart:
                        row.update(kind="chart", chart_part=str(shape.chart.part.partname).lstrip("/"),
                                   series=[{"name": s.name, "values": list(s.values)} for s in shape.chart.series])
                    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                        row.update(kind="group", children=[], children_coordinate_system="group-local")
                        pending.append((shape.shapes, row["children"]))
                    rows.append(row)
            notes_frame = slide.notes_slide.notes_text_frame if slide.has_notes_slide else None
            slides.append({"slide": index, "part": part, "layout": str(layout.part.partname).lstrip("/"), "master": master_part,
                           "shown_in_normal_sequence": slide._element.get("show") not in ("0", "false"),
                           "theme": theme, "shapes": shapes,
                           "notes": notes_frame.text if notes_frame is not None else "",
                           "notes_body_present": notes_frame is not None})
        layouts = [{"master": str(m.part.partname).lstrip("/"), "part": str(l.part.partname).lstrip("/"), "name": l.name,
                    "placeholders": [{"idx": p.placeholder_format.idx, "type": str(p.placeholder_format.type), "box": [p.left, p.top, p.width, p.height]} for p in l.placeholders]}
                   for m in prs.slide_masters for l in m.slide_layouts]
        return {"file": str(path), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                "size_emu": [prs.slide_width, prs.slide_height], "protected_parts": protected, "themes": themes,
                "layouts": layouts, "relationships": relationships, "missing_targets": missing, "slides": slides,
                "embedded_files": sorted(n for n in names if n.startswith("ppt/embeddings/"))}


def compare_migration(start, actual, plan):
    source = start["slides"]
    order = [page["source_slide"] for page in plan["slides"]]
    if sorted(order) != list(range(1, len(source) + 1)):
        raise ValueError("plan must account for every source slide exactly once")
    findings = []
    if len(actual["slides"]) != len(order):
        findings.append({"kind": "slide_count_changed", "expected": len(order), "actual": len(actual["slides"])})
    for page, output in zip(plan["slides"], actual["slides"]):
        original = source[page["source_slide"] - 1]
        ref = {"source_slide": original["slide"], "output_slide": output["slide"]}
        if original["shown_in_normal_sequence"] != output["shown_in_normal_sequence"]:
            findings.append({"kind": "slide_visibility_changed", **ref,
                             "expected_shown": original["shown_in_normal_sequence"],
                             "actual_shown": output["shown_in_normal_sequence"]})
        if (original["notes_body_present"], original["notes"]) != (output["notes_body_present"], output["notes"]):
            findings.append({"kind": "speaker_notes_changed", **ref})
        shapes = {shape["id"]: shape for shape in original["shapes"]}
        slots = {shape["placeholder"]["idx"]: shape for shape in output["shapes"] if "placeholder" in shape}
        for entry in page["slots"]:
            shape = shapes[entry["shape"]]
            slot = slots.get(entry["idx"], {})
            field = {"text": "text", "chart": "series"}[shape["kind"]]
            if shape[field] != slot.get(field):
                findings.append({"kind": "mapped_content_changed", **ref,
                                 "source_shape": shape["id"], "target_slot": entry["idx"]})
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["inspect", "check"])
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--source", type=Path, help="starting deck for a one-to-one migration")
    parser.add_argument("--plan", type=Path, help="reviewed input plan with slides in intended output order")
    args = parser.parse_args()
    if bool(args.source) != bool(args.plan) or (args.source and args.mode != "check"):
        parser.error("--source and --plan are used together in check mode")
    original = inventory(args.template)
    if args.mode == "inspect":
        print(json.dumps(original, ensure_ascii=True, indent=2))
        return
    if args.output is None:
        parser.error("check needs TEMPLATE.pptx and OUTPUT.pptx")
    actual = inventory(args.output)
    findings = [{"kind": "missing_relationship_target", **r} for r in actual["missing_targets"]]
    changed = [part for part, digest in original["protected_parts"].items() if actual["protected_parts"].get(part) != digest]
    if changed:
        findings.append({"kind": "changed_or_missing_template_parts", "parts": changed})
    if original["size_emu"] != actual["size_emu"]:
        findings.append({"kind": "canvas_changed"})
    original_layouts = {layout["part"]: layout for layout in original["layouts"]}
    for slide in actual["slides"]:
        if slide["layout"] not in original_layouts:
            findings.append({"kind": "foreign_layout", "slide": slide["slide"], "part": slide["layout"]})
        else:
            allowed = {p["idx"] for p in original_layouts[slide["layout"]]["placeholders"]}
            for shape in slide["shapes"]:
                if "placeholder" in shape and shape["placeholder"]["idx"] not in allowed:
                    findings.append({"kind": "unmatched_placeholder", "slide": slide["slide"], "shape": shape["id"]})
        if not slide["theme"] or any(p not in original["protected_parts"] for p in [slide["master"], *slide["theme"]]):
            findings.append({"kind": "foreign_or_missing_master_theme", "slide": slide["slide"]})
        for shape in slide["shapes"]:
            x, y, w, h = shape["box"]
            if x < -127 or y < -127 or x+w > actual["size_emu"][0]+127 or y+h > actual["size_emu"][1]+127:
                findings.append({"kind": "shape_outside_canvas", "slide": slide["slide"], "shape": shape["id"], "box": shape["box"]})
    result = {"template": original["file"], "output": actual["file"], "template_sha256": original["sha256"],
              "output_sha256": actual["sha256"], "protected_part_count": len(original["protected_parts"]),
              "changed_parts": changed, "findings": findings, "slides": actual["slides"],
              "scope": "Package lineage and native-object inventory only; human visual/scientific review still required."}
    if args.source:
        start = inventory(args.source)
        try:
            plan = json.loads(args.plan.read_text(encoding="utf-8"))
            findings.extend(compare_migration(start, actual, plan))
        except (ValueError, TypeError, KeyError) as error:
            parser.error(f"invalid or unsupported migration plan: {error}")
        result.update(source_sha256=start["sha256"],
                      plan_sha256=hashlib.sha256(args.plan.read_bytes()).hexdigest(),
                      expected_visible_source_order=[p["source_slide"] for p in plan["slides"]
                                                     if start["slides"][p["source_slide"]-1]["shown_in_normal_sequence"]],
                      visible_output_slides=[s["slide"] for s in actual["slides"] if s["shown_in_normal_sequence"]],
                      scope="Template lineage and mapped slide content, normal show visibility and speaker-note body text.")
    print(json.dumps(result, ensure_ascii=True, indent=2))
    raise SystemExit(bool(findings))


if __name__ == "__main__":
    main()
