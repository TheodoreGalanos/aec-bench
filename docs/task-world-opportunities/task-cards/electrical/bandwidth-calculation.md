# ABOUTME: First-pass task-world opportunity card for bandwidth-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / its-communications / bandwidth-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/bandwidth_calculation`
- Discipline: `electrical`
- Category: `its-communications`
- Tool mode: `with-tool`
- Standards: IEEE 802.3; NTCIP
- Tags: electrical; its; communications; bandwidth; network; deterministic

## Current Task Shape

Calculates network bandwidth demand for an ITS device inventory by summing camera, controller, and sensor data rates. The reduced method applies a network overhead allowance and future capacity buffer to produce base, peak, and required bandwidth values.

## Existing Deterministic Contract

- Parameters: `8`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `future_capacity_buffer_pct`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `camera_count` | Number of cameras | float | range=0..200 |
| `camera_data_rate_mbps` | Data rate per camera | float / Mbps | range=0..50 |
| `controller_count` | Number of controllers | float | range=0..200 |
| `controller_data_rate_mbps` | Data rate per controller | float / Mbps | range=0..5 |
| `sensor_count` | Number of sensors | float | range=0..1000 |
| `sensor_data_rate_mbps` | Data rate per sensor | float / Mbps | range=0..5 |
| `network_overhead_pct` | Network protocol and peak overhead allowance | float / % | range=0..50 |
| `future_capacity_buffer_pct` | Future capacity buffer | float / % | range=0..100 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `base_bandwidth_mbps` | Device bandwidth before allowances |  | tolerance=0.03 |
| `peak_demand_mbps` | Bandwidth after network overhead |  | tolerance=0.03 |
| `required_bandwidth_mbps` | Bandwidth after overhead and future buffer |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_intersection` | Small signalised intersection communications node | urban-intersection; suburban-corridor |
| `corridor_network` | Road corridor ITS aggregation network | motorway-corridor; tunnel-approach |

### Difficulty Notes

```text
easy: all_given | Small node with all rates given
medium: all_given | Mixed ITS device inventory
hard: partial | hidden=future_capacity_buffer_pct | Future buffer hidden in corridor planning context
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
