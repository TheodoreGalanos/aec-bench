# ABOUTME: First-pass task-world opportunity card for t-squared-hrr.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / design-fire / t-squared-hrr

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/t_squared_hrr`
- Discipline: `mechanical`
- Category: `design-fire`
- Tool mode: `with-tool`
- Standards: ISO/TS 16733; SFPE Handbook
- Tags: mechanical; fire-safety; design-fire; heat-release-rate; deterministic

## Current Task Shape

Calculates design fire heat release rate using the t-squared growth model HRR = alpha t^2, with an explicit peak HRR cap. The template reports the unclipped HRR, peak-limited HRR, time to peak, and a numeric cap indicator for deterministic fire safety scenario checks.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `4`
- Archetypes: `3`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `growth_coefficient_kw_s2` | T-squared fire growth coefficient alpha | float / kW/s^2 | range=0.001..0.2 |
| `time_from_ignition_s` | Time from ignition | float / s | range=0.0..1800.0 |
| `peak_hrr_kw` | Peak heat release rate cap | float / kW | range=100.0..20000.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `unclipped_hrr_kw` | Unclipped t-squared heat release rate |  | tolerance=0.03 |
| `hrr_at_time_kw` | Heat release rate at time after applying peak cap |  | tolerance=0.03 |
| `time_to_peak_s` | Time from ignition to reach peak HRR |  | tolerance=0.03 |
| `peak_limited` | Numeric peak-limit indicator: 0 no, 1 yes |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `slow_growth_fire` | Slow-growth design fire for low-combustibility occupancy | office-tenancy; station-concourse |
| `medium_growth_fire` | Medium-growth design fire for mixed fuel load occupancy | retail-tenancy; workshop-area |
| `fast_growth_fire` | Fast-growth design fire for high fuel load storage or plant areas | warehouse-storage; plant-room-fire |

### Difficulty Notes

```text
easy: all_given | All parameters given for a slow-growth design fire
medium: all_given | All parameters given across slow and medium growth fires
hard: all_given | All parameters given for faster growth or peak-limited fire scenarios
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `time-series`, `document-evidence`.

Use floor plans, zone schedules, smoke/temperature traces, occupant profiles, and scenario briefs.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Fire scenarios can combine egress, tenability, ventilation, sprinkler, and hydrant-flow worlds.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_timeseries`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
