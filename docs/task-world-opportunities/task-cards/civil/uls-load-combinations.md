# ABOUTME: First-pass task-world opportunity card for uls-load-combinations.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / load-combinations / uls-load-combinations

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/uls_load_combinations`
- Discipline: `civil`
- Category: `load-combinations`
- Tool mode: `with-tool`
- Standards: AS/NZS 1170.0
- Tags: civil; loading; load-combinations; ULS; structural-actions; deterministic

## Current Task Shape

Computes all five ULS load combinations from AS/NZS 1170.0 Table 4.1 for a structural element subject to permanent, imposed, wind, and earthquake actions. Applies the appropriate combination factors (psi_c and psi_E) based on the imposed action category, then identifies the governing design action for strength design.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `6`
- Archetypes: `6`
- Visibility mix: all_given; partial
- Hidden parameters: `load_category`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `dead_load_kn` | Permanent (dead) load G | float / kN | range=5.0..2000.0 |
| `live_load_kn` | Imposed (live) load Q | float / kN | range=2.0..1500.0 |
| `wind_ultimate_kn` | Ultimate wind action W_u | float / kN | range=0.0..500.0 |
| `earthquake_load_kn` | Earthquake action E | float / kN | range=0.0..500.0 |
| `load_category` | Imposed action category per AS/NZS 1170.0 (A-D general, E storage) | enum | values=A, B, C, D, E |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `uls_permanent_kn` | ULS combination 1: 1.35 * G (kN) |  | tolerance=0.03 |
| `uls_imposed_kn` | ULS combination 2: 1.2 * G + 1.5 * Q (kN) |  | tolerance=0.03 |
| `uls_wind_kn` | ULS combination 3: 1.2 * G + psi_c * Q + W_u (kN) |  | tolerance=0.03 |
| `uls_wind_uplift_kn` | ULS combination 4: 0.9 * G + W_u (kN) |  | tolerance=0.03 |
| `uls_earthquake_kn` | ULS combination 5: G + psi_E * Q + E (kN) |  | tolerance=0.03 |
| `governing_uls_kn` | Governing ULS design action Ed = max of all combinations (kN) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_floor` | Residential floor beam subject to gravity and moderate wind loads | suburban-house-floor-beam; townhouse-first-floor-joist |
| `office_beam` | Office building floor beam (occupancy category B per AS/NZS 1170.0) with moderate imposed and wind actions | city-office-floor-beam; campus-administration-building |
| `retail_floor` | Retail or assembly area floor (occupancy category C per AS/NZS 1170.0) with higher imposed loads | shopping-centre-floor-slab; community-hall-floor |
| `storage_facility` | Warehouse or storage facility (occupancy category E per AS/NZS 1170.0) with high imposed loads | industrial-warehouse-floor; distribution-centre-rack-area |
| `high_wind_coastal` | Coastal commercial structure column (occupancy category B per AS/NZS 1170.0) subject to high ultimate wind actions | north-qld-cyclonic-portal-frame; darwin-commercial-building-column |
| `seismic_zone_column` | Column in a moderate-to-high seismic zone office building (occupancy category B per AS/NZS 1170.0) with significant earthquake action | newcastle-commercial-column; christchurch-office-frame |

### Difficulty Notes

```text
easy: all_given | All parameters given, residential or office with category A, low wind and earthquake
medium: all_given | All parameters given, wider building types including storage (category E) and high wind
hard: partial | hidden=load_category | Load category hidden — agent must determine from building occupancy type described in archetype
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
