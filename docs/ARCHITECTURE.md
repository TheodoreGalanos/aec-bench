# ABOUTME: Describes current AEC-Bench product flows, ownership boundaries, and dependency direction.
# ABOUTME: Separates implemented architecture from the proposed direction for future world-runtime simplification.

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
3. Run a provider-neutral adapter through a local or hosted compute backend.
4. Collect output, transcript, trajectory, and verifier artifacts.
5. Build an `EvaluationResult` and persist a `TrialRecord`.

Deterministic templates and suite generation live with authoring and generation.
Generated instances remain derived artifacts; the template, parameters, seed,
and implementation identity needed to reproduce them belong in provenance.

### Interactive worlds

An interactive world repeatedly exposes an actor-visible observation and
accepts an action that changes task-owned state. Host controls use a separate
authority surface. World state, action meaning, clocks, projections, events,
and verifier logic remain with the task world.

The current registered continual-world path provides:

- content-pinned world definitions and profiles;
- exact catalogue resolution for new work and recovery;
- separate actor and host-control envelopes;
- task-owned execution, branch, Harbor, and evaluation ports when supported;
- shared chosen-point rollout orchestration through an optional branch port;
- task-neutral local durability primitives; and
- evaluation registration for complete journeys and bounded continuations.

The public composition root currently registers two real consumers: the
wastewater pump-station stewardship world and the SSC-03 hydraulic interaction
world. The task-neutral continual package imports neither concrete world. See
the current [interactive-world runtime protocol](protocols/interactive-world-runtime.md).

Beneath those different orchestration paths, the continual runtime owns only
the small accepted-transition and action-rejection values shared by both real
consumers. Initial state, actor observation, transition functions, outputs, and
evaluation remain task-owned because the hydraulic and pump behaviors do not
honestly share one structural protocol.

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

### Durable artifacts

The ledger and artifact stores own persistence mechanics, integrity checks, and
queries. `TrialRecord` is the durable trial provenance envelope. Dataset
manifests identify immutable benchmark snapshots. Evidence-lifecycle and world
records add content-addressed artifacts where replay, recovery, or isolation
requires them.

Immutability is a property of accepted evidence, published datasets, and other
named records. It is not a requirement that every internal object, service, or
source file become a ledger event.

### Provider integrations

Adapters translate between the harness and agent execution. Compute backends
translate local or hosted execution. Provider modules and Harbor integration
sit outside task semantics. They may depend on task-neutral runtime surfaces;
task worlds and core contracts do not depend on provider SDKs, CLI, web, or TUI
modules.

Provider errors, timeouts, missing output, and incomplete execution remain
explicit failures. A transport cannot turn them into successful trials.

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

## Proposed direction

**Status: Proposed.** This section describes a direction for later PRDs. It is
not a claim about interfaces or packages that exist now.

The first functional-core step is implemented in
`src/aec_bench/task_world_templates/continual/world_logic.py`. It does not
replace the registered session, lifecycle, persistence, rollout, Harbor, or
evaluation paths.

Future world-runtime work may continue simplifying the current implementation
around:

- an imperative episode shell that owns limits, retries, provider calls, and
  session coordination;
- lossless episode recording that preserves observations, actions, tool calls,
  state references, failures, and timing needed for replay and audit;
- evaluation as a separate interpretation of recorded evidence;
- versioned training projections derived from canonical records rather than
  embedded in them; and
- provider integrations outside world logic.

This direction does not require snapshots, branching, rollout groups, Harbor,
cloud execution, event sourcing, or durable sessions in the base interactive
world boundary. Add those capabilities only where a real world and execution
path need them.

## Related documents

- [Documentation index](README.md)
- [Boundary contract index](CONTRACTS.md)
- [Benchmark invariants](INVARIANTS.md)
- [Stable project navigation](PROJECT_STRUCTURE.md)
- [Interactive-world runtime protocol](protocols/interactive-world-runtime.md)
