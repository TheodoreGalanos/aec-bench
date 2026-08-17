# ABOUTME: Indexes the major protected, persisted, external, and cross-domain contracts in AEC-Bench.
# ABOUTME: Routes readers to authoritative models and protocols without copying implementation field lists.

# Boundary Contract Index

| Field | Value |
| --- | --- |
| Class | Normative |
| Status | Current |

This index explains who owns each major record family, where trust changes,
and which implementation is authoritative. The source model or generated
schema defines the exact fields. Protocol documents define multi-step behavior.

## Compatibility terms

| Term | Meaning |
| --- | --- |
| Protected | A documented public, external, persisted, or published boundary. Change it only through an approved compatibility decision. |
| Versioned | Persisted or external documents carry an explicit version or content identity. Readers validate that identity before use. |
| Internal | A pre-1.0 implementation boundary used inside this repository. Update all callers directly when it changes. |

A Pydantic model is not protected merely because it exists. Protection comes
from documented use outside its owner or from persisted data that must remain
readable.

## Contract families

| Family | Owner | Trust boundary | Compatibility | Authority | Surface |
| --- | --- | --- | --- | --- | --- |
| Task specification | Task authoring and loading | Repository or imported task material becomes runnable input | Protected where task packages are published; otherwise internal | [`TaskDefinition`](../src/aec_bench/contracts/task_definition.py) and task loaders | Persisted task package |
| Task instance and revision identity | Generation and harness | Selected task bytes become one exact execution identity | Protected when recorded in a dataset or trial | [`ResolvedTaskInstance`](../src/aec_bench/tasks/instance.py), `TaskReference`, and `DatasetTaskEntry` | Internal resolution; persisted references |
| Finite lifecycle execution | Lifecycle task and host | Stage-specific task evidence and actor results become one bounded host-controlled progression | Internal package and runtime contract; persisted accepted evidence is current-format only | [`EvidenceLifecycleSpec`](../src/aec_bench/contracts/evidence_lifecycle.py) and the [staged evidence protocol](protocols/staged-evidence-and-publication.md) | Packaged task, runtime state, and persisted accepted evidence |
| Experiment manifest | Experiment orchestration | User configuration becomes an executable plan | Internal, except documented CLI/config behavior | [`ExperimentManifest`](../src/aec_bench/contracts/experiment_manifest.py) | Persisted configuration |
| Trial and episode record | Harness and ledger | Execution, verifier, and artifact evidence becomes reportable benchmark evidence | Current persisted record; no retained historical reader | [`TrialRecord`](../src/aec_bench/contracts/trial_record.py) plus the owning episode or world protocol | Persisted and exportable |
| Evaluation result | Evaluation | Verifier output and review evidence become reward, validity, and diagnostics | Protected as part of a persisted trial or published result | [`EvaluationResult`](../src/aec_bench/contracts/evaluation_result.py) | Persisted and externally reported |
| Lifecycle verification | Lifecycle verification and evaluation | Canonical accepted lifecycle evidence becomes gates and optional semantic diagnostics | Internal until carried by a protected trial or published result | [`LifecycleVerificationResult`](../src/aec_bench/contracts/lifecycle_evaluation.py) | Internal result; persisted when referenced by trial evidence |
| Dataset manifest and identity | Dataset generation and storage | A set of task bytes becomes a named benchmark snapshot | Protected when published; content identity is authoritative | [`DatasetManifest`](../src/aec_bench/contracts/dataset.py) and dataset hashing/storage | Persisted and publishable |
| Adapter and Harbor execution | Adapters and harness | Harness input crosses into local model execution or the supported Harbor workflow and returns untrusted output | Internal adapter values; Harbor result documents are lenient ingestion boundaries | [`AdapterRequest` and `AdapterResult`](../src/aec_bench/adapters/base.py), the [Harbor workflow](../src/aec_bench/harness/harbor_workflow.py), and [Harbor ingestion models](../src/aec_bench/harness/harbor_contract.py) | Internal, cross-process, and external |
| Output completion and explicit commit | Adapter infrastructure and task contract | A fixed candidate artifact becomes structurally complete and, when required, bound by exact bytes | Versioned when persisted in trial evidence; adapter integration is internal | [`OutputCompletionContract` and `OutputCommitAttestation`](../src/aec_bench/contracts/output_completion.py) plus the shared [commit authority](../src/aec_bench/adapters/output_commit.py) | Request configuration, adapter result, and persisted attestation |
| Prime package and evaluation integration | Prime integration | Current public task or lifecycle material becomes an independently installed package; hosted samples return as untrusted provider evidence | Public command and external package behavior; samples normalize into current records | [`exporter.py`](../src/aec_bench/prime_lab/exporter.py), [`lifecycle_exporter.py`](../src/aec_bench/prime_lab/lifecycle_exporter.py), and [`eval_import.py`](../src/aec_bench/prime_lab/eval_import.py) | External package and provider ingestion |
| Artifact and evidence reference | Harness, ledger, and the producing domain | Filesystem or provider output becomes content-bound evidence | Protected when stored in a trial, dataset, freeze, or published record | `ArtifactReference` in [`trial_record.py`](../src/aec_bench/contracts/trial_record.py) and narrower owner-specific references | Persisted reference |
| Visibility classification | Task ownership and evaluation policy | Material enters public, calibration, or holdout handling | Protected | `Visibility` in [`task_definition.py`](../src/aec_bench/contracts/task_definition.py) and visibility checks in persisted records | Persisted and policy-bearing |
| Interactive-world execution | Interactive-world runtime and registered task worlds | An exact build and profile become one task-owned state, observation, action, transition, and evaluation loop | Internal functional core; task-owned persisted records where a world adds persistence | [`interactive_world.py`](../src/aec_bench/contracts/interactive_world.py), [`world_logic.py`](../src/aec_bench/worlds/runtime/world_logic.py), [`episode.py`](../src/aec_bench/worlds/runtime/episode.py), [`catalogue.py`](../src/aec_bench/worlds/catalogue.py), and the task functions described in [World authoring](world-authoring.md) | Internal, with protected owner-specific extensions |
| Installed world actor and host calls | Interactive-world runtime and concrete integration owners | An actor or host request crosses a process boundary and reaches the permitted task-owned authority | Versioned local actor protocol; pump-owned persisted run records | [`world_interface.py`](../src/aec_bench/contracts/world_interface.py), the shared [`world_actor`](../src/aec_bench/harness/world_actor/) authority, protocol, endpoint, and staged client, plus the [runtime protocol](protocols/interactive-world-runtime.md) | Internal, persisted, and installed JSON |

## Task specification

`TaskDefinition` is the validated runnable description of an artifact or
workspace task. It owns task identity, lifecycle, visibility, instruction,
environment, verifier, limits, tools, and task metadata. Task-family payloads
remain task-owned; the global contract does not attempt to model every output.

Executable interactive worlds use their registered world definition and
profile instead of pretending to be a static `TaskDefinition`. Both families
can still enter the same experiment, trial, evaluation, and reporting layers.

## Interactive World execution

An Interactive World is a task-owned causal process. Exact scenario inputs
create one authoritative state. The current state produces an explicit
actor-visible observation. A task-owned action is either rejected without a
state change or accepted as one transition to the next state. An accepted
action can change a later observation, task evidence, or evaluation result.

The task owns state, observation, action meaning, transition, domain
termination, and evaluation inputs. The episode host owns opaque decisions,
accepted-step advancement, recording, limits, and truncation. Evaluation runs
outside the live transition. Task termination and host truncation are separate.

The wastewater pump station and dam seepage monitoring task prove this
contract with different domain values and effects. The pump task changes
physical and stewardship state. The seepage task releases scheduled and
requested monitoring evidence before accepting an engineering response. They
share no production base class, task model, action union, persistence format,
or provider transport.

Host controls, autonomous clocks, persistence, recovery, snapshots, branches,
rollouts, multiple actors, staged evidence, provider integration, and
multi-session journeys are optional capabilities. A World does not acquire
them only because another World uses them.

The current installed `world_session.py` request and the host-control part of
`world_interface.py` are stewardship-only capabilities. Their run, episode,
branch, and snapshot values are not the minimum Interactive World contract and
must not be imposed on the dam task or another non-persistent World. Keep these
contracts unchanged until a second installed persistent World proves the same
semantics and an approved persisted-record cutover exists.

World profile identity covers task-owned scenario meaning and causal inputs.
World build identity covers executable transition, observation, and related
task semantics. Agent, model, provider, Harbor, and integration configuration
belong to execution evidence. Changing execution metadata alone must not
change a world profile identity. Changing a causal profile input or executable
world source must change the applicable profile or build identity.

## Task instance and revision identity

`ResolvedTaskInstance` joins a validated task definition to the paths used by
one harness invocation. It is an internal path bundle, not durable identity.

Durable identity is recorded as content or source revision:

- `TaskReference.task_revision` binds a trial to the task revision observed by
  its execution/import path;
- `DatasetTaskEntry.content_hash` binds a dataset entry to task-directory
  content; and
- world builds identify exact executable source artifacts, profiles identify
  exact task-owned data, and task-owned run records bind replay state.

Do not infer a revision from a mutable directory name.

## Finite lifecycle execution

A finite lifecycle declares one bounded ordered set of stages before
execution. The task owns stage objectives, visible evidence, required results,
completion meaning, and verification. The host owns release, the active stage,
result acceptance, progression, failure, and finalisation.

No more than one stage is active. An invalid result leaves the current stage
and prior accepted results unchanged. One accepted result completes the active
stage once, but it does not let the actor activate the next stage. Completion
occurs only after the host accepts the terminal result and records lifecycle
completion.

Task calculations, evidence fields, submission shapes, and verifier rules stay
with the task owner. Conditional evidence, calculation operations, source
revisions, variants, provider sessions, and deterministic smoke actors are
optional capabilities. They are not required by the finite lifecycle
contract.

The current implementation uses the staged-evidence subtype described in
[Staged evidence and publication](protocols/staged-evidence-and-publication.md).
`EvidenceCheckpointSpec.depends_on` is only an earlier-checkpoint acceptance
precondition inside the declared list order. It does not provide graph
scheduling, branching, or parallel execution. Conditional evidence is an
experimental staged-evidence capability with no registered task consumer.
The current restriction against mixing conditional evidence and operations is
host implementation policy for this subtype, not finite-lifecycle meaning.

## Trial and episode records

`TrialRecord` is the canonical reportable trial envelope. It binds task, agent,
environment, inputs, outputs, evaluation, timing, cost, completeness, and
optional execution-family provenance. `OutputRecord` distinguishes ordinary
termination from host truncation and records the exact current completion,
stop, or failure reason when one exists. `CostRecord` is the sole aggregate
usage and cost authority.

Lifecycle episode requests/results and world-session records are operational
protocol records. They do not replace `TrialRecord`. Finalization validates and
references their durable artifacts from the canonical trial evidence. A
task-owned episode is represented by one verified `episode_artifact` reference;
the shared trial record does not copy its snapshots, transitions, temporal
facts, or replay model. Lifecycle request and run-state readers accept only the
current shapes and do not migrate prior local run directories.

A finite lifecycle uses `lifecycle_id` and checkpoint identity. It does not use
`world_id`. A harness-program study groups exact task snapshots with
`task_set_id` and `task_set_sha256`; these fields do not identify an interactive
world.

Trial records are append-only evidence once accepted. Internal builders and
temporary run directories remain replaceable implementation.

The current trajectory is entry-only JSONL. The writer does not emit a format
header, and the reader does not select or decode historical versions. Ordinary
adapter runs use it as the ordered interaction authority. Exact provider or
sealed transcripts remain separate only when their producing boundary needs
them.

## Evaluation results

`EvaluationResult` owns reward, mechanical validity, breakdowns, error
taxonomy, confidence, attributable annotations, and registered task-specific
evaluation extensions. Invalid or unparseable output cannot carry positive
reward. Presentation code consumes this record and does not recalculate a
competing result.

Task-specific verifier details can remain in their owning evidence artifact
while the common evaluation envelope reports the normalized result.

The current `EvaluationResult.stewardship` field is a frozen persisted-format
exception for pump records. It is not a template for adding dam, facade, or
hydraulic fields to the shared envelope. New task-specific details stay in a
typed owner-specific evidence artifact and enter the common result through its
normalized fields and evidence reference. Moving the stewardship field needs
an approved persisted-record migration.

Lifecycle verification records are boundary contracts. Lifecycle progression
can validate and store them without importing scoring policy from
`aec_bench.evaluation`. The evaluation package owns scoring functions; the
contract package owns the validated result shape.

## Dataset manifests and immutable identity

`DatasetManifest` binds a name and version to ordered task entries, source
provenance, and a manifest content hash. Each task entry carries its own content
hash. Validation recomputes those identities against task bytes.

A local manifest can be deliberately regenerated or overwritten through an
explicit maintenance command. That creates different content identity. A
published benchmark claim must cite the content hash, not rely on a mutable
`name@version` label alone.

## Provider request and result envelopes

The harness-facing adapter contract is `AdapterRequest` to `AdapterResult`.
Local execution calls the selected adapter directly. Hosted execution lowers
the current experiment manifest into Harbor configuration, dispatches through
the synchronous Harbor workflow, and imports Harbor result documents through
lenient ingestion models before repository-owned validation and normalization.

These are related boundaries, not one universal provider schema. Provider
configuration, resolved model identity, stop reason, failure kind, raw output,
and collected artifacts must survive normalization when they can affect
validity. Aggregate usage normalizes into `CostRecord`; it is not duplicated in
`OutputRecord.agent_result`.

The local composition edge uses `build_local_adapter` from
[`local_registry.py`](../src/aec_bench/adapters/local_registry.py) for its fixed
current adapter set. The file name is historical; it does not expose a mutable
registry. Tests pass an adapter-builder callable directly when they need a
deterministic substitute.

Prime remains separate from Harbor. General Prime packages project the current
`TaskDefinition` and task content revision; they reject holdout tasks. Stateful
packages give the actor a task workspace without `tests/`, while the verifier
uses its own full private task copy. Hosted Prime samples map provider
completion, truncation, and error facts to `OutputRecord`; reward never decides
termination. The provider sample, conversation, and submitted output are
retained as SHA-256-bound `ArtifactReference` values, while score and validity
remain `EvaluationResult` authority.

Adapter-only extraction metadata must not become task-semantic output. The
lambda-RLM `__confidence__` key is reserved for extraction confidence and is
removed before semantic payloads reach generation, persistence, or review.

The DeepSeek Harness adapter qualifies two limits. `timeout_sec` caps the whole
AEC-owned worker process group. On timeout, the runtime retires that process
group. A positive `max_tokens` value caps output for each conversation-model
request through the official SDK. A provider `max-tokens` terminal reason maps
to partial output and a token-budget stop; it cannot map to success. The
composition and runtime evidence record both configured values.

The adapter rejects `max_turns`, `max_tool_calls`, and `max_context_tokens`.
The current public Harness hooks cannot both stop these operations at the exact
boundary and retain a typed budget terminal reason. These limits remain
unsupported until that full contract can be enforced and recorded.

Each DeepSeek trial writes one validated evidence manifest. The manifest keeps
the adapter, model, installed SDK and runtime versions, limits, execution
status, composition modes, optional plugins, and redaction actions readable.
Each retained artifact has one SHA-256 entry in that manifest. Summary fields
do not duplicate artifact hashes. `RuntimeExecutionAttestation` binds the
manifest SHA-256 when the adapter provides one; attestations from other
adapters keep their existing shape.

The model identifier must use `provider:model`. `azure:` requires
`AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_ENDPOINT`; the runtime normalizes the
endpoint to `/openai/v1`. `deepseek:` requires `DEEPSEEK_API_KEY` and uses
`DEEPSEEK_BASE_URL` when set or the public DeepSeek API otherwise. The shared
entrypoint records the provider name in the execution payload and never
serializes the credential. The Azure profile uses the Harness `azure` route
through the generic provider plugin and omits DeepSeek-only reasoning fields.
The DeepSeek profile uses `deepseek-official`. Evidence records the external
provider and internal Harness route separately.

The Harbor child receives only the selected provider environment. The worker
then maps that configuration to `DSH_API_KEY` and `DSH_BASE_URL` and inherits
only those private values, locale, path, certificate values, and AEC-owned
runtime variables. Evidence records inherited variable names and a
credential-free provider endpoint, not secret values. Redaction changes only
owned runtime evidence. Its audit records file paths, categories, and
replacement counts. It does not change the candidate output.

The qualified DeepSeek compatibility conditions are:

| Treatment | AEC identity | DeepSeek identity | Optional plugin | Qualification proof |
| --- | --- | --- | --- | --- |
| Baseline | Installed AEC package version in the manifest | Exact SDK pin from `pyproject.toml`; worker requires the runtime distribution to match | None | Keyless real-composition suite |
| Native tool gateway | Same | Same | `@aec-bench/dsh-tools` protocol v2 with exact `NativeToolDefinition` names and JSON schemas | Authenticated endpoint tests plus lifecycle and pump-world boundary tests |
| Explicit output commit | Same | Same | Named, versioned build copied into the trial evidence | Keyless rejection, repair, acceptance, and stability suite |

The manifest states that resolved composition and resolved tool-surface dumps
are unavailable. The pinned SDK path does not expose them. The adapter retains
the exact Cordis input and does not claim stronger evidence.

For native-tool runs, the manifest records the exact tool names and copied
plugin artifact. The AEC host supplies each model-facing parameter schema
explicitly through `NativeToolDefinition`. The endpoint validates requests
against that schema and gives the handler a hidden `NativeToolInvocation` with
the DeepSeek session, tool-call, turn, generation, cancellation, and trusted
request identity. A world action uses that trusted identity; the model-facing
schema cannot supply or replace it.

`NativeToolRequestSemantics` identifies the component that owns logical
request admission. The gateway owns replay for generic non-world tools. A
world definition uses `handler-authority`: the gateway validates and forwards
each exact retry, while `ActorInvocationAuthority` owns the actor principal,
frozen catalogue identity, request fingerprint and table, action budget, total
dispatch order, terminal latch, and semantic evidence. A transport correlation
does not change logical world-action identity.

`WorldActorEndpoint` exposes the same authority to a scoped local process. The
outer request and response require protocol `aec-bench/world-actor/1` and one
transport request ID. The authenticated Unix-socket transport accepts one
UTF-8 JSON object plus newline, returns one JSON object plus newline, and then
closes the connection. The actor cannot supply a run, profile, branch, host
control, verifier, evaluation, or authority selector. An envelope without the
protocol version is invalid.

The standalone `aec_world` client uses only the Python standard library. It
creates a logical action request ID before it opens the socket and does not
automatically retry actions. A transport failure after an invoke can have an
`unknown` outcome. Resolution must retain the same logical request ID. Client
installation is content-addressed and rejects symbolic links or different
existing content. Prime skill instructions are separate from this client
source.

The handler returns `NativeToolResponse`. Only its generic `conclude-turn`
disposition can conclude the current model turn; the plugin does not inspect a
tool name or task result field. Cancellation crosses the socket into a
cooperative handler token. Endpoint close has a deadline and records either a
quiescent close or the unsettled and unknown request identities. A
non-quiescent close cannot produce a completed adapter result. The sealed close
record prevents late handler output from changing finalized evidence. The
provider plugin cannot add shell access, world host controls, verification, or
reward authority.

The actor authority closes separately from the native transport. It records a
versioned append-only JSONL stream for the full trial actor, including all model
segments. A non-quiescent or unknown authority outcome blocks a complete
pump-station trial record. The task-owned world repository remains the
transition and replay authority; the actor stream records admission and
dispatch semantics at the actor boundary.

## Output completion and explicit commit

`OutputCompletionContract` is a task-owned, reward-blind structural contract
for the fixed expected output path. The current supported format is
`markdown_final_fenced_json`. It checks the final JSON block and its required
top-level keys. It does not check correctness, reward, hidden tests, or verifier
results.

The shared adapter commit authority safely reads the fixed path without
following symbolic links, limits the accepted file size, requires UTF-8,
compares the initial artifact, evaluates the declared structure, and binds the
accepted bytes in `OutputCommitAttestation`. It also revalidates the artifact
after acceptance so a later mutation cannot retain commit authority.

Adapter-specific code owns how an agent requests commitment. The RLM adapter
owns `COMMIT_OUTPUT()` injection, reminders, and turn-state integration. For a
DeepSeek Harness trial that requires commitment, the adapter exposes the shared
authority through an authenticated trial-local Unix socket. Its optional
`aec_commit_output` Cordis tool takes no arguments and concludes the Harness
turn only after that authority accepts the fixed artifact. The endpoint does
not accept an output path from the model, and its evidence does not retain the
capability token. A rejected call is nonterminal and can be repaired.

The shared authority and the DeepSeek transport do not run task verification.
Harbor ingestion independently checks a persisted attestation against the
collected artifact and task contract before it trusts the claim.

## Artifact and evidence references

`ArtifactReference` binds kind, path, media type, and SHA-256 for evidence
attached to a trial. Other domains use narrower references when they need extra
identity, lineage, visibility, or authority fields.

A reference is valid only when the owning protocol verifies the referenced
bytes and their relationship to the parent record. A path string alone is not
artifact integrity. Do not collapse task evidence, provider output, world
snapshots, and dataset entries into one global evidence model merely because
they all contain hashes.

Detailed lifecycle rules live in
[Staged evidence and publication](protocols/staged-evidence-and-publication.md).

## Visibility classification

`Visibility.PUBLIC` and `Visibility.HOLDOUT` are independent of lifecycle,
difficulty, task name, and storage path. Importers and evaluators preserve the
explicit value. Historical records that omit visibility remain unknown and are
ineligible for operations that require a public or holdout classification.
Each exporter and evaluator must enforce the visibility accepted by its own
documented boundary.

## Contract design rules

- Validate untrusted, external, persisted, and cross-process data before use.
- Use strict models for repository-owned boundary documents and lenient models
  only where an external producer may add fields.
- Keep task-specific payload meaning with the task owner.
- Version a document family only when its persisted or external shape requires
  independent evolution.
- Add a hash only when it protects a named integrity claim.
- Add an ID only for durable identity, correlation, replay, stale-action
  detection, or external reference.
- Update all repository callers when an internal pre-1.0 contract changes.
- Do not preserve an obsolete internal envelope with a compatibility adapter.
