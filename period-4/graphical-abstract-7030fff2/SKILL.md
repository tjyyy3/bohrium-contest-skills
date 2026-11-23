---
name: graphical-abstract
description: Create or revise a one-page scientific graphical abstract from supplied research materials. Use for editable schematics, mechanisms, workflows or charts that need traceable entities, relationships and data, plus inspected SVG, PDF and PNG exports.
---

# Graphical Abstract

Version 0.1.0. Run as an Agent workflow with the actual work order and its sources. Use [the minimal call](references/quickstart.md) for the local invocation and the bundled SVG exporter.

## Establish the case and its evidence

1. In Harbor, read `/input/case.json`, the supplied `task.md` and every referenced source needed for the task. Read the actual source even if its filename or domain label suggests an answer. Open a PDF at the relevant pages or figures to verify the extraction, especially symbols, arrows, captions and table headers. Use the exact `case_id`, output names, units and required fields of the original `output_contract`. Use `/app/work` for drafts and `/app/output` for actual deliverables and `result.json`. Resolve bundled resources relative to this Skill, normally installed at `/skills/weekly-skill`.
2. Select the research question, method, central evidence and narrowest supported conclusion. Name the limitation that affects interpretation, in the figure when needed. For each key item, record a stable figure element ID, its intended meaning, source file and version, and a locator such as page and panel, table and row, or data key. Record any transformation, units, group, condition and uncertainty that change how it reads. Link the resulting ledger to the figure and return it with the result.
3. Give arrows a specific meaning. Check direction, endpoints, ordering and location against the source. Distinguish spatial adjacency, transfers, time order, association and established causation by label or legend as needed. Mark schematic scale when the geometry is illustrative. Plot from the actual data rows with their stated units and grouping. Check axes, the plotted positions and legend against those rows. State what intervals or error bars mean. When only a qualitative finding is supplied, use a labelled qualitative encoding and record the missing numbers.

## Compose and revise the figure

Build one page with an obvious reading order and a visual focus on the key evidence. Use the requested figure type. For a text-to-figure task, a short question heading, a schematic or flow for the method, a result panel, and a short finding and scope line make a useful starting layout. Place labels with their marks and encode groups or states with text or shapes as well as colour.

For new SVGs, give the root an explicit size and viewBox. Use named groups/layers, stable IDs, real text and independent vector marks for labels, nodes, arrows, axes and data. Keep critical labels legible at the requested display size. Keep chart inputs and derived values available for revision. For complicated SVG or native formats, use an installed renderer that retains their features. The bundled helper handles simple, self-contained SVG.

For an edit, open the supplied source and record its version/hash before touching it. Write down the requested changes and identify the affected layers, IDs or native objects. Edit a copy of the source. Preserve unrequested content, source data, units, process direction and stable IDs. Diff the relevant objects and evidence before re-exporting. Record the request, versions, changed IDs, comparison method, protected content checked, and any manual confirmation actually obtained. If the only starting artifact is a raster or flattened PDF, state the reconstruction scope and the elements that cannot be recovered.

## Export, inspect and return

Export the actual editable source and requested formats, including real PDF and PNG previews when required. Try the [SVG exporter](references/quickstart.md) for native SVG shapes and text. Reopen the SVG and inspect both rendered outputs at the target scale. Check page count and size, PNG dimensions and DPI, font rendering and embedding, colour, clipping, label and legend readability, and consistency of revisions. Check labels against nearby lines and marks. Verify that editable text and marks are available in the source. Record tool/version, settings and the checks actually performed.

Write `result.json` with the case ID, every case-specific contract field, and the actual paths, source locations, status, uncertainties and change records. Use the case's field names and allowed status values. If the case does not define a schema, return `case_id`, `status`, `main_result`, `artifacts`, `element_sources`, `uncertainty`, and `changes`. Distinguish absent source material, ambiguous interpretation and failed execution. Keep valid partial files with a precise account of unmet requirements. For example, if a font substitutes, inspect glyphs and spacing before choosing a supported font and re-exporting. If a renderer fails, report the attempted command and retain the editable draft while using an available alternative. Export checks establish properties of the files. Compare the science to the supplied sources independently.
