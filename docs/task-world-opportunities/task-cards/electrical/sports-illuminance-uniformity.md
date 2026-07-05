# ABOUTME: First-pass task-world opportunity card for sports-illuminance-uniformity.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / sports-lighting / sports-illuminance-uniformity

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/sports_illuminance_uniformity`
- Discipline: `electrical`
- Category: `sports-lighting`
- Tool mode: `with-tool`
- Standards: EN 12193; AS 2560
- Tags: electrical; lighting; sports-lighting; illuminance; uniformity; deterministic

## Current Task Shape

Calculates reduced sports lighting performance using aggregate luminaire flux, utilisation factor, maintenance factor, and grid extrema. The template reports average horizontal illuminance, U1 and U2 uniformity ratios, and margins against target lighting class values.

## Existing Deterministic Contract

- Parameters: `10`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `target_uniformity_u2`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `field_length_m` | Sports field length | float / m | range=10..200 |
| `field_width_m` | Sports field width | float / m | range=10..120 |
| `luminaire_count` | Number of luminaires | float / count | range=4..300 |
| `luminaire_luminous_flux_lm` | Luminous flux per luminaire | float / lm | range=10000..250000 |
| `utilisation_factor` | Field utilisation factor | float / - | range=0.2..0.8 |
| `maintenance_factor` | Lighting maintenance factor | float / - | range=0.5..0.95 |
| `minimum_illuminance_lux` | Minimum grid illuminance | float / lux | range=0..2000 |
| `maximum_illuminance_lux` | Maximum grid illuminance | float / lux | range=1..5000 |
| `target_average_illuminance_lux` | Target average horizontal illuminance | float / lux | range=50..2000 |
| `target_uniformity_u2` | Target U2 uniformity ratio | float / - | range=0.1..0.9 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `average_horizontal_illuminance_lux` | Average horizontal illuminance |  | tolerance=0.03 |
| `uniformity_u1_min_max` | U1 uniformity ratio, minimum divided by maximum |  | tolerance=0.03 |
| `uniformity_u2_min_avg` | U2 uniformity ratio, minimum divided by average |  | tolerance=0.03 |
| `average_illuminance_margin_pct` | Average illuminance margin against target |  | tolerance=0.03 |
| `uniformity_u2_margin_pct` | U2 uniformity margin against target |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `community_field` | Community sports field lighting | community-sport; field-lighting |
| `stadium_field` | Stadium field lighting | stadium; field-lighting |

### Difficulty Notes

```text
easy: all_given | Community sports field with all values visible
medium: all_given | Sports lighting case selected from community or stadium fields
hard: partial | hidden=target_uniformity_u2 | Stadium field with target U2 embedded in context
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
