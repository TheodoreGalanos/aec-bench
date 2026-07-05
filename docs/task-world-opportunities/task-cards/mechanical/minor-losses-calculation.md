# ABOUTME: First-pass task-world opportunity card for minor-losses-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / pipe-hydraulics / minor-losses-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/minor_losses_calculation`
- Discipline: `mechanical`
- Category: `pipe-hydraulics`
- Tool mode: `with-tool`
- Standards: Crane TP-410; AWWA M11
- Tags: mechanical; pipe-hydraulics; minor-losses; fittings; deterministic

## Current Task Shape

Calculates total minor head loss through fittings from explicit K factors and quantities. The template reports summed K factor, velocity head, total minor loss, and equivalent straight-pipe length using an explicit Darcy friction factor.

## Existing Deterministic Contract

- Parameters: `9`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `fitting_1_k` | K factor for the first fitting group | float / - | range=0.0..20.0 |
| `fitting_1_quantity` | Quantity of first fitting group | float / - | range=0.0..30.0 |
| `fitting_2_k` | K factor for the second fitting group | float / - | range=0.0..20.0 |
| `fitting_2_quantity` | Quantity of second fitting group | float / - | range=0.0..30.0 |
| `fitting_3_k` | K factor for the third fitting group | float / - | range=0.0..20.0 |
| `fitting_3_quantity` | Quantity of third fitting group | float / - | range=0.0..30.0 |
| `flow_velocity_m_s` | Mean pipe flow velocity | float / m/s | range=0.1..8.0 |
| `pipe_diameter_mm` | Pipe internal diameter | float / mm | range=10.0..3000.0 |
| `darcy_friction_factor` | Darcy friction factor used for equivalent length | float / - | range=0.005..0.08 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `total_k` | Summed fitting K factor |  | tolerance=0.03 |
| `velocity_head_m` | Velocity head |  | tolerance=0.03 |
| `total_minor_loss_m` | Total minor head loss |  | tolerance=0.03 |
| `equivalent_length_m` | Equivalent straight pipe length |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `pump_station_header` | Pump station header with valves and bends | water-pump-station; wastewater-pump-station |
| `process_pipework` | Industrial process pipework fitting loss check | industrial-process-plant; chemical-dosing-skid |

### Difficulty Notes

```text
easy: all_given | All parameters given for pump station pipework
medium: all_given | All parameters given across pump station and process pipework
hard: all_given | All parameters given for process pipework
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

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_table`, `source_curve`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
