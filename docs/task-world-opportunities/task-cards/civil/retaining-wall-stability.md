# ABOUTME: First-pass task-world opportunity card for retaining-wall-stability.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / slope-stability / retaining-wall-stability

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/retaining_wall_stability`
- Discipline: `civil`
- Category: `slope-stability`
- Tool mode: `with-tool`
- Standards: AS 4678; Eurocode 7
- Tags: civil; geotechnical; retaining-wall; gravity-wall; sliding; overturning; bearing-capacity; stability

## Current Task Shape

Evaluates the external stability of a rectangular gravity retaining wall against three failure modes: sliding along the base, overturning about the toe, and bearing capacity failure of the foundation soil. Active earth pressure is computed using Rankine theory for horizontal backfill, and bearing capacity uses Terzaghi strip footing factors. Outputs include factors of safety, eccentricity, and maximum base pressure per AS 4678 and Eurocode 7.

## Existing Deterministic Contract

- Parameters: `11`
- Outputs: `6`
- Archetypes: `5`
- Visibility mix: all_given; partial
- Hidden parameters: `backfill_friction_angle_deg`, `backfill_unit_weight_kn_m3`, `foundation_cohesion_kpa`, `foundation_friction_angle_deg`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `wall_height_m` | Total height of the gravity retaining wall H | float / m | range=2.0..6.0 |
| `base_width_m` | Width of the wall base B (typically 0.5H to 0.7H) | float / m | range=2.0..4.5 |
| `wall_thickness_m` | Thickness of the wall stem at the top t | float / m | range=0.4..1.5 |
| `concrete_unit_weight_kn_m3` | Unit weight of the wall material (concrete or masonry) gamma_c | float / kN/m3 | range=22.0..25.0; derivable_from=archetype |
| `backfill_friction_angle_deg` | Effective friction angle of the backfill soil phi' | float / degrees | range=20.0..40.0; derivable_from=archetype |
| `backfill_unit_weight_kn_m3` | Total unit weight of the backfill soil gamma_s | float / kN/m3 | range=16.0..21.0; derivable_from=archetype |
| `backfill_cohesion_kpa` | Effective cohesion of the backfill soil c' | float / kPa | range=0.0..20.0; derivable_from=archetype |
| `surcharge_kpa` | Uniform surcharge pressure on the backfill surface q | float / kPa | range=0.0..25.0 |
| `foundation_friction_angle_deg` | Effective friction angle of the foundation soil phi_f | float / degrees | range=20.0..42.0; derivable_from=archetype |
| `foundation_cohesion_kpa` | Effective cohesion of the foundation soil c_f | float / kPa | range=0.0..50.0; derivable_from=archetype |
| `base_friction_ratio` | Ratio of base interface friction to foundation soil friction (typically 2/3) | float | range=0.5..1.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `ka` | Rankine active earth pressure coefficient Ka (dimensionless) |  | tolerance=0.03 |
| `fos_sliding` | Factor of safety against sliding along the base (dimensionless) |  | tolerance=0.05 |
| `fos_overturning` | Factor of safety against overturning about the toe (dimensionless) |  | tolerance=0.05 |
| `fos_bearing` | Factor of safety against bearing capacity failure (dimensionless) |  | tolerance=0.05 |
| `eccentricity_m` | Eccentricity of the resultant force from the base centre e (m) |  | tolerance=0.05 |
| `max_base_pressure_kpa` | Maximum base contact pressure under the footing q_max (kPa) |  | tolerance=0.05 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `granular_backfill_sandy_foundation` | Clean granular backfill behind a mass concrete wall on medium dense sand | sydney-harbour-seawall; gold-coast-canal-retaining |
| `gravel_backfill_stiff_clay_foundation` | Compacted gravel backfill behind a gravity wall on stiff clay foundation | melbourne-basalt-clay-site; canberra-substation-terrace |
| `silty_sand_backfill_weathered_rock` | Silty sand backfill behind a concrete gravity wall on weathered rock | brisbane-hillside-retaining; cairns-port-access-wall |
| `cohesive_backfill_sandy_foundation` | Cohesive fill behind a masonry gravity wall on sandy foundation | adelaide-hills-road-wall; perth-coastal-terrace |
| `dense_sand_backfill_firm_clay` | Dense sand backfill behind a concrete wall on firm clay | darwin-stormwater-channel-wall; townsville-wharf-retaining |

### Difficulty Notes

```text
easy: all_given | Cohesionless backfill, no surcharge, all parameters given — simplest three-check variant
medium: all_given | Surcharge and cohesion may be present, all parameters given — full formula set
hard: partial | hidden=backfill_friction_angle_deg, backfill_unit_weight_kn_m3, foundation_friction_angle_deg, foundation_cohesion_kpa | Soil properties hidden, agent must infer from site context and soil description
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
