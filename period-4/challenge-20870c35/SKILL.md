---
name: evidence-timed-academic-talk
description: Organize supplied research into an audience-specific, time-budgeted academic presentation with editable template slides, page-level evidence, speaker notes and source-grounded question preparation. Use for research talks, lab meetings, defenses and review presentations.
---

# Organize an evidence-grounded academic talk

The deliverable is a talk the specified audience can follow within its allotted time. Page titles, evidence, speaker notes and answers must express the same bounded claims. Do not write a new paper or generate scientific evidence.

## Read the actual contract first

Read `/input/case.json`, its `task.md`, the supplied source files and `environment/resources.yaml`. Paths here describe the evaluation environment; use the user's actual paths elsewhere. Treat labels as hints, never as source content. Record `case_id`, requested language, audience knowledge, purpose, talk duration, whether Q&A is included, exact total slide count, template, starting deck, required sections and every `output_contract` field. Case requirements override this skill's examples and defaults.

Work under `/app/work`, deliver under `/app/output`. Save an early `result.json` with the original contract keys and an honest partial status. Never return a completed status just because a PPTX exists. Preserve input files. For an edit task, inspect and modify the actual starting deck; rebuilding it from a blank presentation is not an edit.

## Decide what deserves a slide

1. Read the whole supplied source, including limitations, captions and supplementary material that the task includes. For a PDF, extract text and inspect relevant page images. OCR missing text if tools permit, then check symbols against the image. Record unreadable or missing regions. Do not infer source content from its filename or abstract alone.
2. Write one audience outcome, such as “the methods group can identify which control is still missing.” Separate facts explicitly reported by the source, calculations derived from them, interpretations, and proposals. Use the source's strength of evidence, units, denominators and uncertainty. Never turn association into mechanism, a pilot into general validity, or absence of a significance test into significance.
3. Build a compact evidence ledger. Each evidence ID identifies a real file, its version/SHA256, a page/section/table/panel/row locator, an exact short excerpt or numeric values, and a limitation. Keep this beside the deck. It is an index into the source, not a substitute for reading it.
4. Build a selection ledger for candidate content. Record `keep`, `notes`, `qa`, or `omit`, with an audience-specific reason and evidence IDs. Rank by relevance to the audience outcome, strength of evidence and prerequisite value. Include the strongest counterevidence or limiting condition before optional background. Do not hide a caveat in Q&A if it changes the main conclusion.

   Make audience adaptation observable. Record the audience's prior knowledge, one prerequisite they need before interpreting results, and one control or uncertainty they will challenge. Explain why each kept page uses its allocated time. In a paired audience comparison, hold material, template, objective, slide count and talk time fixed. Change only audience and keep the same core result values, units and limiting conditions. Report which content moved between slide, notes and Q&A. Do not claim a quality gain from merely changing two decks with different time budgets.

   Before adapting, list the scientific facts and scope limits that must survive in every version. Locate each in the projected content or the actual spoken script, not merely in appended source excerpts. Background definitions may depend on prior knowledge; arbitrary condition/group labels still need an introduction before their first result. A specialist's familiarity does not justify dropping an outcome's scope boundary. Check this shared list again after shortening the talk, so audience adaptation does not quietly remove a control or limitation.
5. Allocate the fixed slide and time budget. Count covers and backups in total slides unless the case explicitly excludes them. Reserve only the Q&A time actually requested. Allocate more time to the evidence the audience must interpret. Write opening, explanation, caveat and transition in notes with estimated seconds per slide. These are estimates, not measured rehearsal times. Sum all planned seconds and compare with the talk budget. Use roughly 100–150 English words per minute or 180–260 Chinese characters per minute only as a plausibility check, leaving time for figures and pauses. Never inflate a time label to disguise a two-sentence script.
6. Give every slide one job and a supported central claim. Use a short subject title for setup when no finding is established. Specify which exact evidence supports each factual statement, numeric table or figure. Use the plan's `bindings` to map stable item anchors, such as `body:0` or `table`, to evidence IDs; a page-level union of citations alone is insufficient. A claim spanning several items needs several IDs. For a non-expert audience, explain the measured quantity before the comparison. For expert listeners, spend that time on controls, assumptions or failure modes. Changing only the title of a deck does not adapt it.
7. Prepare likely questions about the strongest claim, control adequacy and limits. Each answer needs an evidence ID, a relevant slide number, the warranted answer, and what remains unknown. Unsupported mechanisms receive “not established by the supplied material,” with a source locating the limitation where available. Put Q&A in a separate text/JSON artifact or notes if no backup slides are allowed.

## Build against the actual template

Inspect slide dimensions, master/layout names, placeholders and indices, typography, colors, logos and existing content before editing. Use actual master/layout relationships. Keep the template's design and required elements. Do not paste screenshots of whole slides. Text, tables, editable charts and equations requested as editable must remain editable; original source figures may remain images with provenance. Crop a panel only when its labels, legend and scientific context remain intact. Log every crop, rescaling, calculation and omission.

The optional `scripts/build_deck.py` handles a small, explicit plan format described in [references/plan-format.md](references/plan-format.md). It creates slides from an empty PPTX template or replaces designated title/body placeholders in an existing deck. It supports native text, native tables and source images. It does not parse a paper, infer scientific claims, clone complex slides, or reconstruct charts. If the actual template needs richer objects, adapt a local authoring script in `/app/work` using available tools and preserve the same evidence, timing and QA records. Do not force the helper onto an incompatible template. Never quietly substitute a generic template.

Python dependencies are `python-pptx`, Pillow and PyMuPDF, with an installed office renderer for previews. Check installed versions first. Do not install software or call external APIs unless authorized. Use a provided equivalent renderer if LibreOffice is unavailable. The local helper is an optional execution aid, not a dependency on a personal path.

The builder checks exact normalized source excerpts for text or specified PDF pages. An excerpt match verifies presence, not whether the evidence warrants the claim. Visual sources need a manual `review_note`. Record expected `source_sha256` when freezing a source. The helper counts the spoken notes **and transition**, including numbers, and adds explicit reading/pausing time. It rejects a script requiring more time even at the declared ceiling pace, and flags tighter-than-nominal pacing. Rates are author assumptions, not a measured rehearsal or universal scientific rule. Resolve a warning by cutting detail, reallocating allowed time, or explaining a case-supported pace.

For repeat edits, use the owned shape names written in `owned-objects.json`. The builder updates its own table, caption, caveat and footer instead of stacking them. It preserves unrelated slide shapes and uses stable `etalk:` role names. To adopt an existing untagged caption or picture, supply its inspected shape ID through `shape_ids`; never guess ownership from position alone. Legacy `evidence-table-N` and `narrative-source-footer` names are recognized, while ambiguous duplicate owners cause an error. Keep scientific caveats visible with the native `caveat` field and bind that item to evidence. Inspect the entire edited page for stale unrelated facts.

## Render, inspect and deliver

Run `scripts/render.py DECK --out PREVIEW_DIR [--soffice PATH] [--timeout SECONDS]` for a real PDF plus one PNG per slide. The default timeout is 120 seconds. After an observed timeout, preserve its receipt; if the remaining case budget permits a justified retry, use a fresh directory and an explicit longer timeout. Do not retry indefinitely or silently exceed the case budget. A new preview directory prevents stale outputs. Inspect every rendered page at readable size. Check text clipping, unit/symbol loss, source captions, contrast, table labels, template conformity and reading order. A contact sheet helps navigate; it does not replace inspecting dense slides. Fix the source plan/script, rebuild and rerender after a defect. Record the actual renderer/version, fonts or substitutions, template/input hashes, edits and remaining limits. Do not claim inspection from file existence.

Reopen the PPTX and compare page count, native objects and notes against the plan. Reconcile the entire source coverage/selection ledger, every page's evidence, total seconds, question answers and the actual output contract. Check each numeric value against the source and show formulas for derived values. Technical checks cannot certify scientific validity or human speaking time.

Run `python scripts/check_delivery.py PLAN OUTPUT_DIR --preview PREVIEW_DIR` to check the actual deck, source hashes, native tables, notes, role uniqueness, bindings, template parts and preview freshness. For a requested repeated edit, apply the same plan twice to sequential copies and compare visible content, owned-object counts and unrelated objects. Stable file hashes are not required because package metadata may change. The check does not certify font layout or semantic entailment.

Deliver the editable file, real previews, page evidence map, selection ledger, question preparation, timing and source/change records. Populate **all original** `output_contract` fields in `result.json` and retain `case_id`. Add status, artifact paths, sources and uncertainty without replacing the requested structure. Distinguish `missing_material`, `unreadable_source`, `unsupported_tool`, `render_failed`, and other partial reasons. If rendering fails, keep the editable partial deliverable and report the failure. Never substitute a fabricated image or empty PDF.

## Minimal invocation example

Example only, not a formal case or prepared answer. Given a source report, a master-based template, a one-minute research update and exactly one slide, ask the Agent to read those files and write `plan.json` using [the internal plan format](references/plan-format.md), then run:

```sh
python /skills/weekly-skill/scripts/build_deck.py /app/work/plan.json --out /app/output
python /skills/weekly-skill/scripts/render.py /app/output/deck.pptx --out /app/output/preview
```

Expected output kinds are `deck.pptx`, `evidence-map.json`, `qa.json`, `timing.json`, `build-record.json` and real previews. The Agent still authors the contract-shaped `result.json`, selection ledger and visual review after checking them. See [PROVENANCE.md](PROVENANCE.md) for versions, scope and upstream design references.

An illustrative evidence-map page is `{"slide":1,"claim":"Short supported claim or setup topic","evidence_ids":["E1"],"bindings":[{"anchor":"title","evidence_ids":["E1"]},{"anchor":"body:0","evidence_ids":["E1"]}],"limits":"Scope stated by source"}`. These values explain the interface and are not scientific results.
