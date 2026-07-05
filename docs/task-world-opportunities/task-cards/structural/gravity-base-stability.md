# ABOUTME: First-pass task-world opportunity card for gravity-base-stability.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / wind-turbine-foundations / gravity-base-stability

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/gravity_base_stability`
- Discipline: `structural`
- Category: `wind-turbine-foundations`
- Tool mode: `with-tool`
- Standards: AS 5100.3; EN 1997-1
- Tags: structural; foundation; gravity-base; stability; deterministic

## Current Task Shape

Calculates reduced gravity base foundation stability from vertical load, overturning moment, base geometry, and allowable bearing pressure. The template reports eccentricity, middle-third limit, maximum bearing pressure, bearing utilisation, and a numeric middle-third flag.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `vertical_load_kn` | Resultant vertical load | float / kN | range=1.0..1000000.0 |
| `overturning_moment_knm` | Overturning moment about the base centroid | float / kNm | range=0.0..10000000.0 |
| `base_width_m` | Base width in the overturning direction | float / m | range=0.1..100.0 |
| `base_length_m` | Base length perpendicular to overturning direction | float / m | range=0.1..100.0 |
| `allowable_bearing_kpa` | Allowable bearing pressure | float / kPa | range=1.0..5000.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `eccentricity_m` | Load eccentricity |  | tolerance=0.03 |
| `middle_third_limit_m` | Middle-third eccentricity limit |  | tolerance=0.03 |
| `maximum_bearing_kpa` | Maximum bearing pressure from linear bearing distribution |  | tolerance=0.03 |
| `bearing_utilisation_ratio` | Maximum bearing divided by allowable bearing pressure |  | tolerance=0.03 |
| `middle_third_satisfied` | Numeric flag where 1 means eccentricity is within the middle third |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `equipment_block` | Equipment foundation block stability check | equipment-foundation; plant-foundation |
| `turbine_base` | Wind turbine gravity base stability check | wind-turbine-foundation; gravity-base |

### Difficulty Notes

```text
easy: all_given | All parameters given for an equipment foundation block
medium: all_given | All parameters given across gravity base foundations
hard: all_given | All parameters given for wind turbine gravity bases
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use borehole logs, lab tables, slope sections, retaining-wall sketches, and geotechnical notes.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Ground parameters can feed retaining-wall, foundation, slope-stability, and structural load checks.

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
