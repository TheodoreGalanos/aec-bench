# ABOUTME: Gap log for real-world stormwater drainage grounding.
# ABOUTME: Records missing standards, examples, and source artifacts needed before task hardening.

# Stormwater Gaps

- Locate and index FHWA HEC-22 4th edition, if publicly accessible.
- Scrape additional Australian Rainfall and Runoff books/sections relevant to peak-flow estimation, flood hydraulics, detention, and climate change factors. Book 9/Data Hub/BOM IFD now cover urban-runoff framing and rainfall-source surfaces, but not a full local drainage approval package.
- Find public local council/state drainage design manuals with calculation/report templates.
- Convert the docs-only `swmm_example3_detention_source_pack/` into a runtime fixture when task changes are allowed: decide EPA source-file inclusion/download policy, use a controlled SWMM engine path, run or parse SWMM outputs, preserve the known manual/model mismatches, and generate machine-checkable continuity, node/link summary, and acceptance evidence. A temporary `swmm-toolkit` attempt failed at native binding import in this environment.
- Identify a real stormwater design report that includes catchment plan, drainage long section, outlet detail, and detention summary.
- Find public model-output reports or municipal/council accepted calculation appendices to complement the EPA teaching examples.
