# ABOUTME: First-pass task-world opportunity card for sls-load-combinations.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / load-combinations / sls-load-combinations

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/sls_load_combinations`
- Discipline: `civil`
- Category: `load-combinations`
- Tool mode: `with-tool`
- Standards: AS/NZS 1170.0
- Tags: civil; loading; serviceability; load-combinations; SLS; structural-actions; deterministic

## Current Task Shape

Computes serviceability limit state load combinations for structural deflection checks using AS/NZS 1170.0 Table 4.1. Determines short-term and long-term combination factors from the imposed-action category, applies them to dead and live loads, adds wind serviceability actions where applicable, and identifies the governing SLS combination for design.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `6`
- Archetypes: `7`
- Visibility mix: all_given; partial
- Hidden parameters: `load_category`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `dead_load_kn` | Permanent (dead) load G acting on the member | float / kN | range=1.0..500.0 |
| `live_load_kn` | Imposed (live) load Q acting on the member | float / kN | range=1.0..400.0 |
| `wind_serviceability_kn` | Serviceability wind action W_s on the member (zero if wind not applicable) | float / kN | range=0.0..150.0 |
| `load_category` | Imposed-action category per AS 1170.1 (A = domestic, B = offices, C = public assembly, D = retail, E = storage) | enum | values=A, B, C, D, E; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `psi_s` | Short-term combination factor from AS/NZS 1170.0 Table 4.1 |  | tolerance=0.01 |
| `psi_l` | Long-term combination factor from AS/NZS 1170.0 Table 4.1 |  | tolerance=0.01 |
| `sls_short_term_kn` | Short-term SLS combination G + psi_s * Q (kN) |  | tolerance=0.03 |
| `sls_long_term_kn` | Long-term SLS combination G + psi_l * Q (kN) |  | tolerance=0.03 |
| `sls_wind_kn` | Wind SLS combination G + psi_s * Q + W_s (kN) |  | tolerance=0.03 |
| `governing_sls_kn` | Governing (maximum) SLS combination value (kN) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_floor` | Residential house floor with light dead load and domestic imposed loads | suburban-house-timber-floor; townhouse-concrete-slab |
| `office_floor` | Office building floor with moderate dead and live loads | cbd-office-tower-floor; suburban-office-park-slab |
| `assembly_floor` | Public assembly area such as a theatre or restaurant floor | convention-centre-mezzanine; stadium-concourse-slab |
| `retail_floor` | Retail/shopping floor with moderate imposed loads | shopping-centre-ground-floor; mixed-use-retail-podium |
| `storage_floor` | Storage or warehouse floor with heavy imposed loads | logistics-warehouse-slab; cold-store-mezzanine |
| `exposed_office_with_wind` | Office building member exposed to serviceability wind on an upper storey | coastal-office-tower-facade; high-rise-office-beam |
| `assembly_with_wind` | Public assembly structure with significant serviceability wind actions | grandstand-roof-beam; airport-terminal-long-span |

### Difficulty Notes

```text
easy: all_given | All parameters given including category, no wind action — straightforward factor lookup and arithmetic
medium: all_given | All parameters given, includes wind serviceability actions across multiple categories
hard: partial | hidden=load_category | Load category hidden — agent must infer the correct psi factors from the building use description
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
