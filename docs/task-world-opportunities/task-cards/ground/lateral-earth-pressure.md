# ABOUTME: First-pass task-world opportunity card for lateral-earth-pressure.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# ground / retaining-walls / lateral-earth-pressure

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/ground/lateral_earth_pressure`
- Discipline: `ground`
- Category: `retaining-walls`
- Tool mode: `both`
- Standards: Rankine (1857); Coulomb (1776)
- Tags: geotechnical; earth-pressure; retaining-wall; deterministic

## Current Task Shape

Calculates active and passive earth pressure coefficients, base pressures, and total lateral forces on retaining walls using either Rankine or Coulomb theory. Supports inclined backfill, wall friction, cohesive soils, and uniform surcharge loading, computing the pressure distribution, total force per unit wall length, and the point of application for structural design of retaining structures.

## Existing Deterministic Contract

- Parameters: `8`
- Outputs: `7`
- Archetypes: `5`
- Visibility mix: all_given; partial
- Hidden parameters: `cohesion_kpa`, `friction_angle_deg`, `unit_weight_kn_m3`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `friction_angle_deg` | Effective friction angle φ' | float / degrees | range=0..45; derivable_from=archetype |
| `cohesion_kpa` | Effective cohesion c' | float / kPa | range=0..100; derivable_from=archetype |
| `unit_weight_kn_m3` | Soil unit weight γ | float / kN/m³ | range=14..22; derivable_from=archetype |
| `wall_height_m` | Retaining wall height H | float / m | range=1.5..12.0 |
| `backfill_slope_deg` | Backfill slope angle β above horizontal | float / degrees | range=0..30 |
| `wall_friction_angle_deg` | Wall friction angle δ (Coulomb theory) | float / degrees | range=0..30 |
| `surcharge_kpa` | Uniform surcharge on backfill surface q | float / kPa | range=0..50 |
| `theory` | Earth pressure theory to apply | enum | values=rankine, coulomb |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `ka` | Active earth pressure coefficient Ka |  | tolerance=0.03 |
| `kp` | Passive earth pressure coefficient Kp |  | tolerance=0.03 |
| `active_pressure_at_base_kpa` | Active pressure at base of wall σ_a (kPa) |  | tolerance=0.03 |
| `passive_pressure_at_base_kpa` | Passive pressure at base of wall σ_p (kPa) |  | tolerance=0.03 |
| `total_active_force_kn_m` | Total active force per unit wall length Pa (kN/m) |  | tolerance=0.03 |
| `total_passive_force_kn_m` | Total passive force per unit wall length Pp (kN/m) |  | tolerance=0.03 |
| `active_force_application_point_m` | Active force point of application above base (m) |  | tolerance=0.05 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `loose_sand` | Loose sand backfill | perth-coastal; hunter-valley-alluvial |
| `medium_dense_sand` | Medium dense sand backfill | sydney-harbour; brisbane-river |
| `dense_sand_gravel` | Dense sand and gravel backfill | cairns-coral; adelaide-quarry |
| `stiff_clay` | Stiff clay backfill | melbourne-basalt; sydney-hawkesbury |
| `soft_clay` | Soft normally consolidated clay | darwin-estuarine; brisbane-alluvial |

### Difficulty Notes

```text
easy: all_given | Rankine theory, horizontal backfill, cohesionless soil, no surcharge
medium: all_given | Rankine with inclined backfill or cohesive soil, surcharge may be present
hard: partial | hidden=cohesion_kpa, friction_angle_deg, unit_weight_kn_m3 | Coulomb theory with wall friction, some soil parameters hidden
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
