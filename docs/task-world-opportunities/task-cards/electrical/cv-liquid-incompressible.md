# ABOUTME: First-pass task-world opportunity card for cv-liquid-incompressible.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / control-valve-sizing / cv-liquid-incompressible

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/cv_liquid_incompressible`
- Discipline: `electrical`
- Category: `control-valve-sizing`
- Tool mode: `with-tool`
- Standards: ISA-75.01.01; IEC 60534-2-1
- Tags: electrical; instrumentation; control-valve; cv-sizing; liquid-flow

## Current Task Shape

Sizes control valves for incompressible liquid service by computing the required flow coefficient Cv from the ISA-75.01.01 equation Kv = Q * sqrt(SG / deltaP_eff), with Cv = 1.156 * Kv. Checks for choked (cavitating) flow using the liquid pressure recovery factor FL and critical pressure ratio factor FF, essential for process control and piping system design.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `fl_recovery_factor`, `fluid_critical_pressure_bar`, `fluid_specific_gravity`, `fluid_vapor_pressure_bar`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_m3_h` | Volumetric flow rate through the valve | float / m³/h | range=0.5..500 |
| `upstream_pressure_bar` | Upstream pressure (P1) at valve inlet | float / bar | range=1..100 |
| `downstream_pressure_bar` | Downstream pressure (P2) at valve outlet | float / bar | range=0.5..99 |
| `fluid_specific_gravity` | Fluid specific gravity relative to water at 15°C | float | range=0.5..2.0; derivable_from=archetype |
| `fluid_vapor_pressure_bar` | Fluid vapor pressure at operating temperature | float / bar | range=0.01..50; derivable_from=archetype |
| `fluid_critical_pressure_bar` | Fluid thermodynamic critical pressure | float / bar | range=10..250; derivable_from=archetype |
| `fl_recovery_factor` | Liquid pressure recovery factor FL of the valve | float | range=0.5..1.0; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pressure_drop_bar` | Actual pressure drop across the valve (bar) |  | tolerance=0.03 |
| `cv_required` | Required valve flow coefficient Cv |  | tolerance=0.03 |
| `choked_pressure_drop_bar` | Choked (limiting) pressure drop (bar) |  | tolerance=0.03 |
| `is_choked` | Choked flow indicator (1.0 = choked, 0.0 = not choked) |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `water_utility` | Water utility service — clean water, low pressure | municipal-water-treatment; pumping-station-transfer |
| `petrochemical_light` | Petrochemical light hydrocarbon liquid service | refinery-distillation-unit; petrochemical-transfer-line |
| `chemical_process` | Chemical process — moderate-density process liquid | chemical-plant-reactor-feed; solvent-blending-unit |
| `high_pressure_oil` | High-pressure oil or heavy hydrocarbon service | offshore-production-platform; crude-oil-pipeline-terminal |

### Difficulty Notes

```text
easy: all_given | Water service, moderate pressures, all parameters given, non-choked conditions
medium: all_given | Any fluid type and pressure range, all parameters given
hard: partial | hidden=fluid_specific_gravity, fluid_vapor_pressure_bar, fluid_critical_pressure_bar, fl_recovery_factor | Fluid properties and valve FL hidden, agent must infer from process context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `time-series`.

Use single-line diagrams, layouts, device schedules, demand profiles, and equipment datasheets.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

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
