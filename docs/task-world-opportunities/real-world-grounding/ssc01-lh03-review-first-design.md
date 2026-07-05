# ABOUTME: Records the SSC-01-LH-03 review-first companion design and implementation state.
# ABOUTME: Preserves the existing formula template while tracking the source packet, variants, evidence, and verifier contract.

# SSC-01-LH-03 Review-First Design

This note applies the review-first authoring guide to `SSC-01-LH-03: Road Lighting, ITS, And Drainage Operations Scene`.

It preserves the existing formula-closure template, `road-lighting-its-drainage-operations-package`, as the math/source baseline. The additive review-first companion now exists as `road-visual-operations-issue-review-package`. A targeted missing-PoE Haiku diagnostic run has since been used to harden two source-boundary ambiguities; this does not replace the formula template, claim broad model-run evidence, claim source-pack hardening, or claim benchmark readiness.

## Baseline To Preserve

Existing formula template:

```text
road-lighting-its-drainage-operations-package
```

Current shape:

```text
lighting grid lux values
  -> average/minimum illuminance, uniformity, and glare variation
  -> CCTV/VMS/sensor/controller network load and uplink headroom
  -> CCTV storage retention
  -> PoE budget
  -> storm water-level alarm margin
  -> UPS energy for luminaires and devices
  -> synthetic pass score
```

That template is a useful saved calculation artifact. The review-first companion should not overwrite it. The companion should change the job from "calculate the visual operations memo" to "review whether the road visual operations issue package is ready to issue."

## Review-First Companion

Human title:

```text
Review the road visual operations package for issue
```

Template name:

```text
road-visual-operations-issue-review-package
```

Implemented directory:

```text
src/aec_bench/templates/builtin/electrical/road_visual_operations_issue_review_package/
```

Implemented category:

```text
road-review
```

The category stays aligned with the other SSC-01 review-first companions.

## Scene And Object IDs

Reuse the SSC-01-LH-03 object family so the review-first task remains recognizably connected to the formula baseline:

| Object | Suggested ID | Role |
| --- | --- | --- |
| Road corridor | `RD-SSC01-003` | Road segment and night/storm operating context. |
| Lighting grid | `LGT-SSC01-003` | Six-point grid or summarized luminaire design output. |
| Luminaire group | `LUM-SSC01-003` | Selected luminaires and UPS lighting load. |
| CCTV schedule | `CCTV-SSC01-003` | Active cameras, bitrate, and storage retention basis. |
| VMS device | `VMS-SSC01-003` | Road-user visual device included in network and PoE checks. |
| ITS network | `NET-SSC01-003` | Uplink capacity and communications load aggregation. |
| Cabinet power/PoE | `PWR-SSC01-003` | PoE switch budget and UPS supply. |
| Storm sensor | `WLS-SSC01-003` | Water-level sensor and alarm threshold. |
| Operating case | `OPS-SSC01-003` | Night storm / incident operating case tying visual, ITS, and drainage checks together. |

## Source Packet

The review-first task generates seven source files under `/workspace/sources/`:

| File | Source role | Contents |
| --- | --- | --- |
| `document-register.md` | Register | Document IDs, revisions, status, discipline owner, and current/issued status. |
| `road-segment-and-lighting-grid.md` | Primary visual evidence | Corridor ID, operating case, grid point lux values, average/minimum/claimed uniformity, luminaire group, and lighting design basis. |
| `device-register.md` | Object identity | CCTV, VMS, storm sensor, controller, PoE switch, cabinet, luminaire group, and served road segment. |
| `network-and-storage.md` | Communications evidence | CCTV count/load, VMS load, sensor/controller load, overhead, uplink capacity, bitrate, retention, storage overhead, and claimed network/storage results. |
| `poe-and-ups-schedule.md` | Exposure/criterion evidence | PoE loads, switch budget, luminaire/device UPS load, autonomy, efficiency, and claimed PoE/UPS results. |
| `storm-operations-note.md` | Scenario evidence | Night/storm incident case, water-level sensor reading, alarm threshold, and which devices must stay operational. |
| `criteria-comments.md` | Criteria and review comments | Assessment bases, derived criteria, primary/collateral boundary rules, missing-data boundary rules, review comments, owners, and actions. |

Methods and conventions belong in `criteria-comments.md`, not the instruction. The instruction should only say that the packet is the source of truth.

## Review Matrix

Use the same nine review items:

| Item | SSC-01-LH-03 meaning |
| --- | --- |
| `RLR-01` | Packet completeness: all required visual, device, network, power, storm, and criteria files are present with IDs and revisions. |
| `RLR-02` | Object identity: road segment, lighting grid, luminaires, CCTV, VMS, storm sensor, cabinet, network, PoE switch, and operating case stay consistent. |
| `RLR-03` | Visual operations basis: lighting grid and method are traceable, current, and recomputable. |
| `RLR-04` | Visual/field-device adequacy: the controlling lighting uniformity or PoE budget clears the source criterion for the same device set. |
| `RLR-05` | Scenario consequence: the same night/storm operating case is used across lighting, CCTV/VMS, network, power, and storm operations. |
| `RLR-06` | Secondary-discipline resilience: network headroom, CCTV storage, storm margin, and UPS energy are source-backed and internally consistent. |
| `RLR-07` | Comment and action closure: critical comments are closed or have named actions; minor comments may be carried with owner/action. |
| `RLR-08` | Readiness consistency: the final decision follows the review matrix, findings, information requests, and action register. |
| `RLR-09` | Claim boundary: the response avoids unsupported approval, compliance, source-hardening, executable-verifier, or benchmark-readiness claims. |

## Evidence Keys

Initial evidence keys for `compute()`:

| Key | Review role |
| --- | --- |
| `average_illuminance_lux` | RLR-03 lighting-grid recomputation. |
| `minimum_illuminance_lux` | RLR-03/RLR-04 lighting adequacy. |
| `uniformity_ratio` | RLR-04 visual adequacy. |
| `minimum_uniformity_ratio` | Source-owned criterion evidence. |
| `total_network_load_mbps` | RLR-06 communications recomputation. |
| `network_headroom_mbps` | RLR-06 communications adequacy. |
| `total_cctv_storage_tb` | RLR-06 storage recomputation. |
| `poe_load_w` | RLR-04/RLR-06 PoE recomputation. |
| `poe_headroom_w` | RLR-04 PoE adequacy. |
| `water_level_margin_m` | RLR-06 storm operations adequacy. |
| `ups_energy_kwh` | RLR-06 backup-energy sizing evidence. |

The implemented companion uses PoE budget as the primary RLR-04 genuine-failure route because it ties CCTV/VMS/sensor membership to power and operations. Lighting uniformity remains a second valid adequacy check and a possible later variant.

## Variants

Use the eight-variant skeleton from the guide:

| Variant | Primary flip | Readiness | Required register behavior |
| --- | --- | --- | --- |
| `clean` | None | `ready_to_issue` | No findings, requests, or carried actions. |
| `missing_poe_switch_budget` | `RLR-04 -> insufficient_data` | `not_ready_to_issue` | One information request naming the missing PoE switch budget in `poe-and-ups-schedule.md`. |
| `stale_lighting_grid_revision` | `RLR-03 -> fail` | `not_ready_to_issue` | One finding against the stale lighting-grid revision. |
| `device_register_mismatch` | `RLR-02 -> fail` | `not_ready_to_issue` | One finding where VMS/CCTV/sensor membership differs across device register and network/power schedules. |
| `scenario_copy_forward` | `RLR-05 -> fail` | `not_ready_to_issue` | One finding where the VMS/CCTV/network case is copied from another corridor or daytime case. |
| `open_critical_comment` | `RLR-07 -> fail` | `not_ready_to_issue` | One finding for an open critical visual/ITS/power review comment without owner/action. |
| `minor_open_comment_carried` | None | `ready_with_carried_actions` | One carried action with owner and linked item. |
| `poe_budget_exceeded` | `RLR-04 -> fail` | `not_ready_to_issue` | One finding where recomputed PoE load exceeds source budget, while the package mis-claims adequacy. |

Optional later variant:

```text
uniformity_deficient
```

Keep it out of the first implementation unless PoE proves too narrow. One implementation pass should not include both `poe_budget_exceeded` and `uniformity_deficient` if that makes RLR-04 localization noisy.

## Boundary Rules

These rules should appear in the instruction, system prompt, and criteria source from the first implementation:

- Missing PoE switch budget is an information-request case, not a known failed PoE calculation. Set RLR-04 to `insufficient_data`, omit `poe_headroom_w` if it cannot be computed from packet values, and request the exact missing field/source.
- A copied night/storm operating case belongs under RLR-05. Do not cascade it into RLR-02 if object IDs reconcile. Do not cascade it into RLR-04/RLR-06 when the calculations are source-backed and internally consistent with their stated source values.
- A stale lighting-grid revision belongs under RLR-03. Do not also fail RLR-04 if the current criterion cannot be checked because the visual basis is stale; use the one primary flip only.
- A device-register mismatch belongs under RLR-02. Do not also fail network, PoE, and storage unless the mismatch independently makes those source values unrecomputable.
- Every finding, information request, and action must name one exact RLR item. Do not write combined items such as `RLR-04/RLR-06`.
- RLR-08 is reviewer self-consistency, not package-readiness positivity.

## Derivation-Controlled Quantities

The review-first engine does not reuse the fixed min/max values from the formula template. It samples realistic ranges and derives pass/fail margins:

- Quantize lux values to `0.1 lux`.
- Quantize network loads to `0.1 Mbps`.
- Quantize storage values to `0.01 TB`.
- Quantize PoE loads and budgets to `1 W`.
- Quantize levels and thresholds to `0.01 m`.
- Quantize UPS efficiency to `0.01`.

Derive these quantities from hidden margins:

- `minimum_uniformity_ratio = floor_or_source_value(uniformity_ratio - pass_margin)` for clean/pass variants, or derive one grid value to make uniformity fail in a future uniformity variant.
- `poe_budget_w = ceil_to(poe_load_w + poe_headroom_margin_w, 1 W)` for pass variants.
- For `poe_budget_exceeded`, derive `poe_budget_w = floor_to(poe_load_w - poe_headroom_deficit_w, 1 W)` so the failure is guaranteed.
- `uplink_capacity_mbps = ceil_to(total_network_load_mbps + network_headroom_margin_mbps, 5 Mbps)` if the first implementation chooses to make uplink capacity a derived source value.
- `storm_alarm_threshold_m = storm_sensor_level_m + water_level_margin_m`.
- `ups_capacity_kwh` may be printed instead of `ups_energy_kwh`; if printed capacity is rounded up, recompute gold from the printed capacity and source load.

## Verifier Implications

Start from the existing custom verifier pattern and adapt only constants:

```text
ITEM_EVIDENCE = {
  "RLR-03": ["average_illuminance_lux", "minimum_illuminance_lux", "uniformity_ratio"],
  "RLR-04": ["poe_load_w", "poe_headroom_w"],
  "RLR-05": [],  # status/finding driven unless scenario speed or mode evidence becomes numeric
  "RLR-06": ["total_network_load_mbps", "network_headroom_mbps", "total_cctv_storage_tb", "water_level_margin_m", "ups_energy_kwh"],
}
```

If `RLR-05` gets a numeric copied-scenario evidence key later, add it deliberately. Otherwise keep it status/finding driven so a scenario-provenance defect does not double-count a correlated calculation.

Use `VARIANT_REQUEST_TOKENS` for `missing_poe_switch_budget`:

```text
("poe", "switch", "budget", "pwr-ssc01-003")
```

Use `REQUIRED_LEDGER_TOKENS`:

```text
rd-ssc01-003, lgt-ssc01-003, lum-ssc01-003, cctv-ssc01-003, vms-ssc01-003, net-ssc01-003, pwr-ssc01-003, wls-ssc01-003, ops-ssc01-003
```

## Implementation Outcome

The first implementation used a TDD slice and keeps the formula artifact intact:

1. Added `tests/templates/test_road_visual_operations_issue_review_package.py` before creating the template; the initial red state was the missing template directory.
2. Implemented `src/aec_bench/templates/builtin/electrical/road_visual_operations_issue_review_package/` as an additive `no-tool` review-first task.
3. Covered discovery, variant gold states, source-pack generation, source-only recomputation, scaffold layout, golden pass/fail fixtures, verifier localization, evidence gating, and readiness anti-gaming.
4. Added a composite-catalogue entry for `road-visual-operations-issue-review-package` after the runnable template validated.
5. Preserved `road-lighting-its-drainage-operations-package` unchanged as the formula/source baseline.
6. A targeted Haiku run on `missing_poe_switch_budget` was then used as a model-diagnostic hardening slice. The first run scored `0.75`: it correctly set RLR-04 to `insufficient_data` and raised the information request, but used a 1024-based CCTV storage conversion and treated the unresolved PoE budget as `ready_with_carried_actions`. The instruction, system prompt, and criteria source now make the missing PoE switch budget a `not_ready_to_issue` blocker and state the source-owned decimal TB conversion basis. The rerun scored `1.00` on that targeted instance.
7. The v2 model output still included `"poe_headroom_w": null` even though the instruction says to omit unrecomputable evidence keys. The current verifier tolerates the extra null because the key is absent from the gold state for the missing-budget variant; treat that as a future strict-schema question rather than benchmark-readiness evidence.

## Non-Claims

This is a design and implementation record for a task-owned synthetic review-first companion plus one targeted model-diagnostic hardening increment. It does not claim broad model-run evidence, real lighting/CCTV/ITS source parsing, AGi32/DIALux/Axis/JVSG/NTCIP/MUTCD export validation, accepted project evidence, authority approval, source-pack hardening, full standards compliance, generated benchmark readiness, or benchmark readiness.
