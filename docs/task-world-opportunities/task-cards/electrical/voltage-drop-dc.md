# ABOUTME: First-pass task-world opportunity card for voltage-drop-dc.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / solar-pv-design / voltage-drop-dc

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/voltage_drop_dc`
- Discipline: `electrical`
- Category: `solar-pv-design`
- Tool mode: `with-tool`
- Standards: AS/NZS 5033; AS/NZS 3008.1
- Tags: electrical; solar-pv; dc; voltage-drop; cable; deterministic

## Current Task Shape

Calculates two-way DC cable voltage drop for a solar PV string using current, one-way length, cable cross-section, resistivity, and string voltage. The template also estimates annual resistive energy loss and voltage-drop margin.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `cable_resistivity_ohm_mm2_m`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `string_current_a` | PV string current at maximum power | float / A | range=1..30 |
| `dc_cable_length_m` | One-way DC cable length from string to inverter | float / m | range=1..300 |
| `cable_cross_section_mm2` | Cable conductor cross-section | float / mm2 | range=1.5..240 |
| `cable_resistivity_ohm_mm2_m` | Cable conductor resistivity | float / ohm.mm2/m | range=0.015..0.03 |
| `string_voltage_v` | PV string operating voltage | float / V | range=100..1500 |
| `annual_operating_hours` | Equivalent annual operating hours at the modelled current | float / h/year | range=500..3000 |
| `maximum_voltage_drop_pct` | Maximum permitted voltage drop percentage | float / % | range=0.5..5 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `voltage_drop_v` | Two-way DC cable voltage drop |  | tolerance=0.03 |
| `voltage_drop_pct` | Voltage drop as a percentage of string voltage |  | tolerance=0.03 |
| `annual_energy_loss_kwh` | Annual resistive energy loss |  | tolerance=0.03 |
| `voltage_drop_margin_pct` | Margin against the maximum voltage drop criterion |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `rooftop_pv_string` | Rooftop PV string cable run | rooftop-pv; dc-cable |
| `utility_pv_string` | Utility PV string home-run cable | utility-pv; dc-cable |

### Difficulty Notes

```text
easy: all_given | Rooftop PV string with all values visible
medium: all_given | PV string selected from rooftop or utility cases
hard: partial | hidden=cable_resistivity_ohm_mm2_m | Utility PV string with conductor resistivity embedded in context
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
