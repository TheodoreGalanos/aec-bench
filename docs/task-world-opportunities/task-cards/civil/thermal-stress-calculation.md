# ABOUTME: First-pass task-world opportunity card for thermal-stress-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / rail-stress / thermal-stress-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/thermal_stress_calculation`
- Discipline: `civil`
- Category: `rail-stress`
- Tool mode: `with-tool`
- Standards: AREMA MRE Chapter 5; UIC 720 R; ARTC ETS-05-00
- Tags: civil; rail; CWR; thermal-stress; longitudinal-force; track; deterministic

## Current Task Shape

Computes the longitudinal thermal stress and force in continuously welded rail (CWR) using sigma = E * alpha * delta_T. Critical for managing rail buckling risk in hot conditions and rail pull-apart risk in cold conditions, per AREMA Chapter 5 and ARTC ETS-05-00.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `3`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `elastic_modulus_mpa`, `thermal_expansion_coeff_micro_per_c`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `rail_area_mm2` | Rail cross-sectional area A | float / mm² | range=4000..9000 |
| `thermal_expansion_coeff_micro_per_c` | Coefficient of linear thermal expansion α | float / ×10⁻⁶ per °C | range=1.0..15.0; derivable_from=archetype |
| `elastic_modulus_mpa` | Modulus of elasticity E of rail steel | float / MPa | range=195000..215000; derivable_from=archetype |
| `temperature_change_c` | Temperature change from neutral temperature ΔT = T_rail − T_neutral | float / °C | range=-50..50 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `thermal_stress_mpa` | Thermal stress magnitude σ (MPa) |  | tolerance=0.03 |
| `thermal_force_kn` | Thermal force magnitude F (kN) |  | tolerance=0.03 |
| `stress_state` | Stress state: 1.0 = compression, -1.0 = tension, 0.0 = neutral |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `hot_inland` | Hot inland corridor with large positive temperature rise above neutral | artc-broken-hill-corridor; alice-springs-adelaide-rail; pilbara-port-hedland-wa |
| `cold_alpine` | Cold alpine or highland corridor with large negative temperature drop below neutral | nsw-blue-mountains-line; vic-alpine-northeast; tas-western-explorer |
| `coastal_temperate` | Coastal temperate corridor with moderate temperature variation | sydney-illawarra-line; melbourne-geelong-corridor; perth-fremantle-coastal |
| `tropical_north` | Tropical northern corridor with sustained high temperatures above neutral | cairns-townsville-north-coast; darwin-adelaide-ghan-corridor; mt-isa-rail-qld |

### Difficulty Notes

```text
easy: all_given | All parameters given, moderate temperature changes on mainline corridors
medium: all_given | All parameters given, any corridor type including extreme inland and alpine conditions
hard: partial | hidden=thermal_expansion_coeff_micro_per_c, elastic_modulus_mpa | Material properties hidden — agent must infer E and α for standard rail steel from engineering knowledge
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `spatial-map`, `tabular-source`.

Use alignment drawings, chainage tables, long sections, route maps, and design-speed schedules.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Alignment geometry can feed sight-distance, cant/superelevation, vertical-curve, and comfort checks.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
