# Lifecycle Functional Composition PRD

| Field | Value |
| --- | --- |
| Class | Plan |
| Status | Historical |
| Audience | Lifecycle, harness, experimentation, evaluation, and CLI contributors |
| Owner | Repository maintainers |

This document records the completed functional-composition change. It is not
current architecture. The current
[architecture](../ARCHITECTURE.md), [contracts](../CONTRACTS.md),
[invariants](../INVARIANTS.md), and
[staged evidence protocol](../protocols/staged-evidence-and-publication.md)
are the authority for the implemented behaviour.

## Purpose

Give finite staged lifecycles one direct functional API for checkpoint control,
execution, branching, trial finalisation, and experiments.

The current lifecycle coordinator already protects the important task rules:
the host releases checkpoints, the actor submits work, prior accepted work does
not change, and verification runs after lifecycle progression. The problem is
that application composition is split across the lifecycle runtime, local
harness, lifecycle studies, and `meta-harness` CLI.

This plan keeps the existing coordinator and makes it the only implementation
path:

```text
materialised lifecycle package
-> release and complete ordered checkpoints
-> verify the completed lifecycle
-> build one TrialRecord
-> apply the same operation across planned lifecycle trials
```

Branching is part of lifecycle execution. Meta-harness comparison is not. A
lifecycle experiment can later become one evaluator supplied to the separate
[meta-harness functional API](../ARCHITECTURE.md#meta-harness-composition).

Functional composition here means explicit functions, callable execution
effects, and direct result values. Lifecycle state and artifacts remain
durable because recovery and accepted evidence need those semantics.

## Product outcome

A Python caller can control one lifecycle directly:

```python
context = release_checkpoint(
    package_dir=package_dir,
    run_dir=run_dir,
    operation_resolver=operation_resolver,
)

context = submit_checkpoint(
    package_dir=package_dir,
    run_dir=run_dir,
    operation_resolver=operation_resolver,
)
```

A caller can run all checkpoints through a fresh-context episode environment:

```python
state = run_lifecycle(
    package_dir=package_dir,
    run_dir=run_dir,
    episode_environment=environment,
    operation_resolver=operation_resolver,
)
```

A caller can execute and finalise one reportable trial:

```python
record = run_lifecycle_trial(
    trial=lifecycle_trial,
    execute=execute_trial,
    verify=verify_lifecycle,
)
```

A caller can run several planned trials:

```python
records = run_lifecycle_experiment(
    trials=trials,
    execute=execute_trial,
    verify=verify_lifecycle,
)
```

These functions return state or `TrialRecord` values. They do not return a
runner, manager, or mutable orchestrator that needs another `.run()` call.

## Non-goals

- A common runtime for artifact tasks, finite lifecycles, and interactive
  worlds.
- Treating a lifecycle as an artifact-task `AttemptRecipe` or an interactive
  world episode.
- A general workflow graph, parallel checkpoints, or actor-selected
  progression. Current lifecycles use an ordered checkpoint list.
- Starting a new run at an arbitrary later checkpoint without accepted prior
  evidence.
- Rewinding or mutating a submitted checkpoint in its original run.
- Combining fresh-context and persistent-context execution into one false
  episode model.
- A plugin registry, environment registry, dependency-injection container,
  event bus, or generic workflow language.
- Moving task-owned submission fields, calculations, operations, variants, or
  verification into the shared lifecycle runtime.
- Making conditional evidence or lifecycle operations mandatory for every
  lifecycle.
- Adding a second lifecycle state or checkpoint schema only for the Python
  facade.
- A new persisted lifecycle, trial, branch, or study format as a side effect
  of functional composition.
- Making ledger publication a requirement for direct Python execution.
- Replacing Prime, Harbor, local adapter, or task-specific lifecycle
  integrations with one universal adapter.
- Implementing the meta-harness loop. This plan supplies only the lifecycle
  evaluator used by that separate API.
- Preserving old internal function names or `meta-harness lifecycle-*` CLI
  routes as compatibility aliases.
- Running paid models, hosted evaluation, or provider qualification during
  implementation.

## Dependency and decision boundary

This plan reuses:

- `EvidenceLifecycleSpec` and its ordered checkpoints;
- `EvidenceLifecycleRunState` and existing checkpoint, attempt, branch,
  request, operation, and transition records;
- `LifecycleEpisodeEnvironment` for fresh-context checkpoint execution;
- `LifecycleExecutionMode` and `LifecycleVisibilityPolicy`;
- `PlannedTrial`, `AgentConfig`, and `ComputeConfig` for normal experiment
  planning;
- lifecycle-owned materialisers, operation resolvers, and verifiers; and
- the core `TrialRecord` plus its current lifecycle extensions.

The plan does not depend on the meta-harness implementation. It can land after
or alongside the artifact-task composition work. If `PlannedTrial` changes
under that selected task plan, lifecycle composition uses the final direct
type rather than introducing another copy.

The separate meta-harness plan depends only on a lifecycle evaluator that
returns `TrialRecord` values. It does not import lifecycle packages or state.

This plan changes internal pre-1.0 Python and CLI surfaces directly. Current
supported lifecycle evidence remains readable. Internal call sites move to the
new function names without aliases or dual implementations.

## Plain terms

| Term | Meaning |
| --- | --- |
| Lifecycle package | A materialised task-owned lifecycle specification, release material, and verifier inputs. |
| Lifecycle run | One durable execution directory for one package revision. |
| Checkpoint | One ordered stage with released material, an actor instruction, and a required submission. |
| Release | The host makes the active checkpoint material available to the actor. |
| Submission | Actor-produced checkpoint content accepted and archived by the host. |
| Revisit | Read and record access to an accepted checkpoint without changing the active position. |
| Branch | A new run that inherits an accepted prefix and reopens one submitted checkpoint. |
| Fresh context | One separate model or agent session for each checkpoint attempt. |
| Persistent context | One model or agent session that can continue across several checkpoints. |
| Lifecycle trial | One planned experiment trial plus its package, run directory, execution mode, and visibility policy. |
| Lifecycle executor | A callable that executes or resumes one lifecycle trial and returns execution evidence. |
| Lifecycle experiment | Repeated application of `run_lifecycle_trial()` to planned lifecycle trials. |

The task contract field named `TaskDefinition.lifecycle` remains publication
status. It is unrelated to the finite lifecycle described here.

## Current evidence

### One lifecycle coordinator already exists

`lifecycles.runtime.lifecycle` owns the current checkpoint and recovery
operations:

- `prepare_evidence_checkpoint()`;
- `submit_evidence_checkpoint()`;
- `read_evidence_lifecycle_state()`;
- `revisit_evidence_checkpoint()`;
- `branch_evidence_lifecycle()`;
- `request_evidence_checkpoint()`;
- `execute_lifecycle_operation()`; and
- `run_evidence_lifecycle()`.

All registered lifecycles use this progression runtime. There is no need for a
new lifecycle coordinator.

### Four registered lifecycles prove the finite sequence

The lifecycle catalogue currently contains four definitions across stormwater
and structural review. They share ordered progression while keeping their
submission meaning, variants, calculations, operations, and verification with
their task families.

Every current lifecycle is linear. `depends_on` values validate earlier
accepted checkpoints; they do not make the runtime a general graph scheduler.

### Fresh and persistent execution are different

`run_evidence_lifecycle()` executes each checkpoint through the typed
`LifecycleEpisodeEnvironment`. The environment owns one fresh-context episode.
The lifecycle host remains the checkpoint coordinator.

`run_local_evidence_lifecycle_session()` instead owns one persistent adapter
session across checkpoints and exposes lifecycle tools inside that session.
It does not use repeated fresh episodes.

`run_local_evidence_lifecycle_fresh_context()` builds a local episode
environment and then calls the shared checkpoint coordinator. The CLI selects
between these two local functions itself.

The two modes are real treatments. The public API should make their difference
explicit rather than pretending that a persistent session is a sequence of
fresh episodes.

### Trial finalisation is coupled to ablation

`experimentation.lifecycle_studies.trial_record` can produce a complete core
`TrialRecord`, but its public builder and finaliser require
`LifecycleAblationManifest` and `LifecycleAblationTrial`.

This means an ordinary lifecycle trial cannot use the finalisation logic
without pretending to be part of an ablation. The reusable finalisation
boundary must accept a normal lifecycle trial. Ablation-specific fields can
continue through `PlannedTrial.extensions` and study-owned reports.

### Ablation repeats the application pipeline

`run_lifecycle_ablation()` currently owns planning, package materialisation,
smoke checks, local mode dispatch, recovery, experiment recording, trial
finalisation, ledger reads, and summary generation.

Its study policy is useful. Its execution and finalisation loop should use the
same lifecycle trial and experiment functions as direct callers.

### Lifecycle commands are split across two CLI families

`aec-bench task lifecycle` currently owns:

```text
list
materialize
list-variants
verify
run-smoke
```

`aec-bench meta-harness` currently owns:

```text
lifecycle-start
lifecycle-submit
lifecycle-status
lifecycle-revisit
lifecycle-branch
lifecycle-run-local
lifecycle-ablation
lifecycle-calibration-freeze
```

The second group calls lifecycle runtime, harness, or lifecycle-study
functions. Its location is historical; those operations are not meta-harness
behaviour.

## Required functional composition

### Keep checkpoint control as direct functions

The current implementation functions receive the complete package and run
location, use the existing lock and recovery rules, and return direct context
values. Keep that shape and give it clear public names:

```python
def release_checkpoint(
    package_dir: Path,
    run_dir: Path,
    *,
    operation_resolver: LifecycleOperationResolver | None = None,
) -> dict[str, object]: ...


def submit_checkpoint(
    package_dir: Path,
    run_dir: Path,
    *,
    operation_resolver: LifecycleOperationResolver | None = None,
    episode_result: LifecycleEpisodeResult | None = None,
) -> dict[str, object]: ...


def read_lifecycle(
    package_dir: Path,
    run_dir: Path,
    *,
    operation_resolver: LifecycleOperationResolver | None = None,
) -> dict[str, object]: ...


def revisit_checkpoint(
    package_dir: Path,
    run_dir: Path,
    *,
    checkpoint_id: str,
    reason: str,
    operation_resolver: LifecycleOperationResolver | None = None,
) -> dict[str, object]: ...


def branch_lifecycle(
    package_dir: Path,
    parent_run_dir: Path,
    branch_run_dir: Path,
    *,
    checkpoint_id: str,
    branch_id: str,
    reason: str,
    operation_resolver: LifecycleOperationResolver | None = None,
) -> dict[str, object]: ...
```

These are direct renames and public composition of the existing operations.
They do not add service objects or a `LifecycleManager`.

The functions keep the current validated context projection instead of adding
a second state model. Persisted state remains `EvidenceLifecycleRunState`.

Optional capability functions remain separate:

```python
request_checkpoint_evidence(...)
execute_lifecycle_operation(...)
```

A lifecycle that does not declare those capabilities does not need them.

### Starting, resuming, revisiting, and branching

The lifecycle has four distinct operations:

| Operation | Behaviour |
| --- | --- |
| Start | `release_checkpoint()` creates a run when none exists and releases the first checkpoint. |
| Resume | `run_lifecycle()` or a trial executor reads the existing run and continues its active or next checkpoint. |
| Revisit | `revisit_checkpoint()` returns accepted prior material and logs the revisit without changing the active checkpoint. |
| Branch | `branch_lifecycle()` creates a new run, inherits the accepted prefix, and reopens the selected submitted checkpoint. |

There is no `start_at` argument. Starting a new empty run at checkpoint three
would omit the accepted evidence and visibility state produced by checkpoints
one and two.

To start work from a specific checkpoint, the caller branches from a parent
run in which that checkpoint was submitted:

```python
branch_lifecycle(
    package_dir=package_dir,
    parent_run_dir=completed_or_partial_run,
    branch_run_dir=derived_run,
    checkpoint_id="checkpoint-2",
    branch_id="alternative-review",
    reason="Test a different decision from checkpoint 2",
)
```

The branch inherits earlier accepted submissions, attempts, acquired evidence,
completed operations, and consumed budgets. It reopens the selected checkpoint
and does not change the parent.

If a test or maintained experiment needs to begin from a prepared checkpoint,
it must use a real validated parent run or a task-owned deterministic fixture
that produces the same accepted prefix. The runtime does not synthesize prior
submissions.

### Keep fresh-context coordination lifecycle-owned

Rename the existing checkpoint coordinator directly:

```python
def run_lifecycle(
    package_dir: Path,
    run_dir: Path,
    *,
    episode_environment: LifecycleEpisodeEnvironment,
    operation_resolver: LifecycleOperationResolver | None = None,
) -> dict[str, object]: ...
```

`run_lifecycle()` resumes when the run directory contains valid incomplete
state. It runs until completion or an explicit execution failure. It remains
the only fresh-context checkpoint loop.

`LifecycleEpisodeEnvironment` remains the typed boundary for one fresh
checkpoint episode. Do not expand it to persistent context.

### Give local execution one application function

The local harness exposes one function:

```python
def run_local_lifecycle(
    *,
    trial: LifecycleTrial,
    adapter_builder: Callable[..., object] | None = None,
) -> LifecycleExecution: ...
```

It selects the current fresh-context or persistent-context implementation from
`trial.execution_mode` and validates the selected visibility policy.

The internal mode implementations can remain separate because their session
semantics differ. Callers and the CLI do not repeat the selection branch.

Provider-specific persistent execution can supply another
`LifecycleTrialExecutor`. It does not need to implement
`LifecycleEpisodeEnvironment` when one session spans checkpoints.

### Use one normal lifecycle trial value

```python
@dataclass(frozen=True)
class LifecycleTrial:
    planned: PlannedTrial
    package_dir: Path
    run_dir: Path
    execution_mode: LifecycleExecutionMode
    visibility_policy: LifecycleVisibilityPolicy
```

The materialised package carries lifecycle identity, task variant, and
task-owned behaviour. `PlannedTrial` carries agent, model, adapter, compute,
repetition, and optional study extensions. `LifecycleTrial` does not copy
those fields.

The application validates these mode and visibility pairs:

- persistent context requires `PERSISTENT_CONTEXT` visibility; and
- fresh context cannot use `PERSISTENT_CONTEXT` visibility.

It does not restrict task-owned evidence requests or operations beyond the
current package protocol.

### Return one execution value from executors

```python
@dataclass(frozen=True)
class LifecycleExecution:
    state: dict[str, object]
    agent: dict[str, object]
    tool_schema: tuple[dict[str, object], ...]


type LifecycleTrialExecutor = Callable[[LifecycleTrial], LifecycleExecution]
```

`LifecycleExecution` is an in-memory application value. It contains the
execution facts needed for experiment recording. Canonical attempts, sessions,
submissions, actions, trajectories, and outputs remain in the run directory.

An executor returns failed execution facts when the current runtime can safely
record them. It raises when no valid lifecycle execution can be established.
`run_lifecycle_trial()` does not convert an unrecorded exception into a
successful or complete trial.

### Finalise one trial in one place

```python
def run_lifecycle_trial(
    *,
    trial: LifecycleTrial,
    execute: LifecycleTrialExecutor,
    verify: Callable[[Path, Path], dict[str, object]],
    persist: Callable[[TrialRecord], None] | None = None,
) -> TrialRecord: ...
```

The function:

1. executes or resumes the lifecycle through `execute`;
2. reads and validates the canonical final lifecycle state;
3. invokes the task verifier only after host validation permits it;
4. records the execution manifest and metrics once;
5. builds the lifecycle extensions and output artifacts on one `TrialRecord`;
6. calls the optional persistence function; and
7. returns the same `TrialRecord` value.

Verification and `TrialRecord` construction do not remain inside local mode
selection or an ablation loop.

Refactor the current lifecycle record builder to accept `LifecycleTrial` and
the normal execution evidence. Ablation-specific manifest and plan values
travel through `PlannedTrial.extensions` and study-owned files. Do not retain a
second ablation-only finaliser after migration.

### Apply trials as an experiment

```python
def run_lifecycle_experiment(
    *,
    trials: Sequence[LifecycleTrial],
    execute: LifecycleTrialExecutor,
    verify: Callable[[Path, Path], dict[str, object]],
    persist: Callable[[TrialRecord], None] | None = None,
) -> list[TrialRecord]: ...
```

The first implementation applies `run_lifecycle_trial()` sequentially in the
declared order. Current lifecycle studies already require deterministic
sequential execution. Do not add concurrency configuration before a current
study needs it and the run directories are proven independent.

The function returns records directly. Study evaluation does not need to
re-query the ledger only to access records that were just produced.

Existing complete records can be loaded and validated by a study before it
calls this function for remaining trials. Resume and campaign policy remain
with the study rather than becoming hidden behaviour in every lifecycle
experiment.

## Proposed public Python API

The public lifecycle facade belongs at `aec_bench.lifecycles.application`:

```python
from aec_bench.lifecycles.application import (
    LifecycleExecution,
    LifecycleTrial,
    branch_lifecycle,
    read_lifecycle,
    release_checkpoint,
    revisit_checkpoint,
    run_lifecycle,
    run_lifecycle_experiment,
    run_lifecycle_trial,
    submit_checkpoint,
)
```

Local model execution remains under `harness`:

```python
from aec_bench.harness.lifecycle_local import run_local_lifecycle
```

The direct public names replace these internal names:

| Current name | Target name |
| --- | --- |
| `prepare_evidence_checkpoint()` | `release_checkpoint()` |
| `submit_evidence_checkpoint()` | `submit_checkpoint()` |
| `read_evidence_lifecycle_state()` | `read_lifecycle()` |
| `revisit_evidence_checkpoint()` | `revisit_checkpoint()` |
| `branch_evidence_lifecycle()` | `branch_lifecycle()` |
| `run_evidence_lifecycle()` | `run_lifecycle()` |
| `run_local_evidence_lifecycle_session()` and `run_local_evidence_lifecycle_fresh_context()` as caller choices | `run_local_lifecycle()` |

Update all repository callers and remove the old function names. Do not leave
aliases or parallel wrappers.

The detailed evidence-lifecycle contracts and stored field names remain
unchanged unless implementation proves that a protected format must change.

## Meta-harness composition

Lifecycle composition supplies one small evaluator to the runtime-agnostic
meta-harness API:

```python
@dataclass(frozen=True)
class LifecycleHarnessCandidate:
    trials: tuple[LifecycleTrial, ...]
    execute: LifecycleTrialExecutor


def evaluate_lifecycle_candidate(
    candidate: HarnessCandidate[LifecycleHarnessCandidate],
) -> list[TrialRecord]:
    value = candidate.value
    return run_lifecycle_experiment(
        trials=value.trials,
        execute=value.execute,
        verify=verify_lifecycle,
    )
```

The concrete candidate can vary supported lifecycle treatments, including:

- fresh or persistent context;
- permitted visibility policy;
- agent, model, adapter, tools, and limits;
- task-owned lifecycle variant; and
- a declared branch point or branch policy when the study supplies a valid
  parent run.

The generic meta-harness sees only candidate identities and returned records.
It does not release checkpoints, resolve operations, inspect branch state, or
verify lifecycle submissions.

Lifecycle-specific proposal, assessment, selection, and refinement functions
can live under `experimentation.lifecycle_studies` and plug into the generic
meta-harness. Do not add `LifecycleMetaHarness` or another lifecycle loop.

## CLI composition

All lifecycle commands move under the existing lifecycle command family:

```text
aec-bench task lifecycle list
aec-bench task lifecycle list-variants
aec-bench task lifecycle materialize
aec-bench task lifecycle start
aec-bench task lifecycle submit
aec-bench task lifecycle status
aec-bench task lifecycle revisit
aec-bench task lifecycle branch
aec-bench task lifecycle run
aec-bench task lifecycle verify
aec-bench task lifecycle run-smoke
aec-bench task lifecycle study ablation
aec-bench task lifecycle study calibration-freeze
```

Command behaviour is:

| Command | Library composition |
| --- | --- |
| `start` | Call `release_checkpoint()`. It creates a run or releases its next checkpoint. |
| `submit` | Call `submit_checkpoint()` for the active checkpoint. |
| `status` | Call `read_lifecycle()` without advancing the run. |
| `revisit` | Call `revisit_checkpoint()` without changing the active checkpoint. |
| `branch` | Call `branch_lifecycle()` to create a new derived run at one submitted checkpoint. |
| `run` | Build one `LifecycleTrial`, call `run_local_lifecycle()` through `run_lifecycle_trial()`, and return its `TrialRecord`. Existing valid state resumes. |
| `verify` | Call the task-owned verifier through the lifecycle catalogue. |
| `run-smoke` | Call `run_lifecycle()` with the task-owned deterministic smoke environment. |
| `study ablation` | Build the study plan and call `run_lifecycle_experiment()` for remaining trials. |
| `study calibration-freeze` | Derive the current lifecycle-study selection from completed records. |

The CLI does not add `--start-at`. Users create a branch when they need a
derived run from a submitted checkpoint.

Remove these commands from `aec-bench meta-harness`:

```text
lifecycle-start
lifecycle-submit
lifecycle-status
lifecycle-revisit
lifecycle-branch
lifecycle-run-local
lifecycle-ablation
lifecycle-calibration-freeze
```

Do not retain hidden aliases or print deprecation messages. Update the root
README, installed meta-harness skill, lifecycle examples, and CLI tests in the
same cutover.

The `meta-harness` command then contains only higher-order harness design,
comparison, and refinement operations.

## Existing machinery migration

The new application functions replace overlapping orchestration:

| Current capability | Migration target |
| --- | --- |
| `lifecycles.runtime.lifecycle` checkpoint operations | Rename and export through `lifecycles.application`; retain one underlying implementation. |
| `run_evidence_lifecycle()` | Become `run_lifecycle()` with the same fresh-context coordinator behaviour. |
| Two caller-visible local lifecycle run functions | Become internal mode implementations behind `run_local_lifecycle()`. |
| Local verification and recorder calls | Move to `run_lifecycle_trial()` so both modes finalise identically. |
| Ablation-only `build_lifecycle_trial_record()` and `finalize_lifecycle_trial_record()` inputs | Accept a normal `LifecycleTrial`; keep study metadata in extensions. |
| `run_lifecycle_ablation()` execution loop | Plan and resume the study, then call `run_lifecycle_experiment()` for remaining trials. |
| Lifecycle calibration and evaluation | Consume returned or loaded `TrialRecord` values without owning execution. |
| Prime fresh-checkpoint composition | Continue to supply `LifecycleEpisodeEnvironment` or a lifecycle trial executor. |
| Provider-specific persistent session | Continue as a harness integration behind `LifecycleTrialExecutor`. |
| `meta-harness lifecycle-*` commands | Move to `task lifecycle` and delete the old routes. |

Move useful tests to the new public boundary before deleting old functions.
Tests that only preserve superseded names or command locations are updated or
removed.

## Ownership and dependency direction

| Concern | Owner |
| --- | --- |
| Lifecycle package and checkpoint meaning | Concrete lifecycle task family |
| Checkpoint release, acceptance, branch, revisit, state, and recovery | `lifecycles.runtime` |
| Functional lifecycle application facade | `lifecycles.application` |
| Fresh-context episode boundary | `lifecycles.runtime.episode` |
| Local model and adapter execution | `harness.lifecycle_local` |
| Prime and provider-specific execution | Their concrete harness integrations |
| Verification meaning | Concrete lifecycle verifier |
| Trial construction | Lifecycle application plus core `TrialRecord` builder functions |
| Ledger persistence | `ledger` |
| Ablation, calibration, holdout generalisation, and treatment policy | `experimentation.lifecycle_studies` |
| Generic harness comparison and refinement | `experimentation.meta_harness` |
| CLI parsing and rendering | `cli.commands.lifecycle` |

The shared lifecycle runtime does not import the catalogue, concrete lifecycle
families, harness integrations, experimentation, or meta-harness.

The catalogue is the composition root for registered task-owned materialisers,
operation resolvers, smoke environments, and verifiers. Application and CLI
code can use the catalogue. The neutral runtime cannot.

## Delivery slices

### Slice 1: Direct lifecycle facade

- Add `lifecycles.application`.
- Rename and expose release, submit, read, revisit, branch, and fresh-context
  run functions.
- Update all repository callers directly.
- Remove the old function names and imports.
- Preserve current state, recovery, checkpoint, and branch behaviour.

### Slice 2: One local execution function

- Add `LifecycleTrial` and `LifecycleExecution` as normal in-memory dataclasses.
- Add `run_local_lifecycle()`.
- Keep fresh and persistent mode implementations private and separate.
- Move mode and visibility validation to the common local entry point.
- Remove duplicated mode selection from CLI and lifecycle studies.

### Slice 3: Trial finalisation

- Add `run_lifecycle_trial()`.
- Move verification and experiment recording after the execution callback.
- Refactor lifecycle `TrialRecord` construction to accept `LifecycleTrial`.
- Return the built record directly and make ledger persistence optional.
- Delete the ablation-only finalisation path after its callers move.

### Slice 4: Lifecycle experiments and studies

- Add sequential `run_lifecycle_experiment()`.
- Migrate ablation execution to it.
- Keep campaign resume, calibration selection, transfer policy, summaries, and
  persisted study reports under `experimentation.lifecycle_studies`.
- Use returned records for immediate evaluation instead of querying the ledger
  again.
- Remove repeated local dispatch and finalisation from the ablation runner.

### Slice 5: CLI cutover

- Add start, submit, status, revisit, branch, and run to
  `aec-bench task lifecycle`.
- Add the lifecycle `study` subgroup.
- Move ablation and calibration-freeze commands.
- Delete all lifecycle commands and imports from `meta_harness.py`.
- Move and simplify CLI tests.
- Update the root README and installed skills in the same change.

### Slice 6: Meta-harness bridge

- Add one lifecycle candidate evaluator that calls
  `run_lifecycle_experiment()`.
- Prove one baseline-versus-candidate lifecycle study through the generic
  meta-harness API with deterministic executors.
- Keep candidate construction and lifecycle-specific assessment under
  `experimentation.lifecycle_studies`.
- Do not add a registry or lifecycle-specific meta-harness runner.

## Acceptance criteria

1. Python callers can release, submit, read, revisit, and branch lifecycle runs
   through direct functions.
2. The existing checkpoint coordinator remains the only fresh-context
   progression loop.
3. A new lifecycle run always starts with its first declared checkpoint.
4. An existing valid run resumes its active or next checkpoint without
   repeating accepted work.
5. There is no arbitrary `start_at` function or CLI option.
6. Branching from a submitted checkpoint creates an isolated run with the
   accepted prefix and selected checkpoint reopened.
7. Revisiting a checkpoint does not change active state or accepted content.
8. The parent run does not change when a branch is created or executed.
9. Fresh-context execution continues to use one typed episode per checkpoint
   attempt.
10. Persistent-context execution continues to use one session across
    checkpoints and is not represented as fresh episodes.
11. Local callers choose execution mode through one `run_local_lifecycle()`
    function.
12. A normal `LifecycleTrial` reuses `PlannedTrial`, `AgentConfig`, and
    `ComputeConfig` rather than copying their fields.
13. `run_lifecycle_trial()` executes, verifies, builds, optionally persists,
    and returns one `TrialRecord` through one implementation path.
14. The task verifier runs after host validation and outside checkpoint
    progression.
15. Failed or partial execution does not become complete or positive evidence.
16. Direct Python execution does not require ledger publication.
17. `run_lifecycle_experiment()` applies `run_lifecycle_trial()` and returns
    records directly.
18. The ablation runner uses the common lifecycle experiment path for trial
    execution and finalisation.
19. Calibration, transfer, and study evaluation retain their specialised
    policy without owning another lifecycle runtime.
20. Every lifecycle CLI command is under `aec-bench task lifecycle`.
21. No `lifecycle-*` command remains under `aec-bench meta-harness`.
22. CLI commands and Python callers use the same lifecycle functions.
23. The lifecycle-to-meta-harness integration is one candidate evaluator that
    returns `TrialRecord` values.
24. The meta-harness core does not import lifecycle runtime or catalogue code.
25. No universal environment runtime, plugin registry, compatibility alias, or
    version-suffixed operation is added.
26. Registered lifecycle task behaviour, verification results, branch
    semantics, and accepted artifact bytes remain unchanged.
27. Superseded functions, command branches, tests, and comments are removed
    after callers migrate.

## Verification

Use deterministic and provider-free checks:

- lifecycle runtime tests for release, submit, retry, recovery, revisit, and
  branch behaviour;
- registered lifecycle conformance tests across stormwater and structural
  review;
- fresh-context episode tests with in-process environments;
- persistent-context harness tests with adapter fakes;
- tests that `run_local_lifecycle()` selects and validates both modes;
- trial tests for verification ordering, failed execution, returned records,
  optional persistence, and lifecycle extensions;
- experiment tests that prove declared order and direct record return;
- ablation tests that prove resume and summary behaviour through the shared
  experiment path;
- CLI tests for every command in the new lifecycle family and absence from
  `meta-harness`;
- a deterministic lifecycle evaluator test through the generic meta-harness
  API;
- import-boundary tests that reject catalogue, harness, experimentation, and
  meta-harness imports from the neutral lifecycle runtime; and
- documentation and installed-skill link tests.

Do not run paid models, hosted Harbor execution, Prime, Morph Cloud, or another
credentialed provider as part of normal verification.

## Decisions made by this plan

- Finite lifecycles keep their own runtime and do not join a universal
  environment abstraction.
- The existing checkpoint coordinator is retained and exposed through direct
  functional names.
- Fresh and persistent context remain distinct execution modes.
- A branch from accepted evidence is the supported way to begin derived work
  at a selected checkpoint.
- One normal lifecycle trial and finalisation path replaces ablation-specific
  execution plumbing.
- Lifecycle experiments return `TrialRecord` values directly.
- All lifecycle CLI commands belong under `aec-bench task lifecycle`.
- Meta-harness integration is an evaluator function, not a lifecycle-specific
  meta-harness implementation.

## Completion and retirement

When implementation is complete:

1. update the current architecture, staged-evidence protocol, root README, and
   installed lifecycle guidance to describe the implemented API and CLI;
2. update contracts only if implementation changes a real supported or
   persisted boundary;
3. delete this plan, or retain only a concise historical rationale when it is
   still useful; and
4. keep lifecycle task behaviour with its task-family owner rather than
   copying it into application or experiment code.
