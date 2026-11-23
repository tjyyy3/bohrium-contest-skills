# Minimal local invocation (synthetic illustration)

Save the following two UTF-8 lines as `mirror.txt`:

    Results. The mirror displacement was 0.40 mm.
    Abstract. The same displacement was 4.0 mm.

Ask the agent: “Review numeric consistency in mirror.txt, case mirror-demo. Return case_id, status, findings, coverage, changes and limits as JSON.” Put the input in the working directory. In a POSIX shell with the Skill installed, run:

    S=/skills/weekly-skill
    python "$S/anchors.py" index mirror.txt mirror.index.json
    python "$S/anchors.py" show mirror.index.json 1
    python "$S/anchors.py" check anchors.json mirror.index.json

Before the last command save this working array to `anchors.json`:

    [{"source":"mirror.txt","page":1,"first":1,"last":1,"quote":"0.40 mm"},{"source":"mirror.txt","page":1,"first":2,"last":2,"quote":"4.0 mm"}]

Illustrative output under this example's contract:

    {
      "case_id":"mirror-demo","status":"complete",
      "findings":[{"id":"F1","type":"factual inconsistency","severity":"major",
        "confidence":"high for the mismatch; true value unresolved",
        "claim":"mirror.txt, Abstract, p1 l2: 4.0 mm",
        "evidence":"mirror.txt, Results, p1 l1: 0.40 mm",
        "basis":"Both refer to the same displacement and unit; 4.0/0.40 = 10. The central result changes by a factor of ten.",
        "revision":"Check the measurement log and update the conflicting section. Confirm the two statements give the same logged displacement."}],
      "coverage":[{"check":"numeric consistency","status":"issue","ids":["F1"]}],
      "changes":["Indexed the supplied version, compared values and replayed both locations. Proposed a correction; no source edit."],
      "limits":["The measurement log is needed to select the correct value."]
    }

Formal cases set their own required checks, fields and source boundaries.
