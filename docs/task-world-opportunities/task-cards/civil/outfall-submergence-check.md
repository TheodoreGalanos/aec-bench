# ABOUTME: First-pass task-world opportunity card for outfall-submergence-check.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / outfall-hydraulics / outfall-submergence-check

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/outfall_submergence_check`
- Discipline: `civil`
- Category: `outfall-hydraulics`
- Tool mode: `both`
- Standards: MfE Coastal Hazards Guidance 2024; IPCC AR6 Sea Level Projections
- Tags: coastal; outfall; submergence; tidal; sea-level-rise; drainage

## Current Task Shape

Determines the percentage of time a stormwater or wastewater outfall is submerged by tidal waters under present-day conditions and a future sea level rise scenario. Uses a sinusoidal tide model h(t) = MSL + A sin(2 pi t / T) with a closed-form solution for the submerged fraction, then converts to hours per day. Applicable to coastal outfall feasibility assessments per MfE Coastal Hazards Guidance 2024 and Australian coastal design practice.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `5`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `tidal_period_hours`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `outfall_invert_level_m` | Outfall pipe invert level relative to datum (m AHD or m CD) | float / m AHD | range=-1.0..1.5 |
| `mean_sea_level_m` | Present-day mean sea level relative to datum | float / m AHD | range=-0.2..0.5 |
| `tidal_amplitude_m` | Tidal amplitude (half the spring tidal range), A = (HAT - LAT) / 2 | float / m | range=0.2..4.0 |
| `sea_level_rise_m` | Projected sea level rise for the design planning horizon | float / m | range=0.1..1.2 |
| `tidal_period_hours` | Tidal period (typically 12.42 hours for semi-diurnal M2 constituent) | float / hours | range=6.0..25.0; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `present_submergence_percent` | Percentage of time outfall is submerged under present-day conditions |  | tolerance=1.0 |
| `future_submergence_percent` | Percentage of time outfall is submerged under future sea level conditions |  | tolerance=1.0 |
| `present_hours_submerged_per_day` | Hours per day the outfall is submerged (present-day) |  | tolerance=0.25 |
| `future_hours_submerged_per_day` | Hours per day the outfall is submerged (future) |  | tolerance=0.25 |
| `submergence_increase_percent` | Absolute increase in submergence percentage from SLR |  | tolerance=1.0 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `micro_tidal_estuary` | Micro-tidal sheltered estuary with small tidal range (< 1 m amplitude) | sydney-harbour-estuary; auckland-waitemata-harbour; hobart-derwent-estuary |
| `meso_tidal_coast` | Meso-tidal open coast with moderate tidal range (1-2 m amplitude) | gold-coast-broadwater; wellington-harbour-outfall; newcastle-hunter-river |
| `macro_tidal_port` | Macro-tidal port or river mouth with large tidal range (> 2 m amplitude) | darwin-harbour-outfall; broome-roebuck-bay; gladstone-harbour-discharge |
| `diurnal_gulf` | Diurnal tidal regime with ~24 hour period (Gulf of Carpentaria type) | karumba-gulf-outfall; weipa-port-discharge; gove-peninsula-outfall |

### Difficulty Notes

```text
easy: all_given | Small tidal range, all parameters given — straightforward substitution into closed-form formula
medium: all_given | Larger tidal range with all parameters given — same formula, wider parameter spread
hard: partial | hidden=tidal_period_hours | Tidal period hidden — agent must recognise semi-diurnal or diurnal regime from site description
```

## Multimodal Expansion

Candidate modality families: `spatial-map`, `tabular-source`, `time-series`.

Use catchment plans, rainfall tables, hyetographs, and drainage schedules as source artifacts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Connect rainfall/runoff outputs to detention, pipe, HGL, outlet, and water-quality checks.

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
