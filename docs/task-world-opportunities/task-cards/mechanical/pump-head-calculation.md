# ABOUTME: First-pass task-world opportunity card for pump-head-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / pump-hydraulics / pump-head-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/pump_head_calculation`
- Discipline: `mechanical`
- Category: `pump-hydraulics`
- Tool mode: `with-tool`
- Standards: Hydraulic Institute Standards
- Tags: mechanical; pump-hydraulics; total-dynamic-head; hydraulic-power; deterministic

## Current Task Shape

Calculates total dynamic head for a pump duty point by converting suction and discharge pressure difference, pipe losses, and static elevation difference into metres of fluid head. The template also calculates hydraulic power from flow, fluid density, gravitational acceleration, and total dynamic head.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `5`
- Archetypes: `3`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_m3_h` | Pump flow rate | float / m3/h | range=1.0..5000.0 |
| `suction_pressure_kpa` | Suction pressure at pump inlet | float / kPa | range=-80.0..1000.0 |
| `discharge_pressure_kpa` | Discharge pressure at pump outlet | float / kPa | range=-50.0..3000.0 |
| `elevation_difference_m` | Discharge elevation minus suction elevation | float / m | range=-20.0..200.0 |
| `pipe_friction_losses_kpa` | Pipe friction and minor losses | float / kPa | range=0.0..1000.0 |
| `fluid_density_kg_m3` | Fluid density | float / kg/m3 | range=600.0..1300.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `static_head_m` | Static elevation head |  | tolerance=0.03 |
| `pressure_head_differential_m` | Pressure head differential |  | tolerance=0.03 |
| `friction_head_m` | Friction loss head |  | tolerance=0.03 |
| `total_dynamic_head_m` | Total dynamic head |  | tolerance=0.03 |
| `hydraulic_power_kw` | Hydraulic power |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `water_transfer_pump` | Water transfer pump with moderate pressure rise | water-treatment-transfer; reservoir-booster |
| `process_liquid_pump` | Industrial process liquid pump | industrial-process-skid; chemical-transfer-loop |
| `high_head_booster` | High-head booster pump | mine-water-booster; district-pressure-zone |

### Difficulty Notes

```text
easy: all_given | All parameters given for a water transfer pump
medium: all_given | All parameters given for water and process liquid pumps
hard: all_given | All parameters given for higher-head pump duties
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
