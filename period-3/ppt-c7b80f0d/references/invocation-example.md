# Minimal calling example

This is an interface example only. The paths and requested talk below are hypothetical. This file contains no paper, prebuilt answer, official case, or executed test result.

## Example input

A caller supplies these actual files in a runtime:

```text
/input/case.json
/input/task.md
/input/materials/paper.pdf
/input/templates/lab-template.pptx
```

In this example, `case.json` identifies the paper and template, gives a `case_id`, and defines the required `output_contract`. The task requests an eight-slide, ten-minute talk for graduate students. It requires an editable PPTX, speaker notes, a slide evidence map, and a rendered preview. These constraints illustrate one caller's request. Discover the real field names and constraints from each actual case.

## Example invocation

Give an agent with access to those files and suitable presentation tools this request:

```text
Use the paper-to-academic-ppt skill at /skills/weekly-skill/SKILL.md.
Read /input/case.json and /input/task.md, then create the requested talk
from the supplied materials and template. Work under /app/work.
Save actual deliverables and result.json under /app/output.
Keep the original output contract and report incomplete checks honestly.
```

For a local run, substitute the real skill, input, work, and output paths explicitly. The skill does not install tools or start a model service. An existing agent runtime must execute the request.

## Illustrative output

This tree shows possible artifact roles. It does not claim these files exist. The real case determines filenames and formats.

```text
/app/output/
  result.json                 Original case fields populated with real outcomes
  presentation.pptx           Editable deck with embedded speaker notes
  slide-evidence.json         Each slide mapped to source pages and figure panels
  presentation.pdf           Actual render of the final deck
  run-record.md              Versions, fonts, commands, changes, and limits
```

If a required preview cannot be rendered, the result must say so using the actual contract's failure representation. Omit a nonexistent preview path. Keep the usable deck and identify the render failure. A filename in JSON is not evidence of a completed artifact.
