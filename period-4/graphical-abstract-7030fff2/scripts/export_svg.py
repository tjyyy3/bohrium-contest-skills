"""Export one self-contained SVG as vector PDF and an RGB PNG."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def export(source, dpi, expected_labels):
    import pymupdf

    svg_data = source.read_bytes()
    svg = ET.fromstring(svg_data)
    ns = "{http://www.w3.org/2000/svg}"
    if svg.tag != ns + "svg":
        raise ValueError("Expected an SVG root element with the SVG namespace.")
    ids = [node.get("id") for node in svg.iter() if "id" in node.attrib]
    if len(ids) != len(set(ids)):
        raise ValueError("SVG element IDs must be unique.")

    with pymupdf.open(stream=svg_data, filetype="svg") as svg_doc:
        pdf_data = svg_doc.convert_to_pdf()
    with pymupdf.open(stream=pdf_data, filetype="pdf") as pdf_doc:
        if len(pdf_doc) != 1:
            raise ValueError("The graphical abstract must export as a single PDF page.")
        page = pdf_doc[0]
        text = " ".join(page.get_text().split())
        missing = [label for label in expected_labels if " ".join(label.split()) not in text]
        if missing:
            raise ValueError(f"Expected selectable PDF text missing: {missing!r}")

        bounds = page.rect + (-0.25, -0.25, 0.25, 0.25)
        outside = [
            span["text"]
            for block in page.get_text("dict", clip=pymupdf.INFINITE_RECT())["blocks"]
            for line in block.get("lines", [])
            for span in line["spans"]
            if not bounds.contains(pymupdf.Rect(span["bbox"]))
        ]
        if outside:
            raise ValueError(f"PDF text extends beyond the page: {outside!r}")

        fonts = [
            {"pdf_name": name, "embedded": bool(pdf_doc.extract_font(xref)[-1])}
            for xref, _, _, name, *_ in page.get_fonts()
        ]
        pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
        png_data = pixmap.tobytes("png")
        receipt = {
            "renderer": f"PyMuPDF {version('PyMuPDF')}",
            "svg": {
                "size": [svg.get("width", ""), svg.get("height", "")],
                "view_box": svg.get("viewBox", ""),
                "unique_ids": len(ids),
                "text_elements": sum(1 for _ in svg.iter(ns + "text")),
                "image_elements": sum(1 for _ in svg.iter(ns + "image")),
            },
            "pdf": {
                "pages": len(pdf_doc),
                "size_pt": [page.rect.width, page.rect.height],
                "fonts": fonts,
                "vector_paths": len(page.get_drawings()),
                "embedded_images": len(page.get_images()),
                "confirmed_selectable_labels": expected_labels,
                "off_page_text_spans": outside,
            },
            "png": {
                "size_px": [pixmap.width, pixmap.height],
                "dpi": [pixmap.xres, pixmap.yres],
                "colour_space": pixmap.colorspace.name,
            },
        }

    pdf_path = source.with_suffix(".pdf")
    png_path = source.with_suffix(".png")
    receipt["sha256"] = {
        source.name: sha256(svg_data).hexdigest(),
        pdf_path.name: sha256(pdf_data).hexdigest(),
        png_path.name: sha256(png_data).hexdigest(),
    }
    pdf_path.write_bytes(pdf_data)
    png_path.write_bytes(png_data)
    receipt_path = source.with_suffix(".export.json")
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="SVG file. Exports are written alongside it.")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--expect-text", action="append", default=[], help="Expected selectable PDF label, repeatable.")
    args = parser.parse_args()
    if args.source.suffix.lower() != ".svg" or args.dpi < 1:
        parser.error("Provide an .svg file and a positive DPI.")
    try:
        print(export(args.source, args.dpi, args.expect_text))
    except (ValueError, RuntimeError, OSError, ImportError, ET.ParseError) as exc:
        parser.exit(1, f"Export failed: {exc}\n")
