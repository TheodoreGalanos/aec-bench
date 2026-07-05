# ABOUTME: First-pass task-world opportunity card for rf-link-budget.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / wireless-design / rf-link-budget

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/rf_link_budget`
- Discipline: `electrical`
- Category: `wireless-design`
- Tool mode: `with-tool`
- Standards: IEEE 802.11; FCC Part 15
- Tags: electrical; wireless; rf; link-budget; path-loss; deterministic

## Current Task Shape

Calculates wireless link budget using transmit power, antenna gains, distance, frequency, obstacle losses, and receive sensitivity. The template computes free-space path loss, total path loss, received signal level, and link margin.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `obstacle_losses_db`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `transmit_power_dbm` | Transmit power | float / dBm | range=-20..40 |
| `transmit_antenna_gain_dbi` | Transmit antenna gain | float / dBi | range=-5..30 |
| `distance_m` | Link distance | float / m | range=1..50000 |
| `frequency_ghz` | Carrier frequency | float / GHz | range=0.4..80 |
| `receive_antenna_gain_dbi` | Receive antenna gain | float / dBi | range=-5..30 |
| `obstacle_losses_db` | Additional obstacle and miscellaneous losses | float / dB | range=0..60 |
| `required_receive_sensitivity_dbm` | Required receive sensitivity | float / dBm | range=-120..-40 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `free_space_path_loss_db` | Free-space path loss |  | tolerance=0.03 |
| `total_path_loss_db` | Total path loss including obstacles |  | tolerance=0.03 |
| `received_signal_level_dbm` | Received signal level |  | tolerance=0.03 |
| `link_margin_db` | Margin above required receive sensitivity |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `short_wifi_link` | Short Wi-Fi or telemetry link | station-platform; campus-wireless |
| `long_field_link` | Longer directional field wireless link | roadside-radio; remote-pump-station |

### Difficulty Notes

```text
easy: all_given | Short wireless link with all losses visible
medium: all_given | Short or long wireless link
hard: partial | hidden=obstacle_losses_db | Obstacle loss hidden in path context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `spatial-map`.

Use layout plans, device schedules, coverage diagrams, timing tables, and network topology artifacts.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Communications and ITS tasks combine through shared layouts, device counts, coverage, storage, and power constraints.

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
