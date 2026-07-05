# ABOUTME: First-pass task-world opportunity card for bund-volume-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / oil-containment / bund-volume-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/bund_volume_calculation`
- Discipline: `civil`
- Category: `oil-containment`
- Tool mode: `with-tool`
- Standards: AS/NZS 1940
- Tags: civil; oil-containment; bund; spill; hazardous-materials; deterministic

## Current Task Shape

Calculates the required bund containment capacity for oil and hazardous liquid storage as the greater of 110% of the largest container or 25% of total stored volume, per AS/NZS 1940. Accounts for equipment displacement within the bund and checks whether the net available volume meets the regulatory minimum.

## Existing Deterministic Contract

- Parameters: `8`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `equipment_footprint_area_m2`, `num_equipment_items`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `num_containers` | Number of oil-filled containers within the bund | int / - | range=1..12 |
| `largest_container_volume_l` | Volume of the largest single container | float / L | range=100..50000 |
| `total_stored_volume_l` | Total stored volume across all containers | float / L | range=100..200000 |
| `bund_length_m` | Internal length of the bund enclosure | float / m | range=1.0..25.0 |
| `bund_width_m` | Internal width of the bund enclosure | float / m | range=1.0..15.0 |
| `bund_wall_height_m` | Height of the bund containment walls | float / m | range=0.15..1.5; derivable_from=archetype |
| `num_equipment_items` | Number of equipment items inside the bund (pumps, pipework supports, etc.) | int / - | range=0..6 |
| `equipment_footprint_area_m2` | Average footprint area of each equipment item inside the bund | float / m² | range=0.0..4.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `required_bund_volume_m3` | Required bund capacity per AS/NZS 1940 (m³) |  | tolerance=0.03 |
| `net_bund_volume_m3` | Net available bund volume after equipment displacement (m³) |  | tolerance=0.03 |
| `bund_wall_height_m` | Bund wall height (m) |  | tolerance=0.03 |
| `compliance` | Compliance flag: 1.0 if net >= required, 0.0 otherwise |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `single_transformer` | Single oil-filled power transformer in a dedicated bund enclosure | sydney-substation; brisbane-zone-substation; melbourne-industrial-park |
| `fuel_storage_depot` | Multiple above-ground fuel storage tanks at a bulk fuel depot | perth-kwinana-fuel-depot; darwin-east-arm-terminal; gladstone-industrial |
| `workshop_oil_store` | Small workshop oil and lubricant storage area with drum pallets | cairns-maintenance-depot; adelaide-fleet-workshop; hobart-council-yard |
| `generator_compound` | Diesel generator compound with day tank and bulk storage | townsville-data-centre; alice-springs-remote-power; geelong-hospital-backup |

### Difficulty Notes

```text
easy: all_given | Single container with no equipment displacement — straightforward volume check
medium: all_given | Multiple containers with equipment displacement — agent must apply both AS/NZS 1940 rules
hard: partial | hidden=num_equipment_items, equipment_footprint_area_m2 | Equipment displacement parameters hidden — agent must infer count and footprint from site description
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
