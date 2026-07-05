# ABOUTME: First-pass task-world opportunity card for biogas-production.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / sludge-handling / biogas-production

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/biogas_production`
- Discipline: `mechanical`
- Category: `sludge-handling`
- Tool mode: `with-tool`
- Standards: WEF MOP 8
- Tags: mechanical; wastewater; sludge; biogas; deterministic

## Current Task Shape

Estimates daily biogas and methane production from volatile solids feed, destruction percentage, biogas yield, and methane fraction. The template reports solids destroyed, biogas volume, methane volume, and methane energy.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `volatile_solids_feed_kg_d` | Daily volatile solids feed to digestion | float / kg/d | range=0.0..1000000.0 |
| `volatile_solids_destruction_pct` | Volatile solids destruction percentage | float / % | range=0.0..100.0 |
| `biogas_yield_m3_kg_vs` | Biogas yield per kilogram of volatile solids destroyed | float / m3/kg VS | range=0.0..5.0 |
| `methane_fraction` | Methane fraction of biogas | float / - | range=0.0..1.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `volatile_solids_destroyed_kg_d` | Volatile solids destroyed |  | tolerance=0.03 |
| `biogas_m3_d` | Daily biogas production |  | tolerance=0.03 |
| `methane_m3_d` | Daily methane production |  | tolerance=0.03 |
| `methane_energy_kwh_d` | Daily methane energy content |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `municipal_digester` | Municipal anaerobic digester biogas estimate | municipal-wwtp; anaerobic-digester |
| `industrial_digester` | Industrial sludge digestion biogas estimate | industrial-wwtp; high-strength-waste |

### Difficulty Notes

```text
easy: all_given | All parameters given for a municipal digester
medium: all_given | All parameters given across digestion settings
hard: all_given | All parameters given for industrial digestion
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
