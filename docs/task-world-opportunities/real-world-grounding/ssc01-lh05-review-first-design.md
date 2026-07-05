# ABOUTME: Records the SSC-01-LH-05 review-first companion design before implementation.
# ABOUTME: Preserves the existing formula template while defining the source packet, variants, evidence, and verifier contract.

# SSC-01-LH-05 Review-First Design

This note applies the review-first authoring guide to `SSC-01-LH-05: Bus Priority, Signal Corridor, And Cabinet Load Package`.

It preserves the existing formula-closure template, `bus-priority-signal-cabinet-load-package`, as the math/source baseline. The proposed additive review-first companion is `bus-priority-cabinet-issue-review-package`. This design does not replace the formula template, implement the runnable companion, add model-run evidence, claim source-pack hardening, or claim benchmark readiness.

## Baseline To Preserve

Existing formula template:

```text
bus-priority-signal-cabinet-load-package
```

Current shape:

```text
bus approach speed and grade
  -> yellow interval and all-red interval
  -> bus handling capacity and passenger-demand margin
  -> controller, detector, radio, VMS, and signal-head cabinet load
  -> feeder current and voltage-drop margin
  -> battery runtime and backup-duration margin
  -> synthetic pass score
```

That template is a useful saved calculation artifact. The review-first companion should not overwrite it. The companion should change the job from "calculate the bus-priority signal/cabinet memo" to "review whether the bus-priority corridor package is ready to issue."

## Review-First Companion

Human title:

```text
Review the bus-priority corridor and cabinet package for issue
```

Proposed template name:

```text
bus-priority-cabinet-issue-review-package
```

Proposed directory:

```text
src/aec_bench/templates/builtin/electrical/bus_priority_cabinet_issue_review_package/
```

Proposed category:

```text
road-review
```

The category stays aligned with the other SSC-01 review-first companions.

## Scene And Object IDs

Reuse the SSC-01-LH-05 object family so the review-first task remains connected to the formula baseline:

| Object | Suggested ID | Role |
| --- | --- | --- |
| Bus-priority operating scenario | `BUS-SSC01-005` | Priority period, bus demand, occupancy, and transit-priority objective. |
| Signal timing basis | `SIG-SSC01-005` | Signal group, approach speed/grade, yellow interval, and all-red clearance basis. |
| Detector set | `DET-SSC01-005` | Detectors and priority call inputs that activate the bus-priority case. |
| Signal controller | `CTRL-SSC01-005` | Controller cabinet equipment and timing plan membership. |
| Roadside cabinet | `CAB-SSC01-005` | Cabinet load capacity, connected equipment list, and power boundary. |
| Cabinet feeder | `FEED-SSC01-005` | Feeder voltage, length, conductor resistance, power factor, and allowable drop. |
| Backup supply | `BATT-SSC01-005` | Battery capacity, efficiency, and required backup duration. |
| Owner operations criterion | `OPS-SSC01-005` | Required bus-priority scenario, passenger demand, and readiness criterion. |

## Source Packet

The review-first task should generate eight source files under `/workspace/sources/`:

| File | Source role | Contents |
| --- | --- | --- |
| `document-register.md` | Register | Document IDs, revisions, status, discipline owner, and current/issued status. |
| `bus-priority-operations-plan.md` | Primary operations evidence | Bus-priority scenario, period, buses per hour, occupancy, passenger demand, and owner operations case. |
| `signal-phasing-timing-sheet.md` | Traffic/signal evidence | Signal group, approach speed/grade, yellow reaction/deceleration terms, all-red width, bus length, clearance speed, and claimed timing results. |
| `detector-controller-schedule.md` | Object identity | Detector count, controller ID, priority call source, signal group membership, and cabinet association. |
| `cabinet-load-schedule.md` | Equipment/load evidence | Controller, detector, transit radio, VMS, signal-head, and auxiliary loads plus cabinet capacity and claimed cabinet-load margin. |
| `feeder-backup-schedule.md` | Electrical resilience evidence | Feeder voltage, power factor, length, conductor resistance, allowable voltage drop, battery capacity, efficiency, backup duration, and claimed margins. |
| `owner-operations-criterion.md` | Owner criterion | Required priority period, passenger-demand basis, minimum backup duration, and issue-readiness expectations. |
| `criteria-comments.md` | Criteria and review comments | Assessment bases, derived criteria, primary/collateral boundary rules, missing-data boundary rules, review comments, owners, and actions. |

Methods and conventions belong in `criteria-comments.md`, not the instruction. The instruction should only say that the packet is the source of truth.

## Review Matrix

Use the same nine review items:

| Item | SSC-01-LH-05 meaning |
| --- | --- |
| `RLR-01` | Packet completeness: all required bus-priority, signal, detector/controller, cabinet, feeder/backup, owner-criterion, and criteria files are present with IDs and revisions. |
| `RLR-02` | Object identity: bus-priority scenario, signal group, detectors, controller, cabinet, feeder, backup supply, and owner case stay consistent. |
| `RLR-03` | Signal/priority basis: yellow interval, all-red interval, passenger-demand basis, and timing-plan basis are traceable, current, and recomputable. |
| `RLR-04` | Cabinet and priority adequacy: the cabinet load, passenger capacity, voltage-drop margin, and backup runtime clear the source criteria for the same priority case and equipment set. |
| `RLR-05` | Scenario consequence: the same bus-priority operating scenario is used across operations plan, signal timing, detector/controller schedule, cabinet loads, feeder/backup, and owner criterion. |
| `RLR-06` | Secondary-discipline resilience: feeder voltage drop and backup runtime are source-backed and internally consistent with the cabinet load schedule. |
| `RLR-07` | Comment and action closure: critical comments are closed or have named actions; minor comments may be carried with owner/action. |
| `RLR-08` | Readiness consistency: the final decision follows the review matrix, findings, information requests, and action register. |
| `RLR-09` | Claim boundary: the response avoids unsupported approval, compliance, source-hardening, executable-verifier, or benchmark-readiness claims. |

## Evidence Keys

Initial evidence keys for `compute()`:

| Key | Review role |
| --- | --- |
| `yellow_interval_s` | RLR-03 signal timing recomputation. |
| `all_red_interval_s` | RLR-03 clearance timing recomputation. |
| `bus_handling_capacity_pax_h` | RLR-04 passenger-capacity recomputation. |
| `bus_capacity_margin_pax_h` | RLR-04 passenger-capacity adequacy. |
| `cabinet_load_w` | RLR-04/RLR-06 cabinet-load recomputation. |
| `cabinet_load_margin_w` | RLR-04 cabinet-capacity adequacy. |
| `feeder_current_a` | RLR-06 feeder-current recomputation. |
| `feeder_voltage_drop_percent` | RLR-06 voltage-drop recomputation. |
| `voltage_drop_margin_percent` | RLR-06 voltage-drop adequacy. |
| `battery_runtime_h` | RLR-06 backup-runtime recomputation. |
| `battery_margin_h` | RLR-06 backup-duration adequacy. |

The first implementation should use cabinet load as the primary RLR-04 genuine-failure route because it ties detector/controller membership, signal-priority equipment, connected roadside loads, and the electrical cabinet boundary together. Voltage-drop exceeded remains a strong optional later route, but the first pass should avoid two overlapping electrical failures.

## Variants

Use the eight-variant skeleton from the guide:

| Variant | Primary flip | Readiness | Required register behavior |
| --- | --- | --- | --- |
| `clean` | None | `ready_to_issue` | No findings, requests, or carried actions. |
| `missing_cabinet_capacity` | `RLR-04 -> insufficient_data` | `not_ready_to_issue` | One information request naming the missing cabinet capacity in `CAB-SSC01-005`. |
| `stale_signal_timing_revision` | `RLR-03 -> fail` | `not_ready_to_issue` | One finding against the stale signal timing / priority-plan basis. |
| `detector_controller_mismatch` | `RLR-02 -> fail` | `not_ready_to_issue` | One finding where detector/controller membership differs between the priority plan and cabinet load schedule. |
| `scenario_copy_forward` | `RLR-05 -> fail` | `not_ready_to_issue` | One finding where the bus-priority case is copied from another corridor or period without a decision record. |
| `open_critical_comment` | `RLR-07 -> fail` | `not_ready_to_issue` | One finding for an open critical owner/signal/electrical review comment without owner/action. |
| `minor_open_comment_carried` | None | `ready_with_carried_actions` | One carried action with owner and linked item. |
| `cabinet_load_exceeded` | `RLR-04 -> fail` | `not_ready_to_issue` | One finding where recomputed cabinet load exceeds the cabinet capacity, while the package mis-claims adequacy. |

Optional later variant:

```text
voltage_drop_exceeded
```

Keep it out of the first implementation unless cabinet load proves too narrow. One implementation pass should not include both `cabinet_load_exceeded` and `voltage_drop_exceeded` if that makes RLR-04/RLR-06 localization noisy.

## Boundary Rules

These rules should appear in the instruction, system prompt, and criteria source from the first implementation:

- Missing cabinet capacity is an information-request case, not a known failed cabinet-load calculation. Set RLR-04 to `insufficient_data`, omit `cabinet_load_margin_w` if it cannot be computed from packet values, and request the exact missing cabinet capacity/source.
- Missing cabinet capacity is a critical blocker. The readiness decision should be `not_ready_to_issue`, not `ready_with_carried_actions`; do not carry the missing capacity as a normal action.
- A copied bus-priority scenario belongs under RLR-05. Do not cascade it into RLR-02 if object IDs reconcile. Do not cascade it into RLR-03/RLR-04/RLR-06 when the timing, capacity, cabinet load, feeder, and backup calculations are source-backed and internally consistent with their stated source values.
- A stale signal timing or priority-plan revision belongs under RLR-03. Do not also fail RLR-04 if the cabinet and traffic-priority adequacy checks are internally recomputable from current non-stale sources.
- A detector/controller mismatch belongs under RLR-02. Do not also fail cabinet load, feeder voltage, or backup runtime unless the mismatch independently makes those source values unrecomputable.
- Every finding, information request, and action must name one exact RLR item. Do not write combined items such as `RLR-04/RLR-06`.
- RLR-08 is reviewer self-consistency, not package-readiness positivity.

## Derivation-Controlled Quantities

The review-first engine should not reuse the fixed min/max values from the formula template. It should sample realistic ranges and derive pass/fail margins:

- Quantize speeds to `1 km/h`.
- Quantize approach grade to `0.1 percent`.
- Quantize timing terms to `0.1 s`.
- Quantize bus counts and occupancy to whole units.
- Quantize passenger demand to `10 pax/h`.
- Quantize equipment loads to `5 W`.
- Quantize cabinet capacity to `10 W`.
- Quantize feeder voltage to the selected enum (`230 V` or `240 V`).
- Quantize feeder length to `0.01 km`, resistance to `0.01 ohm/km`, and power factor to `0.01`.
- Quantize voltage-drop limits to `0.1 percent`.
- Quantize battery capacity to `0.1 kWh`, battery efficiency to `0.01`, and backup duration to `0.1 h`.

Derive these quantities from hidden margins:

- `peak_passenger_demand_pax_h = bus_handling_capacity_pax_h - bus_capacity_margin_pax_h` for pass variants.
- `cabinet_capacity_w = ceil_to(cabinet_load_w + cabinet_load_margin_w, 10 W)` for pass variants.
- For `cabinet_load_exceeded`, derive `cabinet_capacity_w = floor_to(cabinet_load_w - cabinet_load_deficit_w, 10 W)` so `cabinet_load_margin_w` is negative after printed-value recomputation.
- `allowable_voltage_drop_pct = ceil_to(feeder_voltage_drop_percent + voltage_drop_margin_percent, 0.1 percent)` for pass variants.
- `battery_capacity_kwh = ceil_to((required_backup_h + battery_margin_h) * cabinet_load_w / 1000 / battery_efficiency, 0.1 kWh)` for pass variants, then recompute runtime from the printed battery capacity.

The criteria source must state all unit conventions explicitly, including km/h to m/s for signal timing, signed grade in the yellow-interval denominator, passenger capacity as buses per hour times occupancy, watts to kilowatts for runtime, two-way feeder voltage-drop percent, and battery kWh/runtime conversion. Do not leave conversion conventions implicit.

## Verifier Implications

Start from the existing custom verifier pattern and adapt only constants:

```text
ITEM_EVIDENCE = {
  "RLR-03": ["yellow_interval_s", "all_red_interval_s"],
  "RLR-04": ["bus_handling_capacity_pax_h", "bus_capacity_margin_pax_h", "cabinet_load_w", "cabinet_load_margin_w"],
  "RLR-06": ["feeder_current_a", "feeder_voltage_drop_percent", "voltage_drop_margin_percent", "battery_runtime_h", "battery_margin_h"],
}
```

Use `VARIANT_REQUEST_TOKENS` for `missing_cabinet_capacity`:

```text
("cabinet", "capacity", "cab-ssc01-005")
```

Use `REQUIRED_LEDGER_TOKENS`:

```text
bus-ssc01-005, sig-ssc01-005, det-ssc01-005, ctrl-ssc01-005, cab-ssc01-005, feed-ssc01-005, batt-ssc01-005, ops-ssc01-005
```

## TDD Implementation Slice

The first implementation should start with tests, not code:

1. Add `tests/templates/test_bus_priority_cabinet_issue_review_package.py` before creating the template; the initial red state should be the missing template directory.
2. Preserve `bus-priority-signal-cabinet-load-package` unchanged as the formula/source baseline.
3. Assert `tool_mode = "no-tool"`, eight source files under `environment/sources/`, no generated calc script, and no engineering numbers in `instruction.md`.
4. Assert all eight variants map to exactly one primary RLR flip, with `missing_cabinet_capacity` producing RLR-04 `insufficient_data` and `cabinet_load_exceeded` producing RLR-04 `fail`.
5. Add closure tests that reparse rendered sources and independently recompute yellow interval, all-red interval, bus capacity, cabinet load, feeder voltage drop, and battery runtime evidence.
6. Add source-boundary tests for copied scenario, detector/controller mismatch, and missing cabinet capacity before running models.
7. Only after focused tests, generated instance validation, and Ara capture should this be added to the composite catalogue.

## Implementation Outcome

The additive review-first companion is now implemented as:

```text
bus-priority-cabinet-issue-review-package
```

The preserved formula baseline remains:

```text
bus-priority-signal-cabinet-load-package
```

Implementation evidence:

- Added a separate `no-tool` built-in template with `params.toml`, `engine.py`, `instruction.md`, `system_prompt.md`, and a custom stage-gated `verify.py`.
- The engine generates the eight-file source packet described above and keeps source values out of the instruction.
- Focused tests pass with 36 tests covering discovery, parameter variation, variant gold states, source-pack IDs, missing-capacity boundaries, source-owned unit conversions, source-only recomputation for clean/genuine-failure/missing-evidence packets, scaffold layout, golden fixtures, verifier localization, evidence gating, and readiness anti-gaming.
- An 8-instance medium batch generated under `/private/tmp/aec-bench-ssc01-lh05-review-first-e2e` validates 8/8 with zero warnings. Every `golden_pass.md` scored `1.000`; fluent-unsafe `golden_fail.md` scored between `0.320` and `0.400`.
- The generated seed batch covered `cabinet_load_exceeded`, `scenario_copy_forward`, `clean`, `detector_controller_mismatch`, `minor_open_comment_carried`, `open_critical_comment`, and `missing_cabinet_capacity`. The `stale_signal_timing_revision` variant is covered by focused tests but was not sampled in that seed batch.
- The composite-catalogue entry materializes and verifies with package-contract score `1.0`, while preserving the formula baseline as a companion source/math reference.

Remaining gaps:

- No model-run evidence has been added for SSC-01-LH-05.
- No source-pack hardening, real controller/timing/cabinet export parsing, accepted project evidence, authority approval, full standards compliance, generated benchmark readiness, or benchmark readiness is claimed.

## Non-Claims

This is a design and implementation record for a task-owned synthetic review-first companion. It does not claim model-run evidence, real controller/timing/SCATS/SCOOT/cabinet export parsing, accepted project evidence, authority approval, source-pack hardening, full standards compliance, generated benchmark readiness, or benchmark readiness.
