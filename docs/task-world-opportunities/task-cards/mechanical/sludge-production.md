# ABOUTME: First-pass task-world opportunity card for sludge-production.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / activated-sludge / sludge-production

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/sludge_production`
- Discipline: `mechanical`
- Category: `activated-sludge`
- Tool mode: `with-tool`
- Standards: WEF MOP 8
- Tags: mechanical; wastewater; activated-sludge; sludge-production; deterministic

## Current Task Shape

Estimates activated sludge production from BOD removal, observed biological yield, solids decay, primary TSS capture, and VSS-to-TSS conversion. The template reports BOD removed, observed yield, biomass VSS production, primary solids, and total sludge production.

## Existing Deterministic Contract

- Parameters: `9`
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
| `influent_tss_mg_l` | Influent TSS concentration | float / mg/L | range=0.0..1000.0 |
| `primary_tss_removal_pct` | Primary treatment TSS removal | float / % | range=0.0..80.0 |
| `yield_coefficient` | Biomass yield coefficient | float | range=0.1..0.9 |
| `decay_coefficient_d_inv` | Endogenous decay coefficient | float / 1/d | range=0.0..0.2 |
| `srt_days` | Solids retention time | float / d | range=1.0..60.0 |
| `vss_to_tss_ratio` | Biomass VSS to TSS ratio | float | range=0.5..0.9 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `bod_removed_kg_d` | BOD removed |  | tolerance=0.03 |
| `observed_yield_vss_per_bod` | Observed biomass yield |  | tolerance=0.03 |
| `biomass_production_kg_vss_d` | Biomass production as VSS |  | tolerance=0.03 |
| `primary_solids_kg_tss_d` | Primary solids captured |  | tolerance=0.03 |
| `total_sludge_kg_tss_d` | Total sludge production as TSS |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `package_plant` | Package activated sludge plant | remote-community-wwtp; industrial-package-wwtp |
| `municipal_plant` | Municipal activated sludge plant | regional-wwtp; urban-nutrient-removal-plant |

### Difficulty Notes

```text
easy: all_given | All parameters given for package plant sludge production
medium: all_given | All parameters given across package and municipal plants
hard: all_given | All parameters given for municipal sludge production
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
