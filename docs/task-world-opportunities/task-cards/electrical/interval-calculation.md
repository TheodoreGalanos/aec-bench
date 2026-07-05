# ABOUTME: First-pass task-world opportunity card for interval-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / traffic-analysis / interval-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/interval_calculation`
- Discipline: `electrical`
- Category: `traffic-analysis`
- Tool mode: `with-tool`
- Standards: CIBSE Guide D
- Tags: electrical; lifts; vertical-transportation; interval; deterministic

## Current Task Shape

Calculates the average waiting interval between lift arrivals by dividing round-trip time by the number of lifts. The template also reports the number of lift arrivals available in a five-minute assessment period.

## Existing Deterministic Contract

- Parameters: `2`
- Outputs: `2`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `lift_count`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `round_trip_time_s` | Lift round-trip time | float / s | range=20..600 |
| `lift_count` | Number of lifts in the group | float | range=1..16 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `interval_s` | Average interval between lift arrivals |  | tolerance=0.03 |
| `arrivals_per_5min` | Lift arrivals in a five-minute period |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_group` | Small lift group in a low- or mid-rise building | low-rise-office; apartment-core |
| `large_group` | Larger lift group in a commercial building | commercial-tower; hospital-core |

### Difficulty Notes

```text
easy: all_given | Small lift group with all values visible
medium: all_given | Small or large lift group
hard: partial | hidden=lift_count | Lift count hidden in group context
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
