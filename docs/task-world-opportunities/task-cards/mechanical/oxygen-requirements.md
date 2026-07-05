# ABOUTME: First-pass task-world opportunity card for oxygen-requirements.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / activated-sludge / oxygen-requirements

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/oxygen_requirements`
- Discipline: `mechanical`
- Category: `activated-sludge`
- Tool mode: `with-tool`
- Standards: WEF MOP 8
- Tags: mechanical; wastewater; activated-sludge; oxygen-demand; deterministic

## Current Task Shape

Calculates activated sludge oxygen demand from BOD removal, nitrogen oxidation, sludge production, and denitrification credit. The template uses explicit stoichiometric factors for carbonaceous demand adjustment, nitrification oxygen demand, and denitrification oxygen recovery.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_m3_d` | Process flow rate | float / m3/d | range=10.0..1000000.0 |
| `influent_bod_mg_l` | Influent BOD concentration | float / mg/L | range=10.0..1000.0 |
| `effluent_bod_mg_l` | Effluent BOD concentration | float / mg/L | range=0.0..100.0 |
| `influent_tkn_mg_l` | Influent TKN concentration | float / mg/L | range=1.0..150.0 |
| `effluent_tkn_mg_l` | Effluent TKN concentration | float / mg/L | range=0.0..50.0 |
| `sludge_production_kg_d` | Biomass sludge production | float / kg/d | range=0.0..100000.0 |
| `denitrified_nitrogen_mg_l` | Nitrate-nitrogen denitrified for oxygen credit | float / mg/L | range=0.0..100.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `bod_removed_kg_d` | BOD removed |  | tolerance=0.03 |
| `carbonaceous_oxygen_kg_d` | Carbonaceous oxygen demand after sludge credit |  | tolerance=0.03 |
| `nitrogenous_oxygen_kg_d` | Nitrogenous oxygen demand |  | tolerance=0.03 |
| `denitrification_credit_kg_d` | Denitrification oxygen credit |  | tolerance=0.03 |
| `total_oxygen_kg_d` | Total oxygen demand |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `package_plant` | Package activated sludge plant | remote-community-wwtp; industrial-package-wwtp |
| `municipal_nutrient_removal` | Municipal nutrient removal activated sludge plant | regional-wwtp; urban-nutrient-removal-plant |

### Difficulty Notes

```text
easy: all_given | All parameters given for a package activated sludge plant
medium: all_given | All parameters given across package and municipal plants
hard: all_given | All parameters given for nutrient removal oxygen demand
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
