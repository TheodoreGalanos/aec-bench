# Formula Template Seed Inventory

This inventory records the structural and mechanical seed review for the
formula-template backlog. The filter is deliberately narrow: accepted templates
need a deterministic, closed-form contract that can be implemented as one pure
`compute()` function with prompt-visible assumptions.

## Current Coverage

- Source task seeds in `tasks/*/*/*/source_task.json`: 472.
- Current built-in templates in this branch: 184.
- Current civil built-ins in this branch: 57.
- Current electrical built-ins in this branch: 52.
- Current ground built-ins in this branch: 10.
- Mechanical seeds reviewed: 143.
- Structural seeds reviewed: 83.
- Structural and mechanical seeds reviewed: 226.
- Current mechanical built-ins in this branch: 50.
- Current structural built-ins in this branch: 15.

## Implemented Source-Task Tranche

These seed-only tasks were converted after correcting the backlog audit from
`manifest.json` to `source_task.json`:

- `tasks/civil/tidal-water-levels/tidal-prism/source_task.json`
- `tasks/electrical/electrical-parameters/line-inductance/source_task.json`
- `tasks/electrical/load-flow/pfc-sizing/source_task.json`
- `tasks/electrical/cctv-design/ppm-calculation/source_task.json`
- `tasks/electrical/signal-timing/yellow-interval-calculation/source_task.json`
- `tasks/electrical/signal-processing/4-20ma-scaling/source_task.json`
- `tasks/electrical/structured-cabling/fiber-link-loss-budget/source_task.json`
- `tasks/electrical/its-communications/bandwidth-calculation/source_task.json`
- `tasks/electrical/cctv-design/cctv-storage-calculation/source_task.json`
- `tasks/electrical/signal-timing/pedestrian-clearance-time/source_task.json`
- `tasks/electrical/poe-network/poe-power-budget/source_task.json`
- `tasks/electrical/power-supply/power-load-calculation/source_task.json`
- `tasks/electrical/wireless-design/rf-link-budget/source_task.json`
- `tasks/electrical/level-crossings/warning-time-calculation/source_task.json`
- `tasks/electrical/vms-design/vms-legibility-distance/source_task.json`
- `tasks/electrical/electrical-parameters/line-capacitance/source_task.json`
- `tasks/electrical/electrical-parameters/voltage-regulation/source_task.json`
- `tasks/electrical/load-flow/radial-feeder-voltage-drop/source_task.json`
- `tasks/electrical/signal-sighting/signal-sighting-distance/source_task.json`
- `tasks/electrical/power-supply/battery-sizing/source_task.json`
- `tasks/electrical/signal-timing/all-red-interval-calculation/source_task.json`
- `tasks/electrical/traffic-analysis/interval-calculation/source_task.json`
- `tasks/electrical/traffic-analysis/handling-capacity/source_task.json`
- `tasks/electrical/escalator-design/escalator-capacity/source_task.json`
- `tasks/electrical/structured-cabling/conduit-fill-calculation/source_task.json`
- `tasks/electrical/energy-performance/road-pdi-calculation/source_task.json`
- `tasks/electrical/energy-performance/road-aeci-calculation/source_task.json`
- `tasks/electrical/energy-performance/leni-calculation/source_task.json`
- `tasks/electrical/road-lighting/road-uniformity-check/source_task.json`
- `tasks/electrical/interior-lighting/interior-uniformity/source_task.json`
- `tasks/electrical/bess-design/bess-sizing-basic/source_task.json`
- `tasks/electrical/structural-loading/wind-load-conductor/source_task.json`
- `tasks/electrical/structural-loading/ice-load-calculation/source_task.json`
- `tasks/electrical/signal-sighting/overlap-calculation/source_task.json`
- `tasks/electrical/solar-pv-design/voltage-drop-dc/source_task.json`
- `tasks/electrical/lighting-design/lux-level-calculation/source_task.json`
- `tasks/electrical/sports-lighting/sports-illuminance-uniformity/source_task.json`
- `tasks/electrical/shaft-sizing/shaft-dimensions/source_task.json`
- `tasks/electrical/shaft-sizing/car-dimensions-check/source_task.json`
- `tasks/electrical/access-control/access-controller-sizing/source_task.json`

## Implemented Mechanical Seeds

- `tasks/mechanical/activated-sludge/oxygen-requirements/source_task.json`
- `tasks/mechanical/activated-sludge/sludge-production/source_task.json`
- `tasks/mechanical/compressed-air/air-demand/source_task.json`
- `tasks/mechanical/braking-systems/braking-distance/source_task.json`
- `tasks/mechanical/clarifier-design/slr-calculation/source_task.json`
- `tasks/mechanical/clarifier-design/sor-calculation/source_task.json`
- `tasks/mechanical/convergence-assessment/mass-balance/source_task.json`
- `tasks/mechanical/design-fire/t-squared-hrr/source_task.json`
- `tasks/mechanical/egress-modeling/egress-width/source_task.json`
- `tasks/mechanical/equipment-selection/pump-head-calculation/source_task.json`
- `tasks/mechanical/fundamental-calculations/a-weighting/source_task.json`
- `tasks/mechanical/fundamental-calculations/chemical-dosing/source_task.json`
- `tasks/mechanical/fundamental-calculations/distance-attenuation/source_task.json`
- `tasks/mechanical/fundamental-calculations/hrt-calculation/source_task.json`
- `tasks/mechanical/fundamental-calculations/mlss-inventory/source_task.json`
- `tasks/mechanical/fundamental-calculations/sabine-rt60/source_task.json`
- `tasks/mechanical/fundamental-calculations/spl-log-sum/source_task.json`
- `tasks/mechanical/fundamental-calculations/srt-calculation/source_task.json`
- `tasks/mechanical/gas-services/gas-load-calculation/source_task.json`
- `tasks/mechanical/heat-exchanger-design/lmtd-calculation/source_task.json`
- `tasks/mechanical/hydrant-flow-test/available-flow-calculation/source_task.json`
- `tasks/mechanical/hydrant-flow-test/water-supply-curve/source_task.json`
- `tasks/mechanical/fire-alarm-systems/nac-load-calculation/source_task.json`
- `tasks/mechanical/industrial-ventilation/air-changes/source_task.json`
- `tasks/mechanical/fatigue-analysis/miner-fatigue/source_task.json`
- `tasks/mechanical/npsh-analysis/npsha-calculation/source_task.json`
- `tasks/mechanical/nutrient-removal/nitrification-srt/source_task.json`
- `tasks/mechanical/mesh-independence/gci-calculation/source_task.json`
- `tasks/mechanical/pipe-hydraulics/hazen-williams-friction/source_task.json`
- `tasks/mechanical/pipe-hydraulics/minor-losses-calculation/source_task.json`
- `tasks/mechanical/pipe-hydraulics/velocity-check/source_task.json`
- `tasks/mechanical/pipe-sizing-water/pressure-loss-calculation/source_task.json`
- `tasks/mechanical/prescriptive-compliance/occupant-load/source_task.json`
- `tasks/mechanical/pump-hydraulics/npsh-available/source_task.json`
- `tasks/mechanical/pump-hydraulics/pump-head-calculation/source_task.json`
- `tasks/mechanical/pump-hydraulics/pump-power-efficiency/source_task.json`
- `tasks/mechanical/pump-sizing/pump-affinity-laws/source_task.json`
- `tasks/mechanical/pump-sizing/pump-power-calculation/source_task.json`
- `tasks/mechanical/reactor-sizing/cstr-volume/source_task.json`
- `tasks/mechanical/reactor-sizing/pfr-volume/source_task.json`
- `tasks/mechanical/sludge-handling/biogas-production/source_task.json`
- `tasks/mechanical/structural-fire/steel-critical-temp/source_task.json`
- `tasks/mechanical/sprinkler-hydraulics/elevation-pressure/source_task.json`
- `tasks/mechanical/sprinkler-hydraulics/friction-loss-hazen-williams/source_task.json`
- `tasks/mechanical/sprinkler-hydraulics/sprinkler-discharge/source_task.json`
- `tasks/mechanical/thrust-restraint/thrust-force-calculation/source_task.json`
- `tasks/mechanical/transient-analysis/joukowsky-pressure/source_task.json`
- `tasks/mechanical/transient-analysis/wave-speed-calculation/source_task.json`
- `tasks/mechanical/train-resistance-dynamics/davis-resistance/source_task.json`
- `tasks/mechanical/vibration/transmissibility/source_task.json`
- `tasks/mechanical/system-curves/por-aor-compliance/source_task.json`
- `tasks/mechanical/tenability-assessment/visibility-criterion/source_task.json`

## Implemented Structural Seeds

- `tasks/structural/berthing-energy/berthing-energy-calc/source_task.json`
- `tasks/structural/bracket-connection/bracket-load-calc/source_task.json`
- `tasks/structural/concrete-mix-design/target-strength-calc/source_task.json`
- `tasks/structural/concrete-mix-design/scm-substitution/source_task.json`
- `tasks/structural/fender-design/fender-energy-check/source_task.json`
- `tasks/structural/rebar-detailing/lap-splice-length/source_task.json`
- `tasks/structural/load-analysis/load-combinations/source_task.json`
- `tasks/structural/mooring-analysis/mooring-line-capacity/source_task.json`
- `tasks/structural/movement-tolerance/construction-tolerance/source_task.json`
- `tasks/structural/movement-tolerance/thermal-movement-calc/source_task.json`
- `tasks/structural/pipe-rack-design/pipe-support-dead-load/source_task.json`
- `tasks/structural/steel-specification/carbon-equivalent-calc/source_task.json`
- `tasks/structural/superstructure-design/composite-section/source_task.json`
- `tasks/structural/wind-load-analysis/effective-wind-area/source_task.json`
- `tasks/structural/wind-turbine-foundations/gravity-base-stability/source_task.json`

## Strong Remaining Mechanical Candidates

All strong mechanical candidates identified in this review have been converted.

## Strong Remaining Structural Candidates

All strong structural candidates identified in this review have been converted.

## Needs Reduced Contract

These seeds are plausible benchmark material only after the reduced formula,
constants, lookup tables, or coefficient sources are made explicit in the
template contract.

- `tasks/mechanical/control-valve-sizing/*`
- `tasks/mechanical/duct-design/*`
- `tasks/mechanical/energy-compliance/*`
- `tasks/mechanical/healthcare-hvac/*`
- `tasks/mechanical/psychrometrics/*`
- `tasks/mechanical/relief-valve-sizing/*`
- `tasks/mechanical/sanitary-drainage/*`
- `tasks/mechanical/stormwater-drainage/*`
- `tasks/mechanical/ventilation-calculations/*`
- `tasks/structural/baseplate-anchor-design/*`
- `tasks/structural/concrete-beam-design/*`
- `tasks/structural/concrete-slab-design/punching-shear-check/source_task.json`
- `tasks/structural/crane-runway-design/*`
- `tasks/structural/fatigue-analysis/*`
- `tasks/structural/glass-design/*`
- `tasks/structural/load-analysis/impact-factor/source_task.json`
- `tasks/structural/load-analysis/live-load-distribution/source_task.json`
- `tasks/structural/rebar-detailing/development-length/source_task.json`
- `tasks/structural/steel-connections/*`
- `tasks/structural/steel-member-design/*`
- `tasks/structural/substation-foundations/*`
- `tasks/structural/superstructure-design/*`
- `tasks/structural/wind-load-analysis/wind-pressure-calc/source_task.json`

## Clear Rejects as Written

These are not good formula-template seeds as written because they are document
review, catalogue selection, QA, network solving, broad design workflows, or
data extraction rather than single closed-form calculations.

- `tasks/mechanical/backflow-prevention/device-selection/source_task.json`
- `tasks/mechanical/commissioning-verification/airflow-verification/source_task.json`
- `tasks/mechanical/convergence-assessment/qoi-stability/source_task.json`
- `tasks/mechanical/equipment-selection/cooling-equipment-selection/source_task.json`
- `tasks/mechanical/npsh-analysis/suction-piping-review/source_task.json`
- `tasks/mechanical/post-processing/qoi-extraction/source_task.json`
- `tasks/mechanical/process-deliverables/datasheet-review/source_task.json`
- `tasks/mechanical/process-deliverables/hmb-generation/source_task.json`
- `tasks/mechanical/qa-hvac/equipment-schedule-review/source_task.json`
- `tasks/mechanical/qa-review/mass-balance-verification/source_task.json`
- `tasks/mechanical/sprinkler-hydraulics/hydraulic-calculation-full/source_task.json`
- `tasks/mechanical/system-curves/operating-point-determination/source_task.json`
- `tasks/structural/bracket-connection/bracket-capacity-check/source_task.json`
- `tasks/structural/concrete-column-design/column-interaction-check/source_task.json`
- `tasks/structural/concrete-mix-design/absolute-volume-mix/source_task.json`
- `tasks/structural/crane-runway-fatigue/*`
- `tasks/structural/deck-structure/crane-beam-design/source_task.json`
- `tasks/structural/deck-structure/deck-beam-design/source_task.json`
- `tasks/structural/design-review-qa/*`
- `tasks/structural/framing-design/transom-design/source_task.json`
- `tasks/structural/glass-design/glass-thickness-selection/source_task.json`
- `tasks/structural/platform-grating-design/grating-selection/source_task.json`
- `tasks/structural/portal-frame-design/portal-deflection-check/source_task.json`
- `tasks/structural/power-plant-structures/pipe-rack-design/source_task.json`
- `tasks/structural/qa-energy-structures/*`
- `tasks/structural/qa-error-detection/unit-consistency-check/source_task.json`
- `tasks/structural/quality-assurance/glass-schedule-review/source_task.json`
- `tasks/structural/piled-foundation/pile-cap-design/source_task.json`
- `tasks/structural/seismic-analysis/capacity-design/source_task.json`
- `tasks/structural/steel-connections/moment-endplate-connection/source_task.json`
- `tasks/structural/transmission-tower-foundations/tower-load-cases/source_task.json`
- `tasks/structural/wind-turbine-foundations/wtg-load-extraction/source_task.json`
