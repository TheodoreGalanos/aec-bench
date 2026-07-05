# ABOUTME: First-pass task-world opportunity card for hazen-williams-headloss.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / pipe-hydraulics / hazen-williams-headloss

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/hazen_williams_headloss`
- Discipline: `civil`
- Category: `pipe-hydraulics`
- Tool mode: `with-tool`
- Standards: AWWA; AS/NZS 3500
- Tags: civil; pipe-hydraulics; head-loss; hazen-williams; deterministic

## Current Task Shape

Calculates friction head loss in pressurised water mains using the Hazen-Williams empirical formula hf = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87), along with the hydraulic gradient and flow velocity. The C-factor encodes pipe material and condition. Widely used in municipal water distribution design per AWWA and AS/NZS 3500 for sizing pipes and evaluating network pressure losses.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `3`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `c_factor`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_rate_l_s` | Volumetric flow rate Q | float / L/s | range=0.5..500.0 |
| `pipe_diameter_mm` | Internal pipe diameter D | float / mm | range=50..2000 |
| `pipe_length_m` | Pipe length L | float / m | range=10..5000 |
| `c_factor` | Hazen-Williams roughness coefficient C | float | range=60..150; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `head_loss_m` | Friction head loss hf (m) |  | tolerance=0.03 |
| `hydraulic_gradient` | Hydraulic gradient S = hf / L (dimensionless) |  | tolerance=0.05 |
| `flow_velocity_m_s` | Mean flow velocity V (m/s) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `new_pvc` | New PVC or HDPE pipeline | sydney-greenfield; brisbane-suburban |
| `new_ductile_iron` | New cement-lined ductile iron pipeline | melbourne-trunk-main; adelaide-distribution |
| `aged_cast_iron` | Aged unlined cast iron pipeline with moderate tuberculation | sydney-inner-west-legacy; melbourne-inner-legacy |
| `corroded_steel` | Corroded steel water main | darwin-industrial-reticulation; cairns-coastal-reticulation |

### Difficulty Notes

```text
easy: all_given | All parameters given, smooth new pipe, moderate flow
medium: all_given | All parameters given, any pipe material and flow regime
hard: partial | hidden=c_factor | C-factor hidden, agent must infer from pipe material description
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

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`, `source_curve`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
