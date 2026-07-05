# ABOUTME: Analysis for grounding the PV storage feeder package in real workflows.
# ABOUTME: Summarizes workflow chain, inputs, outputs, benchmark implications, and multimodal scope.

# PV Storage Feeder Package Analysis

## Real Workflow Chain

The chain is realistic:

load profile and site constraints -> solar resource -> PV array/inverter configuration -> annual/monthly/hourly production -> PV+BESS optimization and dispatch -> SLD/interconnection/export basis -> feeder ampacity, voltage-drop, and power-flow checks -> equipment eligibility, protection settings, commissioning evidence, and compliance note.

The key boundary is that PVWatts/SAM/REopt can ground production, techno-economic modelling, and storage dispatch, but feeder design and compliance need electrical standards, utility rules, equipment-list evidence, commissioning requirements, and drawing-level source packs.

GreenEVT/SMART-DS adds a credible public route for feeder/load-profile substrate. It should not be mistaken for a code-compliant PV+BESS design package, but it gives realistic OpenDSS network objects, loads, limits, and simulation outputs that can feed composite electrical tasks. Repository inspection strengthens this: the OpenDSS data notes name `Master.dss`, bus coordinates, bus metadata, longitude/latitude bus coordinates, and scenario-specific feeder load files; the solver script shows how scenario EV loads become timestamped overload reports.

Energy Networks Australia and PG&E Rule 21 add the missing interconnection-world shape: SLD content, PCC/export basis, protection/control modes, inverter/storage metadata, equipment data sheets, static DER data, commissioning test evidence, and export-control options. CEC equipment lists add a separate eligibility/list-check layer for PV modules, inverters, battery/ESS equipment, meters, and PCS functionality.

## Real Inputs

- Site location, weather dataset, array tilt/azimuth, module type, array type, losses, DC/AC ratio, inverter efficiency, albedo/soiling.
- Load profile: interval data, peak demand, critical loads, demand charges, export constraints, or resilience target.
- Optimization basis: tariff, outage/resilience assumptions, emissions or cost objective, candidate PV/BESS/generator technologies, minimum critical-load coverage, and dispatch time step.
- Feeder model data: buses, lines, transformers, loads, voltage/current limits, peak planning loads, and time-series loads where available.
- Battery capacity, usable depth of discharge, inverter rating, round-trip efficiency, dispatch policy, and reserve margin.
- Interconnection source pack: connection point, PCC, EG/PV/BESS units, load/meter/breaker/isolator locations, SLD, cable route length, conductor material/size, installation method, temperature, voltage, phase, protection device data, and control-system description.
- DER register/static data: NMI or account identifier where applicable, approved capacity, phases, inverter make/model/serial/status/kVA, storage capacity, islandable status, protection/control modes, voltage/frequency settings, volt-watt/volt-var settings, demand-response behavior, ROCOF/vector-shift/inter-trip fields where authority requires them.
- Equipment eligibility basis: PV module list, grid-support inverter list, battery/ESS list, meter list, PCS list, UL 1741/UL 1741 SA or local equivalent evidence, and utility/AHJ smart-inverter functionality requirements.
- Applicable authority basis: NEC/NFPA, IEEE 1547, IEC 62548-1, AS/NZS 5033/4777/5139, ENA guidelines, Rule 21 or utility-specific rules, and task-supplied excerpts where full standards are gated.

## Real Outputs

- PV production estimate: monthly/annual AC energy, capacity factor, solar resource, hourly outputs if required.
- PV+BESS optimization result: selected PV/storage/generator capacity, dispatch schedule, cost/resilience/emissions metrics, and assumptions.
- Feeder voltage-drop, ampacity, voltage, overload, and power-flow checks.
- Interconnection package completeness check: SLD fields, export/non-export/limited-export basis, equipment data sheets, control-system description, and required static DER data.
- Equipment-list and smart-inverter/PCS eligibility check.
- Protection, export-control, and commissioning note with assumptions and required test evidence.
- Single-line mark-up, cable schedule update, or static DER register extract.
- Feeder simulation outputs: bus voltages, component currents/power flows, overload flags, voltage violations, and scenario comparison.

## Harness Implications

- PVWatts API examples provide excellent structured input/output fixtures for benchmark generation and verification.
- REopt adds a higher-level optimization fixture path where PV/BESS sizing and dispatch must be checked against cost, resilience, emissions, or export objectives rather than only against annual PV energy.
- The verifier should distinguish model outputs from code compliance, interconnection completeness, equipment eligibility, and commissioning outputs. PV production can be numerically checked; code compliance may need task-supplied criteria; SLD/equipment/commissioning checks can be structured evidence checks.
- For feeder model-world variants, a good first verifier can check that `Master.dss` was compiled, scenario loads were applied at the right buses/timestamps, and exported overload/voltage reports match expected thresholds.
- A useful composite verifier split is: production model -> optimization/dispatch -> SLD/interconnection completeness -> equipment-list/PCS eligibility -> feeder simulation/study -> commissioning/export-control evidence -> final engineering note.
- Strong failure modes include confusing DC and AC capacity, using annual average energy for peak feeder ampacity, ignoring inverter clipping, treating battery nameplate capacity as usable energy, claiming non-export without an export-control basis, using unlisted or mismatched inverter/ESS equipment, and treating a PVWatts result as a complete interconnection application.

## Multimodal Extension

- Inputs: single-line diagram, roof/site plan, feeder map, cable schedule, load profile chart, inverter/ESS/PCS datasheets, CEC/utility equipment-list extracts, PVWatts/SAM/REopt output files, and OpenDSS feeder files.
- Outputs: annotated SLD, DER register/static-data table, cable schedule changes, PV/BESS sizing and dispatch table, feeder-study summary, equipment-list check, commissioning checklist, and compliance note.
- Interesting checks: extracting cable lengths and breaker ratings from drawings, matching inverter count to array size, comparing load chart peaks to feeder sizing, checking PCC/export-control consistency, and reconciling equipment datasheets with list eligibility.

## Meta-Harness Opportunities

- Reconfigure region/code basis: NEC, IEC, AS/NZS, utility-specific.
- Swap objective: bill savings, resilience, export limitation, feeder constraint relief, or carbon.
- Mutate solar resource, orientation, battery size, feeder length, and conductor material.
- Combine with earthing/arc-flash by passing SLD and fault/protection data downstream.
- Combine with road/rail/civil/geospatial worlds by passing site/feeder location, ROW constraints, or GIS parcels into the source pack.
- Run a meta-harness pass that selects which layers are active for a given world: PV-only production, PV+BESS optimization, utility interconnection, feeder simulation, equipment eligibility, commissioning, or cross-domain electrical safety handoff.
