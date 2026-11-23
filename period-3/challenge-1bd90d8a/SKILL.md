---
name: source-linked-scientific-charts
description: Generate and revise scientific data figures from actual tables, with editable vector text, traceable marks, explicit uncertainty, and rendered exports. Use for source-value charts, multi-panel data plots, and source-preserving figure edits.
---

# Source-linked scientific charts

## Read the real case

Read `/input/case.json`, `task.md`, the original `output_contract`, and `environment/resources.yaml` when present. Resolve and inspect every referenced input. Work under `/app/work`; put deliverables under `/app/output`. Locate this Skill relative to its installed directory, usually `/skills/weekly-skill`. Preserve the original case ID and every required output field. Do not replace the case contract with the helper's diagnostic JSON.

Inventory actual tables, existing figures, plotting scripts, source papers, requested changes, and export requirements. Read table headers and representative rows. For a PDF source, cite page and panel and inspect the page image when extraction omits symbols or layout. Source content takes precedence over a misleading domain label. Never invent values from a paper title or infer error bars from a raster image without labelling digitization uncertainty.

Write a short figure plan covering the scientific question, each panel's role, source file and version, field mapping, units, raw versus summary data, grouping, independent sampling unit, uncertainty meaning, and requested edit. State unresolved information. Proceed on supported panels and mark unsupported parts partial.

## Choose the truthful encoding

- Plot actual supplied values. Keep units and normalization explicit. Do not silently filter rows, average replicates, subtract baselines, impute values, or transform axes.
- For continuous relationships use scatter or ordered line plots. Connect points only when the connecting order is meaningful. Show independent observations when available. For bars use a zero baseline unless a documented scientific reason requires another encoding.
- A mean with SD depicts sample spread. SEM and confidence intervals answer different questions. Never rename them. If the input contains summary statistics, plot those statistics with their stated definition and sample size; do not treat means as replicate measurements.
- Show supplied significance annotations only when the contrast, statistical method, multiplicity correction and source are supplied. Do not calculate or invent significance for this drawing task.
- For repeated measurements, preserve subject identifiers. Multiple measurements from one subject do not increase independent n. Make missingness and differing n visible.
- Keep comparable panels' scales and series mappings consistent where scientifically appropriate. A heatmap needs a labelled color scale, declared transformation, and visible missing-value policy. Do not force every input into the helper's supported plot types.

## Generate or edit

For long-form CSV data with explicit numeric x and y fields, use `chart.py` and the interface in [interface.md](interface.md). The helper supports raw scatter and line plots, or explicitly requested mean-with-SD plots with raw observations. It outputs SVG with live text, PDF with embedded TrueType fonts, PNG, mark-level mapping, calculation records, packaged source, and a diagnostic result. It does not choose statistics, infer units, or handle arbitrary supplied artwork.

For unsupported data or chart types, write a small plotting script in `/app/work` using available scientific tools. Apply the same source and validation contract. Use matplotlib `svg.fonttype='none'` and `pdf.fonttype=42`, stable artist `gid` values, and an explicit font that covers all glyphs. Do not convert scientific text into paths merely to hide font failures. Preserve a rerunnable script, inputs, and configuration alongside the editable figure.

For an existing editable figure, first copy the source to a new output location and record its hash. Change only requested elements in the copy or its generating configuration. Preserve unrequested panels, scientific content, series identities, units, values, and provenance. For native SVG edits preserve existing element IDs and text elements, and record before/after attributes for changed IDs. Retain linked assets. Re-render and compare the unchanged elements. Never label an unrelated redraw as a source-preserving edit.

For helper-generated charts, make a new configuration containing the style changes and invoke `--previous` against the previous output directory. The helper compares data hashes and semantic mappings. Keep both versions. Record requested changes and verify that changed appearance did not change numerical content. If values must change, identify that as a data revision, with both source versions and a new calculation record.

## Inspect the actual exports

1. Recompute at least one value per series from source rows independently. Check all marks against the mapping, including uncertainty endpoints and zero baselines.
2. Open the actual PDF and PNG, and inspect every panel at final size. Check axis units and exponents, ticks, error-bar meanings, sample counts, legend identities, labels, alignment and overlap. Automated file checks cannot establish scientific correctness or legibility.
3. Confirm editable SVG contains text and separate data groups. Check PDF text extraction and font embedding. Check figure dimensions and raster pixel dimensions. State RGB output honestly; do not claim CMYK or journal compliance without checking the requested production contract.
4. Check that every mapped ID exists in SVG and every data element has a source record. Check raw-file hashes after editing. Test a source lookup in both directions.
5. Repair discovered errors and re-render. Keep actual command logs and observed failures. Never invent traces, reviewer approvals, benchmark scores, or hidden-case results.

## Deliver and describe limits

Deliver editable SVG, rerunnable plotting source and configuration, source data or a permitted stable reference, PDF, PNG, source-to-element mapping, calculations, change record, and export checks. If the case asks for another native format, deliver it or report partial status.

Write `/app/output/result.json` with the original `case_id` and all original output-contract fields. Include actual artifact paths, source hashes and locators, changes, validation, status and uncertainty in the contract's fields or additional fields where allowed. Distinguish missing material, unsupported operation, runtime failure, and unverified scientific interpretation. Never upgrade the helper's `rendered_pending_visual_review` status without inspecting the files. Save an honest partial result early if a dependency or source is missing.

The synthetic example in the interface documents invocation only. It is not a scientific finding or an official case answer. This Skill requires no model API, image generator, cloud service, or network access.
