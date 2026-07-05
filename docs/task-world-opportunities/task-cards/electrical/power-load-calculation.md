# ABOUTME: First-pass task-world opportunity card for power-load-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / power-supply / power-load-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/power_load_calculation`
- Discipline: `electrical`
- Category: `power-supply`
- Tool mode: `with-tool`
- Standards: EN 50125; AS 7717
- Tags: electrical; signalling; power-load; supply-sizing; deterministic

## Current Task Shape

Calculates total connected load for a repeated signalling equipment item, applies a diversity factor and future expansion allowance, then converts the resulting demand to recommended supply kVA using the supply power factor.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `future_expansion_pct`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `equipment_power_w` | Power rating per equipment item | float / W | range=1..5000 |
| `equipment_quantity` | Number of equipment items | float | range=1..500 |
| `diversity_factor` | Demand diversity factor | float | range=0.1..1.0 |
| `future_expansion_pct` | Future expansion allowance | float / % | range=0..100 |
| `supply_power_factor` | Assumed supply power factor | float | range=0.5..1.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `total_connected_load_w` | Total connected load |  | tolerance=0.03 |
| `maximum_demand_w` | Maximum demand after diversity |  | tolerance=0.03 |
| `future_allowance_w` | Future expansion allowance |  | tolerance=0.03 |
| `recommended_supply_size_kva` | Recommended apparent supply size |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `signalling_cabinet` | Small signalling cabinet equipment load | rail-signal-location; roadside-controller |
| `equipment_room` | Equipment room or larger signalling supply | station-equipment-room; interlocking-room |

### Difficulty Notes

```text
easy: all_given | Small cabinet with all inputs visible
medium: all_given | Cabinet or room supply sizing
hard: partial | hidden=future_expansion_pct | Future allowance hidden in expansion context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use building elevations, terrain/zone diagrams, load schedules, and standards extracts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Wind-speed and pressure derivations can feed structural member, bracket, cladding, and foundation checks.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
