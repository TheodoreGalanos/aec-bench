# ABOUTME: First-pass task-world opportunity card for chemical-dosing.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / fundamental-calculations / chemical-dosing

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/chemical_dosing`
- Discipline: `mechanical`
- Category: `fundamental-calculations`
- Tool mode: `with-tool`
- Standards: WEF MOP 8
- Tags: mechanical; water-treatment; chemical-dosing; feed-rate; deterministic

## Current Task Shape

Calculates treatment chemical feed requirements from process flow, target active dose, product strength, and product density. The template reports active chemical mass, commercial product mass, volumetric feed rate, and annual product consumption for water and wastewater dosing checks.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_m3_d` | Process flow rate | float / m3/d | range=10.0..1000000.0 |
| `target_dose_mg_l` | Target active chemical dose | float / mg/L | range=0.1..500.0 |
| `product_strength_pct` | Active chemical strength or purity of commercial product | float / % | range=1.0..100.0 |
| `product_density_kg_l` | Commercial chemical product density | float / kg/L | range=0.7..2.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `active_mass_feed_kg_d` | Active chemical mass feed rate |  | tolerance=0.03 |
| `product_mass_feed_kg_d` | Commercial product mass feed rate |  | tolerance=0.03 |
| `volume_feed_l_d` | Commercial product volume feed rate |  | tolerance=0.03 |
| `annual_product_consumption_t` | Annual commercial product consumption |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `disinfection_dose` | Low-dose liquid chemical disinfection application | water-treatment-disinfection; recycled-water-plant |
| `coagulant_dose` | Coagulant or alkalinity chemical dosing application | surface-water-treatment-plant; industrial-pretreatment |

### Difficulty Notes

```text
easy: all_given | All parameters given for low-dose disinfection
medium: all_given | All parameters given across disinfection and coagulant dosing
hard: all_given | All parameters given for higher mass chemical feed rates
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
