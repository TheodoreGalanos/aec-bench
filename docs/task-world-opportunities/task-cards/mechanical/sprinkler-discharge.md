# ABOUTME: First-pass task-world opportunity card for sprinkler-discharge.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / sprinkler-hydraulics / sprinkler-discharge

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/sprinkler_discharge`
- Discipline: `mechanical`
- Category: `sprinkler-hydraulics`
- Tool mode: `with-tool`
- Standards: NFPA 13; AS 2118.1
- Tags: mechanical; fire-services; sprinkler; discharge; deterministic

## Current Task Shape

Calculates sprinkler discharge from an explicit K factor and operating pressure using Q = K sqrt(P). The template reports flow in L/min and L/s plus operating pressure in kPa.

## Existing Deterministic Contract

- Parameters: `2`
- Outputs: `3`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `k_factor_l_min_sqrt_bar` | Sprinkler K factor | float / L/min/sqrt(bar) | range=10.0..400.0 |
| `pressure_bar` | Operating pressure at the sprinkler | float / bar | range=0.1..20.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `discharge_l_min` | Sprinkler discharge |  | tolerance=0.03 |
| `discharge_l_s` | Sprinkler discharge in litres per second |  | tolerance=0.03 |
| `pressure_kpa` | Operating pressure in kilopascals |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `standard_spray` | Standard spray sprinkler discharge check | commercial-sprinkler-zone; standard-spray-head |
| `large_drop` | Large drop or high-flow sprinkler discharge check | warehouse-sprinkler-zone; large-drop-head |

### Difficulty Notes

```text
easy: all_given | All parameters given for standard spray sprinklers
medium: all_given | All parameters given across sprinkler types
hard: all_given | All parameters given for high-flow sprinklers
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
