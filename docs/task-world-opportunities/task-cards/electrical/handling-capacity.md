# ABOUTME: First-pass task-world opportunity card for handling-capacity.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / traffic-analysis / handling-capacity

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/handling_capacity`
- Discipline: `electrical`
- Category: `traffic-analysis`
- Tool mode: `with-tool`
- Standards: CIBSE Guide D
- Tags: electrical; lifts; handling-capacity; vertical-transportation; deterministic

## Current Task Shape

Calculates the five-minute handling capacity of a lift group from building population, round-trip time, car capacity, number of lifts, and car loading factor. The reduced method reports passengers carried in five minutes and capacity as a percentage of population.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `2`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `car_loading_factor_pct`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `building_population` | Population served by the lift group | float | range=10..20000 |
| `round_trip_time_s` | Lift round-trip time | float / s | range=20..600 |
| `car_capacity_persons` | Rated lift car capacity in persons | float | range=2..40 |
| `lift_count` | Number of lifts in the group | float | range=1..16 |
| `car_loading_factor_pct` | Effective car loading factor | float / % | range=30..100 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `passengers_per_5min` | Passengers transported in five minutes |  | tolerance=0.03 |
| `handling_capacity_pct` | Five-minute handling capacity as population percentage |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_group` | Residential lift group | apartment-core; mixed-use-tower |
| `office_group` | Commercial office lift group | office-tower; campus-office |

### Difficulty Notes

```text
easy: all_given | Residential group with all inputs visible
medium: all_given | Residential or office lift group
hard: partial | hidden=car_loading_factor_pct | Loading factor hidden in traffic design context
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
