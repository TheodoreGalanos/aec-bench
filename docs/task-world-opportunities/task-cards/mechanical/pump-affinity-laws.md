# ABOUTME: First-pass task-world opportunity card for pump-affinity-laws.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / pump-sizing / pump-affinity-laws

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/pump_affinity_laws`
- Discipline: `mechanical`
- Category: `pump-sizing`
- Tool mode: `with-tool`
- Standards: ANSI/HI Standards
- Tags: mechanical; pump-sizing; affinity-laws; variable-speed; deterministic

## Current Task Shape

Calculates the new flow rate, head, and power draw for the same pump operating at a different rotational speed. The template applies the standard pump affinity laws Q2 = Q1(N2/N1), H2 = H1(N2/N1)^2, and P2 = P1(N2/N1)^3 for deterministic variable-speed pump checks.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `4`
- Archetypes: `3`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `original_speed_rpm` | Original pump rotational speed N1 | float / rpm | range=500.0..3600.0 |
| `new_speed_rpm` | New pump rotational speed N2 | float / rpm | range=500.0..3600.0 |
| `original_flow_l_s` | Original pump flow rate Q1 | float / L/s | range=1.0..500.0 |
| `original_head_m` | Original pump total head H1 | float / m | range=2.0..150.0 |
| `original_power_kw` | Original pump power P1 | float / kW | range=0.5..1000.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `speed_ratio` | Speed ratio N2/N1 |  | tolerance=0.03 |
| `new_flow_l_s` | New flow rate Q2 |  | tolerance=0.03 |
| `new_head_m` | New total head H2 |  | tolerance=0.03 |
| `new_power_kw` | New pump power P2 |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_booster_speed_reduction` | Small booster pump slowed for low-demand operation | suburban-water-booster; building-services-transfer |
| `transfer_pump_speed_increase` | Transfer pump checked for a moderate speed increase | regional-water-transfer; industrial-process-transfer |
| `large_station_trim` | Large pump station trimmed to match a lower duty point | trunk-main-transfer; raw-water-intake |

### Difficulty Notes

```text
easy: all_given | All parameters given for a small speed reduction
medium: all_given | All parameters given across common pump operating scenarios
hard: all_given | All parameters given for larger pumps and wider speed changes
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

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_table`, `source_curve`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
