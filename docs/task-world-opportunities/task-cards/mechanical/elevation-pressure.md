# ABOUTME: First-pass task-world opportunity card for elevation-pressure.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / sprinkler-hydraulics / elevation-pressure

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/elevation_pressure`
- Discipline: `mechanical`
- Category: `sprinkler-hydraulics`
- Tool mode: `with-tool`
- Standards: NFPA 13; AS 2118.1
- Tags: mechanical; hydraulics; elevation; pressure; deterministic

## Current Task Shape

Calculates hydraulic static pressure change from fluid density and elevation difference using the hydrostatic pressure equation. The template reports elevation head, pressure change in kPa, and pressure change in bar.

## Existing Deterministic Contract

- Parameters: `2`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `fluid_density_kg_m3` | Fluid density | float / kg/m3 | range=500.0..1400.0 |
| `elevation_change_m` | Elevation change, positive for pressure increase with lower elevation | float / m | range=-200.0..200.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `elevation_head_m` | Elevation head |  | tolerance=0.03 |
| `pressure_change_kpa` | Static pressure change |  | tolerance=0.03 |
| `pressure_change_bar` | Static pressure change in bar |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `fire_sprinkler_riser` | Fire sprinkler riser elevation pressure check | fire-sprinkler-riser; multi-level-building |
| `water_transfer_main` | Water transfer main elevation pressure check | water-transfer-main; pump-station |

### Difficulty Notes

```text
easy: all_given | All parameters given for a sprinkler riser
medium: all_given | All parameters given across hydraulic systems
hard: all_given | All parameters given for larger transfer mains
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
