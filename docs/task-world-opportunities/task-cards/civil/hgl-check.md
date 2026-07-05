# ABOUTME: First-pass task-world opportunity card for hgl-check.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / stormwater-piped / hgl-check

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/hgl_check`
- Discipline: `civil`
- Category: `stormwater-piped`
- Tool mode: `with-tool`
- Standards: ARR 2019; QUDM; Local Council DCPs
- Tags: civil; stormwater; hydraulic-grade-line; surcharge; deterministic

## Current Task Shape

Computes the hydraulic grade line (HGL) at the upstream pit of a single stormwater pipe reach using Manning's equation for friction loss and a pit loss coefficient for junction losses. Checks whether the HGL remains below the pit surface level with adequate clearance to prevent surcharging, following ARR 2019 and local council DCP methods.

## Existing Deterministic Contract

- Parameters: `8`
- Outputs: `7`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `mannings_n`, `pit_loss_coefficient`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_flow_m3_per_s` | Design peak flow Q at the pipe reach | float / m³/s | range=0.01..4.0 |
| `pipe_diameter_mm` | Nominal internal pipe diameter DN | enum / mm | values=225, 300, 375, 450, 525, 600, 750, 900, 1050, 1200 |
| `pipe_length_m` | Pipe reach length L between pits | float / m | range=10.0..150.0 |
| `mannings_n` | Manning's roughness coefficient n for the pipe material | float | range=0.009..0.025; derivable_from=archetype |
| `pit_loss_coefficient` | Pit/junction loss coefficient K (dimensionless) | float | range=0.0..5.0; derivable_from=archetype |
| `tailwater_level_m` | HGL at the downstream pit (tailwater condition) | float / m AHD | range=2.0..30.0 |
| `surface_level_m` | Surface level at the upstream pit | float / m AHD | range=4.0..35.0 |
| `minimum_clearance_mm` | Minimum required clearance between HGL and surface level | float / mm | range=50.0..500.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_velocity_m_per_s` | Pipe flow velocity V (m/s) |  | tolerance=0.03 |
| `friction_loss_m` | Friction head loss h_f through the pipe (m) |  | tolerance=0.03 |
| `pit_loss_m` | Pit/junction head loss h_pit (m) |  | tolerance=0.03 |
| `hgl_upstream_m` | HGL elevation at the upstream pit (m AHD) |  | tolerance=0.03 |
| `clearance_mm` | Clearance between surface level and HGL (mm), positive = below surface |  | tolerance=10.0 |
| `surcharge_ratio` | HGL to surface level ratio (> 1.0 indicates surcharging) |  | tolerance=0.03 |
| `pass_fail` | Surcharge compliance (1.0 = pass, clearance adequate; 0.0 = fail) |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `concrete_pipe_straight` | Reinforced concrete pipe through a straight-through pit with benched invert | brisbane-suburban-drainage; sydney-greenfield-subdivision |
| `concrete_pipe_bend` | Reinforced concrete pipe through a pit with a change in direction | melbourne-trunk-stormwater; adelaide-urban-renewal |
| `pvc_pipe_residential` | PVC pipe in a residential inter-allotment drainage pit | perth-residential-estate; gold-coast-infill-development |
| `large_trunk_main` | Large reinforced concrete trunk main through a junction pit with multiple inlets | sydney-trunk-stormwater; brisbane-creek-diversion |

### Difficulty Notes

```text
easy: all_given | Small pipe, straight pit, all parameters given including Manning's n and pit loss K
medium: all_given | Any pipe size and pit configuration, all parameters given
hard: partial | hidden=mannings_n, pit_loss_coefficient | Manning's n and pit loss K hidden, agent must infer from pipe material and junction description
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
