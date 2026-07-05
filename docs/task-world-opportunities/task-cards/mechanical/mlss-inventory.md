# ABOUTME: First-pass task-world opportunity card for mlss-inventory.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / fundamental-calculations / mlss-inventory

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/mlss_inventory`
- Discipline: `mechanical`
- Category: `fundamental-calculations`
- Tool mode: `with-tool`
- Standards: WEF MOP 8
- Tags: mechanical; wastewater; activated-sludge; mlss; deterministic

## Current Task Shape

Calculates total mixed liquor suspended solids inventory in an aeration basin from basin volume and MLSS concentration. The template also applies an explicit volatile-solids fraction to estimate MLVSS inventory and inert solids mass for activated sludge process checks.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `aeration_volume_m3` | Aeration basin volume | float / m3 | range=10.0..200000.0 |
| `mlss_concentration_mg_l` | Mixed liquor suspended solids concentration | float / mg/L | range=500.0..8000.0 |
| `mlvss_fraction` | Fraction of MLSS that is volatile suspended solids | float | range=0.4..0.9 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `mlss_inventory_kg` | Total MLSS inventory |  | tolerance=0.03 |
| `mlvss_inventory_kg` | Estimated MLVSS inventory |  | tolerance=0.03 |
| `inert_solids_inventory_kg` | Estimated inert suspended solids inventory |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `package_activated_sludge` | Package activated sludge plant | remote-community-wwtp; industrial-package-wwtp |
| `municipal_aeration_basin` | Municipal activated sludge aeration basin | regional-wwtp; urban-nutrient-removal-plant |

### Difficulty Notes

```text
easy: all_given | All parameters given for a package activated sludge plant
medium: all_given | All parameters given across package and municipal basins
hard: all_given | All parameters given for municipal aeration basin inventory checks
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
