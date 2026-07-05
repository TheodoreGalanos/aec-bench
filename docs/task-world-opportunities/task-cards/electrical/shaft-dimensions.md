# ABOUTME: First-pass task-world opportunity card for shaft-dimensions.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / shaft-sizing / shaft-dimensions

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/shaft_dimensions`
- Discipline: `electrical`
- Category: `shaft-sizing`
- Tool mode: `with-tool`
- Standards: ISO 4190-1; EN 81-20; AS 1735.1
- Tags: electrical; vertical-transportation; lift; shaft; dimensions; deterministic

## Current Task Shape

Calculates a reduced lift shaft envelope from car dimensions, clearances, counterweight allowance, rated speed, and car count. The template reports shaft width, shaft depth, pit depth, and headroom using explicit clearance formulas for vertical transportation planning.

## Existing Deterministic Contract

- Parameters: `9`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `rear_clearance_mm`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `car_internal_width_mm` | Lift car internal width | float / mm | range=600..3000 |
| `car_internal_depth_mm` | Lift car internal depth | float / mm | range=800..4000 |
| `side_clearance_mm` | Clearance on each side of the car | float / mm | range=50..500 |
| `front_clearance_mm` | Front shaft clearance allowance | float / mm | range=50..800 |
| `rear_clearance_mm` | Rear shaft clearance allowance | float / mm | range=50..800 |
| `counterweight_width_mm` | Counterweight width allowance | float / mm | range=0..800 |
| `rated_speed_m_s` | Lift rated speed | float / m/s | range=0.4..8 |
| `car_count` | Number of cars in the shaft group | float / count | range=1..8 |
| `inter_car_clearance_mm` | Clearance between adjacent cars | float / mm | range=0..800 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `shaft_width_mm` | Required shaft width |  | tolerance=0.03 |
| `shaft_depth_mm` | Required shaft depth |  | tolerance=0.03 |
| `pit_depth_mm` | Reduced pit depth allowance |  | tolerance=0.03 |
| `headroom_mm` | Reduced headroom allowance |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `passenger_lift` | Passenger lift shaft | passenger-lift; shaft-planning |
| `goods_lift` | Goods lift shaft | goods-lift; shaft-planning |

### Difficulty Notes

```text
easy: all_given | Passenger lift with all values visible
medium: all_given | Lift shaft selected from passenger or goods cases
hard: partial | hidden=rear_clearance_mm | Goods lift with rear clearance embedded in context
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
