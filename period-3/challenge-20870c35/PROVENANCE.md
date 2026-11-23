# Provenance and limits

Version 1.0.1, 2026-11-11. Original implementation for the academic presentation content organization challenge. No case-specific answers, datasets or binary templates are shipped. The evaluator supplies the source and actual template. Version 1.0.1 adds item-level source bindings and persistent renderer launch/timeout failure receipts after local independent review.

The workflow uses audience-driven selection, explicit source-bound page claims and estimated delivery budgets. This is not evidence of a quality gain over a base Agent. Official comparison belongs to the platform. Local synthetic trials test portability, traceability and editable output only.

Design references inspected at fixed commits:

- EvoScientist/EvoSkills `4889c2270af5f9a7658bb6a6709bf37040902006`, `skills/academic-slides/references/talk-structure.md`. Used as a conceptual reference for audience-dependent ordering and method overview before detail. Copyright 2026 EvoScientist, Apache-2.0.
- anthropics/skills `2c5958ecac7cee2b583967a2c4981d0f4a75c579`, `skills/pptx/SKILL.md`. Used as a conceptual reference for native notes, editable objects and separate content/structure/render checks. Skill-specific license Apache-2.0.

No upstream scripts, assets or prose are copied. This candidate's scripts and instructions were written locally. The fixed source locations are `https://github.com/EvoScientist/EvoSkills/tree/4889c2270af5f9a7658bb6a6709bf37040902006` and `https://github.com/anthropics/skills/tree/2c5958ecac7cee2b583967a2c4981d0f4a75c579`. No external API is required.

Runtime dependencies are Python 3.10+, python-pptx 1.0.x, Pillow 10+ and PyMuPDF 1.24+; LibreOffice or a supplied office renderer creates actual previews. These are dependency expectations, not automatic install instructions. Record actual versions for each run. The scripts use relative paths and accept a renderer path. Complex templates, native mathematical editing and chart reconstruction require a local script adapted to the actual case. A successful LibreOffice render is not proof of Microsoft PowerPoint fidelity.
