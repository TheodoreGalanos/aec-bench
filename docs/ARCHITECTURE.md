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
Generated instances remain derived artifacts. Runnable task directories contain
task semantics only. One optional `generation-manifest.json` beside the
generated set records the shared template source and per-instance replay inputs.
Task loading does not read this sidecar. The replay command regenerates into a
separate directory and compares runtime files before it reports success.

### Interactive worlds

An interactive world repeatedly exposes an actor-visible observation and
accepts an action that changes task-owned state. Host controls use a separate
authority surface. World state, action meaning, clocks, projections, events,
and verifier logic remain with the task world.

The registered interactive-world minimum provides:

- exact executable world builds and content-pinned profiles;
- exact catalogue resolution;
- private task-owned state, observation, action, transition, and evaluation
  functions;
- shared accepted-transition and rejection values; and
- the task-neutral episode shell for decisions, recording, limits, termination,
  and truncation.

The composition root registers wastewater pump-station stewardship and dam
seepage monitoring. The task-neutral world runtime imports neither concrete
world. See the current
[interactive-world runtime protocol](protocols/interactive-world-runtime.md).

Beneath those different orchestration paths, the world runtime owns the
small accepted-transition and action-rejection values plus the episode shell.
Initial state, actor observation, transition functions, outputs, and evaluation
remain task-owned. A finite lifecycle or calculation does not become a world
only because it also has state or ordered work.

The pump world adds installed actor and host-control boundaries, persistence,
recovery, branching, rollouts, temporal evidence, and provider integrations.
Those are optional pump capabilities, not part of the World minimum. The dam
seepage task uses the same functional and episode boundaries without those
capabilities.

Provider composition owns how the frozen actor catalogue is presented. Prime
uses `WorldActorEndpoint`. DeepSeek compiles the same catalogue into
`world_observe` and exact native action tools. Both paths use one
`ActorInvocationAuthority` contract for actor identity, admission, order,
budget, replay, terminal state, and evidence. A task-world package does not
define provider-specific action wrappers.

Interactive worlds and artifact tasks meet at the experiment and evidence
layers. An interactive world does not need to pretend that each action is a
workspace submission, and an artifact task does not need a world-session API.

## Capability ownership

### Task authoring and compilation

Task contracts define runnable metadata and visibility. Task loaders,
templates, generators, and task-world compilers turn repository sources into
validated runnable material. Task-family semantics stay with their task or
template owner.

Task-genome extraction creates derived review evidence. One task snapshot owns
the source identity; relative source spans locate supporting material without
copying task configuration, instructions, verifier source, or per-file hashes
into the review. Review metadata and decomposition do not participate in task
or dataset identity. The artifact repository stores a review only when a
workflow needs durable review history.

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

Evaluation also owns the public evaluation regime. One canonical
`EvaluationRegimeEnvelope` embeds critics, budgets, and observable policies.
`ArtifactRepository` publishes that envelope once, and its `ArtifactRef`
digest is the compatibility identity used by runs, outcomes, monitors, and
governance. Hidden candidate, split, verifier, and acceptance material stays in
separate assignment or authority-owned escrow records. The regime can consume
World evaluation evidence, but it does not own or reproduce World transitions.

Cross-task model execution and review coordination belong to
`harness/model_execution`. Task-specific evaluation, including wastewater pump
stewardship scoring, remains with the task package.

### Durable artifacts

The ledger and artifact stores own persistence mechanics, integrity checks, and
queries. `ArtifactRepository` publishes exact bytes and canonical model bytes
as `ArtifactRef` values, then verifies ID, size, and digest on each read.
An evaluation regime is one independently published canonical envelope. Its
artifact digest replaces compatibility checks over policy and critic hash
matrices.
Kernel, Harness, execution-program, evaluation, stage, task-snapshot, and
run-plan contracts remain plain domain models. Their joins use stable IDs,
typed references, direct values, and named commitments. They do not calculate
or carry a universal self-digest. A legacy compatibility reader validates old
self-addressed JSON before it creates a plain current model.
`RunPlan` owns the internal execution join. The ledger publishes one
`PublishedRunPackage` archive that contains the plan, exact trial references,
and all referenced artifact bytes. The archive receives one `ArtifactRef` and
is the portable run-package identity. Import verifies the complete archive
before it publishes any contained bytes.
`RunManifest` owns identity shared by all trials in one run. It records the
dataset, source, agent, runtime, provider route, evaluation regime, and
expected authorities once. `TrialRecord` references that identity by
`run_id`, and records execution, evaluation, and evidence status separately.
A full clean Git revision plus repository-relative task path, or one detached
task-package `ArtifactRef`, identifies each exact runnable task. Review data is
separate and a declared stage graph belongs to a stable review profile. The
provider route stays in `RunManifest`; it does not participate in task identity.

`TrialRecord` references evidence authorities; it does not copy task-owned
episode state or replay facts into a second shared model. `TrialOutput` owns
termination versus truncation and the final runtime reason. `CostRecord` owns
aggregate model calls, token usage, cache usage, advisor usage, and estimated
cost. Actor evidence and task-owned World or lifecycle evidence remain
separate `AuthorityEvidenceRef` values. The actor invocation authority returns
its one final reference after quiescent close. Optional subsystem detail uses
typed extension artifacts. Reports consume these canonical fields and never recover
aggregate usage from the open-ended provider metadata map.

`trajectory.jsonl` is the current ordered interaction record for ordinary
adapter runs. It contains validated entries only and has no version header or
historical reader. Provider transcripts remain only where an external or
sealed evidence workflow requires their exact representation.

Immutability is a property of accepted evidence, published datasets, and other
named records. It is not a requirement that every internal object, service, or
source file become a ledger event.

The [provenance policy](PROVENANCE_POLICY.md) classifies source identity,
artifact integrity, domain identity, compatibility, event time, commitments,
and qualification fields. It is a contributor and review boundary, not a new
runtime owner. Each domain and operational authority continues to own the
evidence for the facts it controls.

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

DeepSeek Harness subagents are disabled. Before they can be enabled, the
adapter must maintain one trial-scoped aggregate across the root session and
all descendant sessions. This aggregate must cover model and tool calls,
input, output, and cache tokens, and cost. The runtime must enforce a limit
before the next affected operation, propagate cancellation to descendants,
and retain complete child evidence. Root-session counters are not aggregate
trial evidence.

The DeepSeek adapter owns its trial manifest, runtime-file redaction, and
optional plugin copy. The execution entrypoint does not interpret that
provider evidence. It validates one provider-manifest `ArtifactRef` and binds
the `provider_evidence` role into the runtime execution attestation. The trial
record retains that exact manifest reference once.

The optional `@aec-bench/dsh-tools` Cordis plugin is a transport gateway, not a
tool authority. The AEC host supplies one exact per-run manifest from explicit
`NativeToolDefinition` values. The plugin registers those JSON schemas and
forwards calls to an authenticated trial-local Unix socket. The endpoint owns
trusted invocation identity, cancellation propagation, generic turn
disposition, generation finalization, and bounded transport close reporting.
For generic non-world tools, it also owns request replay. World definitions use
`NativeWorldToolTransport` and delegate logical request admission, replay,
budget, action order, terminal state, and semantic evidence to one trial-wide
`ActorInvocationAuthority`. The authority depends only on the provider-neutral
world host contract. It has no host-control, verification, evaluation, or
reward access. The pump-station Harbor journey can alternate fresh DeepSeek
model segments with the same authority instance and the deterministic
task-owned Operations controls used by the Prime pump journey.

The shared adapter entrypoint owns provider selection and host credential
allowlisting. A DeepSeek Harness model uses `provider:model`, and the selected
provider is stored in the non-secret execution payload. The Harbor agent passes
only that provider's approved environment values. The DeepSeek worker maps
them to private Cordis names and records the selected provider in trial
evidence. The worker selects one provider-specific Cordis profile. Azure uses
the generic Harness provider plugin on an OpenAI-compatible `azure` route.
DeepSeek uses the `deepseek-official` route. This keeps provider-specific wire
fields with the plugin that owns that protocol.

Provider-neutral adapter infrastructure owns safe output-commit evaluation,
exact-byte attestation, and post-commit stability checks. An adapter owns only
its model-visible commit surface and turn integration. The RLM adapter owns the
`COMMIT_OUTPUT()` command and reminders. The DeepSeek Harness adapter owns the
authenticated trial-local endpoint and the optional `aec_commit_output` Cordis
tool. Neither adapter owns a separate structural evaluator or attestation
implementation. Accepted commitment proves the public output structure and
exact bytes, not verifier success or reward.

The separate `prime_agent` integration runs the upstream Prime Agent executable
directly. JSON mode adapts staged artifact tasks on the existing local path.
ACP mode owns the Prime process, protocol, isolation, explicit generic skills,
and session evidence. `harness/world_actor` owns the provider-neutral,
capability-scoped `aec-bench/world-actor/1` transport, semantic invocation
authority, and standalone staged client. The endpoint routes only installed
world actor calls and does not interpret world state. Prime owns only its skill
instructions and session composition.
`harness/pump_station_prime` owns the concrete pump bounded session, guided
treatment, and journey composition. The pump journey can alternate fresh Prime
sessions with exact task-owned host controls.
The pump world owns host-control eligibility and completion. A private journey
checkpoint records coordination phase and canonical references for process
recovery; it is not a second causal record. Task-world persistence,
verification, evaluation, and Harbor paths remain owned by their existing
layers. Read-only treatment and trajectory analysis belongs to
`experimentation/qualification`; it does not change canonical evaluation.

`harness/dam_seepage_prime` owns one concrete bounded Prime composition for the
dam monitoring world. It binds the existing in-memory episode to the shared
world actor authority, then runs task evaluation only after the endpoint closes
completely. It does not add pump persistence, host controls, journey
continuation, or a second dam evaluation.

`harness/hydraulic_review_prime` is a separate concrete composition for the
stormwater hydraulic-review lifecycle. It starts one fresh Prime ACP session
for each host-owned checkpoint.
Its scoped endpoint exposes only actor-visible lifecycle files, declared
operations, and one proposed submission. The existing lifecycle host validates
and archives that proposal and controls checkpoint advance. Prime session
state, lifecycle state, task verification, and benchmark validity remain
separate authorities.

The pump, dam, and hydraulic-review integrations share the generic Prime process
and ACP boundary. The two worlds also share the installed `aec_world` client,
versioned transport, invocation authority, actor request and result models, and
Open or Planned skill composition. Their
world hosts, persistence, continuation, action meaning, replay, and evaluation
stay task-owned. The hydraulic-review lifecycle has a different scoped file and
submission boundary. These concrete integrations now support comparison, but
they do not justify one shared journey or task-semantics abstraction.

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
- Shared world-runtime code does not import a concrete world.
- Adapters, providers, and compute backends translate outward-facing protocols.
- Orchestration depends on task and execution boundaries without taking over
  task semantics.
- Evaluation consumes verifier and trial evidence; persistence does not import
  evaluation policy.
- CLI, TUI, web, reports, and research compose lower-level capabilities.
- A composition root may import concrete implementations to register them. The
  registered core must remain independent of those implementations.

`tests/test_package_ownership.py` enforces the small dependency rules that are
most important to keep mechanical: expected owner roots cannot disappear,
contracts and task domains cannot import optional execution runtimes, shared
environment runtimes cannot import concrete implementations, concrete owners
cannot import their composition catalogue, and owner packages cannot form a
strongly connected component.

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
| Artifact-task template semantics and packaged task data | `src/aec_bench/templates/` |
| Interactive-world runtime and concrete worlds | `src/aec_bench/worlds/` |
| Finite staged lifecycles and concrete lifecycle definitions | `src/aec_bench/lifecycles/` |
| Proposal, governance, qualification, and study policy | `src/aec_bench/experimentation/` |
| Runnable benchmark task packages | `tasks/` |
| Expert-authored task sources | `seeds/` |
| Ready-to-use Harbor agents | `agents/` |
| Maintained repository commands outside the installed API | `scripts/` |
| Permanent tests and test support | `tests/` |
| Current architecture, contracts, invariants, protocols, and guides | `docs/` |

Domain calculations and technical verification stay with the task, template,
lifecycle, or world that owns their meaning. Extract a shared domain package
only after two real benchmark owners need the same stable behaviour.

Research, planning, generated output, and local workspaces are not delivery
surfaces. If the product needs a generator, certifier, migration command, or
fixture, move it to its permanent owner before delivery.

## Related documents

- [Documentation index](README.md)
- [Boundary contract index](CONTRACTS.md)
- [Benchmark invariants](INVARIANTS.md)
- [Stable project navigation](PROJECT_STRUCTURE.md)
- [Interactive-world runtime protocol](protocols/interactive-world-runtime.md)
