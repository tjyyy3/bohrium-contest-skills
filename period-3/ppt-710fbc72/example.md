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
# The Agent reads actual materials, writes and runs a case-specific adaptation script.
python template_audit.py check /input/template.pptx /app/output/presentation.pptx > /app/work/package-check.json
```

Return the actual case's required keys and files. An example partial explanation is "PPTX and source mapping saved; PDF export unavailable in this environment." This statement is only appropriate when that condition actually occurred. Do not copy a success flag from an example.
