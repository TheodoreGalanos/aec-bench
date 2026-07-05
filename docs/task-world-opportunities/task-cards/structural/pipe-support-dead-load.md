# ABOUTME: First-pass task-world opportunity card for pipe-support-dead-load.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# structural / pipe-support / pipe-support-dead-load

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/structural/pipe_support_dead_load`
- Discipline: `structural`
- Category: `pipe-support`
- Tool mode: `with-tool`
- Standards: ASME B31.3; AS 4041; EN 13480
- Tags: structural; pipe-support; dead-load; hydrotest; deterministic

## Current Task Shape

Calculates pipe support dead load from steel pipe annulus, fluid contents area, and insulation annulus using explicit densities and pipe geometry. The template reports operating line load and hydrotest line load when hydrotest density is provided.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pipe_outer_diameter_mm` | Pipe outside diameter | float / mm | range=25.0..2000.0 |
| `pipe_wall_thickness_mm` | Pipe wall thickness | float / mm | range=1.0..80.0 |
| `steel_density_kg_m3` | Steel pipe density | float / kg/m3 | range=7600.0..8000.0 |
| `contents_density_kg_m3` | Operating contents density | float / kg/m3 | range=0.0..1600.0 |
| `insulation_thickness_mm` | Radial insulation thickness | float / mm | range=0.0..200.0 |
| `insulation_density_kg_m3` | Insulation density | float / kg/m3 | range=0.0..300.0 |
| `hydrotest_density_kg_m3` | Hydrotest fluid density | float / kg/m3 | range=950.0..1200.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `steel_pipe_load_kn_m` | Steel pipe self-weight line load |  | tolerance=0.03 |
| `contents_load_kn_m` | Operating contents line load |  | tolerance=0.03 |
| `insulation_load_kn_m` | Insulation line load |  | tolerance=0.03 |
| `operating_line_load_kn_m` | Operating dead line load for pipe support |  | tolerance=0.03 |
| `hydrotest_line_load_kn_m` | Hydrotest dead line load for pipe support |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_process_line` | Small insulated process pipe support dead-load check | process-pipe-rack; plant-room |
| `large_utility_line` | Large utility pipe support dead-load check | utility-corridor; industrial-pipe-rack |

### Difficulty Notes

```text
easy: all_given | All parameters given for a small process pipe
medium: all_given | All parameters given across small and large pipe supports
hard: all_given | All parameters given for a large utility pipe
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
