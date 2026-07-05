# ABOUTME: First-pass task-world opportunity card for pipe-velocity-check.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / pipe-hydraulics / pipe-velocity-check

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/pipe_velocity_check`
- Discipline: `civil`
- Category: `pipe-hydraulics`
- Tool mode: `with-tool`
- Standards: AS/NZS 3500.1 Clause 3.4
- Tags: civil; pipe-hydraulics; velocity; compliance; deterministic

## Current Task Shape

Calculates full-bore pipe flow velocity from V = Q/A and checks compliance against minimum and maximum velocity limits specified in AS/NZS 3500.1 for water supply, gravity sewer, stormwater, and fire service pipes. Ensures velocities remain within self-cleansing and scour-prevention bounds for the given service type.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `2`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `service_type`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pipe_diameter_mm` | Internal pipe diameter D | float / mm | range=15..1200 |
| `flow_rate_l_s` | Volumetric flow rate Q | float / L/s | range=0.1..2000 |
| `service_type` | Pipe service type per AS/NZS 3500.1 | enum | values=water_supply, sewer_gravity, stormwater, fire_services; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `velocity_m_s` | Flow velocity V (m/s) |  | tolerance=0.03 |
| `compliance` | Velocity compliance (1.0 = within limits, 0.0 = outside limits) |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_water_supply` | Residential water supply reticulation in PVC or copper | sydney-suburban-estate; brisbane-residential-infill |
| `trunk_sewer` | Trunk gravity sewer main in reinforced concrete or vitrified clay | melbourne-trunk-sewer; adelaide-catchment-sewer |
| `stormwater_main` | Stormwater drainage main in reinforced concrete pipe | perth-urban-drainage; darwin-monsoon-drainage |
| `fire_hydrant_main` | Fire hydrant main in ductile iron or HDPE | canberra-commercial-precinct; hobart-industrial-park |

### Difficulty Notes

```text
easy: all_given | All parameters given, water supply only, small residential pipes
medium: all_given | All parameters given, any service type and pipe size
hard: partial | hidden=service_type | Service type hidden, agent must infer from site description
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `chart-curve`.

Use network schematics, long sections, asset schedules, rating curves, and source tables.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Pipe and channel outputs naturally feed pump station, detention, outfall, and flood-level checks.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`, `source_curve`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
