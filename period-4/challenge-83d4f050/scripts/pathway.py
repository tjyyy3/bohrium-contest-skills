#!/usr/bin/env python3
"""Render a reviewed mechanism graph and export its editable SVG."""

import argparse
import json
import math
import re
from pathlib import Path
from xml.etree import ElementTree as ET

VERSION = "0.1.0"
SVG = "http://www.w3.org/2000/svg"
INKSCAPE = "http://www.inkscape.org/namespaces/inkscape"
ET.register_namespace("", SVG)
ET.register_namespace("inkscape", INKSCAPE)

INK = "#172b3a"
SECONDARY = "#40586c"
FONT = "Arial, Liberation Sans, sans-serif"
RELATIONS = {
    "activate": ("#176452", "triangle", False, "Increases or enables"),
    "inhibit": ("#963b29", "bar", False, "Decreases or inhibits"),
    "associate": ("#52657a", "", True, "Association or readout"),
    "bind": ("#475570", "", False, "Binding"),
    "modify": ("#54457f", "open", False, "State change / modification"),
    "transport": ("#204d87", "double", False, "Transport"),
    "inferred": ("#52657a", "triangle", True, "Dashed arrow / bar: inferred"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_id(value):
    require(re.fullmatch(r"[a-z][a-z0-9-]*", value), f"invalid ID {value!r}")


def index(rows):
    result = {}
    for row in rows:
        key = row["id"]
        check_id(key)
        require(key not in result, f"duplicate ID: {key}")
        result[key] = row
    return result


def check_refs(row, evidence, required):
    refs = row.get("refs", [])
    require(
        isinstance(refs, list) and (refs or not required) and all(ref in evidence for ref in refs),
        f"{row['id']}: expected known evidence IDs",
    )


def check_point(point, canvas, owner):
    x, y = point
    require(math.isfinite(x) and math.isfinite(y) and 0 <= x <= canvas[0] and 0 <= y <= canvas[1], f"{owner}: point outside canvas")


def check_box(row, canvas):
    x, y, w, h = row["box"]
    require(w > 0 and h > 0, f"{row['id']}: box has nonpositive size")
    check_point((x, y), canvas, row["id"])
    check_point((x + w, y + h), canvas, row["id"])


def on_boundary(point, box):
    x, y = point
    left, top, w, h = box
    right, bottom = left + w, top + h
    return left <= x <= right and top <= y <= bottom and (x in (left, right) or y in (top, bottom))


def validate(graph):
    canvas = graph["canvas"]
    width, height = canvas
    require(math.isfinite(width) and math.isfinite(height) and width >= 700 and height >= 400, "canvas must be finite and at least 700 by 400")
    require(graph["title"].strip(), "empty title")
    require(len(graph.get("notes", [])) <= 3, "use at most three caption lines")

    sources, evidence = graph["sources"], graph["evidence"]
    for source_id, source in sources.items():
        check_id(source_id)
        require(source["title"].strip() and source["version"].strip(), f"{source_id}: missing source metadata")
    for evidence_id, item in evidence.items():
        check_id(evidence_id)
        require(item["source"] in sources, f"{evidence_id}: unknown source")
        require(all(item[key].strip() for key in ("claim", "locator", "context")), f"{evidence_id}: incomplete evidence")

    regions, nodes, edges = (index(graph[key]) for key in ("regions", "nodes", "edges"))
    require(nodes, "a graph needs at least one node")
    for key, region in regions.items():
        check_box(region, canvas)
        check_refs(region, evidence, required=region["kind"] != "panel")
        require(region["kind"] in {"area", "membrane", "panel"}, f"{key}: invalid region kind")
        require(region["label"].strip(), f"{key}: missing region label")
        if "label_at" in region:
            check_point(region["label_at"], canvas, key)
        if "fill" in region:
            require(re.fullmatch(r"#[0-9a-fA-F]{6}", region["fill"]), f"{key}: expected six-digit hex fill")

    for key, node in nodes.items():
        check_refs(node, evidence, required=True)
        check_box(node, canvas)
        require(node["label"].strip(), f"{key}: missing label")
        require(node["region"] in regions, f"{key}: unknown region")
        region = regions[node["region"]]
        x, y, w, h = node["box"]
        rx, ry, rw, rh = region["box"]
        placement = node.get("placement", "inside")
        require(rx <= x and x + w <= rx + rw, f"{key}: box exceeds region horizontally")
        if placement == "inside":
            require(ry <= y and y + h <= ry + rh, f"{key}: box must fit inside its region")
        else:
            require(
                placement == "spans" and region["kind"] == "membrane" and y < ry and ry + rh < y + h,
                f"{key}: spans must cross both sides of the horizontal membrane band",
            )

    for key, edge in edges.items():
        check_refs(edge, evidence, required=True)
        kind = edge["kind"]
        require(kind in RELATIONS and kind != "inferred", f"{key}: invalid relation kind")
        require(edge["action"].strip(), f"{key}: missing action")
        certainty = edge.get("certainty", "supported")
        require(certainty in {"supported", "inferred"}, f"{key}: invalid certainty")
        if certainty == "inferred":
            require(RELATIONS[kind][1], f"{key}: document uncertain undirected relations separately")
            require(edge.get("rationale", "").strip(), f"{key}: missing inference rationale")
        require(edge["from"] in nodes and edge["to"] in nodes, f"{key}: unknown endpoint")
        points = edge["points"]
        require(len(points) >= 2, f"{key}: expected at least two route points")
        for point in points:
            check_point(point, canvas, key)
        require(all(a != b for a, b in zip(points, points[1:])), f"{key}: zero-length segment")
        require(on_boundary(points[0], nodes[edge["from"]]["box"]), f"{key}: first point must touch the source boundary")
        require(on_boundary(points[-1], nodes[edge["to"]]["box"]), f"{key}: last point must touch the target boundary")
        if RELATIONS[kind][1]:
            require(math.dist(points[-2], points[-1]) >= 16, f"{key}: allow 16 units for the terminal symbol")
        check_point(edge["label_at"], canvas, key)


def element(parent, tag, **attrs):
    node = ET.Element(f"{{{SVG}}}{tag}", {key.replace("_", "-"): str(value) for key, value in attrs.items()})
    if parent is not None:
        parent.append(node)
    return node


def text_lines(parent, label, x, bottom, size, *, anchor="start", weight=400, color=INK):
    lines = label.splitlines()
    for index, line in enumerate(lines):
        y = bottom - (len(lines) - 1 - index) * (size + 2)
        node = element(
            parent, "text", x=x, y=y, text_anchor=anchor,
            font_family=FONT, font_size=size, font_weight=weight, fill=color,
        )
        node.text = line


def rect(parent, box, fill, *, stroke="none", radius=0):
    x, y, w, h = box
    return element(parent, "rect", x=x, y=y, width=w, height=h, rx=radius, fill=fill, stroke=stroke)


def layer(parent, id_, label):
    group = element(parent, "g", id=id_)
    group.set(f"{{{INKSCAPE}}}groupmode", "layer")
    group.set(f"{{{INKSCAPE}}}label", label)
    return group


def annotated_group(parent, prefix, row):
    refs = " ".join(row.get("refs", []))
    group = element(parent, "g", id=f"{prefix}-{row['id']}", data_evidence=refs)
    element(group, "title").text = f"{row['id']} | evidence: {refs}" if refs else row["id"]
    return group


def dashed_path(points, dash, gap):
    # Explicit vector segments preserve dashes in SVG renderers that omit stroke-dasharray.
    segments = []
    for (x, y), (target_x, target_y) in zip(points, points[1:]):
        length = math.hypot(target_x - x, target_y - y)
        if length == 0:
            continue
        dx, dy = (target_x - x) / length, (target_y - y) / length
        for start in range(0, math.ceil(length), dash + gap):
            end = min(start + dash, length)
            segments.append(f"M {x + start * dx:.4f} {y + start * dy:.4f} L {x + end * dx:.4f} {y + end * dy:.4f}")
    return " ".join(segments)


def draw_relation(parent, points, kind, inferred=False):
    color, tip, dashed, _ = RELATIONS[kind]
    dx = points[-1][0] - points[-2][0]
    dy = points[-1][1] - points[-2][1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    tx, ty = points[-1]

    def tip_point(back, offset=0):
        return (round(tx - back * ux - offset * uy, 3), round(ty - back * uy + offset * ux, 3))

    def point_list(coords):
        return " ".join(f"{x},{y}" for x, y in coords)

    endpoint = tip_point(5 if tip == "bar" else 1)
    route = [*points[:-1], endpoint]
    stroke = dict(stroke=color, stroke_width=2.6, fill="none", stroke_linejoin="round", stroke_linecap="round")
    if dashed or inferred:
        element(parent, "path", d=dashed_path(route, 7, 6), **stroke)
    else:
        element(parent, "polyline", points=point_list(route), **stroke)
    if tip == "bar":
        element(parent, "polyline", points=point_list([tip_point(5, -7), tip_point(5, 7)]), stroke=color, stroke_width=3)
    if tip == "triangle":
        element(parent, "polygon", points=point_list([tip_point(1), tip_point(12, -6), tip_point(12, 6)]), fill=color)
    if tip in {"open", "double"}:
        for back in (1, 9) if tip == "double" else (1,):
            element(
                parent, "polyline", points=point_list([tip_point(back + 6, -5), tip_point(back), tip_point(back + 6, 5)]),
                stroke=color, stroke_width=2.6, fill="none", stroke_linejoin="round",
            )


def write_svg(root, path):
    require(path.suffix.lower() == ".svg", "destination must be an SVG")
    ET.indent(root, space="  ")
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def draw(graph, output):
    validate(graph)
    width, height = graph["canvas"]
    root = element(
        None, "svg", width=f"{width * .75:g}pt", height=f"{height * .75:g}pt",
        viewBox=f"0 0 {width} {height}", role="img", data_pathway_version=VERSION,
    )
    element(root, "title").text = graph["title"]
    element(root, "desc").text = " ".join(filter(None, [graph.get("subtitle"), *graph.get("notes", [])]))
    background = layer(root, "background", "Background")
    rect(background, [0, 0, width, height], "#ffffff")

    regions = layer(root, "compartments", "Compartments")
    for row in graph["regions"]:
        group = annotated_group(regions, "region", row)
        x, y, _, _ = row["box"]
        is_membrane = row["kind"] == "membrane"
        default_fill = "#c5e2dc" if is_membrane else "#f1f5f8"
        rect(group, row["box"], row.get("fill", default_fill), stroke="#bed1d9", radius=4 if is_membrane else 12)
        label_x, label_y = row.get("label_at", [x + 16, y + 27])
        text_lines(group, row["label"], label_x, label_y, 14, weight=700, color=SECONDARY)

    edges = layer(root, "relationships", "Relationships")
    for row in graph["edges"]:
        group = annotated_group(edges, "edge", row)
        inferred = row.get("certainty") == "inferred"
        for key in ("kind", "from", "to"):
            group.set(f"data-{key}", row[key])
        group.set("data-certainty", "inferred" if inferred else "supported")
        draw_relation(group, row["points"], row["kind"], inferred)
        x, y = row["label_at"]
        bottom = y + (len(row["action"].splitlines()) - 1) * 17
        text_lines(group, row["action"], x, bottom, 15, color=RELATIONS[row["kind"]][0])

    nodes = layer(root, "nodes", "Entities and states")
    for row in graph["nodes"]:
        group = annotated_group(nodes, "node", row)
        group.set("data-region", row["region"])
        group.set("data-placement", row.get("placement", "inside"))
        group.set("data-entity-type", row.get("type", "unspecified"))
        x, y, w, h = row["box"]
        rect(group, row["box"], "#ffffff", stroke="#829aab", radius=10)
        label = element(group, "g", id=f"label-node-{row['id']}")
        lines = len(row["label"].splitlines())
        bottom = y + h / 2 + (1 if row.get("detail") else 7 + (lines - 1) * 11)
        text_lines(label, row["label"], x + w / 2, bottom, 20, anchor="middle", weight=700)
        if row.get("detail"):
            text_lines(group, row["detail"], x + w / 2, y + h / 2 + 23, 14, anchor="middle", color=SECONDARY)

    caption = layer(root, "captions", "Title, legend and caption")
    text_lines(caption, graph["title"], 48, 61, 39, weight=700)
    if graph.get("subtitle"):
        text_lines(caption, graph["subtitle"], 48, 91, 19, color=SECONDARY)
    used = {row["kind"] for row in graph["edges"]}
    if any(row.get("certainty") == "inferred" and RELATIONS[row["kind"]][1] for row in graph["edges"]):
        used.add("inferred")
    legend_y = height - 141
    element(caption, "line", x1=48, y1=legend_y - 20, x2=width - 48, y2=legend_y - 20, stroke="#bfd0da")
    kinds = [kind for kind in RELATIONS if kind in used]
    columns = min(4 if width >= 1140 else 2, max(1, len(kinds)))
    for item, kind in enumerate(kinds):
        col, row = item % columns, item // columns
        x, y = 48 + col * (width - 96) / columns, legend_y + row * 26 + 5
        draw_relation(caption, [(x, y), (x + 42, y)], kind)
        text_lines(caption, RELATIONS[kind][3], x + 54, y + 5, 15, color=SECONDARY)
    notes_y = max(height - 62, legend_y + 26 * math.ceil(len(kinds) / columns) + 12)
    for item, note in enumerate(graph.get("notes", [])):
        text_lines(caption, note, 48, notes_y + item * 21, 15, color=SECONDARY)
    write_svg(root, output)


def relabel(source, output, node_id, lines):
    require(source.resolve() != output.resolve(), "write the edit to a separate SVG")
    root = ET.parse(source).getroot()
    require(root.get("data-pathway-version") == VERSION, "relabel supports SVGs from this tool version")
    label = root.find(f".//{{{SVG}}}g[@id='label-node-{node_id}']")
    require(label is not None and len(label) > 0, f"no editable label for {node_id!r}")
    require(all(line.strip() and "\n" not in line for line in lines), "pass each nonempty label line separately")
    attributes = label[-1].attrib.copy()
    bottom = float(attributes["y"])
    leading = float(attributes["font-size"]) + 2
    for child in list(label):
        label.remove(child)
    for index, line in enumerate(lines):
        attributes["y"] = str(bottom - (len(lines) - index - 1) * leading)
        ET.SubElement(label, f"{{{SVG}}}text", attributes).text = line
    write_svg(root, output)


def export(svg_path, dpi):
    try:
        import pymupdf
    except ImportError as error:
        raise ValueError("PyMuPDF unavailable. See references/graph.md for an existing-tool export route.") from error

    require(dpi > 0, "dpi must be positive")
    with pymupdf.open(stream=svg_path.read_bytes(), filetype="svg") as source:
        pdf_data = source.convert_to_pdf()
    with pymupdf.open(stream=pdf_data, filetype="pdf") as pdf:
        require(len(pdf) == 1, "expected a single vector page")
        pdf.set_metadata({"producer": f"PyMuPDF {pymupdf.__version__}"})
        pdf.save(svg_path.with_suffix(".pdf"), deflate=True)
        page = pdf[0]
        pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
        pixmap.save(svg_path.with_suffix(".png"))
        return {
            "renderer": f"PyMuPDF {pymupdf.__version__}",
            "pdf_pages": len(pdf),
            "pdf_size_pt": [page.rect.width, page.rect.height],
            "pdf_fonts": sorted({font[3] for font in page.get_fonts()}),
            "pdf_image_objects": len(page.get_images()),
            "png_size_px": [pixmap.width, pixmap.height],
            "png_dpi": dpi,
            "png_color": "RGB",
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    drawing = commands.add_parser("draw", help="validate a graph JSON and draw an editable SVG")
    drawing.add_argument("graph", type=Path)
    drawing.add_argument("svg", type=Path)
    editing = commands.add_parser("relabel", help="edit one node label in a generated SVG")
    editing.add_argument("source", type=Path)
    editing.add_argument("output", type=Path)
    editing.add_argument("node_id")
    editing.add_argument("lines", nargs="+")
    exporting = commands.add_parser("export", help="export an SVG's PDF and PNG")
    exporting.add_argument("svg", type=Path)
    exporting.add_argument("--dpi", type=int, default=192)
    args = parser.parse_args()
    try:
        if args.command == "draw":
            graph = json.loads(args.graph.read_text(encoding="utf-8-sig"))
            draw(graph, args.svg)
        elif args.command == "relabel":
            check_id(args.node_id)
            relabel(args.source, args.output, args.node_id, args.lines)
        else:
            print(json.dumps(export(args.svg, args.dpi), indent=2))
    except (OSError, KeyError, TypeError, ValueError, ET.ParseError) as error:
        parser.exit(2, f"{args.command}: {error}\n")


if __name__ == "__main__":
    main()
