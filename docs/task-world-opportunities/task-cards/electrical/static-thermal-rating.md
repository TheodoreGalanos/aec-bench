# ABOUTME: First-pass task-world opportunity card for static-thermal-rating.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / thermal-rating / static-thermal-rating

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/static_thermal_rating`
- Discipline: `electrical`
- Category: `thermal-rating`
- Tool mode: `with-tool`
- Standards: IEEE 738; CIGRE TB 601
- Tags: electrical; thermal-rating; ampacity; overhead-conductor; deterministic

## Current Task Shape

Determines the continuous current-carrying capacity (ampacity) of bare overhead conductors by solving the IEEE 738 steady-state heat balance equation: convective and radiative cooling must equal solar heat gain plus ohmic heating. Accounts for wind speed, solar radiation, conductor emissivity, and temperature-dependent air properties to rate transmission and distribution lines.

## Existing Deterministic Contract

- Parameters: `9`
- Outputs: `4`
- Archetypes: `3`
- Visibility mix: all_given; partial
- Hidden parameters: `absorptivity`, `emissivity`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `conductor_diameter_mm` | Outer diameter of the bare overhead conductor | float / mm | range=5.0..50.0 |
| `conductor_resistance_ohm_per_km` | AC resistance of conductor at 25 deg C | float / ohm/km | range=0.02..1.5 |
| `max_conductor_temp_c` | Maximum allowable conductor operating temperature | float / deg C | range=50.0..150.0 |
| `ambient_temp_c` | Ambient air temperature | float / deg C | range=-10.0..50.0 |
| `wind_speed_m_s` | Wind speed perpendicular component | float / m/s | range=0.0..15.0 |
| `wind_angle_deg` | Angle between wind direction and conductor axis (0 = parallel, 90 = perpendicular) | float / deg | range=0.0..90.0 |
| `solar_radiation_w_m2` | Total solar radiation intensity on surface normal to conductor | float / W/m2 | range=0.0..1200.0 |
| `emissivity` | Conductor surface emissivity (0 = shiny new, 1 = fully weathered) | float | range=0.2..0.9; derivable_from=archetype |
| `absorptivity` | Conductor surface solar absorptivity (0 = fully reflective, 1 = fully absorbing) | float | range=0.2..0.9; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `convective_cooling_w_m` | Convective heat loss per unit length (W/m) |  | tolerance=0.05 |
| `radiative_cooling_w_m` | Radiative heat loss per unit length (W/m) |  | tolerance=0.05 |
| `solar_heat_gain_w_m` | Solar heat gain per unit length (W/m) |  | tolerance=0.05 |
| `ampacity_a` | Steady-state ampacity (A) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `light_distribution` | Light distribution line with small new ACSR conductor (recently strung, minimal weathering) | regional-australia; rural-new-zealand |
| `medium_subtransmission` | Subtransmission line with medium ACSR conductor aged in service (10+ years weathered surface) | sydney-western-corridor; melbourne-northern-ring |
| `heavy_transmission` | High-voltage transmission line with large ACSR conductor aged in service (10+ years weathered surface) | hunter-valley-transmission; queensland-powerlink |

### Difficulty Notes

```text
easy: all_given | Low wind, no solar, all params given including emissivity and absorptivity
medium: all_given | Full weather conditions, all params given
hard: partial | hidden=emissivity, absorptivity | Emissivity and absorptivity hidden, agent must infer from conductor age and conditions
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `time-series`.

Use single-line diagrams, layouts, device schedules, demand profiles, and equipment datasheets.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`, `source_timeseries`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
