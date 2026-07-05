# ABOUTME: Detailed task-world review for mechanical dynamics, thermal, compressed-air, fatigue, and verification tasks.
# ABOUTME: Records multimodal, composition, and meta-harness opportunities for the final mechanical discipline slice.

# Mechanical Dynamics Thermal And Verification Pass 013

Review date: 2026-06-28

Reviewed task cards:

- `mechanical/compressed-air/air-demand`
- `mechanical/braking-systems/braking-distance`
- `mechanical/train-resistance-dynamics/davis-resistance`
- `mechanical/mesh-independence/gci-calculation`
- `mechanical/heat-exchanger-design/lmtd-calculation`
- `mechanical/convergence-assessment/mass-balance`
- `mechanical/fatigue-analysis/miner-fatigue`
- `mechanical/vibration/vibration-transmissibility`

Source files read for this pass:

- `src/aec_bench/templates/builtin/mechanical/air_demand/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/braking_distance/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/davis_resistance/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/gci_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/lmtd_calculation/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/mass_balance/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/miner_fatigue/{params.toml,instruction.md,engine.py}`
- `src/aec_bench/templates/builtin/mechanical/vibration_transmissibility/{params.toml,instruction.md,engine.py}`

## Slice Read

This final mechanical slice collects the less category-neat tasks: compressed air demand, rail dynamics, simulation verification, heat exchanger duty, process mass balance, fatigue damage, and vibration isolation. They are still scalar/all-given, but several are already small verification worlds rather than plain calculations.

The strongest meta-harness pattern is "evidence artifact to acceptance event":

- a tool schedule becomes connected and simultaneous compressed-air demand;
- a train and alignment profile become braking distance and tractive power;
- a CFD convergence table becomes GCI and asymptotic-range evidence;
- a process stream table becomes mass-balance closure;
- a heat exchanger datasheet becomes LMTD and duty;
- a duty-cycle histogram becomes fatigue damage;
- a vibration measurement or equipment schedule becomes transmissibility and isolation efficiency.

This is the slice where meta-harness operations can realistically generate or mutate evidence artifacts: perturb a convergence table, swap a flow arrangement, add a nonmonotonic CFD run, change gradient sign, or reconfigure duty-cycle bins, then verify that the model diagnoses the changed world.

## Task 1: Air Demand

Current world:

- Computes connected and simultaneous compressed-air demand in L/s and m3/min.
- Inputs are three tool flow/quantity pairs and a simultaneity factor.
- The simultaneity factor must be greater than zero and less than or equal to one.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: compressed-air tool or equipment schedule.
- A plant-layout variant can require selecting tools on one branch or area.
- A hard variant can source simultaneity from operating scenario or shift profile.

Requirements:

- Tool flow and quantity source.
- Simultaneity factor source.
- Unit conversion between L/s and m3/min.
- Optional compressor capacity or receiver sizing source if extended.

Harness opportunities:

- Add equipment schedule extraction gate.
- Add simultaneity-source gate.
- Add connected-vs-simultaneous role gate.
- Add compressor-capacity handoff gate.

Natural products:

- `air-demand -> pump/electrical power-load` if compressor power tasks are added.
- `air-demand -> mass-balance` for process utility consumption checks.
- `air-demand -> acoustic source package` where compressors drive noise.

Meta-harness handles:

- `projection`: tool schedule, plant layout, operating scenario table.
- `difference`: include standby or maintenance tools as distractors.
- `product`: compressed-air demand record.

## Task 2: Braking Distance

Current world:

- Computes adhesion-limited brake effort, net deceleration, stopping distance, and stopping time.
- Inputs are train mass, initial speed, brake effort, adhesion coefficient, and track gradient.
- Effective brake effort is the minimum of specified brake effort and adhesion limit.
- The engine rejects cases where net deceleration is non-positive.

Multimodal expansion:

- Best first modality: rolling-stock data sheet plus track gradient profile.
- A route variant can require selecting the governing gradient segment and initial speed.
- A hard variant can combine stopping distance with signal sighting or overlap tasks in electrical rail.

Requirements:

- Train mass and speed source.
- Brake effort source.
- Adhesion coefficient source or scenario.
- Track gradient source and sign convention.
- Stopping-distance acceptance criterion if extended.

Harness opportunities:

- Add adhesion-limited branch gate.
- Add gradient sign-convention gate.
- Add insufficient-braking event gate.
- Add handoff gate to signal sighting/overlap worlds.

Natural products:

- `braking-distance -> electrical signal-sighting-distance/overlap-calculation`.
- `braking-distance -> civil rail vertical/gradient geometry`.
- `braking-distance <-> davis-resistance` for rolling-stock dynamics packages.

Meta-harness handles:

- `projection`: train data sheet, braking curve, track gradient profile, signal layout.
- `difference`: reverse gradient sign or include wet/dry adhesion cases.
- `product`: braking performance record.

## Task 3: Davis Resistance

Current world:

- Computes speed in m/s, resistance per tonne, total resistance, and tractive power.
- Inputs are train mass, speed, and Davis equation coefficients A, B, and C.
- Speed can be zero, which yields zero tractive power after resistance is computed.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: rolling-stock resistance coefficient table.
- A route-energy variant can pair resistance with speed profile and gradients.
- A hard variant can connect tractive power to electrical traction supply tasks.

Requirements:

- Train mass and speed source.
- Davis coefficients source.
- Unit contract for N/t, km/h, m/s, kN, and kW.
- Optional traction power handoff.

Harness opportunities:

- Add coefficient-source gate.
- Add speed-unit conversion gate.
- Add tractive power construction gate.
- Add handoff gate to electrical traction power worlds.

Natural products:

- `davis-resistance -> electrical power-load/feeder tasks` if traction power variants are added.
- `davis-resistance -> braking-distance` as rolling-stock dynamics context.
- `davis-resistance -> civil rail alignment` where gradients/curves affect speed scenarios.

Meta-harness handles:

- `projection`: rolling-stock data sheet, speed profile, resistance coefficient table.
- `difference`: include coefficients in different units or for a different consist.
- `product`: train resistance and tractive power record.

## Task 4: GCI Calculation

Current world:

- Computes observed order, extrapolated value, approximate relative error, fine-grid GCI, and asymptotic range ratio.
- Inputs are coarse, medium, and fine grid values plus refinement ratio.
- The engine requires monotonic convergence and non-zero fine-grid value.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: CFD mesh-independence table.
- A report variant can require selecting the correct scalar response from a simulation summary.
- A hard variant can include nonmonotonic or oscillatory results and ask for diagnosis rather than numeric GCI.

Requirements:

- Ordered grid values and refinement ratio source.
- Response-variable identity.
- Monotonic convergence evidence.
- GCI calculation evidence.

Harness opportunities:

- Add grid-order/source gate.
- Add monotonic-convergence event gate.
- Add observed-order construction gate.
- Add asymptotic-range consistency gate.

Natural products:

- `gci-calculation -> mass-balance` in a CFD/model verification package.
- `gci-calculation -> pressure-loss or drag tasks` when simulation output supplies design values.
- `gci-calculation -> meta-harness repair` where a nonmonotonic run triggers rerun/refinement.

Meta-harness handles:

- `projection`: CFD report, mesh table, convergence plot.
- `difference`: reorder coarse/medium/fine rows or add a nonmonotonic response.
- `product`: simulation verification evidence record.

## Task 5: LMTD Calculation

Current world:

- Computes terminal temperature differences, LMTD, corrected mean temperature difference, heat duty, and minimum approach.
- Inputs are hot/cold inlet/outlet temperatures, U value, area, correction factor, and flow arrangement.
- Terminal temperature difference formulas branch on counterflow versus parallel flow.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: heat exchanger datasheet or process stream table.
- A P&ID variant can require identifying hot and cold streams and their inlet/outlet directions.
- A hard variant can compare multiple heat exchanger arrangements or correction factors.

Requirements:

- Hot and cold stream temperature source.
- Flow arrangement source.
- U, area, and correction factor source.
- Terminal approach and heat-duty evidence.

Harness opportunities:

- Add stream-direction/flow-arrangement gate.
- Add terminal-difference branch gate.
- Add correction-factor source gate.
- Add heat-duty consistency gate.

Natural products:

- `mass-balance -> lmtd-calculation` through process stream context.
- `lmtd-calculation -> pump/utility/electrical load` for heating/cooling duty worlds.
- `lmtd-calculation -> process reactor/chemical-dosing` as a process unit design package.

Meta-harness handles:

- `projection`: heat exchanger datasheet, process stream table, P&ID, TEMA note.
- `difference`: swap inlet/outlet labels or hide flow arrangement.
- `product`: heat exchanger duty record.

## Task 6: Mass Balance

Current world:

- Computes total inlet, total outlet, imbalance, closure error, and closure-satisfied flag.
- Inputs are two inlet streams, two outlet streams, and closure tolerance.
- Closure is based on absolute imbalance divided by total inlet.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: process stream table or simulation balance report.
- A treatment-train variant can require selecting inlets/outlets around one unit boundary.
- A hard variant can include recycle/internal streams and require boundary classification.

Requirements:

- Inlet and outlet stream source.
- System boundary definition.
- Closure tolerance source.
- Pass/fail evidence.

Harness opportunities:

- Add boundary-classification gate.
- Add inlet/outlet role gate.
- Add closure-error construction gate.
- Add mass-balance failure event gate.

Natural products:

- `mass-balance -> gci-calculation` in model verification and QA packages.
- `mass-balance -> treatment process basis` for plant process worlds.
- `mass-balance -> chemical-dosing/sludge/biogas` where mass loads must close.

Meta-harness handles:

- `projection`: process flow diagram, stream table, simulation report.
- `difference`: include recycle streams or internal transfer streams.
- `product`: process balance closure record.

## Task 7: Miner Fatigue

Current world:

- Computes damage for three bins, cumulative damage, remaining damage margin, and fatigue-satisfies flag.
- Inputs are applied and allowable cycles for three bins.
- The pass flag is `1.0` when cumulative damage is less than or equal to one.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: duty-cycle histogram plus S-N/allowable-cycle table.
- A rotating-equipment variant can derive bins from operating hours at load cases.
- A hard variant can join vibration results, start-stop records, and fatigue damage.

Requirements:

- Applied cycle source by bin.
- Allowable cycle source by bin.
- Bin identity/source evidence.
- Damage and pass/fail evidence.

Harness opportunities:

- Add cycle-bin extraction gate.
- Add allowable-cycle source gate.
- Add cumulative-damage consistency gate.
- Add fatigue-failure event gate.

Natural products:

- `vibration-transmissibility -> miner-fatigue` for equipment support fatigue contexts.
- `davis-resistance/braking-distance -> miner-fatigue` if rolling-stock duty cycles are introduced.
- `miner-fatigue -> structural/material tasks` for pressure equipment or supports.

Meta-harness handles:

- `projection`: duty-cycle histogram, fatigue table, equipment operating log.
- `difference`: include cycles from non-design operating modes.
- `product`: fatigue damage record.

## Task 8: Vibration Transmissibility

Current world:

- Computes frequency ratio, transmissibility, and isolation efficiency.
- Inputs are forcing frequency, natural frequency, and damping ratio.
- Isolation efficiency can be negative when transmissibility is greater than one.
- Every difficulty tier exposes every input.

Multimodal expansion:

- Best first modality: equipment speed/frequency schedule plus isolator datasheet.
- A measurement variant can source forcing frequency from a vibration spectrum.
- A hard variant can test whether an isolator moves the system away from resonance and into an acceptance band.

Requirements:

- Forcing frequency source.
- Natural frequency source.
- Damping ratio source.
- Optional transmissibility or isolation criterion.

Harness opportunities:

- Add frequency-source gate.
- Add resonance-region branch gate.
- Add negative-isolation event gate.
- Add equipment-support handoff gate.

Natural products:

- `vibration-transmissibility -> miner-fatigue`.
- `vibration-transmissibility -> acoustic source package` for plant-room comfort worlds.
- `vibration-transmissibility -> structural support/foundation` where support dynamics matter.

Meta-harness handles:

- `projection`: isolator datasheet, equipment speed schedule, vibration spectrum.
- `difference`: provide rpm and Hz together and force conversion.
- `product`: vibration isolation check.

## Cross-Slice Product Worlds

### Rail Dynamics And Signalling Package

Candidate chain:

1. Read rolling-stock mass, speed, resistance coefficients, brake effort, adhesion, and route gradient.
2. Compute Davis resistance and tractive power.
3. Compute braking distance and stopping time.
4. Handoff stopping distance to signal sighting, overlap, or warning-time tasks.

Why it is interesting:

- It combines mechanical train dynamics, civil rail geometry/profile, and electrical signalling.
- It is strongly multimodal: rolling-stock sheets, speed profiles, gradient tables, and signal layouts.
- It creates high-value sign-convention gates around gradient and route chainage.

### Simulation Verification Package

Candidate chain:

1. Read a CFD or simulation report.
2. Check global mass balance closure.
3. Check grid convergence index.
4. Emit a verification artifact that says whether outputs are credible enough for downstream design use.

Why it is interesting:

- It is a practical meta-harness miniature: validate the harness/model before trusting the task result.
- It can intentionally mutate evidence artifacts to create nonmonotonic convergence or failed closure.
- It connects to any task whose source value could come from simulation.

### Thermal Process Unit Package

Candidate chain:

1. Read process streams and heat exchanger datasheet.
2. Check stream mass balance if relevant.
3. Compute LMTD, corrected MTD, and duty.
4. Handoff duty to utilities, pumps, power, or thermal energy tasks.

Why it is interesting:

- It requires stream identity, direction, and arrangement, not just temperature arithmetic.
- It is a natural multimodal datasheet/P&ID task.
- It links process design, mechanical equipment, and electrical/energy demand.

### Equipment Reliability Package

Candidate chain:

1. Read equipment operating speeds, isolator data, and duty cycle.
2. Compute vibration transmissibility.
3. Convert operating modes into fatigue bins.
4. Compute cumulative fatigue damage and identify remaining margin.

Why it is interesting:

- It combines dynamic response and cumulative damage, two areas where final-answer-only scoring is weak.
- It can use measurement spectra, duty logs, and equipment datasheets.
- It gives the meta-harness repair levers: change isolator, shift frequency, reduce cycles, or reclassify duty bins.

## Repair And Extension Notes

- `lmtd-calculation` instructions branch terminal temperature differences by flow arrangement, but the engine computes `minimum_approach_c` from the counterflow terminal pair regardless of `flow_arrangement`. Audit the instruction, verifier, and engine before generating richer heat exchanger variants.
- `braking-distance` needs an explicit gradient sign convention sidecar before multimodal route profiles are introduced.
- `gci-calculation` currently rejects nonmonotonic convergence. A meta-harness benchmark could deliberately include nonmonotonic cases and score diagnosis/recovery rather than only valid GCI arithmetic.
- `vibration-transmissibility` can produce negative isolation efficiency when transmissibility is greater than one. Future variants should expose that as an amplification branch or add an explicit compliance criterion.
