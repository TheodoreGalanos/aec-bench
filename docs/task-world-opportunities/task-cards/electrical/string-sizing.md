# ABOUTME: First-pass task-world opportunity card for string-sizing.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / solar-pv-design / string-sizing

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/string_sizing`
- Discipline: `electrical`
- Category: `solar-pv-design`
- Tool mode: `both`
- Standards: AS/NZS 5033; IEC 62548
- Tags: electrical; solar; pv; string-sizing; temperature-correction; deterministic

## Current Task Shape

Calculates the maximum and minimum number of PV modules per string by applying temperature coefficients to open-circuit and maximum-power-point voltages at site extremes, per AS/NZS 5033 and IEC 62548. Cold-corrected Voc must not exceed the inverter maximum DC voltage, and hot-corrected Vmp must remain above the inverter minimum MPPT tracking voltage.

## Existing Deterministic Contract

- Parameters: `9`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `site_max_temp_c`, `site_min_temp_c`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `voc_stc_v` | PV module open-circuit voltage at STC (25 degC, 1000 W/m2) | float / V | range=20.0..60.0 |
| `vmp_stc_v` | PV module maximum power point voltage at STC | float / V | range=15.0..55.0 |
| `temp_coeff_voc_pct_per_c` | Temperature coefficient of Voc (negative value) | float / %/degC | range=-0.45..-0.2 |
| `temp_coeff_vmp_pct_per_c` | Temperature coefficient of Vmp (negative value) | float / %/degC | range=-0.5..-0.25 |
| `site_min_temp_c` | Site minimum ambient temperature | float / degC | range=-10.0..10.0; derivable_from=archetype |
| `site_max_temp_c` | Site maximum ambient temperature | float / degC | range=30.0..50.0; derivable_from=archetype |
| `inverter_max_dc_voltage_v` | Inverter maximum DC input voltage | float / V | range=450.0..1500.0 |
| `inverter_min_mppt_voltage_v` | Inverter minimum MPPT tracking voltage | float / V | range=100.0..500.0 |
| `inverter_nominal_mppt_voltage_v` | Inverter nominal (midpoint) MPPT voltage | float / V | range=200.0..900.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `voc_corrected_cold_v` | Temperature-corrected Voc at site minimum temperature (V) |  | tolerance=0.03 |
| `vmp_corrected_hot_v` | Temperature-corrected Vmp at site maximum temperature (V) |  | tolerance=0.03 |
| `max_modules_per_string` | Maximum number of modules per string (integer, rounded down) |  | tolerance=0.01 |
| `min_modules_per_string` | Minimum number of modules per string (integer, rounded up) |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `residential_mono_perc` | Residential rooftop monocrystalline PERC module (~400 W) | sydney-suburban-rooftop; melbourne-suburban-rooftop; brisbane-suburban-rooftop |
| `commercial_bifacial` | Commercial bifacial monocrystalline module (~550 W) in Sydney/Melbourne temperate climate | sydney-commercial-rooftop; perth-commercial-rooftop |
| `utility_scale_hjt` | Utility-scale heterojunction (HJT) module (~600 W) in arid inland Australia (Alice Springs/Broken Hill climate) | western-nsw-ground-mount; queensland-ground-mount; south-australia-ground-mount |
| `thin_film_cdte` | Thin-film cadmium telluride (CdTe) module (~450 W) in tropical northern Australia (Darwin/Cairns climate) | darwin-commercial-rooftop; townsville-ground-mount |

### Difficulty Notes

```text
easy: all_given | All parameters given, residential module with small inverter
medium: all_given | All parameters given, any module type and larger inverters
hard: partial | hidden=site_min_temp_c, site_max_temp_c | Site temperatures hidden, agent infers from location context
```

## Multimodal Expansion

Candidate modality families: `tabular-source`, `time-series`, `drawing-geometry`.

Use single-line diagrams, load schedules, demand profiles, equipment datasheets, and cable schedules.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Electrical sizing tasks can compose with renewable generation, storage, protection, and backup-power worlds.

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
