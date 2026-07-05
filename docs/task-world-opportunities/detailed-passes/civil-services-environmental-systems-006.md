# ABOUTME: Detailed task-world review for civil services, pump-station, and environmental control tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the sixth civil slice.

# Civil Services And Environmental Systems Pass 006

Review date: 2026-06-28

Reviewed task cards:

- `civil/oil-containment/bund-volume-calculation`
- `civil/erosion-sediment/sediment-basin-sizing`
- `civil/gravity-sewer/sewer-pipe-sizing`
- `civil/gravity-sewer/sewer-slope-check`
- `civil/pump-station/npsh-calculation`
- `civil/pump-station/pump-power-calc`
- `civil/stormwater-roof/downpipe-sizing`
- `civil/stormwater-roof/gutter-sizing`
- `civil/water-quality/pollutant-load-estimate`

Source files read for this pass:

- `src/aec_bench/templates/builtin/civil/bund_volume_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/sediment_basin_sizing/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/sewer_pipe_sizing/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/sewer_slope_check/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/npsh_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/pump_power_calc/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/downpipe_sizing/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/gutter_sizing/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/civil/pollutant_load_estimate/{params.toml,instruction.md,engine.py}`

## Slice Read

This slice is the civil services and environmental-control layer: roof drainage, sewer gravity design, pump station checks, construction sediment control, oil containment, and pollutant load estimation.

The earlier civil slices focused on water movement through channels, pipes, coasts, and geotechnical states. This slice is more about design-system assembly:

- source layouts: roof plans, gutter/downpipe layouts, sewer long sections, pump station wet-well sections, bund layouts, catchment plans, and erosion-control plans;
- source tables: rainfall intensities, standard gutter/downpipe capacities, Manning roughness values, pump/fluid properties, EMC values, soil loss rates, and sediment basin coefficients;
- selection and compliance: standard size selection, velocity pass/fail, NPSH margin, bund compliance, pollutant load totals, and sediment basin volume components.

The strongest multimodal opportunity is not to invent complex visuals for each formula, but to create realistic drawing/table packs where the model must assemble the right scalar world before applying a small deterministic calculation. These tasks are ideal for evidence-profile gates because many hard modes hide a source-table row rather than a formula term.

This pass found one contract wrinkle for future repair: `gutter-sizing` accepts a `gutter_profile` input and computes its nominated capacity internally, but the output reports the smallest adequate required gutter size and uses that selected capacity for compliance. That may be a design task rather than a check task, but multimodal expansion should make the intended contract explicit so agents are not asked to judge a nominated profile while the verifier scores a replacement design.

## Task 1: Bund Volume Calculation

Current world:

- Computes required bund capacity, net bund volume, wall height, and compliance per AS/NZS 1940.
- Inputs are container count, largest container volume, total stored volume, bund length/width/height, equipment count, and average equipment footprint.
- Hard mode hides equipment count and footprint area.
- The engine requires the greater of 110 percent of the largest container and 25 percent of total stored volume.
- The engine subtracts simplified equipment displacement and returns compliance as `1.0` or `0.0`.
- If total stored volume is less than largest container volume, the engine clamps total stored volume upward before validation.

Multimodal expansion:

- Best first modality: bund layout plan plus container/equipment inventory.
- A layout can expose bund dimensions, wall height, tank footprints, transformer plinths, pumps, generators, and maintenance equipment.
- A schedule can expose container volumes and whether total stored volume has been entered consistently.
- A hazardous materials register can supply flammable/combustible-liquid context and containment standard.

Requirements:

- Bund plan with internal dimensions and wall height.
- Container inventory with largest single container and total stored volume.
- Equipment layout with counted items and footprint areas.
- Explicit rule trace for 110 percent largest versus 25 percent total.
- Compliance record that states whether displacement was included.

Harness opportunities:

- Add source-geometry gate for bund internal dimensions.
- Add inventory gate that total volume includes the largest container instead of relying on engine clamping.
- Add governing-rule gate for 110 percent versus 25 percent capacity.
- Add equipment-displacement gate for hidden hard-mode parameters.
- Add compliance contradiction event if the numeric volume passes but the container inventory is inconsistent.

Natural products:

- `bund-volume-calculation -> pollutant-load-estimate` for industrial yards where spill containment and stormwater quality share a site plan.
- `bund-volume-calculation -> downpipe/gutter/drainage` where bunded areas drain to treatment or isolation systems.
- `bund-volume-calculation -> pump-power/npsh` in generator/fuel compounds with sump pumps or transfer pumps.

Meta-harness handles:

- `projection`: text inventory, bund plan, equipment layout, hazardous-materials register.
- `difference`: hide equipment count/footprint or remove container-volume consistency hints.
- `product`: industrial environmental-control package with containment, drainage, and pollutant checks.

## Task 2: Sediment Basin Sizing

Current world:

- Computes settling volume, sediment storage volume, and total basin volume.
- Inputs are catchment area, volumetric runoff coefficient, soil loss rate, cleanout interval, basin type, and permanent pool volume.
- Hard mode hides volumetric runoff coefficient and soil loss rate.
- Type D basins include settling and sediment storage; Type F basins add permanent pool volume.
- The engine ignores permanent pool volume for Type D basins.

Multimodal expansion:

- Best first modality: erosion and sediment control plan plus catchment/soil table.
- A construction staging plan can expose contributing catchment area and disturbed soil type.
- A rainfall/soil erodibility source can supply `Cv` and soil loss rate.
- A basin detail can expose whether the basin is Type D or Type F and whether permanent pool is relevant.

Requirements:

- Catchment plan with disturbed area and drainage direction.
- Soil or erosion-risk source for `Cv` and soil loss rate.
- Cleanout interval from maintenance plan or standard assumption.
- Basin type source and permanent pool evidence for Type F.
- Component volume ledger for settling, sediment storage, and pool.

Harness opportunities:

- Add catchment geometry gate for contributing area.
- Add source-table gate for hidden `Cv` and soil loss rate.
- Add branch gate for Type D versus Type F.
- Add event trigger if a model adds permanent pool volume to a Type D basin.
- Add maintenance gate for cleanout interval provenance.

Natural products:

- `sediment-basin-sizing -> pollutant-load-estimate` as a construction water-quality package.
- `rational-method/scs-curve-number -> sediment-basin-sizing` when hydrology generates contributing runoff context.
- `sediment-basin-sizing -> detention-volume-preliminary` for projects where temporary sediment basins and permanent basins share earthworks.

Meta-harness handles:

- `projection`: catchment plan, soil table, erosion-control plan, basin detail.
- `difference`: hide `Cv`, soil loss rate, or basin-type source labels.
- `product`: construction-phase stormwater and erosion-control package.

## Task 3: Sewer Pipe Sizing

Current world:

- Selects the smallest standard gravity sewer diameter whose full-pipe capacity exceeds design flow.
- Inputs are design flow, upstream invert, downstream invert, pipe length, and Manning roughness.
- Hard mode hides Manning roughness.
- The engine computes pipe slope using the absolute invert difference, then selects from standard diameters.
- Outputs include selected diameter, pipe slope, full-pipe velocity, and approximate flow depth ratio.

Multimodal expansion:

- Best first modality: sewer long section plus pipe/material schedule.
- A long section can expose invert levels, reach length, grade, direction, and maintenance-hole labels.
- A schedule can expose pipe material for Manning roughness inference.
- A design flow table can connect upstream population/catchment assumptions to the reach.

Requirements:

- Sewer long section with upstream/downstream inverts and pipe length.
- Flow direction or maintenance-hole ordering so the absolute-slope simplification is visible.
- Pipe material/source table for Manning roughness.
- Standard diameter table and selected-diameter trace.
- Capacity and flow-depth ratio evidence.

Harness opportunities:

- Add source-geometry gate for invert and length extraction.
- Add directionality gate if future variants care which invert is upstream.
- Add source-authority gate for Manning roughness.
- Add standard-size selection gate for smallest adequate diameter.
- Add handoff gate to `sewer-slope-check` using selected diameter and slope.

Natural products:

- `sewer-pipe-sizing -> sewer-slope-check` as a design then compliance chain.
- `sewer-pipe-sizing -> pump-power-calc` where a gravity network discharges to a lift station.
- `sewer-pipe-sizing -> hgl/headloss` if sewer and stormwater hydraulics are combined into network tasks.

Meta-harness handles:

- `projection`: long section, pipe schedule, flow table, standard-diameter table.
- `difference`: hide roughness, remove pipe material labels, or remove grade annotation.
- `product`: gravity sewer design reach package.

## Task 4: Sewer Slope Check

Current world:

- Computes full-pipe velocity, capacity, and self-cleansing compliance.
- Inputs are pipe diameter, pipe slope, and Manning roughness.
- Hard mode hides Manning roughness.
- Compliance is `1.0` if velocity lies between 0.6 m/s and 4.0 m/s.
- The task is a check rather than a selection routine.

Multimodal expansion:

- Best first modality: sewer profile/long section plus material note.
- A profile can expose pipe diameter and slope; a schedule or standard note can expose roughness.
- A compliance table can expose minimum self-cleansing and maximum scour velocity.

Requirements:

- Pipe diameter and grade source.
- Pipe material/source for Manning roughness.
- Velocity-limit source or task-level declared constants.
- Explicit pass/fail record for low-velocity and high-velocity failures.

Harness opportunities:

- Add slope percent-to-fraction conversion gate.
- Add source-authority gate for Manning roughness.
- Add velocity-range branch gate: below minimum, within range, or above maximum.
- Add handoff gate from `sewer-pipe-sizing` selected diameter/slope to this check.
- Add contradiction event if final compliance disagrees with computed velocity.

Natural products:

- `sewer-pipe-sizing -> sewer-slope-check` as the obvious two-step chain.
- `sewer-slope-check -> pump station` where inadequate gravity grades trigger lift-station alternatives.
- `sewer-slope-check -> maintenance/condition` future tasks where roughness changes with aging.

Meta-harness handles:

- `projection`: sewer profile, pipe schedule, standards velocity table.
- `difference`: hide roughness or velocity-limit labels.
- `product`: sewer design compliance package.

## Task 5: NPSH Calculation

Current world:

- Computes pressure head, NPSH available, NPSH margin, and margin ratio.
- Inputs are atmospheric pressure, vapour pressure, specific gravity, static suction head, friction loss, and NPSH required.
- Hard mode hides vapour pressure and specific gravity.
- Static suction head is signed: positive for flooded suction and negative for suction lift.
- Instruction notes a margin ratio target above 1.35, but the task does not output explicit compliance.

Multimodal expansion:

- Best first modality: pump station section plus pump datasheet and fluid-property table.
- A wet-well/dry-well section can expose static suction head sign and suction pipe route.
- A datasheet can expose NPSHr at the duty point.
- A fluid table can expose vapour pressure and specific gravity from fluid type and temperature.

Requirements:

- Suction arrangement section with liquid level, pump centreline, and static head sign.
- Suction pipe layout or loss calculation source for friction loss.
- Pump curve/datasheet source for NPSHr.
- Fluid-property source for hidden vapour pressure and specific gravity.
- Margin assessment record if compliance is added.

Harness opportunities:

- Add sign-convention gate for flooded suction versus suction lift.
- Add source-authority gate for fluid properties.
- Add datasheet extraction gate for NPSHr.
- Add pressure-head construction gate using kPa-to-Pa conversion.
- Add compliance gate for margin ratio if the task is extended.

Natural products:

- `npsh-calculation -> pump-power-calc` as a pump station design pair.
- `hazen-williams/darcy headloss -> npsh-calculation` through suction friction loss.
- `sewer-pipe-sizing -> npsh/pump-power` in sewer lift-station package tasks.

Meta-harness handles:

- `projection`: pump station section, pump curve, fluid table, suction-loss calculation.
- `difference`: hide fluid properties, remove pump centreline labels, or remove NPSHr row labels.
- `product`: pump station duty and suction reliability package.

## Task 6: Pump Power Calculation

Current world:

- Computes hydraulic power, brake power, and motor input power.
- Inputs are flow rate, total dynamic head, pump efficiency, and motor efficiency.
- Hard mode hides pump and motor efficiencies.
- The engine converts L/s to m3/s and percent efficiencies to decimal fractions.
- No compliance or motor selection output is currently included.

Multimodal expansion:

- Best first modality: pump duty sheet plus pump/motor efficiency table.
- A system curve or duty-point note can provide flow and total dynamic head.
- A pump datasheet can provide pump efficiency; a motor schedule can provide motor efficiency.
- A single-line diagram could connect motor input power to electrical supply tasks in later cross-discipline products.

Requirements:

- Duty-point source for flow and head.
- Pump efficiency source at the stated duty point.
- Motor efficiency source or schedule.
- Unit conversion evidence for L/s and percent efficiencies.
- Optional motor-size selection table if extended beyond power calculation.

Harness opportunities:

- Add duty-point source gate.
- Add efficiency-table extraction gate for hidden hard-mode values.
- Add percent-to-decimal conversion gate.
- Add handoff gate from hydraulic headloss/system-curve tasks to total dynamic head.
- Add cross-discipline handoff to electrical load tasks if combined later.

Natural products:

- `pump-power-calc -> npsh-calculation` as the paired pump station check.
- `headloss/system curve -> pump-power-calc` for full duty-point assembly.
- `pump-power-calc -> electrical/load-combination` future package for motor supply sizing.

Meta-harness handles:

- `projection`: duty sheet, pump curve, motor schedule, system curve.
- `difference`: hide efficiencies or remove duty-point labels.
- `product`: pump station hydraulic and electrical interface package.

## Task 7: Downpipe Sizing

Current world:

- Computes design flow per downpipe, selects a standard downpipe diameter, returns selected capacity, and compliance.
- Inputs are roof catchment area, rainfall intensity, and number of downpipes.
- Hard mode hides rainfall intensity.
- The engine uses an embedded AS/NZS 3500.3 capacity table for round uPVC downpipes.
- If no standard diameter is adequate, it selects the largest size and returns non-compliance.

Multimodal expansion:

- Best first modality: roof plan plus rainfall intensity table.
- A roof plan can expose catchment area, flow path, and downpipe count.
- A site/ARI note can identify the relevant design rainfall intensity.
- A capacity table can supply standard downpipe selection.

Requirements:

- Roof catchment delineation with area and number of downpipes.
- Rainfall intensity source tied to location and design recurrence interval.
- Standard downpipe capacity table.
- Selection trace showing the smallest adequate size.
- Compliance record for oversized flow cases.

Harness opportunities:

- Add roof-area extraction gate.
- Add rainfall-table source gate.
- Add standard-size selection gate.
- Add event trigger if the model forgets to divide catchment flow by number of downpipes.
- Add product-world handoff from gutters to downpipes or roof drainage to site stormwater.

Natural products:

- `gutter-sizing -> downpipe-sizing` as a roof drainage design chain.
- `downpipe-sizing -> rational-method/pipe-capacity` where roof discharge enters site stormwater.
- `downpipe-sizing -> pollutant-load-estimate` when roof catchments contribute to runoff volume.

Meta-harness handles:

- `projection`: roof plan, rainfall table, downpipe schedule, capacity table.
- `difference`: hide rainfall intensity or remove downpipe-count labels.
- `product`: building roof drainage package.

## Task 8: Gutter Sizing

Current world:

- Computes roof design flow, adjusted gutter capacity, required gutter size, and compliance.
- Inputs are roof catchment area, rainfall intensity, nominated gutter profile, and gutter grade.
- Hard mode hides rainfall intensity.
- The engine validates the nominated gutter profile, computes its capacity internally, then selects the smallest standard gutter that handles the design flow.
- The output reports the selected required size and selected capacity rather than whether the originally nominated gutter profile is adequate.

Multimodal expansion:

- Best first modality: roof drainage plan plus gutter profile/grade schedule.
- A roof plan can expose catchment area and gutter run.
- A schedule can expose nominated gutter profile and installed grade.
- A rainfall intensity table can provide the hidden hard-mode value.
- A standards capacity table can become an explicit source artifact rather than embedded code.

Requirements:

- Roof catchment area source.
- Gutter profile and grade source.
- Rainfall intensity source.
- Capacity table with reference grade and grade-scaling rule.
- Explicit task contract: check nominated gutter, select required gutter, or report both.

Harness opportunities:

- Add roof-area and gutter-grade extraction gates.
- Add rainfall-table source gate.
- Add grade-scaling construction gate using square-root relation.
- Add standard-size selection gate.
- Add repair target for the nominated-profile versus required-profile contract before multimodal expansion.

Natural products:

- `gutter-sizing -> downpipe-sizing` as a roof drainage chain.
- `gutter-sizing -> roadway-spread/open-channel` in mixed building/site drainage packages.
- `gutter-sizing -> solar-array-wind-load` only through shared roof geometry if building roof context is composed later.

Meta-harness handles:

- `projection`: roof plan, gutter schedule, rainfall table, standards capacity table.
- `difference`: hide rainfall intensity or remove gutter grade/profile labels.
- `product`: roof drainage compliance/design package.

## Task 9: Pollutant Load Estimate

Current world:

- Computes annual runoff volume and annual TSS/TP/TN loads using the EMC method.
- Inputs are catchment area, annual rainfall, runoff coefficient, and three EMC values.
- Hard mode hides EMC values.
- The engine uses `V = C * P * A * 10` and `L = EMC * V / 1000`.
- The instruction includes typical EMC values by land use.

Multimodal expansion:

- Best first modality: catchment land-use plan plus rainfall and EMC table.
- A GIS-like catchment map can expose area and land-use class.
- A rainfall/climate table can expose mean annual rainfall.
- A water-quality guideline table can expose EMC values for land use.
- Treatment train tasks could consume the pollutant loads later.

Requirements:

- Catchment boundary and area source.
- Land-use source for EMC selection.
- Annual rainfall source.
- Runoff coefficient source, ideally tied to impervious fraction.
- Pollutant-load evidence for TSS, TP, and TN separately.

Harness opportunities:

- Add land-use classification gate for hidden EMC values.
- Add area/rainfall source gates.
- Add unit conversion gate for ha-mm to m3 and mg/L-m3 to kg.
- Add pollutant-specific construction gates so TSS, TP, and TN cannot be silently swapped.
- Add product-world handoff into sediment basin or treatment train tasks.

Natural products:

- `pollutant-load-estimate -> sediment-basin-sizing` for construction or permanent treatment sizing.
- `pollutant-load-estimate -> scs/rational-method` through shared catchment/runoff context.
- `pollutant-load-estimate -> bund-volume-calculation` in industrial sites where spills and chronic runoff quality both matter.

Meta-harness handles:

- `projection`: catchment map, land-use table, rainfall table, EMC table.
- `difference`: hide EMC values or remove land-use labels.
- `product`: stormwater quality assessment package.

## Cross-Slice Threads Opened

This pass opens the civil systems layer that connects earlier hydrology/hydraulics to built assets and environmental controls:

- roof drainage package: `gutter-sizing` and `downpipe-sizing` feeding stormwater pipe/HGL checks;
- sewer design package: `sewer-pipe-sizing` followed by `sewer-slope-check`, then pump station alternatives where gravity is not enough;
- pump station package: `npsh-calculation`, `pump-power-calc`, headloss tasks, and future electrical motor/load tasks;
- construction environmental package: `pollutant-load-estimate`, `sediment-basin-sizing`, and catchment hydrology;
- industrial containment package: `bund-volume-calculation`, pollutant load, drainage isolation, and pump/sump tasks.

## Meta-Harness Implications

The practical meta-harness shape here is a source-table and standard-selection harness:

- select the right row from a source table;
- apply a simple formula;
- choose the smallest adequate standard size or compliance state;
- preserve enough evidence to prove the model did not guess the hidden table value.

The best event candidates are:

- wrong rainfall, roughness, EMC, efficiency, or fluid-property source row;
- wrong standard-size selection where a larger or smaller standard item is chosen;
- compliance state disagrees with computed capacity/velocity/volume;
- unit conversion error between litres, cubic metres, hectares, millimetres, kPa, percent, and fractions;
- task-contract ambiguity between checking a nominated asset and designing a replacement asset.
