# Artifact Task Composition PRD

| Field | Value |
| --- | --- |
| Class | Plan |
| Status | Proposed |
| Audience | Task generation, dataset, harness, evaluation, and CLI contributors |
| Owner | Repository maintainers |

This document is a proposed plan for ordinary artifact and workspace tasks. It
is not current architecture. The current [architecture](../ARCHITECTURE.md),
[contracts](../CONTRACTS.md), and [invariants](../INVARIANTS.md) remain the
authority until implementation changes them.

## Purpose

Make ordinary task execution easy to compose with normal Python functions. A
single task run stays simple. Optional behaviours such as best-of-K, retry,
refinement, and evolution build on the same task execution path instead of
adding branches to each CLI, adapter, or compute backend.

The same model extends to datasets:

```text
plan a suite
-> generate runnable task instances
-> compose a dataset
-> plan an experiment
-> run trials
-> summarize TrialRecords
```

The design starts with artifact and workspace tasks. It does not define a
common runtime for lifecycles or interactive worlds.

## Product outcome

AEC-Bench has one operation for one agent execution:

```python
runtime.run_once(
    task: ResolvedTaskInstance,
    trial: PlannedTrial,
    *,
    attempt_id: str,
    parent: TaskAttempt | None = None,
    instruction: str | None = None,
) -> TaskAttempt
```

The task is the existing concrete runnable task instance. There is no public
`prepare_task()` function, `PreparedTask` value, or second task model.

When `parent` is `None`, the operation creates a fresh workspace from the task.
When `parent` is a completed attempt, it creates a child workspace from that
attempt. It never changes the task or parent workspace. The returned attempt
contains the complete workspace after one agent execution, the existing
`AdapterResult`, and the elapsed time. It does not contain an official verifier
reward.

`PlannedTrial` carries the per-trial `AgentConfig`, full `ComputeConfig`, task,
and repetition. Shared run information stays in the current experiment and run
contracts. AEC-Bench does not add a second `RunCondition` or public run-context
model. Outcome-affecting agent, model, adapter, client, parameter, resource,
and timeout settings stay in the current contracts.

Normal task policy composes around the one-execution operation:

```text
resolved task + planned trial
-> run one or more tracked attempts
-> select one attempt
-> run the official verifier once
-> run an optional reviewer
-> build one TrialRecord
```

The first implementation is local. Harbor later applies supported recipes
through its dispatch and import boundary. Harbor does not need to expose a
local workspace path or use the local attempt result internally.

## Non-goals

- A universal runtime for artifact tasks, lifecycles, and interactive worlds.
- A plugin registry, dynamic package discovery, hot reload, event bus, or
  dependency-injection framework.
- A new task preparation layer or task representation.
- Direct execution of a task template before it creates a runnable task
  instance.
- New provider adapters or provider SDK changes.
- A redesign of seed authoring or template content.
- A new verifier, reward, or evaluation policy.
- Verifier-guided best-of-K selection.
- Same-session refinement or parallel candidate execution in the first
  implementation.
- Hiding evolution policy inside `run_once()`.
- Reporting verifier-guided evolution as an ordinary reward-blind recipe.
- Automatic conversion of verifier-feedback tasks to the ordinary path.
- A change to task-package, dataset, experiment, or `TrialRecord` persisted
  formats as a side effect of adding functional task composition.
- A versioned batch-operation or execution-program bridge in the ordinary task
  path.
- Making run publication, export, or replay a precondition for ordinary Python
  execution.
- Compatibility aliases, parallel implementations, or version-suffixed
  replacements for internal code that this plan supersedes.
- Replacing the current evolution engine, strategies, workspace, archive, or
  reporting policy.
- UI work or paid provider qualification.

## Proposed public Python API

The composable task flow is a supported Python API, not command-local glue. The
proposed facade is `aec_bench.harness.artifact_tasks`:

```python
from aec_bench.harness.artifact_tasks import (
    LocalTaskRuntime,
    best_of,
    run_trial,
    self_select,
)

runtime = LocalTaskRuntime(work_root=work_root)

record = run_trial(
    runtime=runtime,
    task=resolved_task,
    trial=planned_trial,
    recipe=best_of(k=4, selector=self_select()),
)
```

The facade can use smaller internal modules, but its documented imports and
behaviour form one deliberate public boundary.

### Separate harness construction from attempt composition

The current `HarnessRecipe` describes harness bindings, available
capabilities, contracts, and budgets. It does not describe how one trial
creates, branches, or selects task attempts. In the target design it becomes
`HarnessSpec`, because it is a declarative harness specification rather than a
functional recipe.

This is a direct replacement, not a compatibility rename. `HarnessSpec` uses
its values directly. It does not retain `recipe_id`, `version`,
`HarnessRecipeRef`, a versioned operation name, or an alias for the previous
type. If an optional export later needs exact byte identity, the export owner
can provide that identity outside runtime construction.

Harness construction and attempt composition stay separate:

```text
HarnessSpec -> build or configure a TaskRuntime
AttemptRecipe -> call an AttemptRunner and select one TaskAttempt
run_trial() -> track attempts, verify the selection, and build TrialRecord
```

`AttemptRecipeSpec` is not compiled into `HarnessSpec`. It is an optional
serializable description of a supported built-in attempt recipe for a CLI,
configuration file, or remote transport. A direct Python caller can supply an
`AttemptRecipe` without any serializable specification.

The ordinary task path does not call a generic or versioned batch operation.
`run_experiment()` applies `run_trial()` directly. When this path replaces an
existing artifact-task execution operation, all current callers move to the
application function and the replaced operation is deleted. No compatibility
alias or second execution path remains.

### Reuse the existing trial contracts

`PlannedTrial` remains the per-trial schedule entry. It reuses `AgentConfig`
and `ComputeConfig` instead of copying their fields:

```python
@dataclass(frozen=True)
class PlannedTrial:
    trial_id: str
    experiment_id: str
    task_id: str
    agent: AgentConfig
    compute: ComputeConfig
    repetition: int
    extensions: Mapping[str, BaseModel] = field(default_factory=dict)
```

The change from `compute_backend: str` to `compute: ComputeConfig` keeps
resource limits and timeout overrides available at execution. The extension
mapping uses the current trial-record builder extension input. It lets current
adaptation provenance travel with the ordinary trial instead of requiring a
second execution path.

The planner still creates one `PlannedTrial` for each task, agent, and
repetition. Best-of-K candidate executions remain inside that one planned
trial. They are not extra repetitions.

### Keep recipes task-blind

`run_trial()` closes over the task, planned trial, and runtime. A recipe receives
only the function that it needs to create attempts:

```python
class AttemptRunner(Protocol):
    def __call__(
        self,
        *,
        attempt_id: str,
        parent: TaskAttempt | None = None,
        instruction: str | None = None,
    ) -> TaskAttempt: ...


class AttemptRecipe(Protocol):
    def __call__(self, run_once: AttemptRunner) -> AttemptSelection: ...
```

A call with no parent starts from the concrete task instance. A call with a
parent starts from a copy of that attempt. The recipe does not receive the task
directory, task snapshot, planned trial, runtime, official verifier, or
verifier result.

This interface supports fresh retry, refinement, branching search, and attempt
evolution without adding these policies to the runtime.

### Track attempts in `run_trial()`

`run_trial()` wraps the runtime operation before it gives `run_once` to the
recipe. The wrapper registers every attempt call and its result. The recipe
cannot omit a failed or rejected candidate from usage, evidence, or cleanup by
leaving it out of `AttemptSelection`.

`AttemptSelection` contains only:

- the selected attempt, or a declared failure;
- the selection decision and reason;
- selector evidence and usage, when a selector ran.

`run_trial()` owns the full attempt list. It uses that list to aggregate usage,
retain required evidence, and clean every workspace. Expected execution
failures return a failed `TaskAttempt`. Unexpected exceptions still trigger
cleanup for all workspaces that the runtime created.

After selection, `run_trial()` runs the official verifier against the selected
workspace, runs an optional reviewer, builds the `TrialRecord`, persists the
required artifacts, and cleans the workspaces. A recipe never receives the
official verifier.

`TaskAttempt` is public for recipe composition, but its workspace is valid only
for the active `run_trial()` call. Before cleanup, `run_trial()` materializes
the required artifacts and returns a `TrialRecord` whose artifact references
resolve without the attempt workspace.

### Multiple callers use the same functions

The first callers are:

- `aec-bench run-local`;
- dataset and experiment execution;
- the current adaptation planner;
- the current agent evolution runner;
- direct Python users;
- deterministic tests.

They use `run_trial()` or `run_experiment()` instead of owning another task
execution and trial-record path. `single_attempt()` and `best_of()` are the
first built-in recipes. A custom branching recipe proves that the interface is
not specific to either built-in.

Arbitrary Python recipes are a local Python capability. Harbor can lower a
named built-in recipe only after that recipe has a defined Harbor transport.
An unsupported Harbor recipe fails before dispatch.

### Publication is an optional outer operation

`run_trial()` and `run_experiment()` execute tasks and return `TrialRecord`
values. They do not accept publication policy and do not require a published
run package. Materializing the output and trajectory artifacts needed by a
returned record is normal trial completion; it is not run publication.

Existing ledger, export, and package functions can consume completed records
when a caller needs durable or portable results. A caller can also provide an
`AttemptRecipeSpec` with those results when it used a supported built-in. This
optional step does not constrain custom Python recipes or expand the core task
execution signature.

### The CLI is an access surface, not another runtime

AEC-Bench keeps both public access surfaces:

```text
Python caller ---------+
                       |
CLI command -----------+-> run_trial() / run_experiment() -> runtime
                       |
Evolution SolveFn -----+
```

The Python API is the full in-process composition surface. A Python caller can
pass a custom `AttemptRecipe` directly.

The CLI is the operational surface for people, agents that invoke installed
commands, shell automation, and CI. It owns:

- command and option parsing;
- configuration and filesystem-path loading;
- built-in recipe selection;
- progress display;
- structured output;
- exit codes and user-facing errors.

The CLI does not own workspace execution, attempt tracking, selection,
verification, review, trial construction, or evaluation policy. It resolves
inputs and calls the same public application functions as a Python caller.

For example, the implementation of `aec-bench run-local` has this shape:

```python
def run_local_command(...) -> None:
    task = resolve_task(task_ref)
    trial = build_planned_trial(...)
    recipe = build_attempt_recipe(recipe_spec)
    record = run_trial(
        runtime=LocalTaskRuntime(...),
        task=task,
        trial=trial,
        recipe=recipe,
    )
    emit(record)
```

The default recipe is `single_attempt()`, so current command behaviour stays
the same when the user does not select an add-on.

The CLI and Harbor accept only named, serializable built-in recipes. They do
not accept arbitrary Python callables. The first configuration contract is a
small discriminated union:

```python
class SingleAttemptSpec(StrictModel):
    kind: Literal["single_attempt"] = "single_attempt"


class BestOfSpec(StrictModel):
    kind: Literal["best_of"] = "best_of"
    candidates: PositiveInt
    selector: SelectorSpec


AttemptRecipeSpec = SingleAttemptSpec | BestOfSpec
```

`build_attempt_recipe(spec)` converts this serializable value to the Python
recipe. A CLI option can be a short way to build the same value. For example,
an option equivalent to `--best-of 4 --selector self` would build a
`BestOfSpec` and then call `build_attempt_recipe()`.

The first release does not define a general nested recipe language. A later
built-in gets a new explicit recipe specification only when the CLI or a remote
transport supports it. Custom compositions such as
`retry(refine(best_of(...)))` remain Python-only until they have a supported
serializable specification and transport.

The current commands keep their domain roles:

| Command area | Shared application path |
| --- | --- |
| `run-local` | Resolve one task and planned trial, then call `run_trial()`. |
| `run` | Resolve the experiment and tasks, then call `run_experiment()`. |
| `evolve` | Keep the evolution workflow, but implement its `SolveFn` with `run_experiment()`. |
| `remediate` | Keep the explicit reward-aware workflow and call shared task execution at its real boundary. |
| `generate` and `dataset` | Call the shared generation, dataset construction, storage, and publication functions. |
| `evaluate` | Call the shared summary function with supplied or queried `TrialRecord` values. |

No command calls another AEC-Bench command as a subprocess to reuse behaviour.
Commands import the application functions. This keeps one execution path while
preserving the CLI as a stable automation boundary.

## Plain terms

| Term | Meaning |
| --- | --- |
| Task template | A generator definition that can create runnable task instances. It is not a runtime input. |
| Resolved task | The existing `ResolvedTaskInstance`: a validated `TaskDefinition`, its runnable task directory, and resolved paths. |
| Planned trial | The existing plan for one task, agent, compute configuration, and repetition. |
| Harness specification | The declarative capabilities, bindings, contracts, and budgets used to construct a task runtime. It does not control attempt branching or selection. |
| Task attempt | The in-memory result of exactly one agent execution: attempt identity, optional parent-attempt identity, workspace, `AdapterResult`, and elapsed time. |
| Attempt runner | The tracked callable supplied to a recipe. It starts a fresh attempt or a child attempt. |
| Attempt selection | The selected attempt or failure, plus the selection reason and selector evidence. |
| Attempt recipe | A reward-blind callable that creates and selects attempts but cannot call the official verifier. |
| Attempt recipe specification | An optional serializable description of one named built-in attempt recipe for CLI, configuration, and supported remote transport. |
| Selection | Choosing one candidate before the task verifier runs. |
| Task add-on | A normal function that creates, transforms, or selects attempts. It is not a dynamically discovered plugin. |
| Generated task set | The application result of generation: its output root, runnable task paths, and `GenerationManifest`. |
| Trial | One selected attempt, its official task evaluation, and the resulting `TrialRecord`. |
| Repetition | A new independent trial. It is outside a best-of-K candidate set. |

This PRD introduces no new authority, binding, sealing, or adoption vocabulary.
Existing task, run, dataset, artifact, and trial identity contracts remain in
force.

## Current evidence

Several parts already have the required functional shape:

- [`load_task_definition()`](../../src/aec_bench/tasks/loader.py),
  [`validate_task()`](../../src/aec_bench/tasks/validator.py), and
  [`resolve_instance_paths()`](../../src/aec_bench/tasks/instance.py) already
  load, check, and resolve runnable task instances.
- [`build_task_snapshot()`](../../src/aec_bench/harness/compilation/task_snapshot.py)
  already records the exact repository revision or detached task artifact.
- [`AdapterRequest` and `AdapterResult`](../../src/aec_bench/adapters/base.py)
  provide a provider-neutral adapter boundary.
- [`HarnessRecipe`](../../src/aec_bench/contracts/harness_instance.py) is a
  declarative capability-and-binding value. It does not create or select live
  task attempts, and its internal recipe identity and version fields are not
  needed by the target task-runtime construction path.
- [`ExecutionProgram`](../../src/aec_bench/contracts/execution_program.py)
  executes generic operation graphs. It is not the ordinary task-composition
  API and does not mediate `run_trial()` or `run_experiment()`.
- [`compose_dataset()`](../../src/aec_bench/generation/dataset.py) is already a
  pure suite planner, although its current name suggests that it creates a
  benchmark dataset. `execute_plan()` writes the generated task packages.
- [`plan_trials()`](../../src/aec_bench/trials.py) already
  expands tasks, agents, and repetitions without executing them.
- [`build_trial_record()`](../../src/aec_bench/harness/trial_record_builder.py)
  already builds the current trial contract and accepts typed extensions.
- [`summarize_evaluation_records()`](../../src/aec_bench/evaluation/pipeline.py)
  already summarizes supplied `TrialRecord` values without running an agent.

The missing handoffs are concrete:

- [`run-local`](../../src/aec_bench/cli/commands/run_local.py) owns workspace
  setup, adapter execution, output materialization, verification,
  verifier-feedback retry, review, output copying, and ledger import in one
  command path.
- There is no supported Python recipe API that lets the CLI, dataset runner,
  evolution runner, and external callers share the same task composition.
- An `AdapterResult` cannot represent the task result by itself. Artifact tasks
  can change several files, and the verifier evaluates the resulting workspace.
- Local and Harbor paths retain different fixed sets of output artifacts. They
  can omit task-specific files that the verifier used.
- [`create_dataset_from_tasks()`](../../src/aec_bench/dataset/creator.py) builds
  and writes a `DatasetManifest` in one function. Suite output reaches it
  through CLI path loading instead of a typed application handoff.
- The run workflow returns import counts and paths. Evaluation reads the ledger
  again instead of consuming the records that the run produced.
- [`PlannedTrial`](../../src/aec_bench/trials.py) keeps only the compute
  backend name and loses the rest of `ComputeConfig` before execution.
- [`AdaptationPlannedTrial`](../../src/aec_bench/harness/adaptation_run.py) wraps
  `PlannedTrial` only to carry provenance that the current trial-record builder
  already accepts as an extension.
- [`evolution/backends/local.py`](../../src/aec_bench/evolution/backends/local.py)
  has separate workspace execution, verification, artifact collection, and
  `TrialRecord` construction.
- Before implementation, `evolution/runner.py` had another Harbor solve path
  and wrote the evolved system prompt into the selected task directory before
  dispatch.

These are composition and ownership problems. They do not require a plugin
framework, event bus, dependency-injection container, or universal runtime.

## Existing task operations and their composition role

The repository has more task operations than the basic run path. This plan
reuses them at their current domain boundaries:

| Existing operation | Composition role |
| --- | --- |
| Task loading, validation, path resolution, promotion, and task snapshots | Produce or check a concrete runnable task before trial execution. `run_trial()` uses the resolved task directly. |
| Harness capability and binding specification | Construct the runtime that is available to a task. It does not own attempt branching, selection, or verification order. |
| Template sampling, scaffolding, suite planning, and replay data | Produce runnable task instances and `GeneratedTaskSet` before dataset composition. |
| Task and template genomes and decomposition | Describe or transform task structure before task generation or dataset selection. They do not execute agents. |
| Adaptation specification expansion and adaptation trial planning | Produce ordinary planned trials with adaptation provenance in trial extensions. |
| Output normalization and output-commit validation | Finish one attempt before it can be selected. They stay inside the one-attempt path. |
| Lambda-RLM tournament and synthesis code | Remain adapter-local when they select adapter-internal sections. Provider-neutral whole-task selection can reuse moved generic logic, but the harness does not import upward from an adapter package. |
| Workspace reviewer | Run after official verification and attach review evidence without changing candidate selection or verifier reward. |
| Verifier-feedback retry and remediation | Remain explicit reward-aware workflows because verifier output affects a later agent or edit. They are not ordinary reward-blind recipes. |
| Agent evolution engine and orchestrator | Use `run_experiment()` as their `SolveFn` execution effect. The evolution search policy stays in the evolution domain. |
| Evaluation aggregation and ledger queries | Consume the `TrialRecord` values produced by the shared run path. Ledger persistence does not own evaluation policy. |

No operation gets a second implementation to fit this API. If an existing
operation has the required behaviour, callers use it. If ownership is wrong,
the implementation moves to the correct package and the old copy is removed.

## Required behaviour

### 1. One ordinary task path

1. `run_trial()` accepts a concrete `ResolvedTaskInstance` and a
   `PlannedTrial`. It does not create a second task representation.
2. The application resolves or confirms the selected task revision once before
   attempts start. A direct `run_trial()` call does this internally.
   `run_experiment()` reuses the already resolved task revision for its planned
   trials. This is not a public preparation phase or a second task value.
3. `runtime.run_once()` creates and patches a fresh workspace when no parent is
   supplied. The workspace contains actor-visible task material only.
4. For a child attempt, `runtime.run_once()` copies the parent workspace and
   leaves the parent unchanged. It rejects a parent from another trial.
5. Verifier code, hidden parameters, ground truth, and host-only material do
   not enter an adapter request, recipe, candidate, or selector session.
6. `runtime.run_once()` starts exactly one adapter execution. Provider
   transport retries and multi-turn model calls can remain inside the adapter.
7. Each attempt uses a separate workspace. One attempt cannot change a sibling
   or the source task package.
8. The attempt preserves the final workspace state, including created,
   changed, and deleted files. It is not only the model response text.
9. Output fallback and current output normalization finish before the attempt
   returns. They use `TaskDefinition.verifier.expected_output_path` and do not
   assume `output.md`.
10. The attempt retains its attempt ID, optional parent-attempt ID,
    `AdapterResult`, elapsed time, terminal status, and evidence required by
    the current trial record.
11. `runtime.run_once()` does not stage the verifier, calculate a reward, run a
    reviewer, import a trial, or clean a sibling workspace.
12. After selection, no agent call changes the selected workspace before the
    verifier finishes.
13. `run_trial()` stages the private verifier, evaluates the selected
    workspace, runs the optional reviewer, builds the `TrialRecord`, and
    materializes required artifacts before it cleans all attempt workspaces.
    The returned record resolves those artifacts without a live workspace.
14. `run_trial()` supplies the tracked `AttemptRunner` to the recipe. It does
    not supply the task, runtime, official verifier, or verifier results.
15. `run_trial()` uses all tracked attempts for cost, evidence, and cleanup. It
    does not trust a recipe to return a complete attempt list.

Workspace path replacement happens only after the task or parent workspace is
copied. No candidate file can keep a path to the source task or a sibling
workspace. Output normalization cannot change bytes covered by an
`OutputCommitAttestation`; an inconsistent commitment makes the attempt
invalid.

The public `single_attempt()` recipe has one adapter execution, one official
verifier call, and one `TrialRecord`.

### 2. Best-of-K is the first add-on proof

The public `best_of()` recipe calls its supplied `run_once()` as a normal
function. AEC-Bench does not need dynamic discovery or a middleware graph.

- Start K fresh workspaces by calling `run_once(parent=None)` K times.
- Give each candidate the same actor-visible task inputs and the same planned
  trial configuration. Record its candidate index and any explicit seed.
- Prevent candidate agents from seeing sibling candidates.
- Give the declared selector only the candidate material listed by the recipe.
  It cannot see the official verifier, verifier reward, hidden task data, or
  host-only material.
- Record candidate order, the selected candidate, selector configuration, and
  deterministic tie-breaking policy.
- Run the official task verifier once, against the selected workspace only.
- Include agent and selector usage from all candidates in trial cost and
  evidence. Rejected candidates do not become separate trials.
- Keep failed candidates in evidence, but select only candidates that completed
  and produced the required primary output. This check does not run the task
  verifier.
- Treat `k=1` as `single_attempt()` and make no selector call.
- If no candidate can be selected, do not run the verifier. Return a failed
  execution and failed evaluation with no `EvaluationResult`.

The selector is a self-verification step. It is not the official task verifier
and cannot use the verifier as a hidden ranking function. The first proof uses
a deterministic selector or the declared model in a fresh selector session. A
different selector agent or model is recorded in the selection evidence.

Candidate evidence uses the existing `TrialExtensionRef` route when the caller
persists the trial. The extension records candidate order, result summaries,
durations, selector-visible artifact references, selector configuration,
selector usage, the decision, and the selected index. The winner alone enters
`TrialOutput`. `TimingRecord.total_seconds` remains wall time, and `CostRecord`
aggregates all model usage. These persistence details do not constrain direct
Python composition or require publication of the run.

### 3. Composition examples

The baseline recipe is a normal function:

```python
def single_attempt() -> AttemptRecipe:
    def recipe(run_once: AttemptRunner) -> AttemptSelection:
        attempt = run_once(attempt_id="attempt-0")
        return AttemptSelection.selected(attempt, reason="single attempt")

    return recipe
```

Best-of-K is repeated application and selection:

```python
def best_of(k: int, selector: Selector) -> AttemptRecipe:
    def recipe(run_once: AttemptRunner) -> AttemptSelection:
        candidates = [
            run_once(attempt_id=f"attempt-{index}")
            for index in range(k)
        ]
        return selector(candidates)

    return recipe
```

A custom refinement recipe creates a child attempt. `run_trial()` records both
attempts even though the recipe returns only the selected child:

```python
def draft_then_refine(run_once: AttemptRunner) -> AttemptSelection:
    draft = run_once(attempt_id="draft")
    refined = run_once(
        attempt_id="refined",
        parent=draft,
        instruction="Review the draft and improve the final submission.",
    )
    return AttemptSelection.selected(refined, reason="refinement completed")
```

Recipes can compose without runtime branches:

```python
recipe = retry(
    refine(
        best_of(k=4, selector=self_select()),
    ),
    attempts=2,
)
```

This example proves the intended shape. Retry and refinement do not need to be
built-ins in the first delivery.

### 4. Evolution composes at the level of what changes

Evolution is a higher-order caller of task and experiment functions. It is not
one special phase inside the runtime.

#### Attempt evolution

Attempt evolution searches over candidate solutions to one task. It is a
reward-blind `AttemptRecipe` when it does not use the official verifier:

```python
recipe = evolve_attempts(
    initial=single_attempt(),
    mutate=refine_attempt(),
    select=self_select(),
    generations=3,
)

record = run_trial(
    runtime=runtime,
    task=resolved_task,
    trial=planned_trial,
    recipe=recipe,
)
```

The recipe starts fresh attempts or child attempts through its supplied
`AttemptRunner`. The official verifier stays outside the recipe and runs once
against the final selection. `evolve_attempts()` is a future fit check, not a
required first built-in.

#### Task evolution

Task evolution changes task definitions or packages before dataset composition:

```python
reviews = decompose_task_genomes(tasks)
evolved = evolve_task_packages(tasks=tasks, reviews=reviews, mutate=mutate_task)
dataset = compose_dataset(evolved.tasks, dataset_spec)
```

The existing genome, decomposition, validation, and generation operations do
the work that they already support. `evolve_task_packages()` represents the
missing orchestration only. It does not duplicate task loading, scaffolding,
validation, or publication.

If task evolution uses trial results as fitness, those trials are development
or calibration evidence. They are not silently reused as the final blind
evaluation of the evolved dataset.

#### Agent and configuration evolution

The current evolution runner changes agent prompts, skills, and memory. It
composes outside a trial by creating explicit agent configurations and running
normal experiments:

```python
def solve(snapshot: WorkspaceSnapshot, batch_size: int) -> list[TrialRecord]:
    agent = materialize_evolution_agent(snapshot)
    experiment = build_candidate_experiment(agent=agent, batch_size=batch_size)
    tasks = select_manifest_tasks(task_catalogue, experiment)
    trials = plan_trials(experiment, tasks)
    return run_experiment(
        runtime=runtime,
        tasks=resolve_instances(tasks),
        trials=trials,
        recipe=single_attempt(),
    )
```

The selected agent configuration becomes normal experiment input. It is not
ambient runtime state, and the evolution runner does not write it into a source
task directory.

#### Reward-aware evolution

Evolution can use official verifier results during search. This changes the
task protocol because verifier calls become inputs to later agent executions.
The algorithm uses a declared reward-aware workflow, records every verifier and
agent call, and reports that condition separately. It is not an
`AttemptRecipe`, because `AttemptRecipe` has no verifier access.

### 5. Migration target for the current evolution runner

The existing evolution subsystem is a caller to migrate, not a subsystem to
replace.

Keep the current:

- `EvolutionOrchestrator` and its `SolveFn` boundary;
- the functional evolution coordinator;
- `WorkspaceSnapshot` and snapshot serialization;
- strategies, analysis, enrichment, archive, graveyard, and reporting;
- swarm policy where it remains a current caller.

Replace and remove the duplicate execution effects:

- `LocalSolver`;
- `collect_local_trial_record()`;
- `_run_adapter_in_workspace()`;
- the local solver's custom workspace, verifier, and artifact collection;
- the execution body of `_build_harbor_solve_fn()`;
- direct injection of an evolved snapshot into a selected source task
  directory;
- duplicated task generation in `generate_task_instances()` when the shared
  generation application functions cover it.

The retained `SolveFn` becomes a thin composition of agent materialization,
experiment planning, `plan_trials()`, and `run_experiment()`. Both local
and Harbor execution use the shared harness path. The migration slice removes
the replaced code in the same change. It does not leave the current and new
solvers in parallel.

### 6. Dataset composition uses the same task function

The target application flow is:

```python
plan = plan_suite(templates, suite_spec)
generated = generate_instances(plan)
tasks = load_generated_tasks(generated)
dataset = compose_dataset(tasks, dataset_spec)
save_dataset(dataset)
dataset_ref = publish_dataset(dataset)

experiment = build_experiment_config(dataset_ref, agents, compute)
resolved_dataset = resolve_dataset(dataset_ref)
verify_resolved_dataset(resolved_dataset)
trials = plan_trials(experiment, resolved_dataset.tasks)

records = run_experiment(
    runtime=runtime,
    tasks=resolve_instances(resolved_dataset.tasks),
    trials=trials,
    recipe=best_of(k=4, selector=self_select()),
)
evaluation = summarize_evaluation_records(records)
```

Generation is optional. Hand-authored and evolved runnable task packages can
enter `compose_dataset()` through the same validation and selection boundary.

| Function | Responsibility | Effect |
| --- | --- | --- |
| `plan_suite()` | Select templates and assign difficulty, visibility, tool mode, seed, and instance count. | Pure and deterministic |
| `generate_instances()` | Write runnable task packages and return a `GeneratedTaskSet`. | Filesystem write |
| `load_generated_tasks()` | Load and validate the task packages named by a `GeneratedTaskSet`. | Filesystem read |
| `compose_dataset()` | Select validated task packages and build a `DatasetManifest`. | Pure for resolved inputs |
| `save_dataset()` | Store the dataset manifest without changing its meaning. | Filesystem write |
| `publish_dataset()` | Produce the current immutable dataset reference and publication record. | Repository or bundle boundary |
| `build_experiment_config()` | Build an `ExperimentManifest` from a dataset reference, agents, and compute configuration. | Pure |
| `resolve_dataset()` and `verify_resolved_dataset()` | Resolve the dataset reference, check integrity, and load task material. | Read and integrity boundary |
| `plan_trials()` | Expand verified tasks, agents, compute configuration, and repetitions into planned trials. | Pure and deterministic |
| `run_experiment()` | Apply one recipe through `run_trial()` for each planned trial and return or stream `TrialRecord` values. | Agent, verifier, reviewer, and persistence effects |
| `summarize_evaluation_records()` | Build the current evaluation summary from supplied records. | Pure |

Suite planning and benchmark membership remain separate policies. The first
controls which tasks are generated. The second controls which validated task
packages enter a dataset.

`GeneratedTaskSet` is a public application value with the output root,
generated task paths, and existing `GenerationManifest`. It is not a new
persisted format. `GenerationManifest` remains optional replay data, and task
loading does not depend on the sidecar.

Best-of-K is inside one trial. Repetition remains outside it. For example, two
repetitions with `k=3` produce two `TrialRecord` values and six candidate agent
executions.

### 7. Reviewer, verifier-feedback, and remediation stay explicit

The optional workspace reviewer runs after the official verifier. It can attach
review evidence to the trial, but it does not change candidate selection or the
official reward unless a separate protocol explicitly gives it that role.

The current verifier-feedback path is different. It runs the verifier, removes
private verifier assets, and makes a second agent execution in the same mutable
workspace. It remains one named two-pass reward-aware workflow. It can reuse
the lower-level workspace execution and trial construction functions, but it
is not an ordinary `AttemptRecipe`.

Remediation is also reward-aware. It consumes verifier findings and changes
task or output material through its existing proposer, applier, and verifier
operations. It can call the shared task runner for evaluation, but it stays a
separate workflow with its current remediation result contract.

### 8. Ownership stays narrow

| Concern | Owner |
| --- | --- |
| Task instruction, actor-visible files, environment, tools, and verifier meaning | Task and template domains |
| Workspace creation and one adapter execution | Harness runtime |
| Attempt tracking, recipe application, selection, verification, and trial construction | Harness orchestration |
| Provider protocol translation | Adapter |
| Dataset membership and publication | Dataset domain |
| Reward, validity, review meaning, and aggregation | Evaluation |
| Trial storage and queries | Ledger |
| Evolution search policy | Evolution domain |
| User command composition | CLI |

Adapters remain provider translators. They do not select whole-task candidates,
branch on task type, read verifier results, or score task outputs. The CLI and
evolution runner call application functions and do not own second
implementations.

### 9. CLI and Python use one application path

1. The existing CLI remains a supported interface for people, agents, shell
   automation, and CI.
2. CLI commands import and call the public application functions. They do not
   call another AEC-Bench command as a subprocess.
3. `run-local` uses `run_trial()` and defaults to `single_attempt()`.
4. `run` uses `run_experiment()` for its selected compute backend.
5. `evolve` keeps its domain workflow, but its `SolveFn` uses
   `run_experiment()`.
6. The CLI keeps configuration loading, path resolution, progress, structured
   output, exit codes, and user-facing errors.
7. The CLI does not implement workspace execution, recipe policy,
   verification, trial construction, or evaluation summaries.
8. Python callers can supply any valid `AttemptRecipe`. CLI, configuration,
   and Harbor accept only supported `AttemptRecipeSpec` members.
9. `build_attempt_recipe()` is the one conversion from an optional serializable
   specification to a built-in Python recipe.
10. CLI shorthand options and configuration files build the same
    `AttemptRecipeSpec`; they do not select separate execution branches.
11. Current command behaviour remains the default when no recipe is supplied.
12. A documented CLI or configuration change updates its implementation,
    tests, and public documentation together. It does not preserve the old
    internal path as a fallback.

## Future fit checks

Retry, refinement, and attempt evolution do not need to be built-in recipes in
the first delivery. The recipe contract supports these shapes without a new
execution path:

- A task-level retry calls `run_once(parent=None)` again. It needs an explicit
  retry-safe outcome; a broad provider error or timeout is not enough. It
  cannot use verifier feedback as a retry signal.
- Fresh-session refinement calls `run_once(parent=selected_attempt)`. This
  creates a child workspace and leaves the parent unchanged.
- Attempt evolution repeats the same branching operation and returns one
  selection.
- Same-session continuation remains a runtime-specific capability.
- Output completion and explicit output commitment remain adapter and session
  capabilities, not outer task add-ons.
- Task and agent evolution remain higher-level functions that call generation,
  dataset, experiment, and task-run APIs.

These fit checks constrain the first public API. They are not requirements to
ship all listed add-ons in the first implementation.

## Protected behaviour

Implementation under this plan preserves:

- provider-neutral task semantics and private verifier visibility;
- the task verifier's ownership of task-specific evidence;
- evaluation ownership of reward and validity;
- current task-template and runnable-task-instance meanings;
- the independence of task loading from `GenerationManifest`;
- immutable published dataset references and their integrity checks;
- current `ExperimentManifest`, `TrialRecord`, ledger, and evaluation meaning;
- documented `aec_bench.harness.artifact_tasks` imports and recipe semantics
  after this proposed API becomes current;
- documented CLI behaviour unless this implementation deliberately updates
  the command, tests, and public documentation together.

This plan uses the existing `TrialExtensionRef` route for candidate evidence
and the current extension input to `build_trial_record()`. It does not make
`TaskAttempt`, `AttemptSelection`, or `GeneratedTaskSet` persisted schemas.

This plan uses the current resolved `VerifierSpec.expected_output_path`. A
change to how task packages declare that value is a separate task-contract
decision and is not part of this work.

## Delivery slices

### Slice 1: Extract one local task attempt

- Use `ResolvedTaskInstance` directly. Do not add `PreparedTask` or
  `prepare_task()`.
- Change `PlannedTrial` to retain the full `ComputeConfig` and current typed
  trial extensions.
- Extract workspace creation, safe `/workspace/...` replacement, one adapter
  call, output fallback, current output normalization, and output-commit checks
  from `run-local` into the one-attempt path.
- Keep private verifier material out of the attempt workspace.
- Preserve task-relevant created, changed, and deleted files through
  verification.
- Prove the path with one ordinary task and one task whose verifier reads more
  than the primary output file.
- Delete the replaced command-local execution branches.

### Slice 2: Add the public recipe API and migrate `run-local`

- Add the `aec_bench.harness.artifact_tasks` facade.
- Define `TaskAttempt`, `AttemptRunner`, `AttemptSelection`, and `AttemptRecipe`
  as typed public Python contracts.
- Rename the current declarative `HarnessRecipe` to `HarnessSpec` and update
  its current callers directly. Do not retain an alias.
- Remove `recipe_id`, `version`, `HarnessRecipeRef`, and versioned operation
  identities from this internal harness-construction path.
- Keep `HarnessSpec` construction separate from `AttemptRecipe` execution. Do
  not compile either value into the other.
- Add `LocalTaskRuntime`, `single_attempt()`, and `run_trial()`.
- Make `run_trial()` create the task-blind tracked runner and own all attempt
  registration, usage aggregation, evidence retention, and cleanup.
- Keep verification, optional review, evidence persistence, and trial
  construction outside reward-blind recipes.
- Return a `TrialRecord` whose retained artifacts still resolve after every
  attempt workspace is cleaned.
- Make the ordinary `run-local` path call `run_trial()` with
  `single_attempt()`.
- Keep command parsing, path resolution, progress, structured output, and exit
  codes in the CLI wrapper.
- Prove the interface with a custom branching recipe.
- Consolidate current local trial construction on `build_trial_record()` and
  remove the replaced `local_import` construction path where no current caller
  remains.

This slice establishes the public composition boundary. It does not add a
temporary compatibility API.

### Slice 3: Preserve explicit reward-aware workflows

- Move current verifier-feedback behaviour from CLI branches into one named
  workflow.
- Preserve its one optional second pass, same-workspace behaviour, archived
  first output, feedback instruction, two verifier calls, and `retry.json`.
- Remove private verifier assets before the second agent execution.
- Reuse the shared attempt and record-building operations where their contracts
  fit. Do not represent verifier feedback as a reward-blind recipe.
- Keep remediation separate and reuse the shared runner only at its real
  execution boundary.
- Reject verifier-feedback before Harbor dispatch until Harbor has a tested
  feedback and workspace transport.

### Slice 4: Complete generation and dataset handoffs

- Rename the current pre-generation `compose_dataset()` function to
  `plan_suite()` and update its callers directly.
- Return `GeneratedTaskSet` from generation.
- Separate `DatasetManifest` construction from storage.
- Let generated, evolved, and hand-authored task packages use the same dataset
  builder after normal task validation.
- Remove the CLI-only filesystem join between suite output and dataset
  creation.
- Keep publication explicit and preserve current publication integrity rules.

### Slice 5: Run planned trials and return records

- Add `run_experiment(runtime, tasks, trials, recipe)`.
- Resolve each `PlannedTrial.task_id` to one supplied `ResolvedTaskInstance`.
- Apply the same recipe through `run_trial()` for every planned trial.
- Return or stream produced and imported `TrialRecord` values.
- Persist each record once through the ledger owner.
- Apply trials directly through `run_trial()`. Do not route ordinary task
  execution through a generic or versioned batch operation.
- Move every current artifact-task caller of the replaced batch operation to
  `run_experiment()` and delete that operation and its compatibility paths.
- Let evaluation summarize the supplied records without a required ledger
  query.
- Make `run`, dataset, and evaluation CLI paths thin callers and remove
  duplicate summary code.
- Replace `AdaptationPlannedTrial` with ordinary `PlannedTrial.extensions` and
  update adaptation callers directly.

### Slice 6: Add best-of-K

- Add public `best_of()` and `self_select()` recipe functions.
- Add `SingleAttemptSpec`, `BestOfSpec`, `AttemptRecipeSpec`, and
  `build_attempt_recipe()` as the optional serializable built-in boundary.
- Implement K independent calls through the supplied tracked `AttemptRunner`.
- Use a declared selector and deterministic tie-breaking.
- For `k=1`, make no selector call.
- Verify only the selected workspace.
- Store candidate and selector evidence through one current
  `TrialExtensionRef` when the trial is persisted.
- Aggregate model usage across every candidate and selector. Keep whole-trial
  timing as wall time.
- Keep repetitions outside candidate generation.
- Return a failed trial with no `EvaluationResult` when no candidate can be
  selected.
- Add one clear CLI or experiment-configuration spelling for best-of-K as a
  shorthand for `BestOfSpec`. Do not add a general nested recipe language.

### Slice 7: Migrate the current evolution runner

- Keep the evolution engine, orchestrator, `SolveFn`, workspaces, strategies,
  analysis, enrichment, archives, and reporting.
- Materialize each evolved agent snapshot as explicit agent configuration or
  system-prompt input. Do not write it into a task source directory.
- Make the local and Harbor solve functions compose experiment planning,
  `plan_trials()`, and `run_experiment()`.
- Replace and delete `LocalSolver`, `collect_local_trial_record()`,
  `_run_adapter_in_workspace()`, and the duplicate execution body of
  `_build_harbor_solve_fn()`.
- Reuse the shared generation application path and remove duplicate generation
  code when it covers the same behaviour.
- Update the `evolve` CLI and every other current evolution caller in the same
  slice. Do not keep a fallback solver.

### Slice 8: Complete CLI composition

- Keep the existing `run-local`, `run`, `evolve`, `remediate`, `generate`,
  `dataset`, and `evaluate` command roles.
- Make each command call its shared application function instead of retaining
  command-local domain or execution policy.
- Keep current defaults when the user does not select a recipe.
- Make CLI shorthand and configuration input produce the same
  `AttemptRecipeSpec`.
- Preserve machine-readable output, exit status, and documented error meaning.
- Prove that direct Python and CLI calls with the same resolved inputs produce
  the same task, trial, recipe, and evaluation meaning.
- Remove every replaced command-local execution, selection, record-building,
  and summary path.
- Update public CLI documentation for each new option or configuration field.

### Slice 9: Prove Harbor baseline parity

- Prove the ordinary one-pass task through Harbor after the local path is
  stable.
- Preserve the same selected task output, evaluation, status, cost, evidence,
  task identity, and dataset identity.
- Keep Harbor dispatch and import separate from the local live-workspace type.
- Add a built-in recipe to Harbor only after it has a defined and tested
  transport. Do not silently lower an unsupported recipe to one pass.
- Use recorded fixtures for default tests. Do not require a paid or hosted run.

Each slice is a working end-to-end change. A slice removes the implementation
that it replaces. It does not land unused interfaces for a later slice.

## Acceptance criteria

1. `aec_bench.harness.artifact_tasks` exports the documented runtime, recipe,
   and public value types. It does not export `PreparedTask`, `RunCondition`, or
   command-local helpers.
2. `run_trial()` accepts the existing `ResolvedTaskInstance` and
   `PlannedTrial` directly.
3. `PlannedTrial` retains `AgentConfig`, full `ComputeConfig`, repetition, and
   current typed trial extensions without a parallel run-condition model.
4. `single_attempt()` through `run_trial()` produces the same selected output
   bytes, statuses, reward, usage totals, and task identity as a fixed current
   local fixture.
5. A recipe receives a tracked `AttemptRunner` but no task directory, task
   snapshot, runtime, planned trial, official verifier, or verifier result.
6. A fresh attempt gets a separate workspace from the task. A child gets a
   separate copy of its parent workspace. The task and parent stay unchanged.
7. `run_trial()` records every attempt made through its runner even when the
   recipe does not return that attempt or raises after it was created.
8. `run_trial()` materializes required evidence, returns a record whose
   artifacts resolve without a live workspace, and cleans every created
   workspace on success, recipe failure, selector failure, and verifier
   failure.
9. The same custom recipe works through direct `run_trial()` and dataset-level
   `run_experiment()` without a second implementation.
10. A custom reward-blind branching recipe creates a child, selects it, and
    causes one official verifier call.
11. Private verifier files are absent from every candidate and selector
    session.
12. A multi-file task proves that created, changed, and deleted workspace files
    survive selection and reach the verifier.
13. Output fallback and normalization use
    `TaskDefinition.verifier.expected_output_path`. Normalization cannot
    invalidate an output commitment.
14. A maintained fixture preserves the current verifier-feedback behaviour:
    one optional second pass, the same workspace, archived first-pass evidence,
    hidden verifier assets during pass two, feedback in the second instruction,
    two verifier calls, and retained `retry.json`.
15. `best_of(k=1)` makes no selector call and has baseline cost and output
    parity.
16. `best_of(k=3)` makes three candidate executions, one selector call, and one
    official verifier call. Usage includes every execution.
17. A selector cannot receive official verifier results, hidden parameters,
    ground truth, host-only files, or sibling data from another trial.
18. Failed candidates remain in candidate evidence. If all candidates fail,
    the verifier does not run and the failed trial has no `EvaluationResult`.
19. Candidate evidence records order, summaries, durations, selector-visible
    artifact references, decision, and selected index. `CostRecord` aggregates
    usage while `TimingRecord.total_seconds` remains wall time.
20. Two repetitions with `k=3` produce two trials, six candidate executions,
    and two official verifier calls.
21. `GeneratedTaskSet` passes directly to task loading and dataset composition.
    Task loading remains independent of its optional `GenerationManifest`.
22. Dataset construction accepts generated, evolved, and hand-authored runnable
    task packages and does not write until the storage function runs.
23. Experiment execution produces one `TrialRecord` for each planned
    task-agent-repetition combination and supplies those records directly to
    summary construction.
24. Adaptation uses ordinary planned trials and the current trial extension
    route. It does not own another execution path.
25. The current evolution orchestrator gets its fitness `TrialRecord` values
    through `run_experiment()`. Its old local and Harbor execution copies are
    removed, and it does not mutate source task packages.
26. No adapter contains whole-task selection, task-level retry, refinement,
    evolution, or scoring branches.
27. A recorded Harbor fixture and local fake execution agree on selected output
    bytes, statuses, reward, usage totals, task identity, and dataset identity.
28. A recipe that Harbor does not support fails before dispatch instead of
    running a silent one-pass substitute.
29. Existing public commands retain their documented default behaviour when no
    task add-on is selected.
30. CLI shorthand and configuration input for a built-in recipe produce the
    same `AttemptRecipeSpec` and Python recipe.
31. Python can run a custom `AttemptRecipe` without a serializable
    specification. CLI and Harbor accept only their supported built-in
    specifications.
32. Direct Python and CLI calls with the same resolved inputs produce the same
    task identity, planned-trial meaning, recipe behaviour, and evaluation
    result.
33. No CLI command calls another AEC-Bench command as a subprocess to reuse
    application behaviour.
34. No replaced local, dataset, adaptation, evolution, Harbor, CLI, or
    evaluation execution path remains as a fallback or duplicate.
35. The declarative harness input is named `HarnessSpec`. `HarnessRecipe` does
    not remain as an alias, and `HarnessSpec` does not contain attempt
    branching or selection policy.
36. `AttemptRecipe` is the only callable recipe concept. It does not compile
    into `HarnessSpec`, and no separate `TrialRecipe` remains.
37. Ordinary task execution calls `run_experiment()` and `run_trial()`
    directly. It does not pass through a generic or versioned batch operation.
38. The internal harness-construction path does not retain `recipe_id`,
    `version`, `HarnessRecipeRef`, or version-suffixed operation identities.
    Optional export identity remains outside the execution API.

## Open decisions

The public Python recipe surface is part of Slice 2. These product choices need
resolution before their affected slices are complete:

1. What is the clearest CLI and configuration spelling for `BestOfSpec`?
2. Which actor-visible candidate files or summaries can a declared selector
   receive?
3. Which candidate and selector details should the existing
   `TrialExtensionRef` retain when a trial is persisted?
4. What Harbor artifact representation can retain task-specific files without
   copying private verifier material?

These choices do not block the direct Python recipe proof. Question 1 affects
the CLI and configuration surface. Question 4 affects Harbor support. Neither
changes the core `AttemptRecipe` contract.

## Verification

Use the lowest test layer that proves each slice:

- focused unit tests for workspace path replacement, attempt isolation,
  automatic tracking, selection, and cleanup;
- public import and signature tests for `aec_bench.harness.artifact_tasks`;
- `AttemptRecipeSpec` validation and `build_attempt_recipe()` mapping tests;
- `HarnessSpec` construction tests that prove it does not own attempt policy;
- recipe tests for fresh attempts, child attempts, omitted attempts, failed
  attempts, and every terminal cleanup path;
- one custom branching recipe run directly and through `run_experiment()`;
- a returned-record test that deletes every attempt workspace and then reads
  the retained output and trajectory artifacts;
- one local integration task with several output files;
- a maintained verifier-feedback workflow fixture;
- task-visibility tests that inspect every adapter and selector request;
- deterministic generation and replay tests;
- task-evolution-to-dataset tests that keep development fitness evidence
  separate from final experiment records;
- adaptation planning tests through ordinary `PlannedTrial` extensions;
- evolution `SolveFn` tests that prove shared execution and no task-source
  mutation;
- dataset construction, publication-integrity, scheduling, import, and
  evaluation tests;
- CLI regression tests for current default commands;
- CLI-to-Python parity tests for `single_attempt` and `best_of`;
- structured-output and exit-code tests for unsupported recipe specifications;
- a dependency test that proves ordinary task execution does not use a generic
  or versioned batch operation;
- recorded Harbor fixtures for cross-process normalization.

Default verification does not require credentials, containers, a live model,
or a paid hosted service.

## Completion and retirement

When the work is complete, update the current architecture, contracts, public
documentation, and tests that own the implemented behaviour. Then delete this
plan, or move only durable rationale to `docs/history/` if it remains useful.
