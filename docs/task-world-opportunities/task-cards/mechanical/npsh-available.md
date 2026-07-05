# ABOUTME: First-pass task-world opportunity card for npsh-available.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / pump-hydraulics / npsh-available

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/npsh_available`
- Discipline: `mechanical`
- Category: `pump-hydraulics`
- Tool mode: `with-tool`
- Standards: Hydraulic Institute Standards
- Tags: mechanical; pump-hydraulics; npsh; cavitation; deterministic

## Current Task Shape

Calculates NPSH available from suction vessel absolute pressure, liquid level relative to the pump, suction pipe losses, fluid vapor pressure, and density. The template converts pressure terms to metres of fluid head and compares NPSHa with explicit NPSH required to report cavitation margin.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `6`
- Archetypes: `3`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `suction_vessel_pressure_kpa_abs` | Absolute pressure at the suction vessel free surface | float / kPa abs | range=30.0..800.0 |
| `liquid_level_above_pump_m` | Static liquid level above the pump centreline | float / m | range=-6.0..20.0 |
| `suction_pipe_losses_kpa` | Suction-side friction and minor losses | float / kPa | range=0.0..150.0 |
| `vapor_pressure_kpa_abs` | Fluid vapor pressure at operating temperature | float / kPa abs | range=0.5..100.0 |
| `fluid_density_kg_m3` | Fluid density | float / kg/m3 | range=600.0..1300.0 |
| `npsh_required_m` | Pump manufacturer's NPSH required | float / m | range=0.5..20.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pressure_head_m` | Suction pressure head |  | tolerance=0.03 |
| `vapor_pressure_head_m` | Vapor pressure head |  | tolerance=0.03 |
| `loss_head_m` | Suction loss head |  | tolerance=0.03 |
| `npsh_available_m` | Net Positive Suction Head Available |  | tolerance=0.03 |
| `cavitation_margin_m` | NPSHa minus NPSH required |  | tolerance=0.03 |
| `margin_ratio` | NPSHa divided by NPSH required |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `flooded_water_suction` | Flooded suction water pump with atmospheric vented tank | water-treatment-transfer; building-services-break-tank |
| `hot_process_liquid` | Hot process liquid suction with elevated vapor pressure | industrial-process-skid; thermal-utility-loop |
| `pressurised_suction_vessel` | Pump drawing from a pressurised suction vessel | chemical-transfer-vessel; pressure-booster-skid |

### Difficulty Notes

```text
easy: all_given | All parameters given for flooded water suction
medium: all_given | All parameters given across water and process suction cases
hard: all_given | All parameters given for hot liquid or pressurised suction cases
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
