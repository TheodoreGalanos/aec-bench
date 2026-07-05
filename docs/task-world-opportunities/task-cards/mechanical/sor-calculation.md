# ABOUTME: First-pass task-world opportunity card for sor-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / clarifier-design / sor-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/sor_calculation`
- Discipline: `mechanical`
- Category: `clarifier-design`
- Tool mode: `with-tool`
- Standards: Ten States Standards; WEF MOP 8
- Tags: mechanical; wastewater; clarifier; surface-overflow-rate; deterministic

## Current Task Shape

Calculates clarifier surface overflow rate from flow and plan area, then compares the result with an explicit maximum design criterion. The template reports hydraulic loading, utilisation, margin, and a numeric criterion flag.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_m3_d` | Flow rate to the clarifier | float / m3/d | range=1.0..1000000.0 |
| `clarifier_surface_area_m2` | Clarifier plan surface area | float / m2 | range=1.0..100000.0 |
| `maximum_sor_m3_m2_d` | Maximum allowable surface overflow rate criterion | float / m3/m2.d | range=1.0..100.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `surface_overflow_rate_m3_m2_d` | Calculated surface overflow rate |  | tolerance=0.03 |
| `utilisation_ratio` | Ratio of calculated SOR to maximum criterion |  | tolerance=0.03 |
| `compliance_margin_m3_m2_d` | Positive margin below the maximum criterion |  | tolerance=0.03 |
| `criterion_satisfied` | Numeric flag where 1 means the criterion is satisfied |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `secondary_clarifier` | Secondary clarifier hydraulic loading check | municipal-wwtp; secondary-clarifier |
| `water_treatment_clarifier` | Water treatment clarifier hydraulic loading check | water-treatment-plant; solids-contact-clarifier |

### Difficulty Notes

```text
easy: all_given | All parameters given for a secondary clarifier
medium: all_given | All parameters given across wastewater and water clarifiers
hard: all_given | All parameters given for larger water treatment clarifiers
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
