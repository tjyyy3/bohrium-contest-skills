# Provenance and limits

Version 2.0.0, 2026-11-23. Original project implementation evolved from our period-3 v1.0.1. No case-specific answers, datasets or binary templates are shipped. The evaluator supplies the source and actual template. This version fixes duplicated owned objects on repeated editing, adds source excerpt/version checks, counts spoken transitions and numbers in pacing, provides native caveats and an actual-output checker, and separates audience effects from time/slide-budget effects in local trials.

The workflow uses audience-driven selection, explicit source-bound page claims and estimated delivery budgets. This is not evidence of a quality gain over a base Agent. Official comparison belongs to the platform. Local synthetic trials test portability, traceability and editable output only.

Design references inspected at fixed commits:

- EvoScientist/EvoSkills `4889c2270af5f9a7658bb6a6709bf37040902006`, `skills/academic-slides/references/talk-structure.md`. Used as a conceptual reference for audience-dependent ordering and method overview before detail. Copyright 2026 EvoScientist, Apache-2.0.
- anthropics/skills `2c5958ecac7cee2b583967a2c4981d0f4a75c579`, `skills/pptx/SKILL.md`. Used as a conceptual reference for native notes, editable objects and separate content/structure/render checks. Skill-specific license Apache-2.0.

No upstream scripts, assets or prose are copied. This candidate's scripts and instructions were written locally. The fixed source locations are `https://github.com/EvoScientist/EvoSkills/tree/4889c2270af5f9a7658bb6a6709bf37040902006` and `https://github.com/anthropics/skills/tree/2c5958ecac7cee2b583967a2c4981d0f4a75c579`. No external API is required.

The installed python-pptx 1.0.2 implementation of `BaseShape.name` was inspected to confirm persistence through OOXML `cNvPr.name`. The stable-role editing implementation is original. Installed package metadata confirms python-pptx 1.0.2 uses MIT, Pillow 12.1.1 uses MIT-CMU, and PyMuPDF 1.27.2 is dual licensed under GNU AGPL 3.0 or an Artifex commercial license. These are runtime dependencies and their code is not bundled. Users must use them under applicable terms. Standard library JSON, regular expressions and SHA256 support the checks. The two upstream academic-slide references above remain conceptual workflow references, not evidence of measured gains.

Runtime dependencies are Python 3.10+, python-pptx 1.0.x, Pillow 10+ and PyMuPDF 1.24+; LibreOffice or a supplied office renderer creates actual previews. These are dependency expectations, not automatic install instructions. Record actual versions for each run. The scripts use relative paths and accept a renderer path. Complex templates, native mathematical editing and chart reconstruction require a local script adapted to the actual case. A successful LibreOffice render is not proof of Microsoft PowerPoint fidelity.
