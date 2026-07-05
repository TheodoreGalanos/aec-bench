# ABOUTME: Detailed task-world review for civil coastal, wave, and shoreline tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the third civil slice.

# Civil Coastal And Wave Pass 003

Review date: 2026-06-28

Reviewed task cards:

- `civil/wave-climate/linear-wave-theory`
- `civil/wave-climate/wave-shoaling`
- `civil/wave-climate/wave-breaking`
- `civil/wave-overtopping/wave-runup`
- `civil/coastal-drainage/freeboard-calculation`
- `civil/tidal-water-levels/tidal-prism`
- `civil/armor-stability/hudson-armor-sizing`
- `civil/sediment-transport/cerc-longshore-transport`

Source files read for this pass:

- `src/aec_bench/templates/builtin/civil/linear_wave_theory/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/wave_shoaling/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/wave_breaking/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/wave_runup/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/freeboard_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/tidal_prism/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/hudson_armor_sizing/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/cerc_longshore_transport/{params.toml,instruction.md,engine.py}`

## Slice Read

This slice is best understood as a coastal boundary-condition chain:

1. Offshore or local wave conditions are read from a source.
2. Wave period, height, angle, and bathymetry transform into nearshore wave conditions.
3. Breaking, runup, freeboard, armor stability, sediment transport, and tidal exchange use those transformed conditions.
4. Coastal outfall and drainage tasks from the previous pass can consume water-level and tailwater consequences.

The current templates are deterministic, but the interesting task-world is not only arithmetic. It is source authority and regime selection: correct datum, correct profile, correct wave period, correct incident angle, correct slope, correct material/density, correct planning horizon, and correct sign convention.

## Task 1: Linear Wave Theory

Current world:

- Solves the Airy wave dispersion relation using Newton-Raphson.
- Inputs are `wave_period_s`, `water_depth_m`, and `wave_height_m`.
- Outputs are wavelength, wave celerity, group velocity, wave steepness, and relative depth.
- Hard mode hides `wave_period_s` and expects estimation from wave height using empirical wind-wave relationships.
- The engine reports `relative_depth` so deep/intermediate/shallow water can be inferred.

Multimodal expansion:

- Best first modality: wave buoy table plus bathymetry/profile source.
- A richer variant can provide a wave rose or spectral summary where the model must select the design period.
- A cross-section/profile can provide water depth at a chainage or structure toe.

Requirements:

- Source artifact for wave height and period, or a wave-height-to-period inference rule embedded in the world.
- Bathymetry/profile artifact with datum and extraction point.
- Iteration evidence record: initial deep-water wavelength, convergence, wavelength, celerity, group velocity.
- Depth-regime classification evidence from `relative_depth`.

Harness opportunities:

- Add a construction gate for dispersion convergence or at least final residual tolerance.
- Add a source gate for wave period when hidden.
- Add an event trigger when the model uses deep-water approximation outside deep-water regime.

Natural products:

- `linear-wave-theory -> wave-shoaling` via wavelength/celerity/group velocity concepts or shared wave period/depth.
- `linear-wave-theory -> wave-breaking` through deep-water wavelength and wave period.
- `linear-wave-theory -> wave-runup` through spectral period and wave steepness.

Meta-harness handles:

- `projection`: source wave selection, bathymetry extraction, dispersion arithmetic, depth-regime classification.
- `difference`: remove wave period, then remove explicit depth and require profile extraction.
- `product`: compose with shoaling, breaking, or runup worlds.

## Task 2: Wave Shoaling

Current world:

- Computes shoaling coefficient, refraction coefficient, and nearshore wave height.
- Inputs are deep-water wave height, wave period, nearshore depth, and deep-water approach angle.
- Hard mode hides `wave_period_s` and `deep_water_wave_angle_deg`.
- The engine uses Fenton & McKee explicit wavelength approximation and Snell's law.

Multimodal expansion:

- Best first modality: offshore wave condition table plus bathymetric contour/profile.
- A wave rose can provide incident angle; a shore-normal map can force the model to compute or select angle relative to local shoreline.
- A nearshore transect can supply target depth.

Requirements:

- Source records for offshore wave height, period, approach angle, nearshore depth, and shoreline orientation.
- Coordinate/angle convention made explicit: nautical direction versus shore-normal angle is a likely failure point.
- Construction evidence for shoaling coefficient, refraction coefficient, local angle, and nearshore height.

Harness opportunities:

- Add angle-convention contradiction gate.
- Add source geometry gate for nearshore depth from profile.
- Add product-world handoff that nearshore wave height is the input for wave breaking/runup/armor tasks.

Natural products:

- `wave-shoaling -> wave-breaking` using `nearshore_wave_height_m`.
- `wave-shoaling -> wave-runup` if nearshore conditions are at the structure toe.
- `wave-shoaling -> cerc-longshore-transport` if transformed breaking angle is added.

Meta-harness handles:

- `projection`: offshore-source selection, bathymetry/depth extraction, refraction angle, coefficient arithmetic.
- `difference`: remove period and approach angle, then remove explicit shore-normal orientation.
- `product`: nearshore wave transformation chain.

## Task 3: Wave Breaking

Current world:

- Computes breaking wave height, breaking depth, breaker type, and Iribarren number.
- Inputs are wave height, wave period, water depth, and bottom slope.
- Hard mode hides `wave_period_s` and `bottom_slope`.
- The engine uses a Weggel-style breaker depth index, deep-water wavelength, Iribarren number, and breaker-type classification.

Multimodal expansion:

- Best first modality: beach or reef profile plus incident wave condition table.
- The profile supplies bottom slope and local depth; the table supplies wave height and period.
- A richer variant can ask the model to classify breaker type and explain whether breaking occurs before the structure/toe.

Requirements:

- Profile source artifact with slope extraction method.
- Wave source artifact with height and period.
- Construction gate for breaker index, breaking depth, Iribarren number, and breaker type.
- Optional spatial gate: breaking location along a cross-shore transect.

Harness opportunities:

- Add event trigger for wrong breaker-type classification.
- Add source gate for bottom slope because hidden slope is a real multimodal inference.
- Add contradiction event where `breaking_wave_height_m` is plausible but breaker type disagrees with Iribarren threshold.

Natural products:

- `wave-shoaling -> wave-breaking` by passing nearshore wave height.
- `wave-breaking -> cerc-longshore-transport` by providing breaking wave height.
- `wave-breaking -> wave-runup` by checking wave regime at the structure.

Meta-harness handles:

- `projection`: profile/slope extraction, breaking-depth calculation, breaker classification.
- `difference`: remove wave period and slope labels.
- `product`: surf-zone process chain.

## Task 4: Wave Runup

Current world:

- Computes breaker parameter, 2 percent exceedance runup height, and numeric regime code.
- Inputs are wave height, spectral period, structure slope, roughness factor, and berm factor.
- Hard mode hides `roughness_factor`, `berm_factor`, and `wave_period_s`.
- The engine evaluates both EurOtop/TAW runup expressions and selects the governing regime: breaking/plunging or surging/non-breaking.

Multimodal expansion:

- Best first modality: coastal structure section plus wave condition table.
- The section exposes slope, berm presence, and roughness type.
- A structure/material detail can map roughness and berm factors.

Requirements:

- Structure cross-section artifact with slope, berm, armor/material, and toe reference.
- Embedded roughness/berm factor source table.
- Wave source record from offshore/nearshore chain.
- Construction gate for breaker parameter and governing expression selection.

Harness opportunities:

- Add event trigger for wrong runup regime selection.
- Add geometry/material source gates for structure slope, roughness, and berm factor.
- Add product handle from `runup_height_m` to freeboard and crest-level checks.

Natural products:

- `wave-shoaling/wave-breaking -> wave-runup`.
- `wave-runup -> freeboard-calculation` through `wave_allowance_m`.
- `wave-runup -> hudson-armor-sizing` as shared structure/wave context.

Meta-harness handles:

- `projection`: structure geometry, factor lookup, runup-regime arithmetic.
- `difference`: hide wave period, roughness, and berm factors.
- `product`: coastal structure safety chain.

## Task 5: Freeboard Calculation

Current world:

- Computes total freeboard and minimum crest/floor level.
- Inputs are design water level, wave allowance, sea-level-rise allowance, construction tolerance, and safety margin.
- Hard mode hides all allowances except design water level.
- The engine is additive, but the task-world is source-authority heavy.

Multimodal expansion:

- Best first modality: design-water-level table plus planning-horizon/asset-consequence note.
- A structure section can expose existing/proposed crest level.
- A future scenario table can expose SLR allowance by year/pathway.

Requirements:

- Source artifacts for wave allowance, SLR allowance, tolerance, and safety margin.
- Datum declaration and consistency check.
- Consequence/category source for safety margin.
- Optional comparison against existing crest/floor level.

Harness opportunities:

- Add source-authority gates for every allowance component.
- Add datum-consistency contradiction gate.
- Add artifact-production variant requiring a freeboard decision record with component provenance.

Natural products:

- `wave-runup -> freeboard-calculation` by deriving wave allowance.
- `outfall-submergence-check -> freeboard-calculation` by informing future water level/tailwater.
- `freeboard-calculation -> structural/construction-tolerance` if crest/floor build tolerance is material.

Meta-harness handles:

- `projection`: source allowances, datum check, arithmetic sum, crest decision.
- `difference`: remove allowance values and require source table/note extraction.
- `product`: coastal structure safety package.

## Task 6: Tidal Prism

Current world:

- Computes tidal prism, inlet flow area, mean tidal flow, and mean tidal velocity.
- Inputs are basin surface area, tidal range, inlet width, inlet average depth, and exchange duration.
- Hard mode hides `exchange_duration_h`.
- The engine uses a reduced relation: prism equals basin area times tidal range.

Multimodal expansion:

- Best first modality: basin/inlet plan plus tide table.
- The plan/map provides basin surface area and inlet width; a section provides average depth.
- A tidal-regime note can provide exchange duration.

Requirements:

- GIS/map-like basin polygon artifact with known area.
- Inlet section/source profile for width and depth.
- Tide table or regime table for tidal range and exchange duration.
- Construction gate for prism and mean velocity, especially unit conversion from hours to seconds.

Harness opportunities:

- Add source geometry gate for basin area and inlet area.
- Add event trigger for unrealistic mean inlet velocity relative to design threshold if a threshold is added.
- Add product handle into sediment/inlet stability or outfall/tailwater worlds.

Natural products:

- `tidal-prism -> outfall-submergence-check` as shared tidal context.
- `tidal-prism -> cerc-longshore-transport` for inlet/shoreline sediment-management package.
- `tidal-prism -> open-channel-capacity` if inlet conveyance is framed as channel capacity.

Meta-harness handles:

- `projection`: basin map extraction, inlet section extraction, tidal exchange arithmetic.
- `difference`: hide exchange duration and/or basin area.
- `product`: tidal inlet/outfall package.

## Task 7: Hudson Armor Sizing

Current world:

- Computes rock specific gravity, armor weight, and nominal diameter using Hudson's equation.
- Inputs are design wave height, rock density, water density, slope angle, and stability coefficient `KD`.
- Hard mode hides rock density, water density, and `KD`.
- The engine validates that rock density exceeds water density and computes nominal stone diameter from weight/density.

Multimodal expansion:

- Best first modality: breakwater/revetment section plus material/datasheet table.
- Wave height can come from the nearshore transformation chain.
- The structure section supplies slope; material notes supply rock density and armor placement type for `KD`.

Requirements:

- Structure cross-section with slope angle or H:V slope.
- Rock/material source table for density.
- Stability coefficient source keyed by armor type, placement, and damage level.
- Source-to-parameter trace for `KD` and density, not just final armor size.

Harness opportunities:

- Add source-authority gate for `KD`, which is easy to guess but important.
- Add geometry gate for slope angle conversion from section labels.
- Add artifact-production variant requiring an armor sizing record with assumptions and material provenance.

Natural products:

- `wave-shoaling/wave-breaking -> hudson-armor-sizing` using design wave height.
- `hudson-armor-sizing -> wave-runup/freeboard` as shared structure context.
- `hudson-armor-sizing -> structural/materials` if armor quantities or constructability are added.

Meta-harness handles:

- `projection`: wave input, section slope, material/KD authority, Hudson arithmetic.
- `difference`: remove density and `KD`, then remove slope labels.
- `product`: coastal armor design package.

## Task 8: CERC Longshore Transport

Current world:

- Computes wave energy flux, annual volumetric transport rate, and transport direction.
- Inputs are breaking wave height, wave angle at breaking, CERC coefficient `K`, sediment density, water density, and porosity.
- Hard mode hides `K`, sediment density, water density, and porosity.
- The engine encodes transport direction as `1.0` for positive breaking angle and `-1.0` for negative angle.

Multimodal expansion:

- Best first modality: shoreline/wave-angle diagram plus sediment sample table.
- Breaking wave height can come from `wave-breaking`.
- Sediment density and porosity can come from a geotechnical/sediment source table.
- A shoreline orientation map can force the sign convention for transport direction.

Requirements:

- Source artifact for breaking wave height and angle at breaking.
- Sediment/material table for density and porosity.
- Embedded convention for positive/negative transport direction.
- Construction gate for energy flux and direction sign.

Harness opportunities:

- Add contradiction gate for sign convention: magnitude may be right while direction is wrong.
- Add source-authority gate for `K` and sediment properties.
- Add product-world artifact: littoral drift note with direction, magnitude, and source assumptions.

Natural products:

- `wave-breaking -> cerc-longshore-transport`.
- `cerc-longshore-transport -> coastal inlet/tidal-prism` if sediment bypassing or inlet stability is modeled.
- `cerc-longshore-transport -> erosion/sediment management` tasks if shoreline response artifacts are added.

Meta-harness handles:

- `projection`: wave-at-breaking source, sediment-property source, sign convention, transport arithmetic.
- `difference`: hide sediment properties and sign convention cues.
- `product`: shoreline response package.

## Cross-Task Product Worlds

### Product World A: Nearshore Wave Transformation Chain

Source pack:

- Offshore wave table or wave rose.
- Bathymetry profile/transect.
- Shoreline orientation map.

Composed tasks:

1. `linear-wave-theory` solves wavelength, celerity, group velocity, and depth regime.
2. `wave-shoaling` transforms offshore wave height to nearshore wave height.
3. `wave-breaking` classifies breaking depth and breaker type.

Why it is useful:

- It turns three scalar templates into a coherent wave-physics chain with source extraction, angle conventions, and regime decisions.

### Product World B: Coastal Structure Safety Package

Source pack:

- Nearshore wave condition handoff.
- Coastal structure cross-section.
- Material/roughness/KD table.
- SLR/planning-horizon table.

Composed tasks:

1. `wave-runup` computes runup and regime.
2. `freeboard-calculation` converts wave/SLR/tolerance allowances into crest level.
3. `hudson-armor-sizing` sizes armor for the same design wave and slope.

Why it is useful:

- It tests the whole design conversation: wave condition, structure geometry, material properties, future water level, and safety margin.

### Product World C: Shoreline Sediment Response Package

Source pack:

- Wave transformation output at breaking.
- Shoreline orientation map.
- Sediment sample table.

Composed tasks:

1. `wave-breaking` provides breaking wave height.
2. `cerc-longshore-transport` computes transport rate and direction.
3. Optional tidal/inlet tasks interpret whether transport affects inlet or outfall performance.

Why it is useful:

- The sign convention and sediment properties give strong evidence targets beyond final magnitude.

### Product World D: Tidal Inlet And Coastal Outfall Package

Source pack:

- Basin/inlet map.
- Inlet cross-section.
- Tide table and SLR scenario.
- Outfall profile from the previous conveyance pass.

Composed tasks:

1. `tidal-prism` computes exchange volume and inlet velocity.
2. `outfall-submergence-check` computes present/future submergence.
3. Optional `flap-gate-headloss` consumes outfall/gate context.

Why it is useful:

- It combines map geometry, profile/datum extraction, tide regime, future scenario, and drainage consequences.

## Initial Combination Findings

| Candidate | Product Axis | Handoff Fields | Main New Evidence |
| --- | --- | --- | --- |
| Linear wave to shoaling | `offshore_to_nearshore_wave` | `wave_period_s`, depth/regime, group velocity context | Wave table, bathymetry profile. |
| Shoaling to breaking | `nearshore_to_breaking` | `nearshore_wave_height_m`, angle/depth context | Transect profile, shoreline orientation. |
| Breaking to CERC | `breaking_to_sediment_transport` | `breaking_wave_height_m`, angle at breaking | Sediment table, sign convention map. |
| Runup to freeboard | `runup_to_crest_level` | `runup_height_m` or `wave_allowance_m`, structure slope/factors | Structure section, roughness/berm table, SLR table. |
| Wave to armor | `wave_to_armor_stability` | design wave height, slope, material density, `KD` | Structure section, rock/material datasheet. |
| Tidal prism to outfall | `tidal_exchange_to_tailwater` | tidal range, exchange duration, mean velocity, tide regime | Basin map, inlet section, tide/SLR table. |

## Meta-Harness Follow-Ups

Add operation handles to future explicit world sidecars:

- `source_artifacts.wave_table`
- `source_artifacts.wave_rose`
- `source_artifacts.bathymetry_profile`
- `source_artifacts.shoreline_orientation_map`
- `source_artifacts.structure_section`
- `source_artifacts.roughness_factor_table`
- `source_artifacts.slr_scenario_table`
- `source_artifacts.rock_material_table`
- `source_artifacts.sediment_table`
- `source_artifacts.basin_map`
- `source_artifacts.inlet_section`
- `branch_decisions.depth_regime`
- `branch_decisions.breaker_type`
- `branch_decisions.runup_regime`
- `branch_decisions.transport_direction`
- `branch_decisions.datum_consistency`
- `handoffs.nearshore_wave_height`
- `handoffs.breaking_wave_height`
- `handoffs.runup_allowance`
- `handoffs.tidal_exchange`

Add closure and construction gates:

- wave period, height, and angle are traceable to the selected source row or wave-rose bin;
- bathymetry/profile extraction uses the declared datum and chainage;
- shoaling/refraction coefficients produce the nearshore wave-height handoff;
- breaker type follows the computed Iribarren number;
- runup regime matches the governing expression selected by the engine;
- freeboard components have separate source records and datum consistency;
- Hudson density and `KD` are traceable to material/armor assumptions;
- CERC transport direction matches the signed wave angle convention;
- tidal-prism exchange duration and basin area are source-derived, not guessed.

