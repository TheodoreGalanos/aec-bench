# ABOUTME: First-pass task-world opportunity card for cerc-longshore-transport.
# ABOUTME: Generated from live template metadata for multimodal and meta-harness review.

# civil / sediment-transport / cerc-longshore-transport

Review status: first-pass metadata card. Needs detailed analyst review before it is treated as design direction.

## Source

- Template: `src/aec_bench/templates/builtin/civil/cerc_longshore_transport`
- Discipline: `civil`
- Category: `sediment-transport`
- Tool mode: `with-tool`
- Standards: USACE CEM; Shore Protection Manual (SPM)
- Tags: coastal; sediment; longshore; transport; wave; littoral

## Current Task Shape

Estimates annual volumetric longshore sediment transport using the CERC formula from the USACE Coastal Engineering Manual and Shore Protection Manual. Calculates wave energy flux at the breaker line and converts it to a sediment transport rate, accounting for wave angle, sediment and water densities, and porosity. Used in coastal engineering to predict littoral drift and inform beach nourishment or breakwater design.

## Existing Deterministic Contract

- Parameters: `6`
- Outputs: `3`
- Archetypes: `4`
- Visibility mix: all_given; partial
- Hidden parameters: `k_coefficient`, `porosity`, `sediment_density_kg_m3`, `water_density_kg_m3`

### Inputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `breaking_wave_height_m` | Significant breaking wave height H_b | float / m | range=0.3..5.0 |
| `wave_angle_at_breaking_deg` | Wave angle at breaking relative to shore-normal alpha_b (positive = left-to-right looking shoreward) | float / degrees | range=-45.0..45.0 |
| `k_coefficient` | CERC empirical transport coefficient K | float / - | range=0.1..1.0; derivable_from=archetype |
| `sediment_density_kg_m3` | Sediment grain density rho_s | float / kg/m³ | range=2500.0..2800.0; derivable_from=archetype |
| `water_density_kg_m3` | Water density rho_w | float / kg/m³ | range=1000.0..1035.0; derivable_from=archetype |
| `porosity` | In-situ sediment porosity p | float / - | range=0.3..0.5; derivable_from=archetype |

### Outputs

| Name | Description | Unit/Type | Notes |
| --- | --- | --- | --- |
| `energy_flux_w_m` | Wave energy flux at breaking (E*Cg)_b in W/m |  | tolerance=0.03 |
| `transport_rate_m3_yr` | Volumetric longshore transport rate Q_l (m³/year, absolute value) |  | tolerance=0.05 |
| `transport_direction` | Transport direction: 1.0 = left-to-right, -1.0 = right-to-left (looking shoreward) |  | tolerance=0.01 |

### Archetypes

| Archetype | Description | Site Contexts |
| --- | --- | --- |
| `exposed_sandy_coast` | High-energy exposed sandy coastline with quartz sand and large oblique swell | nsw-south-coast-swell; wa-southwest-capes; sa-great-ocean-road |
| `moderate_energy_beach` | Moderate-energy beach with medium swell and modest wave angles | sunshine-coast-qld; newcastle-nsw-beach; mandurah-wa-coast |
| `sheltered_embayment` | Low-energy sheltered embayment with short-period wind waves and fine sand | moreton-bay-qld; port-phillip-bay-vic; cockburn-sound-wa |
| `high_energy_headland` | High-energy headland-controlled pocket beach with coarse sand and strong oblique waves | byron-bay-nsw-headland; noosa-heads-qld; cape-naturaliste-wa |

### Difficulty Notes

```text
easy: all_given | Moderate wave height, all parameters given — straightforward CERC formula application
medium: all_given | Larger waves, steeper angles, all parameters given — larger numbers but same formula
hard: partial | hidden=k_coefficient, sediment_density_kg_m3, water_density_kg_m3, porosity | K coefficient, sediment density, water density, and porosity hidden — agent must infer from site description
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
