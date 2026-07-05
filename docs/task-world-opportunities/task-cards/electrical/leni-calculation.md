# ABOUTME: First-pass task-world opportunity card for leni-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / energy-performance / leni-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/leni_calculation`
- Discipline: `electrical`
- Category: `energy-performance`
- Tool mode: `with-tool`
- Standards: EN 15193-1
- Tags: electrical; lighting; interior-lighting; leni; energy; deterministic

## Current Task Shape

Calculates annual lighting energy, Lighting Energy Numeric Indicator, and percentage saving against a reference LENI for an interior lighting zone.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `daylight_factor`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `installed_lighting_power_w` | Installed lighting power in the zone | float / W | range=100..200000 |
| `annual_operating_hours` | Annual lighting operating hours | float / h/year | range=100..8760 |
| `control_factor` | Lighting control factor | float / - | range=0..1 |
| `daylight_factor` | Daylight availability factor | float / - | range=0..1 |
| `zone_area_m2` | Interior lighting zone area | float / m2 | range=10..50000 |
| `reference_leni_kwh_m2_year` | Reference LENI used for comparison | float / kWh/m2/year | range=1..100 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `annual_lighting_energy_kwh` | Annual lighting energy consumption |  | tolerance=0.03 |
| `leni_kwh_m2_year` | Lighting Energy Numeric Indicator |  | tolerance=0.03 |
| `reference_saving_pct` | Percentage saving against the reference LENI |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `office_zone` | Open office lighting zone | office-floor; workplace-lighting |
| `healthcare_zone` | Healthcare interior lighting zone | healthcare; clinical-lighting |

### Difficulty Notes

```text
easy: all_given | Office zone with all values visible
medium: all_given | Interior lighting zone selected from office or healthcare cases
hard: partial | hidden=daylight_factor | Healthcare zone with daylight factor embedded in context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `spatial-map`.

Use layout plans, device schedules, coverage diagrams, timing tables, and network topology artifacts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Communications and ITS tasks combine through shared layouts, device counts, coverage, storage, and power constraints.

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
