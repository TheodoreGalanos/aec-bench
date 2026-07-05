# ABOUTME: Source-bounded notes for the pump station duty package.
# ABOUTME: Preserves short evidence notes without copying full manuals or standards.

# Pump Station Duty Package Scraped Notes

## Public Orientation Sources

- Public pump-station summaries describe wet wells, pump-on/off levels, force mains, lift stations, redundancy, and risks from overflow or pump failure.
- Public centrifugal-pump summaries describe the relationship between required head, flow, pump curves, efficiency curves, power, and NPSH curves.
- Public NPSH summaries distinguish available NPSH from required NPSH and connect insufficient NPSH to cavitation risk.

## Ten States Recommended Standards

- The 2014 Recommended Standards for Wastewater Facilities include Chapter 40 for wastewater pumping stations.
- The chapter table of contents includes general requirements, design, suction-lift stations, submersible stations, screw pumps, alarm systems, emergency operation, instructions/equipment, and force mains.
- Wet-well sizing considers design fill time and minimum pump cycle time.
- The standards call for shutoff/check valves on discharge lines and maintenance access.
- Submersible pumps must be removable/replaced without personnel entering or dewatering the wet well.
- Alarm and emergency-operation requirements reinforce that a realistic task should include resilience and operations assumptions, not only hydraulics.

## Grundfos Pump Curves

- Grundfos describes a pump performance curve as the relationship between media flow `Q` and generated head `H` or pressure differential.
- Grundfos describes the efficiency curve as showing pump efficiency and the best efficiency point.
- Grundfos notes that performance curves are used with system characteristics when dimensioning and selecting pumps.
- Grundfos describes parallel pump curves as combining horizontally to increase flow and series pump curves as combining vertically to increase head.

## Grundfos Product Center

- The public Product Center page presents advanced pump selection as a way to find a product for installation requirements.
- The same surface exposes product comparison and application tools, including a Pumping Station Creator.
- This is useful evidence for the benchmark input shape: real pump selection starts from installation requirements, not from a free-floating formula.
- It still does not give us a captured, reusable pump curve artifact with head-flow, efficiency, power, and NPSHr overlays; that remains a fixture gap.

## Xylem Flygt Product And Case-Study Evidence

- Xylem describes Flygt N-technology pumps as self-cleaning non-clog wastewater pumps with sustained efficiency, material/impeller choices, submersible and dry installation options, and broad wastewater application coverage.
- The product page exposes real selection dimensions: capacity, head, motor power, solids/sludge handling, abrasive/corrosive wastewater, sump design, water hammer, pump-start analysis, transient analysis, CFD, and scale-model testing.
- The Columbus OARS case study describes a deep-tunnel pumping system with a 60-mgd capacity, large variation in static head between empty and full tunnel conditions, and multiple adjustable-speed pumps.
- The Bathurst lift-station case describes monthly maintenance to remove fibrous clogs and a pump replacement framed around sustained efficiency and clog resistance.
- These sources improve real-world use-case grounding and multimodal scenario design, but they are manufacturer case studies. They do not provide open curve-point datasets with NPSHr/power overlays.

## Xylem NPSH, Cavitation, LCC, And Sustained Efficiency White Papers

- Xylem's cavitation paper defines NPSH as the difference between absolute total pressure at the pump impeller eye and liquid vapor pressure, converted to liquid head.
- The paper describes cavitation-performance testing as running the pump at different NPSH levels while measuring head, flow, and power, then deriving NPSH3 performance and establishing an NPSH3 curve across flow rates.
- It distinguishes NPSHi, NPSH0, NPSHR, and NPSHav. For benchmark design, this supports a source-pack distinction between pump characteristic curves and installation-specific available NPSH.
- The paper says reliable operation is generally checked by comparing NPSHav and NPSHR at the relevant flow rate, and later emphasizes checking the condition for all possible duty points.
- The paper is especially useful for multi-pump and VSD variants: it discusses cases where a primary duty point may sit near BEP when multiple pumps run, while single-pump or reduced-speed operation can move into a more critical flow region.
- It also identifies real remediation levers: increasing submergence, improving suction design, trimming the impeller, using a VSD, or throttling on the discharge side. These are good meta-harness mutation axes.
- Xylem's LCC white paper grounds pump-station selection in more than capital cost: energy, maintenance, downtime, and operating conditions can dominate the lifetime outcome.
- The LCC paper warns against sizing only for maximum inflow and emphasizes matching the pump's BEP with the most frequent flow, using diurnal flow and duration-curve style evidence.
- The sustained-efficiency paper defines pump efficiency as hydraulic output power divided by shaft input power and distinguishes clean-water published performance from actual wastewater operation.
- The sustained-efficiency paper reports that actual non-clog pump operating efficiency can be materially below published efficiency because of clogging and wastewater conditions. This supports long-horizon tasks that compare initial selection against measured energy/runtime drift.
- These papers do not replace a specific pump curve export with numeric Q-H/efficiency/power/NPSHr data, but they close a large part of the NPSH, energy, and wastewater-efficiency semantics gap.

## Wastewater Pump-Station Simulator And SCADA Paper

- Eshkofti et al. frame municipal wastewater pump stations as critical infrastructure with dynamic hydraulic loads, frequent starts/stops, surcharging, transient events, and mechanical/electrical stress.
- The paper models a three-pump wastewater station with sump water level, inflow/outflow mass balance, parallel pumps, pump/system curve intersection, VFD/soft-start logic, lead/lag operation, power computation, and fault scenarios.
- It reports calibration against high-frequency SCADA from a municipal pump station, with one-second measurements including pump states, electrical quantities, water level, and power consumption.
- It explicitly distinguishes pump-side faults, such as blockage/wear, from system-side faults, such as pipe clogging or valve throttling.
- This is valuable for long-horizon product-world variants because it connects design data, controls, monitoring, diagnosis, and operational maintenance. The raw SCADA dataset is not presented as a reusable public fixture in the current source.

## Inter-Catchment Wastewater Transfer Paper

- Zhang et al. study a real sewer system in Drammen, Norway, where the Muusoya and Solumstrand wastewater treatment plants have different treatment capacities and combined-sewer shares.
- The paper frames inter-catchment wastewater transfer as an operational strategy to reduce overflow by moving wastewater when one treatment area is constrained and another has spare capacity.
- It identifies the Soren Lemmich pump station as a bottleneck for the whole strategy; pump-station operation must respond sensitively, or transfer can worsen upstream burden instead of reducing overflow.
- The paper uses a hydraulic model and monitoring data to evaluate overflow reduction and uses multi-step water-level prediction for pump-station operation.
- This is not a pump selection curve source, but it is a strong long-horizon operations source: pump-station tasks can combine hydraulic model state, WWTP capacity, pump control, water-level prediction, and overflow risk.

## Direct Search And Access Dead Ends

- Direct public search still did not produce a clean reusable manufacturer curve export with selected duty point, impeller/speed, head-flow, efficiency, power, and NPSHr fields.
- Direct access attempts for KSB Amarex product pages returned HTTP 503 in the current environment; direct Sulzer XFP URL guesses returned 404. These are not evidence that the documents do not exist, only that this pass did not recover them.
- Additional broad searches for `NPSHr`, pump curves, PDFs, and manufacturer names mostly returned general pages or irrelevant/noisy results rather than fixture-grade artifacts.
- DuckDuckGo HTML fetches returned anomaly/challenge pages in the current environment. Bing result pages for manufacturer and Australian regional searches were noisy and did not expose stable curve-export or utility-standard links suitable for source indexing.
- Candidate WSAA routes for an Australian sewage pumping station code resolved to a login/404 site shell from this environment, and a targeted WSAA index search did not recover a public page with usable criteria. Treat WSAA/utility code access as an unresolved regional-source route, not as captured evidence.
- A South East Queensland targeted search likewise did not recover stable public criteria during this pass.
- Next pump-source work should prefer known product-document portals, manufacturer selection exports, utility standard portals, authorised distributor PDFs with stable URLs, or an explicitly captured manufacturer selection output rather than repeating generic web search.

## FHWA HEC-22 Context

- FHWA HEC-22 is not a pump station design manual, but it supports the storm-drainage context where pumping/lifting may be required when gravity discharge is constrained.

## Source Quality Note

- The regulatory/design side is grounded by Ten States; the product-selection and real-use-case side is now stronger through Grundfos, Xylem/Flygt, Xylem white papers, and two operational modelling papers. NPSH semantics are now much stronger, but product-specific numeric power/NPSHr curve exports remain weak.
