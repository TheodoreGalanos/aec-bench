# Learning Studies Gate C

| Field | Value |
| --- | --- |
| Class | Decision |
| Status | Current |
| Date | 2026-08-26 |
| Scope | Dam-and-lifecycle-derived action/effect evidence; decides on `LearningUnitRef` / `EffectComparison` |

## Decision

Gate C passes with **zero common substrate changes**. The proposed
`LearningUnitRef` envelope, `EffectComparison` structure, and
action-attribution tagging from PRD LS-10 are each declined under the
promotion rule. Every LS-10 question resolves to "keep it where it already
lives" or "defer until real evidence demands it." No field is added to,
removed from, or moved between `src/aec_bench/contracts/learning_study.py`,
`learning_study_evidence.py`, `learning_study_assessment.py`, or
`learning_family.py`; no new common type is introduced; and the adapter,
lifecycle, and world modules remain non-communicating owners of their own
evidence shapes.

One concrete, documented, tested limitation —
`drainage_phase_completion()`'s reload-robustness gap — is the single
strongest candidate for a narrow common addition. This gate concludes that
it warrants a **targeted follow-up decision** (registering
`"lifecycle_learning_evidence"` in `ledger/reader.py`'s `_hydrate_extensions`
known-type map), but that this narrow fix does NOT justify introducing the
full `LearningUnitRef` envelope. The follow-up is recommended as a separate,
scoped PR, not built by this gate.

This decision authorises **Release D — persistent-world and pump
integration** (PRD LS-11/LS-12) to begin design against the substrate as
documented in Gate A, Gate B, and this record, unchanged.

## Evidence used

- `docs/adr/learning-studies-gate-a.md` (Gate A): artifact-derived substrate
  decision, promotion rule origin, adapter-pattern precedent.
- `docs/adr/learning-studies-gate-b.md` (Gate B): lifecycle-derived substrate
  decision, promotion rule reapplication, zero common changes, explicit
  non-inheritances for worlds.
- `docs/adr/learning-studies-lifecycle-l01-review.md` (L01 review):
  field-by-field common-substrate decision (§5), adapter-ownership split (§4,
  §6), zero common contract changes.
- `docs/research/learning-studies/w01-relation-domain-review.md` (W01
  relation review): initial REJECTED verdict, defect analysis (observation
  leakage, profile matching), post-fix re-review ACCEPTED verdict, five
  updated invariant verdicts, sequence-copy detectability evidence.
- `docs/research/learning-studies/programme.md`: PRD LS-10 charter text
  (verified at line 1876), PRD LS-08 promotion rule, PRD LS-09 scope.
- `src/aec_bench/contracts/trial_record.py`: `TrialExtensionRef` (line 320),
  `TrialRecord.extension_refs` (line 343), `attach_extension()` (line 416),
  `pending_extensions` property (line 523). Confirmed the generic extension
  mechanism required zero common contract changes across L01/L02/L03/W01/W02.
- `src/aec_bench/lifecycles/stormwater_design/drainage_learning.py`:
  `DrainagePhaseEvidence` (line 84), `DrainageLearningEvidence` (line 98),
  `extract_drainage_learning_evidence()` (line 105),
  `drainage_phase_completion()` (line 148), `_PHASE_EVIDENCE_EXTENSION_KIND =
  "lifecycle_learning_evidence"` (line 32).
- `src/aec_bench/lifecycles/structural_review/facade_submittal.py`:
  `FacadePhaseEvidence` (line 136), `FacadeLearningEvidence` (line 147),
  `extract_facade_learning_evidence()` (line 153). Confirmed structurally
  different field shape from drainage (drainage has bounded-count fields;
  facade has `evidence_refs_cited`, `metric_accuracy_pass`,
  `finding_continuity_pass`, `review_decision_correct`); no shared domain
  base class (both inherit only from generic `StrictModel`).
- `src/aec_bench/experimentation/learning_studies/phase_evidence.py`:
  `group_phase_evidence()` (line 22), `PHASE_EVIDENCE_KIND =
  "lifecycle_learning_evidence"` (line 12). Confirmed it reads ONLY the
  opaque `phase_id` field via raw JSON parsing (lines 40–45); never imports
  `DrainagePhaseEvidence`, `FacadePhaseEvidence`, or any typed model from
  either family. This is the closest existing structure to "referencing
  task-owned learning units without domain semantics" — and it lives entirely
  at the study/adapter layer, not the common contracts layer.
- `src/aec_bench/experimentation/learning_studies/lifecycles.py`:
  `attach_extension("lifecycle_learning_evidence", evidence)` (line 385) —
  the adapter attaches both drainage and facade evidence using the same
  `extension_kind` string, confirming the common hook is already an adapter
  convention, not a common contract type.
- `src/aec_bench/ledger/reader.py`: `_hydrate_extensions()` (line 110),
  `known` dict (lines 111–116). Confirmed `"lifecycle_learning_evidence"` is
  deliberately excluded — only `adaptation`, `lifecycle_execution`,
  `lifecycle_provenance`, and `meta_harness_provenance` are hydrated on
  reload.
- `src/aec_bench/worlds/monitoring/dam_seepage/world.py`: `SeepageAction`
  enum (line 42), `SeepageEvaluation` dataclass (line 136, fields:
  `assessment_submitted`, `selected_response`, `required_response`,
  `response_correct`, `all_scheduled_readings_reviewed`,
  `measurement_system_checked`, `latest_downstream_area_inspected`,
  `evidence_complete`, `successful`), `observe()` conditional evidence
  release, `evaluate()` (line 318).
- `src/aec_bench/worlds/monitoring/dam_seepage/dam_learning.py`:
  `dam_escalation_boundary_feedback()` (line 51) with `action_sequence` field
  (line 44), `dam_response_correct()` (line 139), `dam_evidence_complete()`
  (line 147), `dam_inappropriate_escalation()` (line 155). Confirmed all four
  are plain `Callable[[TrialRecord], float]` functions reading
  `TrialRecord.evaluation.breakdown` — a completely different mechanism from
  lifecycle phase evidence's typed-extension-artefact approach.
- `src/aec_bench/experimentation/learning_studies/dam_w01.py` and
  `dam_w02.py`: confirmed neither imports anything from lifecycle
  phase-evidence machinery (`phase_evidence.py`, `DrainageLearningEvidence`,
  `FacadeLearningEvidence`), and neither lifecycle module imports anything
  from the dam modules. Two fully independent implementations of loosely
  analogous ideas that have never shared one line of code.
- `src/aec_bench/experimentation/learning_studies/assessment.py`:
  `OutcomeProjection = Callable[[TrialRecord], ProjectionResult]` (line 60).
  Confirmed unchanged since Gate A and still sufficient across all W01/W02
  dam projections and all lifecycle projections.
- `src/aec_bench/contracts/learning_study.py`,
  `learning_study_evidence.py`, `learning_study_assessment.py`,
  `learning_family.py`: read directly to confirm no `LearningUnitRef`,
  `EffectComparison`, or action-attribution type exists anywhere in
  `src/aec_bench/contracts/`.

## Questions resolved (PRD LS-10)

### 1. The `LearningUnitRef` envelope

**No common `LearningUnitRef` envelope is added.**

The promotion rule (LS-08, reapplied identically by Gate B) requires either
(a) at least one artifact study AND one lifecycle study using a shared unit
concept, or (b) a demonstrated requirement from upcoming world evidence that
can be demonstrated against existing evidence. Neither condition is met:

- **Artifact studies have never used any phase/unit concept.** Release A's
  four protocols (A01–A04) used complete-trial outcomes exclusively. No
  artifact study has referenced a phase, checkpoint, decision, or sub-trial
  unit. This leg of the promotion rule therefore fails outright.

- **Lifecycle and world evidence use structurally independent, non-
  communicating implementations.** Lifecycle phase evidence exists in two
  families: `DrainagePhaseEvidence` (bounded-count fields:
  `evidence_requested`, `evidence_released`, `submissions_accepted`,
  `submissions_rejected`, `constraints_satisfied`, `rework_events`,
  `revisited_decisions`, `recovery_actions`) and `FacadePhaseEvidence`
  (boolean/count fields: `evidence_refs_cited`, `evidence_refs_expected`,
  `metric_accuracy_pass`, `finding_continuity_pass`,
  `review_decision_correct`). These share a `phase_id`/`checkpoint_ids`/
  `phase_outcome` structural triple but NO domain-specific base class (both
  inherit only from generic `StrictModel`). Dam action evidence, meanwhile,
  lives entirely inside `TrialRecord.evaluation.breakdown` as a plain dict,
  using no extension_refs mechanism at all. The dam's `action_sequence`
  field is read from the world evidence JSON file
  (`dam_learning.py:197–213`), not from any typed extension artefact. These
  three evidence shapes (drainage phases, facade phases, dam actions) share
  zero code, zero imports, and zero structural dependency.

- **The study-layer `group_phase_evidence()` already references phase IDs
  without domain semantics.** `phase_evidence.py` reads ONLY the opaque
  `phase_id` field via raw JSON parsing, never importing either family's
  typed model. This is exactly the "minimal common reference" PRD LS-10
  contemplates — and it works as adapter/study-owned glue, not a common
  contract type. Promoting it into `src/aec_bench/contracts/` would add
  structure that no consumer currently requires at the contract level.

- **The dam world studies (W01/W02) never use phase-like evidence.** Neither
  `dam_w01.py` nor `dam_w02.py` imports anything from lifecycle phase-
  evidence machinery. The dam projections (`dam_response_correct`,
  `dam_evidence_complete`, `dam_inappropriate_escalation`) read
  `evaluation.breakdown` directly. There is no convergence pressure.

### 2. `unit_kind` discriminated union (phase / decision / action / feedback event)

**No shared `unit_kind` discriminant is added.**

The two existing "phase"-like implementations (drainage and facade) and the
"action"-like dam evidence do not need a shared discriminated union. Each
works entirely within its own evidence shape:

- Drainage phases record bounded counts of evidence-exchange events.
- Facade phases record boolean accuracy/continuity/decision outcomes.
- Dam actions record an ordered action sequence and boolean evaluation
  outcomes.

A `unit_kind` enum would create an obligation to classify every future
evidence item into one of four categories. Nothing in the current evidence
base has ever needed to ask "is this a phase or an action?" across
environment boundaries. The `group_phase_evidence()` helper already groups
phases by opaque `phase_id` without needing to know their `unit_kind`. The
dam projections never consult any phase concept at all.

### 3. Task-owned effect payloads

**No formalised common effect-payload shape is added.**

PRD LS-10 lists seven candidate effect categories: information acquired;
constraint opened or satisfied; liability created or resolved; resource
consumed; future option enabled or removed; action reversibility; accepted or
rejected authority outcome. None of these has materialised as a formal common
type in any study to date:

- The dam world's `SeepageEvaluation` records whether the actor's response
  was correct, whether evidence was complete, and whether the measurement
  system was checked — but these are task-owned evaluation booleans stored
  in `evaluation.breakdown`, not a common effect payload.
- Lifecycle phase evidence records bounded counts and boolean outcomes — but
  these are lifecycle-family-owned fields stored via the generic
  `attach_extension()` mechanism.
- `TrialRecord.evaluation.breakdown` (an already-existing, already-generic
  `dict[str, Any]`) is sufficient for every projection built so far. Every
  dam projection and every lifecycle gate projection reads this dict
  directly. No projection has ever needed the breakdown values to be
  classified into the seven effect categories listed in LS-10.

### 4. `EffectComparison`

**No `EffectComparison` structure is added.**

Nothing in the current evidence base performs branching or counterfactual
state comparison. W01 and W02 each compare structured-memory and reset arms
against a cold control — using the existing `LearningMeasurementSpec` paired
difference, not a branching state comparison. L01, L02, and L03 also use
only the existing paired-measurement machinery. PRD LS-10 itself lists "no
counterfactual runner yet" as a non-goal. The `EffectComparison` structure
therefore has no demonstrated consumer and is correctly deferred.

### 5. Decision attribution (actor / host / environment / external process)

**No common attribution tagging is added.**

The dam world's evaluation already distinguishes actor actions from host/
environment state transitions in practice:

- `SeepageAction` (five values: `RECORD_CONFIRMATION_READING`,
  `CHECK_MEASUREMENT_SYSTEM`, `INSPECT_DOWNSTREAM_AREA`,
  `ESCALATE_FOR_ENGINEERING_REVIEW`, `CONTINUE_ROUTINE_SURVEILLANCE`) is
  the complete actor action vocabulary, submitted through the episode
  host's `transition()` function (`world.py:229`).
- The host's own state transitions (e.g., conditional evidence release in
  `observe()`) are never represented as `SeepageAction` values and are
  never recorded in the `action_sequence`.
- The W01 relation review (`w01-relation-domain-review.md`) dealt directly
  with the actor-visible vs. host-hidden information boundary: the
  observation-identity leakage defect (profile slug exposed the answer
  before the epistemic action), the fix (neutral `SEEP-WEIR-02` identity
  for both profiles), and the re-review ACCEPTED verdict. This was an
  actor-information-visibility problem, not an action-attribution problem.
  The review never identified a case where an action's owner was ambiguous.

No study in the evidence base has encountered a situation where a host-owned
action was incorrectly attributed to the actor. The world's typed action
enum inherently separates actor-initiated actions from host-owned state
transitions. A formal common attribution tag would add structure with no
demonstrated failure to prevent.

### 6. The `drainage_phase_completion()` reload-robustness gap

**This is the most concrete piece of evidence in the evidence base for a
narrow common addition. It does NOT justify the full `LearningUnitRef`
envelope, but it does warrant a targeted follow-up.**

The documented, tested limitation is plainly stated in
`drainage_learning.py:148–155`:

> This is currently computable only for a record retained in the process that
> executed the lifecycle. D1 deliberately does not register
> `lifecycle_learning_evidence` in `ledger.reader`'s typed-extension
> hydration map, so a reloaded record has no pending extension value and
> fails closed rather than fabricating a zero.

Verification: `ledger/reader.py:111–116` lists exactly four known
extension kinds: `adaptation`, `lifecycle_execution`,
`lifecycle_provenance`, `meta_harness_provenance`. The string
`"lifecycle_learning_evidence"` is absent. A reloaded `TrialRecord`
therefore has no `pending_extensions` entry for this kind, and
`drainage_phase_completion()` correctly returns `eligible=False,
reason="phase-evidence-missing"`. This is a real, present shortcoming: the
phase-completion projection is same-process-only.

**Analysis — does this justify a common `LearningUnitRef`?**

No. The gap is specifically about extension hydration, not about a missing
cross-environment reference envelope. The fix is narrow and well-scoped:
register `"lifecycle_learning_evidence"` in the `known` dict of
`_hydrate_extensions()`, mapping it to an appropriate model type. This
requires resolving ONE design question: which model type to hydrate to,
given that drainage and facade evidence have different field shapes. The
options include:

1. A minimal common `LifecycleLearningEvidence` with only the structural
   triple (`phase_id`, `checkpoint_ids`, `phase_outcome`) and a
   `model_extra` or raw-dict tail for family-specific fields.
2. A thin discriminated union keyed on `evidence_schema`.
3. Hydrating as raw JSON (the approach `phase_evidence.py` already uses for
   grouping).

Each of these is a much narrower ask than the full `LearningUnitRef`
envelope (which adds `unit_id`, `unit_kind`, `parent_unit_id`, `authority`,
`evidence_ref` as a cross-environment concept). The reload gap is a
lifecycle-internal hydration problem, not evidence that dam actions, artifact
tasks, and lifecycle phases need a shared reference abstraction.

**Recommendation:** a separate, scoped PR should evaluate registering
`"lifecycle_learning_evidence"` in `_hydrate_extensions()`. The simplest
approach (option 3: hydrate as raw JSON dict) would make
`drainage_phase_completion()` work on reloaded records without introducing
any new common type. This is a lifecycle-infrastructure decision, not a
Gate C substrate decision, because it involves only the lifecycle adapter's
own extension kind and the ledger's hydration dispatch — neither of which
is a common Learning Studies contract.

## Promotion rule reapplied

Gate B's own promotion rule (LS-08):

> A hierarchical concept enters the common layer only when: at least one
> artifact study and one lifecycle study use it; or it is required for
> upcoming world evidence and can be demonstrated against existing evidence.

PRD LS-10's acceptance criterion 6 restates the same discipline:

> If two environments do not need the proposed envelope, it is not added.

Applied to each candidate:

| Candidate | Artifact study use | Lifecycle study use | World evidence need | Demonstrated against existing evidence | Promoted? |
| --- | --- | --- | --- | --- | --- |
| `LearningUnitRef` | None (A01–A04 use complete-trial outcomes only) | Phase evidence exists in two families, but lives at the adapter/study layer, not the common contracts | Dam action evidence uses `evaluation.breakdown`, not extension-artefact phases | `phase_evidence.py` already references phases without domain semantics, at the study layer | **No** |
| `unit_kind` discriminant | None | Phase evidence exists but never needs to be classified against action evidence | Action evidence never consults phase concepts | No cross-environment discrimination needed | **No** |
| Task-owned effect payloads | None | Bounded counts / boolean outcomes, all family-owned | `evaluation.breakdown` dict, all world-owned | Generic dict is sufficient | **No** |
| `EffectComparison` | None | None | No branching/counterfactual in W01/W02 | No consumer exists | **No** |
| Decision attribution | None | None | World action enum inherently separates actor/host | No attribution failure found | **No** |

No candidate meets either promotion condition. The promotion rule is applied
consistently: every candidate is declined for the same reason — no cross-
environment convergence pressure exists in the actual evidence.

## Evidence limitations

Gate C is closed on one world family (dam-seepage, bounded episodes), two
lifecycle families (drainage and facade), and zero artifact-study phase/unit
usage. The following evidence does NOT yet exist:

- **No artifact study has ever used a phase, checkpoint, decision, or
  sub-trial unit concept.** The entire promotion rule's first leg ("at least
  one artifact study and one lifecycle study") has never been testable for
  unit-like concepts because artifact studies operate at the complete-trial
  level exclusively. This is the same evidence gap Gate B noted.

- **Only two lifecycle families produce phase evidence, and they share no
  domain base class.** The `group_phase_evidence()` adapter-layer helper
  works across both, but only one study (LS-07 D1) has exercised it. No
  multi-family phase-evidence comparison study has run.

- **World action-attribution scrutiny is minimal.** The W01 relation review
  dealt with actor-visible information, not action ownership. No study has
  specifically tested whether actor and host effects are indistinguishable
  in practice. The dam world's typed action enum provides a natural
  separation, but this has not been adversarially tested.

- **The `drainage_phase_completion()` reload gap is documented and tested
  as a limitation, not silently ignored.** It is the only concrete evidence
  that a current mechanism is incomplete, and this gate explicitly
  recommends a targeted follow-up (see §6 above). The gap does not
  constitute evidence for the full `LearningUnitRef` envelope.

This is acceptable here specifically because **every answer above is a
non-promotion**: the gate's purpose is to guard against prematurely
universalising a world-or-lifecycle-specific concept into the common
substrate, and declining to universalise anything carries no forward-
compatibility risk to retract. Nothing is being built on top of a new common
field that later evidence could contradict, because no new common field is
added. If Release D's persistent-world studies or future multi-family
phase-evidence campaigns produce evidence that contradicts a decision above,
this gate is revisited and the promotion rule reapplied to that new
evidence, not overridden speculatively now.

## What Release D (persistent-world/pump) integration receives

Release D (PRD LS-11/LS-12) builds on the following documented minimal
substrate, unchanged by this gate:

**Authored common contracts** (`src/aec_bench/contracts/learning_study.py`,
`learning_study_evidence.py`, `learning_study_assessment.py`,
`learning_family.py`): identical to the list in Gate B's "What worlds
integration receives" section — `LearningStudySpec`,
`LearningStudyProtocolSpec`, compiled plan and steps
(`RunExperienceStep`, `ReleaseFeedbackStep`, `ConsolidateStep`),
`LearningArmSpec` and `StudyArmRole`, `ExperienceRelationSpec` and
`ExperienceRelationPurpose` (`transfer`/`boundary`/`composition`),
`LearnerStateRef`, `FeedbackReleaseRecord`, `LearnerTransitionReceipt`,
the runtime-local `ProjectionResult` and `OutcomeProjection` callback type,
and the assessment validity classes.

**The proven adapter pattern**, demonstrated by three independent
environment families (artifact, lifecycle, world):

- task-ID resolution is owner-local;
- the execution condition is fixed per binding and encoded in `adapter_id`;
- treatment pairs are owner-defined;
- learner state, feedback, and context projection are adapter-owned;
- outcome projections are `Callable[[TrialRecord], ProjectionResult]`,
  unchanged since Gate A, proven sufficient across artifact, lifecycle, AND
  world projections (confirmed: all four dam projections in
  `dam_learning.py` are this exact type);
- `TrialExtensionRef` and `attach_extension()` provide a generic
  extension mechanism for typed artefacts (used by lifecycle phase evidence)
  without common contract changes;
- `TrialRecord.evaluation.breakdown` provides a generic dict mechanism for
  task-owned evaluation evidence (used by dam action evidence) without
  common contract changes.

**Explicit non-inheritances.** The pump/persistent-world adapter does not
inherit, and should not introduce without new evidence:

- lifecycle mode/visibility concepts, checkpoint semantics, or any phase
  model (lifecycle phase evidence stays lifecycle-owned);
- dam-specific action semantics, episode-host machinery, or the
  `SeepageAction` enum (world action evidence stays world-owned);
- a `LearningUnitRef` envelope, `EffectComparison` structure, or
  action-attribution tagging (declined by this gate);
- any formalised effect-payload taxonomy (the seven categories in LS-10
  remain speculative).

Persistent-world integration brings its own execution semantics (multi-
journey persistence, world-owned continuity) and its own evidence semantics,
exactly as lifecycles brought checkpoint/session semantics and worlds
brought action/evaluation semantics, each without asking the common layer
to understand them.

## Acceptance criteria mapping (PRD LS-10)

1. **The envelope can reference dam action evidence and lifecycle phase
   evidence.** Satisfied by non-action: neither evidence family needs a
   common envelope. Dam action evidence lives in `evaluation.breakdown`;
   lifecycle phase evidence lives in typed extensions accessed via
   `pending_extensions`. The study-layer `group_phase_evidence()` already
   references phases by opaque `phase_id` without a common envelope type.

2. **Domain payloads remain owner-local.** Satisfied: drainage phase
   evidence (`DrainageLearningEvidence`), facade phase evidence
   (`FacadeLearningEvidence`), and dam evaluation evidence
   (`SeepageEvaluation` via `evaluation.breakdown`) each remain in their
   respective owner modules with zero cross-imports.

3. **The common package does not import world action types.** Satisfied:
   `src/aec_bench/contracts/` contains no reference to `SeepageAction`,
   `SeepageEvaluation`, `DrainagePhaseEvidence`, `FacadePhaseEvidence`, or
   any domain-specific evidence type.

4. **Actor and host effects are distinguishable.** Satisfied by the world's
   own typed action enum: `SeepageAction` enumerates exactly the actor's
   action vocabulary; host-owned state transitions (conditional evidence
   release in `observe()`) are never represented as `SeepageAction` values.
   No common attribution tag was needed to achieve this.

5. **No generic scalar "progress" field is required.** Satisfied: no
   progress field was added. All projections return bounded domain-specific
   outcomes (`response_correct`, `evidence_complete`,
   `inappropriate_escalation`, `phase_completion`), not a generic progress
   scalar.

6. **If two environments do not need the proposed envelope, it is not
   added.** Satisfied: dam-world studies and lifecycle studies each work
   with their own independent evidence mechanisms. Neither needs the
   proposed `LearningUnitRef` or `EffectComparison` structures. The
   envelope is not added.

## Consequences and open questions

- **LS-07 phase-evidence studies and the L02/L03 campaigns remain open and
  unblocked.** They proceed using the unchanged substrate; phase evidence
  continues to be lifecycle-owned and attached via
  `attach_extension("lifecycle_learning_evidence", ...)`.

- **The `drainage_phase_completion()` reload-hydration gap warrants a
  targeted follow-up.** A separate, scoped PR should evaluate registering
  `"lifecycle_learning_evidence"` in `ledger/reader.py`'s
  `_hydrate_extensions()` known-type map. The simplest option (hydrate as
  raw JSON dict, matching the approach `phase_evidence.py` already uses)
  would resolve the same-process limitation without introducing any new
  common type. This is a lifecycle-infrastructure decision, not a common
  substrate decision.

- **Release D (PRD LS-11/LS-12, persistent-world and pump integration) may
  begin design** against the substrate as documented in Gate A, Gate B, and
  this record. No new common contract, enum, or field is pre-authorised for
  that work. The release sequence (`programme.md` §13) names no dedicated
  substrate-revision gate for Release D; if persistent-world evidence later
  demonstrates a genuine cross-environment convergence need, that would be a
  new gate decision to propose at that time, not one presumed here.

- **If future evidence contradicts this gate's conclusions, this gate is
  revisited.** Specifically: if a persistent-world study or a multi-family
  phase-evidence campaign demonstrates that independent evidence mechanisms
  produce real, demonstrated failures (not hypothetical inconvenience), the
  promotion rule is reapplied to that new evidence. This gate's conclusions
  are non-promotions and carry no forward-compatibility risk to retract.

- **The `EffectComparison` structure remains explicitly deferred.** PRD
  LS-10's own non-goals ("no counterfactual runner yet") correctly
  recognise that branching comparison has no current consumer. This can be
  revisited when a study actually needs controlled branching.

- **Action-attribution tagging remains unnecessary given the current
  evidence.** If a future world produces actions where actor and host
  ownership is genuinely ambiguous (unlike the dam world's typed action
  enum), that is new evidence for a targeted attribution mechanism, not a
  retroactive justification for the full four-category tagging proposed in
  LS-10.
