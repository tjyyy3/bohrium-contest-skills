---
name: paper-to-academic-ppt
description: Turn supplied papers or research materials into an editable academic presentation using the required template, with page-level evidence, speaker notes, and inspected render previews. Use for creating or adapting a research talk from supplied sources.
---

# Turn research sources into an academic presentation

Build a talk whose slide claims follow the supplied research evidence. Keep the editable deck, evidence map, notes, and rendered previews consistent. This skill organizes existing research into a presentation. It does not supply missing scientific findings or redesign research figures.

For a manual invocation, see the [minimal calling example](references/invocation-example.md). For PDF-to-template jobs, follow the [executable runbook](references/runbook.md). It locates originals by physical page and region, populates inspected template layouts, and checks a real render against the editable file. A worked input fragment and all four CLI calls are included.

After reading the case and before laying out slides, use [academic slide design](references/academic-design.md). It includes a materials-science profile for experimental comparisons. Select that profile from the actual methods and evidence in the sources. Choose equivalent evidence forms for other disciplines.

## Read the actual case before choosing a method

1. Read every field of `/input/case.json` and the provided `task.md`. Locate the task file from the supplied paths or the input directory. Read any referenced input contract. Preserve the original `case_id`, `output_contract` field names, value types, enumerations, and required nesting. Do not substitute this skill's example for that contract.
2. Read the supplied `environment/resources.yaml` when present. Resolve its location from the runtime instructions or provided file inventory. Inspect actual materials, the template, and the starting deck. Labels and filenames do not establish scientific content. A missing manifest is a fact to report, not a file to invent.
3. Record the case constraints in `/app/work/run-contract.md`. Include source scope, audience, language, talk duration, required slide count or limit, template and starting-deck paths, target software and version, fonts, notes requirements, required outputs, and any prohibited changes. Keep exact-count and maximum-count rules distinct. Concrete case instructions take precedence over this workflow.
4. Inspect the available parsing, presentation editing, rendering, and font tools before selecting them. Record the actual versions and commands used. Use tools that can preserve the supplied master/layout structure. A resource name does not prove a package is installed. Do not assume a particular library, Office application, plugin, or network service exists.

The official runtime installs this skill under `/skills/weekly-skill`. Work under `/app/work` and save deliverables under `/app/output`, including `/app/output/result.json`. In another runtime, use the caller's explicit paths. This package requires no author-specific files or plugins. Its offline helper uses PyMuPDF and python-pptx. Rendering uses the case environment's presentation software. Use the available runtime tools and respect its installation and network permissions.

## Keep a deliverable within the budget

The platform allows 64 model requests and 900 seconds, with at most 16,384 tokens per response including reasoning. Use any stricter case limit. Track elapsed time and request usage when exposed. If a counter is unavailable, record that limit instead of inventing a count.

Begin a contract-shaped `result.json` after inspecting the inputs. Mark the run incomplete using the contract's permitted status and failure representation. Save a valid first deck and evidence map as soon as supported content exists. Keep these outputs synchronized after each revision. Reserve about the final 150 seconds and 10 model requests for export, inspection, and packaging. Adjust this reserve to observed rendering time. Do not spend the remainder on cosmetic changes while previews or required outputs are missing.

Keep parsing and rendering bounded. Retry a failed operation only after diagnosing a specific fix. On a missing essential resource or exhausted budget, retain usable artifacts and report the incomplete requirements. Do not claim success solely because a file exists.

## Connect each slide claim to its source

1. Inspect all materials required by the case's full-source rule. Extract text and inspect the actual figure and table pages. Use available OCR for scanned pages only when needed. Treat OCR numbers, symbols, and reading order as uncertain until checked against the page image. If parts remain unreadable, name those parts and their effect on the talk.
2. Record the research question, method, main findings, and limitations from the sources. Separate the authors' findings, cited prior work, hypotheses, and your explanatory synthesis. Keep the source's confidence and scope. Do not turn correlation into causation or a schematic into measured results.
3. Create a working slide ledger before generating the deck. For each slide, record its order, narrative purpose, main claim, source locators, chosen evidence visual, how the audience should read that visual, template layout, notes, and unresolved issues. Use the case's evidence schema when provided. Otherwise keep the ledger in a readable table or JSON and adapt it to the required final format.
4. Give each substantive claim or numerical item a locator that another reader can resolve. Include the source filename or identifier and physical PDF page index. Add printed page numbers, section names, figure numbers, panel letters, table numbers, or equation numbers where available. Use equivalent stable locators for other materials. Distinguish physical PDF pages from printed page labels.
5. Preserve units, signs, precision, sample sizes, uncertainty intervals, conditions, and attribution. Check transferred numbers against the actual source. Label any derived value and retain its source values and calculation. Do not estimate missing numbers from a chart unless the case permits it, and then label the estimate.

Build a sequence around the question, the approach, the decisive evidence, and the conclusion within its limits. Adapt that sequence to the case rather than prescribing a fixed slide count. Give each slide one main message. Keep supporting detail in notes or an allowed appendix. An exact slide count includes any title, references, or appendix slides according to the case's counting rule.

For visuals, inspect the full figure and caption before selecting a panel. Preserve axes, scales, legends, error bars, units, and relevant conditions. Use a source crop when that best preserves the evidence. Do not redraw a chart from guessed values. Mark explanatory diagrams as schematics. Map shortened tables back to the omitted rows or columns and disclose exclusions that affect interpretation.

## Build inside the actual template

Inspect the template's slide size, masters, layouts, placeholder types, theme fonts, colors, title hierarchy, and footer rules. Render representative template or starting-deck pages when possible. Select layouts before adding content. For an adaptation task, edit the supplied starting deck and preserve its required content and structures.

Use the supplied master/layout relationships and placeholders. Do not imitate the template on a new blank deck and call that template compliance. Preserve required page numbering, logos, and footers. If the chosen editor cannot retain these structures, choose another available editor or report the limitation.

When the actual case allows an original design and supplies no required template, use the fallback hierarchy in the design reference. The supplied template, layout relationships, and case rules take precedence whenever specified.

Keep titles, body text, tables, labels, and new explanatory shapes editable as presentation objects. Source figure images can remain images unless the case requires editable plots. Keep their attribution and captions editable. Do not rasterize an entire slide to hide layout problems. Record any required object that remains non-editable.

Shorten or redistribute content before reducing text below the template's readable hierarchy. Split a dense table or move details to notes only when the slide-count rule permits it. Keep figures at their native aspect ratio. If the template has insufficient placeholders, use a compatible existing layout or disclose a permitted minimal addition. Do not silently override case typography or footer rules.

Write notes that help someone give the talk. Explain what to point at, why the evidence supports the claim, the transition to the next slide, and any likely caveat. Avoid repeating the slide text. Put notes into the deck when required and supported. A separate script is a fallback only when the contract allows it. Allocate speaking time within the requested duration and label it as an estimate unless a rehearsal was actually timed.

Keep the slide ledger and final evidence map aligned with the deck's current slide order. Include every delivered slide, including title and transition slides. A transition can cite the supporting slides and their underlying sources. After moving or deleting slides, recheck numbering, internal references, notes, and evidence entries.

## Inspect the saved artifact and its render

1. Reopen the saved editable deck with an available reader. Check slide count, notes, nonempty content, referenced media, and required template/layout relationships. Confirm that text and required objects remain editable. For a PPTX, package structure can support this check, but XML validity alone does not establish a usable presentation.
2. Render the final saved deck to real PDF or PNG previews using an available presentation renderer. Use the specified target software and version when available. Record the renderer, version, fonts, command, result, and exact source deck. A browser picture of generated content is not evidence that the PPTX rendered correctly.
3. Inspect all rendered slides. A contact sheet helps check sequence and consistency, but inspect figures, equations, tables, and text at readable resolution. Check clipped text, overlaps, substituted glyphs, low contrast, missing media, aspect ratios, unreadable labels, footer collisions, and notes visibility where relevant. For native quantitative charts, reopen the deck and compare the plotted data and embedded workbook to the ledger. Inspect the rendered chart independently for label, group, unit, and axis integrity.
4. Compare the rendered scientific claims against the ledger and original source pages. Verify figure/panel identity and numerical items. Structural checks do not certify scientific correctness.
5. Fix the observed failures and rerender affected artifacts. Ensure the delivered previews correspond to the final saved deck. Record any issues that remain, including any unavailable target-software or playback check. Do not describe another renderer's success as proof of compatibility with an untested application.

If rendering is unavailable or fails, keep the editable artifact and report the precise failure. Do not manufacture preview files or certify appearance without a render. If a required template, source, or starting deck is missing, identify that requirement explicitly. An alternative artifact can be useful, but it cannot satisfy an unmet template or source requirement.

## Deliver a case-shaped result

Write valid JSON to `/app/output/result.json`. Preserve `case_id` and every original `output_contract` field. Populate the required structure with actual results. Use contract-permitted values for unknown, missing, and failed items. If the contract leaves failure representation undefined, explain the blocker in its free-text fields and an accompanying run record. Do not invent successful values to satisfy a type. Add fields only when the schema allows them.

Point to actual files under `/app/output`. Include the editable presentation, the required notes, the page-level evidence map, and real rendered previews in the locations and formats the case requests. Keep source identifiers, uncertainty, and status in the required fields. Put extra provenance in a small run record when the schema has no place for it.

Record source and template identifiers or hashes, actual tool versions, used fonts and substitutions, commands or generation scripts, render outcomes, unresolved issues, and substantive content or layout changes. Retain generated scripts and deterministic settings when needed to reproduce the delivered layout. Use the platform's native trace as the execution record. Do not fabricate model traces, comparisons, or benchmark results.

Before finishing, parse `result.json`, check every referenced file, and compare the outputs against each case requirement. Verify the evidence map covers all delivered slides and the previews match the final deck. Report separately what is complete, what is partial, and what could not be checked. Leave a failed requirement visible even when other artifacts are usable.
