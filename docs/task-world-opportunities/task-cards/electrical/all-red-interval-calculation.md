# ABOUTME: First-pass task-world opportunity card for all-red-interval-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / signal-timing / all-red-interval-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/all_red_interval_calculation`
- Discipline: `electrical`
- Category: `signal-timing`
- Tool mode: `with-tool`
- Standards: MUTCD; AS 1742.14
- Tags: electrical; traffic-signals; all-red; clearance; deterministic

## Current Task Shape

Calculates the all-red clearance interval for a vehicle to clear an intersection after yellow. The reduced method divides intersection width plus vehicle length by vehicle speed, rounds the operational interval to one decimal place, and caps it at six seconds.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `vehicle_speed_m_s`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `intersection_width_m` | Distance across the conflict area | float / m | range=3..80 |
| `vehicle_length_m` | Design vehicle length | float / m | range=3..30 |
| `vehicle_speed_m_s` | Vehicle clearance speed | float / m/s | range=1..35 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `clearance_distance_m` | Total clearance distance |  | tolerance=0.03 |
| `raw_all_red_interval_s` | Uncapped clearance interval |  | tolerance=0.03 |
| `all_red_interval_s` | Rounded all-red interval capped at six seconds |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `urban_intersection` | Urban signalised intersection | urban-intersection; arterial-road |
| `wide_intersection` | Wide intersection with longer design vehicles | freight-route; multi-lane-arterial |

### Difficulty Notes

```text
easy: all_given | Urban intersection with all values visible
medium: all_given | Urban or wide intersection
hard: partial | hidden=vehicle_speed_m_s | Vehicle speed hidden in clearance context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `spatial-map`.

Use layout plans, device schedules, coverage diagrams, timing tables, and network topology artifacts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Communications and ITS tasks combine through shared layouts, device counts, coverage, storage, and power constraints.

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
