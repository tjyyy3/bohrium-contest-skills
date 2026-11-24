---
name: anchored-reading-ledger
description: 将本地文库中的高亮、划线、评论、独立摘录和修订记录整理为能回到原文位置的笔记。用于阅读批注、跨版本核对、资料恢复与循证检索，支持中英文材料。
---

# 可回读的阅读笔记

when given a library and a work order, **perform the operations on the supplied files**. Return notes and answers in the requested language. The reader should be able to go from a question to a note, file version, location and passage, then independently check the answer. The scripts create a local SQLite index and JSON exports. They do not need a service account.

## 1. 接单与第一次入库

1. Read the complete task and actual case JSON. List its keys, constraints, paths and every field or artifact named by its output contract. Identify its **current** work order, requested document IDs, searches, authors/versions, decisions and access restrictions. Inspect the actual materials, including administrative inventories, aliases, sidecars and recovery records. Compare expected paths with discovered paths. A manifest assertion and an observed byte hash are separate pieces of evidence. Record any expected-but-absent inputs explicitly.
2. On Harbor the case is at `/input/case.json`; locate `task.md` and `environment/resources.yaml` and check available readers. Skill resources are under `/skills/weekly-skill/`. Work in `/app/work`, write final outputs under `/app/output`. Use a material-only root if it covers the complete relevant library, otherwise scan `/input` and distinguish instructions from substantive evidence. Files referenced outside this root require checking access and provenance. Respect any exclusions before indexing (stage just the permitted files in a separate read-only input view when necessary).
3. Python 3.9+ and its standard library (including sqlite3) suffice for text, HTML, DOCX, CSV/TSV, JSON, Markdown and the index. PDF annotation geometry uses optional PyMuPDF, imported as `pymupdf` or `fitz`; check the available version in the runtime receipt. If absent, the script uses installed Poppler `pdftotext` for layout text and flags unexamined native annotations. For a separate local installation, `python -m pip install PyMuPDF` enables the PDF adapter. In a restricted case, use the supplied tools and honor its network/resource conditions. The bundled source is original (`ledger.py`, `extract.py`, version 1.0).

```sh
S=/skills/weekly-skill
M=/input
O=/app/output/reading
mkdir -p /app/work /app/output
python -B "$S/ledger.py" build --input "$M" --out "$O"
python -B "$S/ledger.py" find --out "$O" --source 'relative/path/from/inventory'
```

4. Write an early `/app/output/result.json` with the **original case_id and every original output_contract field**, preserving requested key spelling, structure, filenames and types. Populate completed inventory/evidence paths, explicit missing items, open operations and honest partial status. This is a checkpoint. Before final delivery replace it with actual results, including answers and operation receipts. A list of planned actions or an empty wrapper does not satisfy the work order.

## 2. 锚定与结构化

Read `sources.json.files` by relative path, then its `sha256` entry in `contents`. Identical bytes have one content record and all original names. Check `status` on **both** the path and content, including aliases. Never merge different hashes because a title/slug/DOI matches. Cite the specific copy/version consulted. File timestamps are observed filesystem facts, not publication dates or evidence of which edition supersedes another.

| Source | Location and checks |
|---|---|
| Native PDF | Physical page is 1-based, x/y are PyMuPDF unrotated page coordinates in points. Keep printed page separately if present. Text blocks retain bounding boxes. Text markup retains subtype, quad vertices, color, comment, author, ID and dates. Selected words are those whose centers fall inside individual quads, ordered within each quad by original block/line/word. Verify small selections, rotations, ligatures and two-column boundaries by rendering the original page with annotation overlay. A sticky note, free text or ink can be position-only. Preserve its contents and bbox and report unresolved wording. |
| Scan or cropped screenshot | Inspect actual pixels at the cited physical page/region. If OCR is authorized, render an identified crop, save its source hash, page, bbox, page rotation, DPI, crop origin and tool version. Keep raw OCR/word boxes and corrected text plus diff. On an unrotated rendered crop, page coordinates equal crop origin + pixel coordinates × 72/DPI. For rotated media use the renderer's inverse transform, check two landmarks. Inspect handwriting or low confidence manually against the original and expose remaining doubts. Store such verified or provisional entries in a separate sidecar under output keyed by source hash and crop, and include them in the case results. They are not automatic native text anchors. Never infer a quote from the nearest paragraph. |
| DOCX | WordprocessingML paragraph numbers count table paragraphs too. Ranges preserve comment IDs, body, author/date and per-paragraph offsets; direct run highlight and underline retain style/color. A long comment can have several ranges with one native ID. Unsupported stories such as headers, floating text, inherited styles or tracked changes require inspection of the corresponding XML and a documented part locator. Omit a page label unless a matching render establishes it. |
| HTML or Markdown | Parsed HTML text uses block number, optional element ID and decoded-text offsets. Explicit mark/underline/annotation attributes retain raw metadata. Markdown double-equals highlights retain line and offsets. CSS-only highlights, JavaScript views, loose notebook text and sidecar-exported annotations require an explicit match to the named source. An HTML style or color has semantic meaning only if its legend can be cited. |
| Metadata and sidecars | JSON uses escaped JSON Pointers; CSV/TSV uses logical row and column; text uses actual 1-based line numbers. Preserve source roles. A sidecar quote should be verified against the article before becoming article evidence. For a standalone idea cite its own note as reader commentary. For unsupported formats use an installed reader or authorized export, attach source hash plus native locator and evidence artifact, and record manual actions. |

Decide the unit of knowledge from the user's purpose. For each material judgement, write one concise contextualized claim, question, method, limitation or reusable observation. Retain conditions, quantities, direction, negation and uncertainty. An author assertion and a reader interpretation should carry distinct attribution. Add author, date, project, entities, tags and original metadata where supplied. Keep verbatim quotes inside the evidence list. Native notes initially hold just the raw reader comment or selected words; curate them into useful notes for the work order. Every factual clause in a curated claim must follow from its evidence. The program checks positions; the agent checks meaning.

## 3. 证据计划与版本修复

Write an editable UTF-8 `plan.json` in the work directory. Arrays are optional. Copy the finished plan into the final evidence directory so another reader can rebuild the same notes. The following field definitions form the authoring interface.

* `notes[]` uses `id, kind, claim, evidence[]` and optional `attribution, tags[], entities[], date, annotation_ids[], uncertainty`. Select actual native IDs from `sources.json`. If used, each ID must overlap at least one selected evidence range in the same content. Use ISO dates for authored notes; preserve raw source dates separately.
* An evidence selector is `{"source":"relative/path","quote":"exact substring"}`. Add `locator`, zero-based `start`, `prefix`, `suffix`, or full `sha256` to disambiguate. The stored interval is [start,end) in Unicode code points of the extracted unit. Preserve newlines and punctuation. A whole-file search with multiple matches goes into `issues`; pick a location only after reading the surrounding text. PDF selection text follows the quad word sequence, while the block text is the underlying PDF extraction. A precise annotation selector can address its own `page:N/annotation:XREF`.
* `versions[]` uses `id, from, to, kind, evidence[]`. Kinds are `administrative, revision, edition, translation`. Cite an administrative record, explicit publisher revision or supplied corroborated metadata. Record its authority and scope in optional `reason`. Model local administrative revisions as administrative. A filename or higher version number alone cannot establish a publisher correction. Different byte representations may be related without deciding which content is scientifically preferable.
* `transfers[]` uses `id, version, old` (selector) and optional `new` (target selector overrides), `meaning_review`. The old hash must match the predecessor. The new file is searched afresh. No match or multiple occurrences are saved as unresolved. For wording changes, read both passages, give a verified new selector, classify the change, and revisit each dependent note. Verbatim relocation checks text only. A changed comparator or negation in the surrounding context can reverse its meaning. Never overwrite the older annotation.
* `links[]` uses `id, from, to, kind, reason, evidence[]`, with note IDs as endpoints. Link for an identifiable relation such as shared procedure under the same conditions, an explicit qualification or incompatible measurements of the same quantity. Cite a supporting passage from each endpoint; the script checks interval overlap with each note's evidence. A keyword intersection nominates candidates and does not establish the relation. Keep explanations and rejected/undetermined candidates visible when relevant.

Rebuild with the plan, then check `knowledge.json.issues`, source events and the original work order. Resolve errors that available materials can settle. Keep a diff/decision record of before, after, author/tool, reason, affected paths and resulting hashes for manual edits. Preserve unmatched old selectors for a later review.

## 4. 实际检索、恢复与交付

Run every requested search/question against the rebuilt index. `find` matches all supplied terms case-insensitively in claim, evidence, tags or entities; quotes shell-group a phrase. Filters include `--notes-only --tag TAG --entity NAME --source RELATIVE --since YYYY-MM-DD --until YYYY-MM-DD`. Source filters resolve aliases by bytes; read cited paths to show which copy supplied the statement. Date filtering on curated notes uses ISO dates. Prefer exact topics or use separate searches for synonyms/Chinese substrings. If recall is low, remove one restriction and supplement with passage search. If results are broad, add identifying entities or another term and read surrounding passages. A zero-hit query warrants a receipt describing scope and uncertainty. For every final answer, cite the selected note, source hash and locator, explain the answer, and record why candidates with similar terms were excluded. Derive counts from actual receipts.

When the case orders repairs, copies, manifest updates or index recovery, **carry them out** in the requested output tree. Select permitted bytes using the authority record, copy the source into a case-approved destination, recompute its SHA-256, compare both hashes, and record original/destination, action, relationship, permissions basis and outcome. For alias or version collisions, retain both instances and their separate source facts. Resolve missing paths using actual allowed copies; if none exists, record the search and recovery dependency. Never replace originals or manufacture private account data. Verify the rebuilt index by reopening it and running the required queries. If the case asks for a specific schema/index representation, export from the ledger in that format.

For an authorized byte-copy repair, add `copies[]` to the plan. Each request takes `id, source, destination, sha256, reason, evidence[]`. The destination is relative to the separate recovery root. Cite the case instruction or administrative row that authorizes this operation, include it in the inventory, then execute:

```sh
python -B "$S/ledger.py" restore --input "$M" --out "$O" --dest /app/output/recovered --plan /app/work/plan.json --receipt /app/output/repair.json
```

Check each receipt. Matching existing bytes are verified; conflicting bytes are preserved and require a destination decision. A readable file does not establish permission to redistribute it. Keep the recovery root, build path and source tree separate. If material access rules allow only metadata, deliver the permitted reference/record and mark the copy restriction.

Deliver the requested case artifacts and `result.json`. Include real input IDs and paths, answer/knowledge records, evidence locators, status, uncertainty, read/operation log and recovery action for each missing, skipped, denied, conflicted or failed item. Check requested IDs, operations, query receipts and path references one-by-one; residual failures change the relevant item and case status. Compare on-disk hashes with `build.json`, verify each cited quote via its selector, confirm output files open, then reread the final JSON. A successful build only means the index was produced. Do not infer an official comparative gain from it.

## 可复跑的最小示例（全部为示意数据）

In an empty working directory with this Skill installed at `$S`, create a tiny library, index a native highlight and turn it into a retrievable note:

```sh
mkdir -p materials
printf '%s\n' 'Trial A used ==three repeats== at noon.' > materials/run.md
cat > plan.json <<'EOF'
{"notes":[{"id":"repeat-A","kind":"method","claim":"Trial A used three repeats at noon.","tags":["repeatability"],"evidence":[{"source":"run.md","locator":"line:1","quote":"Trial A used ==three repeats== at noon."}]}]}
EOF
python -B "$S/ledger.py" build --input materials --out reading --plan plan.json
python -B "$S/ledger.py" find --out reading --tag repeatability --notes-only --receipt query.json repeats
```

示意结果：查询返回 `repeat-A`，定位到 `run.md` 第 1 行，附完整 SHA-256 和字符范围。独立的原生 highlight 仍在 `sources.json`。输出文件：`sources.json`（目录、物理文件、内容、原生标记和异常）、`knowledge.json`（笔记、版本、迁移、关联和待核事项）、`index.sqlite`（可重建检索库）、`build.json`（工具与产物摘要）、`query.json`（该次实际检索）。示例只说明接口。
