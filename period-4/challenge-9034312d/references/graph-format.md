# Graph interface, version 1

All coordinates are SVG user units. The origin is top left. Dimensions are positive. IDs use letters, digits, underscores or hyphens and are globally unique. Source paths are relative to the graph file or absolute at runtime. Preserve source bytes. JSON uses UTF-8.

Required root fields are `case_id`, `title`, `sources`, `nodes`, `edges`. Optional root fields are `width` and `height` (defaults 1000 and 650), `note`, `uncertainty` and `changes`. `sources` contains `{id,path,version}`. Each node and edge contains `evidence:[{source,locator,quote}]`. Quotes must occur exactly in the referenced UTF-8 text. For binary originals, cite a faithful text extraction and retain its original source path/hash in additional metadata. The script checks quote existence; the Agent checks the locator and scientific meaning.

Nodes contain `id`, `label`, `x`, `y`, `w`, `h`, `kind`, `evidence`. Coordinates name the center, not top left. `kind` is `process`, `decision`, `detector` or `terminal`. Labels may include newlines. Optional `font_size` defaults to 18. A diamond needs extra room around text. Keep node boxes at least 20 units apart.

Edges contain `id`, `from`, `to`, `from_port`, `to_port`, `type`, `label`, `label_at`, `evidence`. Ports are `top`, `bottom`, `left`, `right`. `type` is `sequence`, `material`, `information` or `energy`. `label_at` is `[x,y]`. Optional `via` is an ordered list of `[x,y]` connector bends. The script calculates start/end ports and arrowheads from source to destination, with a 12-unit arrowhead. It rejects zero-length segments, diagonal segments, endpoints entering their boxes backwards, duplicate IDs and missing evidence. It also rejects connectors that cross unrelated node boxes. It does not validate physical feasibility or infer absent connections. Labels are required so line types and conditions remain readable in monochrome.

Patch format is `{request:{source,locator,quote}, changes:[{id,field,value}]}`. The request source must already exist in the source list, so add the unchanged edit-request file as a source when creating the original graph. Node fields allowed are `label,x,y,w,h,font_size`; edge fields are `label,label_at,via,from_port,to_port`. Patches preserve node and edge evidence. Changing ports means changing drawing attachment, not inventing a physical interface. Scientific or physical interface changes need a source-backed semantic version instead.

## Minimal illustrative invocation

This is a fictional teaching example, not an official case or a scientific protocol. Save `source.txt` containing `S1. Receive the sample, then label it.` and `S2. Rename Label to Label sample.`. The latter is a presentation request.

Save a graph with two terminal/process nodes `receive` and `label`, and a `sequence` edge from `receive.right` to `label.left`. Use `S1` as the evidence locator and the complete first sentence as the quote for both nodes and the edge. Set centers to `[230,240]` and `[650,240]`, widths 200 and heights 70. Place the edge label `then` at `[440,220]`. Use a 900 by 450 canvas. The evidence source object is `{"id":"workorder","path":"source.txt","version":"teaching-1"}`. Use root `case_id:"illustrative"`, `title:"Fictional teaching route"` and `note:"Schematic, not to scale"`.

```sh
python scripts/route.py render route.json --out output/route
```

Illustrative output is a two-node editable SVG and matching PDF/PNG, plus a semantic JSON with source SHA256 and an export-check record. No formal-case outputs are distributed in this Skill.

An illustrative patch is:

```json
{"request":{"source":"workorder","locator":"S2","quote":"S2. Rename Label to Label sample."},"changes":[{"id":"label","field":"label","value":"Label sample"}]}
```

Run `edit`, render the new graph, then compare the source hash and the edge evidence to the original. Original provenance must remain unchanged.
