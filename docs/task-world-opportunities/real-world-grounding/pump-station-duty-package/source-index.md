# ABOUTME: Source index for grounding the pump station duty composite template.
# ABOUTME: Records real pump station sources and evidence gaps for duty, power, and NPSH chains.

# Pump Station Duty Package Source Index

## Current Chain Confidence

The chain is realistic: wet-well/site levels and pipework define static lift and system losses; pump curves intersect the system curve to define the duty point; power and efficiency follow from flow/head; NPSH checks prevent cavitation.

The design-manual source set is weaker than stormwater because many pump station manuals are scattered across utilities or are not easily accessible. We have enough public evidence to keep the chain, and recent manufacturer/case-study/simulator evidence makes the product-world side stronger. Xylem/Flygt white papers now strengthen the NPSH/cavitation, energy, life-cycle-cost, and sustained-efficiency side. A fresh public search pass sharpened rather than closed the remaining gap: broad NPSHr/pump-curve searches, targeted manufacturer searches, DuckDuckGo/Bing result inspection, and candidate Australian WSAA/SEQ routes did not recover a stable reusable selected pump curve export or public regional utility criteria. This is an access/search boundary, not evidence that those artifacts do not exist. The hardening gap remains product-specific: we still need a clean curve export or data sheet that combines numeric head-flow, efficiency, power, duty point, impeller/speed, and NPSHr values for deterministic grading.

## Sources

| Source | Type | Region | Relevance |
| --- | --- | --- | --- |
| Great Lakes - Upper Mississippi River Board, Recommended Standards for Wastewater Facilities, 2014 Edition. https://www.health.state.mn.us/communities/environment/water/docs/tenstates/tenstatestan2014.pdf | primary-open/government-adopted guidance | US/Canada Great Lakes region | Strong public source. Chapter 40 covers wastewater pumping stations; the table of contents identifies design, suction-lift, submersible, screw pump, alarm, emergency operation, instructions/equipment, and force main sections. |
| Grundfos, Pump curves. https://www.grundfos.com/solutions/learn/research-and-insights/pump-curves | industry-practice/example-artifact | Global | Manufacturer-backed explanation of efficiency curves, pump performance curves, Q-H relation, head/pressure conversion, variable-speed curves, parallel/series pump behavior, and use of curves with system characteristics for pump selection. |
| Grundfos Product Center. https://product-selection.grundfos.com/ | industry-tool/example-artifact | Global | Manufacturer product-selection surface for finding pumps against installation requirements. Public page exposes advanced selection, pump sizing, product comparison, and a Pumping Station Creator; useful as a real-world analogue for task inputs even where specific curve exports still need capture. |
| Xylem Flygt N-Technology pumps. https://www.xylem.com/en-us/products--services/pumps-packaged-pump-systems/pumps/submersible-pumps/wastewater-pumps/n-technology-pumps/ | manufacturer/product metadata and case-study index | Global | Public manufacturer page for wastewater pumps. Grounds non-clog/efficiency/material choices, capacity/head/motor ranges, application-engineering services, sump design, water hammer, pump-start and transient analysis, CFD, and real case-study contexts. |
| Xylem Flygt Columbus OARS case study. https://www.xylem.com/en-us/resources/case-studies/flygt-columbus-oh-case-study/ | manufacturer case study | US | Real deep-tunnel pump-station use case: 215-ft deep, 60-mgd pumping system, highly variable static head, multiple adjustable-speed pumps, and dewatering after large flow events. Good long-horizon product-world analogue; not a reusable curve dataset. |
| Xylem Flygt Bathurst lift-station case study. https://www.xylem.com/en-us/resources/case-studies/flygt-pumps-reduce-energy-cost-by-31-percent/ | manufacturer case study | US | Real lift-station maintenance/clogging use case: monthly pump pulls, fibrous clogging, replacement with N-technology pumps, and energy/reliability framing. Useful for failure-mode/task-story design; not a calculation fixture. |
| Xylem, Pump cavitation and how to avoid it. https://www.xylem.com/en-in/resources/case-studies/pump-cavitation-and-how-to-avoid-it/ and PDF https://www.xylem.com/siteassets/support/tekniska-rapporter/white-papers-pdf/cavitation-white-paper.pdf | manufacturer white paper | Global/Flygt | Strong NPSH/cavitation source. Defines NPSH/NPSHav/NPSHR/NPSH3-style concepts, ties NPSH testing to head/flow/power measurement, discusses pump head/power/efficiency curves, and says NPSHav>NPSHR should be checked for all duty points. |
| Xylem/Flygt, Life cycle costs for wastewater pumping systems. https://www.xylem.com/en-us/resources/white-papers/life-cycle-costs-for-wastewater-pumping-systems/ and PDF https://amp.xylem.com/m/463178c0bad69b5e/original/Flygt-life-cycle-costs-for-wastewater-pumping-systems-white-paper.pdf | manufacturer white paper | Global/Flygt | Grounds life-cycle cost, energy, maintenance, diurnal flow/duration curves, common-flow/BEP matching, total head, overall efficiency, pump-station design tools, and system-design effects on energy/cost. |
| Xylem, Understanding sustained efficiency in non-clog pumps. https://www.xylem.com/en-us/resources/case-studies/understanding-sustained-efficiency-in-non-clog-pumps/ and PDF https://www.xylem.com/siteassets/support/tekniska-rapporter/white-papers-pdf/understanding-sustained-efficiency-in-non-clog-pumps.pdf | manufacturer white paper | Global/Flygt | Grounds wastewater-specific efficiency drift. Defines pump efficiency as hydraulic output power divided by shaft input power and distinguishes clean-water published performance from actual wastewater operating efficiency. |
| Eshkofti et al., Modeling and Physics-Enhanced Fault Detection in Wastewater Pump Stations. https://arxiv.org/abs/2511.11304 | academic/report-shaped artifact | Sweden/global | Recent wastewater pump-station simulator paper grounded against municipal SCADA. Includes sump mass balance, pump/system curve intersection, VFD/soft-start logic, lead/lag controls, power computations, one-second SCADA variables, and fault scenarios. Dataset and code release remain caveated. |
| Zhang et al., Enhancing Operation of a Sewage Pumping Station for Inter Catchment Wastewater Transfer by Using Deep Learning and Hydraulic Model. https://arxiv.org/abs/1811.06367 | academic/report-shaped artifact | Norway | Real sewer-system operation study in Drammen. Identifies the Soren Lemmich pump station as a bottleneck in inter-catchment wastewater transfer, uses a hydraulic model, wastewater-treatment capacity constraints, monitoring data, and multi-step water-level prediction. Useful for operational control variants. |
| Wikipedia, Pumping station. https://en.wikipedia.org/wiki/Pumping_station | secondary | Global | Useful orientation only. Confirms wet wells, pump-on/off levels, force mains, redundancy, and wastewater pump station operational risks. Needs replacement with primary manuals. |
| Wikipedia, Centrifugal pump selection and characteristics. https://en.wikipedia.org/wiki/Centrifugal_pump_selection_and_characteristics | secondary | Global | Orientation on total head, pump curves, system resistance, efficiency, and NPSH curve concepts. Needs manufacturer/HI/utility source. |
| Wikipedia, Net positive suction head. https://en.wikipedia.org/wiki/Net_positive_suction_head | secondary | Global | Orientation on NPSH available/required and cavitation. Needs Hydraulic Institute or manufacturer source. |
| FHWA HEC-22 pump/storm-drain context. https://www.fhwa.dot.gov/engineering/hydraulics/pubs/10009/10009.pdf | government-manual | US | Storm drainage outfall guidance mentions pumping/lifting when outlet invert conditions require it; not sufficient for full pump station design. |

## Real Inputs

- Wet-well levels: high/low/start/stop/alarm, emergency storage, operating volume.
- Site profile: suction/discharge elevations, outfall or receiving system hydraulic grade.
- Pipe schedule: lengths, diameters, fittings, roughness, valves, minor-loss coefficients.
- Pump curve: head-flow, efficiency, power, NPSHr, impeller diameter/speed.
- Duty requirements: design flow, peak flow, redundancy arrangement, operating philosophy.
- Cavitation/NPSH basis: NPSHa/NPSHr margin, suction configuration, submergence, operating flow region relative to BEP, and all relevant single/parallel/VSD duty points.
- Electrical constraints: motor rating, starting method, feeder capacity, standby power.
- Operating data for long-horizon variants: pump states, level time series, starts/runtime, current/voltage/power, inflow/overflow, alarms, and fault labels.

## Real Outputs

- System curve and selected duty point.
- TDH at design and peak cases.
- Pump/motor power and efficiency check.
- NPSH available versus required margin.
- Wet-well cycle/storage check.
- Pump selection note and duty handoff table.
- Energy/life-cycle-cost or sustained-efficiency note for wastewater duty variants.
- Operating/control and monitoring handoff: lead/lag sequence, VFD or soft-start assumptions, energy/runtime, and diagnostic flags.

## Task Implications

- The current template chain is correct and now has at least one strong public wastewater-pumping design source plus manufacturer-backed pump-curve, product-selection, case-study, NPSH/cavitation, LCC/energy, sustained-efficiency, and SCADA/control evidence. Product-specific numeric curve exports still need capture.
- The benchmark should not rely only on final scalar TDH. It should preserve pump curve evidence, system curve assumptions, and NPSH margin.
- Strong branch decisions: duty/standby configuration, pump type, operating wet-well level, and force-main roughness/fitting basis.
- Generic manufacturer explainers and white papers should support verifier semantics, not stand in for selected product data. A fixture-grade source pack should require structured selected-curve fields or a digitized/verified chart with explicit provenance.
