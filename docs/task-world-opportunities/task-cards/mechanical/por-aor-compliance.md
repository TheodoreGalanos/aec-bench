# ABOUTME: First-pass task-world opportunity card for por-aor-compliance.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / system-curves / por-aor-compliance

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/por_aor_compliance`
- Discipline: `mechanical`
- Category: `system-curves`
- Tool mode: `with-tool`
- Standards: HI 9.6.3
- Tags: mechanical; pump; operating-range; por; aor; deterministic

## Current Task Shape

Checks pump operating flow against explicit preferred and allowable operating range ratios relative to best efficiency point flow. The template reports flow ratio, POR margins, and numeric POR/AOR flags.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `operating_flow_l_s` | Pump operating flow | float / L/s | range=0.0..100000.0 |
| `best_efficiency_flow_l_s` | Best efficiency point flow | float / L/s | range=0.1..100000.0 |
| `por_min_ratio` | Minimum preferred operating range ratio | float / - | range=0.0..2.0 |
| `por_max_ratio` | Maximum preferred operating range ratio | float / - | range=0.0..3.0 |
| `aor_min_ratio` | Minimum allowable operating range ratio | float / - | range=0.0..2.0 |
| `aor_max_ratio` | Maximum allowable operating range ratio | float / - | range=0.0..3.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `flow_ratio` | Operating flow divided by best efficiency point flow |  | tolerance=0.03 |
| `por_margin_low` | Margin above lower preferred operating range limit |  | tolerance=0.03 |
| `por_margin_high` | Margin below upper preferred operating range limit |  | tolerance=0.03 |
| `within_por` | Numeric flag where 1 means operating flow is inside POR |  | tolerance=0.01 |
| `within_aor` | Numeric flag where 1 means operating flow is inside AOR |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `water_pump` | Water pump operating range check | water-pump-station; transfer-pump |
| `process_pump` | Process pump operating range check | process-plant; chemical-transfer |

### Difficulty Notes

```text
easy: all_given | All parameters given for a water pump
medium: all_given | All parameters given across pump services
hard: all_given | All parameters given for process pump range checks
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `spatial-map`, `tabular-source`.

Use alignment drawings, chainage tables, long sections, route maps, and design-speed schedules.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Alignment geometry can feed sight-distance, cant/superelevation, vertical-curve, and comfort checks.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `source_geometry`, `source_table`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
