# Illustrative interface only

Input request: Adapt a six-page lab talk to the supplied template. Keep the data chart editable and the slide count unchanged. Source files, starting deck and template are supplied by the caller.

Inspect each actual file, then write a plan such as this illustrative record. Values here are placeholders for an interface, not scientific evidence.

```json
{
  "slide_key": "result-1",
  "role": "result",
  "source": {"file": "paper.pdf", "locator": "page 6, Figure 2 caption"},
  "layout_part": "choose from actual template inventory",
  "slots": [{"kind": "chart", "source_data": "provided measurement table"}],
  "uncertainty": "Keep the source's stated uncertainty and analysis limits"
}
```

Run the helper from its installed folder.

```sh
python template_audit.py inspect /input/template.pptx > /app/work/template.json
python template_audit.py inspect /input/start.pptx > /app/work/start.json
python migrate.py /input/start.pptx /input/template.pptx /app/work/plan.json /app/output/presentation.pptx /app/work/migration.json
python template_audit.py check /input/template.pptx /app/output/presentation.pptx --source /input/start.pptx --plan /app/work/plan.json > /app/work/package-check.json
```

Return the actual case's required keys and files. An example partial explanation is "PPTX and source mapping saved; PDF export unavailable in this environment." This statement is only appropriate when that condition actually occurred. Do not copy a success flag from an example.

Illustrative `plan.json` for a **single** slide with a native title and chart. Obtain the real slide numbers, shape IDs, layout part, slot indices and scientific locators from both inventories and verified material. List slides in required output order. Set the examples flag only when the template's existing slides are examples to replace.

```json
{"replace_template_examples":true,"slides":[{"source_slide":1,"layout":"ppt/slideLayouts/slideLayout2.xml","slots":[{"shape":2,"idx":0,"source":"material.pdf, Results heading, p. 2"},{"shape":3,"idx":1,"source":"material.pdf, Fig. 1 and caption, p. 2"}]}]}
```

Each entry maps one top-level source object. Text adopts destination typeface, size and color, retaining semantic run attributes such as superscript and emphasis. Verify source-specific color encodings separately. Each chart requires one internal embedded XLSX relationship. External data, linked paragraphs and additional chart parts require a dedicated adapter. Copies carry the source chart geometry settings such as axis limits and labels into the slot's new size. Review the rendered result. Notes preserve the speaker body including paragraph formatting; note-page drawings, timing and comments need separate handling. Use new output paths for each attempt; on exit 2 read the offending mapping and correct the plan or use the case-specific path. The JSON sidecar links slide and shape IDs to sources and records file digests. Combine it with actual claims, uncertainty, deck lineage and rendered inspection in the contract result.
