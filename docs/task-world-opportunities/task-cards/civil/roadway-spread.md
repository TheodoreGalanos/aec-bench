# ABOUTME: First-pass task-world opportunity card for roadway-spread.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / hydraulic-calculations / roadway-spread

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/roadway_spread`
- Discipline: `civil`
- Category: `hydraulic-calculations`
- Tool mode: `both`
- Standards: HEC-22
- Tags: civil; hydraulics; drainage; roadway; gutter; spread; inlet-spacing

## Current Task Shape

Determines the width of water spread across a roadway pavement and curb flow depth using the HEC-22 Manning's equation for triangular gutter sections: T = (Q*n / (K_u * Sx^(5/3) * S_L^(1/2)))^(3/8). Used for inlet spacing design and pavement drainage adequacy checks to ensure roadway safety during design storms.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `2`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `mannings_n`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `gutter_flow_m3_s` | Design gutter flow rate Q | float / m³/s | range=0.001..0.2 |
| `cross_slope_pct` | Roadway cross-slope Sx (percentage) | float / % | range=1.0..6.0 |
| `longitudinal_slope_pct` | Longitudinal road gradient S_L (percentage) | float / % | range=0.3..10.0 |
| `mannings_n` | Manning's roughness coefficient n for the pavement surface | float | range=0.011..0.02; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `spread_width_m` | Width of water spread on the roadway T (m) |  | tolerance=0.03 |
| `curb_depth_m` | Flow depth at the curb face d (m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `urban_local_road` | Urban local road with steep cross-slope and smooth asphalt pavement | sydney-suburban-street; melbourne-residential-road; brisbane-local-access |
| `suburban_collector` | Suburban collector road with moderate cross-slope and aged asphalt surface | perth-suburban-collector; adelaide-ring-route; canberra-distributor-road |
| `arterial_road` | Major arterial road with standard cross-slope and concrete gutter channel | sydney-arterial-corridor; melbourne-main-road; gold-coast-boulevard |
| `highway_shoulder` | Highway shoulder with shallow cross-slope and textured asphalt surface | bruce-highway-shoulder; hume-motorway-verge; pacific-highway-shoulder |

### Difficulty Notes

```text
easy: all_given | Small urban road, all parameters given, straightforward spread calculation
medium: all_given | Arterial or highway with higher flows, all parameters given
hard: partial | hidden=mannings_n | Manning's n hidden, agent must infer roughness from road surface description
```

## Multimodal Expansion

Candidate modality families: `spatial-map`, `tabular-source`, `time-series`.

Use catchment plans, rainfall tables, hyetographs, and drainage schedules as source artifacts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Connect rainfall/runoff outputs to detention, pipe, HGL, outlet, and water-quality checks.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`, `source_timeseries`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
