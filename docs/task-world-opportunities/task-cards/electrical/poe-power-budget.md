# ABOUTME: First-pass task-world opportunity card for poe-power-budget.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / poe-network / poe-power-budget

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/poe_power_budget`
- Discipline: `electrical`
- Category: `poe-network`
- Tool mode: `with-tool`
- Standards: IEEE 802.3bt; IEEE 802.3at
- Tags: electrical; poe; network; power-budget; deterministic

## Current Task Shape

Calculates total Power over Ethernet demand from device count and per-device power draw, then compares it with the switch PoE budget. The deterministic check reports utilization, available headroom, required headroom allowance, and remaining headroom margin.

## Existing Deterministic Contract

- Parameters: `4`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `required_headroom_pct`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `device_count` | Number of PoE powered devices | float | range=1..96 |
| `power_draw_per_device_w` | Power draw per device | float / W | range=1..90 |
| `switch_poe_budget_w` | Available switch PoE budget | float / W | range=30..3000 |
| `required_headroom_pct` | Required headroom as a percentage of connected PoE load | float / % | range=0..50 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `total_power_requirement_w` | Total PoE power requirement |  | tolerance=0.03 |
| `utilization_pct` | PoE budget utilization |  | tolerance=0.03 |
| `available_headroom_w` | Unused PoE budget |  | tolerance=0.03 |
| `required_headroom_w` | Required headroom allowance |  | tolerance=0.03 |
| `headroom_margin_w` | Margin after required headroom |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `access_switch` | Access switch serving cameras and wireless access points | station-comms-room; campus-access-switch |
| `high_power_switch` | High-power PoE switch serving PTZ cameras or field devices | roadside-cabinet; security-headend |

### Difficulty Notes

```text
easy: all_given | Small access switch budget
medium: all_given | Access or high-power PoE switch
hard: partial | hidden=required_headroom_pct | Headroom allowance hidden in design context
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
