# ABOUTME: Detailed task-world review for electrical lighting design, uniformity, and energy performance tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the third electrical discipline slice.

# Electrical Lighting And Energy Performance Pass 016

Review date: 2026-06-28

Reviewed task cards:

- `electrical/lighting-design/lux-level-calculation`
- `electrical/interior-lighting/interior-uniformity`
- `electrical/road-lighting/road-uniformity-check`
- `electrical/sports-lighting/sports-illuminance-uniformity`
- `electrical/energy-performance/leni-calculation`
- `electrical/energy-performance/road-aeci-calculation`
- `electrical/energy-performance/road-pdi-calculation`

Source files read for this pass:

- `src/aec_bench/templates/builtin/electrical/lux_level_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/interior_uniformity/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/road_uniformity_check/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/sports_illuminance_uniformity/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/leni_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/road_aeci_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/electrical/road_pdi_calculation/{params.toml,instruction.md,engine.py}`

## Slice Read

This lighting slice is compact and highly composable. The task worlds want luminaire schedules, room and road geometry, lighting layouts, photometric calculation grids, maintenance/utilisation assumptions, target-class tables, operating-hour schedules, dimming profiles, daylight/control factors, and illuminated-area definitions.

The strongest composition axis is one lighting design evidence package:

- room/field/road geometry plus luminaire flux and count produce average illuminance;
- photometric grid minima, maxima, and averages produce uniformity checks;
- the same installed/system power and area produce LENI, AECI, PDI, and electrical load handoffs;
- hidden factors are mostly source assumptions: utilisation factor, target class/uniformity, daylight factor, dimmed hours, and illuminated area.

The practical meta-harness opportunity is source consistency. A model can easily use a room area from one drawing, a photometric grid from another, and a power value from a different option. A good world sidecar should bind geometry, luminaires, grid, target class, and energy assumptions to the same design option.

## Task 1: Lux Level Calculation

Current world:

- Computes average illuminance, uniformity ratio, specific luminaire power density, and target margin.
- Inputs are room dimensions, luminaire count/flux, utilisation factor, maintenance factor, lighting power, minimum illuminance, and target illuminance.
- Hard mode hides `utilisation_factor`.
- Uniformity is calculated from supplied minimum illuminance divided by computed average illuminance.

Multimodal expansion:

- Best first modality: room lighting layout plus luminaire schedule.
- A calculation-grid variant can source minimum illuminance from photometric output.
- A hard variant can infer utilisation factor from room index/surface reflectance or design note.

Requirements:

- Room dimensions/source area.
- Luminaire count and flux source.
- Utilisation and maintenance factor source.
- Lighting power source.
- Target/minimum illuminance evidence.

Harness opportunities:

- Add room-geometry extraction gate.
- Add luminaire schedule source gate.
- Add utilisation-factor inference gate.
- Add average/minimum/target consistency gate.

Natural products:

- `lux-level-calculation -> interior-uniformity`.
- `lux-level-calculation -> leni-calculation`.
- `lux-level-calculation -> power-load-calculation` for lighting load.

Meta-harness handles:

- `projection`: room plan, luminaire schedule, photometric grid, design criteria table.
- `difference`: include multiple luminaire options or room zones.
- `product`: interior illuminance design record.

## Task 2: Interior Uniformity

Current world:

- Computes task uniformity, surround-to-task ratio, and background-to-task ratio.
- Inputs are task minimum/average, surround average, and background average illuminance.
- Hard mode hides `background_average_illuminance_lux`.
- The task is a ratio check, but it does not emit a compliance flag.

Multimodal expansion:

- Best first modality: lighting calculation grid with task, surround, and background zones.
- A drawing variant can require mapping grid regions to task/surround/background areas.
- A hard variant can source background values from a separate zone table.

Requirements:

- Task minimum and average source.
- Surround and background source.
- Zone classification evidence.
- Target criteria if extended to compliance.

Harness opportunities:

- Add photometric-grid zone gate.
- Add hidden background-source gate.
- Add ratio consistency gate.
- Add compliance extension gate.

Natural products:

- `lux-level-calculation -> interior-uniformity`.
- `interior-uniformity -> leni-calculation` as visual quality plus energy package.
- `interior-uniformity -> architectural room source package`.

Meta-harness handles:

- `projection`: photometric grid, room zoning plan, lighting criteria table.
- `difference`: swap task/surround/background labels.
- `product`: interior uniformity record.

## Task 3: Road Uniformity Check

Current world:

- Computes overall uniformity, longitudinal uniformity, and margin to target overall uniformity.
- Inputs are minimum/average luminance, longitudinal min/max luminance, and target overall uniformity.
- Hard mode hides `target_overall_uniformity`.
- It reports margin but not a binary compliance flag.

Multimodal expansion:

- Best first modality: road lighting photometric grid plus road lighting class table.
- A corridor variant can require selecting the road class and target from alignment/cross-section context.
- A hard variant can compare several road sections and identify the controlling uniformity margin.

Requirements:

- Luminance grid source.
- Longitudinal row/source evidence.
- Target uniformity source from road class.
- Road section identity.

Harness opportunities:

- Add road-class target gate.
- Add grid row/column selection gate.
- Add overall/longitudinal ratio gate.
- Add governing-section selection gate.

Natural products:

- `road-uniformity-check -> road-aeci-calculation`.
- `road-uniformity-check -> road-pdi-calculation`.
- `civil road geometry -> road-uniformity-check` through corridor class and section.

Meta-harness handles:

- `projection`: road lighting grid, road classification table, road cross-section, luminaire layout.
- `difference`: include multiple road classes or lighting grids.
- `product`: road lighting uniformity record.

## Task 4: Sports Illuminance Uniformity

Current world:

- Computes average horizontal illuminance, U1 min/max, U2 min/average, average illuminance margin, and U2 margin.
- Inputs are field geometry, luminaire count/flux, utilisation and maintenance factors, minimum/maximum illuminance, target average, and target U2.
- Hard mode hides `target_uniformity_u2`.
- The task combines lumen method average with photometric-grid min/max ratios.

Multimodal expansion:

- Best first modality: sports field lighting layout plus photometric grid.
- A competition-class variant can infer target average and U2 from sport/category.
- A hard variant can compare training and match-lighting scenarios.

Requirements:

- Field area source.
- Luminaire schedule source.
- Utilisation/maintenance factors.
- Photometric min/max source.
- Sport/class target source.

Harness opportunities:

- Add field geometry gate.
- Add sport/class target gate.
- Add grid min/max/average consistency gate.
- Add scenario selection gate.

Natural products:

- `sports-illuminance-uniformity -> power-load-calculation`.
- `sports-illuminance-uniformity -> energy performance` if operating schedules are added.
- `sports-illuminance-uniformity -> civil site/venue lighting package`.

Meta-harness handles:

- `projection`: field plan, luminaire layout, photometric grid, sport classification table.
- `difference`: mix training and match-class targets.
- `product`: sports lighting compliance record.

## Task 5: LENI Calculation

Current world:

- Computes annual lighting energy, LENI, and saving relative to reference LENI.
- Inputs are installed power, annual hours, control factor, daylight factor, zone area, and reference LENI.
- Hard mode hides `daylight_factor`.
- Control and daylight factors are applied multiplicatively to installed power and hours.

Multimodal expansion:

- Best first modality: lighting control schedule plus energy model zone table.
- A daylight variant can source daylight factor from facade orientation or daylight assessment.
- A hard variant can connect LENI to lux/uniformity outputs for the same zone.

Requirements:

- Installed power source.
- Operating hours source.
- Control and daylight factor source.
- Zone area source.
- Reference LENI source.

Harness opportunities:

- Add zone identity gate.
- Add daylight-factor source gate.
- Add energy intensity construction gate.
- Add reference-saving consistency gate.

Natural products:

- `lux-level-calculation/interior-uniformity -> leni-calculation`.
- `leni-calculation -> power-load-calculation`.
- `leni-calculation -> building energy report artifact`.

Meta-harness handles:

- `projection`: lighting schedule, control strategy, daylight report, energy model zone table.
- `difference`: include design power and metered power together.
- `product`: interior lighting energy performance record.

## Task 6: Road AECI Calculation

Current world:

- Computes annual energy and Annual Energy Consumption Index.
- Inputs are system power, full-output hours, dimmed hours, dimming level, and illuminated area.
- Hard mode hides `dimmed_hours_per_year`.
- The annual energy formula separates full-output and dimmed operation.

Multimodal expansion:

- Best first modality: road lighting control schedule plus luminaire power schedule.
- A route-section variant can source illuminated area from road geometry.
- A hard variant can infer dimmed hours from operating regime or curfew/night profile.

Requirements:

- System power source.
- Full-output and dimmed-hour source.
- Dimming level source.
- Illuminated area source.
- Annual energy evidence.

Harness opportunities:

- Add dimming schedule source gate.
- Add illuminated-area gate.
- Add full/dimmed energy separation gate.
- Add AECI consistency gate.

Natural products:

- `road-uniformity-check -> road-aeci-calculation`.
- `road-aeci-calculation -> road-pdi-calculation`.
- `road-aeci-calculation -> electrical power-load-calculation`.

Meta-harness handles:

- `projection`: road lighting schedule, control profile, road section geometry, luminaire power table.
- `difference`: include dusk-to-dawn hours and dimmed hours without labels.
- `product`: road lighting annual energy record.

## Task 7: Road PDI Calculation

Current world:

- Computes power density index and specific power density.
- Inputs are system power, maintained illuminance, and illuminated area.
- Hard mode hides `illuminated_area_m2`.
- It is a compact efficiency metric tied to lighting area and maintained illuminance.

Multimodal expansion:

- Best first modality: road geometry plus luminaire/system power schedule.
- A hard variant can derive illuminated area from carriageway width and section length.
- A composition variant can tie maintained illuminance to road lighting class or photometric grid.

Requirements:

- System power source.
- Maintained illuminance source.
- Illuminated area source.
- Road section identity.

Harness opportunities:

- Add area derivation gate.
- Add maintained-illuminance source gate.
- Add PDI role gate separate from AECI.
- Add energy-efficiency comparison gate.

Natural products:

- `road-uniformity-check -> road-pdi-calculation`.
- `road-aeci-calculation <-> road-pdi-calculation`.
- `civil road geometry -> road-pdi-calculation`.

Meta-harness handles:

- `projection`: road geometry, lighting layout, photometric report, system power schedule.
- `difference`: mix illuminated area, road reserve area, and carriageway area.
- `product`: road lighting power density record.

## Cross-Slice Product Worlds

### Interior Lighting Quality And Energy Package

Candidate chain:

1. Read room geometry, luminaire schedule, and photometric grid.
2. Compute average illuminance and task uniformity.
3. Read control/daylight/operating assumptions.
4. Compute LENI and reference saving.
5. Handoff installed lighting power to electrical load tasks.

Why it is interesting:

- It combines visual performance and energy performance in one zone.
- It tests whether geometry, grid, power, and control assumptions belong to the same design option.
- It supports multimodal variants from plans, schedules, photometric tables, and energy model extracts.

### Road Lighting Compliance And Energy Package

Candidate chain:

1. Read road section geometry, luminaire layout, and road class.
2. Compute road uniformity and target margin.
3. Compute AECI from power and dimming schedule.
4. Compute PDI from maintained illuminance and illuminated area.

Why it is interesting:

- It combines road/civil geometry, lighting-class source authority, and energy metrics.
- It exposes common area-definition errors.
- It can pipe into road corridor dashboards or asset upgrade evaluations.

### Sports Field Lighting Package

Candidate chain:

1. Read field geometry and sports lighting class.
2. Compute average illuminance from luminaire flux/count and factors.
3. Compute U1/U2 from grid min/max/average.
4. Handoff lighting power to supply sizing or energy records.

Why it is interesting:

- It is a domain-specific multimodal package with field drawings and photometric grids.
- It has clear scenario mutations: training, match, broadcast, community, stadium.
- It can test whether models keep target average and target uniformity separate.

## Repair And Extension Notes

- Lighting tasks often compute margins but not binary compliance flags. Composed product worlds should add verifier gates that check margin sign and target source before declaring pass/fail.
- `lux-level-calculation` uses a supplied minimum illuminance to compute uniformity while computing average by lumen method. Multimodal variants should make the minimum source explicit, usually a photometric grid or design assumption.
- Road AECI and PDI both use illuminated area, but from different metric stories. A shared area sidecar should record whether the area comes from carriageway, field, road section, task plane, or room floor.
- Hidden target-class parameters are especially suitable for meta-harness differences: change lighting class while keeping geometry and luminaires fixed, then verify which criteria move.
