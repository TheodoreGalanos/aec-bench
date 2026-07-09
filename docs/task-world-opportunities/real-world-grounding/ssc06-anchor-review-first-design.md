# ABOUTME: Design note for the SSC-06 pump duty/NPSH review-first anchor template.
# ABOUTME: Records borrowed math, source packet shape, variants, validation, probes, and provisional rulings.

# SSC-06 Anchor Review-First Design

Template: `pump-station-duty-npsh-issue-review-package`

Status: built for audit hold, uncommitted. This is a task-owned synthetic review environment under provisional engineering rulings, not SME-endorsed evidence.

## Borrowed Math

Borrowed baseline: `pump_station_duty_power_npsh_feeder_package`.

The review template reuses the baseline formula family for:

- Hazen-Williams rising-main headloss.
- Minor-loss and total dynamic head.
- Pump curve head margin.
- Hydraulic, shaft, and motor input power.
- Motor service-factor margin.
- NPSH available from atmospheric pressure, vapor pressure, wet-well level, and suction loss.
- Three-phase feeder current and voltage drop.

The prompt does not state these methods. They live in `sources/criteria-comments.md` as source-owned assessment bases.

## Scene IDs

Scene objects follow the SSC-06 plan:

| Role | ID |
|---|---|
| Wet well | `WW-06` |
| Pump | `PMP-06` |
| Rising main | `RM-06` |
| Motor | `MOT-06` |
| Feeder | `FDR-06` |
| Duty case | `DUTY-06` |
| Criteria memo | `CRIT-SSC06-001` |

Source files:

- `document-register.md`
- `wet-well-suction-geometry.md`
- `rising-main-schedule.md`
- `pump-curve-datasheet.md`
- `motor-feeder-schedule.md`
- `duty-operating-case.md`
- `criteria-comments.md`

## Matrix Specialization

The template keeps the post-triage `RLR-01` to `RLR-09` contract.

| Item | SSC-06 meaning |
|---|---|
| `RLR-01` | Packet completeness across wet-well, rising-main, pump, motor/feeder, duty-case, and criteria files. |
| `RLR-02` | Object identity across pump ID, impeller, wet well, rising main, motor, feeder, duty case, and criteria memo. |
| `RLR-03` | Pump duty basis traceability and recomputation. |
| `RLR-04` | Pump head and NPSH adequacy. |
| `RLR-05` | Same duty flow and operating case across documents. |
| `RLR-06` | Motor sizing and feeder voltage-drop resilience. |
| `RLR-07` | Comment and action closure. |
| `RLR-08` | Reviewer readiness consistency. |
| `RLR-09` | Claim boundary. |

Evidence keys:

- `total_dynamic_head_m`
- `pump_head_margin_m`
- `npsh_available_m`
- `npsh_margin_m`
- `motor_input_kw`
- `motor_margin_kw`
- `feeder_voltage_drop_percent`
- `voltage_drop_margin_percent`

## Variants

| Variant | Primary flip | Readiness | Register expectation |
|---|---|---|---|
| `clean` | none | `ready_to_issue` | none |
| `missing_wetwell_min_level` | `RLR-04 = insufficient_data` | `not_ready_to_issue` | information request |
| `stale_pump_curve_revision` | `RLR-03 = fail` | `not_ready_to_issue` | finding |
| `impeller_diameter_mismatch` | `RLR-02 = fail` | `not_ready_to_issue` | finding |
| `scenario_copy_forward` | `RLR-05 = fail` | `not_ready_to_issue` | finding |
| `open_critical_comment` | `RLR-07 = fail` | `not_ready_to_issue` | finding |
| `minor_open_comment_carried` | none | `ready_with_carried_actions` | carried action |
| `npsh_margin_deficient` | `RLR-04 = fail` | `not_ready_to_issue` | finding |

## Provisional Ruling

Ruling: NPSH margin is the first SSC-06 blocker. The genuine-failure variant recomputes NPSHa at the source-owned minimum wet-well operating level and compares it to NPSHr plus the source-owned required margin. The package claim can be wrong by using average wet-well level, but the review flip remains `RLR-04`.

Alternative an SME may prefer: prioritize off-curve/POR operation or motor/feeder mismatch as the first blocker.

If reversed: change the genuine-failure variant, matrix item evidence map, and one or more evidence keys. The current NPSH variant should remain available as a later SSC-06 variant if the SME accepts the calculation shape but not the first-blocker priority.

## Validation

Targeted tests:

- `uv run pytest tests/templates/test_pump_station_duty_npsh_issue_review_package.py -q`
- Result: `35 passed`.

Lint/format:

- `uv run ruff format src/aec_bench/templates/builtin/mechanical/pump_station_duty_npsh_issue_review_package tests/templates/test_pump_station_duty_npsh_issue_review_package.py`
- `uv run ruff check src/aec_bench/templates/builtin/mechanical/pump_station_duty_npsh_issue_review_package tests/templates/test_pump_station_duty_npsh_issue_review_package.py`
- Result: all checks passed.

Generated-instance validation:

- Command: `uv run aec-bench generate task pump-station-duty-npsh-issue-review-package --instances 8 --difficulty medium --seed 20260706 --output /private/tmp/aec-bench-ssc06-anchor-e2e`
- Variant coverage: 5 variants in 8 instances.
- Validator result: 8/8 generated instances passed.
- Golden pass scores: 1.000 on all 8.
- Fluent unsafe memo scores: 0.320 to 0.350.

Variant-blindness self-check:

- `instruction.md` and `system_prompt.md` do not contain packet variant names or planted-defect tokens.
- The prompt states only generic review workflow, boundary rules, output schema, exact key names, and missing-value behavior.

## Probe Ledger

Probe adapter: `pydantic_ai`.

| Variant | Model | Reward | Main losses | Triage classification |
|---|---|---:|---|---|
| `npsh_margin_deficient` | Haiku `au.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.00 | No parseable fenced JSON block; verifier returned zero details. | `model-evidence` |
| `npsh_margin_deficient` | Sonnet `au.anthropic.claude-sonnet-4-6` | 0.87 | `RLR-03`, missing failed-finding linkage, claim-boundary miss. | `model-evidence` |
| `missing_wetwell_min_level` | Haiku `au.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.43 | `RLR-03/04/06/08`, motor/feeder evidence misses, linkage misses, readiness unsupported by recomputed evidence. | `model-evidence` |
| `missing_wetwell_min_level` | Sonnet `au.anthropic.claude-sonnet-4-6` | 0.92 | `RLR-03`, claim-boundary miss. | `model-evidence` |

Probe artifact root: `/private/tmp/aec-bench-ssc06-anchor-probes`.

No probe loss is classified as a suspected contract defect in this pass. The Haiku zero is a format/output-discipline failure, not a verifier crash or source closure failure.

## Non-Claims

This template is a task-owned synthetic review environment built under a provisional SSC-06 engineering ruling. It does not claim SME endorsement, accepted project evidence, authority approval, source-pack hardening, full standards compliance, executable-verifier readiness, or benchmark readiness.
