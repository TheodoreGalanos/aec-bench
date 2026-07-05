# ABOUTME: Real and near-real artifact examples for pump station duty task grounding.
# ABOUTME: Identifies public inputs, outputs, reports, and fixture candidates for benchmark design.

# Pump Station Duty Artifact Examples

## Public Artifacts Found

| Artifact | Source | Input/Output Shape | Benchmark Use |
| --- | --- | --- | --- |
| Ten States Recommended Standards for Wastewater Facilities | https://www.health.state.mn.us/communities/environment/water/docs/tenstates/tenstatestan2014.pdf | Pumping-station design requirements, wet-well and emergency-operation criteria, force-main sections. | Strong source for wastewater pump-station scenario requirements. |
| Grundfos pump curves explainer | https://www.grundfos.com/solutions/learn/research-and-insights/pump-curves | Q-H performance curves, efficiency curves, series/parallel behavior, system-characteristic selection basis. | Source for pump-curve fixture expectations and duty-point reasoning. |
| Grundfos Product Center | https://product-selection.grundfos.com/ | Advanced selection, pump sizing, product comparison, and Pumping Station Creator entry points. | Real-world tooling analogue for source-pack inputs and product-selection workflow; specific curve exports still need capture. |
| Xylem Flygt N-Technology product page | https://www.xylem.com/en-us/products--services/pumps-packaged-pump-systems/pumps/submersible-pumps/wastewater-pumps/n-technology-pumps/ | Wastewater pump product family, non-clog/efficiency framing, capacity/head/motor ranges, application engineering, sump design, water hammer, pump-start, transient analysis, CFD, case-study index. | Real product-world evidence for pump family selection, scenario construction, and multimodal manufacturer-source packs. |
| Xylem Flygt Columbus OARS case study | https://www.xylem.com/en-us/resources/case-studies/flygt-columbus-oh-case-study/ | Deep tunnel, large pumping capacity, variable static head, adjustable-speed pump selections, tunnel dewatering scenario. | Real long-horizon pump-station use case for variable static head and multi-pump duty variants. |
| Xylem Flygt Bathurst lift-station case study | https://www.xylem.com/en-us/resources/case-studies/flygt-pumps-reduce-energy-cost-by-31-percent/ | Clogging/maintenance problem, pump replacement, motor size, service reliability, energy-cost framing. | Real failure-mode context for clogging, maintenance burden, and lifecycle/reliability variants. |
| Xylem cavitation white paper | https://www.xylem.com/en-in/resources/case-studies/pump-cavitation-and-how-to-avoid-it/ and PDF https://www.xylem.com/siteassets/support/tekniska-rapporter/white-papers-pdf/cavitation-white-paper.pdf | NPSH/NPSHav/NPSHR/NPSH3 semantics, head/flow/power measurement during cavitation testing, pump head/power/efficiency curves, VSD/multi-pump duty-point discussion. | NPSH/cavitation source-pack note and verifier contract for checking NPSH margin at every relevant duty point. |
| Xylem/Flygt LCC white paper | https://www.xylem.com/en-us/resources/white-papers/life-cycle-costs-for-wastewater-pumping-systems/ and PDF https://amp.xylem.com/m/463178c0bad69b5e/original/Flygt-life-cycle-costs-for-wastewater-pumping-systems-white-paper.pdf | Life-cycle cost, energy, maintenance, diurnal flow/duration curve, common-flow/BEP matching, total head, overall pump efficiency. | Energy/LCC extension for long-horizon tasks where selection is judged over lifetime operation, not only first-cost TDH. |
| Xylem sustained-efficiency white paper | https://www.xylem.com/en-us/resources/case-studies/understanding-sustained-efficiency-in-non-clog-pumps/ and PDF https://www.xylem.com/siteassets/support/tekniska-rapporter/white-papers-pdf/understanding-sustained-efficiency-in-non-clog-pumps.pdf | Wastewater pump efficiency definition, clean-water published performance versus actual wastewater operation, clogging-related efficiency drift. | Monitoring/diagnosis fixture for energy drift, clogging, and sustained-efficiency claims. |
| Wastewater pump-station simulator paper | https://arxiv.org/abs/2511.11304 | Sump geometry, pump/system curves, VFD/soft-start control, lead/lag thresholds, SCADA variables, simulated faults, energy/runtime/start-count outputs. | Strong report-shaped artifact for long-horizon monitoring/control/diagnosis variants; raw reusable dataset still unavailable. |
| Inter-catchment wastewater transfer paper | https://arxiv.org/abs/1811.06367 | Real Drammen sewer-system hydraulic model, WWTP capacity constraints, Soren Lemmich pump-station bottleneck, water-level prediction, overflow reduction scenarios. | Operational-control artifact for composite pump-station plus treatment-capacity plus sewer-overflow tasks. |
| FHWA HEC-22 | https://www.fhwa.dot.gov/engineering/hydraulics/pubs/10009/10009.pdf | Drainage context where pumping/lifting may be required. | Useful for stormwater pump-station variants. |

## Fixture Candidates

- Wet-well section drawing with pump-off, pump-on, high-level, invert, and overflow levels.
- Force-main profile with pipe/fitting schedule and receiving hydraulic grade.
- Manufacturer pump curve image/PDF with head-flow, efficiency, power, and NPSHr curves.
- NPSH/cavitation source note with NPSHa/NPSHr comparison, BEP-relative duty points, and VSD/parallel-pump cases.
- Duty table for average, peak, firm-capacity, duty/standby, and emergency cases.
- SCADA/control fixture with water level, pump states, current/voltage/power, flow/head estimates, start/stop thresholds, and fault labels.
- Case-study narrative fixture with problem statement, pump type, duty/capacity requirements, selected equipment, operations impact, and maintenance outcome.
- LCC/energy fixture with diurnal flow/duration curve, common-flow duty, energy tariff, maintenance assumptions, and comparison of pump alternatives.

## Remaining Artifact Need

- Public pump-curve examples with NPSHr/power overlays that are reusable as benchmark inputs.
- Captured numeric curve exports from a manufacturer selection tool, including selected impeller/speed, duty point, efficiency, power, and NPSHr.
- Real pump-station calculation reports with TDH/system-curve/NPSH tables.
- Redistributable SCADA/control datasets or simulator source once publicly released and license-checked.
- Regional utility standards for Australia/NZ and UK wastewater pumping stations.
- Public or authorised utility/manufacturer portal outputs that tie a selected pump curve to a regional pump-station design basis rather than only providing generic curve semantics.
