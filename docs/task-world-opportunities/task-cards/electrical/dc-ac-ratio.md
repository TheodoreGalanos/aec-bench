# ABOUTME: First-pass task-world opportunity card for dc-ac-ratio.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / solar-pv-design / dc-ac-ratio

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/dc_ac_ratio`
- Discipline: `electrical`
- Category: `solar-pv-design`
- Tool mode: `with-tool`
- Standards: IEC 62548; AS/NZS 5033
- Tags: electrical; solar; pv; inverter; dc-ac-ratio; clipping; energy-yield

## Current Task Shape

Calculates the DC/AC ratio (inverter loading ratio) for solar PV systems and estimates annual energy yield accounting for system losses, inverter efficiency, and clipping losses from inverter overloading. Uses a quadratic clipping model to balance higher array utilisation against peak-hour energy curtailment, per IEC 62548 and AS/NZS 5033.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `annual_psh`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `dc_array_capacity_kwp` | Total PV array DC power capacity at STC | float / kWp | range=5..10000 |
| `inverter_ac_capacity_kw` | Total inverter AC power capacity (nameplate rating) | float / kW | range=3..8000 |
| `annual_psh` | Annual peak sun hours for the site location | float / h | range=800..2600; derivable_from=archetype |
| `system_losses_pct` | Total system losses excluding clipping (soiling, wiring, mismatch, temperature) | float / % | range=5..25 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `dc_ac_ratio` | DC/AC ratio (Inverter Loading Ratio) |  | tolerance=0.01 |
| `estimated_clipping_loss_pct` | Estimated annual clipping loss (%) |  | tolerance=0.05 |
| `annual_energy_yield_kwh` | Estimated annual energy yield (kWh) |  | tolerance=0.03 |
| `specific_yield_kwh_per_kwp` | Specific yield (kWh per kWp installed) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_rooftop` | Residential rooftop solar installation | sydney-suburban; brisbane-suburban; adelaide-suburban |
| `commercial_rooftop` | Commercial rooftop solar installation in Melbourne/Sydney (BOM avg 1400-1600 PSH) | melbourne-commercial; perth-commercial; sydney-commercial |
| `utility_scale` | Utility-scale ground-mounted solar farm in North Queensland (BOM avg 1800-2100 PSH) | north-queensland-solar-farm; western-nsw-solar-farm; pilbara-solar-farm |
| `arid_high_irradiance` | Solar installation in arid high-irradiance region near Alice Springs/Broken Hill (BOM avg 2200-2500 PSH) | alice-springs-solar; broken-hill-solar; longreach-solar |

### Difficulty Notes

```text
easy: all_given | Residential scale, all parameters given, moderate ILR
medium: all_given | Commercial or utility scale, all parameters given, wider ILR range
hard: partial | hidden=annual_psh | Peak sun hours hidden, agent must infer from site location context
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
