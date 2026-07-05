# ABOUTME: Collects cross-task workflow candidates found during task-world review.
# ABOUTME: Separates pipeline, shared-context, and discipline-interface ideas from per-task cards.

# Combination Threads

This file starts as a working ledger. Detailed entries should cite the task cards that support them.

For less obvious cross-discipline joins, use `non-traditional-composition-threads.md`. That file focuses on products joined by a shared evidence surface, such as a road profile, SLD, borehole log, equipment layout, or operating scenario, rather than by a direct same-discipline formula pipeline.

## Seed Threads

| Thread | Pattern | Candidate Tasks | Why It Looks Natural | Evidence Needed |
| --- | --- | --- | --- | --- |
| Stormwater drainage chain | pipeline, shared-context | rational method, detention, pipe hydraulics, HGL, pit/loss checks, outlets | Hydrology produces flows; hydraulics sizes conveyance and checks levels; outlets and detention close the design loop. | Shared catchment/drawing artifact, generated pipe network table, verifier that tracks intermediate flow handoff. |
| Coastal outfall and wave setting | pipeline, discipline-interface | wave climate, wave shoaling, wave breaking, runup, outfall submergence, flap gate/headloss | Marine boundary conditions become drainage/outfall constraints. | Profile or chart artifact, tide/wave source table, staged verifier that separates source interpretation from final calculation. |
| Pump station system sizing | pipeline, constraint-loop | pump power, NPSH, Hazen-Williams/Darcy headloss, system curve, motor/electrical supply | Hydraulic losses and duty point feed pump power, motor, and backup power requirements. | Pump curve artifact, network schematic, calculation sheet output, product-world gates for each stage. |
| Road/rail alignment package | shared-context, evidence-assembly | curve elements, superelevation, cant, transition spiral, stopping sight distance, vertical curve | One alignment geometry drives multiple compliance and comfort checks. | Alignment drawing or chainage table, route profile, per-check evidence records. |
| Wind-to-structure chain | pipeline, discipline-interface | design wind speed, wind pressure, wind load analysis, cladding/effective wind area, bracket load | Wind site factors feed pressures, then structural member and connection checks. | Building elevation/zone diagram, terrain/category source, standards-table extraction, load traceability artifact. |

## Detailed Thread: Civil Stormwater And Detention

Detailed pass: `detailed-passes/civil-stormwater-detention-001.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Text baseline drainage chain | pipeline | `peak_runoff_m3_s`, `post_dev_peak_flow_m3_s`, `allowable_release_rate_m3_s`, `design_flow_m3_s` | None required; scalar baseline for handoff discipline. |
| Multimodal basin package | shared-context, evidence-assembly | catchment area, rainfall intensity/depth, allowable release, basin head, orifice/weir geometry | Catchment plan, rainfall table, council release note, basin section, drainage long section. |
| Pipe reach compliance product | pipeline, constraint-loop | pipe diameter, pipe length, invert/obvert levels, design flow, roughness, pit loss | Drainage long section, pipe schedule, material/pit coefficient table. |

## Detailed Thread: Civil Conveyance And Outfall

Detailed pass: `detailed-passes/civil-conveyance-outfall-002.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Pipe reach design package | pipeline, evidence-assembly | design flow, diameter, velocity, roughness, head loss, HGL | Drainage long section, pipe schedule, roughness/material table. |
| Culvert crossing package | pipeline, constraint-loop | `design_flow_m3_s`, tailwater, invert, headwater elevation, controlling condition | Catchment summary, culvert long section, inlet detail, tailwater table, road crest level. |
| Coastal outfall package | discipline-interface, scenario-portfolio | submergence percentages, tidal period, gate type, gate headloss, tailwater | Outfall profile, tide/SLR table, flap gate detail or datasheet. |
| Spillway energy-dissipation package | pipeline, evidence-assembly | `unit_discharge_m3_s_per_m`, drop height, tailwater, basin type | Spillway drawing, pier/abutment correction table, approach section, tailwater profile. |

## Detailed Thread: Civil Coastal And Wave

Detailed pass: `detailed-passes/civil-coastal-wave-003.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Nearshore wave transformation chain | pipeline, shared-context | `wave_period_s`, depth regime, shoaling/refraction coefficients, `nearshore_wave_height_m`, breaker type | Wave table or wave rose, bathymetry profile, shoreline orientation map. |
| Coastal structure safety package | pipeline, evidence-assembly | `runup_height_m`, `wave_allowance_m`, crest level, armor weight, `KD` | Structure section, roughness/berm table, SLR scenario table, rock material table. |
| Shoreline sediment response package | pipeline, discipline-interface | `breaking_wave_height_m`, wave angle at breaking, transport magnitude and direction | Shoreline orientation map, wave-at-breaking handoff, sediment table. |
| Tidal inlet and coastal outfall package | discipline-interface, scenario-portfolio | tidal prism, exchange duration, mean inlet velocity, submergence and tailwater context | Basin map, inlet section, tide/SLR table, outfall profile. |

## Detailed Thread: Civil Road And Rail Geometry

Detailed pass: `detailed-passes/civil-road-rail-geometry-004.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Road horizontal alignment package | pipeline, evidence-assembly | radius, IP/PC/PT chainage, design speed, side friction, superelevation | Alignment plan, alignment schedule, road design criteria, AGRD friction table. |
| Road access and sight package | shared-context, constraint-loop | driveway grade, setback, design vehicle, approach grade, reaction time | Driveway long section, intersection plan, vertical profile, design-vehicle note. |
| Rail curve geometry package | pipeline, evidence-assembly | actual cant, cant deficiency, maximum speed, governing spiral length | Track curve table, corridor class criteria, gauge/cant limits table, transition plan. |
| Rail vertical and thermal condition package | shared-context, scenario-portfolio | vertical acceleration limit, rail section area, material properties, temperature-change sign | Longitudinal rail profile, corridor comfort table, rail section/material table, temperature record. |

## Detailed Thread: Civil Geotechnical Seepage And Stability

Detailed pass: `detailed-passes/civil-geotech-seepage-stability-005.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Dam foundation seepage package | pipeline, evidence-assembly | headwater, tailwater, head difference, seepage path, drain efficiency, soil properties, uplift force | Dam/foundation section, flow-net or seepage path detail, drain gallery detail, operating level table, soil lab table. |
| Embankment stability scenario portfolio | shared-context, scenario-portfolio | slope angle, slip depth, material properties, pore pressure ratio, reservoir levels, `kh`, `kv`, FoS values | Embankment zoning section, phreatic surface profile, reservoir operation record, material table, seismic hazard note. |
| Retaining-wall external stability package | pipeline, constraint-loop | `ka`, active/passive forces, water force, surcharge, backfill/foundation properties, eccentricity, base pressure | Retaining-wall section, geotechnical report extract, groundwater record, surcharge/load plan, stability calculation sheet. |
| Civil-ground retaining interface | discipline-interface, evidence-assembly | civil Rankine pressure assumptions, ground lateral-pressure assumptions, foundation capacity inputs | Civil wall section, ground investigation logs, material design table, cross-discipline assumption register. |

## Detailed Thread: Civil Services And Environmental Systems

Detailed pass: `detailed-passes/civil-services-environmental-systems-006.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Roof drainage package | pipeline, standard-selection | roof area, rainfall intensity, gutter profile/grade, downpipe count, design flow, selected capacities | Roof plan, gutter/downpipe schedule, rainfall table, AS/NZS 3500 capacity tables. |
| Gravity sewer reach package | pipeline, compliance-loop | design flow, invert levels, pipe length, selected diameter, slope, roughness, velocity compliance | Sewer long section, pipe material schedule, flow allocation table, velocity limits table. |
| Pump station duty package | pipeline, discipline-interface | flow, total dynamic head, suction head, friction loss, NPSHr, efficiencies, motor input power | Pump station section, pump curve, system curve, fluid-property table, motor schedule. |
| Construction water-quality package | shared-context, evidence-assembly | catchment area, rainfall, runoff coefficient, EMCs, soil loss rate, basin volume components | Catchment/land-use map, rainfall table, EMC table, erosion-control plan, sediment basin detail. |
| Industrial containment package | shared-context, constraint-loop | container inventory, largest/total volume, bund dimensions, equipment displacement, pollutant/spill context | Bund layout, container register, equipment layout, hazardous materials register, drainage isolation plan. |

## Detailed Thread: Civil Wind And Load Actions

Detailed pass: `detailed-passes/civil-wind-load-actions-007.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Wind action derivation chain | pipeline, evidence-assembly | regional wind speed, terrain category, multipliers, site wind speed, design pressure, tributary force | Site/aerial plan, wind region table, terrain-height table, pressure-zone drawing, tributary-area sketch. |
| Solar PV wind package | pipeline, discipline-interface | site wind speed, tilt, row position, module geometry, uplift/downforce/drag actions | Solar array layout, racking section, module schedule, PV coefficient table, site wind brief. |
| Limit-state action package | pipeline, governing-case | dead load, live load, wind action, earthquake action, occupancy category, psi factors, governing SLS/ULS | Structural load schedule, occupancy/use plan, AS/NZS 1170.0 factor table, wind/earthquake action source. |
| Civil-to-structural action interface | discipline-interface, evidence-assembly | wind force, uplift action, governing load combinations, action sign convention | Civil wind derivation package, structural member schedule, connection/foundation design inputs. |

## Detailed Thread: Ground Site Foundation And Retaining

Detailed pass: `detailed-passes/ground-site-foundation-retaining-008.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Site investigation interpretation package | pipeline, evidence-assembly | corrected SPT values, CPT `Ic`, `Su`, `phi`, unit weight, groundwater state | SPT field sheet, CPT trace, borehole log, groundwater profile, equipment records. |
| Shallow foundation capacity and settlement package | pipeline, constraint-loop | soil parameters, footing geometry, bearing capacity, applied pressure, immediate settlement, consolidation settlement | Footing plan, load schedule, soil profile, lab/stiffness table, settlement stress profile. |
| Retaining-wall staged stability package | pipeline, evidence-assembly | `ka`, active/passive force, overturning moment, resisting moment, vertical load, net moment, bearing pressure | Retaining-wall section, surcharge plan, groundwater record, material table, wall force summary. |
| Civil-ground retaining interface | discipline-interface, method-comparison | civil all-in-one wall assumptions, ground staged wall assumptions, water-table/theory choices | Civil wall detail, ground wall section, theory note, assumption register. |

## Detailed Thread: Structural Systems And Materials

Detailed pass: `detailed-passes/structural-systems-materials-009.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Marine berth system package | pipeline, evidence-assembly | design berthing energy, corrected fender capacity, mooring design tension, utilisation/margins | Vessel schedule, berth layout, fender datasheet, mooring analysis, line datasheet. |
| Facade and bracket package | pipeline, discipline-interface | effective wind area, wind action, bracket service/factored loads, thermal movement, slot allowance | Facade elevation, bracket detail, wind pressure source, component schedule, tolerance table. |
| Pipe/support/foundation package | pipeline, discipline-interface | pipe dead load, support reaction, overturning moment, vertical load, bearing utilisation | Pipe schedule, insulation/fluid table, support layout, foundation plan, geotechnical bearing note. |
| Bridge member and detailing package | shared-context, evidence-assembly | composite section properties, load effects, lap length, concrete target strength | Composite section drawing, load effects table, reinforcement schedule, concrete production records. |
| Material compliance package | evidence-assembly, compliance-loop | steel chemistry, carbon equivalent, binder replacement, target strength, risk/pass flags | Mill certificate, welding specification, concrete mix design, production QA records. |

## Detailed Thread: Mechanical Fire Water Hydraulic Pump And Transient

Detailed pass: `detailed-passes/mechanical-fire-water-hydraulic-pump-transient-010.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Fire-water supply and sprinkler demand package | pipeline, supply-demand | hydrant curve coefficient, available flow, sprinkler discharge, pipe friction, elevation pressure, residual pressure margin | Hydrant flow test sheet, water-supply curve, sprinkler layout, sprinkler schedule, hydraulic calculation sheet. |
| Pipe reach hydraulic loss package | pipeline, evidence-assembly | flow, internal diameter, velocity, Hazen-Williams loss, fitting `K`, minor loss, total pressure loss | Pipe schedule, P&ID, fitting takeoff, material/roughness table, hydraulic profile. |
| Pump station duty and electrical handoff package | pipeline, discipline-interface | total dynamic head, suction loss, NPSHA, NPSHR, pump shaft power, motor input power, operating-flow ratio | Pump station section, pump curve, system curve, suction vessel data, fluid property table, motor schedule. |
| Transient and thrust restraint package | pipeline, scenario-portfolio | pipe wave speed, velocity change, surge pressure, operating pressure, bend angle, bend thrust force | Pipe material schedule, support/restraint drawing, transient event note, pipe alignment plan, thrust block detail. |
| Cross-discipline pipe/support/power package | discipline-interface, product-world | pipe pressure/losses, pump motor load, thrust/support reactions, foundation/bearing demand | Mechanical hydraulic package, structural pipe support layout, electrical load list, civil/ground foundation note. |

## Detailed Thread: Mechanical Treatment Process And Solids

Detailed pass: `detailed-passes/mechanical-treatment-process-solids-011.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Treatment process basis package | pipeline, evidence-assembly | design flow, concentration loads, active/product dose, HRT, reactor volume, conversion target | Process flow diagram, design-basis table, chemical datasheet, basin plan, kinetics table. |
| Activated sludge capacity package | pipeline, actual-vs-required | MLSS inventory, daily solids loss, actual SRT, required nitrification SRT, oxygen demand | Aeration basin schedule, lab reports, WAS/effluent operating data, seasonal temperature/DO table, nitrogen balance. |
| Solids and biogas package | pipeline, energy-handoff | BOD removed, observed yield, sludge production, volatile solids feed, biogas, methane energy | Sludge balance sheet, primary clarifier record, digester feed log, gas meter record, energy use schedule. |
| Clarifier dual-criterion package | shared-context, governing-case | active clarifier area, flow scenario, MLSS, SOR, SLR, utilisation/margins, governing criterion | Clarifier plan, active-unit schedule, flow table, MLSS lab record, Ten States/WEF criteria table. |
| Process-to-aeration package | discipline-interface, product-world | oxygen requirement, nitrification state, sludge production, future air demand and blower/power load | Process design basis, aeration design note, blower schedule, electrical load list. |

## Detailed Thread: Mechanical Life Safety Environment And Acoustics

Detailed pass: `detailed-passes/mechanical-life-safety-environment-acoustics-012.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Life safety prescriptive package | pipeline, evidence-assembly | floor area, area-per-occupant, design occupants, clear egress width, NAC load/capacity | Floor plan, occupancy schedule, code criteria table, egress plan, fire alarm device schedule. |
| Fire scenario and tenability package | pipeline, scenario-portfolio | growth coefficient, HRR at time, peak-limited branch, extinction coefficient, visibility margin, steel critical temperature | Design-fire table, HRR curve, smoke model output, egress route map, steel member/fire-protection schedule. |
| Building services room package | shared-context, product-world | room volume, supply airflow, ACH, gas connected/diversified load, room absorption, RT60 | Room schedule, ventilation schedule, gas appliance schedule, architectural plan/section, finish schedule. |
| Acoustic source-to-receiver package | pipeline, transformation-chain | source SPLs, combined SPL, octave-band A-weighting, source-receiver distance, target SPL | Equipment noise schedule, octave-band report, source map, receiver plan, acoustic criteria table. |
| Structural-fire interface | discipline-interface, evidence-assembly | structural load ratio, protection trigger, critical steel temperature, protection required | Structural utilisation extract, fire protection schedule, design-fire scenario, member schedule. |

## Detailed Thread: Mechanical Dynamics Thermal And Verification

Detailed pass: `detailed-passes/mechanical-dynamics-thermal-verification-013.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Rail dynamics and signalling package | pipeline, discipline-interface | Davis resistance, tractive power, braking distance, stopping time, gradient sign, signal/overlap distance | Rolling-stock datasheet, speed profile, route gradient table, braking curve, signal layout. |
| Simulation verification package | evidence-assembly, meta-harness | mass-balance closure, GCI observed order, fine-grid GCI, asymptotic range ratio, credibility decision | Process stream table, CFD report, mesh table, convergence plot, simulation QA note. |
| Thermal process unit package | pipeline, source-direction | hot/cold stream temperatures, flow arrangement, LMTD, corrected MTD, heat duty, minimum approach | Heat exchanger datasheet, process stream table, P&ID, TEMA/correction-factor note. |
| Equipment reliability package | pipeline, scenario-portfolio | frequency ratio, transmissibility, isolation efficiency, fatigue bins, cumulative damage, remaining margin | Equipment speed schedule, isolator datasheet, vibration spectrum, duty-cycle histogram, fatigue table. |
| Compressed-air utility package | shared-context, product-world | connected demand, simultaneity factor, simultaneous demand, compressor/receiver handoff | Tool schedule, plant layout, operating scenario table, compressor schedule. |

## Detailed Thread: Electrical Power Storage PV And Loadflow

Detailed pass: `detailed-passes/electrical-power-storage-pv-loadflow-014.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Equipment supply and backup package | pipeline, discipline-interface | connected load, maximum demand, future allowance, critical load, autonomy, battery Ah, UPS VA, cable drop | Equipment load list, design basis, UPS/battery schedule, ambient table, single-line diagram, cable schedule. |
| PV and storage package | pipeline, product-world | DC/AC ratio, annual yield, string min/max modules, DC voltage drop, energy loss, BESS BOL/usable capacity | PV layout, module datasheet, inverter datasheet, site climate/solar table, DC cable schedule, BESS duty table. |
| Feeder voltage and reactive power package | pipeline, repair-loop | real/reactive load, initial/target PF, capacitor kVAr, feeder current, voltage drop, receiving-end voltage | Load study, metering record, feeder schedule, line parameters, PFC target note, single-line diagram. |
| Fault current to protection package | pipeline, safety-interface | source/transformer/cable impedance, total impedance, initial fault current, peak current | Single-line diagram, transformer datasheet, source fault level note, cable schedule, IEC voltage-factor table. |
| Mechanical-load electrical handoff | discipline-interface, evidence-assembly | pump motor input, compressor load, ventilation/fire loads, supply kVA, feeder drop | Mechanical load schedule, motor schedule, electrical load list, cable schedule, supply criteria. |

## Detailed Thread: Electrical Cables Lines Earthing And Fault Safety

Detailed pass: `detailed-passes/electrical-cables-lines-earthing-fault-safety-015.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Switchboard fault safety package | pipeline, safety-interface | fault location, bolted current, peak current, busbar force/stress, arcing current, incident energy, PPE category | Single-line diagram, transformer datasheet, switchboard layout, busbar detail, protection study, arc-flash label. |
| Cable and feeder physical rating package | pipeline, repair-loop | cable size/material, installation method, derated ampacity, AC resistance, voltage drop, fault impedance | Cable schedule, installation drawing, ampacity table, ambient condition note, feeder schedule. |
| Overhead line parameter and weather package | shared-context, discipline-interface | line GMD/GMR, inductance, capacitance, thermal ampacity, wind load, ice load | Tower geometry, conductor datasheet, weather table, terrain map, route profile, surface-condition note. |
| OLE sag and weather loading package | pipeline, rail-interface | wire weight, horizontal tension, sag, wire length, wind/ice load, clearance handoff | OLE span schedule, contact-wire datasheet, tensioning table, route profile, weather load table. |
| Grounding and fault-current package | pipeline, safety-interface | soil resistivity, grid resistance, grid current, GPR, fault current | Earthing layout, soil resistivity report, fault-current study, grid conductor schedule. |

## Detailed Thread: Electrical Lighting And Energy Performance

Detailed pass: `detailed-passes/electrical-lighting-energy-performance-016.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Interior lighting quality and energy package | pipeline, product-world | room area, luminaire flux/count, average illuminance, task uniformity, installed power, LENI | Room plan, luminaire schedule, photometric grid, lighting criteria table, control/daylight schedule, energy model extract. |
| Road lighting compliance and energy package | pipeline, discipline-interface | road section area, luminance grid, target class, uniformity margin, AECI, PDI, dimming profile | Road geometry, road lighting grid, luminaire layout, road class table, control profile, power schedule. |
| Sports field lighting package | shared-context, scenario-portfolio | field area, target class, average illuminance, U1/U2 uniformity, power load | Field plan, sports lighting class table, luminaire layout, photometric grid, operating scenario. |
| Lighting load handoff package | discipline-interface, evidence-assembly | installed lighting power, system power, annual energy, connected load, feeder load | Lighting schedule, energy performance record, electrical load list, distribution board schedule. |

## Detailed Thread: Electrical Transport Signalling And Vertical Transportation

Detailed pass: `detailed-passes/electrical-transport-signalling-vertical-017.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Road signal timing package | pipeline, evidence-assembly | approach speed, road grade, yellow interval, intersection width, all-red interval, crosswalk clearance | Intersection plan, vertical profile, speed survey, design vehicle table, pedestrian criteria, signal timing sheet. |
| Rail signalling and braking package | pipeline, discipline-interface | line speed, track gradient, braking rate, sighting distance, overlap, danger-point clearance, strike-in distance | Track profile, signal layout, braking table, adhesion scenario, level crossing plan, mechanical braking output. |
| Station vertical movement package | shared-context, product-world | building population, RTT, lift count, handling capacity, interval, escalator capacity, shaft/car dimensions | Lift traffic study, lift group schedule, escalator datasheet, station plan, shaft/car drawings, accessibility criteria. |
| VMS readability and ITS display package | pipeline, content-interface | character height, road speed, reading time, message length limit, communications handoff | VMS schedule, roadway speed plan, message library, readability criteria, ITS communications plan. |

## Detailed Thread: Electrical Communications Security And Instrumentation

Detailed pass: `detailed-passes/electrical-comms-security-instrumentation-018.md`

| Product World | Pattern | Handoff Fields | Multimodal Source Pack |
| --- | --- | --- | --- |
| Security systems package | pipeline, product-world | door count, controller count, system load, backup Ah, camera PPM, storage TB, PoE headroom, bandwidth | Door schedule, access-control riser, camera schedule, retention policy, PoE switch schedule, network topology. |
| Structured communications link package | pipeline, repair-loop | conduit fill, cable/pathway membership, fibre loss, RF path loss, link margin, required bandwidth | Conduit schedule, cable schedule, patching diagram, radio path profile, transceiver/radio datasheets, topology. |
| Instrumented process control package | pipeline, discipline-interface | instrument range, 4-20 mA signal, process value, valve pressure drop, Cv, choked-flow flag | P&ID, loop schedule, valve datasheet, process data sheet, fluid property table. |
| ITS display and backhaul package | pipeline, content-interface | VMS message length, ITS bandwidth, fibre/RF backhaul margin | VMS schedule, message library, ITS device inventory, network topology, link budget. |
