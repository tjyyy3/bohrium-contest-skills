"""Render an actual PPTX with an installed office renderer, then rasterize all pages."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import fitz
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--soffice", default=shutil.which("soffice") or shutil.which("libreoffice"))
    args = parser.parse_args()
    if not args.soffice:
        raise SystemExit("No office renderer found. Supply --soffice or report a partial result.")
    args.out.mkdir(parents=True, exist_ok=False)
    profile = args.out.resolve() / "office-profile"
    command = [args.soffice, "-env:UserInstallation=" + profile.as_uri(), "--headless", "--convert-to", "pdf", "--outdir", str(args.out.resolve()), str(args.deck.resolve())]
    pdf = args.out / (args.deck.stem + ".pdf")
    receipt = {"command": command, "input_sha256": hashlib.sha256(args.deck.read_bytes()).hexdigest(), "status": "render_failed"}
    try:
        process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        receipt.update(error_type=type(error).__name__, error=str(error))
        (args.out / "render-record.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        raise SystemExit("Office launch/timeout failure; see render-record.json") from error
    receipt.update(exit_code=process.returncode, stdout=process.stdout, stderr=process.stderr)
    (args.out / "render-record.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    if process.returncode or not pdf.is_file():
        raise SystemExit("Office conversion failed; see render-record.json")
    pages = []
    thumbnails = []
    with fitz.open(pdf) as document:
        for index, page in enumerate(document, 1):
            path = args.out / f"slide-{index:02d}.png"
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(path)
            pages.append({"page": index, "png": path.name, "text": page.get_text(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            with Image.open(path) as im:
                thumbnail = im.convert("RGB")
                thumbnail.thumbnail((640, 360))
            thumbnails.append(thumbnail)
        receipt.update(status="rendered_pending_visual_review", pages=len(document), pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(), pymupdf=fitz.VersionBind)
    sheet = Image.new("RGB", (1280, 390 * ((len(thumbnails) + 1) // 2)), "#eeeeee")
    draw = ImageDraw.Draw(sheet)
    for index, thumbnail in enumerate(thumbnails):
        left, top = (index % 2) * 640, (index // 2) * 390
        draw.text((left + 12, top + 4), f"Slide {index + 1}", fill="black")
        sheet.paste(thumbnail, (left, top + 25))
    sheet.save(args.out / "contact-sheet.png")
    (args.out / "render-record.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "rendered-pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
