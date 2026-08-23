# Learning Studies Lifecycle Vertical Slice (L01) Review

| Field | Value |
| --- | --- |
| Class | Decision |
| Status | Current |
| Date | 2026-09-19 |
| Scope | Lifecycle-backed Learning Studies vertical slice: LS-06A, LS-06B, LS-06C, and L01 drainage staged evidence transfer |

## 1. Decision and outcome class

**Outcome class: Pass, with one bounded revision landed as part of this
review.**

The lifecycle Learning Studies adapter (LS-06A), the cross-lifecycle learner
state and read-only context seam (LS-06B), and the terminal feedback and
outcome projection layer plus the L01 study (LS-06C) are each demonstrated,
internally consistent with the programme charter and Gate A decision, and
pass their required test matrices. One test-coverage gap was found and closed
during this review (an explicit cross-arm feedback-restore rejection test for
the lifecycle adapter); no production code defect was found. No common
Learning Studies contract changed.

This review is an **architecture-side** review. It does not include the
independent drainage-domain relation review flagged as still pending in
`docs/research/learning-studies/l01-deterministic-evidence.md` and required
before any L01 result is promoted to a causal claim.

## 2. Implementation summary

- `src/aec_bench/experimentation/learning_studies/lifecycles.py` (707 lines):
  the adapter-owned lifecycle Learning Studies binding. Resolves
  `lifecycle/<template_id>/<variant_id>` (or `lifecycle/<template_id>` for
  no-variant templates) task targets, fixes the `fresh_context` +
  `artifact_memory` execution condition, implements `reset` and
  `structured-memory` treatments over the existing `run_lifecycle_trial()`
  pipeline, and implements experience/feedback/consolidation/restore
  operations with copy-on-write state handles and cross-arm isolation checks.
- `src/aec_bench/experimentation/learning_studies/lifecycle_learning_state.py`
  (276 lines): validates the `memory/` + `feedback/` learner-state tree
  (size, type, symlink, and case-collision checks) and builds/validates the
  byte-identical read-only context projection copied into each experience.
- `src/aec_bench/harness/lifecycle_local.py` (+67/-4 lines): adds one optional
  parameter, `read_only_context_root: Path | None = None`, threaded through
  `run_local_lifecycle`, both session runners, `EvidenceLifecycleWorkspaceTool`,
  and the episode environment builder. Existing callers that omit it are
  unaffected. Exposes a synthetic `learner_context/` root in workspace
  listings only when present, with symlink/traversal/absolute-path rejection
  and no host-path disclosure in errors, plus fixed policy prose stating the
  context is not task evidence and cannot be modified.
- `src/aec_bench/lifecycles/stormwater_design/drainage_learning.py`
  (231 lines): task-owned. Projects a bounded public feedback view
  (`drainage_staged_review_feedback`) from a completed acquisition
  `TrialRecord` with an explicit field allowlist, and reads gate scores
  (`drainage_gate_score`) for outcome projections. Contains no
  Learning Studies imports.
- `src/aec_bench/experimentation/learning_studies/l01_drainage.py`
  (512 lines): composes the L01 protocol (cold-reset / reset-after-acquisition
  / structured-memory arms), runs it end to end, and derives truthful
  `AssessmentArmEvidence` (`arm_isolated`, `lineage_complete`,
  `probe_feedback_hidden`, `probe_state_discarded`,
  `hidden_evaluation_leaked`) from real persisted transition, feedback, and
  state records — never defaulted.
- `src/aec_bench/experimentation/learning_studies/protocols/l01-drainage-staged-evidence-transfer/`:
  `study.toml` (byte-identical to the illustrative example) and `family.toml`
  (paraphrased but semantically identical prose), loaded through the existing
  `protocol_collection` mechanism.
- Documentation: `docs/ARCHITECTURE.md`, `docs/README.md`,
  `docs/research/learning-studies/programme.md`, and the new
  `docs/research/learning-studies/l01-deterministic-evidence.md` describe the
  seam and the deterministic proof; `tests/docs/test_documentation_ownership.py`
  registers the new research document.

No new dependency, registry, plugin layer, common enum, or common contract
field was added.

## 3. Study evidence summary

A fully deterministic, in-repository L01 run
(`test_deterministic_l01_runs_all_arms_and_builds_truthful_assessment_evidence`)
executes all three arms (5 trial records, 15 model calls) and produces:

- identical `initial_state_equivalence_id` across all arms (matched starting
  condition);
- identical `adapter_id` (`lifecycle-local:fresh_context:artifact_memory`)
  across all arms (matched execution condition);
- `arm_isolated`, `lineage_complete`, `probe_feedback_hidden`,
  `probe_state_discarded` all `True`, `hidden_evaluation_leaked` `False`, for
  every arm, derived from real persisted evidence;
- with `relations_reviewed=False`: every measurement `DESCRIPTIVE_ONLY`;
- with `relations_reviewed=True`: every declared treatment-vs-control pair
  becomes `CONTROLLED` with one included pair, zero exclusions, and a real
  `normalised_effect`; the `reset-after-acquisition` sham/order-effect control
  measurement stays `DESCRIPTIVE_ONLY` (it is not the declared relation), which
  is the expected result, not an undeclared order effect;
- when arm evidence is falsified in a test (`probe_state_discarded=False`,
  `hidden_evaluation_leaked=True`), every affected measurement correctly
  degrades to `INVALID` — proving the assessment layer actually consumes this
  evidence rather than trusting caller-declared flags.

The structured-memory arm's probe reads context exclusively from consolidated
memory (`drainage-review-strategy.md`), identically across all three fresh
checkpoint sessions; the probe's own candidate state directory does not
persist (`states/structured-probe` absent); the released feedback artifact
matches the one persisted by the common feedback-artifact store byte-for-byte.

This is consistent with, and supersedes for architecture purposes, the
narrative already recorded in
`docs/research/learning-studies/l01-deterministic-evidence.md`.

## 4. Field-by-field decisions

| Concept | Current owner | Real L01 use | Decision | Rationale | Follow-up |
|---|---|---|---|---|---|
| lifecycle task-ID helper | adapter | exact target resolution | KEEP ADAPTER-LOCAL | Deterministic, safe parsing; rejects `default` alias; reuses `lifecycle_template_ids()`/`lifecycle_variant_ids()` | none |
| lifecycle target value | adapter | compile/execute | KEEP ADAPTER-LOCAL | Reuses pre-existing `run_lifecycle_trial()`; no duplicate compile/execute/verify path introduced | none |
| execution-condition value | adapter | matched probe | KEEP ADAPTER-LOCAL | Fixed per binding (`fresh_context`+`artifact_memory`); encoded in `adapter_id`; proven to match across all three L01 arms | revisit only if a later study needs per-experience conditions |
| reset treatment | adapter | cold and sham control | KEEP ADAPTER-LOCAL | Carries no task output/feedback into state; rejects `release_feedback`/`consolidate` calls; `reset-after-acquisition` independently resets | none |
| structured-memory treatment | adapter | exposed arm | KEEP ADAPTER-LOCAL | Requires explicit feedback release and consolidation before probe; cannot mutate memory from lifecycle execution | none |
| memory root | adapter | probe context | KEEP ADAPTER-LOCAL | Demonstrated: consolidated memory alone reaches the probe context, byte-identical across repeated fresh sessions | none |
| feedback root | adapter | resume/consolidation | KEEP ADAPTER-LOCAL | Demonstrated materially: resume restores exact feedback bytes without rerunning the projector | none |
| read-only context parameter | harness | external context | KEEP EXECUTION-LOCAL | Generic, Learning-Studies-neutral optional parameter; existing callers unaffected by default `None` | none |
| synthetic `learner_context/` root | harness | model retrieval | KEEP EXECUTION-LOCAL | Additive-only in listings; absent when parameter is `None`; proven independent of visibility policy | none |
| context policy text | harness | authority boundary | KEEP EXECUTION-LOCAL | Fixed prose, no Learning-Studies identifiers (arm/state/treatment/probe) leak into the harness prompt | none |
| context projection copy | adapter | immutability | KEEP ADAPTER-LOCAL | Byte-compared before/after every execution; proven read-only via unsafe-path/symlink rejection tests | none |
| feedback projector | drainage owner | teaching feedback | KEEP TASK-OWNED | Strict allowlist; proven to exclude hidden evaluator detail, raw failures, gold submissions, and host paths | none |
| generic terminal projector | adapter/task owner | optional | NOT INTRODUCED | No second study reuses a generic terminal projector yet; introducing one now would be speculative | reconsider only if L02 needs the same shape |
| gate projection helpers | drainage owner/glue | assessment | KEEP TASK-OWNED | `drainage_gate_score` reads existing lifecycle gate output; missing/malformed evidence returns ineligible, never `0.0` | none |
| consolidation context | adapter | memory update | KEEP ADAPTER-LOCAL | Restricted to writing only under `memory_root`; feedback passed read-only | none |
| size limits | adapter | safety | KEEP ADAPTER-LOCAL | Enforced in `lifecycle_learning_state.py`; observed state size well under the enforced ceiling (single-digit KB range) | none |
| adapter ID convention | runner | comparison matching | KEEP ADAPTER-LOCAL | `lifecycle-local:<mode>:<visibility>` proven sufficient for matched-probe validity in assessment | none |

**Common contract fields changed: none.**

## 5. Common-substrate decision

No common Learning Studies contract, enum, channel, registry, phase, or
provider field was added or changed. `git status` against this branch's
merge base shows zero modifications under `src/aec_bench/contracts/`,
`src/aec_bench/experimentation/learning_studies/{planning,runtime,assessment,
recording,resume,protocol_collection}.py`. `TrialRecord` is byte-for-byte
unchanged. This matches the Review Area A default decision exactly: no
scenario in this tranche required a common substrate change, and none is
proposed.

## 6. Adapter and harness decisions

- The adapter (`lifecycles.py`, `lifecycle_learning_state.py`) owns lifecycle
  target identity, execution condition fixing, treatment semantics, learner
  state tree shape and validation, and context-projection immutability
  proofs. This is correctly adapter-local per Review Area B/C/E/F.
- The harness (`lifecycle_local.py`) owns only the generic,
  Learning-Studies-neutral `read_only_context_root` seam: an optional
  parameter, a synthetic listing entry, path confinement, and fixed policy
  prose. It has no knowledge of arms, treatments, states, or probes (verified
  directly: `test_workspace_policy_labels_context_as_non_authoritative`
  asserts none of `arm_id`, `state_id`, `treatment_id`, `probe` appear in the
  harness-composed prompt). This matches Review Area D exactly, including
  every block condition (no hidden-path visibility, no writability, no
  evidence conflation, no verifier access, no behavior change when context is
  absent) being explicitly tested and passing.

## 7. Task-evidence decision

Existing drainage lifecycle gates (`staged_disclosure`, `finding_continuity`,
`closure_evidence`, `claim_boundary`) plus the canonical lifecycle reward were
sufficient to answer L01; no new lifecycle-owned evidence design (LS-07B) was
required. Own checkpoint submissions are read directly from persisted
lifecycle state by the existing `verify_drainage_model_lifecycle` gate
machinery; no additional task-owned boundary projection was needed for this
study.

## 8. Deletions or simplifications required

None found. The implementation is already close to minimal for its scope:
one adapter module, one state-tree module, a narrow non-invasive harness
diff, and one task-owned feedback/projection module. No compatibility alias,
no unused public export, and no duplicated safe-tree/path-confinement logic
was found (the context-projection helpers in `lifecycle_learning_state.py`
are the single implementation reused by both the adapter and its tests). One
test-matrix gap was closed as part of this review (see §10); no other change
is recommended before L02.

## 9. Precise input requirements for L02

L02 (or any further lifecycle study) can proceed using, unchanged:

- the `lifecycle/<template_id>/<variant_id>` task-ID convention and
  `resolve_lifecycle_learning_target`;
- the fixed `fresh_context` + `artifact_memory` execution condition pattern
  (a new study may choose a different fixed condition per binding, but should
  continue to fix it per binding rather than per experience, absent new
  evidence);
- the `reset` / `structured-memory` treatment pair (raw-history is
  deliberately **not** introduced yet — Review Area F requires it to be
  designed explicitly given A02's evidence that it is a scientifically
  meaningful, potentially harmful treatment, not a default continuity mode);
- the `memory/` + `feedback/` learner-state shape, its validation, and the
  read-only context seam, all unchanged;
- task owners must supply their own feedback projector and outcome
  projections, following the same allowlist-and-ineligibility discipline
  demonstrated by `drainage_learning.py`.

## 10. Test-matrix gap closed during this review

`tests/experimentation/learning_studies/test_lifecycle_memory.py` had
implicit but not explicit coverage of "arm A cannot restore arm B feedback"
for the lifecycle adapter (the artifact-task adapter had an equivalent
dedicated test; the lifecycle adapter's structurally identical guard clause
in `restore_feedback` did not). Added
`test_restore_feedback_rejects_a_record_from_another_arm`, which constructs a
`FeedbackReleaseRecord` for one arm and asserts `restore_feedback` raises
`cross-arm-path-detected` when given another arm's restored state. No
production code changed; the existing guard clause already behaved
correctly.

## 11. Whether LS-07B is triggered

**No.** L01's exact interpretation was fully available from existing gates,
the canonical lifecycle reward, and lifecycle session/submission evidence.
No missing quantity was identified that would require a new lifecycle-owner
evidence design.

## 12. Whether the team may proceed immediately or must land a correction PR

The one gap found (§10) has already been landed as part of this review
(committed alongside the reviewed code, not deferred). No further correction
PR is required before proceeding.

## Recommendation

```text
PROCEED TO L02
```

Next concrete document: the detailed L02 study design (per the tranche
README's numbering, the next `LS-0x`/`L02-*` PRD), which should explicitly
scope whether and how a `raw-history` treatment is introduced, per Review
Area F. Independent domain review of the drainage staged-evidence relation
(flagged in `docs/research/learning-studies/l01-deterministic-evidence.md`)
remains a separate, still-pending prerequisite before any L01 result is used
as a causal scientific claim; it does not block starting L02 design work.
