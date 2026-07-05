# ABOUTME: First-pass task-world opportunity card for weir-outlet-design.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / detention-design / weir-outlet-design

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/weir_outlet_design`
- Discipline: `civil`
- Category: `detention-design`
- Tool mode: `with-tool`
- Standards: Hydraulics textbooks; Francis formula (1883)
- Tags: civil; hydraulics; stormwater; detention; weir; spillway

## Current Task Shape

Sizes a sharp-crested rectangular weir for detention basin emergency overflow using the Francis formula Q = Cw * (L - 0.1*n*H) * H^1.5, where Cw = Cd * sqrt(2g). Solves for the required crest length given design flow, head, discharge coefficient, and end contractions, supporting stormwater detention and flood control design.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `2`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `discharge_coefficient`, `head_over_weir_m`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_flow_m3_s` | Design overflow discharge Q | float / m³/s | range=0.01..10.0 |
| `head_over_weir_m` | Head of water over the weir crest H | float / m | range=0.05..1.5; derivable_from=archetype |
| `discharge_coefficient` | Weir discharge coefficient Cd | float | range=0.55..0.7; derivable_from=archetype |
| `number_of_contractions` | Number of end contractions n (0 = suppressed, 1 or 2 = contracted) | int | range=0..2; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `required_weir_length_m` | Required weir crest length L (m) |  | tolerance=0.03 |
| `unit_discharge_m3_s_per_m` | Unit discharge per metre of weir crest q (m³/s/m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_urban_basin` | Small urban detention basin with low-level spillway weir | sydney-infill-residential; melbourne-suburban-subdivision |
| `medium_commercial_basin` | Medium commercial development detention basin spillway | brisbane-commercial-park; adelaide-retail-precinct |
| `large_regional_basin` | Large regional stormwater detention facility with emergency spillway | perth-regional-wetland; gold-coast-flood-control |
| `channel_diversion_weir` | Channel diversion weir with end contractions | canberra-drainage-diversion; townsville-channel-control |

### Difficulty Notes

```text
easy: all_given | All parameters given, suppressed weir with standard coefficient
medium: all_given | All parameters given, variable coefficient and end contractions
hard: partial | hidden=discharge_coefficient, head_over_weir_m | Discharge coefficient and head hidden, agent must infer from site context
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
