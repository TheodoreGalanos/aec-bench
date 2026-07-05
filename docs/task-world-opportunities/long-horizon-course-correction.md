# ABOUTME: Records the 2026-07-05 course-correction review of the long-horizon task stream.
# ABOUTME: Freezes product-family expansion and defines the review-first implementation plan and acceptance criteria.

# Long-Horizon Course Correction

Review date: 2026-07-05

This document records an honest review of the long-horizon task-construction stream and the corrective plan agreed from it. It is the reference for why product-family expansion is frozen and what "done" means for the next runnable artifacts.

## Verdict

The research and design layer is genuinely good: the diagnosis, the compiler boundary, and the review-loop insight are all correct. But the runnable artifacts do not implement the thesis. The 150-template coverage push produced wide, shallow, saturated-at-birth calculation prompts, while the actual long-horizon architecture (`CompositeTaskWorldTemplate`) sits mostly unused. As of this review, the project has excellent documentation for a benchmark that does not exist yet, plus 150 templates for a benchmark it already had.

## What Is Load-Bearing And Right

- The thesis in [long-horizon-task-research-report.md](long-horizon-task-research-report.md): difficulty from preserving engineering meaning across time — source extraction, branch discipline, handoff integrity, contradictions. This is the correct differentiator against generic agent benchmarks.
- The compiler boundary in [long-horizon-methodology.md](long-horizon-methodology.md): composite templates as an authoring layer over `TaskWorldProfile`, not a parallel runtime.
- The review-loop lesson in [real-world-grounding/review-loop-long-horizon-lessons.md](real-world-grounding/review-loop-long-horizon-lessons.md): `[P]/[F]/[N/A]/[ID]` review is what senior AEC work actually looks like, makes missing data and overclaiming first-class gradable outcomes, and is the only design that can distinguish a responsible reviewer from a fluent memo writer.
- The non-claims discipline: every doc honestly separates synthetic from hardened.

## Load-Bearing Problems

1. **The runnable "long-horizon" templates are single-turn formula worksheets.** In the SSC-01 flagship (`road-low-point-resilience-package`), every input value is inline in one prompt table and every formula is given in order, including algebraic rearrangements. There is no source pack to open, no method to select, no branch to decide, no contradiction to notice. An agent can solve it in one response with zero tool calls. The horizon is a longer prompt, not a longer task.

2. **Difficulty was tuned away at creation time.** The runnable-template deltas document the process: SSC-07 went 0.79 → 1.0 by pinning the bearing-factor convention and water-table correction; SSC-14 went 0.89 → 1.0 by hardcoding Nc/Nq/Ngamma in the prompt; SSC-01 went 0.76 → 1.0 by spelling out Manning's n exactly. Those ambiguities are the long-horizon content — real engineers get paid to resolve exactly those. Each was deleted from the task instead of promoted to a graded branch decision. "Done" was defined as both Sonnet and Haiku reaching reward `1.0`, which guarantees every template ships with zero headroom.

3. **143/150 package templates have every parameter fixed (`min == max`).** These are single frozen instances with a constant answer key: no instance distribution, no pass^k reliability measurement, trivial contamination once published, and no way to generate negative variants.

4. **Everything is happy-path.** The instruction tells the model the conclusion ("state that the baseline source pack passes"); `overall_pass_score` is a gimme key. No missing cabinet level, no stale HGL revision, no datum mismatch — the exact negative cases the review-first redesign enumerates. A verifier that only ever sees passing packages cannot measure the behavior that matters.

5. **The verifier is answer-grading, not state-grading.** The generated `verify.py` extracts the last fenced JSON block and does per-key `math.isclose` with flat partial credit. Keys are strongly correlated (margins are subtractions from upstream keys), so partial credit double-counts single computations; nothing checks provenance, handoff consistency, or evidence; downstream credit is not conditioned on upstream consistency, so plausible arithmetic with broken engineering continuity scores fine.

6. **The long-horizon architecture and the coverage push diverged.** `CompositeTaskWorldTemplate` — the object carrying `source_artifacts`, `handoffs`, `branch_decisions`, `verifier_gates` — has 11 catalogue entries, and exactly one of the 19 SSC baselines went through it. The other 18 baselines and ~131 expansion products were built as plain builtin formula templates, bypassing the composite contract. The materializer verifies hand-authored example coherence, not agent behavior; there are still no stage runners, no handoff ledger, no branch ledger.

7. **The 8/8 coverage metric optimized authoring throughput, not environment quality.** 133 of 152 product families were validated only by "generated golden verifier reward 1.0" — the engine's own answer passing the engine's own verifier, a self-consistency tautology with no model evidence.

## Corrective Plan

1. **Freeze expansion.** No ninth product family, no SSC-21, no further coverage rows. The marginal clone contributes approximately nothing to the main goal. This freeze holds until at least one review-first environment exists and has model-run evidence under the inverted acceptance criteria below.

2. **Build the SSC-01 review-first task as the first real environment.** [real-world-grounding/ssc01-lh01-review-first-redesign.md](real-world-grounding/ssc01-lh01-review-first-redesign.md) already specifies the verifier shape, negative cases, and output contract. Implement it as a runnable environment, keeping the composite authoring layer coherent.

3. **Sources are files, not prompt tables.** The document register, drainage tables, cabinet layout, criteria memo, and review comments are separate files in the sandbox — including, per variant, a stale revision, a missing field, or a contradiction. The agent must inventory, open, extract, and reconcile them.

4. **Withhold the formula sheet; grade the branch.** Conventions and method choices are not pinned in the prompt. Ambiguity resolution (which storm case, which datum, which revision governs) is explicit graded state, not a bug to be removed.

5. **Inverted acceptance criteria.** A review-first task instance is acceptable when all of the following hold:
   - the golden structured answer scores `1.0` on its own verifier (sanity floor);
   - across the variant distribution, at least one strong baseline model scores below `1.0` — baseline models at ceiling on all variants is a difficulty defect, not a done-marker;
   - every sub-ceiling run localizes: the verifier details identify which review item, status, linkage, or consistency rule failed;
   - negative variants flip the expected gold statuses (a missing source flips the affected item to `insufficient data`, a stale revision flips identity/basis items to `fail`, and the readiness decision follows);
   - the verifier awards no credit for readiness decisions inconsistent with unresolved findings.

6. **Stage-gated, provenance-aware reward.** Downstream keys earn credit only when consistent with upstream state. Correlated derived keys are not double-counted. Statuses, findings-to-action linkage, missing-data naming, scope reasons for N/A, and claim-boundary compliance are scored as structured state. Parameters are sampled from ranges (`min < max` wherever engineering sense allows), enabling pass^k over the instance distribution.

## Implementation State (2026-07-05)

The review-first environment is implemented as `road-low-point-issue-review-package` (civil / road-review, `no-tool`):

- Sources are files: seven generated documents under `/workspace/sources/` (document register, road geometry, drainage package, field equipment, power/comms, traffic operations, criteria and comments). The instruction carries no numeric values; methods are source-owned in the criteria memo.
- Eight hidden packet variants (`clean`, `missing_cabinet_level`, `stale_hgl_revision`, `chainage_datum_mismatch`, `scenario_copy_forward`, `open_critical_comment`, `minor_open_comment_carried`, `freeboard_deficient`) flip gold review statuses and the readiness decision deterministically. Derivation margins are hidden parameters, so criteria values never leak defect presence.
- Parameters sample from real ranges (no `min == max`), quantized so the source files print exactly the values the engine used. A closure test recomputes all gold evidence from the rendered files alone with independently written formulas.
- The custom verifier is stage-gated: matrix statuses (0.30, evidence-gated), recomputed evidence (0.20), findings/request/carried-action linkage (0.20), readiness (0.20, gated on evidence and self-consistency), identity ledger and claim boundary (0.10). Details localize failures per gate and per item.
- The fluent-unsafe adversary (all-pass matrix, `ready_to_issue`, no evidence, approval claims) is the shipped `golden_fail` fixture; it scores 0.28-0.37 across variants.
- Scaffolder gained four additive template hooks: `build_sources`, `build_golden_pass`, `build_golden_fail`, a template-owned `system_prompt.md`, and `tests/instance.json` for custom verifiers. Existing templates are unaffected.
- Evidence: 33 template tests plus 5 hook tests pass; 8/8 CLI-generated instances pass `aec-bench task validate` with golden pass 1.000 and golden fail at or below 0.37, covering five distinct variants in one seed batch.

Still pending for the `SSC-01-LH-01` reference product itself: model-run evidence under the inverted acceptance criteria (`aec-bench run-local <instance> -m <model> --adapter pydantic_ai` or the current equivalent adapter), and any remaining composite-catalogue authoring cleanup.

Separate cluster-level update: an initial post-cleanup SSC-01 probe packet now exists for `SSC-01-LH-03`, `SSC-01-LH-07`, and `SSC-01-LH-08`. Five fresh variant-blind runs across Haiku and Sonnet scored between `0.75` and `0.95`, restoring non-saturated diagnostic headroom. This is recorded in `real-world-grounding/ssc01-review-first-conversion-plan.md` and Ara-lite `C155` / `E149` / `EV1379` / `N298`; it is not broad variant-distribution evidence or benchmark readiness.

Scaling this shape across the remaining SSC notes is specified in [real-world-grounding/review-first-authoring-guide.md](real-world-grounding/review-first-authoring-guide.md): the load-bearing invariants, file recipes, verifier contract, TDD set, per-SSC adaptation table, and the acceptance checklist authoring agents must satisfy.

The first cluster-level application plan is [real-world-grounding/ssc01-review-first-conversion-plan.md](real-world-grounding/ssc01-review-first-conversion-plan.md). It maps all eight existing `SSC-01` products into review-first candidates, preserves the original formula-closure templates as baselines, and now tracks five additive review-first companions after the `SSC-01-LH-01` reference task. `SSC-01-LH-02` is implemented as `intersection-signal-safety-issue-review-package`; `SSC-01-LH-03` is implemented as `road-visual-operations-issue-review-package`; `SSC-01-LH-04` is implemented as `emergency-detour-device-issue-review-package`; `SSC-01-LH-05` is implemented as `bus-priority-cabinet-issue-review-package`; `SSC-01-LH-08` is implemented as `corridor-comment-response-issue-review-package`. The implemented companions have template/generation evidence and composite-catalogue alignment, while broad model-run evidence remains incomplete.

The `SSC-01-LH-04` implementation keeps the original `emergency-detour-roadside-device-continuity-package` formula artifact and adds a separate no-tool issue-readiness environment over seven source files: document register, detour plan, message library, device inventory, communications topology, power-continuity schedule, and criteria/comments. It tests missing closure duration as RLR-04 `insufficient_data`, battery runtime deficiency as RLR-04 `fail`, stale detour-plan revision as RLR-03, device identity mismatch as RLR-02, copied scenario as RLR-05, open critical comment as RLR-07, and carried minor comment as `ready_with_carried_actions`. Focused tests pass, an 8-instance generated batch validates with golden pass `1.000` and fluent-unsafe fail `0.320` to `0.400`, and the composite package-contract materialize/verify path passes with score `1.0`. It still does not claim model-run evidence, source-pack hardening, real MUTCD/NTCIP/export parsing, accepted project evidence, authority approval, full standards compliance, generated benchmark readiness, or benchmark readiness.

The `SSC-01-LH-05` implementation keeps the original `bus-priority-signal-cabinet-load-package` formula artifact and adds a separate no-tool issue-readiness environment over eight source files: document register, bus-priority operations plan, signal phasing/timing sheet, detector/controller schedule, cabinet load schedule, feeder/backup schedule, owner operations criterion, and criteria/comments. It tests missing cabinet capacity as RLR-04 `insufficient_data`, cabinet load exceeded as RLR-04 `fail`, stale signal timing revision as RLR-03, detector/controller mismatch as RLR-02, copied bus-priority scenario as RLR-05, open critical comment as RLR-07, and carried minor comment as `ready_with_carried_actions`. Focused tests pass, an 8-instance generated batch validates with golden pass `1.000` and fluent-unsafe fail `0.320` to `0.400`, and the composite package-contract materialize/verify path passes with score `1.0`. It still does not claim model-run evidence, source-pack hardening, real controller/timing/cabinet export parsing, accepted project evidence, authority approval, full standards compliance, generated benchmark readiness, or benchmark readiness.

Initial Haiku runs on `SSC-01-LH-08` were useful diagnostics rather than readiness evidence. They exposed concrete gaps that are now recorded in the authoring guide: local `run-local` needed to mirror `environment/sources/*` to `<workspace>/sources/*`; overlapping review-matrix items need explicit boundary semantics; and structured output keys need exact-name reinforcement, because otherwise models invent helpful suffixed evidence keys that the verifier intentionally ignores. After source mirroring was fixed, Haiku read the correct packet and found the copied VMS speed, but cascaded one intended RLR-05 defect into adjacent matrix items. The task now implements primary/collateral boundary rules in its instruction, system prompt, and source-owned criteria memo, with tests proving the generated packet carries those rules. Two post-boundary runs improved localization (`0.81`, then `0.85`) and narrowed the remaining issue to RLR-06 cascade plus exact evidence-key naming. The current v3 artifact clarifies RLR-06 non-cascade behavior and exact `computed_evidence` keys; a single v3 Haiku run on `scenario_copy_forward` scored `1.00` with full matrix, evidence, linkage, readiness, identity, and claim-boundary credit. This proves that one subtle variant is now contract-clear, but does not claim benchmark readiness or full variant-distribution evidence.

## Non-Claims

This review does not claim the 150 synthetic templates are worthless — they remain valid formula-closure content at the difficulty tier the original benchmark already served. It does not claim source-pack hardening, accepted project evidence, or benchmark readiness for anything described here — including the review-first implementation above, which remains a task-owned synthetic environment until model-run evidence and a source-pack hardening pass exist. It claims only that the long-horizon label is not yet earned without those, and defines what earning it requires.
