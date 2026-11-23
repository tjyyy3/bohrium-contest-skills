# Internal plan reference

This is a helper schema, not the external case schema. Derive it from the actual case. Paths are resolved relative to the plan file. The helper refuses mismatched slide count, evidence IDs, QA slide references and a talk schedule exceeding the budget. It validates links and file hashes, not scientific truth.

Required top-level keys:

```json
{
  "case_id": "example-only",
  "audience": "specified audience",
  "outcome": "one audience outcome",
  "template": "actual-template.pptx",
  "mode": "create",
  "slide_count": 1,
  "talk_seconds": 60,
  "font": "Arial",
  "title_pt": 30,
  "body_pt": 22,
  "caption_pt": 11,
  "footer_box": [0.5, 6.8, 12.3, 0.35],
  "evidence": [{"id": "E1", "path": "report.md", "locator": "Section 1", "excerpt": "Exact source excerpt", "limit": "Scope stated by source"}],
  "slides": [{
    "title": "Short supported claim or setup topic",
    "role": "setup",
    "seconds": 60,
    "layout_index": 1,
    "title_idx": 0,
    "body_idx": 1,
    "kind": "text",
    "body": ["One factual point linked below"],
    "evidence_ids": ["E1"],
    "bindings": [{"anchor": "title", "evidence_ids": ["E1"]}, {"anchor": "body:0", "evidence_ids": ["E1"]}],
    "notes": "Actual speakable script with explanation and caveat.",
    "transition": "Connection to the next page or closing.",
    "limits": "What this page does not establish"
  }],
  "qa": [{"question": "What is uncertain?", "answer": "Bounded answer", "unknown": "Missing evidence", "slides": [1], "evidence_ids": ["E1"]}]
}
```

The example is an interface illustration. Do not reuse its claims or geometry without reading the input. `footer_box` contains inches and must fit the actual template. Font sizes must match the supplied template. The font must be available in the renderer environment or a disclosed approved substitution must be used.

`mode=create` requires an actual empty PPTX template with master/layouts. `mode=edit` loads the actual starting PPTX specified by `template`, requires the same number of plan entries as existing slides, and edits those in order. It preserves other shapes; inspect them for stale facts. Empty unused template placeholders can remain empty, but visible placeholder instructions cannot. Complex edits should use a local script rather than removing arbitrary elements.

Each slide's `title_idx` and `body_idx` are placeholder IDs, not shape positions. `layout_index` is used only for create. The body placeholder determines the content bounding rectangle. `kind=text` uses `body`, a list of short paragraphs. `kind=table` uses `table`, an array of equal-length row arrays including a header, and optional `caption`. All table cells remain editable. `kind=image` uses `image`, a source image path, and optional `caption`. Images retain aspect ratio; small source images require visual resolution checks. Never use image kind for a required editable chart or whole-slide screenshot. Tables/images use the body rectangle and leave an empty placeholder beneath them.

Each evidence entry addresses one precise location; multiple entries can share a source file. `verification` defaults to `text`, which requires the whitespace-normalized excerpt to occur literally in the UTF-8 source. Use `verification: "pdf"` and `pages: [1, 2]` for one-based PDF page extraction; the excerpt must occur on those pages. Use `verification: "visual"` with a substantive `review_note` only when image/table transcription requires visual inspection. It is labeled manual, not automatically verified. The builder records SHA256 for every referenced file and rejects a mismatched expected `source_sha256` when supplied. Calculations belong in the evidence ledger with inputs and formula. Matching a quote never proves scientific entailment. Footers display IDs and brief locators; full versions live in the map and notes.

`bindings` maps each visible content item to evidence. Required anchors are `title`; every zero-based text paragraph (`body:0`, `body:1`); `table` or `image` when present; and `caption` when present. Each anchor occurs once and cites one or more of the page's evidence IDs. A whole-table anchor is appropriate when all cells come from the cited table/rows. If cells come from different locations, add a `basis` describing their row/column correspondence. For derived numbers include the formula and inputs in `basis`; for interpretations or proposals explicitly label them there. Every visible factual item needs support; the script checks anchor coverage but cannot assess whether a source warrants the claim. The selection ledger and Q&A remain separate from these item bindings.

`seconds` is an integer >0 for every talk slide. For allowed backup pages set `seconds=0` and `role=backup`. Backups still count toward `slide_count`. `talk_seconds` excludes separately allocated Q&A. The helper counts notes plus transitions, Latin words, numeric tokens and CJK characters. `pause_seconds` defaults to 5 per page. Optional top-level `pacing` defaults to `{"english_wpm":130,"cjk_cpm":220,"english_ceiling_wpm":180,"cjk_ceiling_cpm":320}`. These are declared planning assumptions, not measured norms. Required time equals Latin/numeric tokens divided by words/minute plus CJK characters divided by characters/minute, both times 60, plus pauses. A page exceeding its allocation at the ceiling rate is rejected; exceeding nominal is recorded as a warning. Rehearse separately when possible.

`caveat` is optional visible editable text in the bottom of the content area; add its `caveat` binding. It is intended for concise limiting conditions. `table_height_inches` optionally controls a native table within available space; otherwise height is capped at 0.9 inch per row. Inspect wrapped headers. Tables, images, captions, caveats and footers use the stable names `etalk:table`, `etalk:image`, `etalk:caption`, `etalk:caveat` and `etalk:footer`. Repeated edits update owned text/table objects in place when compatible. A table dimension or image change replaces only its owned object, keeping the role name. Other shapes remain untouched.

Optional per-slide `shape_ids` maps roles to inspected existing shape IDs, for example `{"caption": 7, "image": 8}`. This authorizes adopting those particular non-placeholder objects; never map an unrelated decoration. It is useful for old untagged decks. The build writes actual current IDs to `owned-objects.json`. More than one owner for a role is an error requiring source inspection, not silent deletion. The legacy table/footer names from v1 are recognized. Run the delivery checker and visually inspect stale or duplicated unowned content after adoption.

Output files are generated from this plan. The source plan, selection ledger, actual contract, notes and Q&A must agree. Save any warnings and output limitations in the final case result.
