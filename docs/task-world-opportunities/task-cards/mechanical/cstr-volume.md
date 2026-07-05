# ABOUTME: First-pass task-world opportunity card for cstr-volume.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / reactor-sizing / cstr-volume

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/cstr_volume`
- Discipline: `mechanical`
- Category: `reactor-sizing`
- Tool mode: `with-tool`
- Standards: Chemical Reaction Engineering Fundamentals
- Tags: mechanical; reactor-sizing; cstr; first-order; deterministic

## Current Task Shape

Calculates required CSTR volume for an isothermal constant-density first-order reaction. The template uses the CSTR design relationship tau = X/(k(1-X)) and V = Q tau, while reporting outlet concentration and outlet reaction rate.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `volumetric_flow_m3_h` | Volumetric feed flow rate | float / m3/h | range=0.1..5000.0 |
| `inlet_concentration_kmol_m3` | Inlet concentration of limiting reactant | float / kmol/m3 | range=0.01..20.0 |
| `required_conversion_pct` | Required reactant conversion | float / % | range=5.0..95.0 |
| `rate_constant_h_inv` | First-order reaction rate constant | float / 1/h | range=0.01..10.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `outlet_concentration_kmol_m3` | Outlet concentration at required conversion |  | tolerance=0.03 |
| `outlet_reaction_rate_kmol_m3_h` | First-order reaction rate at CSTR outlet |  | tolerance=0.03 |
| `space_time_h` | Required reactor space time |  | tolerance=0.03 |
| `required_volume_m3` | Required CSTR volume |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_process_reactor` | Small liquid-phase process CSTR | pilot-process-skid; batch-to-continuous-conversion |
| `large_treatment_reactor` | Large first-order stirred treatment reactor | industrial-wastewater-reactor; process-neutralisation-train |

### Difficulty Notes

```text
easy: all_given | All parameters given for a small process CSTR
medium: all_given | All parameters given across small and large first-order CSTRs
hard: all_given | All parameters given for larger stirred treatment reactor sizing
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
