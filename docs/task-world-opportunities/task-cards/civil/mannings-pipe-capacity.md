# ABOUTME: First-pass task-world opportunity card for mannings-pipe-capacity.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / hydraulic-calculations / mannings-pipe-capacity

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/mannings_pipe_capacity`
- Discipline: `civil`
- Category: `hydraulic-calculations`
- Tool mode: `with-tool`
- Standards: HEC-22; QUDM; PUB Code of Practice
- Tags: civil; hydraulics; drainage; pipe-flow; deterministic

## Current Task Shape

Computes the flow capacity, velocity, flow area, and hydraulic radius of circular drainage pipes using Manning's equation Q = (1/n) * A * R^(2/3) * S^(1/2), supporting both full and partially full pipe flow via the central angle geometry method. Used in stormwater and sewer pipe sizing per HEC-22 and QUDM to verify that pipe capacity meets the design discharge.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `mannings_n`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pipe_diameter_m` | Internal pipe diameter D | float / m | range=0.15..3.0 |
| `mannings_n` | Manning's roughness coefficient n | float | range=0.009..0.025; derivable_from=archetype |
| `slope_m_per_m` | Longitudinal pipe slope S | float / m/m | range=0.001..0.1 |
| `flow_depth_ratio` | Flow depth to diameter ratio d/D (1.0 = full) | float | range=0.1..1.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_area_m2` | Flow cross-sectional area A (m²) |  | tolerance=0.03 |
| `hydraulic_radius_m` | Hydraulic radius R (m) |  | tolerance=0.03 |
| `flow_velocity_m_s` | Flow velocity V (m/s) |  | tolerance=0.03 |
| `flow_capacity_m3_s` | Flow capacity Q (m³/s) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `concrete_pipe` | Concrete stormwater pipe | brisbane-suburban-drainage; sydney-trunk-stormwater |
| `pvc_pipe` | PVC or HDPE smooth-wall pipe | perth-residential-drainage; melbourne-subdivision |
| `corrugated_metal_pipe` | Corrugated metal pipe (CMP) | darwin-rural-crossing; cairns-temporary-diversion |
| `vitrified_clay_pipe` | Vitrified clay sewer pipe | adelaide-heritage-sewer; hobart-infill-drainage |

### Difficulty Notes

```text
easy: all_given | Full pipe flow, all parameters given
medium: all_given | Partially full flow, all parameters given
hard: partial | hidden=mannings_n | Partially full flow, roughness coefficient hidden
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
