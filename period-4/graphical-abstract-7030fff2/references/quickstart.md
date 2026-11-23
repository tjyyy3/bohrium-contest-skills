# Minimal call

Give the Agent a case ID, the actual source files, the requested diagram or revision, and the output requirements.

> Case `block-demo`. A rectangular sample rests on a level support. Draw the two labelled objects and their contact in editable SVG. Export PDF and PNG. The diagram is illustrative.

The source locator for both objects and their contact is the supplied sentence. An illustrative SVG that represents it is below. Save it as `block.svg` in a writable output directory.

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="2.5in" height="1.25in" viewBox="0 0 240 120">
  <rect width="240" height="120" fill="#ffffff"/>
  <g id="sample">
    <rect x="65" y="16" width="110" height="53" fill="#c2e3e0" stroke="#134f51"/>
    <text x="89" y="48" font-family="sans-serif" font-size="16">Sample</text>
  </g>
  <g id="contact-with-support">
    <path d="M 24 69 H 216" stroke="#273a4a" stroke-width="2"/>
    <text x="87" y="98" font-family="sans-serif" font-size="16">Support</text>
  </g>
</svg>
```

Run this command from the Skill directory, substituting the SVG path. Use `python3` on systems where that is the Python interpreter name.

```sh
python scripts/export_svg.py /path/to/block.svg --dpi 300 --expect-text Sample --expect-text Support
```

Example outputs are the editable `block.svg`, a one-page 180 × 90 pt `block.pdf`, a 750 × 375 RGB `block.png` at 300 dpi, and `block.export.json` with dimensions, font checks and SHA-256 hashes. Make the case's result JSON link to actual files and source locators. Inspect the preview before marking the case complete.

The script is original to this Skill. It uses Python 3.10+ and an existing PyMuPDF installation (tested with 1.27.2, API available from 1.24.3). If installation is permitted and needed, `python -m pip install PyMuPDF` in the run's environment provides the optional renderer. PyMuPDF has AGPL and commercial licensing options. The Skill bundles no third-party code or fonts. On an offline run without PyMuPDF, use an installed SVG-to-vector-PDF renderer and rasterize that PDF with an installed tool, for example `pdftoppm -r 300 -png -singlefile block.pdf block`.

Prefer inline vector shapes, explicit dimensions and simple text. Set critical font and anchoring properties directly on SVG text elements if the renderer drops inherited properties. The helper checks the supplied text labels in the PDF, looks for text outside the page, and logs embedded fonts and RGB raster dimensions. Renderers can substitute fonts or handle advanced SVG features differently. Compare the rendered figure with the SVG and the source data. The helper does not validate the scientific claims or certify a print colour profile.
