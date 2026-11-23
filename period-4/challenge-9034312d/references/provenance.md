# Provenance and runtime

Version 2.0, authored for challenge-9034312d in November 2026. The graph schema, renderer, byte-preserving native SVG editor, PDF-span collision audit and instructions are original task-specific work. No upstream code, illustrations, fonts or example answers are bundled. No API key, paid service or global installation is required.

The project inspected workflow guidance from Anthropic skills at commit 2c5958ecac7cee2b583967a2c4981d0f4a75c579 and EvoSkills at commit 4889c2270af5f9a7658bb6a6709bf37040902006. Their general separation of editable artifacts and actual rendering checks informed the project. This package does not reproduce their code or text. PyMuPDF is an external runtime dependency with its own license, not redistributed here.

Runtime uses Python standard library and PyMuPDF. Local validation used Python 3.12 and PyMuPDF 1.27.2. Target runtime versions must be discovered rather than assumed. PyMuPDF's font fallback is recorded from the exported PDF. The SVG uses editable sans-serif text and does not embed font binaries. If recipient font substitution is unacceptable, supply an allowed font or use the environment's font tools, retain editable text and document the font dependency. Do not silently replace text with paths and call it editable text.

Known scope: small orthogonal technical routes with explicit manual layout. No automatic scientific interpretation, arbitrary apparatus symbol library, 3-D geometry, quantitative charts or mechanism inference. Native external diagrams require targeted editing in their original source as described in SKILL.md. The bundled graph renderer cannot round-trip arbitrary SVG without loss.

The separate native SVG path now supports exact-ID leaf text and existing presentation attributes. Its exact byte-splice and inverse verification are original implementations. It preserves comments, namespace spelling and unmodified XML bytes. Native SVG rendering uses an existing Chromium browser, then PyMuPDF rasterizes the actual PDF. The browser and fonts are not redistributed. If launching the browser needs host permission, request it through the host mechanism; do not disable the sandbox or change global configuration. A browser process warning is retained even when its PDF can be reopened and inspected.

Methods actually consulted on 2026-11-23:

- Python 3.12 [Expat callbacks and byte positions](https://docs.python.org/3.12/library/pyexpat.html) informed how the editor locates original XML spans. Python software/documentation use PSF License v2; documentation examples are also available under 0BSD from Python 3.8.6. No example code was copied. [License](https://docs.python.org/3.12/license.html).
- [Chrome Headless documentation](https://developer.chrome.com/docs/automation-and-testing/headless) informed unattended rendering with an existing browser. Documentation is CC BY 4.0 and example code Apache-2.0. No documentation text, browser binary or sample implementation is bundled.
- [PyMuPDF page-image recipe](https://pymupdf.readthedocs.io/en/latest/recipes-images.html) informed actual-PDF rasterization with explicit DPI. PyMuPDF/MuPDF have AGPL and commercial licensing options. They remain separately installed runtime dependencies. [License statement](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright).

SVG text-box auditing compares actual PDF spans to ID-bearing SVG text. It reports collision IDs and overlap rectangles. Anonymous labels, duplicate text matches, graphical overlap and scientific meaning still require inspection; the audit does not certify the whole figure. The original graph workflow remains available for creating diagrams from source material.

Observed local renderer limitations: PyMuPDF 1.27.2 dropped marker arrowheads in a probe, rendered SVG dash attributes as solid strokes, and omitted the closing stroke of a polygon in the fresh local trial. This renderer therefore emits explicit arrowhead polygons, explicit dash line segments and an explicitly closed diamond outline. Retest these visible features when changing renderers.
