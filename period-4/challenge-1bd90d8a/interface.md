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
sample,time_ns,voltage_mV,probe
p1,1700000000000000000,1.0,Probe A
p2,1700000000000000000,3.0,Probe A
p3,1700000000000000001,11.0,Probe A
p4,1700000000000000001,13.0,Probe A
```

```json
{
  "case_id": "example-voltage",
  "title": "Voltage at two adjacent clock ticks",
  "caption": "Hollow circles show independent simulated readings. Filled circles show means.",
  "synthetic": true,
  "mode": "mean_sd",
  "replicate_field": "sample",
  "x": {"field": "time_ns", "label": "Clock time", "unit": "ns"},
  "y": {"field": "voltage_mV", "label": "Voltage", "unit": "mV"},
  "group": {"field": "probe", "order": ["Probe A"]},
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

Save those blocks as `data.csv` and `spec.json` and run the first command with their paths. The illustrative outputs are `chart.svg`, `chart.pdf`, `chart.png`, `mapping.json`, `calculations.json`, and `result.json`. For this example, expect two means (2 and 12 mV), two observations per mean, and offsets of 0 and 1 ns from 1700000000000000000 ns. The SVG contains editable text and separately identified data marks. Inspect the real outputs before reporting success.

## Specification fields

- `case_id`, `title`, and `caption` are required strings. Include uncertainty meaning, sample design and synthetic status in the caption.
- `synthetic` is a required boolean. Real cases must not inherit example values or synthetic labels.
- `mode` is `raw_scatter`, `raw_line`, `mean_sd`, or `source_interval`. Raw line connects numeric x in ascending order. Duplicate x within a series is rejected.
- `x` and `y` specify the actual source `field`, display `label`, and nonempty `unit`. For a dimensionless quantity use `dimensionless`. No unit conversion is implicit.
- `group.field` identifies the series. `group.order` lists all observed groups exactly once. Its order controls legend, colors and markers together.
- `replicate_field` is required for `mean_sd`. Each group at each x must contain at least two distinct replicate IDs. The renderer cannot infer biological independence from identifiers. The agent must verify the sampling design.
- `style` contains the explicit width and height in mm, font family, font size in points, ordered color and marker lists, and raster dpi. Request an installed font with all required glyphs. Missing fonts or glyphs fail rather than silently substituting unreadable labels.

Mean and sample SD use all rows in a group at a given x. SD uses the n minus 1 denominator. The display shows the individual raw observations as well as the aggregate. There is no jitter, inferential test, smoothing, imputation, outlier deletion or normalization. Raw data remain unchanged.

### Numeric origins and source-defined intervals

The x grouping key is the exact numeric decimal, so `1.000` and `1e0` denote the same x. Near a large common offset, the renderer subtracts the smallest source x in decimal arithmetic before converting the differences to plotting coordinates. The axis prints the exact origin and unit. In this case `mapping.x_transform` describes the subtraction, mark `values.x` are differences and `calculations.groups[].x` retains the absolute decimal as text. Each mark preserves original cell strings in `source_values`. Unresolvable x values cause an error if they collapse numerically or coincide at SVG precision. Check `render.subpixel_x_spacing` for additional PNG limitations.

For a table of estimates with absolute bounds, set `mode` to `source_interval`, set `y.field` to the source estimate, omit `replicate_field`, and supply this object alongside `mode`:

```json
"interval": {"low_field": "lower_mm", "high_field": "upper_mm", "meaning": "the supplied 90% calibration interval"}
```

For example, the synthetic row `time_ns,estimate_mm,lower_mm,upper_mm,probe` with values `2,4.0,3.8,4.7,A` draws one estimate at 4.0 mm and an interval from 3.8 to 4.7 mm. Set `group.field` to `probe`, `group.order` to `["A"]`, and use the actual axis names and units. Every interval must enclose the estimate and use the y unit. Zero-width sides are allowed. Rows hold source estimates, not replicate observations. No aggregation or confidence calculation runs. Record sample size in the caption when the source states it. Unknown interval meaning should be explicitly described as unspecified by the source. Distinguish absolute bounds from lengths such as lower and upper errors; convert the latter only with a recorded, source-justified calculation.

`mapping.json` maps data element IDs to source records and fields. CSV record 1 is the header; the first data record is 2. Quoted multiline cells occupy one logical record, so record numbers are not physical file line numbers. `calculations.json` records the aggregate inputs and arithmetic results. Use the SVG ID to look up its source records; filter the records to find all marks using an input row.

## Editing and failure handling

For a style-only change, modify style, title, or caption and run with `--previous`. Keep captions scientifically consistent. The source hash, mark semantics, axis metadata, grouping and calculation mode must remain unchanged. A change record identifies the previous revision and differences. A data revision requires a new generation run and explicit provenance, not the style-edit path.

Malformed CSV, duplicate headers, missing fields or values, nonfinite numbers, invalid styles, unknown groups, absent fonts and unsupported modes produce a nonzero exit. Text beyond the canvas also fails. Long unbroken labels may need an explicit line break or a larger figure; the helper does not split scientific names automatically. This boundary check does not detect every overlap inside the canvas. No automatic row dropping occurs. Inspect stderr, correct only a documented error, and retry into a new directory. If export failed after directory creation, preserve the partial directory and its error evidence.

The helper emits `rendered_pending_visual_review`. It has not inspected scientific interpretation or visual collisions. The invoking agent must open every export, check the original output contract, and write the final case result separately. Use partial status when a requested chart type, source edit or format remains unsupported.

The y plotting coordinate is binary64. Extreme dynamic ranges, high-precision y offsets, logarithmic axes, categorical x, and multi-panel arrangements may need a case-specific script. Verify the actual exported marks against source values after any documented scaling.

SVG keeps live text but does not embed the font. Check the SVG in the recipient's editor with the requested font available. The embedded-font PDF is the visual reference. The local PyMuPDF 1.27.2 SVG conversion substituted fonts and changed some hollow-marker fills, so its SVG conversion alone is not an appearance check. This does not affect PyMuPDF rendering of the separately exported PDF.

## Provenance and portability

The Skill and helper are original project-local candidate text. No external Skill, template, font, library source, or scientific dataset is bundled. Runtime dependencies retain their own licenses. No absolute author machine paths are needed. Keep local generated demonstration artifacts outside the candidate package. The platform installs the candidate's text files and provides the runtime materials.
