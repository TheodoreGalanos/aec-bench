# ABOUTME: First-pass task-world opportunity card for lux-level-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / lighting-design / lux-level-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/lux_level_calculation`
- Discipline: `electrical`
- Category: `lighting-design`
- Tool mode: `with-tool`
- Standards: AS/NZS 1680.1; AS/NZS 1680.2.2
- Tags: electrical; lighting; lumen-method; illuminance; deterministic

## Current Task Shape

Calculates reduced room lighting performance using the lumen method. The template uses room area, luminaire count, luminous flux, utilisation factor, maintenance factor, total lighting power, and target illuminance to report average illuminance, uniformity, power density, and target margin.

## Existing Deterministic Contract

- Parameters: `9`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `utilisation_factor`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `room_length_m` | Room length | float / m | range=2..100 |
| `room_width_m` | Room width | float / m | range=2..80 |
| `luminaire_count` | Number of luminaires | float / count | range=1..500 |
| `luminaire_luminous_flux_lm` | Luminous flux per luminaire | float / lm | range=500..80000 |
| `utilisation_factor` | Utilisation factor | float / - | range=0.2..0.9 |
| `maintenance_factor` | Maintenance factor | float / - | range=0.5..0.95 |
| `total_lighting_power_w` | Total installed lighting power | float / W | range=20..100000 |
| `minimum_illuminance_lux` | Minimum calculated illuminance | float / lux | range=0..2000 |
| `target_illuminance_lux` | Target average illuminance | float / lux | range=50..2000 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `average_illuminance_lux` | Average maintained illuminance |  | tolerance=0.03 |
| `uniformity_ratio_uo` | Minimum to average illuminance uniformity ratio |  | tolerance=0.03 |
| `specific_luminaire_power_density_w_m2_100lux` | Lighting power density normalised to 100 lux |  | tolerance=0.03 |
| `target_illuminance_margin_pct` | Percentage margin against target illuminance |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `office_room` | Office room lighting layout | office-lighting; lumen-method |
| `warehouse_room` | Warehouse lighting layout | warehouse-lighting; lumen-method |

### Difficulty Notes

```text
easy: all_given | Office room with all values visible
medium: all_given | Room lighting case selected from office or warehouse layouts
hard: partial | hidden=utilisation_factor | Warehouse lighting case with utilisation factor embedded in context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `spatial-map`.

Use layout plans, device schedules, coverage diagrams, timing tables, and network topology artifacts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Communications and ITS tasks combine through shared layouts, device counts, coverage, storage, and power constraints.

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
