# ABOUTME: First-pass task-world opportunity card for access-controller-sizing.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / access-control / access-controller-sizing

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/access_controller_sizing`
- Discipline: `electrical`
- Category: `access-control`
- Tool mode: `with-tool`
- Standards: SIA OSDP; UL 294
- Tags: electrical; security; access-control; power-supply; battery; deterministic

## Current Task Shape

Calculates a reduced access control system sizing case from door count, controller capacity, per-door device currents, controller current, power supply capacity, and backup duration. The template reports controller count, current demand, supply count, and battery capacity.

## Existing Deterministic Contract

- Parameters: `9`
- Outputs: `5`
- Archetypes: `2`
- Visibility mix: all_given; partial
- Hidden parameters: `battery_derating_factor`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `door_count` | Number of controlled doors | float / count | range=1..500 |
| `doors_per_controller` | Controller door capacity | float / doors/controller | range=1..16 |
| `reader_current_ma_per_door` | Reader current per controlled door | float / mA | range=0..1000 |
| `lock_current_ma_per_door` | Electric lock current per controlled door | float / mA | range=0..3000 |
| `request_to_exit_current_ma_per_door` | Request-to-exit device current per controlled door | float / mA | range=0..1000 |
| `controller_current_ma` | Current draw per access controller | float / mA | range=0..3000 |
| `power_supply_capacity_a` | Usable current capacity per power supply | float / A | range=0.5..50 |
| `backup_duration_h` | Required backup battery duration | float / h | range=0.5..72 |
| `battery_derating_factor` | Battery derating factor applied to backup capacity | float / - | range=0.4..1 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `controllers_required` | Number of access controllers required |  | tolerance=0.01 |
| `door_device_load_a` | Total current for door devices |  | tolerance=0.03 |
| `total_system_load_a` | Total access control system current |  | tolerance=0.03 |
| `power_supplies_required` | Number of power supplies required |  | tolerance=0.01 |
| `battery_capacity_ah` | Required battery capacity |  | tolerance=0.03 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_office_access` | Small office access control system | office-security; access-control |
| `campus_access` | Campus access control system | campus-security; access-control |

### Difficulty Notes

```text
easy: all_given | Small office access control with all values visible
medium: all_given | Access control case selected from office or campus systems
hard: partial | hidden=battery_derating_factor | Campus access control with battery derating embedded in context
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
