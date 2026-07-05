# ABOUTME: First-pass task-world opportunity card for hudson-armor-sizing.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / armor-stability / hudson-armor-sizing

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/hudson_armor_sizing`
- Discipline: `civil`
- Category: `armor-stability`
- Tool mode: `with-tool`
- Standards: USACE CEM; CIRIA C683 Rock Manual
- Tags: coastal; breakwater; armor; riprap; wave

## Current Task Shape

Determines the required median armor stone weight and nominal diameter for breakwater and revetment stability using Hudson's (1959) formula from the USACE Coastal Engineering Manual and CIRIA C683 Rock Manual. Accounts for design wave height, rock and water densities, structure slope, and the stability coefficient KD which depends on armor type and placement method.

## Existing Deterministic Contract

- Parameters: `5`
- Outputs: `3`
- Archetypes: `5`
- Visibility mix: all_given; partial
- Hidden parameters: `rock_density_kg_m3`, `stability_coefficient_kd`, `water_density_kg_m3`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `design_wave_height_m` | Design wave height H | float / m | range=0.5..8.0 |
| `rock_density_kg_m3` | Armor rock density rho_r | float / kg/m³ | range=2200..3000; derivable_from=archetype |
| `water_density_kg_m3` | Water density rho_w | float / kg/m³ | range=1000..1035; derivable_from=archetype |
| `slope_angle_deg` | Structure slope angle alpha from horizontal | float / degrees | range=18..45 |
| `stability_coefficient_kd` | Hudson stability coefficient KD | float / - | range=1.0..16.0; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `specific_gravity_sr` | Specific gravity of rock Sr = rho_r / rho_w |  | tolerance=0.03 |
| `armor_weight_tonnes` | Median armor unit weight W (tonnes) |  | tolerance=0.05 |
| `nominal_diameter_m` | Nominal armor diameter Dn50 (m) |  | tolerance=0.05 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `rough_quarrystone_random` | Rough angular quarrystone placed randomly on trunk section | queensland-outer-reef; nsw-coastal-headland; wa-exposed-coast |
| `rough_quarrystone_special` | Rough angular quarrystone with special placement on trunk | sydney-harbour-breakwater; melbourne-port-revetment |
| `basalt_armor_random` | Dense basalt armor stone placed randomly | victoria-basalt-coast; north-qld-volcanic |
| `freshwater_quarrystone` | Quarrystone armor for freshwater dam or lake revetment | murray-river-weir; snowy-hydro-dam; wivenhoe-dam |
| `concrete_unit_random` | Concrete armor units (cubes) placed randomly | darwin-harbour-breakwater; townsville-port-expansion |

### Difficulty Notes

```text
easy: all_given | Moderate wave height, all parameters given — straightforward Hudson formula
medium: all_given | Larger wave height, steeper slopes — same formula, bigger numbers
hard: partial | hidden=rock_density_kg_m3, water_density_kg_m3, stability_coefficient_kd | Rock density, water density, and KD hidden — agent must infer from site description
```

## Multimodal Expansion

Candidate modality families: `spatial-map`, `chart-curve`, `tabular-source`.

Use beach profiles, tide/wave tables, shoreline maps, spectra, and coastal cross-sections.

Requirements to make this rigorous:

- Preserve source artifacts that expose, hide, or ambiguously imply the current scalar parameters.
- Add source-to-parameter trace records for derived or hidden values.
- Keep the existing numeric engine as the closure oracle, but add construction gates for source interpretation.
- Add verifier evidence for units, assumptions, and intermediate values where the source artifact carries context.

## Natural Combinations

Boundary-condition tasks can feed coastal drainage, outfall, armor, runup, and overtopping worlds.

First-pass composition tags: `shared-context`, `pipeline`, `evidence-assembly`.

## Meta-Harness Handles

Candidate operation handles: `parameters`, `outputs`, `difficulty`, `archetype`, `evidence_profile`, `hidden_parameter_policy`, `source_geometry`, `source_table`, `source_curve`.

Practical operations to consider:

- `projection`: isolate the arithmetic-only world, source-interpretation world, or evidence-review world.
- `difference`: remove visible parameters, calculator access, source labels, or intermediate hints.
- `subset`: restrict to one archetype, standard, modality, or difficulty tier.
- `product`: compose with a downstream or upstream task that consumes/produces compatible engineering quantities.

## Repair/Event Candidates

- Trigger `evidence_profile` repair if the model reaches the right number without citing or preserving the source artifact.
- Trigger `verifier` repair if final-output tolerances pass while intermediate units, assumptions, or handoff values are inconsistent.
- Trigger `world_schema` repair if a promising composition lacks explicit handoff fields or operation handles.
