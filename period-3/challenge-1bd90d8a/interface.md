# Renderer interface

Run with Python 3.10 or newer and installed matplotlib. The local validation used Python 3.12, matplotlib 3.10.8, numpy 2.5.1 and PyMuPDF 1.27.2. PyMuPDF is used by local verification, not by the renderer. Do not install packages or download fonts when the execution environment forbids it. Use the tools listed in the actual case resources.

```sh
python /skills/weekly-skill/chart.py --data /app/work/data.csv --spec /app/work/spec.json --out /app/output/figure-v1
python /skills/weekly-skill/chart.py --data /app/work/data.csv --spec /app/work/edited.json --out /app/output/figure-v2 --previous /app/output/figure-v1
```

Output directories must be new. The helper preserves old revisions. Relative paths resolve from the current working directory.

## Minimal synthetic input

These numbers are invented only to demonstrate the interface. They are not experimental results.

```csv
sample,time_h,signal_au,condition
c1,0,1.0,Control
c2,0,1.2,Control
t1,0,1.1,Treatment
t2,0,1.3,Treatment
```

```json
{
  "case_id": "synthetic-interface-example",
  "title": "Synthetic example",
  "caption": "Synthetic values. Points are independent example samples. Bars show sample SD; no significance test.",
  "synthetic": true,
  "mode": "mean_sd",
  "replicate_field": "sample",
  "x": {"field": "time_h", "label": "Time", "unit": "h"},
  "y": {"field": "signal_au", "label": "Signal", "unit": "a.u."},
  "group": {"field": "condition", "order": ["Control", "Treatment"]},
  "style": {
    "width_mm": 150,
    "height_mm": 110,
    "font_family": "DejaVu Sans",
    "font_size": 9,
    "colors": ["#0072B2", "#D55E00"],
    "markers": ["o", "s"],
    "dpi": 300
  }
}
```

Save those blocks as `data.csv` and `spec.json` and run the first command with their paths. The illustrative outputs are `chart.svg`, `chart.pdf`, `chart.png`, `mapping.json`, `calculations.json`, and `result.json`. The SVG contains editable text and separately identified data marks. Inspect the real outputs before reporting success.

## Specification fields

- `case_id`, `title`, and `caption` are required strings. Include uncertainty meaning, sample design and synthetic status in the caption.
- `synthetic` is a required boolean. Real cases must not inherit example values or synthetic labels.
- `mode` is `raw_scatter`, `raw_line`, or `mean_sd`. Raw line connects numeric x in ascending order. Duplicate x within a series is rejected rather than connected arbitrarily.
- `x` and `y` specify the actual source `field`, display `label`, and nonempty `unit`. For a dimensionless quantity use `dimensionless`. No unit conversion is implicit.
- `group.field` identifies the series. `group.order` lists all observed groups exactly once. Its order controls legend, colors and markers together.
- `replicate_field` is required for `mean_sd`. Each group at each x must contain at least two distinct replicate IDs. The renderer cannot infer biological independence from identifiers. The agent must verify the sampling design.
- `style` contains the explicit width and height in mm, font family, font size in points, ordered color and marker lists, and raster dpi. Request an installed font with all required glyphs. Missing fonts or glyphs fail rather than silently substituting unreadable labels.

Mean and sample SD use all rows in a group at a given x. SD uses the n minus 1 denominator. The display shows the individual raw observations as well as the aggregate. There is no jitter, inferential test, smoothing, imputation, outlier deletion or normalization. Raw data remain unchanged.

`mapping.json` maps data element IDs to source records and fields. CSV record 1 is the header; the first data record is 2. Quoted multiline cells occupy one logical record, so record numbers are not physical file line numbers. `calculations.json` records the aggregate inputs and arithmetic results. Use the SVG ID to look up its source records; filter the records to find all marks using an input row.

## Editing and failure handling

For a style-only change, modify style, title, or caption and run with `--previous`. Keep captions scientifically consistent. The source hash, mark semantics, axis metadata, grouping and calculation mode must remain unchanged. A change record identifies the previous revision and differences. A data revision requires a new generation run and explicit provenance, not the style-edit path.

Malformed CSV, duplicate headers, missing fields or values, nonfinite numbers, invalid styles, unknown groups, absent fonts and unsupported modes produce a nonzero exit. Text beyond the canvas also fails. Long unbroken labels may need an explicit line break or a larger figure; the helper does not split scientific names automatically. This boundary check does not detect every overlap inside the canvas. No automatic row dropping occurs. Inspect stderr, correct only a documented error, and retry into a new directory. If export failed after directory creation, preserve the partial directory and its error evidence.

The helper emits `rendered_pending_visual_review`. It has not inspected scientific interpretation or visual collisions. The invoking agent must open every export, check the original output contract, and write the final case result separately. Use partial status when a requested chart type, source edit or format remains unsupported.

SVG keeps live text but does not embed the font. Check the SVG in the recipient's editor with the requested font available. The embedded-font PDF is the visual reference. The local PyMuPDF 1.27.2 SVG conversion substituted fonts and changed some hollow-marker fills, so its SVG conversion alone is not an appearance check. This does not affect PyMuPDF rendering of the separately exported PDF.

## Provenance and portability

The Skill and helper are original project-local candidate text. No external Skill, template, font, library source, or scientific dataset is bundled. Runtime dependencies retain their own licenses. No absolute author machine paths are needed. Keep local generated demonstration artifacts outside the candidate package. The platform installs the candidate's text files and provides the runtime materials.
