# ABOUTME: Designs long-horizon product-world candidates from SSC-17 energy resilience.
# ABOUTME: Lists shared-subworld manifests, variants, verifier events, and hardening routes.

# SSC-17 Energy Resilience Long-Horizon Design

SSC-17 is the "energy resource, storage, resilience, and operating time-series world" cluster from `shared-subworld-cluster-scan.md`.

The useful design lesson is that SSC-17 should not become "make the PV/BESS task bigger." It becomes long-horizon when an operating event, resource record, load profile, storage state, and feeder or process authority all have to stay aligned across several task worlds.

## Evidence Basis

The scan gives SSC-17 this shape:

| Field | Value |
| --- | --- |
| Shared subworld | solar/weather/load/gas/energy records, BESS/PV, biogas, critical load/autonomy, operating profile |
| Memberships | 62 task-card memberships |
| Primary cards | 13 |
| Disciplines | civil, electrical, mechanical, structural |
| Score | 27/30 |
| Candidate product | Energy resilience product joining PV/BESS, biogas, critical load, and feeder assumptions |
| Main risk | Strong but can duplicate PV-storage unless treatment/process or resilience surface is explicit. |

The primary-card set is mostly electrical, but the full membership set reaches civil stormwater, process/mechanical, fire, rail/weather, coastal, and structural energy/event cards. That matters: SSC-17 is strongest when the electrical energy model is forced to answer for some non-electrical consequence.

## Set-Style Frame

Treat a task world as a set of admissible source-state-answer traces:

```text
W = {source pack, parsed state, staged calculations, answer, verifier trace}
```

For SSC-17, the shared subworld is:

```text
S_energy_event = {
  time_index,
  scenario_id,
  resource_profiles,
  load_profiles,
  energy_asset_register,
  critical_load_register,
  operating_policy,
  feeder_or_network_boundary,
  authority_partition,
  result_ledger
}
```

Long-horizon products then become fiber products over this shared subworld:

```text
W_pv_storage x_S W_feeder
W_treatment_process x_S W_energy_dispatch x_S W_feeder
W_stormwater_event x_S W_critical_controls x_S W_backup_energy
W_bess_layout x_S W_fire_ventilation x_S W_feeder
W_station_population x_S W_emergency_loads x_S W_storage
```

The test is not whether the final number is hard. The test is whether the agent preserves the same event window, equipment identity, time basis, criticality tier, and authority split while moving between worlds.

## Shared Subworld Manifest

Any SSC-17 source pack should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `scenario_id` | Named operating case such as normal day, outage, storm, fire mode, heatwave, or wet-weather process peak. | Design basis, operating note, event table. |
| `time_index` | Hourly/subhourly/daily basis used by resources, loads, dispatch, and autonomy. | Load profile, weather file, SCADA extract, rainfall record. |
| `resource_profiles` | PV production, grid availability, generator fuel, biogas, gas supply, or other energy sources. | PVWatts/SAM/REopt output, gas meter, digester record, generator datasheet. |
| `load_profiles` | Electrical or thermal demand by equipment, process, lighting, communications, fire, or pumping load. | Load schedule, motor schedule, PFD, site operation profile. |
| `critical_load_register` | Which loads must survive the event and for how long. | Emergency power basis, operations plan, fire/life-safety note. |
| `energy_asset_register` | PV, BESS, battery, inverter, generator, fuel, transformer, feeder, and control equipment. | SLD, datasheets, equipment list, interconnection form. |
| `operating_policy` | Dispatch, export limit, load shedding, autonomy, generator-start, or non-export rule. | REopt request, utility rule, control narrative. |
| `feeder_or_network_boundary` | PCC, feeder, cable, voltage, ampacity, protection, export, or voltage-limit boundary. | SLD, cable schedule, feeder model, interconnection study. |
| `authority_partition` | Which source controls each gate: utility, electrical code, process permit, fire standard, stormwater criterion, or owner operation. | Criteria pack, standards matrix, AHJ/utility notes. |
| `result_ledger` | Stage outputs and diagnostics connecting resource, load, storage, feeder, and consequence checks. | Design memo, dispatch CSV, verifier trace. |

## Candidate Long-Horizon Products

### SSC17-LH-01: DER Resilience And Feeder Interconnection

Composition:

```text
PV resource + load profile + BESS/generator candidates
  -> dispatch and autonomy
  -> feeder voltage/ampacity/export checks
  -> interconnection and commissioning memo
```

Task-card anchors:

- `string-sizing`
- `dc-ac-ratio`
- `bess-sizing`
- `bess-sizing-basic`
- `battery-sizing`
- `voltage-drop-dc`
- `voltage-drop`
- `cable-ampacity`
- `static-thermal-rating`

Source pack:

- PVWatts/SAM-style resource inputs and production output;
- REopt-style optimization/dispatch request and response;
- SLD, cable schedule, load profile, inverter/BESS/generator datasheets;
- utility interconnection/export-control form or static DER register;
- optional OpenDSS feeder model with voltage/current limits.

Variants:

| Variant | What Changes | Expected Diagnostic Pressure |
| --- | --- | --- |
| Backup-only | PV is absent or ignored; BESS/generator serves critical load only. | Energy vs power confusion, autonomy-hour mismatch. |
| Self-consumption | Dispatch optimizes grid import reduction. | Load/resource time alignment and SOC boundary. |
| Non-export | PCS/export-control rule limits PCC export. | Export basis and SLD/PCC identity. |
| Feeder-constrained | Feeder voltage or ampacity fails unless dispatch changes. | Downstream network constraint preservation. |
| Equipment-list gate | Inverter/BESS/PCS eligibility must match authority rule. | Datasheet/listing mismatch. |
| EOL battery | End-of-life retention reduces usable energy. | BOL/EOL capacity distinction. |

Best use:

This is the easiest SSC-17 task to ground from existing PV/storage/feeder research, but it is also the one most likely to become merely a larger electrical task. It needs a resilience or utility-operation event to be worth doing as a long-horizon product.

### SSC17-LH-02: Wastewater Energy Island

Composition:

```text
influent/load basis + process criteria
  -> oxygen demand and blower/motor load
  -> sludge and biogas production
  -> PV/BESS/biogas/generator dispatch
  -> feeder and critical-process resilience check
```

Task-card anchors:

- `mass-balance`
- `oxygen-requirements`
- `nitrification-srt`
- `sludge-production`
- `biogas-production`
- `pump-power-efficiency`
- `bess-sizing`
- `dc-ac-ratio`
- `voltage-drop`
- `cable-ampacity`

Source pack:

- influent/effluent sample table and process basis;
- PFD, basin schedule, blower/motor schedule;
- digester feed, volatile-solids destruction, gas meter, or biogas yield record;
- PV/BESS/generator/load schedule and feeder SLD;
- operating policy for critical process loads during outage or peak tariff periods.

Variants:

| Variant | What Changes | Expected Diagnostic Pressure |
| --- | --- | --- |
| Aeration peak day | Process load rises under design influent and nitrification case. | Time-basis and process-load handoff. |
| Wet-weather inflow | Flow/load basis changes while energy assets remain fixed. | Process scenario and dispatch mismatch. |
| Biogas shortfall | Volatile-solids destruction or methane fraction changes. | Gas-to-electric conversion and fuel constraint. |
| Grid outage | Critical aeration, pumping, controls, and disinfection must ride through. | Critical-load register and autonomy. |
| PV low-resource week | Solar profile underperforms against normal resource basis. | Resource/weather provenance. |
| Load-shedding policy | Noncritical process or building loads are shed. | Criticality tier preservation. |

Best use:

This is probably the philosophically richest SSC-17 product. Treatment residuals become an energy source while treatment itself remains a critical load. The same process world appears as both demand and supply.

### SSC17-LH-03: Stormwater Controls And Pumping Outage Resilience

Composition:

```text
rainfall event + drainage/storage model
  -> HGL/storage/outlet or pump condition
  -> control, telemetry, pump, or gate load
  -> BESS/generator autonomy
  -> flood, overtopping, or control-failure memo
```

Task-card anchors:

- `rational-method`
- `detention-volume-preliminary`
- `orifice-outlet-design`
- `weir-outlet-design`
- `hgl-check`
- `flap-gate-headloss`
- `bess-sizing-basic`
- `battery-sizing`
- `voltage-drop`
- `poe-power-budget`

Source pack:

- SWMM-style rainfall, subcatchment, storage, outlet, and report files;
- drainage long section or storage/outlet schedule;
- pump/control panel/telemetry load list;
- backup supply/BESS/generator datasheet;
- event table joining storm duration, grid outage window, and control state.

Variants:

| Variant | What Changes | Expected Diagnostic Pressure |
| --- | --- | --- |
| Control-only backup | BESS supports telemetry/PLC/gates, not pumps. | Load-class overclaiming. |
| Pump backup | Pump motor load is included in backup system. | Power surge vs energy autonomy. |
| Outage before peak | Grid fails before rainfall peak. | Event-window alignment. |
| Outlet blockage | Hydraulic capacity drops while energy system is unchanged. | Correct failure attribution. |
| Low initial SOC | Battery begins below normal operating state. | SOC provenance and autonomy margin. |
| Different design storm | 2-year, 10-year, or 100-year rainfall case. | Scenario ID and target-value traceability. |

Best use:

This is the nearest route to a task-owned fixture because the stormwater research already has a SWMM Example 3 source-pack contract. It becomes SSC-17 rather than pure stormwater only if the outage/control energy surface is explicit.

### SSC17-LH-04: BESS Fire, Containment, Ventilation, And Feeder

Composition:

```text
BESS/inverter layout + energy capacity
  -> feeder, voltage, and export basis
  -> fire/ventilation/containment loads
  -> emergency operating mode and safety memo
```

Task-card anchors:

- `bess-sizing`
- `battery-sizing`
- `voltage-drop`
- `cable-ampacity`
- `air-changes`
- `t-squared-hrr`
- `visibility-criterion`
- `bund-volume-calculation`
- `sprinkler-discharge`
- `incident-energy`

Source pack:

- BESS/battery/inverter datasheets;
- SLD and feeder/cable schedule;
- container or battery-room layout;
- fire strategy and ventilation schedule;
- containment/drainage isolation plan;
- authority matrix separating electrical, fire, ventilation, and environmental gates.

Variants:

| Variant | What Changes | Expected Diagnostic Pressure |
| --- | --- | --- |
| Containerized BESS | Packaged unit with manufacturer fire/ventilation assumptions. | Datasheet vs site-design authority. |
| Battery room | Room ventilation and fire strategy are site-designed. | Layout/volume/load consistency. |
| Fire mode | Ventilation/fire load changes during incident. | Normal load vs emergency load partition. |
| Non-export interconnection | Export-control assumptions constrain operation. | PCS/PCC identity and utility rule. |
| Fire-water interaction | Suppression or water demand touches drainage/containment. | Cross-authority evidence partition. |
| Arc-flash add-on | Fault/protection basis is reused for switchboard safety. | Protection setting provenance. |

Best use:

This is highly realistic and vivid, but public accepted project data is likely sparse. A task-owned redrawn layout and equipment schedule may be the practical first source pack.

### SSC17-LH-05: Road And ITS Field Equipment Energy Resilience

Composition:

```text
road corridor operating scene
  -> lighting, VMS, CCTV, access, and comms load
  -> local cabinet/PV/BESS/PoE/network backup
  -> outage, storm, or traffic-event operating memo
```

Task-card anchors:

- `road-aeci-calculation`
- `vms-legibility-distance`
- `cctv-storage-calculation`
- `poe-power-budget`
- `fiber-link-loss-budget`
- `voltage-drop`
- `battery-sizing`
- `roadway-spread`
- `hgl-check`

Source pack:

- road plan/profile and equipment locations;
- lighting grid, VMS schedule, camera schedule, network topology;
- local cabinet load schedule, PoE switch schedule, backup battery/PV datasheet;
- drainage/flood-risk or storm event note for equipment resilience.

Variants:

| Variant | What Changes | Expected Diagnostic Pressure |
| --- | --- | --- |
| Communications-only resilience | Backup covers CCTV/VMS/network but not lighting. | Critical load tier clarity. |
| Night storm | Lighting and drainage/flood risks coincide. | Event and location consistency. |
| Traffic incident | VMS/CCTV demand rises during outage. | Scenario-driven load change. |
| Cabinet flood exposure | Equipment elevation conflicts with HGL/surface level. | Spatial and energy-world join. |
| PoE budget limit | Camera/VMS network loads exceed switch budget. | Load rollup and device identity. |

Best use:

This is a good bridge back to the road low-point target. It is less pure energy engineering and more operational resilience, which is valuable for meta-harness event design.

### SSC17-LH-06: Station Emergency Operations Energy Package

Composition:

```text
population and operating mode
  -> lift/escalator/egress/fire/ventilation loads
  -> emergency power and storage/generator sizing
  -> feeder, autonomy, and load-shedding memo
```

Task-card anchors:

- `occupant-load`
- `egress-width`
- `handling-capacity`
- `escalator-capacity`
- `air-changes`
- `nac-load-calculation`
- `battery-sizing`
- `bess-sizing-basic`
- `voltage-drop`

Source pack:

- station/floor plan and population schedule;
- lift/escalator schedule and emergency operation rule;
- fire alarm, ventilation, lighting, and access-control load schedules;
- SLD and emergency power basis;
- load-shed sequence or emergency operations plan.

Variants:

| Variant | What Changes | Expected Diagnostic Pressure |
| --- | --- | --- |
| Peak-hour outage | Population and vertical-transport demand are high. | Population/time/load alignment. |
| Fire mode | NAC, smoke ventilation, and egress loads become critical. | Emergency authority partition. |
| Accessibility lift backup | Specific lift load must survive. | Equipment identity and criticality. |
| Load shedding | Escalators or noncritical lighting are dropped. | Load tier and service-level explanation. |
| Generator start delay | Battery must bridge before generator supports load. | Sequential event handling. |

Best use:

This is broad but natural for long-horizon tasks because the same population schedule drives transport, egress, alarm, ventilation, and energy decisions.

### SSC17-LH-07: Rail Corridor Weather, Electrical Capacity, And Backup Operations

Composition:

```text
weather and route profile
  -> OLE sag/thermal or signal equipment load
  -> backup supply and feeder margin
  -> operating restriction or resilience memo
```

Task-card anchors:

- `single-span-sag-tension`
- `static-thermal-rating`
- `line-inductance`
- `line-capacitance`
- `signal-sighting-distance`
- `warning-time-calculation`
- `davis-resistance`
- `battery-sizing`

Source pack:

- route profile and span schedule;
- weather table with heat, wind, ice, or storm event;
- signalling/communications load and backup supply schedule;
- feeder or OLE electrical basis;
- operating rule for degraded weather or power outage.

Variants:

| Variant | What Changes | Expected Diagnostic Pressure |
| --- | --- | --- |
| Heatwave | Thermal rating and load margin tighten. | Temperature/resource basis. |
| Wind/ice event | Mechanical clearance and electrical operation interact. | Weather case partition. |
| Signal backup outage | Communications/signalling load must ride through. | Critical load duration. |
| Reduced-speed operation | Operating state changes energy and signalling consequences. | Scenario propagation. |

Best use:

This is a strong future candidate, but operator standards and project artifacts are harder to source than PV, stormwater, or task-owned plant examples.

### SSC17-LH-08: Coastal Or Marine Flood Energy Resilience

Composition:

```text
coastal level and storm event
  -> pump/outfall/freeboard or marine asset state
  -> electrical equipment elevation and backup energy
  -> flood-resilience and service-continuity memo
```

Task-card anchors:

- `freeboard-calculation`
- `outfall-submergence-check`
- `flap-gate-headloss`
- `pump-head-calculation`
- `battery-sizing`
- `voltage-drop`
- `berthing-energy-calc`
- `fender-energy-check`

Source pack:

- tide/SLR/storm table and site section;
- pump/outfall or marine asset schedule;
- electrical equipment layout and elevation;
- backup energy source and critical-load register;
- operating criterion for storm/flood service continuity.

Variants:

| Variant | What Changes | Expected Diagnostic Pressure |
| --- | --- | --- |
| Flooded electrical room | Equipment elevation conflicts with design flood. | Spatial/source authority conflict. |
| Submerged outfall | Hydraulic head and energy load change together. | Hydraulic-energy handoff. |
| Storm outage | Grid fails during high water. | Event-window alignment. |
| Marine impact event | Energy absorption and emergency power both appear in port operations. | Product boundary control. |

Best use:

This is conceptually strong but probably second-wave. It needs a clean site section and equipment-elevation source pack to avoid becoming a vague resilience story.

## How The Variants Come Together

All SSC-17 variants should share the same kernel:

```text
source ingestion
  -> time/scenario normalization
  -> load and resource profile construction
  -> energy asset capacity and dispatch
  -> feeder/network or process consequence checks
  -> authority-partitioned design memo
  -> localized verifier diagnostics
```

The products differ by what is joined to the energy kernel:

| Join Surface | Product Families | Why It Matters |
| --- | --- | --- |
| Feeder/SLD | LH-01, LH-04, LH-06 | Turns energy sizing into interconnection, ampacity, voltage, export, and protection constraints. |
| Process basis | LH-02 | Makes energy both a product of treatment and a critical input to treatment. |
| Rainfall/hydraulic event | LH-03, LH-08 | Forces event-window alignment between water state, controls, pumps, and backup power. |
| Fire/life-safety mode | LH-04, LH-06 | Separates normal operation from emergency load and authority regimes. |
| Road/station/rail operating scene | LH-05, LH-06, LH-07 | Connects human operation, visibility, communications, transport, and critical power. |
| Weather/resource time-series | LH-01, LH-07, LH-08 | Makes PV, thermal rating, OLE/weather, and flood events comparable but not interchangeable. |

## Verifier Events Worth Designing For

These are the events that make SSC-17 more than a calculation chain.

| Event | Broken Assumption | Useful Diagnostic |
| --- | --- | --- |
| Time-basis drift | PV, load, outage, and process profiles use different intervals or dates. | `time_basis_mismatch` |
| Energy/power confusion | kW, kWh, Ah, autonomy hours, and C-rate are mixed. | `energy_power_unit_confusion` |
| BOL/EOL drift | Battery usable energy ignores degradation or reserve SOC. | `battery_capacity_basis_mismatch` |
| Critical-load overclaim | Answer backs up all loads when source only marks controls or life-safety loads critical. | `critical_load_scope_overclaim` |
| Feeder identity drift | Dispatch or voltage drop uses the wrong PCC, feeder, cable, or voltage level. | `feeder_boundary_mismatch` |
| Authority collapse | Utility/export rule, fire rule, process permit, and owner policy are treated as one source. | `authority_partition_mismatch` |
| Event-window mismatch | Grid outage, storm peak, fire mode, or process peak are not simultaneous in the source. | `event_window_mismatch` |
| Load-shed trace missing | Answer assumes load shedding without identifying shed loads and service consequence. | `unsupported_load_shedding` |
| Resource provenance missing | Solar, gas, biogas, generator fuel, or grid availability is invented. | `resource_profile_untraceable` |
| Dispatch infeasible | Claimed dispatch violates SOC, export, generator, fuel, or feeder constraints. | `dispatch_constraint_violation` |

## Recommended Hardening Order

1. `SSC17-LH-03` stormwater controls and pumping outage resilience: nearest to task-owned fixture work because the SWMM Example 3 source-pack contract already exists. Add a small critical-control load and BESS/generator event surface.
2. `SSC17-LH-02` wastewater energy island: richest philosophical task because process residuals become supply while the process remains a critical load. Needs representative process/load/gas records or task-owned redrawn schedules.
3. `SSC17-LH-01` DER resilience and feeder interconnection: easiest public-source route through PVWatts, REopt, interconnection forms, equipment lists, and synthetic feeder models. Must include a resilience or network constraint event to avoid duplicating the existing PV/storage feeder package.
4. `SSC17-LH-04` BESS fire, containment, ventilation, and feeder: most vivid cross-authority product, but likely needs task-owned layout/datasheets before public accepted project evidence appears.

The practical next artifact should be a `shared_subworld_manifest` for one product, not a runtime verifier. That manifest should define source files, time indices, load/resource tables, asset registers, authority partitions, expected staged outputs, and negative verification events.
