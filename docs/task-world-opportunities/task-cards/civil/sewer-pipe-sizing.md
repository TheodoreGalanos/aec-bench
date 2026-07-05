# ABOUTME: First-pass task-world opportunity card for sewer-pipe-sizing.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / gravity-sewer / sewer-pipe-sizing

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/sewer_pipe_sizing`
- Discipline: `civil`
- Category: `gravity-sewer`
- Tool mode: `with-tool`
- Standards: WSAA WSA 02; PUB Code of Practice; AS 4130
- Tags: civil; sewer; gravity-flow; pipe-sizing; mannings; deterministic

## Current Task Shape

Selects the smallest standard gravity sewer pipe diameter (per WSAA WSA 02 / AS 4130) that conveys a given design flow using Manning's equation for full-pipe capacity. Computes pipe slope from invert levels, iterates standard diameters from 150 mm to 1200 mm, and reports the full-pipe velocity and flow depth ratio for the selected pipe.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `mannings_n`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_flow_l_s` | Peak design flow entering the pipe | float / L/s | range=0.5..500.0 |
| `upstream_invert_m` | Upstream pipe invert elevation | float / m AHD | range=0.5..200.0 |
| `downstream_invert_m` | Downstream pipe invert elevation | float / m AHD | range=0.1..199.5 |
| `pipe_length_m` | Pipe length between manholes | float / m | range=10.0..200.0 |
| `mannings_n` | Manning's roughness coefficient n | float | range=0.009..0.025; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `selected_diameter_mm` | Selected standard pipe internal diameter (mm) |  | tolerance=0.01 |
| `pipe_slope_pct` | Pipe longitudinal slope (%) |  | tolerance=0.03 |
| `full_pipe_velocity_m_s` | Full-pipe flow velocity V (m/s) |  | tolerance=0.03 |
| `flow_depth_ratio` | Approximate flow depth ratio d/D (design flow / full capacity) |  | tolerance=0.05 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_reticulation` | PVC residential sewer reticulation main with small domestic flows | brisbane-suburban-subdivision; perth-residential-infill; adelaide-greenfield-estate |
| `subdivision_collector` | Reinforced concrete collector sewer in a subdivision trunk network | sydney-new-subdivision; melbourne-growth-corridor; gold-coast-mixed-density |
| `trunk_sewer` | Large-diameter reinforced concrete trunk sewer conveying combined catchment flows | melbourne-trunk-sewer; sydney-catchment-interceptor; brisbane-major-trunk |
| `industrial_sewer` | Industrial gravity sewer with trade waste discharges on steep terrain | darwin-industrial-estate; cairns-food-processing-zone; townsville-port-precinct |

### Difficulty Notes

```text
easy: all_given | Small residential pipe, all parameters given, gentle slopes
medium: all_given | All pipe sizes and archetypes, all parameters given
hard: partial | hidden=mannings_n | Manning's n hidden, agent must infer from pipe material and site description
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
