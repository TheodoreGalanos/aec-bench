# ABOUTME: First-pass task-world opportunity card for car-dimensions-check.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / shaft-sizing / car-dimensions-check

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/car_dimensions_check`
- Discipline: `electrical`
- Category: `shaft-sizing`
- Tool mode: `with-tool`
- Standards: ISO 4190-1; AS 1735.12; EN 81-70
- Tags: electrical; vertical-transportation; lift; accessibility; dimensions; deterministic

## Current Task Shape

Calculates numeric margins for lift car internal width, internal depth, and clear door opening against explicit minimum requirements. The template also reports car floor area and rated load density for reduced vertical transportation checks.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `minimum_door_opening_mm`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `car_internal_width_mm` | Lift car internal width | float / mm | range=600..3000 |
| `car_internal_depth_mm` | Lift car internal depth | float / mm | range=800..4000 |
| `door_clear_opening_mm` | Clear door opening width | float / mm | range=500..2000 |
| `rated_load_kg` | Lift rated load | float / kg | range=100..5000 |
| `minimum_width_mm` | Required minimum car width | float / mm | range=500..2500 |
| `minimum_depth_mm` | Required minimum car depth | float / mm | range=500..3500 |
| `minimum_door_opening_mm` | Required minimum clear door opening | float / mm | range=500..1800 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `width_margin_mm` | Actual car width minus minimum width |  | tolerance=0.03 |
| `depth_margin_mm` | Actual car depth minus minimum depth |  | tolerance=0.03 |
| `door_opening_margin_mm` | Actual door opening minus minimum door opening |  | tolerance=0.03 |
| `car_floor_area_m2` | Car floor area |  | tolerance=0.03 |
| `rated_load_density_kg_m2` | Rated load divided by car floor area |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `accessible_passenger_lift` | Accessible passenger lift car | passenger-lift; accessibility |
| `goods_lift_car` | Goods lift car | goods-lift; car-sizing |

### Difficulty Notes

```text
easy: all_given | Accessible passenger lift with all values visible
medium: all_given | Lift car selected from passenger or goods cases
hard: partial | hidden=minimum_door_opening_mm | Goods lift car with minimum door opening embedded in context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `time-series`.

Use single-line diagrams, layouts, device schedules, demand profiles, and equipment datasheets.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`, `source_timeseries`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
