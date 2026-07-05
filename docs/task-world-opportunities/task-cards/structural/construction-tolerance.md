# ABOUTME: First-pass task-world opportunity card for construction-tolerance.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / construction-tolerance / construction-tolerance

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/construction_tolerance`
- Discipline: `structural`
- Category: `construction-tolerance`
- Tool mode: `with-tool`
- Standards: AISC 303; EN 1090-2; AS 4100
- Tags: structural; construction; tolerance; fit-up; deterministic

## Current Task Shape

Sums fabrication, erection, survey, movement, and clearance allowances for a deterministic construction tolerance check. The template also reports root-sum-square tolerance for the first four components and calculates the required slot length using the total allowance at both slot ends.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `fabrication_tolerance_mm` | Fabrication tolerance component | float / mm | range=0.0..50.0 |
| `erection_tolerance_mm` | Erection tolerance component | float / mm | range=0.0..75.0 |
| `survey_tolerance_mm` | Survey tolerance component | float / mm | range=0.0..30.0 |
| `movement_allowance_mm` | Movement allowance component | float / mm | range=0.0..100.0 |
| `clearance_mm` | Installation clearance allowance | float / mm | range=0.0..50.0 |
| `component_length_mm` | Nominal component length accommodated by the slot | float / mm | range=50.0..5000.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `total_allowance_mm` | Arithmetic sum of tolerance and clearance components |  | tolerance=0.03 |
| `rss_tolerance_mm` | Root-sum-square tolerance from fabrication, erection, survey, and movement components |  | tolerance=0.03 |
| `required_slot_length_mm` | Slot length required for the component and allowance at both ends |  | tolerance=0.03 |
| `clearance_included_mm` | Clearance allowance included in the total allowance |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `steel_bracket_slot` | Steel bracket slotted connection tolerance check | steel-frame; industrial-platform |
| `facade_panel_slot` | Facade panel slotted fixing tolerance check | facade-support; building-envelope |

### Difficulty Notes

```text
easy: all_given | All parameters given for a steel bracket slot
medium: all_given | All parameters given across bracket and facade slot checks
hard: all_given | All parameters given for a facade panel slot
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use member sketches, details, load schedules, material tables, and standards/specification extracts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_table`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
