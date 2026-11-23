# Use and limits

Version 1.0, 2026-11-11. This Skill and pptx_guard.py are original task-specific work. The helper runs with Python 3.10+ standard library. Actual artifact editing needs an installed Office-capable tool or a presentation library. Local validation uses Python 3.12, python-pptx 1.0.2, LibreOffice, PyMuPDF 1.27.2 and Pillow 12.1.1. These are validation versions, not mandatory exact pins. Read the runtime resource inventory and test imports first. No API key, online service, global installation or personal file is required. If an authorized environment needs dependencies, its maintainer can install python-pptx, PyMuPDF and LibreOffice; the Skill does not install software itself.

## Minimal call example

Illustrative input only: a user's case.json requests correction of one native chart and accompanying slide text in an existing 5-page deck; the attached source table contains authoritative values. Give the Agent this Skill, the actual case.json/task.md, source and deck. Ask it to make the specified correction, retain untouched pages/template and return the original output_contract.

1. Inspect the deck and read the source table. Run `python pptx_guard.py inspect starting.pptx --out before.json`.
2. Save `versions/v1.pptx`. Write the baseline hash and actual slide/chart/workbook/notes parts into edit-plan.json, with source locators and reasons. Keep the per-shape operation record alongside it.
3. Produce a working copy using an installed library. For simple native category charts, use `CategoryChartData`, preserve categories/series and call the target chart's `replace_data`. Inspect the workbook first and verify it after the edit. Edit target text runs and native notes.
4. If package part identities remain unchanged, run `python pptx_guard.py splice starting.pptx working.pptx edit-plan.json final.pptx` and `python pptx_guard.py diff starting.pptx final.pptx edit-plan.json --out preservation.json`.
5. Render final.pptx and the baseline to real PDFs, rasterize every page, inspect and compare. Check numerical values against the source and unchanged objects within the edited slide.
6. Test restore to a new filename using the saved version's hash. Deliver case-required structured results plus editable deck, PDF, page PNGs and audit records.

Illustrative result keys, subject to the actual contract: case_id, status, presentation, pdf, previews, page_evidence, changes, preservation, rollback, sources, uncertainty. All artifact paths must point to real files. Do not copy example labels or values as case answers.

The following is schematic interface output, not a result from an official case. Replace every example path and locator with artifacts produced from the actual input, and retain that case's required keys and types.

```json
{
  "case_id": "illustrative-edit",
  "status": "complete",
  "presentation": "/app/output/revised.pptx",
  "pdf": "/app/output/revised.pdf",
  "previews": ["/app/output/slide-01.png"],
  "page_evidence": "/app/output/page-evidence.json",
  "changes": "/app/output/changes.json",
  "preservation": "/app/output/preservation.json",
  "rollback": "/app/output/versions.json",
  "sources": [{"file": "provided-source.pdf", "locator": "actual table/page read during execution"}],
  "uncertainty": []
}
```

## Limits that affect decisions

- `inspect` lists top-level shapes and recursively reads their text; nested group shape targeting requires deeper inspection. It does not certify OOXML schemas, links' scientific content, font availability, animation playback or Microsoft PowerPoint rendering.
- `diff` proves byte preservation outside the allowed set. It deliberately rejects serialization churn outside that set. It cannot detect an unrequested edit inside an allowed slide or workbook; compare those objects/cells separately.
- `splice` is an existing-part transplant, not a dependency clone. It preserves unselected members even when a working library rewrote them. Do not select a part whose new content references an unselected changed dependency. Use full relationship inspection and actual rendering afterward.
- Existing macros, OLE objects, SmartArt, complex chart workbooks and linked content need tools that preserve them. If preservation is unproven, report partial and retain the original. Do not flatten them to claim success.
- A PDF/PNG render tests one renderer. Native editability needs object inspection; actual application playback should be reported only if tested.

## Method provenance

The design takes general workflow guidance from these fixed upstream versions. No upstream code, templates, figures or prose passages are included in this candidate.

- Anthropic `anthropics/skills`, commit `2c5958ecac7cee2b583967a2c4981d0f4a75c579`, `skills/pptx/SKILL.md`, Apache-2.0 at that skill's LICENSE.txt. Relevant ideas: native charts/notes, targeted OOXML editing, shared chart dependencies and real render inspection. Source: https://github.com/anthropics/skills/blob/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills/pptx/SKILL.md
- EvoScientist `EvoSkills`, commit `4889c2270af5f9a7658bb6a6709bf37040902006`, `skills/academic-slides/references/slide-design.md`, Apache-2.0, Copyright 2026 EvoScientist. Relevant ideas: readable academic figures, source attribution, consistent templates. Page count and actual source evidence override generic design heuristics. Source: https://github.com/EvoScientist/EvoSkills/blob/4889c2270af5f9a7658bb6a6709bf37040902006/skills/academic-slides/references/slide-design.md

This candidate adds an explicit source-linked changed-part allowance, byte-level preservation check and non-destructive hash-checked rollback. Local synthetic trials do not establish superiority over other tools or success on undisclosed official cases.
