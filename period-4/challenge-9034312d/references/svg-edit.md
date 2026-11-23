# Edit an existing SVG without reconstructing it

Use `scripts/svg_edit.py` for an existing UTF-8 SVG. It edits only the value bytes of selected attributes or leaf `<text>` / `<tspan>` elements. It never serializes the whole document. Namespace prefixes, comments, metadata, styles, definitions and unselected branches retain their original bytes. XML and SVG ID validation still run before and after the change.

First inventory the actual file:

```sh
python scripts/svg_edit.py inspect /input/original.svg --out /app/work/svg-inventory.json
```

Read the scientific source and the edit request. Identify the exact instance by ID and source locator, especially when two parts share a label. Build a patch with the SHA256 from the inventory. Each attribute must already exist. Attribute fields use the bare attribute name. `text` edits a leaf text element; target individual spans in a multiline label.

```json
{
  "source_sha256": "COPY_THE_ACTUAL_INPUT_SHA256",
  "request": {"path":"request.txt","sha256":"COPY_THE_ACTUAL_REQUEST_SHA256","locator":"R1","quote":"Rename the annotation for meter A to Check A."},
  "evidence_files": [{"path":"connections.json","sha256":"COPY_THE_ACTUAL_EVIDENCE_SHA256"}],
  "changes": [{"id":"meter-a-note","field":"text","before":"Check","after":"Check A"}]
}
```

This JSON is an illustrative interface, not a prepared answer. The source and request hashes must be computed from actual files. Request and evidence paths resolve relative to the patch. Keep source bytes immutable and use fresh output names:

```sh
python scripts/svg_edit.py apply /input/original.svg /app/work/patch.json --out /app/output/revised.svg
python scripts/svg_edit.py verify /input/original.svg /app/output/revised.svg /app/output/revised.edit.json
python scripts/svg_export.py /input/original.svg --out /app/output/original
python scripts/svg_export.py /app/output/revised.svg --out /app/output/revised
```

`apply` saves an edit receipt with before/after decoded values, original byte spans, output byte spans and hashes. `verify` reverses those spans and requires byte equality to the original. Unrelated post-edit changes fail this check. The receipt lists untouched ID-bearing subtrees whose original bytes were compared directly. This does not certify the meaning or scientific correctness of an approved edit.

## Moving a part

A move is a set of geometry changes, not a topology change. Preserve instance IDs, port IDs, connection types, source references and arrow direction. Translate only the intended component and explicitly update incident connector vertices, arrowhead geometry and labels if needed. Do not shift an entire enclosing branch to move one part. Determine the global coordinates of each numbered port after transforms. Independently compare each connector's start and end to those ports and its arrow tip to its destination. Inspect the picture as well. A group transform alone can leave lines disconnected.

Use the source connection table as the authority. Enumerate `(connection ID, source instance, source port, destination instance, destination port, type, source locator)`. Same-model instruments are distinct instances. Never replace port identity with merely "left" or "right". For a graphical input, record original figure bounding boxes and explain what was transcribed. Store that semantic mapping beside the SVG. Do not alter protected semantic `data-*` attributes using presentation patches.

For explicit circular port elements and absolute M/L paths or polylines with translation transforms, run `scripts/svg_ports.py revised.svg connections.json --out ports.json`. The table has root `connections`, each containing `id`, `from`, `from_svg`, `to`, `to_svg`, `type`, `locator`. The readable `from` and `to` name instance.port; the `_svg` fields name actual port element IDs. Derive this table from supplied material. The checker compares actual global endpoint coordinates and any existing data-from-port/data-to-port/data-type attributes to that source table. It fails unsupported geometry rather than claiming to check it. For curves, matrix transforms or inferred ports, use a suitable native geometry inspection and report the method; do not simplify scientific connections to fit this checker.

## Supported changes and limits

The allowlist covers position, size, path/point geometry, transform, fill/stroke, opacity and text styling. It excludes IDs, topology attributes, metadata, definitions, descriptions, root document properties and arbitrary XML insertion. The request must support every changed field. A source or before-value mismatch fails without writing a revision. Duplicate IDs, overlapping edits, repeated fields and DTD inputs are rejected. Unsupported source structures remain intact and need a native editor or a clearly reported partial result.

`svg_export.py` uses an existing Chromium-based browser to print the actual SVG with its styles, markers and transforms, then PyMuPDF to rasterize that PDF. It records hashes, page size, fonts and missing text. Browser rendering is used because the earlier PyMuPDF SVG converter omitted some marker, dash and polygon-stroke features. Set `--browser /path/to/executable` if discovery fails. No packages or browser are installed. No sandbox flags are disabled. If no suitable renderer exists, retain the revised SVG and receipt and report exports as missing. External assets must be resolved by a separate documented workflow. The original SVG is never rewritten for export.

The export wrapper uses source width/height or viewBox dimensions and a single PDF page. Examine both renders for glyphs, clipping, arrows and label overlap. Check that unchanged branches also have unchanged rendered pixels, allowing only a documented edit-region mask. Do not treat XML preservation alone as proof that connected geometry remained correct.
