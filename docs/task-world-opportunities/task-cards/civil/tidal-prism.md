# ABOUTME: First-pass task-world opportunity card for tidal-prism.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / tidal-water-levels / tidal-prism

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/tidal_prism`
- Discipline: `civil`
- Category: `tidal-water-levels`
- Tool mode: `with-tool`
- Standards: USACE Coastal Engineering Manual
- Tags: civil; coastal; tidal-prism; inlet; hydraulics; deterministic

## Current Task Shape

Calculates the tidal prism exchanged by an estuary, lagoon, or basin using the reduced relation P = basin surface area x tidal range. It also estimates mean exchange flow and mean inlet velocity from the inlet flow area and exchange duration, giving a deterministic coastal hydraulics screening calculation.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `3`
- Visibility mix: all_given; partial
- Hidden parameters: `exchange_duration_h`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `basin_surface_area_m2` | Water surface area of the tidal basin | float / m2 | range=10000..50000000 |
| `tidal_range_m` | Representative tidal range over the exchange cycle | float / m | range=0.1..8.0 |
| `inlet_width_m` | Hydraulic width of the inlet throat | float / m | range=5..1000 |
| `inlet_average_depth_m` | Average flow depth through the inlet throat | float / m | range=0.5..30 |
| `exchange_duration_h` | Duration of the flood or ebb exchange | float / h | range=1..12.5 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `tidal_prism_m3` | Tidal prism volume exchanged over the tide |  | tolerance=0.03 |
| `inlet_flow_area_m2` | Approximate inlet flow area |  | tolerance=0.03 |
| `mean_tidal_flow_m3_s` | Mean tidal exchange flow rate |  | tolerance=0.03 |
| `mean_tidal_velocity_m_s` | Mean velocity through the inlet throat |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_lagoon` | Small lagoon entrance with modest tidal range | coastal-lagoon; tidal-creek |
| `estuary_inlet` | Medium estuary with a trained or natural inlet | east-coast-estuary; urban-river-mouth |
| `large_embayment` | Large embayment or harbour with broad exchange area | harbour-entrance; large-estuary |

### Difficulty Notes

```text
easy: all_given | All tidal prism inputs given for a small basin
medium: all_given | Mixed estuary sizes and exchange durations
hard: partial | hidden=exchange_duration_h | Large basin context with exchange duration hidden
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
