# ABOUTME: First-pass task-world opportunity card for driveway-gradient-check.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / driveway-access / driveway-gradient-check

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/driveway_gradient_check`
- Discipline: `civil`
- Category: `driveway-access`
- Tool mode: `with-tool`
- Standards: AS/NZS 2890.1:2004; Local Council DCPs
- Tags: civil; driveway; gradient; compliance; access; deterministic

## Current Task Shape

Calculates the driveway gradient as a percentage from the level difference and horizontal distance, then checks compliance against location-specific maximum gradients defined in AS/NZS 2890.1:2004 and typical Australian council development control plans. Covers transition zones, residential and commercial internal sections, garage approaches, and shared pedestrian/vehicle paths.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `3`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `location_type`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `start_level_m` | Start level of the driveway section (reduced level) | float / m AHD | range=0.0..200.0 |
| `end_level_m` | End level of the driveway section (reduced level) | float / m AHD | range=0.0..200.0 |
| `horizontal_length_m` | Horizontal distance of the driveway section | float / m | range=1.0..50.0 |
| `location_type` | Driveway section location type determining the maximum allowable gradient | enum | values=transition_zone, internal_residential, internal_commercial, near_garage, pedestrian_shared; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `gradient_pct` | Calculated driveway gradient (%) |  | tolerance=0.03 |
| `max_allowable_gradient_pct` | Maximum allowable gradient for the location type (%) |  | tolerance=0.01 |
| `compliance` | Compliance with maximum gradient (1.0 = pass, 0.0 = fail) |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `steep_hillside_house` | Steep hillside residential driveway with significant level change | sydney-north-shore-hillside; hobart-steep-residential |
| `flat_suburban` | Flat suburban residential driveway with gentle grade | brisbane-suburban-flat; adelaide-plains-residential |
| `commercial_carpark` | Commercial car park driveway access from street to parking level | melbourne-cbd-carpark; perth-commercial-precinct |
| `shared_access` | Shared pedestrian and vehicle access path in a mixed-use development | canberra-mixed-use-development; gold-coast-shared-access |

### Difficulty Notes

```text
easy: all_given | Flat suburban site, all parameters given, transition zone only
medium: all_given | Any archetype, all parameters given, any location type
hard: partial | hidden=location_type | Location type hidden, agent must infer from site and driveway description
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `spatial-map`, `tabular-source`.

Use plans, profiles, catchment/context maps, schedules, and standards excerpts as source evidence.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
