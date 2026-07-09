# ABOUTME: Design note for the SSC-04 coastal flood equipment elevation review-first anchor.
# ABOUTME: Records borrowed math, source packet shape, variants, validation, probes, and provisional rulings.

# SSC-04 Anchor Review-First Design

Template: `coastal-flood-equipment-elevation-issue-review-package`

Status: built for audit hold, uncommitted. This is a task-owned synthetic review environment under provisional engineering rulings, not SME-endorsed evidence.

## Borrowed Math

Borrowed baseline: `coastal_flood_outfall_pump_elevation_package`.

The review template reuses the baseline formula family for:

- Design flood level from present MSL, tide amplitude, SLR, storm surge, and wave/runup.
- Required equipment elevation/freeboard.
- Pump/outfall duty and tailwater checks.
- Equipment elevation margins.

The review-first anchor narrows the worksheet surface to datum/elevation review. It does not expose the old full storage, motor, and feeder worksheet outputs. The prompt does not state these methods. They live in `sources/criteria-comments.md` as source-owned assessment bases.

## Scene IDs

Scene objects follow the SSC-04 plan:

| Role | ID |
|---|---|
| Site | `SITE-04` |
| Datum | `DATUM-04` |
| Tide/water-level basis | `TIDE-04-BASIS-01` |
| SLR scenario | `SLR-04-SCEN-01` |
| Runup case | `RUNUP-04-WAVE-01` |
| Switchboard | `SWBD-04` |
| Generator | `GEN-04` |
| Outfall | `OUTFALL-04` |
| Pump duty | `PUMP-04` |
| Criteria memo | `CRIT-SSC04-001` |

Source files:

- `document-register.md`
- `tide-water-level-basis.md`
- `slr-planning-horizon.md`
- `wave-runup-basis.md`
- `asset-survey.md`
- `pump-outfall-schedule.md`
- `criteria-comments.md`

## Matrix Specialization

The template keeps the post-triage `RLR-01` to `RLR-09` contract.

| Item | SSC-04 meaning |
|---|---|
| `RLR-01` | Packet completeness across water-level, SLR, runup, survey, pump/outfall, and criteria files. |
| `RLR-02` | Object identity and datum consistency across AHD, chart datum, equipment, outfall, pump, and criteria references. |
| `RLR-03` | Coastal boundary basis traceability and recomputation. |
| `RLR-04` | Equipment elevation adequacy against design flood level and required freeboard. |
| `RLR-05` | Planning horizon, asset class, and coastal event consistency. |
| `RLR-06` | Outfall tailwater/submergence and pump-duty resilience. |
| `RLR-07` | Comment and action closure. |
| `RLR-08` | Reviewer readiness consistency. |
| `RLR-09` | Claim boundary. |

Evidence keys:

- `design_flood_level_m_ahd`
- `wave_runup_m`
- `switchboard_freeboard_m`
- `switchboard_freeboard_margin_m`
- `generator_freeboard_margin_m`
- `outfall_submergence_margin_m`
- `pump_duty_margin`

## Variants

| Variant | Primary flip | Readiness | Register expectation |
|---|---|---|---|
| `clean` | none | `ready_to_issue` | none |
| `missing_switchboard_survey_level` | `RLR-04 = insufficient_data` | `not_ready_to_issue` | information request |
| `stale_water_level_basis_revision` | `RLR-03 = fail` | `not_ready_to_issue` | finding |
| `asset_survey_chart_datum_labelled_ahd` | `RLR-02 = fail` | `not_ready_to_issue` | finding |
| `scenario_copy_forward` | `RLR-05 = fail` | `not_ready_to_issue` | finding |
| `open_critical_comment` | `RLR-07 = fail` | `not_ready_to_issue` | finding |
| `minor_open_comment_carried` | none | `ready_with_carried_actions` | carried action |
| `switchboard_below_design_level` | `RLR-04 = fail` | `not_ready_to_issue` | finding |

## Provisional Ruling

Ruling: the criteria memo declares AHD controlling and owns the chart-datum-to-AHD offset. Conflicting-datum evidence is therefore a review defect with a decidable answer, not an unanswerable puzzle. The datum-label conflict is the identity variant on `RLR-02`; the low switchboard margin remains the genuine-failure variant on `RLR-04`.

Alternative an SME may prefer: treat any chart-datum conflict as a coastal-boundary basis failure on `RLR-03` before evaluating object identity.

If reversed: change the datum variant's primary matrix row and verifier localization expectations. The current `RLR-02` route should remain available if the SME accepts datum preservation as an identity issue.

## Validation

Targeted tests:

- `uv run pytest tests/templates/test_coastal_flood_equipment_elevation_issue_review_package.py -q`
- Result: `36 passed`.

Lint/format:

- `uv run ruff check src/aec_bench/templates/builtin/civil/coastal_flood_equipment_elevation_issue_review_package tests/templates/test_coastal_flood_equipment_elevation_issue_review_package.py`
- `uv run ruff format --check src/aec_bench/templates/builtin/civil/coastal_flood_equipment_elevation_issue_review_package tests/templates/test_coastal_flood_equipment_elevation_issue_review_package.py`
- Result: all checks passed; four files already formatted.

Generated-instance validation:

- Command: `uv run aec-bench generate task coastal-flood-equipment-elevation-issue-review-package --instances 8 --difficulty medium --seed 2026070402 --output /private/tmp/aec-bench-ssc04-anchor-e2e-current`
- Variant coverage: 5 variants in 8 instances.
- Validator result: 8/8 generated instances passed.
- Source count: 7 source files on all 8 instances.

Variant-blindness self-check:

- `instruction.md` and `system_prompt.md` do not contain packet variant names or planted-defect tokens.
- The prompt states only generic review workflow, boundary rules, output schema, exact key names, and missing-value behavior.
- Source-diff audit showed each defect variant changes only the intended source file:
  - `missing_switchboard_survey_level`: `sources/asset-survey.md`
  - `stale_water_level_basis_revision`: `sources/tide-water-level-basis.md`
  - `asset_survey_chart_datum_labelled_ahd`: `sources/asset-survey.md`
  - `scenario_copy_forward`: `sources/slr-planning-horizon.md`
  - `open_critical_comment`: `sources/criteria-comments.md`
  - `minor_open_comment_carried`: `sources/criteria-comments.md`
  - `switchboard_below_design_level`: `sources/asset-survey.md`

## Probe Ledger

Probe adapter: `pydantic_ai`.

Probe artifact root: `/private/tmp/aec-bench-anchor-model-probes-20260709/runs-short-timeout`.

| Variant | Model | Reward | Per-gate losses | Classification |
|---|---:|---:|---|---|
| `switchboard_below_design_level` | Haiku `au.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.74 | `RLR-06/07/08`, outfall and pump-duty evidence keys, failed-finding linkage, readiness support, identity ledger, claim boundary. | `model-evidence` |
| `switchboard_below_design_level` | Sonnet `au.anthropic.claude-sonnet-4-6` | 0.86 | `RLR-08`, failed-finding linkage, readiness support, identity ledger, claim boundary. | `model-evidence` |
| `missing_switchboard_survey_level` | Haiku `au.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.76 | `RLR-04/06/08`, pump-duty evidence, failed-finding linkage, readiness support, claim boundary. | `model-evidence` |
| `missing_switchboard_survey_level` | Sonnet `au.anthropic.claude-sonnet-4-6` | 0.94 | Readiness support, identity ledger, claim boundary. | `model-evidence` |

No probe loss is classified as a suspected contract defect in this pass. The runs show useful discrimination without all-1.00 saturation: both models find much of the issue structure, but lose credit on linkage, readiness support, and claim-boundary discipline.

## Non-Claims

This template is a task-owned synthetic review environment built under a provisional SSC-04 engineering ruling. It does not claim SME endorsement, accepted project evidence, authority approval, source-pack hardening, full standards compliance, executable-verifier readiness, or benchmark readiness.
