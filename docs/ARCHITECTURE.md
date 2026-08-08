# ABOUTME: Describes current AEC-Bench product flows, ownership boundaries, and dependency direction.
# ABOUTME: Separates task-owned semantics from current shared orchestration and provider boundaries.

# AEC-Bench Architecture

| Field | Value |
| --- | --- |
| Class | Architecture |
| Status | Current |

AEC-Bench creates, runs, evaluates, and publishes evidence about Architecture,
Engineering, and Construction benchmark tasks. The architecture protects this
objective order:

```text
validity > reproducibility > coverage > cost > throughput
```

When two designs protect those objectives equally, prefer the simpler final
system.

## Product flow

The product has two execution families. They share task selection, experiment
identity, agent and provider configuration, resource limits, evaluation,
provenance, and reporting. They do not share one forced low-level lifecycle.

```text
task sources and world profiles
            |
            v
authoring, validation, compilation, and deterministic generation
            |
            v
experiment, trial, or episode orchestration
            |
            +-------------------------+
            |                         |
            v                         v
artifact/workspace execution    interactive-world execution
            |                         |
            +------------+------------+
                         v
               task-owned verification
                         v
                    evaluation
                         v
        trial, evidence, and dataset artifacts
                         v
          CLI, TUI, web, reports, and research
```

### Artifact and workspace tasks

An artifact task gives an agent an instruction and an execution environment.
The agent changes files or submits an artifact, and the task verifier evaluates
the resulting workspace. A task can include declarative metadata, executable
environment setup, tools, fixtures, and verifier code.

The current path is:

1. Author or generate a task and validate its `TaskDefinition`.
2. Resolve one runnable task instance and stage its workspace.
3. Run a provider-neutral adapter locally, lower the experiment to the one
   Harbor dispatch-and-import workflow, or use the distinct Prime package and
   hosted-evaluation integration.
4. Collect output, the current trajectory, any provider-required transcript,
   and verifier artifacts.
5. Build an `EvaluationResult` and persist a `TrialRecord`.

Deterministic templates and suite generation live with authoring and generation.
Generated instances remain derived artifacts. Their generation provenance uses
the template source digest, seed, instance index, difficulty, and visibility;
ambient materialization time is not part of task meaning. The generated task
directory is validated through the current `TaskDefinition` loader before use.

### Interactive worlds

An interactive world repeatedly exposes an actor-visible observation and
accepts an action that changes task-owned state. Host controls use a separate
authority surface. World state, action meaning, clocks, projections, events,
and verifier logic remain with the task world.

The current registered continual-world path provides:

- exact executable world builds and content-pinned profiles;
- exact catalogue resolution for new work and recovery;
- one unversioned opaque-decision actor boundary;
- a separate strict host-control boundary;
- private task-owned callable composition;
- shared chosen-point rollout orchestration through an explicitly supplied
  branch capability;
- task-neutral local durability primitives; and
- harness-owned Harbor task integration and task-owned evaluation calls outside
  neutral world registration.

The public composition root currently registers two real consumers: the
wastewater pump-station stewardship world and the SSC-03 hydraulic interaction
world. The task-neutral continual package imports neither concrete world. See
the current [interactive-world runtime protocol](protocols/interactive-world-runtime.md).

Beneath those different orchestration paths, the continual runtime owns the
small accepted-transition and action-rejection values plus the episode shell.
Initial state, actor observation, transition functions, outputs, and evaluation
remain task-owned because the hydraulic and pump behaviors do not honestly
share one public structural protocol.

The pump world has one authoritative `PumpStationStewardshipState`. Its direct
`initial_state`, `observe`, and typed `transition` functions own pump behavior;
the pump task package owns its direct evaluator. The episode shell owns step
advancement and opaque decisions, while the pump persistence edge stores only
the current typed command, receipt, state, commit, and selected pointer.

Interactive worlds and artifact tasks meet at the experiment and evidence
layers. An interactive world does not need to pretend that each action is a
workspace submission, and an artifact task does not need a world-session API.

## Capability ownership

### Task authoring and compilation

Task contracts define runnable metadata and visibility. Task loaders,
templates, generators, and task-world compilers turn repository sources into
validated runnable material. Task-family semantics stay with their task or
template owner.

### Experiment, trial, and episode orchestration

The harness owns ordinary trial staging, backend execution, collection, and
cleanup. Evidence-lifecycle and interactive-world paths own their additional
episode or session coordination. Orchestration applies limits and records
identity; it does not score task outcomes or interpret task-specific state.

### Evaluation

Evaluation owns validity interpretation, reward, score breakdowns, behavioural
analysis, error taxonomy, confidence, and task-specific evaluation extensions.
Verifiers provide task-owned evidence. Reports, the TUI, and the web UI consume
evaluation results; they do not define competing metrics.

Cross-task model reviewing belongs to the meta-harness because it coordinates
review jobs and their evidence. Task-specific evaluation, including wastewater
pump stewardship scoring, remains with the task package.

### Durable artifacts

The ledger and artifact stores own persistence mechanics, integrity checks, and
queries. `TrialRecord` is the durable trial provenance envelope. Dataset
manifests identify immutable benchmark snapshots. Evidence-lifecycle and world
records add content-addressed artifacts where replay, recovery, or isolation
requires them.

`TrialRecord` references evidence authorities; it does not copy task-owned
episode state or replay facts into a second shared model. `OutputRecord` owns
termination versus truncation and the final runtime reason. `CostRecord` owns
aggregate model calls, token usage, cache usage, advisor usage, and estimated
cost. A task-owned episode inventory can be attached through one verified
`ArtifactReference`. Reports consume these canonical fields and never recover
aggregate usage from the open-ended provider metadata map.

`trajectory.jsonl` is the current ordered interaction record for ordinary
adapter runs. It contains validated entries only and has no version header or
historical reader. Provider transcripts remain only where an external or
sealed evidence workflow requires their exact representation.

Immutability is a property of accepted evidence, published datasets, and other
named records. It is not a requirement that every internal object, service, or
source file become a ledger event.

### Provider integrations

Adapters translate between the harness and agent execution. Compute backends
translate local or hosted execution. Provider modules and Harbor integration
sit outside task semantics. They may depend on task-neutral runtime surfaces;
task worlds and core contracts do not depend on provider SDKs, CLI, web, or TUI
modules.

Prime is a separate external package and evaluation boundary, not a Harbor
backend. Its exporter projects current public task or task-owned lifecycle
authority into independently installed Prime/verifiers packages. Its importer
normalizes provider samples into `TrialRecord`, `EvaluationResult`,
`CostRecord`, and content-bound artifact references. It does not introduce a
provider-neutral execution model or a Prime-specific record authority.

Provider errors, timeouts, missing output, and incomplete execution remain
explicit failures. A transport cannot turn them into successful trials.

The separate `prime_agent` integration runs the upstream Prime Agent executable
directly. JSON mode adapts staged artifact tasks on the existing local path;
ACP mode owns one persistent Prime process and a capability-scoped actor proxy
for one bounded interactive segment. The pump journey composition can alternate
these segments with exact, task-owned host controls. The proxy translates only
the current actor request and result models. The pump world owns host-control
eligibility and completion. A private journey checkpoint records coordination
phase and canonical references for process recovery; it is not a second causal
record. Task-world persistence, verification, evaluation, and Harbor paths
remain owned by their existing layers.

Local execution selects from one fixed set of adapter builders at the harness
composition edge. Tests inject a builder callable directly; production does
not expose a mutable adapter registry or a speculative local-environment
protocol.

The installed package keeps these adapters behind feature-owned extras.
Package import and CLI help are provider-free. A command checks only whether
its top-level optional runtime is present, reports the named extra when it is
absent, and then imports the runtime normally. Failures inside an installed
provider are not translated into missing-extra errors.

### Contributor and presentation surfaces

The CLI is the installed automation surface. The TUI and web UI present
catalogues, runs, evaluations, and review workflows. Public guides live on the
documentation site. Repository research may use the maintained APIs and
artifacts, but ignored research paths are not runtime dependencies.

## Dependency direction

Dependencies follow ownership, not a permanent numbered hierarchy:

- Boundary contracts depend only on foundational validation and value
  utilities needed to define that boundary.
- Task definitions and task worlds do not import adapters or providers.
- Shared continual-world code does not import a concrete world.
- Adapters, providers, and compute backends translate outward-facing protocols.
- Orchestration depends on task and execution boundaries without taking over
  task semantics.
- Evaluation consumes verifier and trial evidence; persistence does not import
  evaluation policy.
- CLI, TUI, web, reports, and research compose lower-level capabilities.
- A composition root may import concrete implementations to register them. The
  registered core must remain independent of those implementations.

`tests/test_package_ownership.py` enforces the small dependency rules that are
most important to keep mechanical: contracts and task worlds cannot import
optional provider runtimes, and task worlds cannot import provider adapters.

Pydantic models belong at untrusted, external, persisted, or cross-process
boundaries. Normal Python values are sufficient inside one owner. The
`contracts/` package is a boundary library, not a requirement that every
package or intermediate value depend on a universal schema.

## Repository ownership

A working directory does not determine ownership. Maintained artifacts belong
to these stable surfaces:

| Concern | Owner |
| --- | --- |
| Installed library and runtime behaviour | `src/aec_bench/` |
| Task-template semantics and packaged task data | `src/aec_bench/task_world_templates/` |
| Runnable benchmark task packages | `tasks/` |
| Expert-authored task sources | `seeds/` |
| Ready-to-use Harbor agents | `agents/` |
| Maintained repository commands outside the installed API | `scripts/` |
| Permanent tests and test support | `tests/` |
| Current architecture, contracts, invariants, protocols, and guides | `docs/` |

Research, planning, generated output, and local workspaces are not delivery
surfaces. If the product needs a generator, certifier, migration command, or
fixture, move it to its permanent owner before delivery.

## Related documents

- [Documentation index](README.md)
- [Boundary contract index](CONTRACTS.md)
- [Benchmark invariants](INVARIANTS.md)
- [Stable project navigation](PROJECT_STRUCTURE.md)
- [Interactive-world runtime protocol](protocols/interactive-world-runtime.md)
