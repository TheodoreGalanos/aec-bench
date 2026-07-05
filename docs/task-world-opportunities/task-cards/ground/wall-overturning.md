# ABOUTME: First-pass task-world opportunity card for wall-overturning.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# ground / retaining-walls / wall-overturning

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/ground/wall_overturning`
- Discipline: `ground`
- Category: `retaining-walls`
- Tool mode: `with-tool`
- Standards: AS 4678; Eurocode 7
- Tags: geotechnical; retaining-wall; overturning; stability

## Current Task Shape

Evaluates overturning stability of cantilever retaining walls by computing the factor of safety as the ratio of resisting to overturning moments about the wall toe. Uses Rankine active earth pressure (Ka) to determine lateral forces from backfill and surcharge, and sums stabilising moments from the self-weight of the stem, base slab, and backfill soil per AS 4678 and Eurocode 7.

## Existing Deterministic Contract

- Parameters: `9`
- Outputs: `5`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `backfill_friction_angle_deg`, `backfill_unit_weight_kn_m3`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `wall_height_m` | Height of the wall stem above the base slab | float / m | range=2.0..10.0 |
| `base_width_m` | Total width of the base slab | float / m | range=1.5..8.0 |
| `stem_thickness_m` | Thickness of the wall stem | float / m | range=0.2..1.0 |
| `base_thickness_m` | Thickness of the base slab | float / m | range=0.3..1.2 |
| `backfill_friction_angle_deg` | Effective friction angle of the backfill soil | float / degrees | range=20..45; derivable_from=archetype |
| `backfill_unit_weight_kn_m3` | Unit weight of the backfill soil | float / kN/m³ | range=15..22; derivable_from=archetype |
| `concrete_unit_weight_kn_m3` | Unit weight of the reinforced concrete | float / kN/m³ | range=23..25 |
| `surcharge_kpa` | Uniform surcharge load on the backfill surface | float / kPa | range=0..30 |
| `water_table_depth_m` | Depth to water table from the top of the wall | float / m | range=0..20 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `ka` | Rankine active earth pressure coefficient Ka |  | tolerance=0.03 |
| `active_force_kn_m` | Total active force per metre of wall Pa (kN/m) |  | tolerance=0.05 |
| `overturning_moment_knm_m` | Overturning moment about the toe Mo (kNm/m) |  | tolerance=0.05 |
| `resisting_moment_knm_m` | Resisting moment about the toe Mr (kNm/m) |  | tolerance=0.05 |
| `factor_of_safety_overturning` | Factor of safety against overturning FoS |  | tolerance=0.05 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `loose_granular_fill` | Loose granular fill | brisbane-alluvial; darwin-reclaimed |
| `medium_dense_sand` | Medium dense sand backfill | perth-coastal; hunter-valley-alluvial |
| `dense_gravel` | Dense compacted gravel | sydney-hawkesbury; melbourne-basalt |
| `stiff_clay_fill` | Stiff clay fill | adelaide-stiff; canberra-residual |

### Difficulty Notes

```text
easy: all_given | All parameters given, no surcharge, no water table
medium: all_given | All parameters given, surcharge and water table present
hard: partial | hidden=backfill_friction_angle_deg, backfill_unit_weight_kn_m3 | Soil parameters hidden, surcharge and water table present
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use borehole logs, lab tables, slope sections, retaining-wall sketches, and geotechnical notes.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Ground parameters can feed retaining-wall, foundation, slope-stability, and structural load checks.

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
