# ABOUTME: First-pass task-world opportunity card for incident-energy.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# electrical / arc-flash / incident-energy

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/electrical/incident_energy`
- Discipline: `electrical`
- Category: `arc-flash`
- Tool mode: `with-tool`
- Standards: IEEE 1584; NFPA 70E
- Tags: electrical; arc-flash; incident-energy; safety; PPE

## Current Task Shape

Calculates arc flash incident energy, arcing current, arc flash boundary distance, and required PPE category using the IEEE 1584-2002 empirical method for systems from 208 V to 15 kV. Models both low-voltage and medium-voltage arcing current equations and normalized energy formulas, supporting electrical safety assessments and arc flash labelling per NFPA 70E.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `4`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `electrode_gap_mm`, `enclosure_type`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `system_voltage_v` | System three-phase RMS voltage | float / V | range=208..15000 |
| `bolted_fault_current_ka` | Available bolted (symmetrical) three-phase fault current | float / kA | range=0.5..106 |
| `clearing_time_s` | Protective device clearing time (arc duration) | float / s | range=0.01..2.0 |
| `working_distance_mm` | Distance from arc source to worker | float / mm | range=300..1800 |
| `electrode_gap_mm` | Electrode gap (conductor spacing) | float / mm | range=6..254; derivable_from=archetype |
| `enclosure_type` | Equipment enclosure type | enum | values=open, box, MCC; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `arcing_current_ka` | Predicted arcing fault current (kA) |  | tolerance=0.05 |
| `incident_energy_cal_cm2` | Incident energy at working distance (cal/cm2) |  | tolerance=0.05 |
| `arc_flash_boundary_mm` | Arc flash boundary distance where E = 1.2 cal/cm2 (mm) |  | tolerance=0.05 |
| `ppe_category` | Required PPE category (0-4 per NFPA 70E) |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `lv_switchboard` | Low voltage switchboard (400-480 V) | commercial-building-switchroom; industrial-plant-mcc-room |
| `lv_mcc` | Low voltage motor control centre (400-480 V) | industrial-plant-mcc-lineup; water-treatment-mcc |
| `lv_panelboard` | Low voltage panelboard or distribution board (230-480 V) | office-building-db; retail-distribution-board |
| `mv_switchgear` | Medium voltage switchgear (4160-13800 V) | substation-switchgear-room; industrial-hv-switchroom |

### Difficulty Notes

```text
easy: all_given | Low voltage box/MCC with all parameters given, moderate fault levels
medium: all_given | Any voltage level and enclosure type, all parameters given
hard: partial | hidden=enclosure_type, electrode_gap_mm | Enclosure type and electrode gap hidden, agent must infer from equipment context
```

## Multimodal Expansion

Candidate modality families: `drawing-geometry`, `tabular-source`, `time-series`.

Use single-line diagrams, layouts, device schedules, demand profiles, and equipment datasheets.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Compose with tasks that share the same site context, source artifact, or downstream output obligation.

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
