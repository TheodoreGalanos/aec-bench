# Evolution Functional Composition PRD

| Field | Value |
| --- | --- |
| Class | Plan |
| Status | Proposed |
| Audience | Evolution, harness, experiment, and CLI contributors |
| Owner | Repository maintainers |

This document is a proposed follow-up to the
[artifact task composition plan](artifact-task-composition.md). It is not
current architecture. The current [architecture](../ARCHITECTURE.md),
[contracts](../CONTRACTS.md), and [invariants](../INVARIANTS.md) remain the
authority until implementation changes them.

## Purpose

Give agent evolution the same functional application shape as task and
experiment execution:

```text
run_trial() -> run_experiment() -> run_evolution()
```

The current evolution loop is useful, but callers must build an
`EvolutionOrchestrator` and immediately call `.run()`. This plan replaces that
builder-and-class surface with functions. It keeps the current evolution
engine, workspace, strategies, candidate history, archive, graveyard,
enrichment, persistence, convergence, and reporting behaviour.

Functional composition here means explicit callable inputs and direct result
values. It does not mean that model execution, workspace mutation, or artifact
persistence become pure operations.

## Dependency and decision boundary

Implementation starts only after the artifact task composition plan has:

- added `run_trial()` and `run_experiment()`;
- migrated the evolution fitness `SolveFn` to `run_experiment()`;
- removed the separate local and Harbor task execution owned by evolution; and
- stopped evolution from writing candidate configuration into source task
  directories.

If those requirements are incomplete, finish them in the artifact task plan.
Do not duplicate or carry them into this follow-up.

This plan changes an internal, pre-1.0 Python surface. It does not preserve
`EvolutionOrchestrator`, `build_evolution_runner()`, or
`build_evolution_runner_from_config()` as compatibility aliases.

## Product outcome

Direct Python callers run evolution with one function:

```python
result = run_evolution(
    workspace=workspace,
    config=config,
    engine=engine,
    evaluate=evaluate_candidate,
    strategy=strategy,
    report_writer=write_report,
)
```

The CLI and callers that want repository configuration use one application
function:

```python
result = run_evolution_from_config(
    config=config,
    tasks_root=tasks_root,
    report_writer=write_report,
)
```

Both functions return the existing `EvolutionResult`. Neither returns a
runner, manager, or object that needs a second `.run()` call.

Candidate evaluation is a normal callable:

```python
type CandidateEvaluator = Callable[
    [WorkspaceSnapshot, int],
    list[TrialRecord],
]
```

The current workspace supplies the initial candidate. This plan does not add a
second candidate, workspace, cycle, or result model.

## Non-goals

- Replacing `AECEvolutionEngine` or its model roles.
- Rewriting hill-climb, quality-diversity, archive, graveyard, enrichment,
  mutation, gating, convergence, reporting, or swarm policy.
- Making the evolution loop referentially pure.
- Moving evolution policy into `run_trial()`, `run_experiment()`, an adapter,
  or an attempt recipe.
- Adding a plugin registry, event bus, dependency-injection container, generic
  workflow language, or versioned evolution operation.
- Redesigning `EvolutionConfig`, `WorkspaceSnapshot`, `EvolutionCycleRecord`,
  or `EvolutionResult` without a separately approved requirement.
- Adding evolution support for lifecycles or interactive worlds. Those task
  families can supply a `CandidateEvaluator` after their normal experiment
  paths return `TrialRecord` values.
- Preserving internal builders, classes, imports, or tests only for backward
  compatibility.
- Running paid evolution or provider qualification as part of implementation.

## Current evidence

The current public-looking path has two steps:

```python
runner = build_evolution_runner_from_config(...)
result = runner.run()
```

`src/aec_bench/evolution/runner.py` owns two builders that assemble and return
`EvolutionOrchestrator`. `src/aec_bench/cli/commands/evolve.py` constructs the
runner only to call `.run()` immediately.

`EvolutionOrchestrator` stores six constructor inputs and exposes one main
operation. Its loop already depends on a callable `SolveFn` and returns one
`EvolutionResult`. Its other methods are loop helpers for observation
construction, convergence, reporting, and summary extraction. They do not
require a long-lived public orchestration object.

The `SolveFn` alias is duplicated in the orchestrator and local backend. The
local backend also gives one callable a hidden `.cleanup()` method, which the
orchestrator detects with `hasattr()`. After `run_experiment()` owns task
workspace cleanup, evolution does not need this undeclared callable protocol.

The engine and selection strategies are different. They own real search
behaviour and state across cycles. This plan keeps them as domain objects and
passes them into the application function.

## Required functional composition

The complete composition is:

```text
workspace snapshot
-> CandidateEvaluator
    -> explicit agent configuration
    -> run_experiment()
    -> TrialRecords
-> evolution observations
-> engine step
-> strategy update and parent selection
-> next workspace snapshot
-> EvolutionResult
```

An evaluator created by the artifact task work has this shape:

```python
def evaluate_candidate(
    snapshot: WorkspaceSnapshot,
    batch_size: int,
) -> list[TrialRecord]:
    agent = materialize_evolution_agent(snapshot)
    experiment = build_candidate_experiment(
        agent=agent,
        batch_size=batch_size,
    )
    tasks = select_manifest_tasks(task_catalogue, experiment)
    trials = plan_trials(experiment, tasks)
    return run_experiment(
        runtime=runtime,
        tasks=resolve_instances(tasks),
        trials=trials,
        recipe=single_attempt(),
    )
```

The evaluator can select another supported attempt recipe without changing
the evolution loop:

```python
return run_experiment(
    runtime=runtime,
    tasks=resolved_tasks,
    trials=trials,
    recipe=best_of(k=4, selector=self_select()),
)
```

Best-of-K candidates remain inside one scored trial. Evolution cycles remain
outside the trial and use the resulting `TrialRecord` values as fitness
evidence.

## Public Python API

The supported facade belongs in `aec_bench.evolution` or one small evolution
application module exported from it:

```python
def run_evolution(
    *,
    workspace: Workspace,
    config: EvolutionConfig,
    engine: AECEvolutionEngine,
    evaluate: CandidateEvaluator,
    strategy: SelectionStrategy,
    report_writer: ReportWriter | None = None,
) -> EvolutionResult: ...


def run_evolution_from_config(
    *,
    config: EvolutionConfig,
    tasks_root: Path | None = None,
    report_writer: ReportWriter | None = None,
) -> EvolutionResult: ...
```

`run_evolution()` is the full in-process composition surface. Tests and custom
Python callers can provide a deterministic evaluator, engine, strategy, and
workspace directly.

`run_evolution_from_config()` is the repository application function. It owns
configuration-based assembly: workspace loading, workspace versioning, LLM
clients, engine construction, strategy selection, task selection, and the
candidate evaluator that calls `run_experiment()`.

Outcome-affecting configuration stays in the existing explicit inputs. The
functions do not read hidden global configuration or add another recipe or run
context model.

## Behaviour to preserve

The functional implementation preserves the current accepted behaviour:

1. The workspace is initialized and versioned before the first cycle.
2. Each cycle evaluates the current explicit workspace snapshot.
3. `TrialRecord` values become `EvolutionObservation` values for the current
   candidate.
4. The engine performs the current classify, analyse, evolve, gate, and
   candidate phases.
5. The selected parent is applied with the current next-cycle semantics.
6. Cycle trial outcomes are persisted before temporary task workspaces are
   cleaned.
7. Strategy, archive, and graveyard state are updated and saved.
8. Convergence uses the existing threshold and stagnation-window behaviour.
9. Optional report failure remains non-fatal and is reported through logging.
10. The function returns the same `EvolutionResult` fields and meaning.

`run_evolution()` may mutate its supplied evolution workspace. That effect is
explicit in the function input and remains owned by the evolution domain. The
candidate evaluator must not mutate source task packages.

## Migration and deletion

The implementation changes the current path directly:

1. Move the orchestration loop from `EvolutionOrchestrator.run()` into
   `run_evolution()`.
2. Convert private class helpers to module functions where the loop needs
   them.
3. Move assembly from the two builder functions into
   `run_evolution_from_config()` and small direct construction helpers only
   where reuse is real.
4. Rename `SolveFn` to `CandidateEvaluator` and keep one definition.
5. Update the CLI, tests, and all repository callers to call a function.
6. Delete `EvolutionOrchestrator`.
7. Delete `build_evolution_runner()` and
   `build_evolution_runner_from_config()`.
8. Delete the old `runner.py` or replace it with the one application module;
   do not leave both paths.
9. Remove the evaluator `.cleanup()` convention. `run_experiment()` owns its
   trial workspaces and returns records whose retained artifacts survive
   cleanup.
10. Remove obsolete runner and orchestrator tests after their behaviour moves
    to function tests.

No compatibility alias, deprecation wrapper, alternate builder, or class-based
fallback remains.

## CLI

The `aec-bench evolve run` command remains the operational surface for people,
agents, shell automation, and CI. Its documented options and output stay the
same unless Theo separately approves a public change.

The command loads and validates user input, displays progress, calls
`run_evolution_from_config()`, emits the returned result, and maps failures to
the current user-facing error behaviour. It does not construct an
orchestrator or contain evolution-loop policy.

## Delivery slices

### Slice 1: Functional evolution loop

- Add `CandidateEvaluator` and `run_evolution()`.
- Move the current loop and helpers without changing behaviour.
- Convert orchestrator tests to function tests.
- Delete `EvolutionOrchestrator` in the same change.

### Slice 2: Configuration and CLI cutover

- Add `run_evolution_from_config()`.
- Move current builder assembly into that function.
- Update the CLI and remaining callers.
- Delete both builder functions and the superseded module path.
- Remove the evaluator `.cleanup()` convention.

### Slice 3: Public surface and documentation

- Export the supported functions and callable type from the chosen evolution
  application facade.
- Update public command documentation only if user-visible behaviour changed.
- Remove stale builder and orchestrator references from code and maintained
  documentation.

## Acceptance criteria

1. A direct caller can run evolution with `run_evolution()` and receive an
   `EvolutionResult` without constructing a runner or calling `.run()`.
2. The CLI calls `run_evolution_from_config()` directly.
3. Candidate evaluation uses `run_experiment()` and returns `TrialRecord`
   values.
4. Local and Harbor evaluation do not have evolution-owned copies of task
   execution, verification, artifact collection, or trial construction.
5. Existing hill-climb and quality-diversity cycle behaviour remains covered.
6. Workspace, cycle, archive, graveyard, convergence, persistence, and report
   behaviour remains covered.
7. Candidate evaluation does not mutate a source task directory.
8. Evaluator cleanup is not detected through attributes or another hidden
   protocol.
9. `EvolutionOrchestrator`, both builder functions, duplicate `SolveFn`
   aliases, and their obsolete tests are absent.
10. No compatibility alias, versioned replacement, or parallel execution path
    remains.
11. No persisted evolution contract or documented CLI behaviour changes
    without separate approval.

## Verification

Implementation verification includes:

- focused tests for `run_evolution()` with deterministic evaluators;
- configuration assembly tests for `run_evolution_from_config()`;
- hill-climb and quality-diversity strategy tests;
- archive, graveyard, convergence, trial persistence, report, and workspace
  tests;
- `tests/cli/test_evolve.py`;
- evolution end-to-end tests with local fakes;
- searches proving that deleted class, builder, alias, and duplicate solver
  names have no remaining callers;
- Ruff, formatting, and mypy for the changed Python paths; and
- no paid provider execution.

## Completion and retirement

After implementation, update current architecture or public documentation only
where the supported surface changed. Then delete this plan, or retain only a
concise historical decision if its rationale remains useful.
