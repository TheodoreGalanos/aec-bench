# ABOUTME: First-pass task-world opportunity card for road-aeci-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / energy-performance / road-aeci-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/road_aeci_calculation`
- Discipline: `electrical`
- Category: `energy-performance`
- Tool mode: `with-tool`
- Standards: EN 13201-5; AS/NZS 1158.3.1
- Tags: electrical; lighting; road-lighting; aeci; energy; deterministic

## Current Task Shape

Calculates annual road lighting energy consumption and Annual Energy Consumption Index from system power, full-output hours, dimmed hours, dimming level, and illuminated area.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `2`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `dimmed_hours_per_year`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `system_power_w` | Total road lighting system power at full output | float / W | range=100..200000 |
| `full_output_hours_per_year` | Annual hours at full lighting output | float / h/year | range=0..8760 |
| `dimmed_hours_per_year` | Annual hours at dimmed lighting output | float / h/year | range=0..8760 |
| `dimming_level_pct` | Dimmed output level relative to full power | float / % | range=0..100 |
| `illuminated_area_m2` | Illuminated road or pathway area | float / m2 | range=100..100000 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `annual_energy_kwh` | Annual lighting energy consumption |  | tolerance=0.03 |
| `aeci_kwh_per_m2_year` | Annual Energy Consumption Index |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `local_road_night_dimming` | Local road with overnight dimming | local-road; night-dimming |
| `arterial_road_night_dimming` | Arterial road with adaptive lighting control | arterial-road; adaptive-lighting |

### Difficulty Notes

```text
easy: all_given | Local road with all values visible
medium: all_given | Road lighting dimming scenario
hard: partial | hidden=dimmed_hours_per_year | Arterial road with dimmed hours embedded in context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `spatial-map`, `tabular-source`.

Use alignment drawings, chainage tables, long sections, route maps, and design-speed schedules.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Alignment geometry can feed sight-distance, cant/superelevation, vertical-curve, and comfort checks.

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
