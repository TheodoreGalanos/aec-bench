# ABOUTME: First-pass task-world opportunity card for road-pdi-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / energy-performance / road-pdi-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/road_pdi_calculation`
- Discipline: `electrical`
- Category: `energy-performance`
- Tool mode: `with-tool`
- Standards: EN 13201-5; AS/NZS 1158.3.1
- Tags: electrical; lighting; road-lighting; pdi; energy; deterministic

## Current Task Shape

Calculates Power Density Index and specific power density for a road lighting installation from total system power, maintained illuminance, and illuminated area.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `2`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `illuminated_area_m2`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `total_system_power_w` | Total installed road lighting system power | float / W | range=100..200000 |
| `maintained_illuminance_lux` | Maintained average illuminance over the lit area | float / lux | range=1..50 |
| `illuminated_area_m2` | Illuminated road or pathway area | float / m2 | range=100..100000 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `power_density_index_w_per_lux_m2` | Power Density Index in watts per lux per square metre |  | tolerance=0.03 |
| `specific_power_density_w_per_m2` | Installed power divided by illuminated area |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `local_road` | Local road lighting section | local-road; pedestrian-route |
| `arterial_road` | Arterial road lighting section | arterial-road; transport-corridor |

### Difficulty Notes

```text
easy: all_given | Local road with all values visible
medium: all_given | Road lighting section selected from local or arterial cases
hard: partial | hidden=illuminated_area_m2 | Arterial road with illuminated area embedded in context
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
