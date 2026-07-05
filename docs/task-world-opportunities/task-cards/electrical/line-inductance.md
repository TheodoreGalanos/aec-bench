# ABOUTME: First-pass task-world opportunity card for line-inductance.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / electrical-parameters / line-inductance

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/line_inductance`
- Discipline: `electrical`
- Category: `electrical-parameters`
- Tool mode: `with-tool`
- Standards: IEC 60909; IEEE 738
- Tags: electrical; line-inductance; gmd; gmr; transmission-lines; deterministic

## Current Task Shape

Calculates per-phase line inductance for a reduced transposed three-phase overhead line model. The template computes geometric mean distance from phase spacings, equivalent GMR for simple bundled conductors, and inductance using L = 0.2 ln(GMD/GMR) mH/km.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `3`
- Archetypes: `3`
- Visibility mix: all_given; partial
- Hidden parameters: `bundle_count`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `conductor_gmr_m` | Geometric mean radius of one subconductor | float / m | range=0.001..0.05 |
| `phase_spacing_ab_m` | Spacing between phase A and phase B | float / m | range=0.2..20 |
| `phase_spacing_bc_m` | Spacing between phase B and phase C | float / m | range=0.2..20 |
| `phase_spacing_ca_m` | Spacing between phase C and phase A | float / m | range=0.2..40 |
| `bundle_count` | Number of subconductors in each phase bundle | enum | values=single, two, three, four; derivable_from=archetype |
| `bundle_spacing_m` | Spacing between subconductors in the bundle | float / m | range=0.1..0.8 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `geometric_mean_distance_m` | Geometric mean distance between phases |  | tolerance=0.03 |
| `equivalent_gmr_mm` | Equivalent bundle GMR |  | tolerance=0.05 |
| `inductance_mh_per_km` | Per-phase inductance per kilometre |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `distribution_single` | Single-conductor distribution line | urban-distribution; rural-feeder |
| `transmission_single` | Single-conductor transmission line | 132kv-overhead; 220kv-overhead |
| `bundled_transmission` | Bundled high-voltage transmission line | 330kv-overhead; 500kv-overhead |

### Difficulty Notes

```text
easy: all_given | Single-conductor line with all dimensions given
medium: all_given | Single or two-conductor bundle
hard: partial | hidden=bundle_count | Bundle count inferred from transmission-line context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `time-series`.

Use single-line diagrams, layouts, device schedules, demand profiles, and equipment datasheets.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

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
