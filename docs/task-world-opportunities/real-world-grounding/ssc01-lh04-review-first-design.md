# ABOUTME: Records the SSC-01-LH-04 review-first companion design and implementation outcome.
# ABOUTME: Preserves the existing formula template while defining the source packet, variants, evidence, and verifier contract.

# SSC-01-LH-04 Review-First Design

This note applies the review-first authoring guide to `SSC-01-LH-04: Emergency Detour And Roadside Device Continuity`.

It preserves the existing formula-closure template, `emergency-detour-roadside-device-continuity-package`, as the math/source baseline. The additive review-first companion is `emergency-detour-device-issue-review-package`. This design and implementation record does not replace the formula template, add model-run evidence, claim source-pack hardening, or claim benchmark readiness.

## Baseline To Preserve

Existing formula template:

```text
emergency-detour-roadside-device-continuity-package
```

Current shape:

```text
detour scenario and selected VMS message
  -> VMS reading time and message margin
  -> CCTV/VMS/radio/controller network load and uplink headroom
  -> RF received power and link margin
  -> battery runtime and detour-duration margin
  -> feeder voltage-drop margin
  -> synthetic pass score
```

That template is a useful saved calculation artifact. The review-first companion should not overwrite it. The companion should change the job from "calculate the detour continuity memo" to "review whether the emergency detour device package is ready to issue."

## Review-First Companion

Human title:

```text
Review the emergency detour device package for issue
```

Proposed template name:

```text
emergency-detour-device-issue-review-package
```

Proposed directory:

```text
src/aec_bench/templates/builtin/electrical/emergency_detour_device_issue_review_package/
```

Proposed category:

```text
road-review
```

The category stays aligned with the other SSC-01 review-first companions.

## Scene And Object IDs

Reuse the SSC-01-LH-04 object family so the review-first task remains connected to the formula baseline:

| Object | Suggested ID | Role |
| --- | --- | --- |
| Emergency closure scenario | `OPS-SSC01-004` | Incident, closure duration, and operating mode. |
| Detour plan | `DETOUR-SSC01-004` | Detour route, approach speed, and control points. |
| Traffic management plan | `TMP-SSC01-004` | Closure case, staged operation, and traffic-control basis. |
| VMS device set | `VMS-SSC01-004` | Detour message, character height, and reading-time basis. |
| CCTV device set | `CCTV-SSC01-004` | Cameras required for closure monitoring. |
| Communications link | `RF-SSC01-004` | Radio or temporary link budget for the detour device set. |
| Network uplink | `NET-SSC01-004` | Uplink capacity and aggregate ITS load. |
| Cabinet power supply | `PWR-SSC01-004` | Battery/generator capacity, critical load, feeder, and voltage-drop basis. |
| Message library | `MSG-SSC01-004` | Approved detour message text and message length. |

## Source Packet

The review-first task should generate seven source files under `/workspace/sources/`:

| File | Source role | Contents |
| --- | --- | --- |
| `document-register.md` | Register | Document IDs, revisions, status, discipline owner, and current/issued status. |
| `detour-plan.md` | Primary operations evidence | Closure scenario, detour route, approach speed, control points, and required operating duration. |
| `message-library.md` | VMS/message evidence | Selected message, character height, reading rate, message length, and claimed readability result. |
| `device-inventory.md` | Object identity | VMS, CCTV, radio, controller, cabinet, uplink, feeder, and served detour route membership. |
| `communications-topology.md` | Communications evidence | CCTV/VMS/radio/controller loads, overhead, uplink capacity, RF gains/losses/sensitivity, and claimed communications margins. |
| `power-continuity-schedule.md` | Exposure/criterion evidence | Critical load, battery/generator capacity, efficiency, feeder length/resistance/voltage/power factor, and claimed runtime/voltage-drop results. |
| `criteria-comments.md` | Criteria and review comments | Assessment bases, derived criteria, primary/collateral boundary rules, missing-data boundary rules, review comments, owners, and actions. |

Methods and conventions belong in `criteria-comments.md`, not the instruction. The instruction should only say that the packet is the source of truth.

## Review Matrix

Use the same nine review items:

| Item | SSC-01-LH-04 meaning |
| --- | --- |
| `RLR-01` | Packet completeness: all required detour, message, device, communications, power, and criteria files are present with IDs and revisions. |
| `RLR-02` | Object identity: detour route, VMS, CCTV, radio link, network uplink, controller, cabinet, feeder, and operating case stay consistent. |
| `RLR-03` | Detour/message basis: the selected detour case and VMS message legibility basis are traceable, current, and recomputable. |
| `RLR-04` | Continuity adequacy: the battery/generator runtime clears the required closure duration for the same critical device set. |
| `RLR-05` | Scenario consequence: the same emergency closure scenario is used across detour plan, message library, device inventory, communications, and power schedule. |
| `RLR-06` | Secondary-discipline resilience: network headroom, RF link margin, and feeder voltage-drop margin are source-backed and internally consistent. |
| `RLR-07` | Comment and action closure: critical comments are closed or have named actions; minor comments may be carried with owner/action. |
| `RLR-08` | Readiness consistency: the final decision follows the review matrix, findings, information requests, and action register. |
| `RLR-09` | Claim boundary: the response avoids unsupported approval, compliance, source-hardening, executable-verifier, or benchmark-readiness claims. |

## Evidence Keys

Initial evidence keys for `compute()`:

| Key | Review role |
| --- | --- |
| `vms_reading_time_s` | RLR-03 VMS legibility recomputation. |
| `vms_message_margin_chars` | RLR-03/RLR-04 driver-message readability. |
| `required_network_mbps` | RLR-06 network-load recomputation. |
| `network_headroom_mbps` | RLR-06 uplink adequacy. |
| `rf_received_power_dbm` | RLR-06 RF link-budget recomputation. |
| `rf_link_margin_db` | RLR-06 RF link adequacy. |
| `battery_runtime_h` | RLR-04 backup-runtime recomputation. |
| `battery_margin_h` | RLR-04 continuity adequacy. |
| `feeder_voltage_drop_percent` | RLR-06 feeder-voltage recomputation. |
| `voltage_drop_margin_percent` | RLR-06 feeder-voltage adequacy. |

The first implementation should use battery runtime as the primary RLR-04 genuine-failure route because it ties detour duration, device membership, critical load, and cabinet backup supply together. RF link margin remains a strong secondary check and optional later genuine-failure route.

## Variants

Use the eight-variant skeleton from the guide:

| Variant | Primary flip | Readiness | Required register behavior |
| --- | --- | --- | --- |
| `clean` | None | `ready_to_issue` | No findings, requests, or carried actions. |
| `missing_closure_duration` | `RLR-04 -> insufficient_data` | `not_ready_to_issue` | One information request naming the missing required closure duration in `detour-plan.md` / `OPS-SSC01-004`. |
| `stale_detour_plan_revision` | `RLR-03 -> fail` | `not_ready_to_issue` | One finding against the stale detour/message basis. |
| `device_inventory_mismatch` | `RLR-02 -> fail` | `not_ready_to_issue` | One finding where VMS/CCTV/radio/cabinet membership differs across inventory, communications, and power sources. |
| `scenario_copy_forward` | `RLR-05 -> fail` | `not_ready_to_issue` | One finding where the detour duration, message, or traffic-control case is copied from another closure without a decision record. |
| `open_critical_comment` | `RLR-07 -> fail` | `not_ready_to_issue` | One finding for an open critical traffic/ITS/power review comment without owner/action. |
| `minor_open_comment_carried` | None | `ready_with_carried_actions` | One carried action with owner and linked item. |
| `battery_runtime_deficient` | `RLR-04 -> fail` | `not_ready_to_issue` | One finding where recomputed battery runtime is less than required closure duration, while the package mis-claims continuity. |

Optional later variant:

```text
rf_link_margin_deficient
```

Keep it out of the first implementation unless battery runtime proves too narrow. One implementation pass should not include both `battery_runtime_deficient` and `rf_link_margin_deficient` if that makes RLR-04/RLR-06 localization noisy.

## Boundary Rules

These rules should appear in the instruction, system prompt, and criteria source from the first implementation:

- Missing required closure duration is an information-request case, not a known failed runtime calculation. Set RLR-04 to `insufficient_data`, omit `battery_margin_h` if it cannot be computed from packet values, and request the exact missing duration/source.
- Missing required closure duration is a critical blocker. The readiness decision should be `not_ready_to_issue`, not `ready_with_carried_actions`; do not carry the missing duration as a normal action.
- A copied emergency closure scenario belongs under RLR-05. Do not cascade it into RLR-02 if object IDs reconcile. Do not cascade it into RLR-04/RLR-06 when the calculations are source-backed and internally consistent with their stated source values.
- A stale detour plan or message-library revision belongs under RLR-03. Do not also fail RLR-04 if the current runtime criterion cannot be checked because the detour/message basis is stale; use the one primary flip only.
- A device inventory mismatch belongs under RLR-02. Do not also fail network, RF, battery, and feeder checks unless the mismatch independently makes those source values unrecomputable.
- Every finding, information request, and action must name one exact RLR item. Do not write combined items such as `RLR-04/RLR-06`.
- RLR-08 is reviewer self-consistency, not package-readiness positivity.

## Derivation-Controlled Quantities

The review-first engine should not reuse the fixed min/max values from the formula template. It should sample realistic ranges and derive pass/fail margins:

- Quantize speeds to `1 km/h`.
- Quantize VMS character height to `1 in`.
- Quantize message length to `1 char`.
- Quantize network loads and capacities to `0.1 Mbps`.
- Quantize RF values to `0.1 dB` / `0.1 dBm`.
- Quantize battery capacity to `0.1 kWh` and battery efficiency to `0.01`.
- Quantize critical load to `5 W`.
- Quantize closure duration and runtime to `0.1 h`.
- Quantize voltage-drop values to `0.01 percent`.

Derive these quantities from hidden margins:

- `detour_message_length_chars = floor_to(readable_character_capacity - message_margin_chars, 1 char)` for pass variants, while preserving a realistic selected message string in `message-library.md`.
- `uplink_capacity_mbps = ceil_to(required_network_mbps + network_headroom_margin_mbps, 1 Mbps)` for pass variants.
- `rf_receiver_sensitivity_dbm = rf_received_power_dbm - rf_link_margin_db` for pass variants, or derive path loss / sensitivity to make an optional RF failure deterministic.
- `battery_capacity_kwh = ceil_to(required_capacity_kwh_from_duration + battery_capacity_margin_kwh, 0.1 kWh)` for pass variants.
- For `battery_runtime_deficient`, derive `battery_capacity_kwh` or `required_detour_duration_h` so `battery_margin_h` is negative by a sampled deficit after printed-value recomputation.
- `allowable_voltage_drop_pct = ceil_to(feeder_voltage_drop_percent + voltage_drop_margin_percent, 0.1 percent)` for pass variants.

The criteria source must state all unit conventions explicitly, including ft/in to metres for VMS legibility, kWh/W to runtime hours, RF dBm arithmetic, and voltage-drop percent. Do not leave conversion conventions implicit.

## Verifier Implications

Start from the existing custom verifier pattern and adapt only constants:

```text
ITEM_EVIDENCE = {
  "RLR-03": ["vms_reading_time_s", "vms_message_margin_chars"],
  "RLR-04": ["battery_runtime_h", "battery_margin_h"],
  "RLR-05": [],
  "RLR-06": ["required_network_mbps", "network_headroom_mbps", "rf_received_power_dbm", "rf_link_margin_db", "feeder_voltage_drop_percent", "voltage_drop_margin_percent"],
}
```

If `RLR-05` gets a numeric copied-scenario evidence key later, add it deliberately. Otherwise keep it status/finding driven so a scenario-provenance defect does not double-count a correlated calculation.

Use `VARIANT_REQUEST_TOKENS` for `missing_closure_duration`:

```text
("closure", "duration", "ops-ssc01-004", "detour")
```

Use `REQUIRED_LEDGER_TOKENS`:

```text
ops-ssc01-004, detour-ssc01-004, tmp-ssc01-004, vms-ssc01-004, cctv-ssc01-004, rf-ssc01-004, net-ssc01-004, pwr-ssc01-004, msg-ssc01-004
```

## TDD Implementation Slice

The first implementation should start with tests, not code:

1. Add `tests/templates/test_emergency_detour_device_issue_review_package.py` before creating the template; the initial red state should be the missing template directory.
2. Preserve `emergency-detour-roadside-device-continuity-package` unchanged as the formula/source baseline.
3. Assert `tool_mode = "no-tool"`, seven source files under `environment/sources/`, no generated calc script, and no engineering numbers in `instruction.md`.
4. Assert all eight variants map to exactly one primary RLR flip, with `missing_closure_duration` producing RLR-04 `insufficient_data` and `battery_runtime_deficient` producing RLR-04 `fail`.
5. Add closure tests that reparse rendered sources and independently recompute VMS legibility, network load, RF margin, battery runtime, and voltage-drop evidence.
6. Add source-boundary tests for copied scenario and missing closure duration before running models.
7. Only after focused tests, generated instance validation, and Ara capture should this be added to the composite catalogue.

## Implementation Outcome

Implemented artifacts:

```text
src/aec_bench/templates/builtin/electrical/emergency_detour_device_issue_review_package/
tests/templates/test_emergency_detour_device_issue_review_package.py
src/aec_bench/task_world_templates/catalogue.py
tests/task_world_templates/test_products.py
```

The implemented companion keeps `tool_mode = "no-tool"`, generates the seven-file source packet under `/workspace/sources/`, samples real parameter ranges, withholds numeric values from `instruction.md`, keeps source-owned methods in `criteria-comments.md`, and uses a custom matrix/evidence/linkage/readiness/identity-claims verifier.

Focused tests pass:

```text
uv run pytest tests/templates/test_emergency_detour_device_issue_review_package.py -q
36 passed
```

Composite alignment and focused task tests pass together:

```text
uv run pytest tests/templates/test_emergency_detour_device_issue_review_package.py tests/task_world_templates/test_products.py -q
42 passed
```

Generated medium batch:

```text
uv run aec-bench generate task emergency-detour-device-issue-review-package --instances 8 --difficulty medium --seed 20260705 --output /private/tmp/aec-bench-ssc01-lh04-review-first-e2e
```

The generated batch covered `clean`, `missing_closure_duration`, `device_inventory_mismatch`, `battery_runtime_deficient`, `stale_detour_plan_revision`, and `scenario_copy_forward` in that seed run. All eight generated instances validated with zero warnings; every `golden_pass.md` scored `1.000`, and fluent-unsafe `golden_fail.md` scored between `0.320` and `0.400`.

Composite package-contract validation:

```text
uv run aec-bench --json task composite-template materialize-example emergency-detour-device-issue-review-package --output /private/tmp/aec-bench-ssc01-lh04-issue-review-composite-example
uv run aec-bench --json task composite-template verify-example /private/tmp/aec-bench-ssc01-lh04-issue-review-composite-example
```

Both composite commands passed with `score=1.0` and five explicit data gaps: model-run evidence, real VMS/CCTV/ITS sources, real power-continuity sources, source-pack hardening, and accepted project sources.

## Non-Claims

This is a design and implementation record for a task-owned synthetic review-first companion. It does not claim model-run evidence, real MUTCD/NTCIP/export parsing, accepted project evidence, authority approval, source-pack hardening, full standards compliance, generated benchmark readiness, or benchmark readiness.
