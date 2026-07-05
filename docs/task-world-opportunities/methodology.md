# ABOUTME: Defines the repeatable review method for AEC-Bench task-world analysis.
# ABOUTME: Keeps per-task multimodal, composition, and meta-harness notes comparable.

# Methodology

Each task is reviewed as a task-world rather than only as a formula prompt.

## Per-Task Rubric

For every task, record:

| Field | Question |
| --- | --- |
| Current task shape | What does the template currently ask the model to infer or compute? |
| Existing deterministic contract | What inputs, outputs, tolerances, archetypes, and hidden parameters already exist? |
| Multimodal expansion | What image, drawing, table, map, chart, PDF, spreadsheet, sensor trace, or artifact could replace or supplement the visible inputs? |
| Multimodal requirements | What generators, parsers, assets, calibration rules, verifier evidence, and anti-leakage controls would be needed? |
| Harness engineering opportunities | What evidence artifacts, intermediate checks, source authority records, or side-effect files would make the task-world stronger? |
| Natural combinations | Which tasks can pipe outputs to inputs, share context, or form a design workflow? |
| Meta-harness handles | Which projection, subset, difference, or product operations should this world expose? |
| Repair/event candidates | What failure modes should trigger a meta-harness redesign rather than only a wrong-answer mark? |

## Multimodal Families

Use these families consistently when tagging opportunities:

| Family | Examples |
| --- | --- |
| `drawing-geometry` | Plans, sections, elevations, schematics, drainage layouts, road alignment drawings. |
| `tabular-source` | Standards tables, equipment schedules, borehole logs, lighting schedules, cable schedules. |
| `spatial-map` | Catchments, terrain, alignments, flood extents, route context, coastal profiles. |
| `chart-curve` | Pump curves, fan curves, IDF curves, stress-strain curves, gradation curves. |
| `document-evidence` | Design briefs, calculations, RFIs, specifications, datasheets, standards extracts. |
| `time-series` | Demand profiles, rainfall hyetographs, battery load traces, process monitoring. |
| `artifact-production` | JSON records, drawings, calculation sheets, risk registers, reviewer reports. |

## Composition Patterns

Use these composition labels when tasks naturally combine:

| Pattern | Meaning |
| --- | --- |
| `pipeline` | Output from one task becomes an input to another. |
| `shared-context` | Tasks use the same site, asset, drawing, or design brief. |
| `constraint-loop` | A downstream check forces upstream redesign or parameter adjustment. |
| `discipline-interface` | Tasks cross civil, structural, mechanical, electrical, or ground boundaries. |
| `evidence-assembly` | Multiple calculations feed one auditable report or decision artifact. |
| `scenario-portfolio` | Several alternatives are compared under the same verifier/rubric. |

## Meta-Harness Mapping

Map opportunities onto the current meta-harness vocabulary:

| Operation | Task-world use |
| --- | --- |
| `projection` | Isolate one evidence channel, output family, or reasoning obligation. |
| `subset` | Restrict archetypes, difficulties, standards, modalities, or site contexts. |
| `difference` | Remove a scaffold, tool, source table, or visible parameter to create a harder world. |
| `product` | Compose two task-worlds into a multi-step task with merged evidence and gates. |

## Review Discipline

Separate four kinds of claims:

| Claim Type | Evidence Needed |
| --- | --- |
| Present contract | Direct evidence from `params.toml`, `instruction.md`, `engine.py`, or generated task output. |
| Low-risk extension | Straightforward transformation of existing inputs or hidden params into richer source artifacts. |
| Harness engineering idea | Requires new generator, verifier, artifact contract, operation handle, or review mode. |
| Research bet | Plausible but needs a prototype before it should be treated as design direction. |

