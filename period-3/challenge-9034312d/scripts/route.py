#!/usr/bin/env python3
"""Render source-bound orthogonal routes and record narrow presentation edits."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

STYLES = {
    "sequence": ("#263746", ""),
    "material": ("#007B77", ""),
    "information": ("#315AAB", "7 4"),
    "energy": ("#945D00", "2 4"),
}
PORTS = {"left": (-1, 0), "right": (1, 0), "top": (0, -1), "bottom": (0, 1)}
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate(graph, origin):
    sources = {}
    ids = set()
    for item in graph["sources"]:
        if item["id"] in ids:
            raise ValueError("Duplicate source ID: " + item["id"])
        ids.add(item["id"])
        path = (origin.parent / item["path"]).resolve()
        sources[item["id"]] = {**item, "resolved_path": str(path), "sha256": sha(path),
                               "text": path.read_text(encoding="utf-8-sig")}
        if item.get("sha256") and item["sha256"] != sources[item["id"]]["sha256"]:
            raise ValueError("Source hash changed: " + item["id"])
    for item in graph["nodes"] + graph["edges"]:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", item["id"]) or item["id"] in ids:
            raise ValueError("Invalid or duplicate element ID: " + item["id"])
        ids.add(item["id"])
        if not item["evidence"]:
            raise ValueError("Missing evidence: " + item["id"])
        for ref in item["evidence"]:
            if not ref["locator"] or not ref["quote"] or ref["quote"] not in sources[ref["source"]]["text"]:
                raise ValueError("Unresolved quote/locator: " + item["id"])
    width, height = graph.get("width", 1000), graph.get("height", 650)
    svg_ids = ["layer-connections", "layer-entities", "layer-labels", "layer-legend"]
    svg_ids += [n["id"] for n in graph["nodes"]] + [n["id"]+"-text" for n in graph["nodes"]]
    svg_ids += [e["id"]+suffix for e in graph["edges"] for suffix in ["", "-arrow", "-label"]]
    if len(svg_ids) != len(set(svg_ids)):
        raise ValueError("Element ID collides with generated SVG IDs")
    if not 100 <= width <= 10000 or not 100 <= height <= 10000:
        raise ValueError("Canvas dimensions outside 100..10000")
    nodes = {n["id"]: n for n in graph["nodes"]}
    for n in nodes.values():
        if n["kind"] not in {"process", "decision", "detector", "terminal"}:
            raise ValueError("Unknown node kind: " + n["id"])
        if not all(math.isfinite(n[k]) for k in ["x", "y", "w", "h"]) or min(n["w"], n["h"]) <= 0:
            raise ValueError("Invalid node geometry: " + n["id"])
        if n["x"] - n["w"] / 2 < 20 or n["x"] + n["w"] / 2 > width - 20 or n["y"] - n["h"] / 2 < 80 or n["y"] + n["h"] / 2 > height - 80:
            raise ValueError("Node outside drawing area: " + n["id"])
    boxes = list(nodes.values())
    for i, n in enumerate(boxes):
        for m in boxes[i + 1:]:
            if abs(n["x"]-m["x"]) < (n["w"]+m["w"])/2 and abs(n["y"]-m["y"]) < (n["h"]+m["h"])/2:
                raise ValueError("Overlapping nodes: " + n["id"] + ", " + m["id"])
    routes = {}
    for e in graph["edges"]:
        if e["type"] not in STYLES or not e["label"]:
            raise ValueError("Unknown edge type or absent label: " + e["id"])
        points = []
        for endpoint, port in [("from", "from_port"), ("to", "to_port")]:
            n, direction = nodes[e[endpoint]], PORTS[e[port]]
            points.append([n["x"] + direction[0]*n["w"]/2, n["y"] + direction[1]*n["h"]/2])
        points[1:1] = e.get("via", [])
        for point in points + [e["label_at"]]:
            if len(point) != 2 or not all(math.isfinite(x) for x in point) or not (10 <= point[0] <= width-10 and 70 <= point[1] <= height-65):
                raise ValueError("Edge geometry outside canvas: " + e["id"])
        for a, b in zip(points, points[1:]):
            if a == b or (a[0] != b[0] and a[1] != b[1]):
                raise ValueError("Use nonzero orthogonal segments: " + e["id"])
            for n in nodes.values():
                left, right = n["x"]-n["w"]/2, n["x"]+n["w"]/2
                top, bottom = n["y"]-n["h"]/2, n["y"]+n["h"]/2
                if (a[0] == b[0] and left < a[0] < right and max(min(a[1],b[1]),top) < min(max(a[1],b[1]),bottom)) or (a[1] == b[1] and top < a[1] < bottom and max(min(a[0],b[0]),left) < min(max(a[0],b[0]),right)):
                    raise ValueError("Connector crosses node: " + e["id"] + "/" + n["id"])
        start = [points[1][k]-points[0][k] for k in range(2)]
        end = [points[-1][k]-points[-2][k] for k in range(2)]
        if sum(start[k]*PORTS[e["from_port"]][k] for k in range(2)) <= 0 or sum(end[k]*PORTS[e["to_port"]][k] for k in range(2)) >= 0:
            raise ValueError("Connector enters/leaves endpoint backwards: " + e["id"])
        if math.hypot(*end) < 15:
            raise ValueError("Final segment too short for arrowhead: " + e["id"])
        routes[e["id"]] = points
    return sources, nodes, routes


def render(graph, origin, out, dpi):
    sources, nodes, routes = validate(graph, origin)
    width, height = graph.get("width", 1000), graph.get("height", 650)
    root = ET.Element("{"+NS+"}svg", {"width": str(width)+"pt", "height": str(height)+"pt", "viewBox": f"0 0 {width} {height}"})
    def add(parent, tag, attrs, text=None):
        element = ET.SubElement(parent, "{"+NS+"}"+tag, {k: str(v) for k,v in attrs.items()})
        element.text = text
        return element
    def stroke(parent, points, color, dash="", width=2):
        add(parent,"polyline",{"points":" ".join(f"{x},{y}" for x,y in points),"fill":"none","stroke":"none" if dash else color,"stroke-width":width})
        if dash:
            on, off = map(float,dash.split())
            for a,b in zip(points,points[1:]):
                length=math.dist(a,b)
                for offset in range(0,math.ceil(length),int(on+off)):
                    start=[a[k]+(b[k]-a[k])*offset/length for k in range(2)]
                    end=[a[k]+(b[k]-a[k])*min(offset+on,length)/length for k in range(2)]
                    add(parent,"line",{"x1":start[0],"y1":start[1],"x2":end[0],"y2":end[1],"stroke":color,"stroke-width":width})
    def label(parent, value, x, y, size=18, color="#172C3A", ident=None):
        lines = value.split("\n")
        attrs = {"x": x, "y": y-(len(lines)-1)*size*.65, "font-family": "sans-serif", "font-size": size, "text-anchor": "middle", "fill": color}
        if ident:
            attrs["id"] = ident
        text = add(parent, "text", attrs)
        for i, line in enumerate(lines):
            add(text, "tspan", {"x":x, "dy": 0 if i == 0 else size*1.3}, line)
        return text
    metadata = {"case_id":graph["case_id"], "graph_sha256":sha(origin), "sources":[{k:v for k,v in s.items() if k != "text"} for s in sources.values()], "nodes":graph["nodes"], "edges":graph["edges"], "changes":graph.get("changes",[]), "uncertainty":graph.get("uncertainty",[])}
    add(root,"metadata",{},json.dumps(metadata,ensure_ascii=False))
    add(root,"rect",{"width":width,"height":height,"fill":"white"})
    label(root,graph["title"],width/2,37,24)
    connections = add(root,"g",{"id":"layer-connections"})
    for e in graph["edges"]:
        group = add(connections,"g",{"id":e["id"],"data-source":e["from"],"data-target":e["to"],"data-type":e["type"]})
        add(group,"desc",{},json.dumps(e["evidence"],ensure_ascii=False))
        color, dash = STYLES[e["type"]]
        points = routes[e["id"]]
        stroke(group,points,color,dash)
        tip, prev = points[-1],points[-2]
        length = math.dist(tip,prev)
        dx,dy = (tip[0]-prev[0])/length,(tip[1]-prev[1])/length
        triangle = [tip,[tip[0]-12*dx+4.5*dy,tip[1]-12*dy-4.5*dx],[tip[0]-12*dx-4.5*dy,tip[1]-12*dy+4.5*dx]]
        add(group,"polygon",{"id":e["id"]+"-arrow","points":" ".join(f"{x},{y}" for x,y in triangle),"fill":color})
    entities = add(root,"g",{"id":"layer-entities"})
    for n in nodes.values():
        group = add(entities,"g",{"id":n["id"]})
        add(group,"desc",{},json.dumps(n["evidence"],ensure_ascii=False))
        x,y,w,h = n["x"],n["y"],n["w"],n["h"]
        attrs = {"fill":"#F2F7F8","stroke":"#334C5C","stroke-width":1.7}
        if n["kind"] == "decision":
            diamond=[[x-w/2,y],[x,y-h/2],[x+w/2,y],[x,y+h/2],[x-w/2,y]]
            add(group,"polygon",{**attrs,"stroke":"none","points":" ".join(f"{px},{py}" for px,py in diamond)})
            stroke(group,diamond,"#334C5C",width=1.7)
        else:
            add(group,"rect",{**attrs,"x":x-w/2,"y":y-h/2,"width":w,"height":h,"rx":h/2 if n["kind"] == "terminal" else 2})
            if n["kind"] == "detector":
                add(group,"line",{"x1":x-w/2+7,"x2":x-w/2+7,"y1":y-h/2,"y2":y+h/2,"stroke":"#334C5C","stroke-width":2})
        label(group,n["label"],x,y+6,n.get("font_size",18),ident=n["id"]+"-text")
    labels = add(root,"g",{"id":"layer-labels"})
    for e in graph["edges"]:
        label(labels,e["label"],*e["label_at"],size=15,color=STYLES[e["type"]][0],ident=e["id"]+"-label")
    legend = add(root,"g",{"id":"layer-legend"})
    used = list(dict.fromkeys(e["type"] for e in graph["edges"]))
    for i, kind in enumerate(used):
        x = 30 + i*width/len(used)
        color,dash = STYLES[kind]
        stroke(legend,[[x,height-48],[x+30,height-48]],color,dash)
        label(legend,kind,x+90,height-43,14,color)
    label(root,graph.get("note","Schematic; not to scale"),width/2,height-15,13)
    out.parent.mkdir(parents=True,exist_ok=True)
    svg = out.with_suffix(".svg")
    ET.ElementTree(root).write(svg,encoding="utf-8",xml_declaration=True)
    save(out.with_suffix(".semantic.json"),metadata)
    import fitz
    with fitz.open(svg) as source:
        pdf_bytes = source.convert_to_pdf()
    out.with_suffix(".pdf").write_bytes(pdf_bytes)
    with fitz.open(out.with_suffix(".pdf")) as doc:
        page = doc[0]
        page.get_pixmap(dpi=dpi,alpha=False).save(out.with_suffix(".png"))
        actual_text="".join(page.get_text().split())
        missing_text=[value for value in [graph["title"]]+[n["label"] for n in graph["nodes"]]+[e["label"] for e in graph["edges"]] if "".join(value.split()) not in actual_text]
        checks = {"status":"partial_export" if missing_text else "rendered_needs_visual_review","missing_pdf_text":missing_text,"node_count":len(nodes),"edge_count":len(routes),"dpi":dpi,"page_points":list(page.rect),"pdf_fonts":page.get_fonts(),"pdf_text":page.get_text(),"source_hashes":{k:v["sha256"] for k,v in sources.items()},"graph_sha256":sha(origin),"renderer":"PyMuPDF "+fitz.VersionBind,"artifacts":{ext:{"path":str(out.with_suffix('.'+ext)),"sha256":sha(out.with_suffix('.'+ext))} for ext in ['svg','pdf','png']},"visual_review":"not performed by script"}
        save(out.with_suffix(".checks.json"),checks)
    print(json.dumps({"status":checks["status"],"svg":str(svg),"nodes":len(nodes),"edges":len(routes)}))


def edit(graph, origin, patch_path, out):
    sources,_,_ = validate(graph,origin)
    patch = load(patch_path)
    request = patch["request"]
    if not request["locator"] or not request["quote"] or request["quote"] not in sources[request["source"]]["text"]:
        raise ValueError("Edit request does not resolve to source")
    updated = copy.deepcopy(graph)
    elements = {n["id"]:(n,{"label","x","y","w","h","font_size"}) for n in updated["nodes"]}
    elements.update({e["id"]:(e,{"label","label_at","via","from_port","to_port"}) for e in updated["edges"]})
    changes=[]
    for change in patch["changes"]:
        item,allowed = elements[change["id"]]
        if change["field"] not in allowed:
            raise ValueError("Not a presentation field: " + change["field"])
        changes.append({**change,"before":item.get(change["field"]),"request":request})
        item[change["field"]] = change["value"]
    updated.setdefault("changes",[]).append({"parent_sha256":sha(origin),"patch_sha256":sha(patch_path),"changes":changes})
    for item in updated["sources"]:
        item["path"] = sources[item["id"]]["resolved_path"]
    validate(updated,out)
    save(out,updated)
    print(json.dumps({"status":"edited","out":str(out),"changes":len(changes)}))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=["render","edit","validate"])
    parser.add_argument("graph",type=Path)
    parser.add_argument("patch",type=Path,nargs="?")
    parser.add_argument("--out",type=Path)
    parser.add_argument("--dpi",type=int,default=200)
    args=parser.parse_args()
    try:
        graph=load(args.graph)
        if args.mode == "render":
            if args.out is None or not 72 <= args.dpi <= 600:
                raise ValueError("render requires --out and dpi 72..600")
            render(graph,args.graph,args.out,args.dpi)
        elif args.mode == "edit":
            if args.out is None or args.patch is None:
                raise ValueError("edit requires patch and --out")
            edit(graph,args.graph,args.patch,args.out)
        else:
            validate(graph,args.graph)
            print('{"status":"valid_structure_and_quotes"}')
    except (ValueError,KeyError,OSError,TypeError,ImportError) as error:
        print(json.dumps({"status":"failed","error":str(error)},ensure_ascii=False),file=sys.stderr)
        sys.exit(1)
