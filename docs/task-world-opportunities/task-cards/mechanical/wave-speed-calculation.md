# ABOUTME: First-pass task-world opportunity card for wave-speed-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / transient-analysis / wave-speed-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/wave_speed_calculation`
- Discipline: `mechanical`
- Category: `transient-analysis`
- Tool mode: `with-tool`
- Standards: AWWA M11
- Tags: mechanical; water-hammer; wave-speed; transient-analysis; deterministic

## Current Task Shape

Calculates pressure wave propagation speed in an elastic pipe from fluid bulk modulus, fluid density, pipe elastic modulus, diameter, wall thickness, and restraint condition. The template separates the fluid-only wave speed from the pipe flexibility reduction used in first-pass water hammer screening.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `3`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `fluid_bulk_modulus_gpa` | Fluid bulk modulus K | float / GPa | range=0.8..2.4 |
| `fluid_density_kg_m3` | Fluid density rho | float / kg/m3 | range=700.0..1300.0 |
| `pipe_elastic_modulus_gpa` | Pipe material elastic modulus E | float / GPa | range=0.5..220.0 |
| `pipe_diameter_mm` | Pipe internal diameter D | float / mm | range=50.0..2500.0 |
| `pipe_wall_thickness_mm` | Pipe wall thickness e | float / mm | range=2.0..80.0 |
| `restraint_condition` | Pipe restraint condition factor | enum | values=fully_restrained, anchored_with_expansion, unrestrained |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `fluid_only_wave_speed_m_s` | Wave speed considering fluid compressibility only |  | tolerance=0.03 |
| `flexibility_factor` | Pipe flexibility reduction factor |  | tolerance=0.03 |
| `wave_speed_m_s` | Pressure wave speed in the pipe |  | tolerance=0.03 |
| `pipe_flexibility_ratio` | Dimensionless pipe flexibility contribution |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `steel_water_main` | Steel water main with high wall stiffness | trunk-water-main; raw-water-pipeline |
| `ductile_iron_main` | Ductile iron water main with cement lining | urban-distribution-main; regional-transfer-main |
| `hdpe_rising_main` | Flexible HDPE rising main | sewer-rising-main; irrigation-transfer-line |

### Difficulty Notes

```text
easy: all_given | All parameters given for a stiff steel water main
medium: all_given | All parameters given across steel and ductile iron water mains
hard: all_given | All parameters given across stiff and flexible pipe systems
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
