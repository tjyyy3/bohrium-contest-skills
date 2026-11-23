---
name: evidence-bound-slide-edit
description: Edit academic PowerPoint slides against source evidence while preserving unrequested slides, native charts, notes and templates. Use for targeted corrections and versioned presentation revision, with real editable output, render checks and rollback.
---

# Evidence-bound slide editing

Deliver the requested academic presentation from the actual source files. The distinctive workflow is a bounded edit transaction: source locator, target object, changed package parts, visual check, saved version. A byte-identical unchanged part proves preservation, not the truth of a scientific claim.

## Read the actual case

Read `/input/case.json`, its `task.md`, all referenced materials and `environment/resources.yaml` if present. Do not infer paper content from a title or domain label. Resolve relative paths against the actual case location. Follow all original `output_contract` keys, output names, audience, duration, page count, slide order and template rules. Work under `/app/work`; save final files under `/app/output`. Allow paths to be relocated for local use.

Inspect the full scientific source, not only an abstract or extracted snippets. For PDF, extract text and render relevant source pages to read figures, equations and legends. Distinguish missing material, unreadable material, unsupported operations and uncertain interpretation. Never invent data, references, replication counts, p values or mechanisms. Label supplied synthetic inputs as synthetic in the deck and report.

Save an early result.json with the real case_id and output-contract fields marked according to the actual schema. Keep status partial until both content and real artifact checks finish. The platform budget is 900 seconds and 64 requests; aim to save the editable deck by the midpoint and reserve the final third for export, inspection and repair. Do not claim a comparison gain from a single run.

## Establish the edit boundary

If the actual task creates a new deck and supplies no starting deck, inspect the supplied template and follow the new-presentation branch below. Do not demand a nonexistent original or claim preserved slides/rollback for a deck that did not exist. Save your first actual draft as the first version. The following baseline workflow applies to editing an existing deck.

Run `python /skills/weekly-skill/pptx_guard.py inspect INPUT.pptx --out before.json`. The script is beside this Skill; substitute that directory when relocated. Inspect every starting slide visually. Resolve displayed page order using `slide_order`, not an assumed slideN filename. Read shape IDs/text, native charts, notes and relationships. Inspect actual master/layout/theme styling and available fonts.

Copy the original to a new version file and record its SHA256. Do not edit the original or overwrite a saved version. Create `edit-plan.json` before editing:

```json
{
  "baseline_sha256": "actual hash from inspect",
  "allowed_parts": [
    {"part": "ppt/slides/slide3.xml", "reason": "requested result correction", "source": "actual source file and section/table/page"}
  ]
}
```

This is an interface illustration, not a supplied answer. Derive every part name from the actual deck. List only parts that the instruction requires. Record per-operation slide ID, shape ID, expected old text/data, new text/data and evidence locator in the change record. Changing a slide does not authorize changing all its shapes or dependencies.

For every chart or other shared part, inspect `referenced_by` in the inventory. Select a native chart through its graphicFrame, c:chart relationship ID and resolved chart part; shape-name prefixes can also match ordinary text boxes. A chart may feed multiple slides; a layout, theme or master usually does. If only one use may change, clone the required dependency and update that slide's relationship with correct content-type registration, or report that operation unsupported. Do not mutate a shared part and label the other slides preserved.

## Make the smallest supported edit

- For text, retain paragraphs, runs, language, font, color and position. Replace the specific existing run(s). Do not assign an entire text frame unless formatting replacement is required. When XML editing, use a namespace-preserving parser such as minidom or lxml and preserve namespace declarations; use XML escaping through the parser, never raw string replacement of unescaped user text.
- For native notes, edit the body notes placeholder, not slide-number or header placeholders. Use actual notes parts. A Markdown sidecar alone is not native speaker notes.
- For a chart, read exact source values, categories, units and uncertainty first. Update both chart caches and its embedded workbook. `python-pptx` `chart.replace_data(CategoryChartData(...))` is suitable for a simple dedicated category-chart workbook. It replaces the entire workbook: inspect worksheets/formulas first; do not use it on custom multi-sheet/formula workbooks. Preserve chart type, series identity, styles, scales and geometry unless asked otherwise. If only a source image exists, cite and embed it; do not infer exact measurements from pixels without an explicit digitization request and uncertainty.
- Use native text, shapes, tables and supported charts. An image of an entire slide is not an editable deck. Keep source images as images when redrawing would invent or lose evidence.

For ordinary edits, either patch the selected ZIP members directly or save a working copy with python-pptx and use `splice` to transplant only the explicitly allowed existing parts. Before splicing, confirm every new value and dependency in those parts. `splice` refuses added/deleted parts and is intentionally not a slide-cloning engine. `python-pptx` can renumber slide parts; if part identities have shifted, do not splice by filename. Use a correct identity mapping or a direct patch. It can also drop unsupported Office elements. Never deliver such losses silently.

```text
python pptx_guard.py splice original.pptx working.pptx edit-plan.json staged.pptx
python pptx_guard.py diff original.pptx staged.pptx edit-plan.json --out preservation.json
```

If a case requires new slides, a full new presentation, adaptation or added relationships, follow that requirement. Start from the actual template and its layouts; build native elements with an available presentation library. Keep a page plan with narrative role, evidence, visual and notes. Organize around research question, method, supported result and limitation as appropriate to the actual material. Do not force that sequence or add pages against the case. Use the inspector and an expanded, justified edit plan to audit final changes; do not use the existing-parts-only splicer for structural edits.

## Verify what stayed unchanged

Run `diff` against the saved original. Exit 0 means no unapproved package-member changes, all internal relationships resolve, XML parses and presentation shape IDs are unique within each part. It is not an Office schema validator or scientific check. Read the report, including any unused allowances. A whole allowed slide part can still contain unwanted changes: compare unchanged shapes' text, runs, positions and sizes inside that slide separately. For chart edits, read back chart cache and embedded workbook cells independently. Check notes text, page count/order and every original contract clause.

Render the actual final PPTX with the installed Office renderer. A typical local command is `soffice --headless -env:UserInstallation=file:///ABSOLUTE/WORK/profile --convert-to pdf --outdir OUTPUT staged.pptx`. Use a fresh profile and output directory to avoid stale results; keep stdout, stderr and exit code. Confirm the produced PDF exists, has the expected page count and contains the expected text. Rasterize every PDF page with PyMuPDF or the provided PDF renderer.

Inspect every final page at readable size. Compare edited pages beside their originals for wrapping, clipping, missing glyphs, misleading scales, chart labels, sources and visual hierarchy. Render the baseline with the same engine/settings and compare untouched pages. Check figures and diagram connections, not just text boxes. Read all sources/captions and notes separately. Fix findings and rerender. If rendering or fonts are unavailable, deliver the editable partial file and name the unverified requirement; do not fabricate previews or claim visual QA.

Demonstrate rollback by `python pptx_guard.py restore saved-v1.pptx rollback-check.pptx EXPECTED_SHA256`. It copies to a new path and checks the original hash. Do not destructively replace the current version.

## Deliver

Deliver the case's required fields and files. Include an actual editable PPTX, real PDF/PNG previews, page evidence mapping for all pages, native notes, source file hashes/locators, change record, preservation report and version/rollback record. Record font names, renderer/library versions, commands and failures. For every page, map claim/figure/data to a precise source location and note whether unchanged, edited or new. Distinguish source statements, derived arithmetic and uncertain interpretation.

Read `USAGE.md` for dependency checks, a minimal invocation example, source attribution and known limitations. Do not bundle local demonstrations or prepared official answers with this Skill.
