# ABOUTME: First-pass task-world opportunity card for npsh-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / pump-station / npsh-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/npsh_calculation`
- Discipline: `civil`
- Category: `pump-station`
- Tool mode: `with-tool`
- Standards: Hydraulics Institute; ANSI/HI 9.6.1
- Tags: civil; pump-station; npsh; cavitation; suction-head; deterministic

## Current Task Shape

Calculates the Net Positive Suction Head Available (NPSHa) at a pump inlet from atmospheric pressure, vapour pressure, static suction head, and friction losses using the Hydraulics Institute formula NPSHa = (P_atm - P_vap)/(rho*g) + h_s - h_f. Determines the NPSH margin and margin ratio against the pump's required NPSHr to verify cavitation-free operation per ANSI/HI 9.6.1.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `specific_gravity`, `vapour_pressure_kpa`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `atmospheric_pressure_kpa` | Atmospheric pressure at the site elevation | float / kPa | range=70.0..101.325 |
| `vapour_pressure_kpa` | Vapour pressure of the fluid at pumping temperature | float / kPa | range=0.6..50.0; derivable_from=archetype |
| `specific_gravity` | Specific gravity of the fluid relative to water | float / - | range=0.8..1.3; derivable_from=archetype |
| `static_suction_head_m` | Static suction head (positive = pump below liquid surface, negative = pump above) | float / m | range=-8.0..15.0 |
| `friction_loss_m` | Total friction losses in the suction piping | float / m | range=0.1..5.0 |
| `npsh_required_m` | NPSH required by the pump (from manufacturer data) | float / m | range=1.0..12.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pressure_head_m` | Net pressure head contribution (P_atm - P_vap) / (rho * g) (m) |  | tolerance=0.03 |
| `npsh_available_m` | Net Positive Suction Head Available NPSHa (m) |  | tolerance=0.03 |
| `npsh_margin_m` | NPSH margin: NPSHa - NPSHr (m) |  | tolerance=0.03 |
| `npsh_margin_ratio` | NPSH margin ratio: NPSHa / NPSHr (dimensionless) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `wet_well_flooded` | Wet well pump station with flooded suction (submersible or dry-pit pump below water level) | brisbane-sewage-wet-well; sydney-stormwater-wet-well |
| `dry_well_suction_lift` | Dry well pump station with suction lift (pump above liquid level, negative suction head) | melbourne-dry-well-sps; adelaide-dry-well-transfer |
| `elevated_tank_feed` | Pump fed from elevated storage tank with generous static head and long suction pipe | perth-hilltop-reservoir; darwin-elevated-tank |
| `high_temp_process` | High-temperature industrial process pump handling warm fluid with elevated vapour pressure | gladstone-process-plant; kwinana-industrial-pump |

### Difficulty Notes

```text
easy: all_given | All parameters given, flooded suction or elevated tank with comfortable NPSH margin
medium: all_given | All parameters given, any suction arrangement including suction lift and high-temperature
hard: partial | hidden=vapour_pressure_kpa, specific_gravity | Vapour pressure and specific gravity hidden, agent must infer from fluid type and temperature
```

## Multimodal Expansion

Candidate modality families: `chart-curve`, `drawing-geometry`, `tabular-source`.

Use pump curves, system schematics, hydrant flow tests, pipe schedules, and fire-service drawings.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Hydraulic duty points can feed pump power, motor sizing, NPSH, backup power, and transient checks.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`, `source_curve`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
