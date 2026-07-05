# ABOUTME: Build plan for the first wave of review-first menu anchors (SSC-06, 19, 15, 07, 04).
# ABOUTME: Records provisional SME rulings, per-anchor specs, build rules, probe protocol, and acceptance gates.

# Review-First Anchor Build Plan

This plan authorizes building the five priority menu anchors now, at final-task quality, with SME review moved from a pre-build gate to a post-build confirmation pass. SMEs are hard to schedule; they will review built packets, probe evidence, and the provisional rulings below — concrete artifacts, not catalogue rows.

Every engineering decision made here in place of an SME answer is marked **PROVISIONAL** and collected in the SME confirmation sheet at the end. A later SME reversal is handled as a redesign of the affected variant or matrix row, not as a failure.

Authority order for this work: [review-first-authoring-guide.md](review-first-authoring-guide.md) (binding, all 13 invariants, the 12-test TDD set, and the probe-triage section), then the implementation menu in [review-first-task-construction-catalogue.md](review-first-task-construction-catalogue.md), then this plan.

## Build Order And Rationale

Build strictly one at a time; a template must pass its full acceptance gate before the next starts.

1. `SSC-06-LH-01` pump duty/NPSH — closest to the proven SSC-01 shape; calibrates the workflow on the strongest borrowed math.
2. `SSC-19-LH-01` fire-water/hazard — introduces classification-before-arithmetic, the first genuinely new judgment type.
3. `SSC-15-LH-04` product submittal — the evidence-world test: no physics chain, certificates and traceability as the review surface. If the guide generalizes here, it generalizes.
4. `SSC-07-LH-01` ground structural-electrical — the authority-partition flagship; hardest identity design.
5. `SSC-04-LH-01` coastal elevation — datum-conversion identity; consolidates everything.

Do not build anything beyond these five. The rest of the menu waits for SME feedback on this wave.

## Universal Build Rules

1. The authoring guide applies without exception: sources are files, no numbers or methods in prompts, hidden `packet_variant` plus hidden margins, quantize-then-derive, derivation-controlled criteria with safe rounding, the universal eight variants with exactly one primary flip each, stage-gated verifier with the standard weights, fluent-unsafe golden_fail, closure test with independently written formulas, `tool_mode = "no-tool"`, variant-blind instructions.
2. Reuse the SSC-01 post-triage contract verbatim where it is domain-neutral: workflow rule 6 including the pending-value clause, the generic boundary-rules block, fractional identity-ledger scoring, and the negation-equivalence claim-boundary check. Copy from the current `road_low_point_issue_review_package` and `roadside_cabinet_serviceability_issue_review_package` files, which carry all triage fixes.
3. Borrow the physics from the named baseline engine; do not re-derive domain math. Record the borrowed template in the design note.
4. Object IDs follow the SSC's existing conventions from its baseline package (new IDs use the same shape, e.g. `PMP-06-01`, `TANK-19-01`).
5. TDD: write the 12-test suite first, watch it fail, then implement. Targeted tests only.
6. Do not commit. Each finished template is audited before commit; leave work in the tree.
7. Probes are triage-only. Expected outcome is sub-1.0 with localized details. Any suspected contract defect gets a written triage proposal in the design note and stops there. "Hardened to 1.00" must not appear anywhere.
8. Each template gets a short design note in this directory (`sscNN-anchor-review-first-design.md` pattern) recording: borrowed math source, scene IDs, matrix specialization, variant table, provisional rulings applied, probe ledger, and non-claims.

## Per-Anchor Specifications

The universal variant skeleton applies to all five; each spec lists only the domain-specific content: the genuine failure, the missing-data field, the identity defect, the scenario-copy case, and the evidence keys. Comment variants (open critical / minor carried) always live in the criteria/comments file.

### 1. `pump-station-duty-npsh-issue-review-package` (SSC-06-LH-01)

- Borrow math: `pump_station_duty_power_npsh_feeder_package`. Preserved baseline untouched.
- Scene: wet well, pump, rising main, motor, feeder, duty case (`WW-06`, `PMP-06`, `RM-06`, `MOT-06`, `FDR-06`, `DUTY-06` shapes).
- Source files (7): document register; wet-well and suction geometry; rising-main schedule; pump curve and datasheet extract (head/flow/NPSHr/efficiency at stated points); motor and feeder schedule; duty/operating case; criteria and comments (assessment bases: Hazen-Williams, static+friction TDH, NPSHa from wet-well level minus losses minus vapor pressure, motor sizing with service factor, voltage-drop formula).
- Evidence keys: `total_dynamic_head_m`, `pump_head_margin_m`, `npsh_available_m`, `npsh_margin_m`, `motor_input_kw`, `motor_margin_kw`, `feeder_voltage_drop_percent`, `voltage_drop_margin_percent`.
- Genuine failure (RLR-04): `npsh_margin_deficient` — recomputed NPSHa at the source-owned minimum wet-well level falls below NPSHr plus the required margin, while the package claims adequacy using the average level. **PROVISIONAL ruling** on the catalogue's SME question: NPSH margin is the first blocker (most fundamental, crisply recomputable); off-curve/BEP-POR operation is deferred as a later variant; motor/feeder mismatch stays in evidence keys.
- Missing data (RLR-04 → `insufficient_data`): minimum wet-well operating level absent ("pending survey of stop/start setpoints").
- Identity defect (RLR-02): pump curve sheet references a different impeller diameter than the datasheet/schedule.
- Scenario copy (RLR-05): duty flow adopted from another station's case without a selection record.

### 2. `fire-water-storage-hazard-issue-review-package` (SSC-19-LH-01)

- Borrow math: `fire_water_sprinkler_storage_package`.
- Scene: storage building, commodity, rack arrangement, sprinkler system, tank, fire pump, AHJ case.
- Source files (7): document register; hazard and storage arrangement (commodity, storage height, rack config); classification table (source-owned: class as a function of commodity + height, in the criteria memo); sprinkler/hydrant demand sheet; tank and pump schedule; fire strategy/operating case; criteria and comments.
- Evidence keys: `design_density_mm_min`, `design_area_m2`, `sprinkler_demand_l_min`, `hose_allowance_l_min`, `required_duration_min`, `required_volume_m3`, `storage_volume_margin_m3`, `pump_capacity_margin_l_min`.
- Genuine failure (RLR-04): `storage_deficient_under_true_class` — the packet computes demand under a lower hazard class; the true class per the source-owned classification table (given the stated commodity and storage height) drives demand above the provided storage. The classification error is the cause cited in the finding; the single flip stays on RLR-04. **PROVISIONAL ruling**: classification drift is exercised through the genuine-failure route first, not as a separate RLR-02 variant, keeping one flip per variant.
- Missing data: commodity classification certificate absent → class not determinable → `insufficient_data` plus request.
- Identity defect: tank ID/volume differs between tank schedule and demand sheet.
- Scenario copy: design area/duration adopted from another building's strategy.

### 3. `product-submittal-compliance-issue-review-package` (SSC-15-LH-04)

- Borrow math: `product_submittal_compliance_package` (CEV formula and property checks).
- Scene: steel product submittal — product, heats, certificates, application schedule, deviation register.
- Source files (7): document register; submittal manifest; mill certificates (chemistry and mechanical properties per heat); heat/batch traceability table; product application schedule (which heat goes where, required grade/properties); deviation register; criteria and comments (assessment bases: CEV = C + Mn/6 + (Cr+Mo+V)/5 + (Ni+Cu)/15, property limits, certificate-scope rules).
- Evidence keys: `carbon_equivalent_max`, `carbon_equivalent_margin`, `yield_strength_margin_mpa`, `tensile_strength_margin_mpa`, `certificate_coverage_count`, `traceability_match_count`.
- Genuine failure (RLR-04): `carbon_equivalent_exceeds` — CEV recomputed from printed chemistry exceeds the weldability limit for one heat while the certificate summary claims pass. **PROVISIONAL ruling** on the SME question: absent evidence (missing certificate, missing heat number) is `insufficient_data` with a request; present-but-nonconforming evidence is `fail`. Valid-certificate-wrong-application is reserved for the later `SSC-15-LH-03` build.
- Missing data: one application-schedule row has no heat number ("traceability pending").
- Identity defect: a heat number in the traceability table does not exist on any certificate.
- Scenario copy: acceptance limits quoted from a different product standard/grade than the application schedule requires.

### 4. `ground-structural-electrical-issue-review-package` (SSC-07-LH-01)

- Borrow math: `ground_structural_electrical_safety_package` (SPT corrections, source-owned Terzaghi factors, resistivity/grid formulas).
- Scene: one site, two report chains — geotechnical (boreholes, SPT, groundwater, foundation) and electrical (resistivity traverse, earthing grid) — plus the interpretation memo that must keep them partitioned.
- Source files (8): document register; borehole/SPT logs; groundwater record; ground interpretation memo (parameter selection); foundation load table; resistivity survey; earthing grid design extract; criteria and comments (bases: N60/N1_60 corrections, friction-angle correlation, Terzaghi factors as source-owned values, grid resistance and touch-voltage formulas and limits).
- Evidence keys: `corrected_spt_n60`, `design_friction_angle_deg`, `allowable_bearing_kpa`, `bearing_margin_kpa`, `grid_resistance_ohm`, `grid_resistance_margin_ohm`, `touch_voltage_margin_v`.
- Genuine failure (RLR-04): `bearing_fos_deficient` — recomputed allowable bearing under the source-owned water-table correction falls below the applied load, while the package used the uncorrected value.
- Missing data: design groundwater level absent ("standpipe readings pending") → bearing check `insufficient_data`.
- Identity defect (RLR-02, the partition flagship): the interpretation memo cites a resistivity-traverse layer value as if it were a strength stratum parameter (authority collapse between the two report chains). **PROVISIONAL ruling** on the SME question: the partition defect is the identity variant; the numeric bearing failure remains the genuine-failure variant; both exist, one flip each.
- Scenario copy: seismic/load case adopted from a different structure's design basis.

### 5. `coastal-flood-equipment-elevation-issue-review-package` (SSC-04-LH-01)

- Borrow math: `coastal_flood_outfall_pump_elevation_package`.
- Scene: coastal pump station and outfall — tide boundary, SLR scenario, runup, switchboard/generator elevations.
- Source files (7): document register; tide and water-level basis (chart datum and AHD, with the source-owned CD-to-AHD offset); SLR scenario and planning-horizon table; wave/runup basis; asset survey (equipment levels); pump/outfall schedule; criteria and comments (bases: design flood level = tide + surge + SLR + runup in AHD; required equipment freeboard; outfall submergence check). **PROVISIONAL ruling** on the SME question: the criteria memo declares AHD controlling and owns the CD offset; conflicting-datum evidence is a defect, not a puzzle without an answer.
- Evidence keys: `design_flood_level_m_ahd`, `wave_runup_m`, `switchboard_freeboard_m`, `switchboard_freeboard_margin_m`, `generator_freeboard_margin_m`, `outfall_submergence_margin_m`, `pump_duty_margin`.
- Genuine failure (RLR-04): `switchboard_below_design_level` — recomputed design flood level in AHD exceeds the surveyed switchboard level plus required freeboard, while the package claims adequacy by omitting the runup component.
- Missing data: switchboard survey level absent ("survey to follow") → `insufficient_data`.
- Identity defect: the asset survey quotes levels in chart datum while labelled AHD (no conversion applied).
- Scenario copy: SLR planning horizon adopted from a different asset class's assessment.

## Acceptance Gate Per Template

All of the following before the next template starts; record results in the design note:

1. The guide's 12-test suite passes, including the closure test (independent formulas over rendered sources) and the fluent-memo bound.
2. `ruff check` and `ruff format --check` clean.
3. Fresh 8-instance medium batch: 8/8 pass `aec-bench task validate` (golden 1.000, fluent fail ≤ 0.5), ≥ 4 variants present.
4. Variant-blindness self-check: instructions and system prompt enumerate no variants; sources diff shows only the intended defect per variant.
5. Probe set, triage-only: Haiku + Sonnet on the genuine-failure variant and the missing-data variant (4 runs). Capture reward and details; classify every loss (`model-evidence` or `suspected-contract-defect` with the proposed lane); change nothing.
6. Audit hold: stop, leave uncommitted, and hand the design note + probe ledger over for review before the next template begins.

## SME Confirmation Sheet

Maintain one consolidated list (in each design note and summarized here when the wave completes) of every **PROVISIONAL** ruling: the five listed above plus any new ruling made during construction. For each: the ruling, the alternative an SME might prefer, and which variant/matrix row changes if reversed. This is what SMEs review, together with one generated packet per template and the probe evidence.

## Non-Claims

These templates are task-owned synthetic review environments built under provisional engineering rulings. They do not claim SME endorsement, accepted project evidence, authority approval, source-pack hardening, full standards compliance, or benchmark readiness. SME confirmation status must be stated wherever these anchors are cited.
