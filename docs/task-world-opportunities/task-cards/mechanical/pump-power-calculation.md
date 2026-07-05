# ABOUTME: First-pass task-world opportunity card for pump-power-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / pump-sizing / pump-power-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/pump_power_calculation`
- Discipline: `mechanical`
- Category: `pump-sizing`
- Tool mode: `with-tool`
- Standards: HI 14.6; ISO 9906
- Tags: mechanical; pump; power; hydraulics; deterministic

## Current Task Shape

Calculates pump hydraulic power and shaft power from flow rate, total dynamic head, fluid density, and pump efficiency. The template reports converted flow, hydraulic power, shaft power, and efficiency fraction.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_l_s` | Pump flow rate | float / L/s | range=0.1..5000.0 |
| `total_dynamic_head_m` | Total dynamic head | float / m | range=0.1..500.0 |
| `fluid_density_kg_m3` | Fluid density | float / kg/m3 | range=500.0..1400.0 |
| `pump_efficiency_pct` | Pump efficiency | float / % | range=1.0..100.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_m3_s` | Flow rate in cubic metres per second |  | tolerance=0.03 |
| `hydraulic_power_kw` | Hydraulic power |  | tolerance=0.03 |
| `shaft_power_kw` | Required shaft power |  | tolerance=0.03 |
| `efficiency_fraction` | Pump efficiency as a fraction |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `water_pump` | Water pump power calculation | water-pump-station; transfer-pump |
| `process_pump` | Industrial process pump power calculation | process-plant; dosing-pump |

### Difficulty Notes

```text
easy: all_given | All parameters given for a water pump
medium: all_given | All parameters given across pump types
hard: all_given | All parameters given for process pumps
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
