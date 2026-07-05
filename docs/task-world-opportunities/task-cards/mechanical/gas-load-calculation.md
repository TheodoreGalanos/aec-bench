# ABOUTME: First-pass task-world opportunity card for gas-load-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / gas-services / gas-load-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/gas_load_calculation`
- Discipline: `mechanical`
- Category: `gas-services`
- Tool mode: `with-tool`
- Standards: AS/NZS 5601.1
- Tags: mechanical; gas-services; load; demand; deterministic

## Current Task Shape

Calculates connected and diversified gas demand from explicit appliance gas loads, quantities, and diversity factor. The template reports demand in MJ/h and kW.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `appliance_1_load_mj_h` | Gas load for first appliance group | float / MJ/h | range=0.0..10000.0 |
| `appliance_1_quantity` | Quantity of first appliance group | float / - | range=0.0..1000.0 |
| `appliance_2_load_mj_h` | Gas load for second appliance group | float / MJ/h | range=0.0..10000.0 |
| `appliance_2_quantity` | Quantity of second appliance group | float / - | range=0.0..1000.0 |
| `appliance_3_load_mj_h` | Gas load for third appliance group | float / MJ/h | range=0.0..10000.0 |
| `appliance_3_quantity` | Quantity of third appliance group | float / - | range=0.0..1000.0 |
| `diversity_factor` | Demand diversity factor | float / - | range=0.01..1.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `connected_load_mj_h` | Total connected gas load |  | tolerance=0.03 |
| `diversified_load_mj_h` | Diversified gas load |  | tolerance=0.03 |
| `connected_load_kw` | Connected gas load in kilowatts |  | tolerance=0.03 |
| `diversified_load_kw` | Diversified gas load in kilowatts |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `commercial_kitchen` | Commercial kitchen appliance gas load | commercial-kitchen; food-service |
| `plant_room` | Plant room gas-fired equipment load | boiler-room; gas-plant |

### Difficulty Notes

```text
easy: all_given | All parameters given for a commercial kitchen
medium: all_given | All parameters given across gas services settings
hard: all_given | All parameters given for plant room gas loads
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

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_table`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
