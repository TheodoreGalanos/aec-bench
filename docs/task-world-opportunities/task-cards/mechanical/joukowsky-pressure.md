# ABOUTME: First-pass task-world opportunity card for joukowsky-pressure.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / transient-analysis / joukowsky-pressure

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/joukowsky_pressure`
- Discipline: `mechanical`
- Category: `transient-analysis`
- Tool mode: `with-tool`
- Standards: AWWA M11
- Tags: mechanical; water-hammer; joukowsky; pressure-rise; deterministic

## Current Task Shape

Calculates transient pressure rise using the Joukowsky equation from fluid density, pressure wave speed, and velocity change. The template reports the pressure rise in pascals and kilopascals and the equivalent pressure head in metres.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `fluid_density_kg_m3` | Fluid density rho | float / kg/m3 | range=700.0..1300.0 |
| `wave_speed_m_s` | Pressure wave speed a | float / m/s | range=100.0..1500.0 |
| `velocity_change_m_s` | Magnitude of velocity change | float / m/s | range=0.01..5.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `pressure_rise_pa` | Joukowsky pressure rise |  | tolerance=0.03 |
| `pressure_rise_kpa` | Joukowsky pressure rise |  | tolerance=0.03 |
| `pressure_head_m` | Equivalent pressure rise head |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `steel_water_main` | Stiff water main with high pressure wave speed | trunk-water-main; raw-water-pipeline |
| `flexible_rising_main` | Flexible rising main with lower pressure wave speed | sewer-rising-main; irrigation-transfer-line |

### Difficulty Notes

```text
easy: all_given | All parameters given for a stiff water main
medium: all_given | All parameters given across stiff and flexible water mains
hard: all_given | All parameters given for larger transient velocity changes
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
