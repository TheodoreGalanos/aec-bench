# ABOUTME: First-pass task-world opportunity card for darcy-weisbach-headloss.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / pipe-hydraulics / darcy-weisbach-headloss

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/darcy_weisbach_headloss`
- Discipline: `civil`
- Category: `pipe-hydraulics`
- Tool mode: `with-tool`
- Standards: AWWA; Darcy-Weisbach; Swamee-Jain (1976)
- Tags: civil; pipe-hydraulics; head-loss; friction-factor; deterministic

## Current Task Shape

Calculates friction head loss in pressurised pipe flow using the Darcy-Weisbach equation hf = f * (L/D) * V^2/(2g), with the friction factor determined by the Swamee-Jain explicit approximation for turbulent flow or f = 64/Re for laminar flow. Computes Reynolds number and flow velocity as intermediate results. Used in water supply and hydraulic pipeline design to size pipes and evaluate pressure losses.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `roughness_height_mm`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_m3_s` | Volumetric flow rate Q | float / m³/s | range=0.01..2.0 |
| `pipe_diameter_m` | Internal pipe diameter D | float / m | range=0.05..2.0 |
| `pipe_length_m` | Pipe length L | float / m | range=10..5000 |
| `roughness_height_mm` | Absolute roughness height epsilon | float / mm | range=0.01..5.0; derivable_from=archetype |
| `kinematic_viscosity_m2_s` | Kinematic viscosity of the fluid nu | float / m²/s | range=5e-07..1.5e-05 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_velocity_m_s` | Mean flow velocity V (m/s) |  | tolerance=0.03 |
| `reynolds_number` | Reynolds number Re |  | tolerance=0.03 |
| `friction_factor` | Darcy friction factor f |  | tolerance=0.05 |
| `head_loss_m` | Friction head loss hf (m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `new_pvc` | New PVC or HDPE pipeline | sydney-greenfield; brisbane-suburban |
| `new_ductile_iron` | New cement-lined ductile iron pipeline | melbourne-trunk-main; adelaide-distribution |
| `aged_cast_iron` | Aged unlined cast iron pipeline with moderate tuberculation | sydney-inner-west-legacy; melbourne-inner-legacy |
| `corrugated_steel` | Corrugated steel drainage culvert | darwin-rural-crossing; cairns-rural-crossing |

### Difficulty Notes

```text
easy: all_given | All parameters given, smooth pipe, moderate flow
medium: all_given | All parameters given, any pipe material and flow regime
hard: partial | hidden=roughness_height_mm | Roughness hidden, agent must infer from pipe material description
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
