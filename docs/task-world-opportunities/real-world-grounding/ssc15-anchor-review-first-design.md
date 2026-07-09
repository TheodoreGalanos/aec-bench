# ABOUTME: Design note for the SSC-15 product submittal review-first anchor template.
# ABOUTME: Records borrowed math, source packet shape, variants, validation, probes, and provisional rulings.

# SSC-15 Anchor Review-First Design

Template: `product-submittal-compliance-issue-review-package`

Status: built for audit hold, uncommitted. This is a task-owned synthetic review environment under provisional engineering rulings, not SME-endorsed evidence.

## Borrowed Math

Borrowed baseline: `product_submittal_compliance_package`.

The review template reuses the baseline product-compliance family for:

- Product submittal evidence completeness.
- Certificate and heat traceability.
- Review-comment and deviation closeout.
- Product compliance disposition.

The review-first anchor adds the SSC-15 plan's source-owned material checks:

- Carbon equivalent: `CEV = C + Mn/6 + (Cr + Mo + V)/5 + (Ni + Cu)/15`.
- Carbon-equivalent margin.
- Yield-strength margin.
- Tensile-strength margin.
- Certificate coverage count.
- Traceability match count.

The prompt does not state these methods. They live in `sources/criteria-comments.md` as source-owned assessment bases.

## Scene IDs

Scene objects follow the SSC-15 plan:

| Role | ID |
|---|---|
| Submittal | `SUB-15` |
| Product | `PROD-15` |
| Required grade | `GRADE-15` |
| Heat A | `HEAT-15-A` |
| Heat B | `HEAT-15-B` |
| Mill certificates | `CERT-15-MILL-01` |
| Application schedule | `APP-15-SCH-01` |
| Deviation register | `DEV-15-LOG-01` |
| Criteria memo | `CRIT-SSC15-001` |

Source files:

- `document-register.md`
- `submittal-manifest.md`
- `mill-certificates.md`
- `heat-traceability-table.md`
- `product-application-schedule.md`
- `deviation-register.md`
- `criteria-comments.md`

## Matrix Specialization

The template keeps the post-triage `RLR-01` to `RLR-09` contract.

| Item | SSC-15 meaning |
|---|---|
| `RLR-01` | Packet completeness across submittal, certificate, traceability, application, deviation, and criteria files. |
| `RLR-02` | Object identity across submittal, product, grade, heat numbers, certificates, application rows, deviations, and criteria memo. |
| `RLR-03` | Certificate and property basis traceability and recomputation. |
| `RLR-04` | Product compliance adequacy for CEV, yield, tensile, certificate coverage, and traceability. |
| `RLR-05` | Same product grade, standard, and application use case across schedule, certificates, deviations, and criteria. |
| `RLR-06` | Certificate coverage and heat-traceability source-status resilience. |
| `RLR-07` | Comment and action closure. |
| `RLR-08` | Reviewer readiness consistency. |
| `RLR-09` | Claim boundary. |

Evidence keys:

- `carbon_equivalent_max`
- `carbon_equivalent_margin`
- `yield_strength_margin_mpa`
- `tensile_strength_margin_mpa`
- `certificate_coverage_count`
- `traceability_match_count`

## Variants

| Variant | Primary flip | Readiness | Register expectation |
|---|---|---|---|
| `clean` | none | `ready_to_issue` | none |
| `missing_heat_number` | `RLR-04 = insufficient_data` | `not_ready_to_issue` | information request |
| `stale_certificate_revision` | `RLR-03 = fail` | `not_ready_to_issue` | finding |
| `heat_number_mismatch` | `RLR-02 = fail` | `not_ready_to_issue` | finding |
| `scenario_copy_forward` | `RLR-05 = fail` | `not_ready_to_issue` | finding |
| `open_critical_comment` | `RLR-07 = fail` | `not_ready_to_issue` | finding |
| `minor_open_comment_carried` | none | `ready_with_carried_actions` | carried action |
| `carbon_equivalent_exceeds` | `RLR-04 = fail` | `not_ready_to_issue` | finding |

## Provisional Ruling

Ruling: absent evidence is `insufficient_data` with an information request; present-but-nonconforming evidence is `fail`. In this anchor, a missing heat number in the application schedule blocks the compliance check for that application row and flips `RLR-04` to `insufficient_data`. A recomputed CEV exceedance from printed chemistry flips `RLR-04` to `fail`.

Alternative an SME may prefer: treat a missing heat number as an identity/traceability defect on `RLR-02` or source-status defect on `RLR-06` before compliance adequacy.

If reversed: change the missing-data variant's primary matrix row and verifier localization expectations. The current `RLR-04` route should remain available if the SME agrees that the missing value blocks compliance adequacy but wants identity/source-status raised first.

Valid-certificate-wrong-application remains reserved for the later `SSC-15-LH-03` build, per the first-wave plan.

## Validation

Targeted tests:

- `uv run pytest tests/templates/test_product_submittal_compliance_issue_review_package.py -q`
- Result: `35 passed`.

Lint/format:

- `uv run ruff check src/aec_bench/templates/builtin/mechanical/product_submittal_compliance_issue_review_package tests/templates/test_product_submittal_compliance_issue_review_package.py`
- `uv run ruff format --check src/aec_bench/templates/builtin/mechanical/product_submittal_compliance_issue_review_package tests/templates/test_product_submittal_compliance_issue_review_package.py`
- Result: all checks passed; four files already formatted.

Generated-instance validation:

- Command: `uv run aec-bench generate task product-submittal-compliance-issue-review-package --instances 8 --difficulty medium --seed 2026071501 --output /private/tmp/aec-bench-ssc15-anchor-e2e`
- Variant coverage: 6 variants in 8 instances.
- Validator result: 8/8 generated instances passed.
- Golden pass scores: 1.000 on all 8.
- Fluent unsafe memo scores: 0.320 to 0.400.

Variant-blindness self-check:

- `instruction.md` and `system_prompt.md` do not contain packet variant names or planted-defect tokens.
- The prompt states only generic review workflow, boundary rules, output schema, exact key names, and missing-value behavior.
- Source-diff audit showed each defect variant changes only the intended source file.

## Probe Ledger

Probe adapter: `pydantic_ai`.

| Variant | Model | Reward | Main losses | Triage classification |
|---|---|---:|---|---|
| `carbon_equivalent_exceeds` | Haiku `au.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.80 | `RLR-03`, `RLR-07`, `RLR-08`, failed-finding linkage, claim boundary. Evidence recomputation succeeded. | `model-evidence` |
| `carbon_equivalent_exceeds` | Sonnet `au.anthropic.claude-sonnet-4-6` | 0.97 | `RLR-03` only. Evidence, linkage, readiness, and claim boundary passed. | `model-evidence` |
| `missing_heat_number` | Haiku `au.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.68 | `RLR-02`, `RLR-04`, `RLR-06`, `RLR-07`, `RLR-08`, failed-finding linkage, required-register linkage, claim boundary. Evidence gate passed for the present certificate-coverage key. | `model-evidence` |
| `missing_heat_number` | Sonnet `au.anthropic.claude-sonnet-4-6` | 0.85 | `RLR-02`, `RLR-04`, `RLR-06`, required-register linkage. Evidence, readiness, and claim boundary passed. | `model-evidence` |

Probe artifact root: `/private/tmp/aec-bench-ssc15-anchor-probes`.

No probe loss is classified as a suspected contract defect in this pass. The missing-heat losses are retained as useful evidence that models may localize absent heat evidence to identity/source-status rather than the provisional compliance-adequacy branch.

## Non-Claims

This template is a task-owned synthetic review environment built under a provisional SSC-15 engineering ruling. It does not claim SME endorsement, accepted project evidence, authority approval, source-pack hardening, full standards compliance, executable-verifier readiness, or benchmark readiness.
