# ABOUTME: First-pass task-world opportunity card for escalator-capacity.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / escalator-design / escalator-capacity

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/escalator_capacity`
- Discipline: `electrical`
- Category: `escalator-design`
- Tool mode: `with-tool`
- Standards: EN 115-1; AS 1735.10
- Tags: electrical; escalator; capacity; vertical-transportation; deterministic

## Current Task Shape

Calculates escalator passenger capacity from escalator speed, step pitch, step width, and practical loading factor. The reduced method converts speed to steps per second, assigns one or two persons per step from width, then reports theoretical and practical hourly capacity.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `practical_loading_factor_pct`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `escalator_speed_m_s` | Escalator running speed | float / m/s | range=0.3..0.9 |
| `step_width_mm` | Nominal step width | float / mm | range=500..1200 |
| `step_pitch_mm` | Step pitch along travel direction | float / mm | range=300..500 |
| `practical_loading_factor_pct` | Practical passenger loading factor | float / % | range=20..100 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `steps_per_second` | Steps passing the comb per second |  | tolerance=0.03 |
| `persons_per_step` | Assumed persons per step from step width |  | tolerance=0.01 |
| `theoretical_capacity_persons_per_h` | Theoretical passenger capacity |  | tolerance=0.03 |
| `practical_capacity_persons_per_h` | Practical passenger capacity |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `narrow_escalator` | Narrow escalator with one person per step | retail-escalator; station-secondary-access |
| `wide_escalator` | Wide escalator with two persons per step | rail-station; airport-terminal |

### Difficulty Notes

```text
easy: all_given | Narrow escalator capacity
medium: all_given | Narrow or wide escalator
hard: partial | hidden=practical_loading_factor_pct | Practical loading factor hidden in site context
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
