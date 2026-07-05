# ABOUTME: First-pass task-world opportunity card for miner-fatigue.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / fatigue-analysis / miner-fatigue

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/miner_fatigue`
- Discipline: `mechanical`
- Category: `fatigue-analysis`
- Tool mode: `with-tool`
- Standards: ASME VIII-2; EN 13445
- Tags: mechanical; fatigue; miner; damage; deterministic

## Current Task Shape

Calculates cumulative fatigue damage from three explicit applied-cycle and allowable-cycle bins using Miner's rule. The template reports each damage fraction, cumulative damage, remaining damage margin, and a numeric pass flag.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `6`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `applied_cycles_1` | Applied cycles for first bin | float / cycles | range=0.0..1000000000.0 |
| `allowable_cycles_1` | Allowable cycles for first bin | float / cycles | range=1.0..1000000000000.0 |
| `applied_cycles_2` | Applied cycles for second bin | float / cycles | range=0.0..1000000000.0 |
| `allowable_cycles_2` | Allowable cycles for second bin | float / cycles | range=1.0..1000000000000.0 |
| `applied_cycles_3` | Applied cycles for third bin | float / cycles | range=0.0..1000000000.0 |
| `allowable_cycles_3` | Allowable cycles for third bin | float / cycles | range=1.0..1000000000000.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `damage_bin_1` | Damage fraction for first cycle bin |  | tolerance=0.03 |
| `damage_bin_2` | Damage fraction for second cycle bin |  | tolerance=0.03 |
| `damage_bin_3` | Damage fraction for third cycle bin |  | tolerance=0.03 |
| `cumulative_damage` | Total cumulative fatigue damage |  | tolerance=0.03 |
| `remaining_damage_margin` | Remaining damage margin to cumulative damage of 1 |  | tolerance=0.03 |
| `fatigue_satisfies` | Numeric flag where 1 means cumulative damage is not greater than 1 |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `rotating_equipment` | Rotating equipment duty cycle fatigue check | rotating-equipment; pump-shaft |
| `pressure_equipment` | Pressure equipment fatigue damage check | pressure-vessel; thermal-cycling |

### Difficulty Notes

```text
easy: all_given | All parameters given for rotating equipment
medium: all_given | All parameters given across fatigue checks
hard: all_given | All parameters given for pressure equipment fatigue
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
