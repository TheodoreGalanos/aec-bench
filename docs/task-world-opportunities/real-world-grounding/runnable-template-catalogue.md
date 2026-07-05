# ABOUTME: Tracks which shared-subworld SSC notes have one runnable template.
# ABOUTME: Separates synthetic execution evidence from real source-pack readiness.

# Runnable Template Catalogue

This catalogue covers the 19 physical/product SSC notes and intentionally excludes the `SSC-20` regional standards and authority overlay. A row is counted as runnable when it has one task-owned template or package-contract example that can generate/materialize, verify a golden pass, and has local execution evidence recorded for the current runnable path.

Current status: **19/19 physical SSC notes have one runnable template; 0 remain.**

These runnable entries are task-owned synthetic or package-contract examples. They do not claim accepted project evidence, authority approval, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.

| SSC | First hardening candidate | Runnable template | Status | Evidence |
| --- | --- | --- | --- | --- |
| SSC-07 | Soil and groundwater structural-electrical safety package | `ground-structural-electrical-safety-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-01 | Road low-point drainage and field equipment resilience | `road-low-point-resilience-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-14 | Pipe transient support and foundation package | `pipe-transient-support-foundation-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-11 | Pump transient, thrust, support, and protection-trip package | `pump-transient-protection-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-03 | Detention and outlet design-check package | `detention-outlet-hgl-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-17 | Stormwater controls and pumping outage resilience | `stormwater-pumping-outage-resilience-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-06 | Pump station duty, power, NPSH, and feeder package | `pump-station-duty-power-npsh-feeder-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-10 | Wastewater energy island | `wastewater-energy-island-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-05 | Mechanical-load to feeder and voltage package | `mechanical-load-feeder-voltage-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-02 | Level crossing warning-time and backup-power package | `level-crossing-warning-backup-power-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-19 | Fire-water, sprinkler demand, and storage hazard package | `fire-water-sprinkler-storage-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-09 | Facade wind, bracket, anchor, and tolerance package | `facade-wind-bracket-anchor-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-04 | Coastal flood, outfall, pump, and electrical elevation package | `coastal-flood-outfall-pump-elevation-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-08 | Station population, vertical movement, egress, alarm, and ventilation package | `station-population-egress-vertical-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-15 | Product submittal review packet overlay | `product-submittal-compliance-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-13 | Road visual operations, ITS, CCTV, lighting, and comms power package | `road-visual-operations-package` | Done | Package-contract composite template; materialize/verify score `1.0`. |
| SSC-16 | Construction environmental controls, temporary traffic, and monitoring power package | `construction-stage-controls-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-12 | Blower or pump duty to acoustic impact package | `acoustic-receiver-impact-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |
| SSC-18 | Valve Cv, process value, and signal scaling package | `control-loop-signal-package` | Done | Built-in synthetic template; Sonnet and Haiku `tool_loop` reward `1.0`. |

## SSC-07 Delta

The `ground-structural-electrical-safety-package` template covers `SSC-07-LH-01` with one closed synthetic ground package:

- SPT correction for `SPT-07-03-06M` and `BH-07-03`;
- CPT interpretation for `CPT-07-02`;
- a ground interpretation memo value for the governing friction angle;
- a Terzaghi shallow foundation bearing check for `FDN-07-MAT-01`;
- a separate resistivity and grounding-grid check for `RES-07-ERT-01` and `GRID-07-EARTH-01`.

The first Sonnet debug attempts scored `0.79` because the prompt left the bearing-factor convention and water-table correction too open. The final template pins the source-bound Terzaghi factors and the interpolated water-table `gamma_eff` rule; after that, Sonnet and Haiku both reached verifier reward `1.0`.

## SSC-01 Delta

The `road-low-point-resilience-package` template covers `SSC-01-LH-01` with one closed synthetic road low-point package:

- rational-method runoff for `DRN-CAT-01` and upstream bypass at `DRN-BYP-01`;
- HEC-22-style triangular gutter spread at `LP-01`;
- inlet interception, residual ponding, and one full-pipe HGL reach for `DRN-PIT-01`, `DRN-PIPE-01`, and `HGL-01`;
- cabinet flood freeboard for `CAB-01`;
- VMS reading-time margin, network headroom, battery runtime, and overall pass score for `VMS-01`, `ITS-NET-01`, and `BATT-01`.

The first Sonnet debug attempt scored `0.76` because the prompt rendered small Manning values with too little precision: `0.016` appeared as `0.02`, and `0.013` appeared as `0.01`. The final template stores those source values as per-thousand fields and states the exact `n = 0.016` and `n = 0.013` values in the generated instruction; after that, Sonnet and Haiku both reached verifier reward `1.0`.

## SSC-14 Delta

The `pipe-transient-support-foundation-package` template covers `SSC-14-LH-01` with one closed synthetic pipe support and foundation package:

- transient bend thrust for `PIPE-SSC14-001` and `TRANS-14-001`;
- operating pipe, contents, and insulation dead load for `SUP-14-ANCH-01`;
- support vertical service reaction and concrete foundation self-weight for `FDN-14-BASE-01`;
- source-owned Terzaghi allowable bearing, factored actions, eccentric bearing pressure, anchor shear, sliding margin, and overall pass score for `SOIL-14-BEAR-01`, `LC-14-ULS-01`, and `ANCH-14-001`.

The first Sonnet debug run scored `0.89` because the prompt left the Terzaghi bearing-factor convention open enough for the model to use a different `Nq`/`Nc` basis. The final template pins the source-owned factors `Nc = 37.162`, `Nq = 22.456`, and `Ngamma = 19.7`; after that, Sonnet and Haiku both reached verifier reward `1.0`.

## SSC-11 Delta

The `pump-transient-protection-package` template covers `SSC-11-LH-01` with one closed synthetic pump transient, support, and protection package:

- source-owned wave-speed and Joukowsky pressure-rise checks for `TRANS-11-TRIP-01`;
- steady pump head and hydraulic power for `PUMP-11-DUTY-01`;
- bend transient thrust and operating pipe/support load for `PID-SSC11-401` and `SUP-11-ANCH-01`;
- high-high pressure trip margin, pipe MAWP margin, thrust utilization, support vertical utilization, and overall pass score for `PROT-11-HHP-01` and `MEMO-11-SUPPORT-PROTECT-01`.

Sonnet and Haiku both reached verifier reward `1.0` on the first model-run pass. Haiku's prose decomposition of support line-load components was internally inconsistent even though the checked final metrics were correct; future verifier hardening should add component-level source-echo checks instead of relying only on final scalar metrics.

## SSC-03 Delta

The `detention-outlet-hgl-package` template covers `SSC-03-LH-01` with one closed synthetic stormwater detention, outlet-control, and HGL package:

- Rational Method runoff for `CATCH-03-DET-01` and `RAIN-03-IDF-10YR`;
- simplified triangular-hydrograph detention storage for `DET-03-BASIN-01`;
- low-flow orifice release for `OUT-03-ORIFICE-01`;
- emergency weir release for `OUT-03-WEIR-01`;
- basin freeboard and downstream HGL clearance for `HGL-03-OUTLET-01` and `MEMO-03-DRAINAGE-01`.

Sonnet and Haiku both reached verifier reward `1.0` on the first model-run pass. Haiku's prose rounded one intermediate weir coefficient differently while still producing all checked final metrics correctly; future verifier hardening should add intermediate source-echo checks and sensitivity cases rather than relying only on final scalar metrics.

## SSC-17 Delta

The `stormwater-pumping-outage-resilience-package` template covers `SSC-17-LH-03` with one closed synthetic stormwater pumping outage resilience package:

- storm inflow volume, pumpable volume, residual storage, and storage margin for `RAIN-17-HYETO-01`, `PUMP-17-STORM-01`, and `BASIN-17-WETWELL-01`;
- pump hydraulic/input power and mixed critical load for `PUMP-17-STORM-01`, `LOAD-17-CRITICAL-01`, and `CTRL-17-RTU-01`;
- BESS usable energy, generator energy, backup energy margin, and battery-only runtime for `BESS-17-BACKUP-01` and `GEN-17-BACKUP-01`;
- source-owned three-phase feeder voltage drop, voltage-drop margin, and overall pass score for `FEEDER-17-480V-01` and `MEMO-17-RESILIENCE-01`.

Sonnet and Haiku both reached verifier reward `1.0` on the first model-run pass. Both prose outputs rounded the conductor resistance display to `0.32 ohm/km` while the source value is `0.321 ohm/km`; future verifier hardening should add exact source-value echo checks for voltage-drop, pump-runtime, outage-duration, and BESS derating inputs.

## SSC-06 Delta

The `pump-station-duty-power-npsh-feeder-package` template covers `SSC-06-LH-01` with one closed synthetic pump station duty package:

- Hazen-Williams rising-main headloss, flow velocity, minor losses, total dynamic head, and pump curve head margin for `RM-06-RISING-MAIN-01` and `CURVE-06-PUMP-01`;
- hydraulic power, shaft power, motor input power, required motor power, and motor size margin for `EQUIP-06-PUMP-01` and `MOTOR-06-SCHED-01`;
- NPSH available, NPSH margin, and NPSH ratio for `WW-06-WETWELL-01`, `NPSH-06-SUCTION-01`, and `CURVE-06-PUMP-01`;
- reactive load, feeder current, feeder voltage-drop percent, voltage-drop margin, and overall pass score for `FEEDER-06-480V-01` and `MEMO-06-SELECTION-01`.

Sonnet and Haiku both reached verifier reward `1.0` on the first model-run pass. Both prose outputs rounded feeder resistance/reactance source values from `0.386` and `0.083 ohm/km` to `0.39` and `0.08 ohm/km`; future verifier hardening should add exact source-value echo checks for feeder R/X, pump curve head, NPSHr, service factor, and power factor values.

## SSC-10 Delta

The `wastewater-energy-island-package` template covers `SSC-10-LH-01` with one closed synthetic wastewater process-energy package:

- source-bound BOD/TKN removal, carbonaceous oxygen, nitrogenous oxygen, denitrification credit, and total oxygen demand for `PROCESS-10-BASIS-01`, `PFD-10-AERATION-01`, and `AER-10-BASIN-01`;
- blower airflow, oxygen-transfer capacity, blower shaft/input power, and selected motor margin for `BLOWER-10-01`;
- volatile-solids destruction, biogas volume, methane volume, methane energy, and CHP electric energy for `DIG-10-BIOGAS-01`;
- daily process energy, PV/BESS/biogas onsite energy, island energy margin, energy intensity, feeder current, voltage drop, and overall pass score for `PV-10-ARRAY-01`, `BESS-10-ISLAND-01`, `FEEDER-10-480V-01`, and `MEMO-10-ENERGY-ISLAND-01`.

The first implementation pass caught a prompt/verifier precision mismatch before model execution: hidden source values `0.232` and `1.204` rendered as `0.23` and `1.2` in the generated instruction. The final template uses the visible source values directly, so the verifier and prompt agree. Sonnet and Haiku both reached verifier reward `1.0`; future verifier hardening should penalize unsupported benchmark/prose claims, require explicit unresolved-gap language, and add exact source-value echo checks for transfer efficiency, air constants, BESS reserve, CHP efficiency, and voltage-drop inputs.

## SSC-05 Delta

The `mechanical-load-feeder-voltage-package` template covers `SSC-05-LH-01` with one closed synthetic mechanical-load feeder package:

- mechanical equipment connected load, demand load, future allowance, and design load for `LOAD-05-MECH-SCHED-01` and `LOAD-05-CALC-01`;
- power-factor correction from initial to target power factor, required capacitor size, selected capacitor margin, corrected apparent power, and feeder current for `FEEDER-05-MCC-01`;
- source-owned cable ampacity derating, breaker continuous loading, voltage drop, voltage-drop margin, and overall pass score for `CABLE-05-FDR-01`, `PROT-05-BKR-01`, and `CRIT-05-VDROP-01`;
- source-bound memo trace for `SLD-05-MCC-01`, `SWBD-05-MSB-01`, `MCC-05`, and `MEMO-05-ELEC-LOAD-01`.

Sonnet and Haiku both reached verifier reward `1.0`. Haiku's prose stated an inconsistent target reactive-power intermediate while the checked JSON fields remained correct; future verifier hardening should add intermediate source-echo checks for target reactive power, target power factor, capacitor sizing, breaker margin, and voltage-drop assumptions.

## SSC-02 Delta

The `level-crossing-warning-backup-power-package` template covers `SSC-02-LH-03` with one closed synthetic level-crossing warning and backup-power package:

- approach speed, total warning time, strike-in distance, minimum-warning margin, and gate-horizontal margin for `ROUTE-02-PROFILE-01`, `LX-02-LAYOUT-01`, `WT-02-WARN-01`, and `CTRL-02-XING-01`;
- connected and design signal load for `LOAD-02-SIG-01`;
- battery energy, required Ah capacity, installed-capacity margin, UPS rating margin, and block count for `BATT-02-UPS-01`;
- source-owned 48 V DC feeder current, voltage drop, and voltage-drop margin for `FEEDER-02-DC-01`;
- fiber total loss, receive power, link margin, excess margin, and overall pass score for `FIBER-02-COMMS-01`, `OPS-02-DEGRADED-01`, and `MEMO-02-LX-OPS-01`.

Sonnet and Haiku both reached verifier reward `1.0`. Haiku's prose included a slightly garbled fiber-margin formula while the checked JSON fields remained correct; future verifier hardening should add exact formula/source-echo checks for optical budget, battery derating, DC feeder resistance, warning-time basis, and degraded-mode source IDs.

## SSC-19 Delta

The `fire-water-sprinkler-storage-package` template covers `SSC-19-LH-01` with one closed synthetic fire-water and sprinkler storage package:

- density-area sprinkler demand, hose allowance, sprinkler head discharge, required remote-head count, and head-count margin for `HAZ-19-STORAGE-01`, `SPR-19-AREA-01`, and `SPR-19-HEAD-01`;
- hydrant supply-curve coefficient, available flow at 20 psi residual, flow margin, and residual pressure at total fire demand for `HYD-19-TEST-01` and `CURVE-19-SUPPLY-01`;
- Hazen-Williams riser friction, equivalent length, elevation pressure loss, available riser pressure, pump-boosted pressure, required riser pressure, and pressure margin for `PIPE-19-RISER-01`, `ELEV-19-ZONE-01`, `PUMP-19-BOOST-01`, and `CRIT-19-AHJ-01`;
- required storage, storage margin, and overall pass score for `TANK-19-STORAGE-01` and `MEMO-19-FIRE-WATER-01`.

Sonnet and Haiku both reached verifier reward `1.0`. Sonnet invented a memo date while the checked JSON fields remained correct; future verifier hardening should add source-echo checks for administrative memo fields, hydrant-test dates, source revision IDs, AHJ criteria, and near-fail margins rather than relying only on final scalar metrics.

## SSC-09 Delta

The `facade-wind-bracket-anchor-package` template covers `SSC-09-LH-01` with one closed synthetic redrawn facade fixing package:

- source-owned facade velocity pressure and body/edge/corner pressure-zone demand for `WIND-09-CRIT-01` and `PRESS-09-ZONES-01`;
- representative bracket tributary area, body/edge/corner wind loads, and dead load for `ELEV-09-REDRAWN-01` and `SUP-09-BRACKET-01`;
- corner bracket horizontal/vertical utilization, body/edge/corner anchor combined utilization, and governing utilization for `SUP-09-BRACKET-01` and `ANCH-09-CONC-01`;
- anchor embedment, edge, and spacing margins plus bracket projection/tolerance and fixed-point vertical margin for `ANCH-09-CONC-01` and `TOL-09-SETOUT-01`.

The first Sonnet debug run scored `0.39` because the generated prompt rendered a tiny velocity-pressure coefficient as `0.0`; the final template uses the visible source-owned velocity pressure directly. The first Haiku debug run on that fix scored `0.70` because it converted already-kN utilization ratios by 1000; the final prompt states the source-pack unit convention explicitly. After those source-contract fixes, Sonnet and Haiku both reached verifier reward `1.0`. Future verifier hardening should add drawing-to-table checks, exact source-value echoes, fixed/sliding point preservation, and negative cases for corner pressure, anchor geometry, spacing, and projection tolerance.

## SSC-04 Delta

The `coastal-flood-outfall-pump-elevation-package` template covers `SSC-04-LH-01` with one closed synthetic coastal resilience package:

- present and future outfall submergence fraction for `TIDE-04-HORIZON-01` and `OUTFALL-04-FLAP-01`;
- design stillwater, design flood level, and minimum equipment elevation for `DATUM-04-AHD-01`, `TIDE-04-HORIZON-01`, and `ELEC-04-SWBD-01`;
- tide-locked inflow, pumped volume, storage margin, pump total dynamic head, hydraulic power, and motor margin for `PUMP-04-FLOOD-01` and `BASIN-04-WETWELL-01`;
- switchboard/control freeboard, feeder current, voltage drop, voltage-drop margin, and overall pass score for `ELEC-04-SWBD-01`, `FEEDER-04-PUMP-01`, and `MEMO-04-RESILIENCE-01`.

The first Sonnet run scored `0.95` because the source parameter used a hidden `0.095 km` feeder length while the generated prompt displayed `0.1 km`; the final template makes the source value visible by using `0.10 km` and updating the oracle. After that fix, Sonnet and Haiku both reached verifier reward `1.0`. Future verifier hardening should add datum/source-value echo checks, real drawing/source-pack fixtures, tide and pump source artifacts, feeder schedule parsing, and negative cases for datum mixing, storage deficit, motor sizing, equipment freeboard, voltage drop, and unsupported authority claims.

## SSC-08 Delta

The `station-population-egress-vertical-package` template covers `SSC-08-LH-01` with one closed synthetic station life-safety operations package:

- occupant load, occupant density, egress width, egress utilization, and egress flow time for `ZONE-08-CONCOURSE-L1`, `POP-08-PEAK-001`, and `EGRESS-08-ROUTE-A`;
- escalator practical capacity, lift five-minute handling capacity, vertical movement margin, and lift handling margin for `ESC-08-UP-01` and `LIFT-08-GROUP-01`;
- emergency ventilation ACH, NAC circuit load, spare capacity, utilization, and overall pass score for `VENT-08-SMOKE-01`, `NAC-08-ALARM-01`, and `MEMO-08-OPS-01`.

The implementation pass caught a prompt/verifier visibility mismatch before model execution: a hidden `0.025 A` speaker current rendered as `0.03 A` in the generated instruction. The final template uses the visible `0.03 A` source value directly, so the prompt and oracle agree on `nac_total_load_a = 2.4`, `nac_spare_capacity_a = 0.6`, and `nac_utilization_percent = 80.0`. After that source-contract fix, Sonnet and Haiku both reached verifier reward `1.0`. Future verifier hardening should add station plan/source fixtures, exact source-value echoes, route/zone consistency checks, device schedule checks, and negative cases for population, egress time, vertical capacity, ventilation ACH, overloaded NAC circuits, and unsupported authority claims.

## SSC-15 Delta

The `product-submittal-compliance-package` template covers `SSC-15-LH-04` with one closed synthetic pump product submittal review package:

- duty, POR, motor, and pressure-certificate checks for `DAT-15-PUMP-001`, `CERT-15-PRESS-001`, and `CALC-15-DUTY-001`;
- evidence completeness, certificate field match, review-comment closeout, elapsed review timing, approved/unresolved deviations, open critical comments, and overall pass score for `SUB-15-PKG-001`, `REG-15-SUB-001`, `CMT-15-REVIEW-001`, `DEV-15-LOG-001`, `SPEC-15-15100`, and `MEMO-15-DISP-001`.

Sonnet and Haiku both reached verifier reward `1.0` on the first model-run pass. Because SSC-15 is an evidence and review-packet task, future verifier hardening should add source-pack-like submittal register, datasheet, certificate, comment-log, and deviation-register fixtures; exact source-value and source-ID echo checks; product identity and revision checks; negative cases for missing certificates, open critical comments, unresolved deviations, elapsed-review overruns, and unsupported authority or approval claims.

## Next Target

The physical/product SSC runnable-template stream is complete at 19/19, with `SSC-20` still excluded because it is a regional standards and authority overlay. The next useful work is source-pack hardening for selected templates rather than another physical SSC runnable baseline: add concrete file-like manifests, parser/formula checks, source-value echo checks, provenance checks, and localized negative cases before making any benchmark-readiness claim.
