# ABOUTME: First-pass task-world opportunity card for conduit-fill-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / structured-cabling / conduit-fill-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/conduit_fill_calculation`
- Discipline: `electrical`
- Category: `structured-cabling`
- Tool mode: `with-tool`
- Standards: ANSI/TIA-569; AS/NZS 3080
- Tags: electrical; conduit; fill; structured-cabling; deterministic

## Current Task Shape

Calculates conduit fill for identical circular cables in a circular conduit. The deterministic method sums cable cross-sectional area, computes conduit internal area, reports fill percentage, and gives margin against an explicit maximum fill percentage.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `maximum_fill_pct`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `conduit_internal_diameter_mm` | Conduit internal diameter | float / mm | range=10..200 |
| `cable_count` | Number of identical cables | float | range=1..200 |
| `cable_outer_diameter_mm` | Cable outer diameter | float / mm | range=1..50 |
| `maximum_fill_pct` | Maximum permitted fill percentage | float / % | range=10..80 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `total_cable_area_mm2` | Total cable cross-sectional area |  | tolerance=0.03 |
| `conduit_area_mm2` | Conduit internal cross-sectional area |  | tolerance=0.03 |
| `fill_percentage` | Conduit fill percentage |  | tolerance=0.03 |
| `fill_margin_pct` | Margin below the maximum fill percentage |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_data_conduit` | Small structured cabling conduit | office-cabling; comms-room |
| `large_cable_pathway` | Larger pathway for multiple communications cables | station-cabling; campus-backbone |

### Difficulty Notes

```text
easy: all_given | Small conduit with all dimensions visible
medium: all_given | Small or larger conduit fill
hard: partial | hidden=maximum_fill_pct | Maximum fill hidden in cabling standard context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `time-series`.

Use single-line diagrams, layouts, device schedules, demand profiles, and equipment datasheets.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`, `source_timeseries`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
