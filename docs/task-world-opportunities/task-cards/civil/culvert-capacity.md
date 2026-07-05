# ABOUTME: First-pass task-world opportunity card for culvert-capacity.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / culvert-design / culvert-capacity

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/culvert_capacity`
- Discipline: `civil`
- Category: `culvert-design`
- Tool mode: `both`
- Standards: HDS-5; ARR
- Tags: civil; hydraulics; culvert; drainage; inlet-control; outlet-control

## Current Task Shape

Determines the headwater depth for circular culverts under both inlet control and outlet control conditions per the FHWA HDS-5 methodology, then identifies the controlling condition. Inlet control uses regression-based unsubmerged/submerged equations while outlet control applies an energy balance with entrance, friction, and exit losses. Used in road drainage design to verify that headwater elevations remain within acceptable limits.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `4`
- Archetypes: `5`
- Visibility mix: all_given; partial
- Hidden parameters: `invert_elevation_m`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `culvert_diameter_m` | Internal culvert diameter D | float / m | range=0.3..3.0 |
| `culvert_length_m` | Culvert barrel length L | float / m | range=5.0..100.0 |
| `culvert_slope_m_per_m` | Culvert barrel slope S | float / m/m | range=0.001..0.1 |
| `design_flow_m3_s` | Design discharge Q through the culvert | float / m³/s | range=0.1..30.0 |
| `culvert_configuration` | Culvert material and inlet type combination | enum | values=concrete_square_edge_headwall, concrete_groove_end_headwall, concrete_groove_end_projecting, cmp_headwall, cmp_mitered, cmp_projecting; derivable_from=archetype |
| `tailwater_depth_m` | Tailwater depth above outlet invert TW | float / m | range=0.0..5.0 |
| `invert_elevation_m` | Inlet invert elevation | float / m AHD | range=10.0..200.0; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `inlet_control_hw_m` | Headwater depth above inlet invert under inlet control (m) |  | tolerance=0.05 |
| `outlet_control_hw_m` | Headwater depth above inlet invert under outlet control (m) |  | tolerance=0.05 |
| `controlling_condition` | Controlling condition: 1.0 = inlet control, 2.0 = outlet control |  | tolerance=0.01 |
| `headwater_elevation_m` | Headwater elevation at controlling condition (m AHD) |  | tolerance=0.05 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `urban_culvert` | Urban road culvert crossing in a developed catchment | sydney-road-crossing; brisbane-suburban-culvert; melbourne-trunk-drainage |
| `highway_culvert` | Highway culvert crossing with moderate to high design flow | perth-highway-crossing; pacific-highway-upgrade |
| `rural_crossing` | Rural creek or farm track culvert crossing | adelaide-rural-access; hobart-farm-crossing; gippsland-farm-track |
| `hillside_crossing` | Steep terrain culvert crossing with significant grade | toowoomba-hillside-road; blue-mountains-crossing |
| `tropical_crossing` | Tropical region culvert crossing with high rainfall intensity | darwin-rural-road; cairns-forestry-access |

### Difficulty Notes

```text
easy: all_given | Concrete culvert with headwall, all parameters given, moderate flow
medium: all_given | Any material and inlet type, all parameters given, wider flow range
hard: partial | hidden=invert_elevation_m | Invert elevation hidden, agent must infer from site context
```

## Multimodal Expansion

Candidate modality families: `spatial-map`, `tabular-source`, `time-series`.

Use catchment plans, rainfall tables, hyetographs, and drainage schedules as source artifacts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Connect rainfall/runoff outputs to detention, pipe, HGL, outlet, and water-quality checks.

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
