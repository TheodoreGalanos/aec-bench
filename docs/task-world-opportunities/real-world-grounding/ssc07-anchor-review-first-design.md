# ABOUTME: Design note for the SSC-07 ground structural-electrical review-first anchor template.
# ABOUTME: Records borrowed math, source packet shape, variants, validation, probes, and provisional rulings.

# SSC-07 Anchor Review-First Design

Template: `ground-structural-electrical-issue-review-package`

Status: built for audit hold, uncommitted. This is a task-owned synthetic review environment under provisional engineering rulings, not SME-endorsed evidence.

## Borrowed Math

Borrowed baseline: `ground_structural_electrical_safety_package`.

The review template reuses the baseline formula family for:

- SPT correction factors.
- Source-owned Terzaghi bearing factors and water-table correction.
- Earthing-grid resistance.
- Grid-current screening converted to the task-owned touch-voltage convention.

The review-first anchor intentionally narrows the old worksheet surface. It does not expose CPT-derived governing friction-angle outputs; instead the criteria memo owns the provisional SSC-07 SPT-to-friction-angle correlation for this packet. The prompt does not state these methods. They live in `sources/criteria-comments.md` as source-owned assessment bases.

## Scene IDs

Scene objects follow the SSC-07 plan:

| Role | ID |
|---|---|
| Site | `SITE-07` |
| Borehole | `BH-07` |
| SPT record | `SPT-07` |
| Groundwater record | `GW-07` |
| Ground interpretation memo | `GIM-07-MEMO-01` |
| Foundation | `FDN-07` |
| Resistivity survey | `RES-07` |
| Earthing grid | `GRID-07` |
| Criteria memo | `CRIT-SSC07-001` |

Source files:

- `document-register.md`
- `borehole-spt-logs.md`
- `groundwater-record.md`
- `ground-interpretation-memo.md`
- `foundation-load-table.md`
- `resistivity-survey.md`
- `earthing-grid-design.md`
- `criteria-comments.md`

## Matrix Specialization

The template keeps the post-triage `RLR-01` to `RLR-09` contract.

| Item | SSC-07 meaning |
|---|---|
| `RLR-01` | Packet completeness across borehole/SPT, groundwater, ground memo, foundation, resistivity, earthing grid, and criteria files. |
| `RLR-02` | Object identity and authority partition across geotechnical strength evidence and electrical resistivity evidence. |
| `RLR-03` | Ground interpretation basis traceability and recomputation. |
| `RLR-04` | Structural bearing adequacy under the source-owned water-table correction. |
| `RLR-05` | Same structure, load case, and design basis across ground memo, foundation table, and earthing package. |
| `RLR-06` | Earthing-grid resistance and touch-voltage resilience. |
| `RLR-07` | Comment and action closure. |
| `RLR-08` | Reviewer readiness consistency. |
| `RLR-09` | Claim boundary. |

Evidence keys:

- `corrected_spt_n60`
- `design_friction_angle_deg`
- `allowable_bearing_kpa`
- `bearing_margin_kpa`
- `grid_resistance_ohm`
- `grid_resistance_margin_ohm`
- `touch_voltage_margin_v`

## Variants

| Variant | Primary flip | Readiness | Register expectation |
|---|---|---|---|
| `clean` | none | `ready_to_issue` | none |
| `missing_groundwater_level` | `RLR-04 = insufficient_data` | `not_ready_to_issue` | information request |
| `stale_ground_memo_revision` | `RLR-03 = fail` | `not_ready_to_issue` | finding |
| `resistivity_strength_misuse` | `RLR-02 = fail` | `not_ready_to_issue` | finding |
| `scenario_copy_forward` | `RLR-05 = fail` | `not_ready_to_issue` | finding |
| `open_critical_comment` | `RLR-07 = fail` | `not_ready_to_issue` | finding |
| `minor_open_comment_carried` | none | `ready_with_carried_actions` | carried action |
| `bearing_fos_deficient` | `RLR-04 = fail` | `not_ready_to_issue` | finding |

## Provisional Ruling

Ruling: the authority-partition defect is the identity variant. If the ground interpretation memo cites a resistivity-traverse layer as a strength stratum, the primary flip is `RLR-02`. The numeric bearing failure remains the genuine-failure variant on `RLR-04`; both exist with one flip each.

Alternative an SME may prefer: treat the resistivity-as-strength misuse as an interpretation-basis failure on `RLR-03`, or make the bearing adequacy row fail when the misuse affects the selected bearing parameters.

If reversed: change the partition variant's primary matrix row and verifier localization expectations. The current `RLR-02` route should remain available if the SME accepts authority partition as an identity-preservation issue.

## Validation

Targeted tests:

- `uv run pytest tests/templates/test_ground_structural_electrical_issue_review_package.py -q`
- Result: `36 passed`.

Lint/format:

- `uv run ruff check src/aec_bench/templates/builtin/ground/ground_structural_electrical_issue_review_package tests/templates/test_ground_structural_electrical_issue_review_package.py`
- `uv run ruff format --check src/aec_bench/templates/builtin/ground/ground_structural_electrical_issue_review_package tests/templates/test_ground_structural_electrical_issue_review_package.py`
- Result: all checks passed; four files already formatted.

Generated-instance validation:

- Command: `uv run aec-bench generate task ground-structural-electrical-issue-review-package --instances 8 --difficulty medium --seed 2026070701 --output /private/tmp/aec-bench-ssc07-anchor-e2e`
- Variant coverage: 6 variants in 8 instances.
- Validator result: 8/8 generated instances passed.
- Source count: 8 source files on all 8 instances.

Variant-blindness self-check:

- `instruction.md` and `system_prompt.md` do not contain packet variant names or planted-defect tokens.
- The prompt states only generic review workflow, boundary rules, output schema, exact key names, and missing-value behavior.
- Source-diff audit showed each defect variant changes only the intended source file:
  - `missing_groundwater_level`: `sources/groundwater-record.md`
  - `stale_ground_memo_revision`: `sources/ground-interpretation-memo.md`
  - `resistivity_strength_misuse`: `sources/ground-interpretation-memo.md`
  - `scenario_copy_forward`: `sources/foundation-load-table.md`
  - `open_critical_comment`: `sources/criteria-comments.md`
  - `minor_open_comment_carried`: `sources/criteria-comments.md`
  - `bearing_fos_deficient`: `sources/foundation-load-table.md`

## Probe Ledger

Probe adapter: `pydantic_ai`.

Probe artifact root: `/private/tmp/aec-bench-anchor-model-probes-20260709/runs-short-timeout`.

| Variant | Model | Reward | Per-gate losses | Classification |
|---|---:|---:|---|---|
| `bearing_fos_deficient` | Haiku `au.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.46 | `RLR-03/04/06`, bearing and earthing evidence keys, required-register linkage, readiness support, claim boundary. | `model-evidence` |
| `bearing_fos_deficient` | Sonnet `au.anthropic.claude-sonnet-4-6` | 0.83 | `RLR-03/04`, allowable bearing and bearing-margin evidence, readiness support, claim boundary. | `model-evidence` |
| `missing_groundwater_level` | Haiku `au.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.56 | `RLR-03/06`, earthing evidence keys, readiness support, claim boundary. | `model-evidence` |
| `missing_groundwater_level` | Sonnet `au.anthropic.claude-sonnet-4-6` | 0.97 | `RLR-03`, readiness support. | `model-evidence` |

No probe loss is classified as a suspected contract defect in this pass. The runs show useful discrimination: Haiku struggles with both recomputation and readiness support, while Sonnet mostly localizes the missing-data case but still loses small review-matrix/readiness credit.

## Non-Claims

This template is a task-owned synthetic review environment built under a provisional SSC-07 engineering ruling. It does not claim SME endorsement, accepted project evidence, authority approval, source-pack hardening, full standards compliance, executable-verifier readiness, or benchmark readiness.
