# ABOUTME: Detailed task-world review for civil wind-load and limit-state action tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the seventh civil slice.

# Civil Wind And Load Actions Pass 007

Review date: 2026-06-28

Reviewed task cards:

- `civil/wind-load-derivation/design-wind-speed`
- `civil/wind-load-derivation/design-wind-pressure`
- `civil/wind-load-derivation/solar-array-wind-load`
- `civil/load-combinations/sls-load-combinations`
- `civil/load-combinations/uls-load-combinations`

Source files read for this pass:

- `src/aec_bench/templates/builtin/civil/design_wind_speed/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/design_wind_pressure/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/solar_array_wind_load/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/sls_load_combinations/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/uls_load_combinations/{params.toml,instruction.md,engine.py}`

## Slice Read

This slice closes the civil discipline sweep with wind actions and limit-state load combinations. It is also the clearest bridge from civil task worlds into structural, renewable-energy, and electrical task worlds.

The natural pipeline is:

- derive site wind speed from regional wind speed and site multipliers;
- convert wind speed into pressure and tributary force;
- specialize wind pressure into solar array uplift/downforce/drag;
- combine dead, live, wind, and earthquake actions into SLS and ULS design actions.

These tasks are good multimodal targets because the hidden work is often source classification rather than formula derivation. A model must infer terrain category, shielding, topography, aerodynamic sign, row position, tilt, or occupancy category from a site description, plan, elevation, aerial context, datasheet, or load schedule.

This pass found two future repair candidates:

- `solar-array-wind-load` validates `array_height_m` but does not otherwise use it in the current calculation. Future variants should either keep height as context only or wire it into a declared coefficient/source rule.
- `uls-load-combinations` hard-mode metadata says the agent should infer load category from occupancy, but the instruction fallback says to use Category A when the category is not given. That conflicts with the intended hidden-parameter task shape and should be resolved before harder multimodal variants are generated.

## Task 1: Design Wind Speed

Current world:

- Computes terrain/height multiplier `M_z,cat` and site wind speed.
- Inputs are regional wind speed, terrain category, building height, topographic multiplier, shielding multiplier, and wind direction multiplier.
- Hard mode hides terrain category and shielding multiplier.
- The engine interpolates `M_z,cat` from an embedded AS/NZS 1170.2 terrain-height table.
- Heights below 3 m and above 200 m are clamped to table bounds.

Multimodal expansion:

- Best first modality: site plan/aerial context plus wind region and exposure table.
- A site plan or aerial tile can expose open terrain, suburban shielding, dense urban context, hilltop exposure, or escarpment context.
- A building elevation can expose height.
- A standards table can expose `M_z,cat` rows and interpolation.

Requirements:

- Source for regional wind speed and wind direction multiplier.
- Site exposure evidence for terrain category.
- Shielding evidence or assumption record.
- Topography source for topographic multiplier.
- Building height source and `M_z,cat` interpolation evidence.

Harness opportunities:

- Add source-classification gate for terrain category.
- Add shielding source gate for hard-mode hidden multiplier.
- Add interpolation gate for `M_z,cat`.
- Add multiplier closure gate for `V_sit,beta = V_R * M_d * M_z,cat * M_s * M_t`.
- Add contradiction event if the site description implies a terrain category different from the selected one.

Natural products:

- `design-wind-speed -> design-wind-pressure` as the core wind action pipeline.
- `design-wind-speed -> solar-array-wind-load` for renewable-energy structures.
- `design-wind-speed -> uls/sls-load-combinations` through derived wind actions.

Meta-harness handles:

- `projection`: text site brief, aerial/site plan, wind region table, terrain-height table.
- `difference`: hide terrain category, shielding, or table row labels.
- `product`: wind action derivation package.

## Task 2: Design Wind Pressure

Current world:

- Computes dynamic pressure, design pressure, and total tributary force.
- Inputs are design wind speed, aerodynamic shape factor, dynamic response factor, air density, and tributary area.
- Hard mode hides dynamic response factor and air density.
- The engine preserves the sign of `C_fig`, so suction can produce negative pressure and force.
- Outputs are in kPa and kN after Pa/N conversion.

Multimodal expansion:

- Best first modality: building elevation/roof plan plus pressure coefficient table.
- A facade, roof, or cladding drawing can expose tributary area.
- A zone diagram or aerodynamic-factor table can expose `C_fig`, including suction sign.
- A dynamic response note can justify `C_dyn`.
- An environmental/fluid assumption table can expose air density.

Requirements:

- Handoff source for design wind speed.
- Tributary area geometry source.
- Aerodynamic coefficient source with sign convention.
- Dynamic response factor source or standard default record.
- Unit conversion evidence for Pa to kPa and N to kN.

Harness opportunities:

- Add handoff gate from `design-wind-speed`.
- Add geometry gate for tributary area.
- Add sign-convention gate for positive pressure versus suction.
- Add source-authority gate for `C_fig`, `C_dyn`, and air density.
- Add force closure gate: pressure times area equals total force with sign preserved.

Natural products:

- `design-wind-speed -> design-wind-pressure -> sls/uls-load-combinations`.
- `design-wind-pressure -> structural member/cladding checks` when structural tasks are reviewed.
- `design-wind-pressure -> solar-array-wind-load` as a comparison between generic pressure and PV-specific net coefficients.

Meta-harness handles:

- `projection`: elevation/roof plan, pressure-zone diagram, coefficient table, tributary-area sketch.
- `difference`: hide `C_dyn`, air density, coefficient sign, or tributary-area labels.
- `product`: wind pressure and structural action package.

## Task 3: Solar Array Wind Load

Current world:

- Computes dynamic pressure, uplift pressure, downforce pressure, uplift force per module, and drag force per metre.
- Inputs are design wind speed, tilt angle, array height, module width/length, modules wide, row position, and air density.
- Hard mode hides tilt angle and row position.
- The engine interpolates SEAOC PV2 net pressure coefficients by tilt and applies a 0.6 reduction factor for interior rows.
- Uplift/downforce outputs are positive magnitudes.
- `array_height_m` is validated but does not otherwise influence the current calculation.

Multimodal expansion:

- Best first modality: solar array layout, module schedule, and racking section.
- A layout can expose exposed end rows versus interior rows.
- A racking section can expose tilt angle, module dimensions, and modules in slope direction.
- A site wind-speed handoff can come from `design-wind-speed`.
- A coefficient table can expose tilt interpolation and interior-row reduction.

Requirements:

- Handoff source for design wind speed.
- Array geometry source for tilt, module dimensions, and row depth.
- Row-position source distinguishing exposed and interior rows.
- Air-density source or standard assumption.
- Clear decision on whether array height is context-only or coefficient-driving.

Harness opportunities:

- Add row-position classification gate.
- Add tilt-angle extraction and interpolation gate.
- Add interior reduction gate.
- Add geometry gate for module area and projected height.
- Add repair target for unused `array_height_m` before height-sensitive variants are attempted.

Natural products:

- `design-wind-speed -> solar-array-wind-load` as a renewable-energy wind package.
- `solar-array-wind-load -> uls-load-combinations` for uplift/drag design action packaging.
- `solar-array-wind-load -> electrical/solar tasks` later through shared module layout and array geometry.

Meta-harness handles:

- `projection`: site wind brief, array layout, racking section, module schedule, coefficient table.
- `difference`: hide tilt, row position, or coefficient table labels.
- `product`: PV structural action package.

## Task 4: SLS Load Combinations

Current world:

- Computes short-term, long-term, wind SLS, and governing serviceability combination.
- Inputs are dead load, live load, serviceability wind action, and imposed-action category.
- Hard mode hides load category.
- The engine looks up `psi_s` and `psi_l` for Categories A to E, then takes the maximum of three combinations.
- Instruction asks the agent to infer category from building use when hidden.

Multimodal expansion:

- Best first modality: load schedule plus occupancy/use note.
- A structural loading table can expose dead, live, and serviceability wind actions.
- A room/use plan or building description can identify imposed-action category.
- A standards table can expose `psi_s` and `psi_l` values.

Requirements:

- Load schedule with G, Q, and serviceability wind action.
- Occupancy/use source for load category.
- Factor table for `psi_s` and `psi_l`.
- Governing-combination evidence across short-term, long-term, and wind cases.

Harness opportunities:

- Add occupancy-category inference gate.
- Add factor lookup gate.
- Add combination-by-combination construction gates.
- Add governing max gate.
- Add handoff gate from wind pressure/solar load tasks to serviceability wind action.

Natural products:

- `design-wind-pressure -> sls-load-combinations` for serviceability wind.
- `sls-load-combinations -> structural deflection/serviceability checks` when structural tasks are reviewed.
- `sls-load-combinations -> uls-load-combinations` as a paired limit-state package.

Meta-harness handles:

- `projection`: load schedule, occupancy plan, standards factor table.
- `difference`: hide category, wind action, or factor table row labels.
- `product`: structural action combination package.

## Task 5: ULS Load Combinations

Current world:

- Computes permanent-only, imposed, wind, wind-uplift, earthquake, and governing ultimate combinations.
- Inputs are dead load, live load, ultimate wind action, earthquake action, and imposed-action category.
- Hard mode hides load category.
- The engine uses Category A to D companion factors of `psi_c = 0.4`, `psi_E = 0.3`, and Category E factors of `0.6` for both.
- The instruction fallback currently says to use Category A if the imposed action category is not given, which conflicts with hard-mode metadata that says category should be inferred from occupancy.

Multimodal expansion:

- Best first modality: ultimate load schedule plus occupancy/use note.
- A structural loading table can expose G, Q, W, and E actions.
- A member/site context can expose whether wind uplift or earthquake is likely to govern.
- A standards table can expose companion factors.

Requirements:

- Load schedule with permanent, imposed, wind, and earthquake actions.
- Occupancy/use source for imposed-action category.
- Factor table for `psi_c` and `psi_E`.
- Governing-combination evidence across all five ULS expressions.
- Instruction repair so hidden-category variants require inference rather than defaulting to Category A.

Harness opportunities:

- Add category-inference gate with explicit occupancy evidence.
- Add companion-factor lookup gate.
- Add branch gate for wind uplift combination using `0.9G + W`.
- Add governing max gate across all combinations.
- Add repair target for metadata/instruction mismatch in hidden-category behavior.

Natural products:

- `design-wind-pressure/solar-array-wind-load -> uls-load-combinations` for ultimate wind actions.
- `fos-seismic -> uls-load-combinations` only conceptually through seismic action packaging if structural seismic tasks appear.
- `sls-load-combinations -> uls-load-combinations` as a paired limit-state package.

Meta-harness handles:

- `projection`: load schedule, occupancy plan, wind/earthquake action source, standards factor table.
- `difference`: hide load category, wind action, earthquake action, or factor table row labels.
- `product`: structural ultimate action package.

## Cross-Slice Threads Opened

This slice completes the civil wind/action pathway and sets up the next cross-discipline work:

- wind derivation chain: `design-wind-speed -> design-wind-pressure -> sls/uls-load-combinations`;
- PV wind package: `design-wind-speed -> solar-array-wind-load -> uls-load-combinations`;
- building action package: civil wind/load tasks feeding structural member, cladding, connection, and foundation checks;
- electrical/renewables package: solar array layout and wind loads eventually feeding DC layout, mounting, and earthing tasks if present.

## Meta-Harness Implications

The practical meta-harness shape here is a classification-and-handoff harness:

- classify the source context: terrain, shielding, row position, coefficient sign, or occupancy category;
- compute a deterministic quantity;
- hand it to the next task as a declared structural action;
- verify that source classification, intermediate value, and downstream action all close.

The best event candidates are:

- wrong terrain or shielding category;
- wrong `M_z,cat` interpolation;
- suction sign lost in wind pressure;
- wrong solar row-position reduction;
- load-category default used where hard mode expects inference;
- governing combination selected incorrectly even when individual combinations are correct.
