# ABOUTME: First-pass task-world opportunity card for pedestrian-clearance-time.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / signal-timing / pedestrian-clearance-time

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/pedestrian_clearance_time`
- Discipline: `electrical`
- Category: `signal-timing`
- Tool mode: `with-tool`
- Standards: MUTCD; AS 1742.14
- Tags: electrical; traffic-signals; pedestrian; clearance-time; signal-timing; deterministic

## Current Task Shape

Calculates the pedestrian clearance interval for a signalised crossing from crosswalk length and assumed walking speed. The deterministic relation divides crossing distance by walking speed and reports both exact and whole-second rounded flashing clearance time.

## Existing Deterministic Contract

- Parameters: `2`
- Outputs: `2`
- Archetypes: `3`
- Visibility mix: all_given; partial
- Hidden parameters: `walking_speed_m_s`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `crosswalk_length_m` | Crosswalk length | float / m | range=3..60 |
| `walking_speed_m_s` | Design pedestrian walking speed | float / m/s | range=0.6..1.8 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pedestrian_clearance_time_s` | Calculated pedestrian clearance time |  | tolerance=0.03 |
| `pedestrian_clearance_rounded_s` | Clearance time rounded up to a whole second |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `short_crossing` | Short urban pedestrian crossing | urban-intersection; local-street |
| `wide_crossing` | Wide arterial or staged crossing | arterial-road; transport-interchange |
| `accessible_crossing` | Accessible design crossing with slower walking speed | hospital-precinct; aged-care-frontage |

### Difficulty Notes

```text
easy: all_given | Short crossing with all inputs visible
medium: all_given | Urban or arterial crossing
hard: partial | hidden=walking_speed_m_s | Walking speed hidden in accessibility context
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
