# ABOUTME: First-pass task-world opportunity card for nac-load-calculation.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# mechanical / fire-services / nac-load-calculation

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/mechanical/nac_load_calculation`
- Discipline: `mechanical`
- Category: `fire-services`
- Tool mode: `with-tool`
- Standards: NFPA 72
- Tags: mechanical; fire-services; nac; notification-appliance-circuit; deterministic

## Current Task Shape

Calculates fire alarm notification appliance circuit load from strobe, horn, and speaker quantities and device currents. The template reports total load, circuit utilisation, spare capacity, and whether the load is within the circuit capacity.

## Existing Deterministic Contract

- Parameters: `7`
- Outputs: `4`
- Archetypes: `2`
- Visibility mix: all_given
- Hidden parameters: None recorded

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `strobe_quantity` | Number of strobes on the circuit | int | range=0..200 |
| `strobe_current_a` | Current draw per strobe | float / A | range=0.0..0.5 |
| `horn_quantity` | Number of horns on the circuit | int | range=0..200 |
| `horn_current_a` | Current draw per horn | float / A | range=0.0..0.3 |
| `speaker_quantity` | Number of speakers on the circuit | int | range=0..200 |
| `speaker_current_a` | Current draw per speaker | float / A | range=0.0..0.2 |
| `circuit_capacity_a` | Available circuit current capacity | float / A | range=0.5..10.0 |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `total_load_a` | Total notification appliance current load |  | tolerance=0.03 |
| `utilisation_pct` | Circuit load as a percentage of capacity |  | tolerance=0.03 |
| `spare_capacity_a` | Remaining circuit current capacity |  | tolerance=0.03 |
| `passes_capacity_check` | Whether total load is within circuit capacity |  | tolerance=0.0 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `small_notification_circuit` | Small notification circuit with modest appliance count | office-fire-alarm-zone; small-public-building |
| `voice_evacuation_circuit` | Voice evacuation notification circuit with speakers and strobes | station-public-address-fire-mode; large-assembly-building |

### Difficulty Notes

```text
easy: all_given | All parameters given for a small notification circuit
medium: all_given | All parameters given across conventional and voice evacuation circuits
hard: all_given | All parameters given for higher-load voice evacuation circuits
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
