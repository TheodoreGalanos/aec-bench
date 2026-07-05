# ABOUTME: First-pass task-world opportunity card for thrust-force-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / thrust-restraint / thrust-force-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/thrust_force_calculation`
- Discipline: `mechanical`
- Category: `thrust-restraint`
- Tool mode: `with-tool`
- Standards: AWWA M11; AS 2566.1
- Tags: mechanical; pipe; thrust; restraint; deterministic

## Current Task Shape

Calculates unbalanced thrust force at a pressurised pipe bend from internal pressure, pipe internal diameter, and bend angle. The template reports pipe area, straight pressure force, and bend thrust force.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `internal_pressure_kpa` | Internal pipe pressure | float / kPa | range=0.0..5000.0 |
| `pipe_internal_diameter_mm` | Pipe internal diameter | float / mm | range=10.0..3000.0 |
| `bend_angle_deg` | Pipe bend angle | float / degrees | range=0.0..180.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pipe_area_m2` | Pipe internal area |  | tolerance=0.03 |
| `pressure_force_kn` | Straight pressure force |  | tolerance=0.03 |
| `bend_thrust_force_kn` | Unbalanced bend thrust force |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `water_main_bend` | Water main bend thrust check | water-main; thrust-block |
| `rising_main_bend` | Wastewater rising main bend thrust check | wastewater-rising-main; restrained-joint |

### Difficulty Notes

```text
easy: all_given | All parameters given for a water main bend
medium: all_given | All parameters given across restrained pipe bends
hard: all_given | All parameters given for larger rising mains
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `chart-curve`.

Use network schematics, long sections, asset schedules, rating curves, and source tables.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Pipe and channel outputs naturally feed pump station, detention, outfall, and flood-level checks.

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
