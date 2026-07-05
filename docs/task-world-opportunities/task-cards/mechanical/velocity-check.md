# ABOUTME: First-pass task-world opportunity card for velocity-check.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / pipe-hydraulics / velocity-check

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/velocity_check`
- Discipline: `mechanical`
- Category: `pipe-hydraulics`
- Tool mode: `with-tool`
- Standards: AWWA M11; Crane TP-410
- Tags: mechanical; pipe; hydraulics; velocity; deterministic

## Current Task Shape

Calculates pipe velocity from flow rate and internal diameter, then compares it with explicit minimum and maximum velocity criteria. The template reports pipe area, velocity, margins, and a numeric range flag.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_l_s` | Pipe flow rate | float / L/s | range=0.0..100000.0 |
| `pipe_internal_diameter_mm` | Pipe internal diameter | float / mm | range=10.0..5000.0 |
| `minimum_velocity_m_s` | Minimum acceptable velocity | float / m/s | range=0.0..20.0 |
| `maximum_velocity_m_s` | Maximum acceptable velocity | float / m/s | range=0.1..50.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pipe_area_m2` | Pipe internal area |  | tolerance=0.03 |
| `velocity_m_s` | Calculated pipe velocity |  | tolerance=0.03 |
| `min_margin_m_s` | Velocity margin above minimum criterion |  | tolerance=0.03 |
| `max_margin_m_s` | Velocity margin below maximum criterion |  | tolerance=0.03 |
| `velocity_within_range` | Numeric flag where 1 means velocity is within the explicit range |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `water_distribution` | Water distribution pipe velocity check | water-distribution-main; pump-discharge |
| `process_pipe` | Industrial process pipe velocity check | process-pipe; utility-pipe |

### Difficulty Notes

```text
easy: all_given | All parameters given for water distribution pipes
medium: all_given | All parameters given across pipe types
hard: all_given | All parameters given for process pipe velocity checks
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `chart-curve`.

Use network schematics, long sections, asset schedules, rating curves, and source tables.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Pipe and channel outputs naturally feed pump station, detention, outfall, and flood-level checks.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_table`, `source_curve`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
