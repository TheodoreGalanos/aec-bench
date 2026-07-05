# ABOUTME: First-pass task-world opportunity card for fos-rapid-drawdown.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / slope-stability / fos-rapid-drawdown

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/fos_rapid_drawdown`
- Discipline: `civil`
- Category: `slope-stability`
- Tool mode: `with-tool`
- Standards: USACE EM 1110-2-1902
- Tags: civil; dams; slope-stability; drawdown; geotechnical; embankment

## Current Task Shape

Computes the factor of safety before and after rapid reservoir drawdown on an embankment dam upstream slope using the simplified infinite slope method per USACE EM 1110-2-1902. Assumes undrained pore-pressure response in low-permeability core materials, comparing the submerged steady-state condition to the post-drawdown condition where full saturated weight drives shear but pore pressures remain elevated.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `cohesion_kpa`, `friction_angle_deg`, `saturated_unit_weight_kn_m3`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `slope_angle_deg` | Upstream slope angle measured from horizontal | float / degrees | range=5.0..45.0 |
| `slip_depth_m` | Depth of potential slip surface below the slope face | float / m | range=0.5..10.0 |
| `cohesion_kpa` | Effective cohesion c' of the embankment material | float / kPa | range=0.0..50.0; derivable_from=archetype |
| `friction_angle_deg` | Effective friction angle phi' of the embankment material | float / degrees | range=10.0..40.0; derivable_from=archetype |
| `saturated_unit_weight_kn_m3` | Saturated unit weight of the embankment material gamma_sat | float / kN/m3 | range=16.0..22.0; derivable_from=archetype |
| `initial_reservoir_level_m` | Initial (pre-drawdown) reservoir water level above the dam base | float / m | range=3.0..80.0 |
| `final_reservoir_level_m` | Final (post-drawdown) reservoir water level above the dam base | float / m | range=0.0..40.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `fos_before_drawdown` | Factor of safety of the upstream slope before drawdown (submerged steady state) |  | tolerance=0.03 |
| `fos_after_drawdown` | Factor of safety of the upstream slope after rapid drawdown (undrained pore pressures) |  | tolerance=0.03 |
| `drawdown_ratio` | Drawdown ratio R = (initial_level - final_level) / initial_level (dimensionless) |  | tolerance=0.03 |
| `pore_pressure_kpa` | Undrained pore pressure at the slip surface after drawdown u (kPa) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `homogeneous_earth_dam` | Homogeneous compacted clay embankment dam with moderate upstream slope | queensland-irrigation-dam; darling-downs-farm-dam |
| `zoned_embankment` | Zoned embankment dam with clay core and granular shells on upstream slope | snowy-mountains-hydro-dam; tasmania-power-dam |
| `tailings_dam` | Mining tailings storage facility with upstream-raise embankment | pilbara-iron-ore-tsf; bowen-basin-coal-tsf |
| `flood_levee` | Flood protection levee with steep upstream face on alluvial foundation | murray-river-levee; fitzroy-river-flood-levee |

### Difficulty Notes

```text
easy: all_given | Homogeneous dam scenario, all parameters given including material properties
medium: all_given | All parameters given, wider range of dam types and operating conditions
hard: partial | hidden=cohesion_kpa, friction_angle_deg, saturated_unit_weight_kn_m3 | Material properties hidden; agent must infer cohesion, friction angle, and unit weight from site context
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
