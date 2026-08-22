# LS-01A — Learning Study Contracts and Deterministic Compilation

**Status:** Proposed
**Type:** Implementation PRD
**Release:** Learning Studies Release A
**Depends on:** LS-00
**Blocks:** LS-01B, LS-02A, LS-03, LS-04A
**Primary owner:** `aec_bench.experimentation.learning_studies`
**Shared persisted contract owner:** `aec_bench.contracts`
**Repository baseline:** `main`, reviewed 22 August 2026

## 1. Purpose

Define the smallest authored study contract and compile it deterministically into exact existing `PlannedTrial` values.

This PRD answers:

- what a study author declares;
- what the compiler resolves;
- how arms, repetitions, experiences, and steps receive exact identities;
- which validations occur before execution;
- how the implementation reuses existing planning rather than creating a second trial model.

It does not execute a study or calculate learning metrics.

## 2. Current architectural seam

AEC-Bench already has:

- `AgentConfig` and `ComputeConfig` for execution configuration;
- `PlannedTrial` as the direct planned value used across runnable task families;
- deterministic `trial_id` construction;
- `TrialRecord` as the returned execution evidence;
- runtime-neutral experimentation functions that accept caller-supplied evaluators.

The learning layer should compile down to that seam:

```text
LearningStudySpec
        ↓
compile_learning_study(...)
        ↓
CompiledLearningStudy
        ↓
exact PlannedTrial for every RunExperience step
```

It must not define `LearningTrial`, duplicate `PlannedTrial`, or create a new task-resolution path.

## 3. Goals

1. Represent an explicit finite study with arms and ordered steps.
2. Reuse one ordinary task ID and one ordinary `PlannedTrial` for each experience execution.
3. Support acquisition, practice, interference, and probe roles.
4. Support explicit feedback-release and consolidation steps without implementing them yet.
5. Represent study relationships separately from task semantics.
6. Expand repetitions into isolated arm runs.
7. Produce stable, inspectable identities without content hashes or version variables.
8. Reject ambiguous or invalid studies before any model call or workspace creation.

## 4. Non-goals

This PRD does not implement:

- learner-state contents or persistence;
- study execution;
- feedback projection;
- consolidation behaviour;
- assessment metrics;
- adaptive sequencing or branching;
- environment-specific treatments;
- task-family selectors;
- CLI commands;
- model-weight updates.

## 5. Contract placement rule

Only values that are authored, persisted, or exchanged across package boundaries belong in `aec_bench.contracts`.

Runtime-only compiled helper values remain frozen dataclasses under:

```text
src/aec_bench/experimentation/learning_studies/
```

This PRD must not turn every internal helper into a Pydantic model.

## 6. Authored study contract

Add:

```text
src/aec_bench/contracts/learning_study.py
```

Use the repository’s existing strict model and non-empty string conventions.

### 6.1 Enums

```python
class StudyClaimMode(StrEnum):
    DESCRIPTIVE = "descriptive"
    CONTROLLED = "controlled"


class ExperienceRole(StrEnum):
    ACQUISITION = "acquisition"
    PRACTICE = "practice"
    INTERFERENCE = "interference"
    PROBE = "probe"


class StudyArmRole(StrEnum):
    CONTROL = "control"
    EXPOSURE = "exposure"


class ExperienceRelationPurpose(StrEnum):
    TRANSFER = "transfer"
    BOUNDARY = "boundary"
    COMPOSITION = "composition"
    RETENTION = "retention"
    INTERFERENCE = "interference"
```

These enums describe study design only. They do not alter task execution.

### 6.2 Experience declaration

```python
class LearningExperienceSpec(StrictModel):
    experience_id: NonEmptyStr
    task_id: NonEmptyStr
    role: ExperienceRole
    description: str | None = None
```

Rules:

- `experience_id` is unique within the study.
- `task_id` must resolve through the existing task resolver supplied to the compiler.
- Two experience IDs may reference the same task when the study deliberately repeats it.
- The role describes the study use, not the task’s domain type.

### 6.3 Ordered step union

Use a discriminated union with exactly three step types.

```python
class RunExperienceStep(StrictModel):
    kind: Literal["run_experience"] = "run_experience"
    step_id: NonEmptyStr
    experience_id: NonEmptyStr
    commit_post_state: bool | None = None


class ReleaseFeedbackStep(StrictModel):
    kind: Literal["release_feedback"] = "release_feedback"
    step_id: NonEmptyStr
    source_experience_id: NonEmptyStr
    feedback_view_id: NonEmptyStr


class ConsolidateStep(StrictModel):
    kind: Literal["consolidate"] = "consolidate"
    step_id: NonEmptyStr
    feedback_step_ids: tuple[NonEmptyStr, ...]
    operation_id: NonEmptyStr
```

`feedback_view_id` and `operation_id` are adapter-owned identifiers. The common contract does not define a universal feedback or consolidation ontology.

Compilation resolves `commit_post_state` as follows:

```text
explicit true or false  → preserve author choice
omitted probe value     → false
omitted non-probe value → true
```

A controlled study that explicitly commits probe state must be rejected unless a later step genuinely requires post-probe continuation and the study is downgraded to descriptive. Release A should prefer simply rejecting this combination.

### 6.4 Arm declaration

```python
class LearningArmSpec(StrictModel):
    arm_id: NonEmptyStr
    role: StudyArmRole
    treatment_id: NonEmptyStr
    steps: tuple[LearningStudyStep, ...]
```

Rules:

- `arm_id` is unique.
- An arm has at least one step.
- Step IDs are unique within the arm.
- `treatment_id` is interpreted by the environment adapter, not the common compiler.
- An arm is an authored sequence, not a dynamically branching workflow.

### 6.5 Experience relation

```python
class ExperienceRelationSpec(StrictModel):
    relation_id: NonEmptyStr
    purpose: ExperienceRelationPurpose
    source_experience_ids: tuple[NonEmptyStr, ...]
    target_experience_id: NonEmptyStr
    invariant_claims: tuple[NonEmptyStr, ...]
    changed_dimensions: tuple[NonEmptyStr, ...]
    rationale: NonEmptyStr
```

Release A validations:

- every source and target resolves to a declared experience;
- target is not also a source;
- composition has at least two sources;
- all other purposes have exactly one source;
- transfer and composition require at least one invariant claim;
- every relation requires at least one changed dimension;
- boundary requires `applicability` or `causal` among its changed dimensions once LS-03 establishes those labels;
- relation IDs are unique.

The compiler validates shape and references. It cannot prove the domain truth of an invariant claim.

### 6.6 Top-level study

```python
class LearningStudySpec(StrictModel):
    study_id: NonEmptyStr
    title: NonEmptyStr
    research_question: NonEmptyStr
    claim_mode: StudyClaimMode
    agent: AgentConfig
    compute: ComputeConfig
    repetitions: PositiveInt = 1
    experiences: tuple[LearningExperienceSpec, ...]
    relations: tuple[ExperienceRelationSpec, ...] = ()
    arms: tuple[LearningArmSpec, ...]
```

Release A deliberately uses one initial `AgentConfig` and one `ComputeConfig` across the study. Treatment differences are expressed through `treatment_id` and declared learner-state transitions rather than arbitrary per-arm model changes.

Measurement declarations are added by LS-02B before Release A is considered public. LS-01A should not invent a placeholder metric dictionary.

## 7. Runtime-only compiled values

Add frozen dataclasses under:

```text
src/aec_bench/experimentation/learning_studies/planning.py
```

Conceptual shape:

```python
@dataclass(frozen=True)
class CompiledExperienceStep:
    step_id: str
    experience_id: str
    role: ExperienceRole
    trial: PlannedTrial
    commit_post_state: bool


@dataclass(frozen=True)
class CompiledFeedbackStep:
    step_id: str
    source_experience_id: str
    feedback_view_id: str


@dataclass(frozen=True)
class CompiledConsolidationStep:
    step_id: str
    feedback_step_ids: tuple[str, ...]
    operation_id: str


@dataclass(frozen=True)
class PlannedArmRun:
    arm_run_id: str
    arm_id: str
    arm_role: StudyArmRole
    treatment_id: str
    repetition: int
    steps: tuple[CompiledStudyStep, ...]


@dataclass(frozen=True)
class CompiledLearningStudy:
    study_run_id: str
    spec: LearningStudySpec
    arm_runs: tuple[PlannedArmRun, ...]
```

Names may change during implementation if repository conventions demand it, but the ownership and information boundaries may not.

## 8. Compiler API

Provide one direct function:

```python
def compile_learning_study(
    *,
    study_run_id: str,
    spec: LearningStudySpec,
    resolve_task: Callable[[str], ResolvedTaskInstance],
) -> CompiledLearningStudy:
    ...
```

If the current resolver needs a root or catalogue argument, bind that dependency at the call site rather than embedding repository discovery into the compiler.

The compiler is pure with respect to execution:

- no model calls;
- no workspace creation;
- no ledger writes;
- no task mutation;
- no random task choice;
- no adaptive branching.

## 9. Trial compilation

For each `RunExperienceStep`, the compiler creates one exact `PlannedTrial` using existing planning and identity helpers.

### 9.1 Required identity components

Each planned experience must be unambiguous across:

- study run;
- arm;
- repetition;
- experience;
- repeated uses of the same experience within an arm.

Use a readable caller-owned experiment identity derived from those declared values. For example:

```text
<study_run_id>--<arm_id>--r<repetition>--<step_id>
```

The normal trial ID helper then creates the ordinary `trial_id`.

Do not include content hashes, timestamps, or generated schema versions in identity.

### 9.2 Repetition semantics

`repetitions = N` expands each authored arm into `N` independent `PlannedArmRun` values.

For repetition `r`:

- every arm receives one arm run with the same repetition number;
- the number is the matched comparison key used later by LS-02B;
- learner state never carries between repetitions;
- the number does not claim that provider sampling randomness is identically seeded unless the provider separately guarantees that.

### 9.3 Reusing `PlannedTrial`

Do not define a second persisted trial field list in the learning package.

Before implementation, prove that the existing `PlannedTrial` can be round-tripped through the repository’s chosen plan serializer. If direct Pydantic support is insufficient, add one canonical serialisation helper alongside `PlannedTrial` in `trials.py` and reuse it everywhere. Do not create an independently maintained `LearningPlannedTrial` schema.

## 10. Static validation

Compilation must fail before any execution when any of the following holds.

### 10.1 Identity errors

- empty or duplicate study, experience, relation, arm, or step IDs;
- duplicate resulting arm-run or trial IDs;
- a study run ID that cannot be represented safely in normal path or record identity rules.

### 10.2 Reference errors

- unresolved task ID;
- step references an undeclared experience;
- feedback references an experience not yet run in that arm;
- consolidation references a missing or later feedback step;
- relation references undeclared experiences.

### 10.3 Order errors

- an experience is used as feedback source before it runs;
- a feedback step releases the same view from the same experience twice in one arm without an explicit future use case;
- consolidation has no feedback inputs;
- a controlled probe commits post-state;
- a step follows a non-committing probe and assumes probe-created state.

### 10.4 Controlled-study shape errors

LS-01A performs only structural checks:

- controlled mode requires at least one control arm and one exposure arm;
- every arm used in a future comparison must contain the relevant probe experience;
- a control arm cannot contain the acquisition experience that defines the intended exposure contrast unless the later assessment explicitly treats it as a different comparator.

Detailed comparison validity remains LS-02B’s responsibility.

### 10.5 Unsupported Release A features

Reject:

- dynamic branches;
- loops;
- adaptive next-task selectors;
- per-arm model changes;
- model-weight update steps;
- mixed execution families in one arm;
- unknown step kinds.

## 11. Error model

Add bounded planning errors under the learning-study owner, for example:

```text
LearningStudySpecInvalid
LearningStudyReferenceInvalid
LearningStudyOrderInvalid
LearningStudyTaskResolutionFailed
LearningStudyPlanCollision
LearningStudyFeatureUnsupported
```

Use existing repository error conventions where available. Errors must include:

- study ID;
- arm and step ID when relevant;
- the violated rule;
- no hidden task or verifier data.

Do not collapse all failures into `ValueError` at the public boundary.

## 12. Worked example

Authored study:

```yaml
study_id: drainage-transfer
claim_mode: controlled
repetitions: 3
experiences:
  - experience_id: acquire
    task_id: drainage-case-a
    role: acquisition
  - experience_id: probe
    task_id: drainage-case-b
    role: probe
arms:
  - arm_id: cold
    role: control
    treatment_id: reset
    steps:
      - kind: run_experience
        step_id: cold-probe
        experience_id: probe
  - arm_id: memory
    role: exposure
    treatment_id: structured-memory
    steps:
      - kind: run_experience
        step_id: acquire-task
        experience_id: acquire
      - kind: release_feedback
        step_id: acquire-feedback
        source_experience_id: acquire
        feedback_view_id: public-evaluation
      - kind: consolidate
        step_id: consolidate-lesson
        feedback_step_ids: [acquire-feedback]
        operation_id: update-memory
      - kind: run_experience
        step_id: transfer-probe
        experience_id: probe
relations:
  - relation_id: same-method-new-surface
    purpose: transfer
    source_experience_ids: [acquire]
    target_experience_id: probe
    invariant_claims:
      - governing calculation method is unchanged
    changed_dimensions: [surface, parameter]
    rationale: tests whether prior method use helps under changed representation
```

Compilation produces six independent arm runs:

```text
cold:r0      memory:r0
cold:r1      memory:r1
cold:r2      memory:r2
```

and one ordinary `PlannedTrial` for every `RunExperienceStep` in each arm run.

## 13. File changes

Expected additions:

```text
src/aec_bench/contracts/learning_study.py
src/aec_bench/experimentation/learning_studies/planning.py
tests/contracts/test_learning_study.py
tests/experimentation/learning_studies/test_planning.py
```

Expected modifications:

```text
src/aec_bench/contracts/__init__.py          # only if current export conventions require it
src/aec_bench/experimentation/learning_studies/__init__.py
src/aec_bench/trials.py                      # only for one canonical PlannedTrial serializer if required
```

Do not add environment adapters in this PRD.

## 14. Test matrix

### Contract tests

- strict round-trip for every model;
- duplicate identifiers rejected;
- unsupported step kind rejected;
- empty tuple and empty string rules enforced;
- probe commit default resolves correctly during compilation.

### Planning tests

- deterministic compilation with identical inputs;
- exact number of arm runs and trials;
- readable unique identities;
- same task referenced by several experiences remains unambiguous;
- repetitions do not share learner identity or trial ID;
- task-resolution failure identifies the experience;
- source-before-feedback ordering enforced;
- composition cardinality enforced;
- controlled mode requires control and exposure arms.

### Architecture tests

- contract module imports no experimentation implementation;
- planning module imports no artifact, lifecycle, or world implementation;
- no new runtime family appears.

### Regression tests

- ordinary `plan_trials()` and existing trial IDs are unchanged outside learning studies;
- existing experiment manifests and task execution remain loadable.

## 15. Acceptance criteria

LS-01A is complete when:

1. A strict authored `LearningStudySpec` can represent the finite Release A study language.
2. Compilation resolves every task and produces one exact existing `PlannedTrial` per experience step.
3. The same spec and study-run ID compile identically.
4. Repetitions expand into isolated, pairable arm runs.
5. Invalid references and ordering fail before execution.
6. Probe state is non-committing by default.
7. No duplicate trial model, task resolver, execution runtime, metric schema, or model-update mechanism has been added.
8. Existing planning and execution tests remain unchanged in behaviour.

## 16. Agent handoff

The implementation agent should return:

- the final field-level contract;
- any deviation from the conceptual names above and the repository convention that required it;
- the exact trial-identity construction;
- compiler validation inventory;
- proof of `PlannedTrial` round-trip or the one canonical serializer added;
- tests demonstrating deterministic compilation and collision-free repetitions.
