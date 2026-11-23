"""Build a source-linked SVG or replace specific plain SVG text nodes."""

import argparse
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.parsers import expat
from xml.sax.saxutils import escape


SVG = "http://www.w3.org/2000/svg"
INKSCAPE = "http://www.inkscape.org/namespaces/inkscape"
ET.register_namespace("", SVG)
ET.register_namespace("inkscape", INKSCAPE)


def element(parent, tag, attributes, text=None):
    child = ET.SubElement(parent, f"{{{SVG}}}{tag}", {k: str(v) for k, v in attributes.items()})
    child.text = text
    return child


def layer(parent, name):
    return element(parent, "g", {
        "id": name.lower(), f"{{{INKSCAPE}}}groupmode": "layer", f"{{{INKSCAPE}}}label": name,
    })


def line_text(parent, x, y, content, size, **attributes):
    return element(parent, "text", {"x": x, "y": y, "font-size": size, **attributes}, content)


def text_value(value, field):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError(f"{field} must be non-empty, single-line text")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", value):
        raise ValueError(f"Invalid graph ID: {value!r}")
    return value


def numbers(values, count):
    if not isinstance(values, list) or len(values) != count or any(
        type(value) not in (int, float) or not math.isfinite(value) for value in values
    ):
        raise ValueError(f"Expected {count} finite numbers: {values!r}")
    return values


def center(box):
    x, y, width, height = box
    return x + width / 2, y + height / 2


def boundary(box, towards):
    x, y = center(box)
    dx, dy = towards[0] - x, towards[1] - y
    if abs(dx) <= box[2] / 2 and abs(dy) <= box[3] / 2:
        raise ValueError("Connector direction point must be outside its entity box")
    factor = min(box[2] / (2 * abs(dx)) if dx else math.inf,
                 box[3] / (2 * abs(dy)) if dy else math.inf)
    return round(x + factor * dx, 3), round(y + factor * dy, 3)


def draw(spec):
    mm_w, mm_h = numbers(spec["canvas_mm"], 2)
    if mm_w <= 0 or mm_h <= 0:
        raise ValueError("Canvas dimensions must be positive")
    w, h = 4 * mm_w, 4 * mm_h
    title = text_value(spec["title"], "title")
    svg = ET.Element(f"{{{SVG}}}svg", {
        "width": f"{mm_w}mm", "height": f"{mm_h}mm", "viewBox": f"0 0 {w} {h}",
        "font-family": text_value(spec.get("font_family", "Arial, Liberation Sans, sans-serif"), "font_family"),
        "fill": "#172D3B", "role": "img", "aria-labelledby": "figure-title",
    })
    element(svg, "title", {"id": "figure-title"}, title)
    defs = element(svg, "defs", {})
    page = layer(svg, "Page")
    nodes = layer(svg, "Entities")
    arrows = layer(svg, "Connections")
    legend = layer(svg, "Legend")

    element(page, "rect", {"width": w, "height": h, "fill": "#FFFFFF"})
    line_text(page, 36, 37, title, 23, **{"font-weight": "bold"})
    if "subtitle" in spec:
        line_text(page, 36, 59, text_value(spec["subtitle"], "subtitle"), 12, fill="#42586B")

    boxes = {}
    for node in spec["nodes"]:
        node_id = identifier(node["id"])
        x, y, width, height = numbers(node["box"], 4)
        if node_id in boxes:
            raise ValueError(f"Duplicate entity: {node_id}")
        if min(x, y) < 0 or min(width, height) <= 0 or x + width > w or y + height > h:
            raise ValueError(f"Box for {node_id} falls outside the viewBox")
        for other, (ox, oy, ow, oh) in boxes.items():
            if x <= ox + ow and ox <= x + width and y <= oy + oh and oy <= y + height:
                raise ValueError(f"Entity boxes touch or overlap: {node_id}, {other}")
        boxes[node_id] = (x, y, width, height)
        group = element(nodes, "g", {
            "id": f"node-{node_id}", "data-source": text_value(node["source"], "node source"),
        })
        element(group, "rect", {
            "x": x, "y": y, "width": width, "height": height, "rx": 6,
            "fill": "#F3F7FA", "stroke": "#ACBCC8", "stroke-width": 1.2,
        })
        line_text(group, x + width / 2, y + height / 2 + (5 if "detail" not in node else -3),
                  text_value(node["label"], "node label"), 16,
                  id=f"label-{node_id}", **{"text-anchor": "middle", "font-weight": "bold"})
        if "detail" in node:
            line_text(group, x + width / 2, y + height / 2 + 16,
                      text_value(node["detail"], "node detail"), 11,
                      id=f"detail-{node_id}", fill="#42586B", **{"text-anchor": "middle"})
    if not boxes:
        raise ValueError("At least one entity is required")

    strokes = {}
    for kind in dict.fromkeys(edge["kind"] for edge in spec["edges"]):
        identifier(kind)
        style = spec["styles"][kind]
        color = style["color"]
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError(f"Style {kind} needs an RGB hex color")
        dashed = style.get("dashed", False)
        if not isinstance(dashed, bool):
            raise ValueError(f"Style {kind} needs a boolean dashed value")
        marker = element(defs, "marker", {
            "id": f"arrow-{kind}", "viewBox": "0 0 10 10", "refX": 10, "refY": 5,
            "markerWidth": 10, "markerHeight": 10, "markerUnits": "userSpaceOnUse", "orient": "auto",
        })
        element(marker, "path", {"d": "M 0 0 L 10 5 L 0 10 Z", "fill": color})
        strokes[kind] = {
            "fill": "none", "stroke": color, "stroke-width": 2.4, "stroke-linejoin": "round",
            "marker-end": f"url(#arrow-{kind})",
        }
        if dashed:
            strokes[kind]["stroke-dasharray"] = "6 4"

    edge_ids = set()
    for edge in spec["edges"]:
        edge_id = identifier(edge["id"])
        start, end = edge["from"], edge["to"]
        if edge_id in edge_ids or start == end:
            raise ValueError(f"Duplicate edge ID or self loop: {edge_id}")
        edge_ids.add(edge_id)
        source_box, target_box = boxes[start], boxes[end]
        via = [tuple(numbers(point, 2)) for point in edge.get("via", [])]
        if any(not (0 <= x <= w and 0 <= y <= h) for x, y in via):
            raise ValueError(f"Waypoint falls outside the viewBox: {edge_id}")
        points = [boundary(source_box, via[0] if via else center(target_box)),
                  *via, boundary(target_box, via[-1] if via else center(source_box))]
        if any(a == b for a, b in zip(points, points[1:])):
            raise ValueError(f"Zero-length leg: {edge_id}")
        kind = edge["kind"]
        group = element(arrows, "g", {
            "id": f"edge-{edge_id}", "data-from": start, "data-to": end, "data-kind": kind,
            "data-source": text_value(edge["source"], "edge source"),
        })
        path = "M " + " L ".join(f"{x} {y}" for x, y in points)
        element(group, "path", {"d": path, **strokes[kind]})
        if "label" in edge:
            lx, ly = numbers(edge["label_at"], 2)
            if not (0 <= lx <= w and 0 <= ly <= h):
                raise ValueError(f"Edge label falls outside the viewBox: {edge_id}")
            line_text(group, lx, ly, text_value(edge["label"], "edge label"), 11,
                      id=f"edge-label-{edge_id}", fill="#42586B")

    if strokes:
        separator = h - 57
        element(legend, "path", {
            "d": f"M 36 {separator} H {w - 36}", "stroke": "#CCD7DF", "stroke-width": 1,
        })
        for index, (kind, stroke) in enumerate(strokes.items()):
            x, y = 36 + index * (w - 72) / len(strokes), h - 29
            group = element(legend, "g", {"id": f"legend-{kind}", "data-kind": kind})
            element(group, "path", {"d": f"M {x} {y} h 36", **stroke})
            line_text(group, x + 47, y + 4, text_value(spec["styles"][kind]["label"], "legend label"),
                      12, fill="#42586B")

    ET.indent(svg)
    return ET.tostring(svg, encoding="utf-8", xml_declaration=True) + b"\n"


def edit_svg(original, changes):
    requested = {}
    for change in changes:
        target = text_value(change["id"], "SVG id")
        if target in requested:
            raise ValueError(f"Duplicate requested edit: {target}")
        text_value(change["expect"], "expected previous text")
        text_value(change["replace"], "replacement text")
        text_value(change["source"], "edit source")
        if change["expect"] == change["replace"]:
            raise ValueError(f"Replacement matches previous text: {target}")
        requested[target] = change
    if not requested:
        raise ValueError("At least one edit is required")

    original.decode("utf-8-sig")
    parser = expat.ParserCreate(encoding="UTF-8", namespace_separator="}")
    active = None
    chunks = []
    body_start = 0
    seen = set()
    patches = []
    is_root = True

    def require_plain_text(*_):
        if active is not None:
            raise ValueError(f"{active} needs a manual edit of its nested or mixed content")

    def start(name, attrs):
        nonlocal active, is_root
        require_plain_text()
        if is_root and name != f"{SVG}}}svg":
            raise ValueError("Expected an SVG document")
        is_root = False
        target = attrs.get("id")
        if target in requested:
            if target in seen or name != f"{SVG}}}text":
                raise ValueError(f"{target} must identify one SVG text element")
            seen.add(target)
            active = target
            chunks.clear()

    def characters(data):
        nonlocal body_start
        if active is not None:
            if not chunks:
                body_start = parser.CurrentByteIndex
            chunks.append(data)

    def end(_name):
        nonlocal active
        if active is not None:
            change = requested[active]
            if "".join(chunks) != change["expect"]:
                raise ValueError(f"Previous text differs for {active}")
            patches.append((body_start, parser.CurrentByteIndex, escape(change["replace"]).encode("utf-8")))
            active = None

    def reject_doctype(*_):
        raise ValueError("SVG with a DOCTYPE requires manual review")

    parser.StartElementHandler = start
    parser.CharacterDataHandler = characters
    parser.EndElementHandler = end
    parser.CommentHandler = require_plain_text
    parser.ProcessingInstructionHandler = require_plain_text
    parser.StartCdataSectionHandler = require_plain_text
    parser.StartDoctypeDeclHandler = reject_doctype
    parser.Parse(original, True)
    missing = requested.keys() - seen
    if missing:
        raise ValueError(f"Unknown SVG ids: {', '.join(sorted(missing))}")
    edited = original
    for first, last, replacement in sorted(patches, reverse=True):
        edited = edited[:first] + replacement + edited[last:]
    ET.fromstring(edited)
    return edited


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("graph", type=Path)
    edit = subparsers.add_parser("edit")
    edit.add_argument("svg", type=Path)
    edit.add_argument("changes", type=Path)
    for command in (create, edit):
        command.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        inputs = [args.graph] if args.command == "create" else [args.svg, args.changes]
        if any(args.output.resolve() == path.resolve() for path in inputs):
            raise ValueError("Choose a destination distinct from the input")
        spec = json.loads(inputs[-1].read_text(encoding="utf-8-sig"))
        if args.command == "create":
            result = draw(spec)
            ET.fromstring(result)
        else:
            original = args.svg.read_bytes()
            result = edit_svg(original, spec)
        args.output.write_bytes(result)
        receipt = {"output": args.output.as_posix(), "sha256": hashlib.sha256(result).hexdigest()}
        if args.command == "edit":
            receipt.update(before_sha256=hashlib.sha256(original).hexdigest(), changes=spec)
        print(json.dumps(receipt, ensure_ascii=True))
    except (OSError, KeyError, TypeError, ValueError, OverflowError, ET.ParseError, expat.ExpatError) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
