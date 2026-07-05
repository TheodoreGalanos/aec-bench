# SSC-07 Ground investigation, groundwater, and soil/resistivity world Long-Horizon Design

This document treats the site ground model as one source-controlled package: boreholes, CPT or SPT logs, groundwater, soil parameters, resistivity tests, structure layout, and load or fault case have to line up. A useful long-horizon task keeps that ground basis consistent while moving between stability, seepage, bearing, uplift, earthing, foundations, and authority review.

## Evidence Basis

| Field | Value |
| --- | --- |
| Ground source state | borehole/CPT/SPT logs, groundwater record, soil profile, resistivity/grounding test area |
| Memberships | 22 task-card memberships |
| Primary cards | 17 |
| Disciplines | civil, electrical, ground, structural |
| Score | 30/30 |
| Candidate product | Soil and groundwater as both structural stability and electrical safety medium |
| Main risk | Soil strength and soil resistivity are adjacent but not interchangeable; authority partition is critical. |

The current card anchors cover soil strength, groundwater, retaining-wall, slope, uplift, bearing, solar-array, and earthing checks:

| Card | Plain-language role |
| --- | --- |
| `exit-gradient` | Calculates exit gradient at downstream toe and factor of safety against piping. |
| `fos-rapid-drawdown` | Calculates factor of safety for upstream slope during rapid reservoir drawdown. |
| `fos-seismic` | Factor of safety under pseudo-static seismic loading using the infinite slope method. |
| `fos-steady-state` | Factor of safety for embankment slope under steady-state seepage. |
| `lateral-earth-pressure` | Active and passive earth pressures using Rankine or Coulomb theory. |
| `retaining-wall-stability` | Sliding, overturning, and bearing stability checks for gravity retaining walls. |
| `solar-array-wind-load` | Wind loads on ground-mounted solar PV arrays including uplift, downforce, and drag. |
| `uplift-pressure` | Calculates uplift pressure distribution on concrete gravity dam foundation for stability analysis. |
| `wave-breaking` | Wave breaking criteria using depth-limited breaking height, Iribarren number, and breaker type classification (USACE CEM). |
| `grid-resistance` | Substation grounding grid resistance calculation per IEEE 80-2013. |

## Ground And Resistivity Data Model

Treat each task as a check against the same ground investigation package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-07`, the ground investigation package source state is:

```text
S_ssc_07 = {
  ground_model_id,
  stratigraphy,
  strength_parameters,
  groundwater_case,
  resistivity_model,
  structure_or_grid_layout,
  load_or_fault_case,
  authority_partition,
}
```

The product combinations below share the same ground investigation package data. A change to borehole, CPT or SPT record, groundwater case, soil parameter, resistivity test, structure layout, or load case must carry through each check.

```text
W_ssc07_lh_01 x_S W_ssc07_lh_02
W_ssc07_lh_02 x_S W_ssc07_lh_03
W_ssc07_lh_03 x_S W_ssc07_lh_04
W_ssc07_lh_04 x_S W_ssc07_lh_05
W_ssc07_lh_05 x_S W_ssc07_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_07` | The ground investigation package source state that all combined checks must agree on. |
| `W_ssc07_lh_01` | The first SSC-07 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same ground investigation package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Ground Source Manifest

Any `SSC-07` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `ground_model_id` | Borehole/CPT/SPT/resistivity record identity and spatial frame. | GI report, test plan |
| `stratigraphy` | Layer depths, material descriptions, groundwater, and design cases. | borehole logs |
| `strength_parameters` | phi, c, unit weight, SPT/CPT-derived design values. | geotechnical interpretation |
| `groundwater_case` | Steady, drawdown, seismic, uplift, exit-gradient, or flood water state. | groundwater record |
| `resistivity_model` | Soil resistivity measurements, layers, seasonal/moisture assumptions. | resistivity report |
| `structure_or_grid_layout` | Retaining wall, foundation, solar array, earthing grid, or buried asset geometry. | layout/section |
| `load_or_fault_case` | Surcharge, seismic, wind, fault current, or grid-current case. | design basis |
| `authority_partition` | Geotechnical, structural, electrical, and owner standard authority split. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-07-LH-01: Soil And Groundwater Structural-Electrical Safety Package

This is a ground, groundwater, and resistivity work package for soil and groundwater structural-electrical safety. It starts with the borehole/CPT/SPT logs, groundwater monitoring record, and soil parameter summary.

The engineer checks groundwater design case, foundation or slope stability check, and soil resistivity/earthing check. The output is the partitioned safety memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
borehole/CPT/SPT interpretation
  -> groundwater design case
  -> foundation or slope stability check
  -> soil resistivity/earthing check
  -> partitioned safety memo
```

Task-card anchors:

- `spt-corrections`
- `cpt-parameter-derivation`
- `retaining-wall-stability`
- `grid-resistance`
- `terzaghi-bearing-capacity`

Source pack:

- borehole/CPT/SPT logs;
- groundwater monitoring record;
- soil parameter summary;
- resistivity test record;
- foundation/earthing layout.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change borehole/CPT/SPT logs while keeping the downstream groundwater design case fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make borehole/CPT/SPT logs disagree with groundwater monitoring record about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in soil parameter summary only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on borehole/CPT/SPT interpretation. The response should show groundwater design case and foundation or slope stability check, then record partitioned safety memo using the same source values throughout.

### SSC-07-LH-02: Retaining Wall Seepage, Uplift, And Foundation Package

This is a ground, groundwater, and resistivity work package for retaining wall seepage, uplift, and foundation. It starts with the geotechnical report, wall section, and groundwater table.

The engineer checks lateral pressure and seepage check, wall stability and bearing, and uplift/exit gradient consequence. The output is the retaining design memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
soil profile and groundwater case
  -> lateral pressure and seepage check
  -> wall stability and bearing
  -> uplift/exit gradient consequence
  -> retaining design memo
```

Task-card anchors:

- `lateral-earth-pressure`
- `retaining-wall-stability`
- `wall-overturning`
- `wall-bearing`
- `exit-gradient`

Source pack:

- geotechnical report;
- wall section;
- groundwater table;
- surcharge plan;
- wall/foundation schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change geotechnical report while keeping the downstream lateral pressure and seepage check fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make geotechnical report disagree with wall section about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in groundwater table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on soil profile and groundwater case. The response should show lateral pressure and seepage check and wall stability and bearing, then record retaining design memo using the same source values throughout.

### SSC-07-LH-03: Solar Array Wind Load, Ground Bearing, And Earthing Package

This is a ground, groundwater, and resistivity work package for solar array wind load, ground bearing, and earthing. It starts with the PV layout, wind criteria, and rack/foundation schedule.

The engineer checks wind load and support reaction, ground bearing/foundation check, and earthing/resistivity check. The output is the PV foundation safety memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
PV/rack layout
  -> wind load and support reaction
  -> ground bearing/foundation check
  -> earthing/resistivity check
  -> PV foundation safety memo
```

Task-card anchors:

- `solar-array-wind-load`
- `design-wind-pressure`
- `terzaghi-bearing-capacity`
- `grid-resistance`
- `voltage-drop-dc`

Source pack:

- PV layout;
- wind criteria;
- rack/foundation schedule;
- geotechnical parameters;
- resistivity/earthing test area.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change PV layout while keeping the downstream wind load and support reaction fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make PV layout disagree with wind criteria about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in rack/foundation schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on PV/rack layout. The response should show wind load and support reaction and ground bearing/foundation check, then record PV foundation safety memo using the same source values throughout.

### SSC-07-LH-04: Excavation/Dewatering And Temporary Power Safety Package

This is a ground, groundwater, and resistivity work package for excavation/dewatering and temporary power safety. It starts with the excavation section, groundwater record, and pump schedule.

The engineer checks drawdown/seepage case, temporary pump/power load, and slope or basal stability. The output is the temporary works memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
excavation geometry and water table
  -> drawdown/seepage case
  -> temporary pump/power load
  -> slope or basal stability
  -> temporary works memo
```

Task-card anchors:

- `fos-rapid-drawdown`
- `exit-gradient`
- `uplift-pressure`
- `pump-power-calculation`
- `battery-sizing`

Source pack:

- excavation section;
- groundwater record;
- pump schedule;
- temporary power layout;
- temporary works criteria.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change excavation section while keeping the downstream drawdown/seepage case fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make excavation section disagree with groundwater record about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pump schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on excavation geometry and water table. The response should show drawdown/seepage case and temporary pump/power load, then record temporary works memo using the same source values throughout.

### SSC-07-LH-05: Liquefaction/Seismic Slope And Service Continuity Package

This is a ground, groundwater, and resistivity work package for liquefaction/seismic slope and service continuity. It starts with the seismic design case, soil parameter table, and slope section.

The engineer checks soil strength interpretation, stability check, and affected utilities/equipment. The output is the resilience response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
seismic or slope case
  -> soil strength interpretation
  -> stability check
  -> affected utilities/equipment
  -> resilience response
```

Task-card anchors:

- `fos-seismic`
- `infinite-slope`
- `lateral-earth-pressure`
- `pipe-support-dead-load`
- `voltage-drop`

Source pack:

- seismic design case;
- soil parameter table;
- slope section;
- utility/equipment layout;
- service continuity criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change seismic design case while keeping the downstream soil strength interpretation fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make seismic design case disagree with soil parameter table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in slope section only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on seismic or slope case. The response should show soil strength interpretation and stability check, then record resilience response using the same source values throughout.

### SSC-07-LH-06: Ground Improvement Acceptance And Foundation Recheck Package

This is a ground, groundwater, and resistivity work package for ground improvement acceptance and foundation recheck. It starts with the ground improvement certificate, pre/post test logs, and foundation plan.

The engineer checks improvement target or certificate, bearing/settlement recheck, and authority acceptance gate. The output is the foundation review memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
baseline ground parameters
  -> improvement target or certificate
  -> bearing/settlement recheck
  -> authority acceptance gate
  -> foundation review memo
```

Task-card anchors:

- `cpt-parameter-derivation`
- `spt-corrections`
- `immediate-settlement`
- `consolidation-settlement`
- `meyerhof-bearing-capacity`

Source pack:

- ground improvement certificate;
- pre/post test logs;
- foundation plan;
- bearing/settlement worksheet;
- acceptance criteria.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change ground improvement certificate while keeping the downstream improvement target or certificate fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make ground improvement certificate disagree with pre/post test logs about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in foundation plan only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on baseline ground parameters. The response should show improvement target or certificate and bearing/settlement recheck, then record foundation review memo using the same source values throughout.

### SSC-07-LH-07: Buried Pipe, Thrust Block, And Soil Resistance Package

This is a ground, groundwater, and resistivity work package for buried pipe, thrust block, and soil resistance. It starts with the pipe alignment, transient/thrust event table, and soil profile.

The engineer checks soil profile and groundwater case, thrust/support/foundation check, and seepage or uplift consequence. The output is the buried-pipe support memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
pipe alignment and transient/thrust event
  -> soil profile and groundwater case
  -> thrust/support/foundation check
  -> seepage or uplift consequence
  -> buried-pipe support memo
```

Task-card anchors:

- `thrust-force-calculation`
- `lateral-earth-pressure`
- `wall-bearing`
- `uplift-pressure`
- `hazen-williams-headloss`

Source pack:

- pipe alignment;
- transient/thrust event table;
- soil profile;
- groundwater table;
- thrust block detail.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change pipe alignment while keeping the downstream soil profile and groundwater case fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make pipe alignment disagree with transient/thrust event table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in soil profile only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on pipe alignment and transient/thrust event. The response should show soil profile and groundwater case and thrust/support/foundation check, then record buried-pipe support memo using the same source values throughout.

### SSC-07-LH-08: Ground Investigation Review And Parameter Repair Package

This is a ground, groundwater, and resistivity work package for ground investigation review and parameter repair. It starts with the borehole/CPT/SPT logs, lab/test summary, and parameter derivation table.

The engineer checks interpreted parameter set, affected design checks, and repair decision. The output is the geotechnical review response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
conflicting logs or tests
  -> interpreted parameter set
  -> affected design checks
  -> repair decision
  -> geotechnical review response
```

Task-card anchors:

- `cpt-parameter-derivation`
- `spt-corrections`
- `terzaghi-bearing-capacity`
- `retaining-wall-stability`
- `grid-resistance`

Source pack:

- borehole/CPT/SPT logs;
- lab/test summary;
- parameter derivation table;
- design calculation excerpts;
- comment register.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change borehole/CPT/SPT logs while keeping the downstream interpreted parameter set fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make borehole/CPT/SPT logs disagree with lab/test summary about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in parameter derivation table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on conflicting logs or tests. The response should show interpreted parameter set and affected design checks, then record geotechnical review response using the same source values throughout.

## How The Variants Come Together

All `SSC-07` variants should use the same ground investigation package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the ground investigation package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-07-LH-01` | Soil And Groundwater Structural-Electrical Safety Package | `ground_model_id` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-07-LH-02` | Retaining Wall Seepage, Uplift, And Foundation Package | `stratigraphy` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-07-LH-03` | Solar Array Wind Load, Ground Bearing, And Earthing Package | `strength_parameters` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-07-LH-04` | Excavation/Dewatering And Temporary Power Safety Package | `groundwater_case` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-07-LH-05` | Liquefaction/Seismic Slope And Service Continuity Package | `resistivity_model` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-07-LH-06` | Ground Improvement Acceptance And Foundation Recheck Package | `structure_or_grid_layout` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-07-LH-07` | Buried Pipe, Thrust Block, And Soil Resistance Package | `load_or_fault_case` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-07-LH-08` | Ground Investigation Review And Parameter Repair Package | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The ground package should keep the same borehole logs, CPT or SPT data, groundwater case, strength parameters, resistivity model, structure layout, and load or fault case across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when treated as a ground-investigation-to-design handoff, not as one geotechnical formula. A normal workflow starts with borehole/CPT/SPT logs, lab tests, groundwater observations, and sometimes resistivity or geophysical data; then it turns those records into interpreted strata and design parameters for retaining, foundation, dewatering, buried-pipe, earthing, corrosion, or temporary-works checks.
- The resistivity and electrical-safety link is plausible, but the note must not imply that soil strength and soil resistivity are the same property. The useful package forces two interpretations from the same investigation: a mechanical ground model for stability, bearing, settlement, and uplift; and a resistivity model for earthing, corrosion, or safety checks.
- The current product list makes sense. The main tightening is to require a named ground interpretation and parameter-selection memo before downstream structural or electrical calculations can use the values.

Typical practitioner steps:

1. Register field logs, coordinates, levels, test methods, water levels, samples, and lab test identifiers.
2. Interpret strata and assign design cases for strength, stiffness, unit weight, permeability, groundwater, resistivity, and uncertainty.
3. Run the product-specific checks: stability, seepage/uplift, bearing/settlement, dewatering drawdown, thrust resistance, earthing/resistivity, and review-response repairs.
4. Issue a memo that names the controlling ground model, selected design case, changed assumptions, and values handed to other disciplines.

Software stack notes:

- [OpenGround](https://www.seequent.com/products-solutions/openground/) is a realistic data-management and reporting anchor for borehole/test data, source validation, report templates, and project collaboration.
- [PLAXIS](https://www.seequent.com/products-solutions/plaxis/) and [GeoStudio](https://www.seequent.com/products-solutions/geostudio/) are realistic analysis-family anchors for deformation, stability, soil-structure interaction, groundwater, consolidation, and flow cases.
- [Res2DInv/Res3DInv](https://www.seequent.com/products-solutions/res2dinv-and-res3dinv/) is a realistic resistivity/geophysical processing anchor when the electrical model comes from ERT/IP survey data rather than only point soil-box tests.

Design implications:

- Add a `ground_interpretation_memo` or equivalent expected field before hardening `SSC-07-LH-01`.
- Keep resistivity as its own source field with test method, depth/spacing, moisture/temperature context, and interpretation status.
- Negative cases should include a mechanical soil model being silently reused as an electrical resistivity model.

## Power Playground Skill-Derived Task Candidates

These candidates translate the local `Power-Playground-main` SME review skills into this SSC. They are design-note candidates only; they do not add runnable templates, accepted evidence, or source-pack hardening.

| Candidate Task | Source Skill | Source Pack Shape | What The Check Should Catch |
| --- | --- | --- | --- |
| Is this substation earthing study safe to issue? | `earthing-study-review` | Earthing study report, soil resistivity table, fault-current/protection extract, earthing layout, EPR results, and step/touch voltage results. | Safety criteria, clearing time, grid current, soil model, EPR, touch/step voltage, and layout evidence do not support the conclusion. |
| Do the soil model and fault-current basis support the step-touch result? | `earthing-study-review` | Test traverse records, adopted layered model, grid-current calculation, surface-layer assumptions, shock duration, and model output table. | The adopted resistivity model is not traceable to tests, the shock duration does not match clearing time, or surface-layer assumptions are used without drawing evidence. |
| Are transferred potentials controlled at the fence and services? | `earthing-study-review` | Fence/gate layout, metallic services, LV MEN, telecoms, pipelines, rail interfaces, cable screen paths, and transferred-voltage results. | External conductive interfaces are absent, treated as generic, or not reconciled with the EPR and transferred-voltage controls. |

## Checks The Template Should Catch

These checks make `SSC-07` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `ground_model_id` source object or evidence artifact. | `ssc_07_source_identity_mismatch` |
| Scenario drift | One stage uses a different `stratigraphy` case without a case-selection record. | `ssc_07_scenario_mismatch` |
| Geometry or topology drift | `strength_parameters` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_07_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_07_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_07_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_07_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_07_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_07_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_07_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_07_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-07-LH-01` Soil And Groundwater Structural-Electrical Safety Package: start here because it uses the main ground investigation package source files and produces a source-pack-sized memo.
2. `SSC-07-LH-02` Retaining Wall Seepage, Uplift, And Foundation Package: add this after the first source pack has stable source files and control values.
3. `SSC-07-LH-03` Solar Array Wind Load, Ground Bearing, And Earthing Package: add this after the first source pack has stable source files and control values.
4. `SSC-07-LH-04` Excavation/Dewatering And Temporary Power Safety Package: add this after the first source pack has stable source files and control values.

The next artifact should be a `ground_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-07 product into a source pack.

A first executable-quality source pack for `SSC-07` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `ground_source_manifest.yaml` | source fields such as `ground_model_id`, `stratigraphy`, `strength_parameters`, `groundwater_case`, `resistivity_model` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `ground_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `ground_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as ground investigation package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
