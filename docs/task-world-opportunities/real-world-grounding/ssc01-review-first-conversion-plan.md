# ABOUTME: Maps SSC-01 long-horizon products into review-first task shapes.
# ABOUTME: Preserves existing formula-closure templates while defining the next review-native increments.

# SSC-01 Review-First Conversion Plan

This note applies `review-first-authoring-guide.md` to the full `SSC-01` road/corridor cluster. It preserves the existing `SSC-01-LH-*` products and runnable formula-closure templates as baselines, while defining review-native replacements or companions that follow the new standard.

The purpose is not to add product-count coverage. The purpose is to turn selected SSC-01 products into file-backed issue-readiness environments where the model must inventory sources, preserve corridor identity, recompute evidence, assign `pass` / `fail` / `not_applicable` / `insufficient_data`, link findings and actions, and issue a readiness decision.

## Current State

The old all-product SSC-01 stream is complete as formula-closure coverage: eight products have runnable synthetic templates in `product-expansion-catalogue.md`.

The new review-first stream has one implemented reference and seven implemented additive companions:

| Product | Existing Formula Template | Review-First Template | Review-First Status |
| --- | --- | --- | --- |
| `SSC-01-LH-01` Road Low-Point Drainage And Field Equipment Resilience | `road-low-point-resilience-package` | `road-low-point-issue-review-package` | Implemented as the reference review environment; composite-catalogue entry added; model-run evidence remains pending. |
| `SSC-01-LH-02` Intersection Timing, Grade, And Sight-Distance Package | `intersection-timing-grade-sight-distance-package` | `intersection-signal-safety-issue-review-package` | Implemented as the first additive review-first companion; composite-catalogue entry added; model-run evidence remains pending. |
| `SSC-01-LH-03` Road Lighting, ITS, And Drainage Operations Scene | `road-lighting-its-drainage-operations-package` | `road-visual-operations-issue-review-package` | Implemented as the third additive review-first companion; composite-catalogue entry added; prompt-leakage cleanup removed variant-specific missing-PoE/readiness prescriptions from instruction and system prompt. Prior post-hardening 1.00 runs are contaminated diagnostics, not model-quality evidence. |
| `SSC-01-LH-04` Emergency Detour And Roadside Device Continuity | `emergency-detour-roadside-device-continuity-package` | `emergency-detour-device-issue-review-package` | Implemented as the fourth additive review-first companion; composite-catalogue entry added; model-run evidence remains pending. |
| `SSC-01-LH-05` Bus Priority, Signal Corridor, And Cabinet Load Package | `bus-priority-signal-cabinet-load-package` | `bus-priority-cabinet-issue-review-package` | Implemented as the fifth additive review-first companion; composite-catalogue entry added; model-run evidence remains pending. |
| `SSC-01-LH-06` Culvert, Driveway Access, And Safety Continuity Package | `culvert-driveway-access-safety-continuity-package` | `driveway-access-safety-issue-review-package` | Implemented as the sixth additive review-first companion; composite-catalogue entry added; model-run evidence remains pending. |
| `SSC-01-LH-07` Roadside Cabinet Flood, Heat, And Backup Energy Package | `roadside-cabinet-flood-heat-backup-energy-package` | `roadside-cabinet-serviceability-issue-review-package` | Implemented as the seventh additive review-first companion; composite-catalogue entry added; prompt-leakage cleanup removed missing-derating, identity-ledger, and worked-value prescriptions from prompt surfaces while keeping source-owned thermal-ratio convention and verifier-side claim wording normalization. Broad two-model/variant evidence remains pending. |
| `SSC-01-LH-08` Multimodal Corridor Review Response Package | `multimodal-corridor-review-response-package` | `corridor-comment-response-issue-review-package` | Implemented as the second additive review-first companion; composite-catalogue entry added; prompt-leakage cleanup removed copied-scenario and missing-chainage answer mappings from prompt surfaces. Pre-strip sub-1.0 runs remain useful discrimination/contract diagnostics; post-strip model evidence must be recollected. |

The old templates remain useful as math sources and saved baseline artifacts. Review-first companions do not replace or overwrite them; they change the task identity from "calculate a package memo" to "review whether the issue package is ready to issue."

## Conversion Rules For SSC-01

Apply the authoring guide without dilution:

- Source values live only in generated `environment/sources/*.md` files, not in `instruction.md`.
- Methods and conventions live in the criteria/comments source file, not prompt scaffolding.
- Every review task uses `tool_mode = "no-tool"` so no calc script enters the sandbox.
- Every task has one hidden `packet_variant` enum plus hidden derivation margins.
- Every generated instance has real parameter variation (`min < max` where engineering sense allows).
- Every defect variant flips exactly one primary review item.
- Every verifier scores a review packet with matrix, evidence, linkage, readiness, identity, and claim-boundary gates.
- Golden pass at `1.0` is a sanity floor; model ceiling everywhere is a difficulty defect.

## Product Conversion Map

| Product | Review-First Candidate | Primary Source Packet | RLR-04 Criterion Check | Evidence Keys To Borrow Or Derive | Genuine Failure Variant | Implementation Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `SSC-01-LH-01` Road Low-Point Drainage And Field Equipment Resilience | `road-low-point-issue-review-package` | Document register, road geometry, drainage package, field equipment, power/comms, traffic operations, criteria/comments. | CAB-01 pad freeboard vs controlling water level. | `peak_runoff_m3_s`, `gutter_approach_flow_m3_s`, `spread_width_m`, `allowable_spread_m`, `controlling_water_level_m`, `cabinet_freeboard_m`, `vms_message_margin_chars`, `battery_runtime_h`, `network_headroom_mbps`. | `freeboard_deficient`. | Done as reference implementation. Closure tests now cover clean, genuine-failure, and missing-evidence packets. |
| `SSC-01-LH-02` Intersection Timing, Grade, And Sight-Distance Package | `intersection-signal-safety-issue-review-package` | Document register, intersection layout, approach profile, signal timing sheet, pedestrian crossing sheet, sight-distance note, controller handoff note, criteria/comments. | Controlling approach safety adequacy: available sight distance and pedestrian clearance must both clear source criteria. | `stopping_distance_m`, `sight_distance_margin_m`, `yellow_interval_s`, `all_red_interval_s`, `ped_clearance_required_s`, `ped_clearance_margin_s`, `grade_adjusted_braking_distance_m`. | `pedestrian_clearance_deficient`. | Implemented as the first additive companion. It proves the guide generalizes beyond the low-point drainage scene while preserving `intersection_timing_grade_sight_distance_package` as the formula-closure baseline. |
| `SSC-01-LH-03` Road Lighting, ITS, And Drainage Operations Scene | `road-visual-operations-issue-review-package` | Document register, road segment/lighting grid, device register, network topology, CCTV/storage schedule, PoE/cabinet schedule, storm operations note, criteria/comments. | Night/storm operations adequacy: PoE power budget must clear the criterion for the same CCTV/VMS/sensor device set; lighting uniformity remains a secondary adequacy check. | `average_illuminance_lux`, `minimum_illuminance_lux`, `uniformity_ratio`, `minimum_uniformity_ratio`, `total_network_load_mbps`, `network_headroom_mbps`, `total_cctv_storage_tb`, `poe_load_w`, `poe_headroom_w`, `water_level_margin_m`, `ups_energy_kwh`. | `poe_budget_exceeded`; keep `uniformity_deficient` as a later optional variant. | Implemented as the third additive companion after the design contract in `ssc01-lh03-review-first-design.md`. After prompt-leakage cleanup, it keeps defect classification in the matrix/verifier and leaves decimal CCTV storage convention in criteria/comments. It borrows math from `road_lighting_its_drainage_operations_package` while preserving that formula baseline. |
| `SSC-01-LH-04` Emergency Detour And Roadside Device Continuity | `emergency-detour-device-issue-review-package` | Document register, detour plan, message library, device inventory, communications topology, power continuity schedule, criteria/comments. | Detour device continuity: the battery/generator runtime must clear the required closure duration for the same VMS/CCTV/radio/controller device set; VMS readability, RF link, network headroom, and voltage drop remain secondary continuity checks. | `vms_reading_time_s`, `vms_message_margin_chars`, `required_network_mbps`, `network_headroom_mbps`, `rf_received_power_dbm`, `rf_link_margin_db`, `battery_runtime_h`, `battery_margin_h`, `feeder_voltage_drop_percent`, `voltage_drop_margin_percent`. | `battery_runtime_deficient`; keep `rf_link_margin_deficient` as a later optional variant. | Implemented as the fourth additive companion after the design contract in `ssc01-lh04-review-first-design.md`. After prompt-leakage cleanup, it uses variant-blind prompt rules, source-owned criteria/methods, and verifier-owned localization. It borrows math from `emergency_detour_roadside_device_continuity_package` while preserving that formula baseline. |
| `SSC-01-LH-05` Bus Priority, Signal Corridor, And Cabinet Load Package | `bus-priority-cabinet-issue-review-package` | Document register, bus-priority operations plan, signal phasing/timing sheet, detector/controller schedule, cabinet load schedule, feeder/battery sheet, owner operations criterion, criteria/comments. | Cabinet and traffic-priority adequacy: the same bus-priority case must clear timing, capacity, cabinet load, feeder, and backup limits. | `yellow_interval_s`, `all_red_interval_s`, `bus_handling_capacity_pax_h`, `bus_capacity_margin_pax_h`, `cabinet_load_w`, `cabinet_load_margin_w`, `feeder_current_a`, `feeder_voltage_drop_percent`, `voltage_drop_margin_percent`, `battery_runtime_h`, `battery_margin_h`. | `cabinet_load_exceeded`; keep `voltage_drop_exceeded` as a later optional variant. | Implemented as the fifth additive companion after the design contract in `ssc01-lh05-review-first-design.md`. After prompt-leakage cleanup, it keeps item/status/readiness localization out of prompt surfaces and relies on source evidence plus the custom verifier. It borrows math from `bus_priority_signal_cabinet_load_package` while preserving that formula baseline. |
| `SSC-01-LH-06` Culvert, Driveway Access, And Safety Continuity Package | `driveway-access-safety-issue-review-package` | Document register, access profile, culvert drainage schedule, surface/tailwater table, roadway spread note, sight-distance note, owner access criterion, criteria/comments. | Access usability adequacy: access grade, culvert capacity, and freeboard must refer to the same driveway, road edge, culvert, storm, and vehicle case; roadway spread and sight distance remain secondary safety checks. | `driveway_grade_percent`, `driveway_grade_margin_percent`, `culvert_capacity_m3_s`, `culvert_capacity_margin_m3_s`, `headwater_level_m`, `freeboard_m`, `freeboard_margin_m`, `roadway_spread_m`, `spread_margin_m`, `sight_distance_required_m`, `sight_distance_margin_m`. | `access_freeboard_deficient`; keep `sight_distance_deficient` as a later optional variant. | Implemented as the sixth additive companion after the design contract in `ssc01-lh06-review-first-design.md`. After prompt-leakage cleanup, it keeps missing-value and scenario-copy judgments variant-blind and source-bound rather than instruction-prescribed. It borrows math from `culvert_driveway_access_safety_continuity_package` while preserving that formula baseline. |
| `SSC-01-LH-07` Roadside Cabinet Flood, Heat, And Backup Energy Package | `roadside-cabinet-serviceability-issue-review-package` | Document register, cabinet setout/elevation, flood/HGL event table, enclosure derating note, critical load/backup schedule, feeder/access note, owner serviceability criterion, criteria/comments. | Cabinet serviceability: flood freeboard and thermal derated capacity must both clear the event case for the same cabinet, critical load, and serviceability scenario. | `cabinet_freeboard_m`, `flood_freeboard_margin_m`, `thermal_derated_capacity_w`, `thermal_margin_w`, `thermal_utilization`, `battery_runtime_h`, `battery_margin_h`, `bess_power_margin_kw`, `bess_energy_margin_kwh`, `feeder_voltage_drop_percent`, `voltage_drop_margin_percent`, `road_lighting_aeci_kwh_m2_y`. | `thermal_capacity_deficient`; keep `flood_freeboard_deficient` as a later optional variant. | Implemented as the seventh additive companion after the design contract in `ssc01-lh07-review-first-design.md`. It deliberately uses thermal derating as the first genuine RLR-04 failure so LH07 is not just another flood-freeboard task. After prompt-leakage cleanup, thermal ratio convention remains source-owned and hidden-variant expected statuses are no longer prompt-prescribed. It borrows math from `roadside_cabinet_flood_heat_backup_energy_package` while preserving that formula baseline. |
| `SSC-01-LH-08` Multimodal Corridor Review Response Package | `corridor-comment-response-issue-review-package` | Document register, comment register, marked-up plan/long section, drainage recalculation, signal/pedestrian recalculation, VMS operations note, electrical feeder check, criteria/comments. | Review-response adequacy: the changed chainage/scenario must propagate through all impacted drainage, pedestrian, VMS, voltage, and comment closeout checks. | `changed_chainage_delta_m`, `hgl_clearance_mm`, `hgl_clearance_margin_mm`, `ped_clearance_required_s`, `ped_clearance_margin_s`, `vms_reading_time_s`, `vms_message_margin_chars`, `feeder_voltage_drop_percent`, `voltage_drop_margin_percent`, `comment_closeout_percent`, `impacted_calculation_count`. | `unsupported_downstream_repair`. | Implemented as the second additive companion. It proves the pattern on comment-to-recalculation propagation while preserving `multimodal_corridor_review_response_package` as the formula-closure baseline. |

## Universal SSC-01 Variant Translation

Use the same eight-variant skeleton from the guide, but localize names and defect evidence:

| Generic Variant | SSC-01 Interpretation |
| --- | --- |
| `clean` | All sources reconcile and issue-readiness is `ready_to_issue`. |
| `missing_<critical-field>` | One source omits the critical level, timing value, load, capacity, sight-distance field, or comment owner needed for RLR-04. |
| `stale_<basis>_revision` | The formula-bearing design basis or criteria document is one revision behind the register. |
| `<identity>_mismatch` | Chainage, datum, approach ID, device ID, cabinet ID, source revision, or scenario ID drifts across files. |
| `scenario_copy_forward` | A timing, storm, detour, night, bus-priority, or closure case is copied from another corridor without a decision record. |
| `open_critical_comment` | A critical authority/discipline comment is open with no owner and no agreed action. |
| `minor_open_comment_carried` | A minor comment is open but has an owner and carried action; readiness should be `ready_with_carried_actions`. |
| `<genuine-criterion-failure>` | One recomputable criterion is genuinely exceeded; the package may claim pass by using a wrong method or stale source. |

## Brainstorm: New Review-First SSC-01 Task Shapes

These are not new product-count coverage rows. They are possible review-native variants or later composite environments built from the same SSC-01 source world.

1. **Corridor Source-Triage Review**
   A source-only packet where the model inventories plan/profile, drainage, ITS, signal, power, and authority files, then identifies which products are even reviewable. This would emphasize `[ID]` and `not_applicable` discipline rather than calculations.

2. **Comment-To-Calculation Propagation Review**
   A reviewer changes one chainage, storm case, closure case, or device membership. The task asks which calculations must be rerun and which claimed results are now stale. This is closest to `SSC-01-LH-08`.

3. **Device Identity Reconciliation Review**
   The same VMS/camera/cabinet appears under slightly different IDs across drawings, schedules, and network sheets. The model must decide whether this is one object, two objects, or insufficient evidence. This would stress RLR-02 and avoid purely numeric grading.

4. **Issue-Readiness Delta Review**
   Two package revisions are supplied: previous and current. The task asks whether the latest issue closes previous findings without collateral source drift. This would add a comparison dimension without adding new runtime machinery.

5. **Authority-Partition Review**
   Road authority, ITS owner, drainage reviewer, and electrical criteria disagree. The task asks which criterion controls each gate and whether the package overclaims approval. This would use the `SSC-20` overlay inside an SSC-01 source packet.

## Recommended Small-Increment Order

1. **Keep `SSC-01-LH-01` as the reference implementation**, but do not call it complete for benchmark purposes until model-run evidence exists.
2. **Keep `SSC-01-LH-02` as the first additive companion**, but likewise do not call it benchmark-ready until model-run evidence exists.
3. **Keep `SSC-01-LH-08` as the second additive companion**, but likewise do not call it benchmark-ready until broader model-run evidence exists.
4. **Keep `SSC-01-LH-03` as the third additive companion**, preserving `road-lighting-its-drainage-operations-package` and treating `road-visual-operations-issue-review-package` as synthetic review-first coverage only until model runs exist.
5. **Keep `SSC-01-LH-04` as the fourth additive companion**, preserving `emergency-detour-roadside-device-continuity-package` and treating `emergency-detour-device-issue-review-package` as synthetic review-first coverage only until model runs exist.
6. **Keep `SSC-01-LH-05` as the fifth additive companion**, preserving `bus-priority-signal-cabinet-load-package` and treating `bus-priority-cabinet-issue-review-package` as synthetic review-first coverage only until model runs exist.
7. **Keep `SSC-01-LH-06` as the sixth additive companion**, preserving `culvert-driveway-access-safety-continuity-package` and treating `driveway-access-safety-issue-review-package` as synthetic review-first coverage only until model runs exist.
8. **Keep `SSC-01-LH-07` as the seventh additive companion**, preserving `roadside-cabinet-flood-heat-backup-energy-package` and treating `roadside-cabinet-serviceability-issue-review-package` as synthetic review-first coverage only until model runs exist.
9. **Decide whether to broaden model-run evidence across the SSC-01 review-first set**, based on whether targeted model runs localize failures under the inverted acceptance criteria.

## Acceptance Notes For The Next SSC-01 Task

The next implementation should not be accepted on template tests alone. Before calling it claimable:

- all twelve authoring-guide tests must exist and pass;
- generated medium instances must cover at least four variants;
- every generated instance must validate with golden pass `1.0` and fluent-unsafe fail `<= 0.5`;
- source diffing across variants must show only the intended defect;
- closure tests should recompute evidence for at least the clean variant, the genuine-failure variant, and the missing-evidence variant;
- model-run evidence should later show at least one strong model below `1.0` somewhere with localized verifier details.

`SSC-01-LH-01`, `SSC-01-LH-02`, `SSC-01-LH-03`, `SSC-01-LH-04`, `SSC-01-LH-05`, `SSC-01-LH-06`, `SSC-01-LH-07`, and `SSC-01-LH-08` currently satisfy the template/test/generation side of this checklist, and the preserved SSC-01 formula-baseline tests remain saved baseline artifacts. After the prompt-leakage cleanup, `SSC-01-LH-03` through `SSC-01-LH-08` also have regression guards that instructions and system prompts stay variant-blind: prompts may state generic schema, matrix, missing-data, exact-key, and RLR-08 self-consistency rules, but they may not map hidden defects to statuses, omitted keys, source citations, or readiness decisions. The existing generated-batch validations remain useful golden-fixture and fluent-unsafe-fixture checks; the post-hardening model runs that reached `1.00` after defect-to-answer prompt edits are no longer valid model-quality evidence. All post-cleanup model evidence should be recollected under the inverted acceptance criterion.

## Prompt-Leakage Correction, 2026-07-05

The first model-probe pass on `SSC-01-LH-03`, `SSC-01-LH-07`, and `SSC-01-LH-08` taught two different lessons that must be kept separate:

- Valid contract lessons remain: exact `computed_evidence` key names belong in the generic schema; unavailable keys should be omitted rather than emitted as `null`; claim-boundary scoring should accept equivalent explicit negation such as "does not constitute"; decimal CCTV storage and thermal utilization ratio are source-owned conventions; and the local source-mirroring bug invalidated affected runs until fixed.
- The post-probe prompt hardening that mapped hidden defects to expected item/status/readiness outcomes was contamination. Runs that reached `1.00` after those edits are retained only as contaminated-prompt diagnostics showing how not to tune these tasks.
- The pre-strip sub-ceiling runs are the more useful evidence. `SSC-01-LH-08` copied-scenario rewards around `0.56` to `0.85`, `SSC-01-LH-08` missing-revised-chainage at `0.83`, `SSC-01-LH-07` missing-derating at `0.83`, and `SSC-01-LH-07` thermal-deficiency at `0.87` show real discrimination: the models found much of the packet but over-cascaded, used the wrong convention, or made a questionable readiness/localization decision. Under the inverted acceptance criterion, those are task-quality signals, not automatic defects to patch away.
- The cleanup strip removed variant-specific missing-PoE, missing-closure-duration, missing-cabinet-capacity, missing-road-edge-level, missing-derating, copied-scenario, and missing-chainage answer mappings from instructions and system prompts. The same pass removed generated-criteria text that pre-classified hidden variants. Generic matrix definitions, exact-key schema rules, omit-vs-null rules, source-owned calculation conventions, and verifier-side equivalence fixes remain.

After this correction, the old "hardened to `1.00`" claims for `SSC-01-LH-03`, `SSC-01-LH-07`, and `SSC-01-LH-08` are void as model-quality evidence. The next model-run pass should recollect evidence from the stripped prompt state and should expect at least one strong model to score below `1.00` somewhere with localized verifier details.

## Post-Cleanup Probe Gate, 2026-07-06

Fresh current-state instances were generated for `SSC-01-LH-03`, `SSC-01-LH-07`, and `SSC-01-LH-08` after the prompt-leakage cleanup, then probed through the Bedrock-backed `pydantic_ai` adapter. This creates the initial model evidence required by the cross-SSC implementation menu, without treating 1.00 saturation as the goal.

| Product | Variant | Model | Reward | Main verifier signal |
| --- | --- | --- | --- | --- |
| `SSC-01-LH-03` road visual operations | `missing_poe_switch_budget` | Haiku | `0.83` | Identity and claim boundary passed; missing-data localization still cascaded into RLR-04/RLR-06/RLR-08 and one evidence key. |
| `SSC-01-LH-07` roadside cabinet serviceability | `thermal_capacity_deficient` | Haiku | `0.78` | Numeric evidence passed, but finding linkage, identity ledger, claim boundary, and RLR-07/RLR-08 localization lost credit. |
| `SSC-01-LH-07` roadside cabinet serviceability | `thermal_capacity_deficient` | Sonnet | `0.95` | Matrix, evidence, linkage, readiness, and claim boundary passed; only identity-ledger credit failed. |
| `SSC-01-LH-08` corridor comment response | `missing_revised_chainage` | Haiku | `0.75` | Evidence/readiness mostly passed; the missing chainage condition over-cascaded into RLR-02/RLR-03/RLR-04, with linkage and claim-boundary losses. |
| `SSC-01-LH-08` corridor comment response | `missing_revised_chainage` | Sonnet | `0.88` | Linkage/readiness/identity/claim boundary passed; the same missing chainage condition over-cascaded into RLR-02/RLR-03/RLR-04 and missed one evidence key. |

Evidence is recorded in `ara/evidence/logs/ssc01_review_first_post_cleanup_model_probes_self_check.txt` and Ara-lite `C155` / `E149` / `EV1379` / `N298`. The result is an initial probe packet only. It does not claim broad two-model evidence across every SSC-01 companion, full hidden-variant coverage, source-pack hardening, accepted project evidence, authority approval, generated benchmark readiness, or benchmark readiness.

## Evidence Packet v2 (2026-07-06, Post-Triage)

Collected after the probe-triage commit (generic pending-value clause; fractional identity-ledger scoring). Raw run artifacts (instances, outputs, reward and details JSON) are archived untracked at `artefacts/local-runs/ssc01-evidence-v2/`; instances regenerate deterministically from the recorded seeds at the triage commit. Adapter `pydantic_ai`; Haiku `claude-haiku-4-5`, Sonnet `claude-sonnet-4-6`.

Triage-validation and breadth results (one run per row):

| Product | Variant | Model | Reward | Classification |
| --- | --- | --- | --- | --- |
| LH-08 | `missing_revised_chainage` | Sonnet | `0.95` (was `0.88`) | Pending-value definition resolved the cascade for Sonnet; residual RLR-03 and one evidence key are model evidence. |
| LH-08 | `missing_revised_chainage` | Haiku | `0.72` | Cascade persists under decidable definitions: standing capability finding, not ambiguity. |
| LH-08 | `scenario_copy_forward` | Haiku | `0.72` | Same over-cascade signature; model evidence. |
| LH-07 | `thermal_capacity_deficient` | Sonnet | `0.99` (was `0.95`) | Fractional ledger validated (7/8 tokens); model evidence. |
| LH-03 | missing PoE budget | Haiku | `0.77` | RLR-06 plus readiness contradiction; model evidence. |
| LH-01 | `freeboard_deficient` | Haiku / Sonnet | `0.86` / `0.95` | Haiku: RLR-05/08, linkage. Sonnet loss was claim-boundary wording only, reclassified as verifier inconsistency and fixed by porting the accepted negation-equivalence check to LH-01 through LH-06 (retroactively `1.00`). |
| LH-02 / LH-04 / LH-05 / LH-06 | defect variants | Haiku | `0.78` / `0.88` / `0.97` / `0.76` | All localized losses; model evidence. |

Reliability (LH-01, Haiku, five fresh seeds per variant; pass = reward `1.0`):

| Variant | Mean reward | pass@1 | pass@5 | pass^5 |
| --- | --- | --- | --- | --- |
| `clean` | `0.822` | `0.20` | `1.00` | `~0.0003` |
| `freeboard_deficient` | `0.844` | `0.00` | `0.00` | `0.00` |

Standing model findings from this packet: (1) Haiku over-cascades single defects across adjacent matrix items even under decidable definitions, while Sonnet localizes; (2) recurring RLR-08 self-inconsistency — readiness decisions contradicting the model's own matrix; (3) phantom findings on defect-free packets — clean-variant runs at `0.59`-`0.63` flipped RLR-02/03/04 with no defect present. Reporting convention going forward: `pass^k` means all `k` runs pass (tau-bench); `pass@k` means at least one.

This packet does not claim full hidden-variant coverage, two-model evidence on every companion, source-pack hardening, accepted project evidence, authority approval, generated benchmark readiness, or benchmark readiness.

## Non-Claims

This plan does not claim accepted project evidence, authority approval, real source-pack parsing, full standards compliance, source-pack hardening, executable verifier readiness beyond implemented template validation, generated benchmark readiness, or benchmark readiness. It is a design and sequencing artifact for converting SSC-01 products to the review-first standard.
