# ABOUTME: First-pass task-world opportunity card for srt-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / fundamental-calculations / srt-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/srt_calculation`
- Discipline: `mechanical`
- Category: `fundamental-calculations`
- Tool mode: `with-tool`
- Standards: WEF MOP 8; Ten States Standards
- Tags: mechanical; wastewater; activated-sludge; srt; deterministic

## Current Task Shape

Calculates solids retention time for an activated sludge process from aeration basin solids inventory and daily solids losses through waste activated sludge and effluent TSS. The template reports system solids, wasted solids, effluent solids loss, total loss, and SRT.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `aeration_volume_m3` | Aeration tank volume | float / m3 | range=10.0..200000.0 |
| `mlss_concentration_mg_l` | Mixed liquor suspended solids concentration | float / mg/L | range=500.0..8000.0 |
| `was_flow_m3_d` | Waste activated sludge flow rate | float / m3/d | range=1.0..50000.0 |
| `was_tss_mg_l` | Waste activated sludge TSS concentration | float / mg/L | range=1000.0..20000.0 |
| `effluent_tss_mg_l` | Effluent TSS concentration | float / mg/L | range=0.0..100.0 |
| `effluent_flow_m3_d` | Effluent flow rate | float / m3/d | range=1.0..1000000.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `solids_in_system_kg` | Mass of solids in aeration system |  | tolerance=0.03 |
| `solids_wasted_kg_d` | Mass of solids wasted per day |  | tolerance=0.03 |
| `effluent_solids_loss_kg_d` | Mass of solids lost in effluent per day |  | tolerance=0.03 |
| `total_solids_loss_kg_d` | Total daily solids loss |  | tolerance=0.03 |
| `srt_days` | Solids retention time |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `package_activated_sludge` | Package activated sludge plant | remote-community-wwtp; industrial-package-wwtp |
| `municipal_activated_sludge` | Municipal activated sludge process | regional-wwtp; urban-nutrient-removal-plant |

### Difficulty Notes

```text
easy: all_given | All parameters given for a package activated sludge plant
medium: all_given | All parameters given across package and municipal activated sludge systems
hard: all_given | All parameters given for municipal activated sludge SRT checks
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
