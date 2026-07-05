# ABOUTME: Catalogue of long-horizon composite task-world templates represented in AEC-Bench.
# ABOUTME: Records product scope, task combinations, multimodal paths, and data gaps.

# Composite Task-World Product Benchmark

This benchmark slice turns the task-by-task opportunity analysis into eleven composite task-world templates. Each template describes a product-world scenario, then compiles into the existing task-world/meta-harness payload shape. The runnable definitions live in `src/aec_bench/task_world_templates/catalogue.py`; this document is the human review map.

Boundary rule: "long-horizon" is the evaluation property, "product world" is the engineering scenario, and `CompositeTaskWorldTemplate` is the contract object. Do not create a separate long-horizon task class or runtime unless the native task-world contract proves unable to express a required capability.

Each product is runnable as an example package through:

```bash
uv run aec-bench --json task composite-template materialize-example <template-id> --output /tmp/<template-id>
uv run aec-bench --json task composite-template verify-example /tmp/<template-id>
```

## Product Summary

| Template | Disciplines | Long-horizon challenge |
| --- | --- | --- |
| `stormwater-drainage-package` | Civil, hydrology, hydraulics | Carry rainfall, runoff, detention, outlet, pipe, HGL, and freeboard decisions through one drainage memo. |
| `pump-station-duty-package` | Civil, mechanical, hydraulics | Build a duty point from wet-well levels, pipe losses, pump curves, power, and NPSH. |
| `fire-water-supply-sprinkler-demand` | Mechanical, fire, hydraulics | Reconcile hydrant supply, sprinkler demand, elevation/friction losses, and pump boost. |
| `road-rail-alignment-package` | Civil, rail, electrical | Join road geometry, rail cant, sighting distance, and signal warning time. |
| `wind-facade-structural-package` | Civil, structural | Carry wind speed into facade pressure, bracket reactions, load combinations, and constructability checks. |
| `civil-ground-retaining-interface` | Civil, ground, structural | Preserve soil interpretation, water state, earth pressure, wall stability, bearing, and settlement assumptions. |
| `treatment-aeration-power-package` | Process, mechanical, electrical | Connect influent loads, reactor inventory, SRT, oxygen demand, blower power, and sludge production. |
| `pv-storage-feeder-package` | Electrical, renewables | Combine load profile, PV strings, inverter ratio, storage, voltage drop, and ampacity. |
| `earthing-arc-flash-package` | Electrical, power, safety | Combine fault level, earthing, incident energy, protection clearing time, and busbar forces. |
| `rail-braking-signalling-package` | Mechanical, civil, electrical, rail | Carry rolling resistance and grade into braking, sighting, warning time, and overlap checks. |
| `road-visual-operations-package` | Electrical, transport, communications, security | Preserve one road visual-operations scene across lighting, CCTV, VMS, network, PoE, fibre, UPS, and memo checks. |

## Product Notes

### `stormwater-drainage-package`

Built from `rational-method`, `scs-curve-number`, `detention-volume-preliminary`, `orifice-outlet-design`, `weir-outlet-design`, `pipe-velocity-check`, `hazen-williams-headloss`, `hgl-check`, `pipe-invert-calculation`, `freeboard-calculation`, and `outfall-submergence-check`.

Natural composition path: catchment hydrology produces `peak_runoff_m3_s`; detention consumes it to produce `detention_volume_m3`; outlet design produces `outlet_capacity_m3_s`; pipe and HGL checks produce velocity and clearance; the final memo checks freeboard and outfall conditions.

Multimodal path: catchment plans, IDF tables, drainage long sections, detention sections, and outlet details. The key harness requirement is drawing-zone provenance for catchment areas, pipe levels, and outlet geometry.

Meta-harness opportunity: project to source pack for source-authority tests; subset to hydrology-only, detention-only, or conveyance-only variants; difference two product variants to expose changed outlet-control branches or missing HGL gates.

Primary data gaps: local IDF/climate factors, survey/CAD extraction, and tailwater time series.

### `pump-station-duty-package`

Built from `pump-head-calculation`, `hazen-williams-friction`, `minor-losses-calculation`, `velocity-check`, `water-supply-curve`, `pump-power-calculation`, `pump-power-efficiency`, and `npsh-available`.

Natural composition path: wet-well and site profile establish static lift; pipe schedule establishes losses; pump curve establishes duty point; power and NPSH checks close the selection note.

Multimodal path: pump-curve charts, wet-well schedules, rising-main long sections, pipe schedules, and electrical motor schedules. The key harness requirement is curve digitisation and consistent duty-point interpolation.

Meta-harness opportunity: product-combine with fire-water supply, stormwater pump-out, or electrical feeder tasks through `design_flow_l_s`, `total_dynamic_head_m`, and `motor_input_kw`.

Primary data gaps: manufacturer curve digitisation, wet-well operating rules, and as-built pipework.

### `fire-water-supply-sprinkler-demand`

Built from `available-flow-calculation`, `water-supply-curve`, `sprinkler-discharge`, `elevation-pressure`, `friction-loss-hazen-williams`, `pressure-loss-calculation`, and `pump-power-efficiency`.

Natural composition path: hydrant test becomes supply curve; hazard classification and layout become sprinkler demand; riser schematic becomes losses; pump curve becomes boost requirement.

Multimodal path: hydrant test forms, sprinkler plans, riser schematics, hazard tables, and pump curves. The verifier needs source-cell provenance for test pressures and drawing-zone provenance for remote-area geometry.

Meta-harness opportunity: branch repair around hazard class and remote-area selection; difference variants with and without pump boost; compose with pump-station duty worlds.

Primary data gaps: code rule pack, node-level hydraulic model, and hydrant-test provenance.

### `road-rail-alignment-package`

Built from `curve-elements`, `min-curve-radius`, `transition-spiral-length`, `superelevation-rate`, `vertical-curve-design`, `ssd-on-grade`, `cant-calculation`, `signal-sighting-distance`, and `warning-time-calculation`.

Natural composition path: horizontal alignment produces curve radius and superelevation; vertical geometry produces sight distance; rail comfort consumes curve radius; signalling consumes sight-distance outputs.

Multimodal path: alignment plans, profiles, survey control, design criteria, and signalling layouts. The harness must preserve chainage, coordinate frame, grade sign convention, and controlling element identity.

Meta-harness opportunity: product-combine civil alignment and rail signalling tasks through chainage and sight-distance handoffs; event trigger on grade sign convention changes.

Primary data gaps: chainage geometry parsing, standard selection, and sighting photo evidence.

### `wind-facade-structural-package`

Built from `design-wind-speed`, `design-wind-pressure`, `effective-wind-area`, `bracket-load-calc`, `load-combinations`, `construction-tolerance`, and `carbon-equivalent-calc`.

Natural composition path: wind source produces design speed; facade elevation produces pressure zone and tributary area; bracket detail receives the load; structural combination produces ULS action; tolerance and material checks close the package.

Multimodal path: wind criteria, facade elevations, bracket details, material certificates, and load-case schedules. The key harness need is elevation-zone detection and panel/bracket association.

Meta-harness opportunity: difference facade-zone variants; repair hidden pressure-zone decisions; compose wind outputs into structural bracket tasks.

Primary data gaps: current wind standard tables, facade drawing OCR, and fixing capacity data.

### `civil-ground-retaining-interface`

Built from `spt-corrections`, `cpt-parameter-derivation`, `lateral-earth-pressure`, `retaining-wall-stability`, `wall-overturning`, `wall-bearing`, `exit-gradient`, `uplift-pressure`, `terzaghi-bearing-capacity`, and `immediate-settlement`.

Natural composition path: ground logs become interpreted parameters; groundwater records become water state; earth pressure consumes soil and surcharge; wall stability consumes earth pressure; bearing and settlement close the foundation side.

Multimodal path: geotechnical reports, borehole logs, groundwater records, wall sections, surcharge plans, and bearing memos. The harness must normalise wall geometry across civil and ground assumptions.

Meta-harness opportunity: branch repair for wall layout and water case; product-combine civil and ground retaining-wall variants; difference variants by drainage assumption or surcharge case.

Primary data gaps: complete ground investigation records, wall geometry normalisation, and groundwater design case evidence.

### `treatment-aeration-power-package`

Built from `mass-balance`, `hrt-calculation`, `cstr-volume`, `pfr-volume`, `mlss-inventory`, `srt-calculation`, `nitrification-srt`, `oxygen-requirements`, `pump-power-efficiency`, `chemical-dosing`, `sludge-production`, and `biogas-production`.

Natural composition path: influent sampling becomes loads; basin dimensions and criteria become reactor volume and inventory; SRT and nitrification gates close biological compliance; oxygen demand becomes blower power; sludge production follows the same mass basis.

Multimodal path: sampling tables, PFDs, basin drawings, process criteria, and blower datasheets. The verifier needs stream ID consistency and time-series aggregation checks.

Meta-harness opportunity: subset to carbon-only or nitrification variants; repair reactor-model branch drift; compose process oxygen output into electrical power tasks.

Primary data gaps: representative sampling time series, permit/criteria authority, and blower selection curves.

### `pv-storage-feeder-package`

Built from `power-load-calculation`, `string-sizing`, `dc-ac-ratio`, `bess-sizing`, `bess-sizing-basic`, `battery-sizing`, `voltage-drop-dc`, `voltage-drop`, `cable-ampacity`, `radial-feeder-voltage-drop`, and `pfc-sizing`.

Natural composition path: load profile produces peak load; module and inverter datasheets produce string voltage and DC/AC ratio; battery datasheet produces usable storage; SLD and cable schedule produce voltage drop and ampacity.

Multimodal path: load profiles, single-line diagrams, module/inverter/battery datasheets, cable schedules, and weather-resource tables. The harness must preserve time-basis, conductor material, and derating assumptions.

Meta-harness opportunity: subset backup-only, self-consumption, or feeder-only variants; product-combine with building load and arc-flash worlds through feeder and fault assumptions.

Primary data gaps: solar resource series, protection study inputs, and battery degradation model.

### `earthing-arc-flash-package`

Built from `three-phase-fault-current`, `grid-resistance`, `incident-energy`, `busbar-forces`, `static-thermal-rating`, and `cable-ampacity`.

Natural composition path: SLD establishes fault level; soil report establishes earthing model; protection settings establish clearing time; incident energy uses both; busbar forces consume the same fault basis.

Multimodal path: single-line diagrams, relay settings, soil resistivity reports, switchboard layouts, and cable schedules. The verifier needs curve-setting provenance and switchboard geometry extraction.

Meta-harness opportunity: event trigger when clearing time changes after incident energy is calculated; difference variants by soil model or protection setting; compose with PV/BESS and feeder packages.

Primary data gaps: protection curve digitisation, earthing standard limits, and network fault contribution assumptions.

### `rail-braking-signalling-package`

Built from `davis-resistance`, `braking-distance`, `cant-calculation`, `signal-sighting-distance`, `warning-time-calculation`, and `overlap-calculation`.

Natural composition path: rolling-stock and alignment data produce resistance and equivalent grade; braking consumes grade and speed; sighting consumes braking distance and field records; warning time and overlap consume sighting and braking outputs.

Multimodal path: alignment profiles, rolling-stock datasheets, signalling plans, sighting photo logs, and operations standards. The harness must preserve grade sign convention, signal identity, and sighting evidence.

Meta-harness opportunity: branch repair for grade sign convention; product-combine mechanical braking and electrical signalling worlds; subset to braking-only, sighting-only, or overlap-only variants.

Primary data gaps: certified rolling-stock data, calibrated sighting media, and current operations rule packs.

### `road-visual-operations-package`

Built from `lux-level-calculation`, `road-uniformity-check`, `ppm-calculation`, `cctv-storage-calculation`, `vms-legibility-distance`, `bandwidth-calculation`, `poe-power-budget`, `fiber-link-loss-budget`, and `battery-sizing`.

Natural composition path: the task-owned SSC-13 source pack establishes one road scene and operating scenario; lighting consumes the grid rows; CCTV consumes target-width and resolution rows; VMS policy preserves the message boundary; network and power consume device schedule loads; the final visual-operations memo preserves the same handoff values.

Multimodal path: road layout, luminaire grid, device schedule, camera coverage table, message policy, cabinet/switch/fibre topology, and power/UPS schedule. The current fixture is task-owned and table-based; real instances would need approved photometric exports, authority message evidence, issued network topology, and design-source provenance.

Meta-harness opportunity: project to lighting-only, CCTV-only, or network-power-only views; difference variants where the camera target width, cabinet route, or source-status branch changes; repair silent scene, policy, or handoff mutation.

Primary data gaps: approved photometric model exports, authority-approved message criteria, issued ITS network/power evidence, and source-pack parsers that recompute formulas from fixture files.

## What Is Runnable Now

The current composite templates are runnable at package-contract level. For each template, the materializer writes `template.json`, a compiled task-world payload in `world.json`, hidden expected state, verifier configuration, an example structured answer, and verifier results. The verifier checks:

- source references are present;
- every expected handoff is present and unchanged;
- branch decisions are present and unchanged;
- deliverable manifest entries are present;
- product-specific required evidence is present.

What is not yet real-stage execution:

- source parsers are not extracting values from actual PDFs, drawings, images, or spreadsheets;
- stage runners are not yet invoking each underlying template in sequence;
- verifier gates do not yet recompute formulas from source values;
- multimodal provenance is represented as source metadata, not inspected media regions;
- project-specific standards, rule packs, and authority data are recorded as data gaps.

That is the right boundary for the current pass: runnable composite task-world template examples first, then source adapters and stage execution once the native contract stabilises.
