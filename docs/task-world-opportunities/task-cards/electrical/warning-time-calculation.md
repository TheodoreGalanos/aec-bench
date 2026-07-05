# ABOUTME: First-pass task-world opportunity card for warning-time-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / level-crossings / warning-time-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/warning_time_calculation`
- Discipline: `electrical`
- Category: `level-crossings`
- Tool mode: `with-tool`
- Standards: AS 7711; Network Rail standards
- Tags: electrical; rail; level-crossing; warning-time; signalling; deterministic

## Current Task Shape

Calculates total level crossing warning time by summing minimum road-user warning time, clearance time, barrier lowering time, and system delay. The template converts maximum train speed to m/s and computes the required strike-in detection distance.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `system_delay_s`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `maximum_train_speed_kmh` | Maximum train speed | float / km/h | range=5..200 |
| `minimum_warning_time_s` | Minimum road-user warning time | float / s | range=5..120 |
| `road_user_clearance_time_s` | Road user clearance time | float / s | range=0..60 |
| `barrier_lowering_time_s` | Barrier lowering or equipment operating time | float / s | range=0..30 |
| `system_delay_s` | Signal processing and system delay | float / s | range=0..20 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `maximum_train_speed_m_s` | Maximum train speed converted to m/s |  | tolerance=0.01 |
| `total_warning_time_s` | Total warning time used for strike-in |  | tolerance=0.03 |
| `strike_in_distance_m` | Strike-in detection distance |  | tolerance=0.03 |
| `minimum_warning_margin_s` | Additional time above the minimum warning time |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `low_speed_crossing` | Low-speed urban or yard crossing | urban-crossing; yard-access |
| `mainline_crossing` | Mainline level crossing with active controls | regional-mainline; suburban-mainline |

### Difficulty Notes

```text
easy: all_given | Low-speed crossing with all timing values visible
medium: all_given | Low-speed or mainline crossing
hard: partial | hidden=system_delay_s | System delay hidden in signalling context
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
