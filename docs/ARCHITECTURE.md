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

The product has distinct artifact, lifecycle, and Interactive World execution families. They share task selection, experiment
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
2. Resolve one `ResolvedTaskInstance` and expand the experiment into
   `PlannedTrial` values.
3. Call `run_experiment()`, which applies `run_trial()` directly for each local
   trial. `LocalTaskRuntime.run_once()` performs one adapter execution in one
   isolated workspace.
4. Let an `AttemptRecipe` create and select attempts without verifier access.
   `run_trial()` verifies only the selected workspace, builds one
   `TrialRecord`, materializes its artifacts, and removes attempt workspaces.
5. For Harbor, use the separate dispatch-and-import runtime through the same
   `run_experiment()` boundary. Harbor accepts only recipe specifications that
   its transport supports.
6. Persist records through the ledger owner. Evaluation can summarize the
   returned records directly without another ledger query.

`HarnessSpec` describes runtime capabilities, bindings, contracts, and
budgets. It does not control attempt branching or selection. Interactive-world
and lifecycle runtimes do not use this artifact-task attempt path.

### Finite lifecycle composition

Finite staged lifecycles use one checkpoint coordinator and one functional
application surface. `release_checkpoint()`, `submit_checkpoint()`,
`read_lifecycle()`, `revisit_checkpoint()`, `branch_lifecycle()`, and
`run_lifecycle()` control canonical state. A branch can start only from a
submitted checkpoint. It receives the accepted prefix through that checkpoint
and continues through the same coordinator.

`LifecycleTrial` binds a `PlannedTrial` to one validated `CompiledLifecycle`,
one run location, one execution mode, and one visibility policy. Compilation
binds the materialized package bytes, lifecycle contract, executable source,
and operation protocol before execution.
`run_local_lifecycle()` dispatches to separate fresh-session and
persistent-session implementations because their memory and recovery rules are
different. Both return `LifecycleExecution`, which contains canonical state and
the agent and tool evidence needed for trial construction.

`run_lifecycle_trial()` executes, verifies, records one canonical invocation,
selects its evidence through one retention policy, finalizes one normal
`TrialRecord`, optionally persists that same record, and returns it. The default
policy uses the live package and run. A study can retain an immutable snapshot
before the core finalizer runs; it cannot construct a second current trial
record.
`run_lifecycle_experiment()` applies that operation to planned lifecycle trials
and returns the records in declared order. Lifecycle studies call these
functions and keep only their study design, immutable snapshot, recovery, and
selection policy under `experimentation.lifecycle_studies`.

The lifecycle API does not implement meta-harness. A lifecycle evaluator can
return these `TrialRecord` values to the separate runtime-independent
meta-harness API.

### Agent evolution

Evolution is one functional application path. `run_evolution()` composes task
and attempt planning, evaluation, variation, search policy, and persistence;
it does not create a second task executor or verifier. Its cycle is:

```text
search selection and exact parent evidence
        ↓
bounded AVO scratch loop
        ↓
private public-task revision checks
        ↓
one exact child, abstention, or budget exhaustion
        ↓
exact parent-child selection checks
        ↓
trusted search policy
        ↓
explicit commit, archive, graveyard, lineage, and swarm effects
```

The shell receives an explicit `Workspace`, `EvolutionConfig`,
`CandidateChecks`, and candidate proposer. `CandidateChecks` owns batch
planning, execution, and optional observation enrichment. Its `assess()` method
returns one exact `EvaluatedCandidate`. A child is checked before any gate or
workspace write can accept it. Parent and child evidence are never combined.

`EvolutionState` is the sole owner of the hill-climb active candidate, best
candidate, score, and stagnation state. Pure transition functions decide the
next state. The shell applies a canonical workspace commit only after an
accepted child. Rejected or invalid child material is written to the
graveyard. A proposal call operates on a scratch workspace and returns one
complete `CandidateProposal`.

The built-in proposer is bounded agentic variation (AVO). The application
passes one immutable `CandidateProposalRequest` after it selects the parent and
inspirations and checks the selected parent. The proposer creates a fresh
`RevisionEvaluation`, scratch workspace, and `AVOSession` for each call. The
revision boundary plans one fixed, candidate-independent public batch. AVO
checks the parent at revision `0`, then permits bounded scratch mutations and
exact revision checks. Each `RevisionAttempt` binds one revision to its material
and evidence. AVO can submit only the current evaluated revision. It returns a
`CandidateProposal` with a submitted child or one explicit terminal status;
selection, acceptance, canonical workspace state, archive, graveyard, and
lineage remain outside this result.

Conditional advice is an optional, bounded part of the same AVO call. The
advisor receives only an `AVOAdviceRequest` with the goal, selected
parent ID, strategy, bounded attempt summaries, projected remaining budget,
and trigger reason. It has no workspace, tools, evaluation, or outer-loop
authority. Validated advice is stored in the call-local `AVOState` and may
enter a later main-agent context in that call. It is not returned in
`CandidateProposal` and cannot change selection, parent, strategy, goal, budget,
evaluation, or any search effect.

AVO memory is bounded structured evidence from attempts. The application may
carry the returned memory into a later proposal request; it does not become
outer search state. Checkpoint schema `2` is the sole validated resume
authority for a durable call. Resume validates the run, variation, parent,
selection, development case order, budget, configuration identity, and current
scratch material. An incomplete external effect blocks retry until its owner
reconciles it. Unknown token or cost usage reaches the budget boundary as
unknown and fails closed when the matching limit is configured.

Quality-diversity runs keep explicit `QDState` for cell-selection and strategy
bandit feedback. The host selects the mutation strategy and shortlist. The
archive agent may select a parent and inspirations only within those host
constraints; it cannot change the strategy. An archive insertion is accepted
when it enters a new cell or improves a cell, even when it does not improve the
global score. Bandit and cell feedback updates once from that archive outcome.
Graveyard rescue is allowed only when the entry contains a resolvable
`rejected_snapshot` with the exact candidate ID.

Swarm execution uses `SwarmManager` as an asynchronous shell over the same
candidate/evidence boundary. Each `SwarmAssignment` contains exact parent and
inspiration snapshots. An agent returns a `SwarmAgentResult` containing only a
proposal and its agent cost; it does not submit a score, descriptor, or archive
decision. The manager checks the assigned parent and submitted child through
shared selection checks outside the shared-state lock. Archive and
graveyard effects, budget accounting, pure reduction, and `SwarmState` updates
are applied in one short locked section. `SwarmState` is immutable and is the
decision authority; the event log reports those decisions and is not state.
The manager persists `swarm_state.json`, exact candidate snapshots, archive,
graveyard, budget, lineage, notes, and events as separate owned outputs.

The durable ownership boundaries are:

| Concern | Owner |
| --- | --- |
| Selection batch planning, execution, and enrichment | `CandidateChecks` |
| Validity and score meaning | Evaluation |
| Candidate/evidence binding | Evolution functional core |
| Parent and inspiration selection | Search policy |
| Proposal goal and strategy | Search selection contract |
| Scratch planning, editing, diagnosis, and repair | AVO main agent |
| Revision task membership | Revision-check composition |
| Revision validity and score meaning | Evaluation |
| Final parent-child comparison | Selection-check composition |
| Acceptance | Search-specific trusted policy |
| Candidate persistence | Workspace/application shell |
| QD insertion | Archive adapter |
| Graveyard projection | Functional core |
| AVO checkpoint and private memory | AVO runtime |
| Inner stagnation trigger | Pure AVO advice policy |
| Advisor output | AVO advisor |
| Outer stagnation and swarm pivot | Existing search and manager state |
| Swarm concurrency | Async manager shell |
| Swarm decisions | Functional reducer |

`run_evolution_from_config()` is the composition root. It loads the workspace
and model clients, builds local or Harbor `CandidateChecks`, builds the AVO
proposer, and calls `run_evolution()`.
The `aec-bench evolve run` command is a thin caller of this function.

Best-of-K attempts stay inside one scored trial. Evolution cycles stay outside
the trial and use returned `TrialRecord` values as fitness evidence.

Deterministic templates and suite generation live with authoring and generation.
Generated instances remain derived artifacts. Runnable task directories contain
task semantics only. One optional `generation-manifest.json` beside the
generated set records the shared template source and per-instance replay inputs.
Task loading does not read this sidecar. The replay command regenerates into a
separate directory and compares runtime files before it reports success.

### Meta-harness composition

`aec_bench.experimentation.meta_harness` is the runtime-neutral public facade
for harness candidate studies. It supplies immutable generic candidate and
result values plus three direct functions:

- `evaluate_harness_candidate()` validates one non-empty set of `TrialRecord`
  evidence;
- `run_harness_study()` evaluates one baseline and one or more candidates; and
- `run_meta_harness()` performs a bounded propose, evaluate, assess, select,
  and refine process.

These three functions are async. An evaluator can return records directly or
return an awaitable. Python callers use `await`; synchronous CLI commands own
the single event-loop entry at their command boundary.

Callers own candidate values, assessment values, and every policy callback.
The core does not import artifact-task, lifecycle, interactive-world, adapter,
provider, Harbor, or Prime implementations. A runtime participates by supplying
one evaluator that returns its normal `TrialRecord` values. Failed and invalid
records remain assessment evidence.

Specialist qualification code still owns program materialisation, Harbor study
execution, repair diagnosis and patch creation, motif learning, promotion, and
persisted reports. Its overlapping candidate iteration uses the common
functional composition. Evaluation owns metric meaning.

### Learning Studies composition

`aec_bench.experimentation.learning_studies` is an optional experimentation
layer over existing trials. It compiles an authored finite study into exact
`PlannedTrial` values, coordinates isolated control and exposure arms through
caller-supplied operations, and consumes ordinary `TrialRecord` results.

The layer owns the controlled relationship between experiences, declared
learner continuity, feedback-release policy, study validity, and learning-level
comparison. It does not own task meaning, execution, verification, evaluation,
or model-weight training. An experience is one existing trial in a study; it is
not another task or runtime type.

Measurements use one named paired-difference shape. The assessor derives
validity from explicit evidence. It reports `controlled` only for an exposure
arm against a matched cold-control arm on the same probe. Within-arm and
treatment-to-treatment comparisons remain descriptive.

Generalisation measures one fixed learner on changed holdout material. Learning
transfer compares a learner that received a declared prior experience with a
matched cold learner on the same probe. A sequence without the required control
can describe behaviour, but it cannot support a controlled learning claim.

Learner state is separate from task, lifecycle, and world state. Every committed
learner transition is explicit. Probe feedback stays hidden until scoring is
complete, and probe-created learner state is discarded by default. Thin
environment adapters may translate these operations to their existing public
execution APIs. Execution and task owners do not import Learning Studies policy.

Artifact learning-family files are caller-selected TOML overlays. They name
exact existing task IDs, declare dimension values, and state directed authored
claims. They do not change task definitions, `VariationAxis`, generation, or a
global task catalogue. The exact `task_id` resolves through normal task loading;
a family file remains host-held and is not staged for the learner.

Repository-maintained studies form a task-like collection under
`learning_studies/protocols/`. Each study directory contains one `study.toml`
and one `family.toml`. The generic collection loader resolves family members
and relations into `LearningStudySpec`, then binds the caller's fixed agent,
compute configuration, and repetition count. The protocol directory contains
no task assets, execution runtime, or verifier logic. External callers can
supply another self-contained protocol directory by path. Collection discovery
is filesystem-based and is not a global study or task registry.

The local artifact adapter depends downward on the existing artifact harness.
It supports the Release A `reset`, `raw-history`, and `structured-memory`
treatments, one local single-attempt trial for each experience, named public
feedback projectors, and explicit consolidation callbacks. Each arm has a
separate writable root and each experience has a separate task workspace. Only
files below `.aec-bench-learning/` can enter a later experience. Raw history is
appended only after an explicit public feedback release. Structured memory is
read-only during a task and can change only during consolidation. Model and
adapter identity continue to come from the immutable planned trial.

The local lifecycle adapter resolves exact task IDs of the form
`lifecycle/<template_id>/<variant_id>` through the existing lifecycle catalogue;
templates without variants omit the final component. One adapter binding fixes
the lifecycle execution condition. The first binding supports only
`fresh_context` with `artifact_memory`. It provides reset and structured-memory
treatments. Each complete lifecycle uses its existing compiler, local harness,
verifier, recorder, and normal `TrialRecord` builder through
`run_lifecycle_trial()`.

Lifecycle learner state is adapter-owned and contains only `memory/` and
`feedback/`. Every experience, feedback release, and consolidation operation
uses a separate copy-on-write candidate. Feedback can change only `feedback/`,
and consolidation can change only `memory/`. Lifecycle package, run, hidden,
verification, and metrics files never enter this tree.

Local lifecycle execution has one optional `read_only_context_root` composition
input. When present, the workspace tool exposes it as `learner_context/` and
labels it as prior-task guidance that is not current task evidence. The root is
not part of lifecycle episode requests, package identity, run state, visibility
policy, or verifier input. Fresh checkpoint sessions receive the same context
projection. Direct lifecycle callers that omit the input keep their existing
workspace and prompt behavior.

Lifecycle feedback meaning remains task-owned. A feedback projector receives a
completed normal `TrialRecord` and constructs one explicit public view. The
lifecycle adapter checks JSON structure, size, unsafe keys, hidden paths, and
host paths before it writes or publishes the exact bytes. Feedback does not
enter later lifecycle context directly; only an explicit consolidation can
write to `memory/`.

Lifecycle outcome meaning also remains outside the common assessor. Study-owned
glue supplies explicit projection callbacks that read canonical reward or
task-owned gate scores from the existing record. Missing or malformed evidence
makes a projection ineligible; it is not changed to zero. The first maintained
lifecycle study uses the existing drainage gates and archived learner
submissions. It adds no lifecycle phase contract, global projection registry,
or `TrialRecord` field.

The [Gate A decision](adr/learning-studies-gate-a.md) records the field-level
extraction review and the concepts that remain adapter-owned.

`run_trial()` has one execution-owner seam that can atomically export the exact
selected actor snapshot before verification. The harness does not interpret
that export as learner state. The artifact adapter validates the reserved
namespace, constructs a new candidate learner snapshot, and leaves commit or
probe discard to the common runtime. Verifier files and task-workspace files do
not enter learner state.

The study recorder publishes complete adapter-supplied learner snapshots through
the existing artifact repository and writes ordinary trial records through the
existing ledger. A final step receipt is the resume authority. The event stream
is an append-only index over receipts, not a second execution or provenance
system. Assessment uses caller-supplied named outcome projections and retains
matched repetition values. Missing controls downgrade a usable comparison to
descriptive evidence; isolation, lineage, or probe-secrecy failures make it
invalid.

The A01 Stage 1 protocol proves the structural-transfer path. The A02 Stage 1
protocol adds matched cold, reset-after-acquisition, raw-history, and
structured-memory paths for an authored drainage applicability boundary. The
A03 Stage 1 protocol adds non-committing immediate and delayed probes, a neutral
intervening task, and an explicitly released conflicting public episode. The
A04 Stage 1 protocol adds separate component controls, both component orders,
and a composite target with task-owned component and integration projections.
These deterministic integration runs use real artifact tasks and verifiers but
a model-boundary test double. They prove the learning-study plumbing and do not
make model-learning claims. The programme charter and remaining programme
material stay maintained as
[Learning Studies research](research/learning-studies/programme.md).

The supported prose-intake process is a higher-order composition under
`experimentation.process_runtime`. It uses “problem model” for the generated
representation. It is not an interactive world and does not import the
interactive-world runtime. Low-level model execution and deterministic process
helpers remain under `harness`.

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

`aec_bench.worlds` projects that registration as stable discovery values,
creates provider-neutral `WorldTask` values, and loads exact registered
profiles. A file-backed world task uses `instruction.md` and `world.toml`.
`plan_trials()` expands artifact, lifecycle, or world task IDs through one
planner. `run_world_experiment()` maps planned world trials to one supplied
async world trial function and returns ordered `TrialRecord` values.

The dam and pump trial functions share one Prime actor-session integration.
They keep their state, journey, persistence, host controls, replay,
verification, and evaluation with the concrete world. The pump Harbor runner
uses the same complete-trial boundary. Dataset entries select their concrete
loader by `task_kind`; the top-level run application routes complete trials by
family and preserves planned order.

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
