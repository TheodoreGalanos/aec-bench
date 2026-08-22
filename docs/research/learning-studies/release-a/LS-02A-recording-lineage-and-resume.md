# LS-02A — Study Recording, Learner-State Lineage, and Resume

**Status:** Proposed
**Type:** Implementation PRD
**Release:** Learning Studies Release A
**Depends on:** LS-01A and LS-01B
**Blocks:** LS-02B and production use of LS-04A
**Primary owner:** `aec_bench.experimentation.learning_studies`
**Shared evidence contract owner:** `aec_bench.contracts`
**Repository baseline:** `main`, reviewed 22 August 2026

## 1. Purpose

Make a learning study inspectable and safely resumable without expanding `TrialRecord` into a multi-experience career record.

This PRD defines:

- the study run bundle;
- exact learner-state snapshot references;
- state lineage and transition receipts;
- append-only study events;
- atomic step commit;
- crash recovery and resume;
- evidence and secrecy boundaries.

It does not interpret whether learning occurred. LS-02B owns that judgment.

## 2. Design principle

A learning study has two different evidence authorities:

```text
Trial authority
ordinary TrialRecord produced by the existing execution owner
```

and:

```text
Study authority
ordered step receipts, learner-state lineage, feedback releases,
and declared comparisons
```

The study layer references trial records. It does not copy task state, output artifacts, verifier internals, or full evaluation payloads into a new universal record.

## 3. Goals

1. Persist the exact authored spec and compiled plan used by a study run.
2. Persist every completed ordinary `TrialRecord` through the existing ledger path.
3. Record what learner state existed before and after every committed transition.
4. Record exactly which feedback view was released and from which experience.
5. Resume after interruption without rerunning committed steps.
6. Distinguish incomplete, abandoned, committed, and discarded transitions.
7. Preserve enough evidence to audit arm isolation and probe contamination.
8. Reuse `ArtifactRepository`, `ArtifactRef`, and existing ledger machinery.
9. Avoid a new hash/version/provenance subsystem.

## 4. Non-goals

This PRD does not provide:

- assessment metrics;
- statistical confidence;
- task-specific feedback contents;
- incremental or content-addressed learner-state deltas;
- cross-machine distributed transactions;
- concurrent arm execution;
- model-weight snapshots;
- automatic migration of old study bundles.

## 5. Study run bundle

Use one caller-selected run root:

```text
<run-root>/learning-studies/<study_run_id>/
```

Within it:

```text
study-spec.json
study-plan.json
events.jsonl
result.json                         # written when the run reaches a terminal study state

steps/
  <arm_run_id>/
    000-<step_id>.json
    001-<step_id>.json

states/
  <state_id>.json

transitions/
  <transition_id>.json

feedback/
  <feedback_id>.json

ledger/
  ... ordinary TrialRecord files through existing ledger conventions ...

staging/
  <arm_run_id>/
    <step_id>/
```

The implementation may adapt the exact ledger subpath to existing writer conventions. It must not create a second bespoke trial-record format.

`study-spec.json` and `study-plan.json` are immutable after the first committed step.

## 6. Persisted evidence contracts

Add a focused module such as:

```text
src/aec_bench/contracts/learning_study_evidence.py
```

Do not overload the authored-spec module with every run-time receipt.

### 6.1 Learner-state reference

```python
class LearnerStateRef(StrictModel):
    state_id: NonEmptyStr
    arm_run_id: NonEmptyStr
    treatment_id: NonEmptyStr
    parent_state_id: str | None
    created_after_step_id: str | None
    artifact: ArtifactRef
    changed_channels: tuple[NonEmptyStr, ...] = ()
```

Rules:

- initial state has no parent and no creating step;
- every later committed state has exactly one parent in the same arm run;
- state IDs are readable study identities, not content hashes;
- the existing `ArtifactRef` carries exact-byte integrity;
- `changed_channels` uses adapter-owned labels and is descriptive, not a global state ontology.

### 6.2 Feedback-release record

```python
class FeedbackReleaseRecord(StrictModel):
    feedback_id: NonEmptyStr
    arm_run_id: NonEmptyStr
    release_step_id: NonEmptyStr
    source_experience_id: NonEmptyStr
    source_trial_id: NonEmptyStr
    view_id: NonEmptyStr
    public_artifact_refs: tuple[ArtifactRef, ...]
    state_before_id: NonEmptyStr
    state_after_id: NonEmptyStr
```

It records what was released to the learner, not every item available to the host.

### 6.3 Learner-transition receipt

```python
class LearnerTransitionReceipt(StrictModel):
    transition_id: NonEmptyStr
    arm_run_id: NonEmptyStr
    step_id: NonEmptyStr
    operation_kind: Literal[
        "initialise",
        "experience",
        "feedback_release",
        "consolidation",
        "probe_discard",
    ]
    state_before_id: str | None
    candidate_state_id: NonEmptyStr
    committed_state_id: str | None
    committed: bool
    feedback_ids: tuple[NonEmptyStr, ...] = ()
    changed_channels: tuple[NonEmptyStr, ...] = ()
    diagnostics: tuple[str, ...] = ()
```

For a discarded probe candidate:

```text
candidate_state_id = the produced candidate
committed_state_id = the unchanged prior state
committed = false
```

The candidate state does not need to remain materialised after its discard is recorded unless a debugging mode explicitly retains it. The receipt remains.

### 6.4 Committed step receipt

Use a discriminated receipt or one strict envelope with step-specific references.

It must include:

```text
study_run_id
arm_run_id
step_id
step_index
step_kind
status
trial_id, if an experience
feedback_id, if a feedback release
transition_id, if state-producing
started_at
completed_at
failure, if terminally failed
```

The step receipt is the authoritative commit marker for resume.

### 6.5 Study event

```python
class StudyEvent(StrictModel):
    sequence: NonNegativeInt
    timestamp: datetime
    study_run_id: NonEmptyStr
    kind: StudyEventKind
    arm_run_id: str | None
    step_id: str | None
    reference: str | None
```

Keep events small. Detailed evidence belongs in referenced receipts.

Required kinds include:

```text
study_started
arm_run_started
learner_initialised
step_started
step_committed
step_failed
arm_run_completed
arm_run_failed
study_completed
study_cancelled
```

## 7. Learner-state snapshot format

Release A stores each **committed** learner state as a complete portable snapshot rather than a delta.

Reasons:

- simpler resume;
- clear arm isolation;
- easier inspection;
- no parent-chain reconstruction failure;
- no premature state-diff protocol.

The adapter supplies a snapshot directory that already excludes protected task or verifier material. The recorder then:

1. validates every path is relative and contained;
2. rejects symlinks, device files, sockets, and absolute paths;
3. archives files in sorted relative-path order;
4. publishes the archive through the existing artifact repository;
5. writes a `LearnerStateRef` containing the resulting `ArtifactRef`.

Use one standard-library archive format selected during implementation. Do not introduce a new compression dependency.

The archive’s existing artifact digest is sufficient. Do not add a second state hash.

## 8. State identity

Generate readable state identities from study execution order, for example:

```text
<arm_run_id>:state:000
<arm_run_id>:state:001
```

Generate transition and feedback identities similarly.

Identity must not depend on:

- wall-clock time;
- archive digest;
- model output content;
- package version.

The exact bytes remain independently protected by `ArtifactRef`.

## 9. Recording API

Provide a recorder object or functional bundle local to the learning-study owner. Do not require execution adapters to write JSON directly.

Conceptual operations:

```python
create_study_run(spec, plan, root) -> StudyRunRecorder
stage_step(...)
publish_trial_record(...)
publish_state(...)
publish_feedback(...)
publish_transition(...)
commit_step(...)
fail_step(...)
complete_arm_run(...)
complete_study(...)
load_resumable_study(...)
```

A small stateful recorder is acceptable here because it owns an append-only run bundle and file handles. The study runtime and domain logic should remain functionally composed.

## 10. Atomic step commit

A study step often has several outputs:

- an ordinary trial record;
- a candidate learner snapshot;
- a state reference;
- a transition receipt;
- possibly a feedback record.

No filesystem provides one transaction across all of them. Release A therefore uses a staging-and-receipt protocol.

### 10.1 Staging

Before calling an adapter step, create:

```text
staging/<arm_run_id>/<step_id>/
```

The adapter keeps any candidate workspace or state snapshot available there until commit or explicit abandonment.

### 10.2 Publication order

After a successful callback:

1. validate returned trial identity and candidate state;
2. materialise the candidate learner snapshot into staging;
3. publish referenced state and feedback artifacts;
4. publish the ordinary `TrialRecord` through the existing ledger writer, if present;
5. write state, feedback, and transition receipts atomically;
6. write the final step receipt atomically;
7. append the `step_committed` event;
8. remove staging data no longer needed.

The final step receipt is the authoritative commit marker.

### 10.3 Event repair

A crash can occur after the step receipt is written but before its event is appended.

On resume:

- receipts determine committed truth;
- missing events are reconstructed and appended in sequence;
- events never override a receipt.

### 10.4 Partially published outputs

A crash before the step receipt may leave staged or published artifacts.

On resume:

- if all required outputs exist and validate, finish the commit and write the receipt;
- if outputs are incomplete but the staging workspace is intact, complete publication from staging;
- if the callback never returned a valid result, abandon staging and rerun the step from the previous committed state;
- never treat an unreferenced artifact as a committed state;
- never silently overwrite a different trial record at the same trial ID.

This protocol avoids rerunning a completed expensive trial merely because the event append was interrupted.

## 11. Trial-record integration

Use the existing ledger writer and artifact materialisation path.

The learning recorder must verify that:

- returned trial ID equals the compiled plan;
- task ID equals the planned task;
- the record is fully materialised according to existing ledger rules;
- its extension references remain task-owned;
- the same trial ID does not resolve to different content.

The study result stores trial IDs or normal record references. It does not embed full records.

## 12. Resume algorithm

`load_resumable_study(run_root)` performs:

1. load and strictly validate `study-spec.json`;
2. load `study-plan.json`;
3. compare the requested compiled plan by exact canonical data equality;
4. reject a changed plan rather than trying to migrate it;
5. scan authoritative step receipts in plan order;
6. validate referenced trial records, states, feedback, and transitions;
7. repair missing event entries;
8. identify the first uncommitted step in every incomplete arm run;
9. restore the latest committed learner state for that arm run;
10. abandon or complete any staging transaction according to Section 10.4;
11. continue without rerunning committed steps.

No plan hash or schema-version matrix is required. The persisted plan itself is compared.

## 13. Result and terminal states

The final `result.json` introduced here records execution completion, not learning assessment yet.

Study terminal states:

```text
completed
completed_with_failed_arms
cancelled
invalid
```

An arm run may be:

```text
completed
failed
cancelled
```

A failed task inside a valid `TrialRecord` does not automatically make the arm-run execution failed.

LS-02B later enriches the result with comparison validity and measurements.

## 14. Security and leakage constraints

The recorder must never publish into learner-state artifacts:

- verifier source;
- expected answers;
- hidden task data;
- host-only paths;
- provider credentials;
- another arm’s files;
- evaluation details not selected by a feedback view.

The adapter owns the projection, but the recorder enforces generic path safety and arm ownership.

State artifacts and feedback artifacts must be stored separately. The existence of host evidence does not imply learner visibility.

## 15. Failure taxonomy

At minimum:

```text
study-bundle-exists
study-plan-mismatch
study-event-corrupt
step-receipt-corrupt
trial-record-publication-failed
trial-record-conflict
state-snapshot-invalid
state-publication-failed
state-lineage-invalid
feedback-record-invalid
transition-receipt-invalid
resume-artifact-missing
resume-staging-unrecoverable
```

Persistence failure is fatal to the study run because later learning claims cannot be trusted without exact evidence.

## 16. File changes

Expected additions:

```text
src/aec_bench/contracts/learning_study_evidence.py
src/aec_bench/experimentation/learning_studies/recording.py
src/aec_bench/experimentation/learning_studies/resume.py
tests/contracts/test_learning_study_evidence.py
tests/experimentation/learning_studies/test_recording.py
tests/experimentation/learning_studies/test_resume.py
```

Reuse existing:

```text
src/aec_bench/ledger/writer.py
src/aec_bench/contracts/artifacts.py
```

Modify those owners only if a genuinely reusable primitive is missing.

## 17. Test matrix

### Recording tests

- new bundle creation;
- immutable spec and plan;
- trial record written through existing ledger;
- full state snapshot published through artifact repository;
- parent lineage validated;
- feedback record references only selected public artifacts;
- probe discard receipt preserves prior committed state.

### Transaction tests

Inject failure after every publication stage:

1. after callback return;
2. after state artifact publication;
3. after trial-record publication;
4. after transition receipt;
5. after step receipt;
6. before event append.

Resume must either finish the exact commit or rerun only an uncommitted step from its previous state.

### Resume tests

- resume after each completed step;
- completed steps never execute again;
- missing event is repaired from receipt;
- changed plan is rejected;
- missing committed state artifact is fatal;
- incomplete staging is abandoned safely;
- arm failures remain isolated on resume.

### Security tests

- absolute path rejected;
- symlink rejected;
- cross-arm state parent rejected;
- hidden verifier fixture excluded from learner archive;
- feedback not declared by view absent from learner archive.

### Regression tests

- existing ledger semantics remain unchanged;
- existing `TrialRecord` round-trips remain unchanged;
- no new top-level fields are added to `TrialRecord`.

## 18. Acceptance criteria

LS-02A is complete when:

1. Every study run persists its exact spec, plan, events, step receipts, learner states, feedback releases, transitions, and ordinary trial records.
2. Every committed learner state has one valid parent lineage inside its arm run.
3. Probe candidates can be recorded as discarded without entering later state.
4. A run can resume after interruption at every step boundary.
5. Committed steps are never rerun.
6. Partially published outputs are either completed from staging or rejected explicitly.
7. The existing artifact repository and ledger remain the byte and trial authorities.
8. No task evidence is copied into a universal study record.
9. No new hash catalogue, per-feature version field, or migration layer is introduced.

## 19. Agent handoff

The implementation agent should return:

- final bundle layout;
- evidence-contract field list;
- the exact atomic commit sequence;
- failure-injection test results for every commit stage;
- resume behaviour for each interrupted state;
- proof that learner snapshots exclude protected and cross-arm data;
- confirmation that `TrialRecord` was not expanded.
