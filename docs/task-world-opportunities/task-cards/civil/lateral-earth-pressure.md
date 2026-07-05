# ABOUTME: First-pass task-world opportunity card for lateral-earth-pressure.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / slope-stability / lateral-earth-pressure

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/lateral_earth_pressure`
- Discipline: `civil`
- Category: `slope-stability`
- Tool mode: `with-tool`
- Standards: AS 4678; Rankine (1857)
- Tags: civil; geotechnical; earth-pressure; retaining-wall; water-table; rankine

## Current Task Shape

Calculates active and passive earth pressure coefficients and resultant forces on retaining walls using Rankine theory per AS 4678. Handles two-zone pressure distribution when a water table is present, computing effective earth pressure above and below the water table plus hydrostatic thrust. Outputs include Ka, Kp, active and passive forces, overturning moment, and water force per unit wall length for stability assessment.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `6`
- Archetypes: `5`
- Visibility mix: all_given; partial
- Hidden parameters: `friction_angle_deg`, `unit_weight_kn_m3`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `wall_height_m` | Retaining wall height H | float / m | range=1.0..12.0 |
| `friction_angle_deg` | Effective friction angle of backfill soil phi' | float / degrees | range=15.0..45.0; derivable_from=archetype |
| `cohesion_kpa` | Effective cohesion of backfill soil c' | float / kPa | range=0.0..50.0; derivable_from=archetype |
| `unit_weight_kn_m3` | Total (bulk) unit weight of backfill soil gamma | float / kN/m3 | range=15.0..22.0; derivable_from=archetype |
| `surcharge_kpa` | Uniform surcharge pressure on the backfill surface q | float / kPa | range=0.0..30.0 |
| `water_table_depth_m` | Depth from ground surface to the water table behind the wall (equal to wall height means no water) | float / m | range=0.0..12.0 |
| `backfill_slope_deg` | Backfill slope angle beta above horizontal | float / degrees | range=0.0..25.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `ka` | Active earth pressure coefficient Ka (dimensionless) |  | tolerance=0.03 |
| `kp` | Passive earth pressure coefficient Kp (dimensionless) |  | tolerance=0.03 |
| `active_force_kn_per_m` | Total active earth pressure force per unit wall length Pa (kN/m) |  | tolerance=0.03 |
| `passive_force_kn_per_m` | Total passive earth pressure force per unit wall length Pp (kN/m) |  | tolerance=0.03 |
| `active_moment_knm_per_m` | Active overturning moment about the wall base Ma (kNm/m) |  | tolerance=0.03 |
| `water_force_kn_per_m` | Hydrostatic water force per unit wall length Pw (kN/m) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `loose_sand_dry` | Loose sand backfill, no water table | perth-coastal-retaining-wall; gold-coast-canal-wall |
| `medium_dense_sand_dry` | Medium dense sand backfill, no water table | sydney-harbour-foreshore-wall; brisbane-river-terrace |
| `dense_gravel_fill` | Dense gravel fill behind a cantilever wall | adelaide-quarry-haul-road; cairns-port-wharf-wall |
| `silty_sand_with_water` | Silty sand backfill with elevated water table | darwin-stormwater-channel-wall; townsville-coastal-revetment |
| `stiff_clay_fill` | Stiff clay backfill behind a gravity wall | melbourne-basalt-clay-wall; canberra-substation-retaining |

### Difficulty Notes

```text
easy: all_given | Cohesionless sand, no water table, no surcharge, horizontal backfill
medium: all_given | Surcharge and cohesion may be present, horizontal or sloping backfill, no water
hard: partial | hidden=friction_angle_deg, unit_weight_kn_m3 | Water table present, some soil parameters hidden; agent infers from site context
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
