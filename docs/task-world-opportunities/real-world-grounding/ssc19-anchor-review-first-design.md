# ABOUTME: Design note for the SSC-19 fire-water hazard review-first anchor template.
# ABOUTME: Records borrowed math, source packet shape, variants, validation, probes, and provisional rulings.

# SSC-19 Anchor Review-First Design

Template: `fire-water-storage-hazard-issue-review-package`

Status: built for audit hold, uncommitted. This is a task-owned synthetic review environment under provisional engineering rulings, not SME-endorsed evidence.

## Borrowed Math

Borrowed baseline: `fire_water_sprinkler_storage_package`.

The review template reuses the baseline formula family for:

- Hazard-class driven design density, area, hose allowance, and duration.
- Sprinkler demand as design density times design area.
- Total fire-water demand as sprinkler demand plus hose allowance.
- Required storage volume from total demand and duration.
- Storage-volume margin.
- Fire-pump capacity margin.

The prompt does not state these methods. They live in `sources/criteria-comments.md` as source-owned assessment bases, including the source-owned hazard classification table.

## Scene IDs

Scene objects follow the SSC-19 plan:

| Role | ID |
|---|---|
| Building | `BLDG-19` |
| Hazard arrangement | `HAZ-19` |
| Commodity certificate | `CERT-19-COM-01` |
| Sprinkler system | `SPR-19` |
| Fire-water tank | `TANK-19` |
| Fire pump | `PUMP-19` |
| Water-supply basis | `WS-19` |
| Fire strategy case | `AHJ-19-CASE-A` |
| Criteria memo | `CRIT-SSC19-001` |

Source files:

- `document-register.md`
- `hazard-storage-arrangement.md`
- `sprinkler-hydrant-demand.md`
- `tank-pump-schedule.md`
- `fire-strategy-operating-case.md`
- `water-supply-basis.md`
- `criteria-comments.md`

## Matrix Specialization

The template keeps the post-triage `RLR-01` to `RLR-09` contract.

| Item | SSC-19 meaning |
|---|---|
| `RLR-01` | Packet completeness across hazard, demand, tank/pump, strategy, water-supply, and criteria files. |
| `RLR-02` | Object identity across building, hazard arrangement, commodity evidence, sprinkler, tank, pump, water-supply basis, fire strategy case, and criteria memo. |
| `RLR-03` | Hazard classification and demand basis traceability and recomputation. |
| `RLR-04` | Fire-water storage and pump adequacy. |
| `RLR-05` | Same AHJ strategy case and storage arrangement across documents. |
| `RLR-06` | Water-supply and pump-capacity resilience. |
| `RLR-07` | Comment and action closure. |
| `RLR-08` | Reviewer readiness consistency. |
| `RLR-09` | Claim boundary. |

Evidence keys:

- `design_density_mm_min`
- `design_area_m2`
- `sprinkler_demand_l_min`
- `hose_allowance_l_min`
- `required_duration_min`
- `required_volume_m3`
- `storage_volume_margin_m3`
- `pump_capacity_margin_l_min`

## Variants

| Variant | Primary flip | Readiness | Register expectation |
|---|---|---|---|
| `clean` | none | `ready_to_issue` | none |
| `missing_commodity_classification` | `RLR-04 = insufficient_data` | `not_ready_to_issue` | information request |
| `stale_hazard_basis_revision` | `RLR-03 = fail` | `not_ready_to_issue` | finding |
| `tank_volume_mismatch` | `RLR-02 = fail` | `not_ready_to_issue` | finding |
| `scenario_copy_forward` | `RLR-05 = fail` | `not_ready_to_issue` | finding |
| `open_critical_comment` | `RLR-07 = fail` | `not_ready_to_issue` | finding |
| `minor_open_comment_carried` | none | `ready_with_carried_actions` | carried action |
| `storage_deficient_under_true_class` | `RLR-04 = fail` | `not_ready_to_issue` | finding |

## Provisional Ruling

Ruling: classification drift is exercised through the genuine-failure route first. The packet may compute fire-water demand under a lower hazard class, but the true class follows the source-owned classification table using the stated commodity and storage height. When that true class drives required storage above the provided tank storage, the primary flip stays on `RLR-04`, with the classification error cited as the cause.

Alternative an SME may prefer: treat the classification drift itself as an `RLR-02` identity or basis defect before evaluating storage adequacy.

If reversed: change the genuine-failure variant, matrix item evidence map, and verifier localization expectations so classification is the primary flip. The current storage-deficiency route should remain available as a later SSC-19 variant if the SME accepts the calculation shape but not the first-flip priority.

## Validation

Targeted tests:

- `uv run pytest tests/templates/test_fire_water_storage_hazard_issue_review_package.py -q`
- Result: `35 passed`.

Lint/format:

- `uv run ruff check src/aec_bench/templates/builtin/mechanical/fire_water_storage_hazard_issue_review_package tests/templates/test_fire_water_storage_hazard_issue_review_package.py`
- `uv run ruff format --check src/aec_bench/templates/builtin/mechanical/fire_water_storage_hazard_issue_review_package tests/templates/test_fire_water_storage_hazard_issue_review_package.py`
- Result: all checks passed; four files already formatted.

Generated-instance validation:

- Command: `uv run aec-bench generate task fire-water-storage-hazard-issue-review-package --instances 8 --difficulty medium --seed 2026070602 --output /private/tmp/aec-bench-ssc19-anchor-audit-current`
- Variant coverage: 6 variants in 8 instances.
- Validator result: 8/8 generated instances passed.
- Golden pass scores: 1.000 on all 8.
- Fluent unsafe memo scores: 0.320 to 0.400.

Variant-blindness self-check:

- `instruction.md` and `system_prompt.md` do not contain packet variant names or planted-defect tokens.
- The prompt states only generic review workflow, boundary rules, output schema, exact key names, and missing-value behavior.
- Source-diff audit showed each defect variant changes only the intended source file or files.

## Probe Ledger

Probe adapter: `pydantic_ai`.

| Variant | Model | Reward | Main losses | Triage classification |
|---|---|---:|---|---|
| `storage_deficient_under_true_class` | Haiku `au.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.40 | `RLR-03/04/06`, all computed evidence keys, required-register linkage, readiness support, claim boundary. The response followed the package's lower hazard class and declared ready. | `model-evidence` |
| `storage_deficient_under_true_class` | Sonnet `au.anthropic.claude-sonnet-4-6` | 0.40 | Same loss pattern as Haiku: missed true-class storage deficiency, omitted recomputed true-class evidence, and declared ready. | `model-evidence` |
| `missing_commodity_classification` | Haiku `au.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.00 | Official verifier returned no parseable structured answer. Audit found JSON-like content, but the output violated the required final fenced-block contract. | `model-evidence` |
| `missing_commodity_classification` | Sonnet `au.anthropic.claude-sonnet-4-6` | 0.83 | `RLR-03/04`, required-register linkage, partial identity ledger, and claim boundary. The response mostly found the missing-data state and selected `not_ready_to_issue`. | `model-evidence` |

Probe artifact root: `/private/tmp/aec-bench-ssc19-anchor-probes`.

No probe loss is classified as a suspected contract defect in this pass. The Haiku missing-data zero is a format/output-discipline failure against the explicit final-fenced-JSON contract, not a verifier crash or source closure failure.

## Non-Claims

This template is a task-owned synthetic review environment built under a provisional SSC-19 engineering ruling. It does not claim SME endorsement, accepted project evidence, authority approval, source-pack hardening, full standards compliance, executable-verifier readiness, or benchmark readiness.
