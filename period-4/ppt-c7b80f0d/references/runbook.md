# Executable PDF and template workflow

The bundled Python entry point is `scripts/paper_deck.py`. In a shell, set `K=/skills/weekly-skill/scripts/paper_deck.py`, then run the four calls below. It needs Python 3.10+, PyMuPDF (`import fitz`), and python-pptx. Local exercise used Python 3.12.2, PyMuPDF 1.27.2 and python-pptx 1.0.2. For a permitted clean installation use `python -m pip install PyMuPDF==1.27.2 python-pptx==1.0.2`. A PDF exporter is separate. Inspect the case's installed tools before attempting installation. The script works offline. Review the maintained .py source when adapting a feature.

1. `python "$K" index /input/materials/paper.pdf /app/work/paper` writes physical page numbers, printed labels, unrotated point dimensions and text block rectangles to pages.json. Repeat with a distinct directory for every PDF. Read the source in context. Render selected pages, including figure legends and neighbouring panels. A portable Python call is `page.get_pixmap(dpi=125).save(path)` with a PyMuPDF document open. For non-PDF sources retain original row, tab, section or frame references in a companion ledger and adapt build if needed.
2. `python "$K" layouts /input/templates/lab.pptx /app/work/layouts.json` lists masters, layouts, inherited slots and sizes. Inspect rendered examples, logos/footer, safe area, styles, and actual case rules before choosing. Master/layout numbers are zero-based, placeholder indices are their real idx values. Slides and PDF page numbers are one-based. For edit-in-place jobs, open the supplied starting deck, modify only authorized content and use its mapping. This builder implements the new-talk path from a template. It leaves source files intact. Removing exemplar slides in the copy requires explicit `discard_exemplar_slides: true` after the case author checks that they serve as examples. If a template has meaningful existing slides, preserve them and author by adapting the copy.
3. Write /app/work/plan.json using the schema below. `python "$K" build /app/work/plan.json /app/output/talk.pptx /app/output/evidence.json` validates anchors, builds in the original template and writes the editable deck plus page map. Reopen the artifacts. Translate the map into any case-specific schema and keep corroborating evidence.
4. Use the specified presentation renderer. An available headless alternative is `soffice -env:UserInstallation=file:///app/work/lo-prof --headless --convert-to pdf --outdir /app/output /app/output/talk.pptx`. Use a fresh work profile and capture exit status, version and output. Then run `python "$K" check /app/output/talk.pptx /app/output/evidence.json /app/output/talk.pdf /app/work/review`. This writes slide PNGs and checks the slide count, actual titles in the preview, notes, assigned layouts, native table cells, chart categories, values, axis units and embedded category-chart workbook. Supply PNGs under /app/output when required. Visually inspect every page at presentation size. Check axis labels, text wrapping, clipping, footer, crop boundaries and exact panel identity. If PDF text extraction cannot recover a displayed title, inspect the actual rendering and report the distinction. Record limitations and takeaways in the case's result.json with every original field.

## Working plan format

The following **illustrative input fragment** assumes one PDF whose physical page 2 really contains the quoted text and a template with title and body placeholders. Replace every example value with inspected case evidence. Relative source and template paths resolve from the plan file's directory. One slide here demonstrates the interface. Extend the plan to meet the stated talk time and real count.

```json
{
  "case_id": "illustrative",
  "template": "/input/templates/lab.pptx",
  "pdfs": {"main": "/input/materials/paper.pdf"},
  "anchors": {
    "a": {"pdf": "main", "page": 2, "locator": "Results, paragraph 1", "quote": "The median was 12 s."}
  },
  "slides": [{
    "master": 0, "layout": 1, "claim": "Median response time was 12 s",
    "refs": ["a"],
    "notes": "Point to the median and identify the response definition before moving to the condition comparison.",
    "limits": [],
    "objects": [{
      "kind": "text", "slot": 1, "in_placeholder": true,
      "lines": ["Response time", "Median across the reported trials: 12 s"],
      "refs": ["a"]
    }]
  }]
}
```

Anchor IDs are author-chosen. For repeated labels in different panels, bind the panel letter, condition, group, unit and value together. For an exact panel check, add `quote_rect: [x0,y0,x1,y1]` in unrotated physical-page coordinates and quote the text within that rectangle. When the region is also a crop, place the scoped quote inside that crop. Cite an external caption with a separate anchor. Find the coordinates in the page index or a visual page inspection. A page-wide match cannot distinguish identical labels elsewhere. For rotated PDFs, inspect the displayed crop; PyMuPDF uses its page rotation matrix for rendering. Exact-text validation ignores whitespace/case, but preserves digit order, punctuation and signs. Inspect typography such as minus signs, superscripts and OCR errors before drawing scientific conclusions. For image-only data, use `reading` and `rect` in place of quote only after visually verifying it. The receipt labels this as a visual transcription. Never guess missing digits.

Each slide needs evidence for the title and every scientific object. For quantitative results keep provenance for each condition, group, row or panel in the object's refs, along with sample size, units, uncertainty and any numerical calculation. Use short visible source labels plus full notes and the external map. For two panels with opposing findings, verify each channel's direction separately against the caption. Inspect axis orientation, reference category and normalisation before translating a trend into a headline.

Each object uses an actual template `slot` and optional `box: [left,top,width,height]` as fractions within that slot. The box defaults to the entire slot. Keep objects disjoint unless overlaid by design. The template title always goes into its native title placeholder. Text inherits the theme. Use a full-slot text object with `in_placeholder: true` to preserve its paragraph hierarchy. Optional pt, bold, accent (theme Accent 1) and space_after apply to other compact blocks when the template permits.

| Object | Additional fields | Source treatment |
|---|---|---|
| text | lines; optional pt, bold, accent, space_after | Editable. Label synthesis, attribution and uncertainty. |
| crop | anchor; optional dpi (default 180) | Its anchor needs rect, same point coordinates; include anchor in refs. A source image is a movable picture, with original pixels rendered from the PDF. Add editable caption/labels separately. Preserve full scales, legends and aspect. |
| table | rows (rectangular matrix); optional pt | Native table. Retain original precision, units, uncertainty and row/column labels, including in shortened tables. |
| chart | chart_type (column or line); string categories; series object mapping name to numeric list; unit; optional min, max, labels | Native chart with editable embedded data. Use column min 0 for magnitude, and meaningful order for a line. Preserve series and error definitions. Where input requires error bars, images of formulae, native equations, specialized plots or multiple axes, use a faithful source crop or adapt the tool to support all required semantics before calling it complete. |

Invalid page, quote, region or layout is a diagnostic to inspect the source, never a reason to silently change the claim. If a PDF lacks a text layer, render it and use OCR or reviewed visual anchors. When software or template features fall outside this route, apply the main skill workflow with available source-aware editing tools. Save usable partials and a precise issue when a requirement remains open.
