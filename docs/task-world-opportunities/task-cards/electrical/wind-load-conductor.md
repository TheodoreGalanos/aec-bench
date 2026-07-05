# ABOUTME: First-pass task-world opportunity card for wind-load-conductor.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / structural-loading / wind-load-conductor

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/wind_load_conductor`
- Discipline: `electrical`
- Category: `structural-loading`
- Tool mode: `with-tool`
- Standards: IEC 60826; AS/NZS 7000
- Tags: electrical; transmission-line; wind-load; conductor; deterministic

## Current Task Shape

Calculates a reduced overhead conductor wind load using an explicit terrain height exponent, conductor diameter, drag coefficient, and span length. The template is a deterministic structural-loading calculation for line design screening.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `terrain_category`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `wind_pressure_pa` | Reference wind pressure at 10 m | float / Pa | range=100..2500 |
| `conductor_diameter_mm` | Conductor outside diameter | float / mm | range=5..80 |
| `span_length_m` | Conductor span length | float / m | range=20..800 |
| `drag_coefficient` | Conductor drag coefficient | float / - | range=0.8..1.5 |
| `terrain_category` | Reduced terrain category | enum / - | values=open, suburban, urban |
| `height_above_ground_m` | Conductor height above ground | float / m | range=5..80 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `height_adjusted_wind_pressure_pa` | Wind pressure adjusted from 10 m to conductor height |  | tolerance=0.03 |
| `wind_load_per_unit_length_n_m` | Transverse wind load per metre of conductor |  | tolerance=0.03 |
| `transverse_wind_load_n` | Total transverse wind load over the span |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `distribution_span` | Distribution overhead line span | distribution-line; overhead-conductor |
| `transmission_span` | Transmission overhead line span | transmission-line; overhead-conductor |

### Difficulty Notes

```text
easy: all_given | Distribution span with all values visible
medium: all_given | Overhead span selected from distribution or transmission cases
hard: partial | hidden=terrain_category | Transmission span with terrain category embedded in context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use building elevations, terrain/zone diagrams, load schedules, and standards extracts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Wind-speed and pressure derivations can feed structural member, bracket, cladding, and foundation checks.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
