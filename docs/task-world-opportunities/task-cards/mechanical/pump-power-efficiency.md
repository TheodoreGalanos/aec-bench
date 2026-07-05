# ABOUTME: First-pass task-world opportunity card for pump-power-efficiency.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / pump-hydraulics / pump-power-efficiency

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/pump_power_efficiency`
- Discipline: `mechanical`
- Category: `pump-hydraulics`
- Tool mode: `with-tool`
- Standards: Hydraulic Institute Standards
- Tags: mechanical; pump; power; efficiency; deterministic

## Current Task Shape

Calculates pump hydraulic power from flow, head, and fluid density, then accounts for pump efficiency, motor efficiency, and a sizing factor. The template reports shaft power, motor input power, and recommended motor size as explicit numeric outputs.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_m3_h` | Pump flow rate | float / m3/h | range=0.1..20000.0 |
| `total_dynamic_head_m` | Total dynamic head | float / m | range=0.1..500.0 |
| `fluid_density_kg_m3` | Fluid density | float / kg/m3 | range=500.0..1400.0 |
| `pump_efficiency_pct` | Pump efficiency | float / % | range=1.0..100.0 |
| `motor_efficiency_pct` | Motor efficiency | float / % | range=1.0..100.0 |
| `motor_sizing_factor` | Motor sizing factor | float | range=1.0..2.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `hydraulic_power_kw` | Hydraulic power delivered to the fluid |  | tolerance=0.03 |
| `shaft_power_kw` | Pump shaft power |  | tolerance=0.03 |
| `motor_input_power_kw` | Motor electrical input power |  | tolerance=0.03 |
| `recommended_motor_size_kw` | Recommended motor power after sizing factor |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `water_transfer_pump` | Water transfer pump power sizing | water-transfer-pump; pump-station-duty |
| `process_pump` | Industrial process pump power sizing | process-pump; chemical-transfer-pump |

### Difficulty Notes

```text
easy: all_given | All parameters given for a water transfer pump
medium: all_given | All parameters given across pump power settings
hard: all_given | All parameters given for process pump motor sizing
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
