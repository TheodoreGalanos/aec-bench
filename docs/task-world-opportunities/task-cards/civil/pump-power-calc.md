# ABOUTME: First-pass task-world opportunity card for pump-power-calc.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / pump-station / pump-power-calc

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/pump_power_calc`
- Discipline: `civil`
- Category: `pump-station`
- Tool mode: `with-tool`
- Standards: AWWA; Hydraulics Institute
- Tags: civil; pump-station; hydraulic-power; brake-power; motor-power; deterministic

## Current Task Shape

Calculates hydraulic power (P_h = rho*g*Q*H), brake (shaft) power, and motor input power for a water or wastewater pump station at a specified duty point. Accounts for pump and motor efficiencies to determine the electrical power draw, following AWWA and Hydraulics Institute methodology for pump station design.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `3`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `motor_efficiency_pct`, `pump_efficiency_pct`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_l_s` | Volumetric flow rate Q at the duty point | float / L/s | range=1.0..500.0 |
| `total_dynamic_head_m` | Total dynamic head H (static head plus friction losses) | float / m | range=2.0..120.0 |
| `pump_efficiency_pct` | Pump efficiency at the duty point | float / % | range=40.0..90.0; derivable_from=archetype |
| `motor_efficiency_pct` | Motor efficiency at the operating load | float / % | range=80.0..97.0; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `hydraulic_power_kw` | Hydraulic (water) power P_h (kW) |  | tolerance=0.03 |
| `brake_power_kw` | Brake (shaft) power P_b (kW) |  | tolerance=0.03 |
| `motor_input_power_kw` | Motor input (electrical) power P_m (kW) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_sewer_lift` | Small sewage lift station with submersible pump | brisbane-suburban-sps; gold-coast-residential-sps |
| `medium_water_booster` | Medium water supply booster station with end-suction centrifugal pump | sydney-distribution-booster; melbourne-zone-booster |
| `large_trunk_transfer` | Large trunk sewage or water transfer station with split-case pump | adelaide-trunk-transfer; perth-trunk-main |
| `high_head_raw_water` | High-head raw water intake pump station with multi-stage pump | darwin-raw-water-intake; cairns-hillside-reservoir |

### Difficulty Notes

```text
easy: all_given | All parameters given, small to medium pump station
medium: all_given | All parameters given, any pump station type including high head
hard: partial | hidden=pump_efficiency_pct, motor_efficiency_pct | Efficiencies hidden, agent must infer from pump station type and size
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `chart-curve`.

Use network schematics, long sections, asset schedules, rating curves, and source tables.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Pipe and channel outputs naturally feed pump station, detention, outfall, and flood-level checks.

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
