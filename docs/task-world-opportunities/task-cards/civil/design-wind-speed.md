# ABOUTME: First-pass task-world opportunity card for design-wind-speed.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / wind-load-derivation / design-wind-speed

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/design_wind_speed`
- Discipline: `civil`
- Category: `wind-load-derivation`
- Tool mode: `with-tool`
- Standards: AS/NZS 1170.2
- Tags: civil; wind; loading; structural; deterministic

## Current Task Shape

Calculates the design site wind speed using the AS/NZS 1170.2 Section 2.2 equation V_sit,beta = V_R * M_d * M_z,cat * M_s * M_t. The terrain/height multiplier M_z,cat is looked up from Table 4.1(A) with linear interpolation for intermediate heights across five terrain categories. Applicable to buildings and structures in Australian and New Zealand wind regions.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `2`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `shielding_multiplier`, `terrain_category`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `regional_wind_speed_m_per_s` | Regional 3-second gust wind speed V_R | float / m/s | range=25..70 |
| `terrain_category` | Terrain category per AS/NZS 1170.2 Section 4.2 | enum | values=1, 2, 2.5, 3, 4; derivable_from=archetype |
| `building_height_m` | Building height above ground z | float / m | range=2..200 |
| `topographic_multiplier` | Topographic multiplier M_t | float / - | range=1.0..1.5 |
| `shielding_multiplier` | Shielding multiplier M_s | float / - | range=0.7..1.0; derivable_from=archetype |
| `wind_direction_multiplier` | Wind direction multiplier M_d | float / - | range=0.8..1.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `mz_cat` | Terrain/height multiplier M_z,cat from Table 4.1(A) |  | tolerance=0.03 |
| `site_wind_speed_m_per_s` | Site wind speed V_sit,beta (m/s) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `flat_unshielded` | Flat open terrain site with no surrounding obstructions (terrain category 1 or 2) and no topographic amplification | darling-downs-qld; riverina-nsw; gold-coast-beachfront; darwin-coastal |
| `lightly_shielded` | Site in suburban area with partial shielding from nearby low-rise buildings or vegetation (terrain category 2.5 or 3) | sydney-western-suburbs; melbourne-outer-east; brisbane-northside; wetherill-park-nsw |
| `heavily_shielded` | Site in dense urban centre heavily shielded by closely spaced multi-storey buildings (terrain category 4) | sydney-cbd; melbourne-cbd; brisbane-cbd |
| `hilltop_exposed` | Building on or near a hilltop or escarpment with topographic wind acceleration in open terrain (terrain category 1 or 2) | blue-mountains-nsw; mt-coot-tha-qld; adelaide-hills-sa |

### Difficulty Notes

```text
easy: all_given | All parameters given, flat terrain with no shielding or topographic effects
medium: all_given | All parameters given, includes shielding and topographic effects
hard: partial | hidden=terrain_category, shielding_multiplier | Terrain category and shielding hidden — agent must infer from site description
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use building elevations, terrain/zone diagrams, load schedules, and standards extracts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Wind-speed and pressure derivations can feed structural member, bracket, cladding, and foundation checks.

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
