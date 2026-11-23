# Declare exact changes to existing objects

Use `object_guard.py inspect` before editing. Match the requested displayed page to its presentation slide ID and part; these are not interchangeable. The recursive object inventory supplies shape IDs and native chart bindings, even when a group or a misleading name appears first.

`edit-plan.json` contains the original file SHA256, source-linked `allowed_parts` and `xml_edits`. Each edit changes one existing XML element's text. `part`, `selector`, `old`, `new`, `source` are required strings. `shape_id` is an optional string that first limits the search to an existing shape. `node_index` is an optional zero-based integer among the selector matches; without it the selector must resolve to exactly one node. `member` optionally names the XML inside an embedded `.xlsx`. Overlapping edits to the same node are rejected. Preserve leading/trailing spaces in old/new text.

Supported namespace prefixes are p (presentation), a (drawing text), r (Office relationships), c (chart), s (spreadsheet). Selectors use Python ElementTree's limited XPath syntax, not full XPath. Inspect actual source XML before choosing one. Do not use shape names as selector keys or assume text lives in one run.

Example interface fragments below are schematic, not scientific answers. Substitute actual paths, IDs, values and locators from the case.

```json
{
  "baseline_sha256": "actual SHA256",
  "allowed_parts": [
    {"part":"ppt/slides/slide8.xml","reason":"requested caption correction","source":"source.md section 2"},
    {"part":"ppt/notesSlides/notesSlide8.xml","reason":"requested native notes correction","source":"source.md section 2"},
    {"part":"ppt/charts/chart4.xml","reason":"requested chart point correction","source":"table.csv row B"},
    {"part":"ppt/embeddings/Microsoft_Excel_Sheet4.xlsx","reason":"same chart embedded data correction","source":"table.csv row B"}
  ],
  "xml_edits": [
    {"part":"ppt/slides/slide8.xml","shape_id":"17","selector":".//a:t","node_index":0,"old":"old caption","new":"corrected caption","source":"source.md section 2"},
    {"part":"ppt/notesSlides/notesSlide8.xml","shape_id":"3","selector":".//a:t","node_index":0,"old":"old notes","new":"corrected notes","source":"source.md section 2"},
    {"part":"ppt/charts/chart4.xml","selector":".//c:ser/c:val/c:numRef/c:numCache/c:pt[@idx='1']/c:v","old":"8","new":"7","source":"table.csv row B"},
    {"part":"ppt/embeddings/Microsoft_Excel_Sheet4.xlsx","member":"xl/worksheets/sheet1.xml","selector":".//s:c[@r='B3']/s:v","old":"8","new":"7","source":"table.csv row B"}
  ]
}
```

The actual chart may have multiple series, repeated values or different cell positions. Narrow the chart selector using an existing series index, for example `.//c:ser[c:idx...]` is not supported by ElementTree; instead locate actual supported nodes and use an explicit node_index among matches after inspecting ordering. Record why that node is the requested series. Verify the chart formula points to the worksheet/cells being changed. A guessed B3 is not a binding.

For notes, inspect the actual body placeholder and edit only its text nodes. Preserve header and page-number placeholders. For workbook correction, leave formulas, styles, other sheets and unrequested cells intact. A full `replace_data` may rewrite metadata or workbook structure and fail this exact scope. Use a namespace-preserving XML editor for the smallest correction when safe; this verifier reads XML and does not itself perform edits.

```text
python object_guard.py verify original.pptx revised.pptx edit-plan.json --out preservation.json
```

The report separately records changed parts, checked XML and chart binding identities. A same-page drift returns `out_of_scope_or_missing_edit` with shape IDs. A chart target swap returns `chart_bindings_changed`, even if both target chart files exist. A missing/wrong old value or an ambiguous target fails rather than editing a nearby value. An unchanged deck fails a nonempty requested-change plan. Every declared change must have different old/new text. Both inspectors check the root Office relationship, presentation root and declared main content type; a valid zero-slide template is permitted, but an ordinary ZIP is not. Malformed input returns a structured invalid-input issue. Every nonzero exit means the revision is not verified.

The comparison ignores XML indentation and namespace spelling but retains element names/order, attributes and text contents, including whitespace within text nodes. It is not a pixel comparison. Chart cache/workbook agreement and truth of source mappings still require direct readback; previews must be rendered from the delivered PPTX.
