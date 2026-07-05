# ABOUTME: First-pass task-world opportunity card for immediate-settlement.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# ground / shallow-foundations / immediate-settlement

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/ground/immediate_settlement`
- Discipline: `ground`
- Category: `shallow-foundations`
- Tool mode: `with-tool`
- Standards: Bowles (1996); Boussinesq elastic theory
- Tags: geotechnical; settlement; elastic; immediate; deterministic

## Current Task Shape

Calculates the elastic (immediate) settlement of shallow foundations using the Boussinesq equation Si = q*B*(1-nu^2)/E * If, where the influence factor If depends on footing shape and L/B ratio per Bowles (1996) Table 5-6. Supports square, rectangular, and circular footings with flexible or rigid foundation corrections for settlement prediction in granular and stiff cohesive soils.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `2`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `elastic_modulus_mpa`, `poisson_ratio`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `applied_pressure_kpa` | Net applied foundation pressure q | float / kPa | range=25..500 |
| `footing_width_m` | Footing width B (shorter dimension) | float / m | range=0.5..10.0 |
| `footing_length_m` | Footing length L (longer dimension, L >= B) | float / m | range=0.5..30.0 |
| `elastic_modulus_mpa` | Soil elastic modulus E | float / MPa | range=2..200; derivable_from=archetype |
| `poisson_ratio` | Soil Poisson's ratio nu | float | range=0.15..0.49; derivable_from=archetype |
| `footing_shape` | Footing shape | enum | values=square, rectangular, circular |
| `foundation_rigidity` | Foundation rigidity | enum | values=flexible, rigid |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `influence_factor` | Settlement influence factor I_f |  | tolerance=0.05 |
| `settlement_mm` | Immediate elastic settlement Si (mm) |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `loose_sand` | Loose to medium sand | perth-coastal; gold-coast-sand |
| `dense_sand` | Dense sand and gravel | hunter-valley-alluvial; newcastle-fill |
| `stiff_clay` | Stiff overconsolidated clay | sydney-hawkesbury; melbourne-basalt; adelaide-stiff |
| `soft_clay` | Soft normally consolidated clay | brisbane-alluvial; darwin-estuarine |

### Difficulty Notes

```text
easy: all_given | Square flexible footing, all parameters given
medium: all_given | Any shape and rigidity, all parameters given
hard: partial | hidden=elastic_modulus_mpa, poisson_ratio | Soil properties hidden, agent must estimate E and nu from site description
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `document-evidence`.

Use borehole logs, lab tables, slope sections, retaining-wall sketches, and geotechnical notes.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Ground parameters can feed retaining-wall, foundation, slope-stability, and structural load checks.

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
