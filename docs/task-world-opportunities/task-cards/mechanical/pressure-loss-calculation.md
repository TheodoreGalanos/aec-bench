# ABOUTME: First-pass task-world opportunity card for pressure-loss-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / pipe-sizing-water / pressure-loss-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/pressure_loss_calculation`
- Discipline: `mechanical`
- Category: `pipe-sizing-water`
- Tool mode: `with-tool`
- Standards: AS/NZS 3500.1; Hazen-Williams
- Tags: mechanical; hydraulics; pipe; pressure-loss; deterministic

## Current Task Shape

Calculates water pipe pressure loss using the Hazen-Williams equation for straight-pipe friction and a total K value for fittings and valves. The template reports pipe velocity, friction loss, fitting loss, and total pressure loss in kPa.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_l_s` | Water flow rate | float / L/s | range=0.01..1000.0 |
| `pipe_internal_diameter_mm` | Internal pipe diameter | float / mm | range=10.0..1000.0 |
| `pipe_length_m` | Pipe length | float / m | range=0.1..5000.0 |
| `hazen_williams_c` | Hazen-Williams roughness coefficient | float | range=40.0..160.0 |
| `total_fitting_k` | Total fitting and valve K value | float | range=0.0..100.0 |
| `fluid_density_kg_m3` | Fluid density | float / kg/m3 | range=900.0..1200.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `velocity_m_s` | Pipe flow velocity |  | tolerance=0.03 |
| `friction_loss_kpa` | Straight-pipe friction pressure loss |  | tolerance=0.03 |
| `fitting_loss_kpa` | Fitting and valve pressure loss |  | tolerance=0.03 |
| `total_pressure_loss_kpa` | Total pipe pressure loss |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `building_water_service` | Building water service pressure-loss check | building-water-service; domestic-water-riser |
| `site_water_main` | Site water main pressure-loss check | site-water-main; campus-water-ring-main |

### Difficulty Notes

```text
easy: all_given | All parameters given for a building water service
medium: all_given | All parameters given across water pipe contexts
hard: all_given | All parameters given for a site water main
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
