# ABOUTME: First-pass task-world opportunity card for lmtd-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / heat-exchanger-design / lmtd-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/lmtd_calculation`
- Discipline: `mechanical`
- Category: `heat-exchanger-design`
- Tool mode: `with-tool`
- Standards: TEMA Standards
- Tags: mechanical; heat-exchanger; lmtd; heat-duty; deterministic

## Current Task Shape

Calculates heat exchanger LMTD from hot and cold terminal temperatures for counterflow or parallel flow arrangements. The template applies an explicit correction factor, calculates corrected mean temperature difference, and estimates heat duty from U, area, and corrected MTD.

## Existing Deterministic Contract

- Parameters: `8`
- Outputs: `6`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `hot_inlet_c` | Hot fluid inlet temperature | float / C | range=30.0..400.0 |
| `hot_outlet_c` | Hot fluid outlet temperature | float / C | range=20.0..350.0 |
| `cold_inlet_c` | Cold fluid inlet temperature | float / C | range=-10.0..200.0 |
| `cold_outlet_c` | Cold fluid outlet temperature | float / C | range=0.0..250.0 |
| `overall_u_kw_m2_c` | Overall heat transfer coefficient | float / kW/m2.C | range=0.02..5.0 |
| `heat_transfer_area_m2` | Heat transfer surface area | float / m2 | range=1.0..10000.0 |
| `correction_factor` | LMTD correction factor | float | range=0.5..1.0 |
| `flow_arrangement` | Heat exchanger flow arrangement | enum | values=counterflow, parallel |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `delta_t1_c` | First terminal temperature difference |  | tolerance=0.03 |
| `delta_t2_c` | Second terminal temperature difference |  | tolerance=0.03 |
| `lmtd_c` | Log mean temperature difference |  | tolerance=0.03 |
| `corrected_mtd_c` | Corrected mean temperature difference |  | tolerance=0.03 |
| `heat_duty_kw` | Estimated heat duty |  | tolerance=0.03 |
| `minimum_approach_c` | Minimum terminal temperature approach |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `process_cooler` | Process liquid cooler with counterflow exchanger | industrial-process-cooler; plant-utility-exchanger |
| `hot_water_heat_exchanger` | Hot water heat exchanger for building or process service | district-heating-skid; building-services-heat-exchanger |

### Difficulty Notes

```text
easy: all_given | All parameters given for a counterflow process cooler
medium: all_given | All parameters given across common heat exchanger duties
hard: all_given | All parameters given with explicit correction factor and arrangement
```

## Multimodal Expansion

Candidate modality families: `chart-curve`, `drawing-geometry`, `tabular-source`.

Use schematics, equipment curves, schedules, commissioning tables, and source datasheets.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

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
