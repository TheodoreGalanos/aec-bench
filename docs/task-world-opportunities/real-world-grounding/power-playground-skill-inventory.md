# ABOUTME: Inventories the local Power Playground electrical review skill pack.
# ABOUTME: Maps SME review workflows to possible aec-bench task-world inputs, checks, and outputs.

# Power Playground Skill Inventory

This inventory summarizes the local SME-authored power distribution skill pack copied to `research/Power-Playground-main`. The copied source pack is intentionally ignored by git via the repo-level `research/` rule; this document is the distilled, tracked inventory.

The pack is not a runnable software project. Its own `AGENTS.md` notes that there are no root manifests, lockfiles, CI workflows, or local OpenCode config files. It is a set of electrical engineering review skills: four concrete domain skills plus one reusable review-skill template.

## Pack Contents

| Item | Source Path | What It Is |
| --- | --- | --- |
| Root README | `research/Power-Playground-main/README.md` | Describes the skills pack, layout, four skills, and generic review-skill template. |
| Root AGENTS | `research/Power-Playground-main/AGENTS.md` | Repo-specific guidance: treat this as a skills pack, avoid inventing build/test/release workflows, and use lowercase hyphenated skill folders. |
| `earthing-study-review` | `research/Power-Playground-main/skills/earthing-study-review/` | Review workflow for earthing studies, grounding studies, EPR assessments, step/touch voltage calculations, soil resistivity models, and earthing layouts. |
| `hv-power-system-review` | `research/Power-Playground-main/skills/hv-power-system-review/` | Review workflow for HV SLDs, distribution designs, load schedules, cable schedules, layouts, and power-system study documents. |
| `protection-study-review` | `research/Power-Playground-main/skills/protection-study-review/` | Review workflow for 1 kV to 38 kV protection coordination studies, relay settings, TCC curves, one-lines, and equipment data. |
| `substation-safe-design-assessment` | `research/Power-Playground-main/skills/substation-safe-design-assessment/` | Drawing-led Safety In Design screening workflow for substation, switchroom, control building, and transformer compound GA drawings. |
| `templates/review-skill` | `research/Power-Playground-main/templates/review-skill/` | Generic scaffold for future checklist-led review skills. |

## Shared Review Pattern

Three of the four domain skills follow the same review protocol:

1. Inventory exactly what documents were provided.
2. Extract the relevant study basis, source values, equipment data, assumptions, criteria, and cross-document links.
3. Work through every checklist item sequentially.
4. Mark each item with exactly one status: `[P]` pass, `[F]` fail, `[N/A]` not applicable, or `[ID]` insufficient data.
5. Cite direct evidence for passes and failures; state exact missing information for `[ID]` items.
6. Perform quantitative adequacy checks only where source data supports them.
7. Produce a completed checklist, review findings summary, prioritized action list, and verification pass.

This pattern is a strong task-world shape because it defines source inventory, missing-data behavior, failure taxonomy, action prioritization, and verifier-like completeness checks.

## Skill Inventory

### Earthing Study Review

Purpose: review earthing and grounding studies for substations, switchyards, switchrooms, industrial electrical installations, and conductive infrastructure. The skill anchors to ENA EG-1, IEEE Std 80, AS 2067, and related Australian practice.

Primary inputs:

- earthing or grounding study report;
- earthing layout drawings;
- soil resistivity data and adopted layered soil model;
- fault current and protection clearing-time data;
- CDEGS, Current Distribution, or equivalent model outputs;
- SLDs, civil layouts, cable schedules, fence drawings, metallic services, telecoms, LV MEN, rail, pipeline, and adjacent infrastructure data;
- testing, commissioning, as-built, client standard, utility, and SID records where available.

Checklist structure: 13 sections and 88 checklist items:

- scope, standards, and design criteria;
- source data and study inputs;
- soil resistivity testing and soil model;
- fault current, grid current, and current division;
- earthing grid geometry and model representation;
- touch, step, mesh, and transferred voltage assessment;
- EPR and external interfaces;
- conductor, bonding, and material adequacy;
- mitigation measures and design controls;
- drawings, specifications, and constructability;
- testing, commissioning, and validation;
- documentation quality and traceability;
- general risk review.

Quantitative checks implied:

- compare touch, step, mesh, and transferred voltages against tolerable limits;
- check safety criteria use the same shock duration as protection clearing time;
- verify grid-current basis from fault current, split factors, and return paths;
- check earthing conductor thermal withstand against current and duration;
- verify surface-layer resistivity, thickness, extent, and maintenance assumptions;
- compare soil resistivity test data against the adopted layered model;
- reconcile EPR and transferred-voltage controls at fences, gates, pipelines, telecoms, LV MEN, rail, and metallic services;
- reconcile model geometry against earthing drawings.

Required outputs:

- completed checklist with `[P]`, `[F]`, `[N/A]`, and `[ID]` labels;
- findings summary with critical, non-critical, insufficient-data, and observation sections;
- prioritized action list with Priority 1 through Priority 4;
- final verification counts and most critical issues.

Good task candidates:

- Is this substation earthing study safe to issue?
- Do the soil model and fault-current basis support the step-touch result?
- Are transferred-potential risks handled at the fence and services?
- Does the earthing layout match the model and report conclusions?

Likely aec-bench mapping: `SSC-07` ground investigation and resistivity, `SSC-05` electrical SLD/protection interfaces, `SSC-14` foundation/support interfaces, and `SSC-20` standards and authority overlay.

### HV Power System Review

Purpose: review high-voltage power system designs for substations, switchrooms, industrial plants, mine sites, utilities, renewables, and large infrastructure. The skill is SLD-led but explicitly expects cross-checks against schedules, studies, layouts, and datasheets.

Primary inputs:

- single line diagram or one-line diagram;
- design basis or power-system report;
- load schedule or maximum-demand summary;
- cable or feeder schedule;
- fault-level, load-flow, motor-starting, harmonic, power-quality, and related studies;
- protection, arc-flash, and earthing documents;
- equipment datasheets and ratings;
- site layouts, GAs, cable route drawings, access and egress drawings;
- project requirements, grid connection data, utility supply agreements, and vendor interfaces.

Checklist structure: 16 sections and 98 checklist items:

- scope, standards, and design basis;
- input data and cross-document traceability;
- SLD completeness and drawing quality;
- system architecture and operating philosophy;
- load, demand, and capacity adequacy;
- load flow, voltage regulation, and power quality;
- fault level and equipment duty;
- transformers and neutral earthing;
- switchgear, breakers, and switching devices;
- cables, feeders, and overhead lines;
- protection, control, metering, and communications interfaces;
- earthing, arc flash, and safety interfaces;
- generation, grid connection, and power electronics;
- layout, constructability, and maintainability;
- studies, calculations, and model quality;
- documentation quality and risk review.

Quantitative checks implied:

- compare maximum demand plus margin against transformer, generator, feeder, busbar, switchgear, cable, and auxiliary ratings;
- compare fault levels against interrupting, making, short-time, peak, arc containment, CT/VT, cable, busbar, and earthing-switch duties;
- check minimum fault levels against protection sensitivity and trip reliability;
- reconcile transformer impedance, vector group, tap range, neutral earthing, NER, and parallel operation assumptions;
- check cable ampacity, short-circuit withstand, route length, voltage drop, derating, and clearing-time assumptions;
- review load-flow results for voltage regulation, loading, reactive power, power factor, and losses;
- review motor-starting or large-load energisation assumptions;
- confirm units, voltage bases, MVA bases, operating cases, and revision data are consistent.

Required outputs:

- completed checklist with evidence citations;
- findings summary with counts and critical issues first;
- prioritized action list;
- verification pass proving no checklist item remains unmarked.

Good task candidates:

- Is this HV single-line design ready for issue?
- Do the SLD, load schedule, cable schedule, and studies agree?
- Can the transformers, switchgear, feeders, and cables carry the stated operating cases?
- Are fault duty, protection, earthing, and arc-flash interfaces visible enough for design QA?

Likely aec-bench mapping: `SSC-05` electrical SLD/feeders/protection, `SSC-17` energy resources and storage, `SSC-06` equipment loads and motor duty, `SSC-13` communications/control interfaces, `SSC-19` fire and emergency interfaces, and `SSC-20` standards and authority overlay.

### Protection Study Review

Purpose: review medium-voltage protection coordination studies for 1 kV to 38 kV systems. The skill focuses on protection maloperation, equipment damage, safety risk, and documentation consistency.

Primary inputs:

- protection setting report with TCC curves, relay settings, and coordination analysis;
- one-line diagram;
- relay setting sheets or relay configuration exports;
- equipment data such as transformer, cable, motor, switchgear, CT, breaker, and NER information.

Checklist structure: 14 sections and 96 checklist items:

- system basics and modelling;
- transformer protection;
- feeder and cable protection;
- grading and selectivity;
- documentation and compliance;
- ground fault protection;
- motor protection;
- bus and differential protection;
- directional and distance protection;
- breaker failure and backup protection;
- voltage and frequency protection;
- arc flash considerations;
- numerical adequacy checks;
- general report quality and consistency.

Quantitative checks implied:

- compare phase overcurrent pickup against protected-equipment FLA;
- set instantaneous pickup above downstream maximum fault current with allowance for asymmetry;
- compare clearing I2t against cable withstand I2t;
- verify transformer through-fault protection clearing;
- verify motor starting curve clearance and safe-stall protection;
- verify ground-fault pickup sensitivity against minimum ground-fault current;
- measure coordination time interval between series device pairs;
- check LV main pickup against transformer secondary FLA where LV devices are included.

Required outputs:

- completed checklist with source citations;
- findings summary with critical findings first;
- action list by priority;
- final counts and verification that every visible protective device is addressed.

Good task candidates:

- Will the relay settings trip the right device first?
- Are transformer and feeder protection settings safe for the equipment?
- Do MV and LV protection curves coordinate on a common voltage base?
- Are cable, motor, and transformer damage limits protected by the proposed settings?

Likely aec-bench mapping: `SSC-05` protection and feeder design, `SSC-02` rail signalling/power interfaces where protection affects supply continuity, `SSC-06` motor and equipment protection, `SSC-18` instrumentation/control settings, and `SSC-20` standards and authority overlay.

### Substation Safe Design Assessment

Purpose: screen substation, switchroom, control-building, transformer-compound, and yard GA drawings for Australian Safety In Design workshop preparation. This is drawing-based pre-workshop screening, not formal compliance certification.

Primary input:

- PDF general arrangement drawing showing site plan, floor plan, elevations, sections, room names, equipment labels, door swings, dimensions, clearances, transformers, switchgear lineups, panels, battery rooms, access paths, fire walls, fencing, gates, bunds, drainage, services, or ventilation notes.

Workflow:

1. Parse and catalogue the drawing.
2. Build a spatial safety model with zones such as external approach, fenced HV yard, transformer area, control room, switchroom, battery room, cable areas, egress routes, maintenance routes, operator positions, and vehicle/lifting paths.
3. Screen hazards using the taxonomy and risk matrix.
4. Separate actual layout-driven hazards from verification items.
5. Produce one markdown output named `sid_substation_assessment.md`.

Hazard taxonomy: 12 categories:

- access, egress, and emergency escape;
- arc flash and switching exposure;
- electric shock, step potential, touch potential, and earthing interface;
- transformer fire, explosion, oil, and thermal release;
- battery room, DC, chemical, and gas hazard;
- fire detection, suppression, and emergency response;
- ventilation, heat, moisture, and environmental conditions;
- human factors and operability;
- maintenance, testing, replacement, and manual handling;
- security and unauthorised access;
- civil, structural, and general layout hazard;
- construction, installation, and commissioning hazard.

Classification logic:

- assign one primary hazard category and optional secondary tags;
- place commonly expected but not visible features in the verification log rather than the main risk register;
- require drawing evidence first;
- avoid generic hazards unless the drawing shows a layout-driven mechanism;
- classify likelihood, consequence, overall risk, and confidence.

Required output sections:

- assessment summary;
- drawing inventory;
- risk register with hazard ID, drawing reference, category, description, harm pathway, affected persons, visible controls, likelihood, consequence, risk, action, and confidence;
- considered-items and verification log;
- key assumptions and data gaps;
- priority workshop questions.

Good task candidates:

- What safety risks are visible in this substation layout?
- Which hazards should go into the SID workshop?
- Is the GA evidence enough to raise a design action?
- Which expected safety provisions are not verifiable from the drawing alone?

Likely aec-bench mapping: `SSC-05` electrical rooms and switchgear, `SSC-08` occupancy and egress, `SSC-19` fire/hazard/emergency response, `SSC-16` staging and construction/commissioning safety, `SSC-07` earthing and step-touch interfaces, and `SSC-20` authority/review overlay.

### Generic Review Skill Template

Purpose: scaffold future review skills. It provides frontmatter, a requested-inputs template, a six-section checklist, the shared `[P]`, `[F]`, `[N/A]`, `[ID]` status protocol, required findings/action outputs, and final verification pass.

Checklist structure: six sections and 26 checklist items:

- scope and design basis;
- input data completeness;
- technical adequacy;
- quantitative checks;
- documentation and deliverable quality;
- general risk review.

This template is useful as a pattern for future AEC-bench domain-review tasks because it makes the review contract explicit before domain-specific criteria are added.

## Cross-Skill Requirements

These requirements recur across the pack and are the strongest candidates for benchmark verifier design:

- inventory provided documents before judging;
- do not invent missing source data;
- distinguish failure from insufficient data;
- cite the source location for each failure;
- mark every checklist item or risk-log item;
- translate every failure into an action item;
- prioritize actions by safety, compliance, equipment damage, reliability, and information need;
- keep review scope explicit, especially where a single document cannot prove adequacy;
- perform numerical checks only when source data supports them;
- finish with counts and a verification pass.

## Conversion Opportunities For AEC-Bench

The pack suggests several high-value task families.

| Candidate Task Family | Best Source Inputs | Expected Output | Verifier Shape | Notes |
| --- | --- | --- | --- | --- |
| Earthing study acceptance review | Earthing report, soil table, fault-current/protection extract, layout table, EPR/touch-step results | Completed checklist, critical findings, action list | Check status labels, missing-data handling, computed margins, source-value echoes, and action priority | Strong fit for `SSC-07`; needs careful source-policy boundary around standards. |
| HV SLD cross-document QA | SLD-like topology table, load schedule, cable schedule, transformer data, fault/load-flow extracts | Review checklist, inconsistency findings, required actions | Check traceability between tags, ratings, loads, cables, fault duties, and study results | Strong fit for `SSC-05`; can reuse existing electrical-load and feeder templates as seeds. |
| Protection coordination review | TCC-derived curve table, relay settings, one-line, transformer/cable/motor data | Coordination findings and setting/action list | Check CTI, pickup, damage-curve clearance, voltage-base conversion, and report/setting consistency | Strong fit for `SSC-05` and `SSC-18`; may need synthetic TCC tables before graphical plots. |
| Substation SID GA screening | Redrawn GA or structured drawing object list with rooms, doors, equipment, hazards, dimensions | Risk register, verification log, workshop questions | Check hazard-vs-verification separation, drawing-evidence citations, likelihood/consequence/risk, and actionable design responses | Strong fit for `SSC-08`, `SSC-19`, `SSC-05`; hardest if source is only a PDF image. |
| Review-skill scaffold task | Domain-specific checklist plus small document packet | Completed checklist and action list | Check every item is marked and every fail/ID is handled | Useful as a generic pattern, but less domain-rich unless tied to one of the four power skills. |

## SSC Note Inserts

The first mapping pass added compact `Power Playground Skill-Derived Task Candidates` sections to the notes where the skills most directly fit. These inserts are design-note candidates only; they do not change product counts, runnable-template coverage, or benchmark-readiness claims.

| SSC Note | Inserted Candidate Themes |
| --- | --- |
| `SSC-05` Electrical SLD, feeder, load, and protection | HV SLD issue-readiness, protection coordination, and switchroom electrical-safety interface QA. |
| `SSC-07` Ground investigation, groundwater, and soil/resistivity | Earthing study acceptance, soil-model/fault-current basis, and transferred-potential boundary controls. |
| `SSC-08` Building occupancy, room, egress, and vertical movement | Switchroom egress during arc-flash/fire, operator switching position, and SID verification-log provisions. |
| `SSC-16` Construction, temporary works, environmental controls, and staging | Substation equipment installation/commissioning hazards and temporary safety controls during staged work. |
| `SSC-18` Instrumentation, controls, valve, and process signal | Protection/control settings reconciliation, intertrip/alarm logic, and safe-state handoff evidence. |
| `SSC-19` Fire, hazard, suppression, and tenability | Transformer or battery event effects on egress/emergency response and visible fire/containment provisions. |
| `SSC-20` Regional standards, authority, and review packet overlay | Checklist-to-action registers, authority-basis separation, evidence-status discipline, and non-claim boundaries. |

The broader long-horizon construction lesson from these skills is captured in `review-loop-long-horizon-lessons.md`. The first concrete note-level application is in `SSC-01`, where the review-loop lens reframes the road corridor as an auditable issue-readiness packet rather than only a sequence of calculations.

## Operationalization Gaps

The pack is rich enough to shape benchmark tasks, but it is not itself a benchmark source pack yet.

- No example input document sets are included.
- No golden completed checklists or action lists are included.
- No machine-readable schema exists for checklist items, findings, action priorities, or risk registers.
- No parsers or executable validators exist.
- Standards are named as review basis, but the pack does not provide standards text or acceptance tables.
- Drawing-based SID review will need either redrawn fixtures, structured drawing tables, or a controlled PDF parsing path.
- Protection review will need synthetic TCC and relay-setting tables before we can reliably verify curve reasoning.
- HV SLD review will need a stable representation of topology, equipment tags, ratings, schedules, and study outputs.

## Suggested Next Step

Start with a narrow source-pack design for one task family rather than trying to port all four skills at once. The most direct route is likely an `SSC-05` HV SLD cross-document QA task because it can be represented with structured tables and connects naturally to existing electrical-load, feeder, protection, arc-flash, and earthing interfaces. The second strongest route is an `SSC-07` earthing study acceptance review because the checklist has clear numerical checks and source traceability requirements.
