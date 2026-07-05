# ABOUTME: First-pass task-world opportunity card for sewer-slope-check.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / gravity-sewer / sewer-slope-check

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/sewer_slope_check`
- Discipline: `civil`
- Category: `gravity-sewer`
- Tool mode: `with-tool`
- Standards: WSAA WSA 02; BS EN 752
- Tags: civil; sewer; gravity-flow; self-cleansing; compliance; deterministic

## Current Task Shape

Verifies that a gravity sewer pipe's installed slope produces a full-pipe velocity within the self-cleansing range (0.6-4.0 m/s) required by WSAA WSA 02. Uses Manning's equation V = (1/n)*R_h^(2/3)*S^(1/2) for a circular pipe at full flow to compute velocity and capacity, then reports compliance status.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `3`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `mannings_n`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pipe_diameter_mm` | Internal pipe diameter D | float / mm | range=100..900 |
| `pipe_slope_pct` | Pipe longitudinal slope as a percentage | float / % | range=0.1..10.0 |
| `mannings_n` | Manning's roughness coefficient n | float | range=0.009..0.025; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `full_pipe_velocity_m_s` | Full-pipe flow velocity V (m/s) |  | tolerance=0.03 |
| `full_pipe_capacity_l_s` | Full-pipe flow capacity Q (L/s) |  | tolerance=0.03 |
| `compliance` | Self-cleansing compliance (1.0 = adequate, 0.0 = non-compliant) |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_reticulation` | PVC residential sewer reticulation main | brisbane-suburban-subdivision; perth-residential-infill |
| `trunk_sewer` | Reinforced concrete or vitrified clay trunk sewer | melbourne-trunk-sewer; sydney-catchment-sewer |
| `rising_main_connection` | Gravity sewer downstream of a rising main discharge point | adelaide-pump-station-outlet; gold-coast-rising-main-junction |
| `industrial_sewer` | Industrial gravity sewer on steep grade with heavy solids | darwin-industrial-estate; cairns-food-processing-plant |

### Difficulty Notes

```text
easy: all_given | Small residential pipe, all parameters given, gentle slope
medium: all_given | Any pipe size and archetype, all parameters given
hard: partial | hidden=mannings_n | Manning's n hidden, agent must infer from pipe material description
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

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`, `source_curve`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
