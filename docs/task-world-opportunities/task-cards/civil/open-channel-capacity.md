# ABOUTME: First-pass task-world opportunity card for open-channel-capacity.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / hydraulic-calculations / open-channel-capacity

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/open_channel_capacity`
- Discipline: `civil`
- Category: `hydraulic-calculations`
- Tool mode: `with-tool`
- Standards: HEC-22; ARR
- Tags: civil; hydraulics; drainage; open-channel; mannings; deterministic

## Current Task Shape

Computes flow area, wetted perimeter, hydraulic radius, velocity, discharge capacity, and Froude number for trapezoidal or rectangular open channels using Manning's equation V = (1/n)*R^(2/3)*S^(1/2). Used in drainage and flood conveyance design per HEC-22 and Australian Rainfall and Runoff (ARR) standards.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `6`
- Archetypes: `5`
- Visibility mix: all_given; partial
- Hidden parameters: `mannings_n`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `bottom_width_m` | Channel bottom width b | float / m | range=0.3..10.0 |
| `flow_depth_m` | Flow depth y | float / m | range=0.1..5.0 |
| `side_slope_z` | Side slope ratio z (horizontal:vertical, 0 for rectangular) | float / - | range=0.0..4.0 |
| `mannings_n` | Manning's roughness coefficient n | float | range=0.01..0.06; derivable_from=archetype |
| `channel_slope_m_per_m` | Longitudinal channel slope S | float / m/m | range=0.0005..0.1 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_area_m2` | Flow cross-sectional area A (m²) |  | tolerance=0.03 |
| `wetted_perimeter_m` | Wetted perimeter P (m) |  | tolerance=0.03 |
| `hydraulic_radius_m` | Hydraulic radius R (m) |  | tolerance=0.03 |
| `flow_velocity_m_s` | Flow velocity V (m/s) |  | tolerance=0.03 |
| `flow_capacity_m3_s` | Flow capacity Q (m³/s) |  | tolerance=0.03 |
| `froude_number` | Froude number Fr (dimensionless) |  | tolerance=0.05 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `concrete_lined` | Concrete-lined trapezoidal channel | brisbane-trunk-drainage; sydney-stormwater-channel |
| `grassed_channel` | Grassed or turfed drainage swale | melbourne-suburban-swale; perth-bioretention-swale |
| `riprap_lined` | Riprap or rock-lined channel | darwin-creek-stabilisation; cairns-erosion-control |
| `natural_earth` | Unlined natural earth channel | adelaide-rural-drain; hobart-farm-channel |
| `gabion_lined` | Gabion-lined channel | gold-coast-creek-works; townsville-flood-channel |

### Difficulty Notes

```text
easy: all_given | Rectangular channel (z = 0), all parameters given
medium: all_given | Trapezoidal channel, all parameters given
hard: partial | hidden=mannings_n | Trapezoidal channel, roughness coefficient hidden
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
