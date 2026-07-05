# ABOUTME: First-pass task-world opportunity card for orifice-outlet-design.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / detention-design / orifice-outlet-design

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/orifice_outlet_design`
- Discipline: `civil`
- Category: `detention-design`
- Tool mode: `with-tool`
- Standards: Hydraulics textbooks
- Tags: civil; hydraulics; stormwater; detention; orifice

## Current Task Shape

Sizes a circular orifice outlet for a stormwater detention basin by rearranging the orifice equation Q = Cd*A*sqrt(2gH) to solve for the required orifice area and diameter given a target discharge flow rate and available head. Commonly applied in urban stormwater management to control post-development peak flows.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `3`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `discharge_coefficient`, `head_above_centreline_m`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_flow_m3_s` | Target discharge flow rate Q | float / m³/s | range=0.005..2.0 |
| `head_above_centreline_m` | Head of water above orifice centreline H | float / m | range=0.1..5.0; derivable_from=archetype |
| `discharge_coefficient` | Orifice discharge coefficient Cd | float | range=0.4..0.8; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `required_orifice_area_m2` | Required orifice area A (m²) |  | tolerance=0.03 |
| `orifice_diameter_mm` | Orifice diameter D (mm) |  | tolerance=0.03 |
| `discharge_velocity_m_s` | Discharge velocity through orifice v (m/s) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_urban_basin` | Small urban detention basin with low head | sydney-infill-residential; melbourne-suburban-subdivision |
| `medium_commercial_basin` | Medium commercial development detention basin | brisbane-commercial-park; adelaide-retail-precinct |
| `large_regional_basin` | Large regional stormwater detention facility | perth-regional-wetland; gold-coast-flood-control |
| `shallow_linear_basin` | Shallow linear detention basin along road corridor | canberra-road-corridor; townsville-drainage-channel |

### Difficulty Notes

```text
easy: all_given | All parameters given, standard discharge coefficient
medium: all_given | All parameters given, variable discharge coefficient
hard: partial | hidden=discharge_coefficient, head_above_centreline_m | Discharge coefficient and head hidden, agent must infer from site context
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
