# LS-01B — Learning Study Runtime and Arm Isolation

**Status:** Proposed
**Type:** Implementation PRD
**Release:** Learning Studies Release A
**Depends on:** LS-01A
**Blocks:** LS-02A and LS-04A
**Primary owner:** `aec_bench.experimentation.learning_studies`
**Repository baseline:** `main`, reviewed 22 August 2026

## 1. Purpose

Execute a compiled learning study without knowing how a particular environment stores learner state or runs its trials.

This PRD defines:

- the runtime callback boundary;
- immutable learner-state transitions;
- arm and repetition isolation;
- step ordering and commit semantics;
- probe-state discard;
- failure behaviour;
- synchronous and asynchronous operation support.

Persistence, resume, and assessment are added by LS-02A and LS-02B.

## 2. Design principle

The runtime follows the same broad pattern as the runtime-neutral meta-harness:

> The common owner coordinates a process through caller-supplied functions. It does not import or understand each execution family.

```text
CompiledLearningStudy
        ↓
common step coordinator
        ↓
LearningStudyOperations callbacks
        ↓
environment-specific adapter
        ↓
ordinary execution owner
```

The runtime must not import:

- `LocalTaskRuntime`;
- lifecycle runners;
- world actions or states;
- provider implementations;
- task-specific evaluators.

## 3. Goals

1. Execute each planned arm run in declared order.
2. Give every arm and repetition an independently initialised learner state.
3. Require copy-on-write learner-state transitions.
4. Execute existing planned trials and retain ordinary `TrialRecord` values.
5. Make feedback release and consolidation explicit steps.
6. Discard probe-created state by default.
7. Continue independent arm runs after a local arm failure.
8. Support sync and async callbacks without separate runtimes.
9. Return a complete in-memory execution result suitable for later persistence and assessment.

## 4. Non-goals

This PRD does not provide:

- disk persistence;
- crash recovery;
- metrics or controlled comparison;
- environment-specific state formats;
- parallel execution;
- automatic retry;
- adaptive branching;
- model-weight updates;
- universal memory or feedback schemas.

## 5. Runtime values

Keep these as frozen dataclasses under:

```text
src/aec_bench/experimentation/learning_studies/runtime.py
```

They are not shared persisted contracts in LS-01B.

### 5.1 Opaque learner-state handle

```python
StateT = TypeVar("StateT")


@dataclass(frozen=True)
class LearnerStateHandle(Generic[StateT]):
    state_id: str
    value: StateT
```

The common runtime may inspect `state_id` only. It must not inspect or mutate `value`.

Rules:

- state IDs are unique within one study run;
- the adapter returns a new state ID for every successful state-producing step;
- callbacks treat input state as immutable;
- two arm runs must never share the same state ID;
- later persistence may replace the runtime value with an artifact-backed reference without changing these semantics.

### 5.2 Feedback handle

```python
FeedbackT = TypeVar("FeedbackT")


@dataclass(frozen=True)
class FeedbackHandle(Generic[FeedbackT]):
    feedback_id: str
    source_experience_id: str
    view_id: str
    value: FeedbackT
```

The common runtime tracks identity and provenance only. The adapter owns the payload.

### 5.3 Experience execution result

```python
@dataclass(frozen=True)
class ExperienceExecutionResult(Generic[StateT]):
    trial_record: TrialRecord
    candidate_state: LearnerStateHandle[StateT]
    diagnostics: tuple[str, ...] = ()
```

Returning a `TrialRecord` with a failed or invalid task result is still a completed experience step. Throwing before a `TrialRecord` exists is an execution failure.

### 5.4 State-transition result

```python
@dataclass(frozen=True)
class LearnerTransitionResult(Generic[StateT]):
    candidate_state: LearnerStateHandle[StateT]
    changed_channels: tuple[str, ...]
    diagnostics: tuple[str, ...] = ()
```

Feedback release additionally returns its feedback handle.

### 5.5 Arm-run result

```python
@dataclass(frozen=True)
class ArmRunExecutionResult:
    arm_run_id: str
    status: ArmRunStatus
    completed_steps: tuple[StepExecutionResult, ...]
    trial_records: tuple[TrialRecord, ...]
    final_state_id: str | None
    failure: StudyStepFailure | None
```

A top-level result contains all arm-run results in compiled order.

## 6. Operations callback boundary

Use one frozen operations bundle rather than a required adapter base class.

Conceptually:

```python
@dataclass(frozen=True)
class LearningStudyOperations(Generic[StateT, FeedbackT]):
    initialise_learner: Callable[[InitialiseLearnerRequest], MaybeAwaitable[LearnerStateHandle[StateT]]]
    execute_experience: Callable[[ExecuteExperienceRequest[StateT]], MaybeAwaitable[ExperienceExecutionResult[StateT]]]
    release_feedback: Callable[[ReleaseFeedbackRequest[StateT]], MaybeAwaitable[FeedbackReleaseResult[StateT, FeedbackT]]]
    consolidate: Callable[[ConsolidationRequest[StateT, FeedbackT]], MaybeAwaitable[LearnerTransitionResult[StateT]]]
    discard_state: Callable[[LearnerStateHandle[StateT]], MaybeAwaitable[None]]
    close_state: Callable[[LearnerStateHandle[StateT]], MaybeAwaitable[None]]
```

The implementation should use existing async utility conventions if available. Otherwise, one private `maybe_await` helper is sufficient.

### 6.1 Initialisation request

Contains only:

- study run ID;
- arm run ID;
- arm and treatment IDs;
- repetition;
- initial agent and compute configuration;
- a caller-owned working root if the adapter needs one.

The common runtime does not construct workspaces itself.

### 6.2 Experience request

Contains:

- compiled experience step;
- current learner-state handle;
- earlier completed trial records in the same arm run;
- feedback handles already released in the same arm run.

It does not expose another arm’s history.

### 6.3 Feedback request

Contains:

- compiled feedback step;
- current learner state;
- the exact source `TrialRecord` from this arm run;
- no unrestricted access to every study record.

The adapter produces both:

- a new learner state in which the permitted feedback is visible;
- a feedback handle identifying what was released.

### 6.4 Consolidation request

Contains:

- compiled consolidation step;
- current learner state;
- only the explicitly referenced feedback handles;
- the operation ID interpreted by the adapter.

The callback may run a model or deterministic operation. It returns a new learner state and changed-channel labels.

## 7. Copy-on-write state semantics

No callback may mutate the supplied learner state in place.

For every successful state-producing step:

```text
state_before ──operation──> candidate_state
```

The common runtime then either:

- commits `candidate_state` as the arm’s current state; or
- discards it and retains `state_before`.

This rule is required for:

- probe isolation;
- arm isolation;
- later persistence and resume;
- inspectable state lineage;
- safe failure recovery.

The runtime checks that `candidate_state.state_id != state_before.state_id`. The adapter remains responsible for proving that the underlying mutable storage is also separate. LS-04A adds filesystem-level tests for that guarantee.

## 8. Step semantics

### 8.1 `RunExperience`

1. Invoke `execute_experience` with the current state and exact `PlannedTrial`.
2. Validate that the returned `TrialRecord.trial_id` and task identity match the plan.
3. Record the trial result in the arm-run history.
4. If `commit_post_state` is true:
   - commit the candidate state;
   - close or release the superseded state when safe.
5. If `commit_post_state` is false:
   - call `discard_state(candidate_state)`;
   - keep the previous state current.

A probe normally follows the second branch.

### 8.2 `ReleaseFeedback`

1. Find the exact completed source experience in the same arm run.
2. Invoke `release_feedback` with only that record and the declared view ID.
3. Validate a new state ID and unique feedback ID.
4. Commit the new state.
5. Store the feedback handle for later consolidation steps.

Evidence not selected by the view remains host-held.

### 8.3 `Consolidate`

1. Resolve only the feedback handles named by the compiled step.
2. Invoke `consolidate` with the current state and those handles.
3. Validate a new state ID.
4. Commit the new state.

The runtime does not judge whether the resulting notes or skills are good. Later probe behaviour provides that evidence.

## 9. Arm-run algorithm

Conceptually:

```python
async def run_arm_run(plan, operations):
    state = await operations.initialise_learner(...)
    seen_state_ids = {state.state_id}
    trials = {}
    feedback = {}

    for step in plan.steps:
        try:
            if step is experience:
                result = await operations.execute_experience(...)
                validate_trial_identity(result.trial_record, step.trial)
                validate_new_state(result.candidate_state, seen_state_ids)
                trials[step.experience_id] = result.trial_record
                state = commit_or_discard(...)

            elif step is feedback:
                result = await operations.release_feedback(...)
                validate_new_state(...)
                validate_new_feedback(...)
                state = result.candidate_state
                feedback[step.step_id] = result.feedback

            elif step is consolidation:
                result = await operations.consolidate(...)
                validate_new_state(...)
                state = result.candidate_state

        except Exception as exc:
            return failed_arm_result(...)

    return completed_arm_result(...)
```

Implementation should preserve typed errors and cancellation behaviour rather than catching `BaseException`.

## 10. Study execution order

Release A runs:

```text
arm run 1, all steps
arm run 2, all steps
...
```

in the deterministic order produced by compilation.

The order should interleave matched repetitions by default to reduce temporal provider drift:

```text
repetition 0: control, exposure treatments...
repetition 1: control, exposure treatments...
```

rather than running every control repetition before every treatment repetition.

This is still sequential execution. Parallelism is deferred until state isolation and provider-rate behaviour have been proven.

## 11. Isolation rules

### 11.1 Between arms

- `initialise_learner` is called separately for every arm run.
- Initial state IDs must differ.
- No state or feedback handle may appear in two arm runs.
- An arm receives no other arm’s trials, feedback, paths, or diagnostics.

### 11.2 Between repetitions

- Repetition `r+1` never starts from repetition `r` state.
- Identical treatment IDs do not imply shared storage.
- Results are paired later by repetition number only.

### 11.3 Between learner and environment

The common runtime transports only adapter-provided state handles. It must not add task files, verifier data, world state, or provider secrets to learner state.

### 11.4 Probe isolation

By default:

- the learner sees the probe task through normal task execution;
- probe evaluation is not released during the step;
- candidate state produced during the probe is discarded;
- subsequent study steps cannot access probe-created files or conversation state.

## 12. Failure model

Use typed failures with at least these categories:

```text
learner-initialisation-failed
experience-execution-failed
trial-record-mismatch
feedback-source-missing
feedback-release-failed
consolidation-failed
state-identity-reused
state-discard-failed
arm-isolation-failed
unsupported-step
```

### 12.1 Arm-local failures

An arm-local failure:

- stops the current arm run;
- marks remaining steps skipped;
- preserves completed trial records;
- closes the current state where possible;
- allows later independent arm runs to continue.

### 12.2 Fatal study failures

The runtime stops the whole study only for failures that invalidate coordination itself, such as:

- corrupt compiled plan;
- duplicate arm-run identity discovered at runtime;
- operations bundle missing a required callback;
- caller cancellation;
- later persistence failure once LS-02A is integrated.

### 12.3 Trial failure versus runtime failure

A returned `TrialRecord` with task status `failed`, `invalid`, `truncated`, or equivalent is a completed experience outcome.

An exception before a valid `TrialRecord` is returned is a runtime failure.

Do not synthesise a fake trial record to hide the distinction.

### 12.4 Retry

The common runtime performs no automatic retry in Release A.

Retries already owned inside an execution family remain part of that trial’s normal semantics. Cross-step retry and resume belong to LS-02A.

## 13. Cancellation and cleanup

- Propagate `asyncio.CancelledError`.
- Attempt bounded cleanup of the current candidate and committed state.
- Do not convert cancellation into a normal failed arm result.
- Cleanup failure should be attached as diagnostic context without hiding the primary error.
- Adapter cleanup must never delete a state still referenced by another live step; correct isolation should make that situation impossible.

## 14. File changes

Expected additions:

```text
src/aec_bench/experimentation/learning_studies/runtime.py
tests/experimentation/learning_studies/test_runtime.py
```

Expected modifications:

```text
src/aec_bench/experimentation/learning_studies/__init__.py
```

Do not add artifact-task imports or persistence code here.

## 15. Test matrix

### Happy paths

- cold arm with one probe;
- exposure arm with acquisition, feedback, consolidation, and probe;
- sync callbacks;
- async callbacks;
- failed task represented by a normal `TrialRecord`;
- several repetitions interleaved deterministically.

### State tests

- initial states are unique by arm run;
- input state is not replaced until a successful return;
- new state IDs are required;
- committed acquisition changes become current;
- probe candidate state is discarded;
- discarded state never appears in a later request;
- feedback and consolidation create explicit transitions.

### Isolation tests

- callbacks for one arm never receive another arm’s trial or feedback;
- repetition state does not carry forward;
- duplicate state or feedback IDs are rejected;
- one arm failure does not stop an independent arm.

### Failure tests

- exception before `TrialRecord`;
- wrong trial ID returned;
- missing feedback source;
- feedback callback failure;
- consolidation failure;
- discard failure;
- cancellation.

### Architecture tests

- runtime imports no environment-specific runner;
- no universal adapter base class is required;
- no persistence, assessment, or RL dependency is introduced.

## 16. Acceptance criteria

LS-01B is complete when:

1. A compiled synthetic study executes through a caller-supplied operations bundle.
2. Every arm and repetition receives isolated learner state.
3. All state-producing operations are copy-on-write.
4. Existing `TrialRecord` values remain the only trial outcome.
5. Probe state is discarded by default and cannot contaminate later steps.
6. Feedback and consolidation are explicit, ordered transitions.
7. Arm-local failures preserve partial evidence and do not stop independent arms.
8. Sync and async callbacks behave identically.
9. The runtime imports no artifact, lifecycle, world, provider, or RL implementation.

## 17. Agent handoff

The implementation agent should return:

- final callback signatures;
- state and feedback identity rules;
- the exact arm-run ordering;
- copy-on-write enforcement tests;
- probe-discard evidence;
- arm-local versus fatal failure taxonomy;
- proof that the runtime contains no environment-specific imports.
