# ABOUTME: First-pass task-world opportunity card for pfc-sizing.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / load-flow / pfc-sizing

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/pfc_sizing`
- Discipline: `electrical`
- Category: `load-flow`
- Tool mode: `with-tool`
- Standards: IEEE 3002.2; AS/NZS 2067
- Tags: electrical; power-factor; capacitor; reactive-power; load-flow; deterministic

## Current Task Shape

Calculates the reactive power compensation needed to improve a load from an initial lagging power factor to a target power factor. The reduced method uses Qc = P x (tan phi_initial - tan phi_target), then reports the corrected apparent power and current reduction.

## Existing Deterministic Contract

- Parameters: `3`
- Outputs: `4`
- Archetypes: `3`
- Visibility mix: all_given; partial
- Hidden parameters: `initial_power_factor`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `real_power_kw` | Real load power | float / kW | range=1..20000 |
| `initial_power_factor` | Initial lagging power factor | float | range=0.5..0.94 |
| `target_power_factor` | Target corrected power factor | float | range=0.9..0.99 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `initial_apparent_power_kva` | Initial apparent power |  | tolerance=0.03 |
| `corrected_apparent_power_kva` | Apparent power after correction |  | tolerance=0.03 |
| `required_reactive_power_kvar` | Required capacitor reactive power |  | tolerance=0.03 |
| `current_reduction_pct` | Reduction in line current at unchanged voltage |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_commercial_load` | Small commercial motor and HVAC load | commercial-switchboard; retail-centre |
| `industrial_motor_load` | Industrial motor control centre load | water-treatment-plant; manufacturing-site |
| `utility_customer_load` | Large utility customer connection | mining-load; large-campus |

### Difficulty Notes

```text
easy: all_given | Small load with all power factors given
medium: all_given | Commercial or industrial correction calculation
hard: partial | hidden=initial_power_factor | Larger load with initial power factor hidden in context
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
