# Provenance and runtime

Version 1.0, authored for challenge-9034312d in November 2026. The graph schema, renderer and instructions are original task-specific work. No upstream code, illustrations, fonts or example answers are bundled. No API key, paid service or global installation is required.

The project inspected workflow guidance from Anthropic skills at commit 2c5958ecac7cee2b583967a2c4981d0f4a75c579 and EvoSkills at commit 4889c2270af5f9a7658bb6a6709bf37040902006. Their general separation of editable artifacts and actual rendering checks informed the project. This package does not reproduce their code or text. PyMuPDF is an external runtime dependency with its own license, not redistributed here.

Runtime uses Python standard library and PyMuPDF. Local validation used Python 3.12 and PyMuPDF 1.27.2. Target runtime versions must be discovered rather than assumed. PyMuPDF's font fallback is recorded from the exported PDF. The SVG uses editable sans-serif text and does not embed font binaries. If recipient font substitution is unacceptable, supply an allowed font or use the environment's font tools, retain editable text and document the font dependency. Do not silently replace text with paths and call it editable text.

Known scope: small orthogonal technical routes with explicit manual layout. No automatic scientific interpretation, arbitrary apparatus symbol library, 3-D geometry, quantitative charts or mechanism inference. Native external diagrams require targeted editing in their original source as described in SKILL.md. The bundled graph renderer cannot round-trip arbitrary SVG without loss.

Observed local renderer limitations: PyMuPDF 1.27.2 dropped marker arrowheads in a probe, rendered SVG dash attributes as solid strokes, and omitted the closing stroke of a polygon in the fresh local trial. This renderer therefore emits explicit arrowhead polygons, explicit dash line segments and an explicitly closed diamond outline. Retest these visible features when changing renderers.
