# ABOUTME: First-pass task-world opportunity card for fiber-link-loss-budget.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / structured-cabling / fiber-link-loss-budget

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/fiber_link_loss_budget`
- Discipline: `electrical`
- Category: `structured-cabling`
- Tool mode: `with-tool`
- Standards: ISO/IEC 11801; TIA-568
- Tags: electrical; fibre; fiber; link-loss; structured-cabling; deterministic

## Current Task Shape

Calculates total optical link loss by summing fibre attenuation, connector losses, and splice losses, then compares the result with the system loss budget. This deterministic structured-cabling check reports component losses, total link loss, and remaining power margin.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `system_loss_budget_db`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `fiber_length_km` | Fibre route length | float / km | range=0.01..80 |
| `fiber_attenuation_db_per_km` | Fibre attenuation | float / dB/km | range=0.1..3.5 |
| `connector_count` | Number of connector interfaces | float | range=0..20 |
| `connector_loss_db` | Loss per connector | float / dB | range=0..1.5 |
| `splice_count` | Number of splices | float | range=0..40 |
| `splice_loss_db` | Loss per splice | float / dB | range=0..0.5 |
| `system_loss_budget_db` | Available system optical loss budget | float / dB | range=1..40 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `fiber_loss_db` | Loss due to fibre attenuation |  | tolerance=0.03 |
| `connector_loss_total_db` | Total connector loss |  | tolerance=0.03 |
| `splice_loss_total_db` | Total splice loss |  | tolerance=0.03 |
| `total_link_loss_db` | Total optical link loss |  | tolerance=0.03 |
| `power_margin_db` | Remaining optical power margin |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `campus_backbone` | Multimode or short single-mode campus backbone | campus-backbone; station-comms-room |
| `long_haul_link` | Longer single-mode field fibre link | roadside-fibre; rail-corridor |

### Difficulty Notes

```text
easy: all_given | Short link with all component losses given
medium: all_given | Short or long fibre link
hard: partial | hidden=system_loss_budget_db | System budget hidden in the link context
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
