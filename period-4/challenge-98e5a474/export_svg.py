"""Export a self-contained SVG to vector PDF and a PNG rendered from that PDF."""

import argparse
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def export(svg_path, output_dir, dpi, size_mm, chromium_path):
    import pymupdf
    from playwright.sync_api import sync_playwright

    source = svg_path.read_text(encoding="utf-8-sig")
    if "<!DOCTYPE" in source:
        raise ValueError("Use a self-contained SVG without a DOCTYPE")
    root = ET.fromstring(source)
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError("Expected an SVG document")
    if size_mm is None:
        dimensions = [root.get(key, "") for key in ("width", "height")]
        if any(not re.fullmatch(r"(?:\d+(?:\.\d+)?|\.\d+)mm", value) for value in dimensions):
            raise ValueError("SVG has no explicit millimeter size. Supply --size-mm WIDTH HEIGHT.")
        size_mm = [float(value[:-2]) for value in dimensions]
    if dpi <= 0 or any(not math.isfinite(value) or value <= 0 for value in size_mm):
        raise ValueError("Size and DPI must be positive and finite")
    width, height = size_mm
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{svg_path.stem}.pdf"
    png_path = output_dir / f"{svg_path.stem}.png"
    html = f"""<!doctype html><meta charset="utf-8"><style>
        @page {{ size: {width + 1}mm {height + 1}mm; margin: 0; }}
        html, body {{ margin: 0; padding: 0; }}
        body > svg {{ display: block; width: {width}mm !important; height: {height}mm !important; }}
    </style><body></body>"""

    blocked = set()

    def block_request(route):
        blocked.add(route.request.url)
        route.abort()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=chromium_path,
            args=["--disable-background-networking", "--disable-component-update"],
            timeout=20000,
        )
        browser_version = browser.version
        try:
            page = browser.new_page(java_script_enabled=False, offline=True, service_workers="block")
            page.route("**/*", block_request)
            page.set_content(html)
            page.evaluate("""source => {
                const parsed = new DOMParser().parseFromString(source, "image/svg+xml");
                const svg = document.importNode(parsed.documentElement, true);
                document.body.append(svg);
            }""", source)
            page.evaluate("() => document.fonts.ready.then(() => true)")
            pdf_data = page.pdf(prefer_css_page_size=True, print_background=True, display_header_footer=False)
        finally:
            browser.close()
    if blocked:
        raise ValueError("SVG requests linked resources. Embed required assets for offline export.")

    with pymupdf.open(stream=pdf_data, filetype="pdf") as pdf:
        if len(pdf) != 1:
            raise ValueError(f"Expected one PDF page, rendered {len(pdf)}")
        page = pdf[0]
        # Print with spare space at the right and bottom, then set the requested
        # paper size without re-scaling the artwork or losing Chromium's vectors.
        width_pt, height_pt = (value * 72 / 25.4 for value in size_mm)
        media = page.mediabox
        if media.width < width_pt or media.height < height_pt:
            raise ValueError("Chromium's printed page is smaller than the requested canvas")
        page.set_mediabox(pymupdf.Rect(media.x0, media.y1 - height_pt, media.x0 + width_pt, media.y1))
        pdf_mm = [value * 25.4 / 72 for value in (page.rect.width, page.rect.height)]
        if any(abs(actual - requested) > 0.01 for actual, requested in zip(pdf_mm, size_mm)):
            raise ValueError(f"PDF page size differs from requested {size_mm} mm: {pdf_mm} mm")
        pixmap = page.get_pixmap(dpi=dpi, alpha=False)
        png_data = pixmap.tobytes("png")
        pdf_data = pdf.tobytes()
        fonts = sorted({item[3] for item in page.get_fonts()})
    pdf_path.write_bytes(pdf_data)
    png_path.write_bytes(png_data)
    return {
        "input_svg": svg_path.as_posix(), "pdf": pdf_path.as_posix(), "png": png_path.as_posix(),
        "requested_mm": size_mm, "pdf_mm": pdf_mm, "png_px": [pixmap.width, pixmap.height],
        "dpi": dpi, "pdf_fonts": fonts, "chromium": browser_version, "pymupdf": pymupdf.__version__,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svg", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--size-mm", type=float, nargs=2, metavar=("WIDTH", "HEIGHT"))
    parser.add_argument("--chromium", help="Use an installed Chromium-family browser executable")
    args = parser.parse_args()
    try:
        receipt = export(args.svg, args.output_dir, args.dpi, args.size_mm, args.chromium)
    except (ImportError, OSError, RuntimeError, ValueError, ET.ParseError) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")
    print(json.dumps(receipt, ensure_ascii=True))


if __name__ == "__main__":
    main()
