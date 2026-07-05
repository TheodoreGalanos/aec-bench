# ABOUTME: Records the SSC-01-LH-06 review-first companion design before implementation.
# ABOUTME: Preserves the existing formula template while defining the source packet, variants, evidence, and verifier contract.

# SSC-01-LH-06 Review-First Design

This note applies the review-first authoring guide to `SSC-01-LH-06: Culvert, Driveway Access, And Safety Continuity Package`.

It preserves the existing formula-closure template, `culvert-driveway-access-safety-continuity-package`, as the math/source baseline. The additive review-first companion is `driveway-access-safety-issue-review-package`. This design and implementation record does not replace the formula template, add model-run evidence, claim source-pack hardening, or claim benchmark readiness.

## Baseline To Preserve

Existing formula template:

```text
culvert-driveway-access-safety-continuity-package
```

Current shape:

```text
driveway profile levels and length
  -> driveway grade and grade margin
  -> circular full-pipe culvert capacity and capacity margin
  -> headwater level and freeboard margin
  -> roadway spread margin
  -> grade-adjusted sight-distance margin
  -> synthetic pass score
```

That template is a useful saved calculation artifact. The review-first companion should not overwrite it. The companion should change the job from "calculate the driveway access safety memo" to "review whether the driveway/culvert access package is ready to issue."

## Review-First Companion

Human title:

```text
Review the driveway access and culvert safety package for issue
```

Proposed template name:

```text
driveway-access-safety-issue-review-package
```

Proposed directory:

```text
src/aec_bench/templates/builtin/civil/driveway_access_safety_issue_review_package/
```

Proposed category:

```text
road-review
```

The category stays aligned with the other SSC-01 review-first companions.

Implementation status:

```text
runnable synthetic review-first companion implemented
```

## Scene And Object IDs

Reuse the SSC-01-LH-06 object family so the review-first task remains connected to the formula baseline:

| Object | Suggested ID | Role |
| --- | --- | --- |
| Access profile | `ACCESS-SSC01-006` | Driveway/local-road access levels, chainage, length, grade, and tie-in basis. |
| Local road edge | `ROAD-SSC01-006` | Road edge level, shoulder/traffic-lane boundary, and spread limit location. |
| Culvert crossing | `CULV-SSC01-006` | Diameter, roughness, slope, design flow, and drainage object identity. |
| Tailwater and headwater table | `TAIL-SSC01-006` | Tailwater level, base headwater depth allowance, and loss factor. |
| Sight-distance basis | `SIGHT-SSC01-006` | Access speed, reaction time, friction, signed grade, and available sight distance. |
| Access vehicle/storm scenario | `OPS-SSC01-006` | Vehicle class, selected storm/access case, and issue-readiness basis. |
| Access criteria memo | `MEMO-SSC01-006` | Allowable grade, minimum freeboard, allowable spread, and sight-distance criteria. |
| Review comments | `CRIT-SSC01-006` | Review comments, boundary rules, and claim boundary. |

## Source Packet

The review-first task should generate eight source files under `/workspace/sources/`:

| File | Source role | Contents |
| --- | --- | --- |
| `document-register.md` | Register | Document IDs, revisions, status, discipline owner, and current/issued status. |
| `access-profile.md` | Primary access evidence | Driveway chainage, low/high levels, grade length, access scenario, and road-edge object link. |
| `culvert-drainage-schedule.md` | Drainage evidence | Culvert diameter, Manning roughness, slope, design flow, claimed capacity, and object identity. |
| `surface-tailwater-table.md` | Flood/access evidence | Tailwater level, headwater allowance, loss factor, road edge level, and claimed freeboard. |
| `roadway-spread-note.md` | Roadway drainage evidence | Gutter flow, cross slope, longitudinal slope, gutter roughness, allowable spread, and claimed spread. |
| `sight-distance-note.md` | Access safety evidence | Access speed, reaction time, friction, signed grade, available sight distance, and claimed sight-distance margin. |
| `owner-access-criterion.md` | Owner/operations criterion | Required vehicle/storm case, minimum freeboard, maximum grade, sight-distance basis, and issue-readiness rule. |
| `criteria-comments.md` | Criteria and review comments | Assessment bases, primary/collateral boundary rules, missing-data boundary rules, review comments, owners, and actions. |

Methods and conventions belong in `criteria-comments.md`, not the instruction. The instruction should only say that the packet is the source of truth.

## Review Matrix

Use the same nine review items:

| Item | SSC-01-LH-06 meaning |
| --- | --- |
| `RLR-01` | Packet completeness: all required access profile, culvert, tailwater, roadway spread, sight-distance, owner-criterion, and criteria files are present with IDs and revisions. |
| `RLR-02` | Object identity: access chainage, local road edge, culvert, tailwater table, sight-distance basis, and owner access case stay consistent. |
| `RLR-03` | Access/drainage basis: driveway grade, culvert capacity, and headwater level are traceable, current, and recomputable. |
| `RLR-04` | Access usability adequacy: grade, culvert capacity, and freeboard clear the source criteria for the same access point and storm/vehicle case. |
| `RLR-05` | Scenario consequence: the same access storm/vehicle case is used across access profile, culvert schedule, tailwater table, spread note, sight-distance note, and owner criterion. |
| `RLR-06` | Secondary safety resilience: roadway spread and sight-distance margins are source-backed and internally consistent with the access profile and road edge. |
| `RLR-07` | Comment and action closure: critical comments are closed or have named actions; minor comments may be carried with owner/action. |
| `RLR-08` | Readiness consistency: the final decision follows the review matrix, findings, information requests, and action register. |
| `RLR-09` | Claim boundary: the response avoids unsupported approval, compliance, source-hardening, executable-verifier, or benchmark-readiness claims. |

## Evidence Keys

Initial evidence keys for `compute()`:

| Key | Review role |
| --- | --- |
| `driveway_grade_percent` | RLR-03 access-profile recomputation. |
| `driveway_grade_margin_percent` | RLR-04 access-grade adequacy. |
| `culvert_capacity_m3_s` | RLR-03 culvert-capacity recomputation. |
| `culvert_capacity_margin_m3_s` | RLR-04 culvert-flow adequacy. |
| `headwater_level_m` | RLR-03 headwater recomputation. |
| `freeboard_m` | RLR-04 freeboard recomputation. |
| `freeboard_margin_m` | RLR-04 freeboard adequacy. |
| `roadway_spread_m` | RLR-06 roadway-spread recomputation. |
| `spread_margin_m` | RLR-06 spread adequacy. |
| `sight_distance_required_m` | RLR-06 sight-distance recomputation. |
| `sight_distance_margin_m` | RLR-06 sight-distance adequacy. |

The first implementation should use `access_freeboard_deficient` as the primary RLR-04 genuine-failure route because it ties the access profile, culvert/tailwater schedule, road edge, and storm/access case together. `sight_distance_deficient` remains a strong optional later route, but the first pass should avoid two overlapping access-safety failures.

## Variants

Use the eight-variant skeleton from the guide:

| Variant | Primary flip | Readiness | Required register behavior |
| --- | --- | --- | --- |
| `clean` | None | `ready_to_issue` | No findings, requests, or carried actions. |
| `missing_road_edge_level` | `RLR-04 -> insufficient_data` | `not_ready_to_issue` | One information request naming the missing road edge level in `ACCESS-SSC01-006` / `ROAD-SSC01-006`. |
| `stale_access_profile_revision` | `RLR-03 -> fail` | `not_ready_to_issue` | One finding against the stale access profile / driveway grade basis. |
| `culvert_chainage_mismatch` | `RLR-02 -> fail` | `not_ready_to_issue` | One finding where the culvert chainage differs between access profile and culvert/tailwater sources. |
| `scenario_copy_forward` | `RLR-05 -> fail` | `not_ready_to_issue` | One finding where the access storm/vehicle case is copied from another driveway or local road without a decision record. |
| `open_critical_comment` | `RLR-07 -> fail` | `not_ready_to_issue` | One finding for an open critical access/drainage/safety review comment without owner/action. |
| `minor_open_comment_carried` | None | `ready_with_carried_actions` | One carried action with owner and linked item. |
| `access_freeboard_deficient` | `RLR-04 -> fail` | `not_ready_to_issue` | One finding where recomputed road-edge freeboard is below the minimum freeboard, while the package mis-claims adequacy. |

Optional later variant:

```text
sight_distance_deficient
```

Keep it out of the first implementation unless freeboard proves too narrow. One implementation pass should not include both `access_freeboard_deficient` and `sight_distance_deficient` if that makes RLR-04/RLR-06 localization noisy.

## Boundary Rules

These rules should appear in the instruction, system prompt, and criteria source from the first implementation:

- Missing road edge level is an information-request case, not a known failed freeboard calculation. Set RLR-04 to `insufficient_data`, omit `freeboard_m` and `freeboard_margin_m` if they cannot be computed from packet values, and request the exact missing road edge level/source.
- Missing road edge level is a critical blocker. The readiness decision should be `not_ready_to_issue`, not `ready_with_carried_actions`; do not carry the missing road edge level as a normal action.
- A copied access storm/vehicle case belongs under RLR-05. Do not cascade it into RLR-02 if object IDs reconcile. Do not cascade it into RLR-03/RLR-04/RLR-06 when the grade, culvert, freeboard, spread, and sight-distance calculations are source-backed and internally consistent with their stated source values.
- A stale access profile revision belongs under RLR-03. Do not also fail RLR-04 if the adequacy checks are internally recomputable from current non-stale culvert, tailwater, road-edge, and criteria sources.
- A culvert chainage mismatch belongs under RLR-02. Do not also fail freeboard, spread, or sight distance unless the mismatch independently makes those source values unrecomputable.
- Every finding, information request, and action must name one exact RLR item. Do not write combined items such as `RLR-04/RLR-06`.
- RLR-08 is reviewer self-consistency, not package-readiness positivity.

## Derivation-Controlled Quantities

The review-first engine should not reuse the fixed min/max values from the formula template. It should sample realistic ranges and derive pass/fail margins:

- Quantize levels to `0.01 m`.
- Quantize lengths and sight distances to `0.1 m`.
- Quantize slopes and grades to `0.1 percent`.
- Quantize Manning roughness values to `0.001`.
- Quantize flows and culvert capacity to `0.01 m3/s`.
- Quantize freeboard criteria and margins to `0.01 m`.
- Quantize speeds to `1 km/h`, reaction time to `0.1 s`, and friction coefficient to `0.01`.

Derive these quantities from hidden margins:

- `driveway_high_level_m = driveway_low_level_m + driveway_length_m * target_driveway_grade_percent / 100` for pass variants.
- `allowable_driveway_grade_pct = ceil_to(abs(driveway_grade_percent) + driveway_grade_margin_percent, 0.1 percent)` for pass variants.
- `design_flow_m3_s = floor_to(culvert_capacity_m3_s - culvert_capacity_margin_m3_s, 0.01 m3/s)` for pass variants.
- `road_edge_level_m = headwater_level_m + minimum_freeboard_m + freeboard_margin_m` for pass variants.
- For `access_freeboard_deficient`, derive `road_edge_level_m = headwater_level_m + minimum_freeboard_m - freeboard_deficit_m` so `freeboard_margin_m` is negative after printed-value recomputation.
- `allowable_spread_m = ceil_to(roadway_spread_m + spread_margin_m, 0.1 m)` for pass variants.
- `available_sight_distance_m = ceil_to(sight_distance_required_m + sight_distance_margin_m, 0.1 m)` for pass variants.

The criteria source must state all unit conventions explicitly, including grade percent as level difference divided by length times 100, circular full-pipe Manning capacity, headwater as tailwater plus base depth plus ratio-squared loss allowance, triangular-gutter spread with SI coefficient `0.376`, speed conversion from km/h to m/s, signed access grade in the sight-distance denominator, and freeboard as road edge level minus headwater level. Do not leave conversion conventions implicit.

## Verifier Implications

Start from the existing custom verifier pattern and adapt only constants:

```text
ITEM_EVIDENCE = {
  "RLR-03": ["driveway_grade_percent", "culvert_capacity_m3_s", "headwater_level_m"],
  "RLR-04": ["driveway_grade_margin_percent", "culvert_capacity_margin_m3_s", "freeboard_m", "freeboard_margin_m"],
  "RLR-06": ["roadway_spread_m", "spread_margin_m", "sight_distance_required_m", "sight_distance_margin_m"],
}
```

Use `VARIANT_REQUEST_TOKENS` for `missing_road_edge_level`:

```text
("road", "edge", "level", "access-ssc01-006")
```

Use `REQUIRED_LEDGER_TOKENS`:

```text
access-ssc01-006, road-ssc01-006, culv-ssc01-006, tail-ssc01-006, sight-ssc01-006, ops-ssc01-006, memo-ssc01-006
```

## TDD Implementation Slice

The first implementation started with tests, not code:

1. Add `tests/templates/test_driveway_access_safety_issue_review_package.py` before creating the template; the initial red state should be the missing template directory.
2. Preserve `culvert-driveway-access-safety-continuity-package` unchanged as the formula/source baseline.
3. Assert `tool_mode = "no-tool"`, eight source files under `environment/sources/`, no generated calc script, and no engineering numbers in `instruction.md`.
4. Assert all eight variants map to exactly one primary RLR flip, with `missing_road_edge_level` producing RLR-04 `insufficient_data` and `access_freeboard_deficient` producing RLR-04 `fail`.
5. Add closure tests that reparse rendered sources and independently recompute driveway grade, culvert capacity, headwater, freeboard, roadway spread, and sight-distance evidence.
6. Add source-boundary tests for copied scenario, culvert chainage mismatch, stale access profile, and missing road edge level before running models.
7. Add the template to the composite catalogue only after focused tests, generated instance validation, and Ara capture.

## Implementation Outcome

`driveway-access-safety-issue-review-package` is now implemented as an additive no-tool built-in template under:

```text
src/aec_bench/templates/builtin/civil/driveway_access_safety_issue_review_package/
```

Implementation artifacts:

- `params.toml`: variable sampled parameters, eight packet variants, archetypes, difficulty presets, and review/evidence outputs.
- `engine.py`: source-pack rendering, quantized derivations, localized variant gold states, and golden pass/fail fixtures.
- `instruction.md` and `system_prompt.md`: source-packet review workflow, RLR matrix, missing-data boundary, primary/collateral boundary, exact evidence keys, and claim boundary.
- `verify.py`: custom matrix/evidence/linkage/readiness/identity-claims verifier.
- `tests/templates/test_driveway_access_safety_issue_review_package.py`: focused TDD coverage for discovery, parameter variation, variant gold states, source-pack IDs, missing-road-edge boundary, source-owned methods, source-only recomputation, scaffold layout, golden fixtures, verifier localization, evidence gating, and readiness anti-gaming.
- `src/aec_bench/task_world_templates/catalogue.py` and `tests/task_world_templates/test_products.py`: composite-catalogue entry and tests preserving `culvert-driveway-access-safety-continuity-package` as the formula/source reference.

Validation captured in `ara/evidence/logs/ssc01_lh06_review_first_companion_self_check.txt`:

```text
uv run pytest tests/templates/test_driveway_access_safety_issue_review_package.py tests/task_world_templates/test_products.py -q
38 failed, 4 passed
```

The initial red state was the expected missing template/catalogue entry.

```text
uv run pytest tests/templates/test_driveway_access_safety_issue_review_package.py tests/task_world_templates/test_products.py tests/templates/test_registry.py -q
65 passed
```

```text
uv run aec-bench generate task driveway-access-safety-issue-review-package --instances 8 --difficulty medium --seed 20260705 --output /private/tmp/aec-bench-ssc01-lh06-review-first-e2e
8 generated instances
```

The generated batch covered seven variants: `access_freeboard_deficient`, `clean`, `culvert_chainage_mismatch`, `minor_open_comment_carried`, `missing_road_edge_level`, `open_critical_comment`, and `scenario_copy_forward`. The `stale_access_profile_revision` variant is covered by focused tests but was not sampled in that seed batch.

All 8 generated instances validated with golden pass `1.000`, fluent-unsafe fail between `0.320` and `0.400`, and zero warnings. The first in-sandbox validation attempt hit a uv cache permission error on `~/.cache/uv/sdists-v6/.git`; rerunning the same validator outside the sandbox resolved the environment issue and produced the passing evidence.

```text
uv run aec-bench --json task composite-template materialize-example driveway-access-safety-issue-review-package --output /private/tmp/aec-bench-ssc01-lh06-issue-review-composite-example
overall: pass, score: 1.0, data_gap_count: 6
```

```text
uv run aec-bench --json task composite-template verify-example /private/tmp/aec-bench-ssc01-lh06-issue-review-composite-example
overall: pass, score: 1.0
```

## Non-Claims

This is a design and runnable synthetic implementation record for a task-owned review-first companion. It does not claim model-run evidence, real HEC-22/HDS-5/12d/OpenRoads/CAD/GIS export parsing, accepted project evidence, authority approval, source-pack hardening, full standards compliance, generated benchmark readiness, or benchmark readiness.
