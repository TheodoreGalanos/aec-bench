# ABOUTME: Detailed task-world review for mechanical treatment-process, activated-sludge, clarifier, and solids tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the second mechanical discipline slice.

# Mechanical Treatment Process And Solids Pass 011

Review date: 2026-06-28

Reviewed task cards:

- `mechanical/fundamental-calculations/chemical-dosing`
- `mechanical/fundamental-calculations/hrt-calculation`
- `mechanical/reactor-sizing/cstr-volume`
- `mechanical/reactor-sizing/pfr-volume`
- `mechanical/fundamental-calculations/srt-calculation`
- `mechanical/nutrient-removal/nitrification-srt`
- `mechanical/activated-sludge/oxygen-requirements`
- `mechanical/activated-sludge/sludge-production`
- `mechanical/sludge-handling/biogas-production`
- `mechanical/fundamental-calculations/mlss-inventory`
- `mechanical/clarifier-design/slr-calculation`
- `mechanical/clarifier-design/sor-calculation`

Source files read for this pass:

- `src/aec_bench/templates/builtin/mechanical/chemical_dosing/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/hrt_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/cstr_volume/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/pfr_volume/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/srt_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/nitrification_srt/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/oxygen_requirements/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/sludge_production/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/biogas_production/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/mlss_inventory/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/slr_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/sor_calculation/{params.toml,instruction.md,engine.py}`

## Slice Read

This slice is also all-scalar and all-given today. The real task-world opportunity is to turn treatment process calculations into a plant evidence package: process flow diagrams, design-basis tables, influent/effluent laboratory data, basin layouts, clarifier plans, WAS/RAS records, sludge balance sheets, digester records, gas data, chemical product datasheets, and operating criteria.

The natural composition axis is a wastewater process basis:

- flow and concentration loads feed chemical dosing, HRT, reactor volume, oxygen demand, sludge production, clarifier loading, and solids retention;
- MLSS inventory, wasting, and effluent loss feed SRT, which should be compared with required nitrification SRT;
- sludge production can feed volatile-solids and biogas production if a digestion task world is added around it;
- clarifier SOR and SLR share flow, surface area, and solids concentration but test different compliance stories.

The strongest meta-harness setting is staged process-accounting. A model must preserve whether a value is an influent load, effluent load, biological inventory, daily loss, design criterion, or equipment/feed requirement. Without those roles, many outputs are numerically plausible but operationally nonsensical.

## Task 1: Chemical Dosing

Current world:

- Computes active mass feed, product mass feed, volume feed, and annual product consumption.
- Inputs are flow, target active dose, product strength, and product density.
- The unit conversion uses `flow_rate_m3_d * target_dose_mg_l / 1000` to obtain kg/d active feed.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: chemical product datasheet plus dosing design basis.
- A plant-schedule variant can require selecting the correct chemical and strength from a chemical storage/feed schedule.
- A hard variant can include duty/standby dosing pumps and require checking product feed against pump capacity.

Requirements:

- Flow source.
- Target dose source.
- Product strength and density source.
- Unit contract between mg/L, m3/d, kg/d, and L/d.
- Optional dosing pump capacity source for equipment acceptance.

Harness opportunities:

- Add chemical datasheet source-authority gate.
- Add active-vs-product-mass gate.
- Add annual consumption consistency gate.
- Add dosing pump capacity handoff if equipment sizing is introduced.

Natural products:

- `chemical-dosing -> pump_power_efficiency/electrical load` if dosing pump power is added.
- `chemical-dosing -> treatment process basis` where dose depends on flow and concentration.
- `chemical-dosing -> civil bund-volume-calculation` for chemical storage containment.

Meta-harness handles:

- `projection`: chemical datasheet, dosing schedule, process design basis.
- `difference`: provide multiple product strengths or trade names.
- `product`: chemical feed and storage basis.

## Task 2: HRT Calculation

Current world:

- Computes hydraulic retention time in days and hours plus flow in m3/h.
- Inputs are reactor volume and flow rate.
- It is a simple volume/flow closure gate.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: basin plan/section with dimensions and process flow rate.
- A process-flow-diagram variant can require choosing the relevant unit volume and excluding bypass/storage volume.
- A hard variant can compare HRT for average, peak, and minimum flow cases.

Requirements:

- Reactor volume source or geometry-derived volume.
- Flow source and flow case label.
- Unit contract for days and hours.
- Optional process-unit role label.

Harness opportunities:

- Add unit-volume extraction gate.
- Add flow-case selection gate.
- Add geometry-to-volume construction gate.
- Add HRT handoff to reactor or treatment compliance tasks.

Natural products:

- `hrt-calculation -> cstr-volume/pfr-volume` as a treatment reactor sizing comparison.
- `hrt-calculation -> chemical-dosing` when dose contact time matters.
- `hrt-calculation -> civil sediment-basin-sizing` as a cross-domain detention/retention analogue.

Meta-harness handles:

- `projection`: process flow diagram, basin plan, section, design flow table.
- `difference`: include dead volume, freeboard, or standby basin distractors.
- `product`: treatment unit retention-time record.

## Task 3: CSTR Volume

Current world:

- Computes outlet concentration, outlet reaction rate, space time, and required volume for a first-order CSTR.
- Inputs are volumetric flow, inlet concentration, required conversion, and rate constant.
- The CSTR space time is `X / (k * (1 - X))`.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: reactor design basis plus reaction-kinetics table.
- A method-comparison variant can pair the same conversion requirement with the PFR template.
- A hard variant can require extracting conversion from an inlet/outlet concentration target.

Requirements:

- Flow and inlet concentration source.
- Conversion criterion source.
- Rate constant source and temperature condition.
- Reactor-model assumption: complete mixing, first-order, constant density.

Harness opportunities:

- Add reactor-model assumption gate.
- Add conversion construction gate.
- Add CSTR/PFR comparison gate.
- Add source-authority gate for rate constant.

Natural products:

- `cstr-volume <-> pfr-volume` as a reactor model comparison.
- `cstr-volume -> hrt-calculation` where required volume becomes retention time.
- `cstr-volume -> chemical-dosing` in treatment process control worlds.

Meta-harness handles:

- `projection`: reaction design basis, kinetics table, process flow diagram.
- `difference`: hide whether reactor is CSTR or plug-flow.
- `product`: reactor sizing alternative.

## Task 4: PFR Volume

Current world:

- Computes molar feed, outlet concentration, space time, and required volume for a first-order plug-flow reactor.
- Inputs match the CSTR task: flow, inlet concentration, conversion, and rate constant.
- The PFR space time is `-ln(1 - X) / k`.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: process design basis with reaction model note.
- A flow-sheet variant can require selecting plug-flow assumptions from channel/tank geometry.
- A hard variant can compare PFR and CSTR volume implications for the same conversion target.

Requirements:

- Flow and concentration source.
- Conversion target source.
- Rate constant and temperature source.
- Plug-flow/first-order assumption source.

Harness opportunities:

- Add reactor-type source gate.
- Add logarithmic space-time construction gate.
- Add molar-feed consistency gate.
- Add method-comparison gate with `cstr-volume`.

Natural products:

- `pfr-volume <-> cstr-volume`.
- `pfr-volume -> hrt-calculation`.
- `pfr-volume -> process layout/drawing` where required volume drives physical footprint.

Meta-harness handles:

- `projection`: reaction data sheet, flow sheet, reactor layout.
- `difference`: include mixed reactor and plug-flow cues in conflict.
- `product`: plug-flow reactor sizing record.

## Task 5: SRT Calculation

Current world:

- Computes solids in system, wasted solids, effluent solids loss, total solids loss, and SRT.
- Inputs are aeration volume, MLSS, WAS flow/TSS, effluent TSS, and effluent flow.
- It uses kg/d solids accounting and divides inventory by daily loss.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: aeration basin volume record plus WAS and effluent operating data.
- A plant-operations variant can require selecting the correct day or average period from trend tables.
- A hard variant can compare actual SRT against required nitrification SRT.

Requirements:

- Basin volume source.
- MLSS lab source.
- WAS flow and TSS source.
- Effluent flow and TSS source.
- Time-basis consistency.

Harness opportunities:

- Add inventory construction gate.
- Add daily solids-loss source gate.
- Add time-window consistency gate.
- Add actual-vs-required SRT compliance gate with `nitrification-srt`.

Natural products:

- `mlss-inventory -> srt-calculation -> nitrification-srt`.
- `srt-calculation -> sludge-production` through solids age.
- `srt-calculation -> oxygen-requirements` where sludge production affects carbonaceous demand.

Meta-harness handles:

- `projection`: operating trend table, lab report, basin volume schedule, sludge balance sheet.
- `difference`: mix WAS and RAS streams or daily and hourly records.
- `product`: activated-sludge solids age record.

## Task 6: Nitrification SRT

Current world:

- Computes temperature-corrected growth, substrate factor, oxygen factor, net growth, and required SRT.
- Inputs are maximum growth, theta, temperature, ammonia, half-saturation constants, dissolved oxygen, decay rate, and safety factor.
- The engine raises an error if net growth is non-positive.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: process design basis plus temperature/ammonia/DO design table.
- A seasonal variant can require selecting the cold-weather governing temperature.
- A hard variant can compare actual SRT from operations against required nitrification SRT.

Requirements:

- Kinetic constants source.
- Wastewater temperature source.
- Ammonia and DO source.
- Safety factor source.
- Actual SRT handoff if checking compliance.

Harness opportunities:

- Add temperature-correction gate.
- Add substrate and oxygen limitation gates.
- Add infeasible-net-growth event gate.
- Add actual-vs-required SRT gate.

Natural products:

- `srt-calculation -> nitrification-srt` as actual/required solids-age check.
- `nitrification-srt -> oxygen-requirements` where nitrification load drives oxygen demand.
- `nitrification-srt -> process upgrade meta-harness event` when required SRT exceeds available solids age.

Meta-harness handles:

- `projection`: design criteria table, seasonal temperature record, lab table, operating DO trend.
- `difference`: include warm and cold weather rows and force governing-case selection.
- `product`: nitrification solids-age requirement.

## Task 7: Oxygen Requirements

Current world:

- Computes BOD removed, carbonaceous oxygen, nitrogenous oxygen, denitrification credit, and total oxygen demand.
- Inputs are flow, influent/effluent BOD, influent/effluent TKN, sludge production, and denitrified nitrogen.
- The engine clamps carbonaceous oxygen and total oxygen to zero when the calculated value would be negative.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: influent/effluent lab report plus process design basis.
- A nutrient-removal variant can require extracting denitrification credit from a nitrogen balance.
- A hard variant can join sludge production output into the oxygen calculation.

Requirements:

- Flow source.
- Influent and effluent BOD/TKN source.
- Sludge production source or handoff.
- Denitrified nitrogen source.
- Branch evidence for zero-clamp cases.

Harness opportunities:

- Add load-conversion gates for BOD, nitrogen, and denitrified nitrogen.
- Add sludge-production handoff gate.
- Add oxygen-credit branch gate.
- Add clamp-event gate for negative carbonaceous or total demand.

Natural products:

- `sludge-production -> oxygen-requirements`.
- `nitrification-srt -> oxygen-requirements`.
- `oxygen-requirements -> mechanical air-demand` for aeration blower sizing.

Meta-harness handles:

- `projection`: lab report, process flow diagram, nitrogen balance, aeration design basis.
- `difference`: include BOD/TKN rows from different sampling periods.
- `product`: activated-sludge aeration oxygen demand.

## Task 8: Sludge Production

Current world:

- Computes BOD removed, observed yield, biomass production, primary solids, and total sludge.
- Inputs are flow, influent/effluent BOD, influent TSS, primary TSS removal, yield coefficient, decay coefficient, SRT, and VSS/TSS ratio.
- Observed yield decreases with decay coefficient and SRT.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: process design basis plus influent lab data and sludge-yield assumptions.
- A plant-operations variant can source SRT from the SRT calculation task.
- A digestion variant can send sludge/volatile solids onward to biogas production.

Requirements:

- Flow and concentration source.
- Primary removal source.
- Yield/decay coefficient source.
- SRT source or handoff.
- VSS/TSS conversion source.

Harness opportunities:

- Add BOD-removal load gate.
- Add observed-yield construction gate.
- Add primary-solids source gate.
- Add VSS/TSS conversion gate.

Natural products:

- `srt-calculation -> sludge-production`.
- `sludge-production -> oxygen-requirements`.
- `sludge-production -> biogas-production` if volatile solids feed is derived.

Meta-harness handles:

- `projection`: lab report, process design basis, sludge balance, primary clarifier record.
- `difference`: mix VSS and TSS values in the source pack.
- `product`: sludge mass balance record.

## Task 9: Biogas Production

Current world:

- Computes volatile solids destroyed, biogas volume, methane volume, and methane energy.
- Inputs are volatile solids feed, volatile solids destruction, biogas yield, and methane fraction.
- The methane energy factor is `9.97 kWh/m3`.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: digester feed record plus gas yield/design-basis table.
- A plant-operations variant can reconcile VS feed from sludge production and VSS/TSS assumptions.
- A hard variant can compare estimated methane energy against CHP or boiler demand.

Requirements:

- Volatile solids feed source.
- VS destruction source.
- Biogas yield source.
- Methane fraction source.
- Energy conversion factor source if made explicit.

Harness opportunities:

- Add VS feed handoff gate.
- Add gas-yield source-authority gate.
- Add methane fraction range gate.
- Add energy handoff gate to electrical/thermal use worlds.

Natural products:

- `sludge-production -> biogas-production`.
- `biogas-production -> electrical power/battery or heat recovery` if energy-use templates are added.
- `biogas-production -> chemical-dosing` only as a shared plant operations record, not a direct numeric chain.

Meta-harness handles:

- `projection`: digester feed log, gas meter record, design yield table, energy use schedule.
- `difference`: include wet sludge feed and volatile solids feed in the same pack.
- `product`: anaerobic digestion gas and energy estimate.

## Task 10: MLSS Inventory

Current world:

- Computes MLSS inventory, MLVSS inventory, and inert solids inventory.
- Inputs are aeration volume, MLSS concentration, and MLVSS fraction.
- It is a compact inventory decomposition task.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: aeration basin schedule plus lab MLSS/MLVSS report.
- A drawing variant can derive aeration volume from basin dimensions.
- A hard variant can feed inventory into actual SRT calculation.

Requirements:

- Basin volume source.
- MLSS source.
- MLVSS fraction source.
- Solids inventory handoff.

Harness opportunities:

- Add basin-volume extraction gate.
- Add MLSS/MLVSS lab source gate.
- Add inert-solids decomposition gate.
- Add inventory handoff gate to SRT.

Natural products:

- `mlss-inventory -> srt-calculation`.
- `mlss-inventory -> slr-calculation` through clarifier solids mass flow context.
- `mlss-inventory -> oxygen-requirements` as part of activated-sludge state.

Meta-harness handles:

- `projection`: basin plan, lab report, operating summary.
- `difference`: confuse MLSS concentration with inventory.
- `product`: mixed-liquor inventory record.

## Task 11: SLR Calculation

Current world:

- Computes solids mass flow, solids loading rate, utilisation ratio, compliance margin, and criterion-satisfied flag.
- Inputs are total flow, MLSS concentration, clarifier surface area, and maximum SLR.
- The pass flag is `1.0` when SLR is less than or equal to the maximum.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: clarifier plan plus design criteria table.
- A plant variant can source total flow and MLSS from operating records.
- A hard variant can run SOR and SLR together and identify which criterion governs.

Requirements:

- Flow source.
- MLSS source.
- Clarifier surface area source.
- Maximum SLR criterion source.
- Pass/fail evidence.

Harness opportunities:

- Add clarifier area extraction gate.
- Add solids mass-flow construction gate.
- Add criterion-source gate.
- Add pass-flag consistency gate.

Natural products:

- `mlss-inventory/srt-calculation -> slr-calculation` through MLSS context.
- `slr-calculation <-> sor-calculation` as clarifier dual-criterion package.
- `slr-calculation -> process upgrade event` when solids loading controls clarifier expansion.

Meta-harness handles:

- `projection`: clarifier plan, operating MLSS record, design criteria table.
- `difference`: include multiple clarifiers and require total active surface area.
- `product`: clarifier solids loading compliance record.

## Task 12: SOR Calculation

Current world:

- Computes surface overflow rate, utilisation ratio, compliance margin, and criterion-satisfied flag.
- Inputs are flow, clarifier surface area, and maximum SOR.
- The pass flag is `1.0` when SOR is less than or equal to the maximum.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: clarifier plan plus flow case and criteria table.
- A hard variant can compare average day, peak day, and peak hour SOR.
- A dual-check variant can combine SOR and SLR for the same clarifier.

Requirements:

- Flow source and scenario label.
- Clarifier surface area source.
- Maximum SOR criterion source.
- Pass/fail evidence.

Harness opportunities:

- Add active-clarifier count and area gate.
- Add flow-case selection gate.
- Add criterion-source gate.
- Add pass-flag consistency gate.

Natural products:

- `sor-calculation <-> slr-calculation`.
- `sor-calculation -> hrt-calculation` where clarifier hydraulic loading is part of a treatment-train check.
- `sor-calculation -> process upgrade event` when hydraulic loading controls clarifier expansion.

Meta-harness handles:

- `projection`: clarifier plan, flow table, Ten States/WEF criteria table.
- `difference`: mix peak flow and average-flow criteria rows.
- `product`: clarifier hydraulic loading compliance record.

## Cross-Slice Product Worlds

### Treatment Process Basis Package

Candidate chain:

1. Read design flow and influent/effluent concentration basis.
2. Compute target chemical dose and product feed.
3. Compute unit HRT and reactor volume alternatives.
4. Emit a process basis record with flow, loads, dose, and volume.

Why it is interesting:

- It forces models to keep design flow, concentration, mass load, volume, and chemical product quantities separate.
- It can be rendered from a process flow diagram, tabular design basis, or mixed drawing/table pack.
- It creates a reusable upstream context for activated-sludge and clarifier checks.

### Activated Sludge Capacity Package

Candidate chain:

1. Compute MLSS inventory from basin volume and lab data.
2. Compute actual SRT from inventory, wasting, and effluent solids loss.
3. Compute required nitrification SRT from temperature, ammonia, DO, and kinetics.
4. Compute oxygen demand using BOD, nitrogen, denitrification credit, and sludge production.

Why it is interesting:

- It separates actual plant state from required process design criteria.
- It creates a meaningful meta-harness repair path: raise MLSS, reduce wasting, add volume, or change operating temperature/DO assumptions.
- It connects naturally to future aeration air-demand and blower/power tasks.

### Solids And Biogas Package

Candidate chain:

1. Compute sludge production from BOD removal, yield, SRT, and primary solids.
2. Convert sludge production into volatile solids feed when a sidecar provides VS fraction.
3. Compute biogas, methane, and methane energy.
4. Handoff energy to electrical or heat-use task worlds.

Why it is interesting:

- It transforms a waste-stream calculation into an energy recovery product world.
- It requires strong source role labelling: TSS, VSS, VS feed, methane fraction, and energy factor are not interchangeable.
- It can support artifact-level checking against a sludge balance diagram.

### Clarifier Dual-Criterion Package

Candidate chain:

1. Read clarifier geometry and active units.
2. Compute SOR for the relevant flow scenario.
3. Compute SLR for the relevant solids scenario.
4. Identify whether hydraulic or solids loading controls compliance.

Why it is interesting:

- It is a simple but strong multi-step compliance world.
- It has natural multimodal extraction from clarifier plans and criteria tables.
- It tests whether the model can track two criteria over the same asset without merging them.

## Repair And Extension Notes

- `oxygen-requirements` clamps carbonaceous oxygen and total oxygen to zero when credits or sludge production would make them negative. Multimodal variants should expose these as named branch events, not silent arithmetic side effects.
- `nitrification-srt` rejects non-positive net growth. A future meta-harness variant could treat that as a design infeasibility event and ask the model to identify the failed assumption rather than only sampling valid cases.
- `sor-calculation` and `slr-calculation` already emit compliance flags. They are good early candidates for staged verifiers that check utilisation, margin, and flag consistency together.
- Every load calculation in this slice repeatedly uses the same mg/L and m3/d to kg/d conversion. A shared `load_conversion` gate would help composed wastewater worlds avoid hidden unit drift.
