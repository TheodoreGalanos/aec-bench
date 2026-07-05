# ABOUTME: First-pass task-world opportunity card for spillway-weir-capacity.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / spillway-hydraulics / spillway-weir-capacity

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/spillway_weir_capacity`
- Discipline: `civil`
- Category: `spillway-hydraulics`
- Tool mode: `with-tool`
- Standards: USBR Design Standard No. 14; USACE EM 1110-2-1603
- Tags: civil; hydraulics; dams; spillway; weir; discharge

## Current Task Shape

Calculates spillway discharge capacity using the weir equation Q = C*L_eff*H_e^1.5 with pier and abutment contraction corrections to effective crest length and approach velocity head adjustments per USBR Design Standard No. 14 and USACE EM 1110-2-1603. Supports ogee and broad-crested weir types for dam safety and flood routing assessments.

## Existing Deterministic Contract

- Parameters: `8`
- Outputs: `5`
- Archetypes: `5`
- Visibility mix: all_given; partial
- Hidden parameters: `abutment_shape`, `discharge_coefficient`, `pier_shape`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `crest_length_m` | Gross crest length of the spillway L | float / m | range=3.0..120.0 |
| `design_head_m` | Design head over the spillway crest H | float / m | range=0.3..8.0 |
| `discharge_coefficient` | Weir discharge coefficient C (SI metric) | float | range=1.4..2.25; derivable_from=archetype |
| `number_of_piers` | Number of piers on the spillway crest N | int | range=0..8 |
| `pier_shape` | Pier nose geometry for contraction coefficient Kp | enum | values=square, round, pointed; derivable_from=archetype |
| `abutment_shape` | Abutment geometry for contraction coefficient Ka | enum | values=square, rounded, streamlined; derivable_from=archetype |
| `approach_channel_width_m` | Width of the approach channel upstream of the spillway B | float / m | range=5.0..200.0 |
| `approach_depth_m` | Depth of flow in the approach channel h_approach | float / m | range=0.5..15.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `effective_crest_length_m` | Effective crest length after pier and abutment contraction corrections L_eff (m) |  | tolerance=0.03 |
| `approach_velocity_head_m` | Approach velocity head correction Va²/(2g) (m) |  | tolerance=0.05 |
| `total_energy_head_m` | Total energy head over crest He = H + Va²/(2g) (m) |  | tolerance=0.03 |
| `discharge_m3_s` | Total spillway discharge capacity Q (m³/s) |  | tolerance=0.03 |
| `unit_discharge_m3_s_per_m` | Unit discharge per metre of effective crest q (m³/s/m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_ogee_dam` | Small ogee spillway dam with low head and no piers | tasmania-small-hydro; victoria-farm-dam |
| `medium_ogee_gated` | Medium ogee spillway with gated bays and piers | nsw-water-supply-dam; queensland-irrigation-dam |
| `large_ogee_flood` | Large ogee flood spillway with multiple pier bays | snowy-mountains-flood-dam; north-queensland-major-dam |
| `broad_crested_weir` | Broad-crested weir spillway on low-head dam or diversion structure | south-australia-diversion-weir; western-australia-creek-crossing |
| `broad_crested_large` | Large broad-crested spillway with piers for multi-bay structure | northern-territory-barrage; canberra-lake-overflow |

### Difficulty Notes

```text
easy: all_given | Simple ogee spillway, no piers, all parameters given
medium: all_given | All parameters given, includes pier and abutment corrections across both types
hard: partial | hidden=discharge_coefficient, pier_shape, abutment_shape | Discharge coefficient, pier shape, and abutment shape hidden; agent infers from site context
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
