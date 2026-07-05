# ABOUTME: First-pass task-world opportunity card for visibility-criterion.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / tenability-assessment / visibility-criterion

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/visibility_criterion`
- Discipline: `mechanical`
- Category: `tenability-assessment`
- Tool mode: `with-tool`
- Standards: SFPE Handbook; ISO 13571
- Tags: mechanical; fire-safety; tenability; visibility; deterministic

## Current Task Shape

Calculates smoke visibility from extinction coefficient and an explicit visibility constant, then compares the result with a minimum visibility criterion. The template reports visibility, margin, utilisation, and a numeric criterion flag.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `extinction_coefficient_m_inv` | Smoke extinction coefficient | float / 1/m | range=0.001..10.0 |
| `visibility_constant` | Visibility constant for the target sign or object contrast | float / - | range=1.0..20.0 |
| `minimum_visibility_m` | Minimum acceptable visibility | float / m | range=0.1..100.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `visibility_m` | Calculated visibility |  | tolerance=0.03 |
| `visibility_margin_m` | Visibility margin above minimum criterion |  | tolerance=0.03 |
| `visibility_utilisation_ratio` | Minimum visibility divided by calculated visibility |  | tolerance=0.03 |
| `criterion_satisfied` | Numeric flag where 1 means visibility meets the criterion |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `egress_route` | Egress route smoke visibility check | egress-route; smoke-control-zone |
| `large_volume_space` | Large volume space smoke visibility check | atrium; station-concourse |

### Difficulty Notes

```text
easy: all_given | All parameters given for an egress route
medium: all_given | All parameters given across tenability settings
hard: all_given | All parameters given for large volume spaces
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
