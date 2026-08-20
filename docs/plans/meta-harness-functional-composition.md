# Meta-Harness Functional Composition PRD

| Field | Value |
| --- | --- |
| Class | Plan |
| Status | Proposed |
| Audience | Experimentation, harness, evaluation, lifecycle, world, and CLI contributors |
| Owner | Repository maintainers |

This document is a proposed plan. It is not current architecture. The current
[architecture](../ARCHITECTURE.md), [contracts](../CONTRACTS.md), and
[invariants](../INVARIANTS.md) remain the authority until implementation
changes them.

## Purpose

Create one functional Python API for designing, testing, comparing, and
refining harness candidates.

The API works above execution runtimes. It does not run an artifact task,
lifecycle, or interactive world itself. A caller supplies a function that can
evaluate one candidate and return `TrialRecord` values. This keeps the
meta-harness independent from the execution model while letting every runtime
participate through its normal experiment path.

The intended flow is:

```text
current harness
-> propose candidate harnesses
-> test candidates through a supplied evaluator
-> assess their TrialRecords
-> select and optionally refine a candidate
-> stop or repeat
```

Functional composition here means explicit function inputs and direct return
values. Candidate execution, model calls, workspaces, and artifact persistence
can still have effects.

## Product outcome

A Python caller can run one comparison:

```python
study = run_harness_study(
    baseline=baseline,
    candidates=candidates,
    evaluate=evaluate_candidate,
    assess=assess_candidates,
)
```

A caller can also run a bounded propose-test-refine process:

```python
result = run_meta_harness(
    initial=baseline,
    propose=propose_candidates,
    evaluate=evaluate_candidate,
    assess=assess_candidates,
    select=select_candidate,
    refine=refine_candidate,
    stop=stop_when_sufficient,
    max_rounds=3,
)
```

The candidate value is selected by the caller. It can contain an artifact-task
`HarnessSpec`, a lifecycle treatment, a world actor configuration, a program
candidate, or another current harness input. The meta-harness records the
candidate identity but does not inspect or interpret the value.

The evaluator is the only runtime connection:

```python
type CandidateEvaluator[CandidateT] = Callable[
    [HarnessCandidate[CandidateT]],
    Sequence[TrialRecord],
]
```

The result contains all candidate evaluations, assessments, selections, and
the final selected candidate. It does not return a runner, manager, or mutable
orchestrator that needs another `.run()` call.

## Non-goals

- A universal runtime, environment base class, or common task state model.
- Making artifact tasks, lifecycles, and interactive worlds share execution
  functions or candidate values.
- Moving lifecycle or world semantics into `experimentation`.
- A plugin registry, dependency-injection container, event bus, or generic
  workflow language.
- A universal persisted candidate, assessment, or meta-harness schema.
- Versioned internal operation names or compatibility aliases.
- Moving all proposal, execution, evaluation, study, or governance code into
  one `meta_harness` package.
- Treating task prose intake or problem-model generation as a required stage
  for every meta-harness run.
- Making governance or promotion mandatory for an in-process comparison.
- Letting the meta-harness reinterpret task completion, validity, reward, or
  runtime-specific evidence.
- Adding a second evolution engine. Existing evolution can supply proposal or
  refinement functions.
- Implementing a lifecycle or interactive-world experiment API in this plan.
- Moving lifecycle CLI commands. The lifecycle functional composition plan
  owns that change.
- Requiring publication, a ledger write, or a durable study report for a
  direct Python call.
- Running paid models, hosted evaluations, or provider qualification during
  implementation.

## Dependency and decision boundary

The core meta-harness API depends only on:

- runtime-neutral candidate wrappers defined by this plan;
- `TrialRecord`, which is already the common reportable trial value; and
- callables supplied by the caller.

It does not depend on completion of the lifecycle work. The artifact-task
composition plan supplies the first simple evaluator through
`run_experiment()`. Existing harness-program studies can also supply an
evaluator while that task work is in progress.

The separate lifecycle composition plan will:

- organise lifecycle execution as functions;
- consolidate the lifecycle CLI under `aec-bench task lifecycle`;
- produce lifecycle `TrialRecord` values through one normal experiment path;
  and
- provide a lifecycle candidate evaluator for this API.

Interactive worlds can add the same small bridge after their experiment path
has a suitable functional entry point. No change to the meta-harness core is
needed for that later integration.

This plan changes internal pre-1.0 Python code directly. It does not preserve
superseded runners, process orchestrators, comparison helpers, or private
imports as aliases.

## Plain terms

| Term | Meaning |
| --- | --- |
| Harness candidate | A named candidate plus a caller-owned value that describes the harness behaviour under test. |
| Candidate evaluator | A function that executes one candidate through the correct runtime and returns its `TrialRecord` values. |
| Candidate trials | One candidate and the records returned by its evaluator call. |
| Assessment | A caller-owned interpretation of a current candidate and proposed candidate trials. |
| Selection | The choice of one already evaluated candidate after assessment. |
| Refinement | Creation of the next candidate from a selected candidate and assessment. |
| Harness study | One baseline-versus-candidates evaluation with no refinement loop. |
| Meta-harness round | Proposal, evaluation, assessment, and selection performed once. |
| Meta-harness run | One initial candidate followed by a bounded sequence of rounds. |

`HarnessCandidate` does not replace `HarnessSpec`. `HarnessSpec` is one
possible candidate value. The wrapper supplies only the identity needed to
organise a study.

## Current evidence

### Ownership is already separated

The repository architecture deliberately removed the old
`aec_bench.meta_harness` umbrella package. Current ownership is:

| Capability | Owner |
| --- | --- |
| Model and candidate execution | `harness` |
| Problem intake and process-stage coordination | `harness.process_runtime` and `harness.model_execution` |
| Program proposal and execution studies | `experimentation.proposals` |
| Candidate comparison and qualification | `experimentation.qualification` |
| Acceptance, promotion, and monitoring policy | `experimentation.governance` |
| Scoring and evaluation interpretation | `evaluation` |
| Artifact-task, lifecycle, and world behaviour | Their respective task-family owners |

The public `aec-bench meta-harness` CLI composes these owners. There is no
current Python facade that represents the full product operation.

### The process runtime is a staged design workflow

`harness.process_runtime.world_runtime.run_process()` currently coordinates:

```text
task prose
-> problem brief
-> generated problem model
-> externally supplied task run
-> review and logic evaluation
-> proposed operation
-> governance decision
```

It pauses when a stage input is absent. It can run configured model endpoints
and write a process log. It does not execute a normal multi-trial candidate
study. Its use of `world` means a generated problem representation, not an
AEC-Bench interactive world.

### The comparison recipe is narrow

`experimentation.qualification.recipe` can materialise a scriptable workspace
and compare one baseline run JSON file with one candidate run JSON file. It is
useful as a CLI and agent example, but it does not call the normal experiment
path or support a general refinement process.

### Harness-program studies execute real trials

`experimentation.qualification.harness_program_study` materialises candidate
programs, runs repeated Harbor trials, analyses `TrialRecord` values, and
writes a verified report. It is a real meta-harness consumer, but its public
surface is specialised for fixed-kernel program studies and Harbor.

### Adaptive cycles already contain the intended loop

`experimentation.qualification.adaptive_cycle_runtime.run_adaptive_cycle()`
currently performs a source study, diagnosis, repair, a child study, and motif
learning. This is the closest current implementation of test-assess-refine.
It is tied to its qualification, repair, motif, and Harbor contracts rather
than exposing the general functional seam.

### The CLI mixes unrelated lifecycle operations

`aec-bench meta-harness` currently includes intake, review, operation,
governance, comparison, lifecycle host controls, and lifecycle studies. The
lifecycle commands call lifecycle-owned functions, but their CLI location
makes them appear to be required meta-harness stages.

The lifecycle plan will move those commands. This plan can then make the
remaining command family describe only higher-order harness work.

## Required functional composition

The dependency direction is:

```text
runtime-specific candidate value
-> runtime-specific CandidateEvaluator
-> TrialRecords
-> runtime-neutral study and refinement functions
-> caller-owned assessment and next candidate
```

The direction never reverses. Artifact-task, lifecycle, and world packages do
not import meta-harness policy to run ordinary work.

### Candidate values remain runtime-specific

The meta-harness adds only a small wrapper:

```python
@dataclass(frozen=True)
class HarnessCandidate[CandidateT]:
    candidate_id: str
    value: CandidateT
```

`candidate_id` is non-empty and unique for one distinct candidate in a
meta-harness run. When refinement changes the candidate value, it creates a
new candidate identity.

The API does not serialize `value`, compare it for equality, calculate an
identity from it, or constrain its type. Runtime-specific callers validate
their own values before execution.

### Candidate evaluation has one shape

```python
type CandidateEvaluator[CandidateT] = Callable[
    [HarnessCandidate[CandidateT]],
    Sequence[TrialRecord],
]


@dataclass(frozen=True)
class HarnessCandidateTrials[CandidateT]:
    candidate: HarnessCandidate[CandidateT]
    records: tuple[TrialRecord, ...]
```

The application function normalises the returned sequence to a tuple and
rejects an empty result or duplicate `trial_id` values. It does not require
successful execution or a positive reward. Failed and invalid trials remain
evidence for the assessor.

Runtime-specific evaluators remain responsible for:

- selecting and resolving the task, lifecycle, or world inputs;
- selecting the agent, model, adapter, tools, limits, and treatment;
- executing the candidate through the normal runtime path;
- verifying and importing the resulting records; and
- proving that the records belong to the candidate evaluation they report.

### Assessment remains caller-owned

Different studies need different comparisons. The core API does not invent a
universal score or assessment schema.

```python
type CandidateAssessor[CandidateT, AssessmentT] = Callable[
    [
        HarnessCandidateTrials[CandidateT],
        tuple[HarnessCandidateTrials[CandidateT], ...],
    ],
    AssessmentT,
]
```

An assessor can use the existing evaluation summary, a lifecycle treatment
comparison, a world trajectory analysis, a program-study report, or a direct
custom calculation. Evaluation continues to own metric meaning. The
meta-harness only calls the assessor and retains its returned value in memory.

### Selection chooses evaluated work

```python
type CandidateSelector[CandidateT, AssessmentT] = Callable[
    [
        HarnessCandidateTrials[CandidateT],
        tuple[HarnessCandidateTrials[CandidateT], ...],
        AssessmentT,
    ],
    HarnessCandidate[CandidateT],
]
```

The selector must return the current candidate or one candidate from the
evaluated candidate set. It cannot select an unevaluated value. The runner
checks the selected `candidate_id` before it records the round.

### Refinement creates the next candidate

```python
type CandidateRefiner[CandidateT, AssessmentT] = Callable[
    [HarnessCandidate[CandidateT], AssessmentT],
    HarnessCandidate[CandidateT],
]
```

Refinement can be a model call, deterministic transformation, human-reviewed
operation, or existing evolution function. When another round is required,
the returned candidate has a new identity and is evaluated as the current
candidate for that round.

The meta-harness does not know which fields changed or apply patches itself.

### Proposal and stopping are explicit

```python
type CandidateProposer[CandidateT, AssessmentT] = Callable[
    [HarnessCandidate[CandidateT], AssessmentT | None],
    Sequence[HarnessCandidate[CandidateT]],
]

type MetaHarnessStop[CandidateT, AssessmentT] = Callable[
    [MetaHarnessRound[CandidateT, AssessmentT]],
    bool,
]
```

Each proposal call returns at least one candidate. Candidate identities in one
proposal are unique and do not reuse the current candidate identity for a
different value.

`max_rounds` is always required and positive. It is the outer safety bound.
The stop function can end the run earlier after an assessed and selected
candidate exists.

### Results are normal in-memory values

```python
@dataclass(frozen=True)
class HarnessStudyResult[CandidateT, AssessmentT]:
    baseline: HarnessCandidateTrials[CandidateT]
    candidates: tuple[HarnessCandidateTrials[CandidateT], ...]
    assessment: AssessmentT


@dataclass(frozen=True)
class MetaHarnessRound[CandidateT, AssessmentT]:
    round_index: int
    study: HarnessStudyResult[CandidateT, AssessmentT]
    selected: HarnessCandidateTrials[CandidateT]


@dataclass(frozen=True)
class MetaHarnessResult[CandidateT, AssessmentT]:
    initial: HarnessCandidateTrials[CandidateT]
    rounds: tuple[MetaHarnessRound[CandidateT, AssessmentT], ...]
    selected: HarnessCandidateTrials[CandidateT]
    stop_reason: str
```

These values are Python composition results. They are not new persisted
contracts. A specialised study can write its existing report after the
function returns.

## Proposed public Python API

The facade belongs at `aec_bench.experimentation.meta_harness`:

```python
from aec_bench.experimentation.meta_harness import (
    HarnessCandidate,
    HarnessCandidateTrials,
    HarnessStudyResult,
    MetaHarnessResult,
    MetaHarnessRound,
    evaluate_harness_candidate,
    run_harness_study,
    run_meta_harness,
)
```

The module is a composition facade. It does not become the physical owner of
proposal, runtime, evaluation, lifecycle, world, or governance behaviour.

### Evaluate one candidate

```python
def evaluate_harness_candidate(
    candidate: HarnessCandidate[CandidateT],
    *,
    evaluate: CandidateEvaluator[CandidateT],
) -> HarnessCandidateTrials[CandidateT]: ...
```

This is the only place where the core calls a runtime-specific evaluator. Both
the one-shot study and iterative runner use it.

### Run one study

```python
def run_harness_study(
    *,
    baseline: HarnessCandidate[CandidateT],
    candidates: Sequence[HarnessCandidate[CandidateT]],
    evaluate: CandidateEvaluator[CandidateT],
    assess: CandidateAssessor[CandidateT, AssessmentT],
) -> HarnessStudyResult[CandidateT, AssessmentT]: ...
```

The function evaluates the baseline and every candidate once, then calls the
assessor. A caller that already has candidate records can use the assessor
directly; the API does not add a second file-based comparison engine.

### Run a bounded refinement process

```python
def run_meta_harness(
    *,
    initial: HarnessCandidate[CandidateT],
    propose: CandidateProposer[CandidateT, AssessmentT],
    evaluate: CandidateEvaluator[CandidateT],
    assess: CandidateAssessor[CandidateT, AssessmentT],
    select: CandidateSelector[CandidateT, AssessmentT],
    refine: CandidateRefiner[CandidateT, AssessmentT],
    stop: MetaHarnessStop[CandidateT, AssessmentT],
    max_rounds: int,
) -> MetaHarnessResult[CandidateT, AssessmentT]: ...
```

The runner:

1. evaluates the initial candidate;
2. asks the proposer for candidates;
3. evaluates each proposed candidate;
4. asks the assessor to interpret current and candidate trials;
5. asks the selector to choose evaluated work;
6. records the complete round;
7. stops if the stop function accepts the round or the bound is reached; and
8. otherwise asks the refiner for the next current candidate and repeats.

The result always selects evaluated work. A refined candidate becomes an
input to the next round; it cannot become the final result before evaluation.

Expected run failures belong in returned `TrialRecord` values. Invalid
callback outputs raise direct exceptions. The API does not convert programming
errors or infrastructure exceptions into successful study results.

## Runtime-specific composition examples

### Artifact tasks

After the artifact-task composition plan is complete:

```python
def evaluate_task_candidate(
    candidate: HarnessCandidate[TaskHarnessCandidate],
) -> list[TrialRecord]:
    value = candidate.value
    return run_experiment(
        runtime=value.runtime,
        tasks=value.tasks,
        trials=value.trials,
        recipe=value.attempt_recipe,
    )
```

The meta-harness can compare agent configuration, tools, context, limits, or
attempt recipes without adding a branch to `run_experiment()`.

### Lifecycles

The lifecycle plan will supply an equivalent evaluator:

```python
def evaluate_lifecycle_candidate(
    candidate: HarnessCandidate[LifecycleHarnessCandidate],
) -> list[TrialRecord]:
    return run_lifecycle_experiment(candidate.value)
```

Lifecycle candidate values can select supported treatments such as model
context continuity, visibility, operations, or branch policy. Lifecycle
progression remains lifecycle-owned.

There is no `LifecycleMetaHarness` class. Lifecycle-specific proposal,
assessment, and refinement functions plug into the same generic API.

### Interactive worlds

A later world experiment function can supply:

```python
def evaluate_world_candidate(
    candidate: HarnessCandidate[WorldHarnessCandidate],
) -> list[TrialRecord]:
    return run_world_experiment(candidate.value)
```

World state, actions, transitions, controls, persistence, and replay remain
world-owned. The meta-harness receives only completed trial records.

### Evolution as refinement

Evolution remains a separate domain. It can provide candidate proposal or
refinement:

```python
result = run_meta_harness(
    initial=baseline,
    propose=propose_with_evolution,
    evaluate=evaluate_task_candidate,
    assess=assess_candidates,
    select=select_candidate,
    refine=refine_with_evolution,
    stop=stop_when_sufficient,
    max_rounds=3,
)
```

The meta-harness does not copy evolution archives, strategies, mutation, or
convergence policy.

## Existing machinery migration

The new API replaces overlapping orchestration. It does not sit beside the
current implementations indefinitely.

| Current capability | Migration target |
| --- | --- |
| `qualification.recipe.compare_harness_runs()` | Use the common assessor and `run_harness_study()` path. Keep file loading and report writing as CLI I/O only. |
| `qualification.recipe.run_harness_comparison_from_files()` | Load files, create candidate-trial values, call the common comparison, and write the result. Remove its separate comparison calculation. |
| `harness_program_study` | Use candidate evaluation and study composition while retaining its program materialisation, Harbor execution, analysis, and report contract. |
| `adaptive_cycle_runtime` | Express source evaluation, repair/refinement, child evaluation, and stopping through the common functions. Keep motif learning and promotion after the returned result. |
| `repair_runtime` | Supply refinement and runtime-specific evidence functions. Remove loop control that the common runner replaces. |
| `process_runtime.run_process()` | Decompose into intake/proposal/review/refinement helpers and one supported built-in composition. Remove the competing staged orchestrator after callers move. |
| `process_runtime.autonomy` | Become a bounded proposal/refinement policy over `run_meta_harness()` or be removed when it has no separate behaviour. |
| `model_execution` | Stay under `harness` and provide proposer, assessor, or refiner callables. |
| `experimentation.proposals` | Stay proposal-owned and supply candidate-generation functions. |
| `experimentation.governance` | Stay governance-owned and run after an assessment or selected result when a workflow requires approval. |

The migration must first preserve useful tests at the new function boundary.
It then removes the old orchestration path and stale tests. It does not add a
compatibility wrapper with the old implementation behind it.

The old `world` name in `harness.process_runtime` means problem model. Rename
that value and its internal modules when the process callers migrate. Do not
use it as evidence that this API depends on an interactive-world runtime.

## CLI composition

The public `aec-bench meta-harness` command remains useful for humans and
agents. It is a presentation and composition surface over the Python API.

The CLI follows these rules:

- `recipe`, `compare`, and `example` use the same study and assessment
  functions as Python callers;
- a supported bounded process uses `run_meta_harness()` rather than a second
  command-owned loop;
- stage commands can expose useful intake, proposal, review, or refinement
  functions without becoming a required universal sequence;
- model configuration, file loading, and output writing stay in CLI or
  application assembly code;
- the CLI does not accept arbitrary import strings for callbacks;
- custom candidate values and callables remain a Python API capability; and
- lifecycle commands leave this command family in the lifecycle plan.

The first API implementation does not need a universal `meta-harness.yaml`.
Existing supported concrete recipes can keep their current configuration until
their migration proves a smaller shared input.

After migration, no CLI command owns candidate execution, comparison, or
refinement logic that is also implemented in the library.

## Ownership and dependency direction

| Concern | Owner |
| --- | --- |
| Runtime-neutral candidate wrapper and functional composition | `aec_bench.experimentation.meta_harness` |
| Artifact-task execution | `harness.artifact_tasks` and its runtime implementations |
| Lifecycle execution and progression | `lifecycles` plus lifecycle harness integrations |
| Interactive-world state and execution | `worlds` plus world harness integrations |
| Model execution | `harness.model_execution` |
| Candidate proposal policy | `experimentation.proposals` or the concrete caller |
| Study and qualification policy | `experimentation.qualification` |
| Metric meaning | `evaluation` and task-family evaluation owners |
| Evolution strategy | `evolution` |
| Approval and promotion policy | `experimentation.governance` |
| CLI parsing and rendering | `cli` |

`experimentation.meta_harness` can import runtime-neutral contracts and call
injected functions. It does not import lifecycle catalogues, concrete worlds,
adapters, providers, Harbor, Prime, or task-specific evaluation modules.

Runtime-specific adapter functions live with their current experiment or
harness integration. They import the meta-harness callable types only when
that improves their public signature; ordinary runtime execution does not
depend on meta-harness composition.

## Delivery slices

### Slice 1: Functional core

- Add `HarnessCandidate`, `HarnessCandidateTrials`, `HarnessStudyResult`,
  `MetaHarnessRound`, and `MetaHarnessResult` as normal generic dataclasses.
- Add the callable type aliases.
- Implement `evaluate_harness_candidate()` and `run_harness_study()`.
- Implement `run_meta_harness()` with explicit `max_rounds`.
- Add deterministic unit tests with `TrialRecord` fixtures and no model calls.

### Slice 2: First real study migration

- Migrate the simple candidate-versus-baseline comparison recipe.
- Reuse current evaluation functions for metric meaning.
- Keep file loading, Markdown, JSON, and script materialisation at the recipe
  boundary.
- Delete the separate comparison implementation.

### Slice 3: Harness-program study migration

- Adapt the current harness-program study to the functional study boundary.
- Keep its current candidate materialisation, Harbor execution, analysis, and
  report behaviour.
- Remove duplicate candidate iteration and record-normalisation logic when the
  common functions replace it.
- Prove the existing report still derives from the same accepted records.

### Slice 4: Adaptive refinement migration

- Express current candidate proposal, evaluation, selection, and repair as
  supplied functions.
- Make the adaptive cycle call `run_meta_harness()` for the overlapping loop.
- Keep specialised diagnosis, patch creation, motif learning, and governance
  with their present owners.
- Delete superseded loop orchestration and object lifecycle code.

### Slice 5: Process and CLI rewiring

- Reuse intake, problem-model, review, operation, and model-execution helpers
  as optional callable building blocks.
- Replace or remove `run_process()` and its autonomous wrapper after all
  current callers use the functional API.
- Rewire the non-lifecycle `meta-harness` commands to library functions.
- Update the installed meta-harness skill and root README examples.
- Do not move lifecycle commands in this slice; the lifecycle plan owns that
  public CLI cutover.

### Slice 6: Runtime-family integrations

- Add the artifact-task evaluator after `run_experiment()` is available.
- Add the lifecycle evaluator when the lifecycle composition plan completes.
- Add a world evaluator only when a real world experiment entry point exists.
- Keep these as small caller-owned functions. Do not add a universal runtime
  adapter registry.

## Acceptance criteria

1. Python callers can evaluate one candidate with one supplied function and
   receive its `TrialRecord` values in a typed result.
2. Python callers can run a baseline-versus-candidates study with one function.
3. Python callers can run a bounded propose-evaluate-assess-select-refine loop
   with one function.
4. `max_rounds` always bounds the iterative process.
5. The final selected candidate has completed evaluation evidence.
6. The result retains every candidate evaluation performed by the common
   runner, including failed and invalid trials.
7. Candidate callbacks receive caller-owned candidate values without a common
   runtime schema.
8. Assessment values remain caller-owned and are not forced into one metric
   model.
9. The functional core imports no artifact-task, lifecycle, interactive-world,
   adapter, provider, Harbor, or Prime implementation.
10. Artifact-task execution can participate through `run_experiment()` without
    changing the meta-harness core.
11. Lifecycle execution can later participate through one evaluator function
    without a `LifecycleMetaHarness` implementation.
12. Interactive worlds can later participate through the same evaluator shape
    without a universal environment runtime.
13. The comparison recipe uses the common study path and has no second
    comparison calculation.
14. Harness-program studies use the common candidate evaluation or study
    functions where their behaviour overlaps.
15. Adaptive refinement uses the common loop where its behaviour overlaps and
    retains only its specialised study policy.
16. Model execution, proposals, evaluation, evolution, and governance remain
    with their current owners.
17. The current process runtime is decomposed or removed; it does not remain as
    a competing full meta-harness orchestrator.
18. The public `meta-harness` CLI calls the same library functions as Python
    callers for supported workflows.
19. The CLI does not introduce arbitrary callback import configuration or a
    generic workflow language.
20. No version-suffixed operations, compatibility aliases, plugin registry, or
    dependency-injection framework is added.
21. Superseded production code and tests are removed after their current
    callers migrate.
22. No persisted task, dataset, trial, lifecycle, world, or study format
    changes only to support direct functional composition.

## Verification

Use deterministic and provider-free checks:

- unit tests for candidate validation and record normalisation;
- unit tests for one-shot studies, selection, refinement, early stop, and
  maximum-round stop;
- tests for empty candidate sets, duplicate candidate identities, empty record
  sets, duplicate trial identities, and selection of unevaluated candidates;
- comparison-recipe tests using existing local fixtures;
- harness-program study tests using current test executors;
- adaptive-cycle and repair tests using current deterministic executors;
- CLI tests that prove commands call the library surface;
- import-boundary tests that reject runtime-family imports from the functional
  core; and
- existing documentation and installed-skill tests after CLI examples change.

Do not run paid models, hosted Harbor execution, Prime, Morph Cloud, or another
credentialed provider as part of normal verification.

## Decisions made by this plan

- The meta-harness is runtime-agnostic and uses a supplied evaluator function.
- `TrialRecord` is the common completed-trial evidence passed to assessment.
- Candidate and assessment values remain caller-owned.
- The public facade belongs under `experimentation`, while concrete behaviour
  remains with its current owners.
- The API supports both one-shot studies and bounded iterative refinement.
- Evolution can participate as proposal or refinement policy; it is not
  duplicated.
- Direct Python composition does not require a persisted meta-harness format.
- Lifecycle CLI relocation and lifecycle experiment composition belong to a
  separate lifecycle plan.

## Completion and retirement

When implementation is complete:

1. update current architecture and public documentation to describe the
   implemented API and CLI;
2. update contracts only if implementation introduces a real supported or
   persisted boundary change;
3. delete this plan, or retain only a concise historical rationale when it is
   still useful; and
4. keep runtime-family protocols with their own owners rather than copying
   this plan into them.
