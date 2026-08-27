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
| Task genome review | Tasks and feedback | A derived genome and its source spans become review evidence for one exact task snapshot | Internal; independently retained reviews use current-format artifacts | [`TaskGenomeReview`](../src/aec_bench/contracts/task_genome.py), `TaskSnapshotRef`, and `ArtifactRef` | Regenerable review; optional persisted artifact |
| Generated-task handoff and replay | Task generation | Generated runnable paths pass in process to normal task loading; template sources and sampling inputs remain optional reproducibility data | `GeneratedTaskSet` is an in-process value; the schema 1 sidecar is not a runtime task contract | [`GeneratedTaskSet`](../src/aec_bench/generation/contracts.py), [`GenerationManifest`](../src/aec_bench/generation/replay.py), and the `generate replay` command | Internal handoff and optional persisted sidecar |
| Finite lifecycle execution | Lifecycle task and host | Stage-specific task evidence and actor results become one bounded host-controlled progression | Internal package and runtime contract; persisted accepted evidence is current-format only | [`EvidenceLifecycleSpec`](../src/aec_bench/contracts/evidence_lifecycle.py) and the [staged evidence protocol](protocols/staged-evidence-and-publication.md) | Packaged task, runtime state, and persisted accepted evidence |
| Experiment manifest | Experiment orchestration | User configuration becomes an executable plan | Internal, except documented CLI/config behavior | [`ExperimentManifest`](../src/aec_bench/contracts/experiment_manifest.py) | Persisted configuration |
| Learning Study design and evidence | Experimentation | An authored protocol composes exact task members and family relations, then compiles to existing trials; committed state and explicit comparison-validity evidence stay outside `TrialRecord` | Internal Release A persisted contracts | [`LearningStudyProtocolSpec`, `LearningStudySpec`](../src/aec_bench/contracts/learning_study.py), [`LearningFamilySpec`](../src/aec_bench/contracts/learning_family.py), [`learning_study_evidence.py`](../src/aec_bench/contracts/learning_study_evidence.py), [`learning_study_assessment.py`](../src/aec_bench/contracts/learning_study_assessment.py), and the [Gate A decision](adr/learning-studies-gate-a.md) | Maintained or caller-selected protocol directory, compiled plan, append-only receipts and sequenced events, ordinary trial ledger, and pair-level paired-difference assessment |
| Evolution workspace candidate lineage | Experimentation and feedback | Mutable workspace files become exact Git source and explicit candidate lineage | Workspace manifest schema 1; legacy labels require an explicit migration plan | [`WorkspaceCandidateVersion`, `WorkspaceManifest`, and `WorkspaceMigrationPlan`](../src/aec_bench/contracts/evolution.py) plus [`Workspace`](../src/aec_bench/evolution/workspace.py) | Persisted workspace Git metadata and manifest |
| Evolution functional search and swarm coordination | Evolution application and swarm manager | Exact candidate material is paired with its own evaluation evidence before policy or shared effects use it | Internal pre-1.0 values; no new public schema promise | [`EvaluatedCandidate`, `CandidateEvaluationBatch`, `CandidateProposal`, `SwarmAssignment`, `SwarmAgentResult`, and `SwarmState`](../src/aec_bench/evolution/core.py), [`evaluation.py`](../src/aec_bench/evolution/evaluation.py), and [`swarm/core.py`](../src/aec_bench/evolution/swarm/core.py) | In-process functional values, AVO checkpoints, and swarm state outputs |
| Run plan and published run package | Harness and ledger | One internal execution plan and its trial records become one portable retained package | Internal `RunPlan`; published package schema 1 | [`RunPlan` and `PublishedRunPackage`](../src/aec_bench/contracts/run_bundle.py), [`TaskSnapshotRef`](../src/aec_bench/contracts/task_snapshot.py), and [`run_package.py`](../src/aec_bench/ledger/run_package.py) | Internal plan; persisted and exportable package |
| Trial and episode record | Harness and ledger | Execution, verifier, and authority evidence becomes reportable benchmark evidence | Protected schema 2; no historical reader | [`RunManifest` and `TrialRecord`](../src/aec_bench/contracts/trial_record.py) plus the owning episode or world protocol | Persisted and exportable |
| Evaluation regime | Evaluation | Observable evaluation policy becomes one independently published compatibility identity | Envelope schema 1; legacy component plans migrate only when all inputs resolve | [`EvaluationRegimeEnvelope`](../src/aec_bench/contracts/evaluation_plane.py), `EvaluationRegimeRef`, and [`regime.py`](../src/aec_bench/evaluation/regime.py) | Persisted and independently publishable |
| Evaluation result | Evaluation | Verifier output and review evidence become reward, validity, and diagnostics | Protected as part of a persisted trial or published result | [`EvaluationResult`](../src/aec_bench/contracts/evaluation_result.py) | Persisted and externally reported |
| Lifecycle verification | Lifecycle verification and evaluation | Canonical accepted lifecycle evidence becomes gates and optional semantic diagnostics | Internal until carried by a protected trial or published result | [`LifecycleVerificationResult`](../src/aec_bench/contracts/lifecycle_evaluation.py) | Internal result; persisted when referenced by trial evidence |
| Dataset manifest and identity | Dataset generation and storage | A semantic task selection resolves to one exact Git source or detached bundle | Protected schema 2 and immutable references | [`DatasetManifest`, `RepositoryDatasetRef`, and `BundleDatasetRef`](../src/aec_bench/contracts/dataset.py) | Persisted and publishable |
| Public library catalogue | Templates and tasks | Public template and seed source becomes one site-facing content document | Protected schema; the current writer emits schema 2 | [`LibraryCatalogue`](../src/aec_bench/contracts/library_catalogue.py) and [`library_export.py`](../src/aec_bench/tasks/library_export.py) | Public JSON export |
| Adapter and Harbor execution | Adapters and harness | Harness input crosses into local model execution or the supported Harbor workflow and returns untrusted output | Internal adapter values; Harbor result documents are lenient ingestion boundaries | [`AdapterRequest` and `AdapterResult`](../src/aec_bench/adapters/base.py), the [Harbor workflow](../src/aec_bench/harness/harbor_workflow.py), and [Harbor ingestion models](../src/aec_bench/harness/harbor_contract.py) | Internal, cross-process, and external |
| Artifact-task attempt composition | Harness | One resolved task and one planned trial produce tracked attempts, one selection, one official verification, and one durable trial record | Supported Python composition API; optional built-in recipe specifications are internal configuration | [`artifact_tasks.py`](../src/aec_bench/harness/artifact_tasks.py), `ResolvedTaskInstance`, and `PlannedTrial` | Internal execution with persisted trial evidence |
| Output completion and explicit commit | Adapter infrastructure and task contract | A fixed candidate artifact becomes structurally complete and, when required, bound by exact bytes | Versioned when persisted in trial evidence; adapter integration is internal | [`OutputCompletionContract` and `OutputCommitAttestation`](../src/aec_bench/contracts/output_completion.py) plus the shared [commit authority](../src/aec_bench/adapters/output_commit.py) | Request configuration, adapter result, and persisted attestation |
| Prime package and evaluation integration | Prime integration | Current public task or lifecycle material becomes an independently installed package; hosted samples return as untrusted provider evidence | Public command and external package behavior; samples normalize into current records | [`exporter.py`](../src/aec_bench/prime_lab/exporter.py), [`lifecycle_exporter.py`](../src/aec_bench/prime_lab/lifecycle_exporter.py), and [`eval_import.py`](../src/aec_bench/prime_lab/eval_import.py) | External package and provider ingestion |
| Artifact and evidence reference | Harness, ledger, and the producing domain | Filesystem or provider output becomes content-bound evidence | Protected when stored in a trial, dataset, freeze, or published record | `ArtifactRef` in [`artifacts.py`](../src/aec_bench/contracts/artifacts.py), `ArtifactReference` in [`trial_record.py`](../src/aec_bench/contracts/trial_record.py), and narrower owner-specific references | Persisted reference |
| Visibility classification | Task ownership and evaluation policy | Material enters public, calibration, or holdout handling | Protected | `Visibility` in [`task_definition.py`](../src/aec_bench/contracts/task_definition.py) and visibility checks in persisted records | Persisted and policy-bearing |
| Interactive-world execution | Interactive-world runtime and registered task worlds | A `WorldTask`, exact build, and profile become one complete evaluated world trial | Supported Python discovery, task, planning, and trial API; task-owned persisted records remain protected | [`worlds`](../src/aec_bench/worlds/__init__.py), [`tasks.py`](../src/aec_bench/worlds/tasks.py), [`world_trials.py`](../src/aec_bench/harness/world_trials.py), and the [runtime protocol](protocols/interactive-world-runtime.md) | Python API, persisted task package, and trial evidence |
| Installed world actor and host calls | Interactive-world runtime and concrete integration owners | An actor or host request crosses a process boundary and reaches the permitted task-owned authority | Versioned local actor protocol; pump-owned persisted run records | [`world_interface.py`](../src/aec_bench/contracts/world_interface.py), the shared [`world_actor`](../src/aec_bench/harness/world_actor/) authority, protocol, endpoint, and staged client, plus the [runtime protocol](protocols/interactive-world-runtime.md) | Internal, persisted, and installed JSON |

## Task specification

`TaskDefinition` is the validated runnable description of an artifact or
workspace task. It owns task identity, lifecycle, visibility, instruction,
environment, verifier, limits, tools, and task metadata. Task-family payloads
remain task-owned; the global contract does not attempt to model every output.

Executable interactive worlds use their registered world definition and
profile instead of pretending to be a static `TaskDefinition`. Both families
can still enter the same experiment, trial, evaluation, and reporting layers.

`WorldTask` is the provider-neutral runnable value. It binds one objective to
exact `WorldBuildRef` and `InteractiveWorldProfileRef` values and carries the
normal selection fields. Its revision covers normalized task ID, instruction,
world and profile references, and selection metadata. `WorldInfo` and
`WorldProfileInfo` are read-only discovery projections. They do not expose a
profile loader or provider object.

A file-backed world task contains `instruction.md` and `world.toml`. The task
directory path relative to `tasks/` supplies `task_id`. `world.toml` declares
the exact registered world, profile, and selection metadata. Loading rejects a
stale build, stale profile, or metadata that differs from registration.

## Task genome reviews

`TaskGenomeReview` is derived review evidence, not a task definition or a task
identity. It binds one `TaskGenomeManifest` and a map of relative `SourceSpan`
values to one exact `TaskSnapshotRef`. A span can identify stable line numbers,
a named section, and a short extracted signal. It does not contain source bytes
or a separate digest.

The selected snapshot resolves all source spans. A review is stale when that
snapshot changes. Changes to confidence, reviewer, notes, span presentation,
or the genome decomposition do not change the task or dataset identity.

An independently retained review is stored as one canonical model artifact
and receives one `ArtifactRef`. Durable review history records its reviewer,
event time, and review artifact reference separately. It does not modify the
runnable task package.

## Public library catalogue

`LibraryCatalogue` schema 2 is the deterministic public projection of current
templates and seeds. The canonical document contains only `schema_version`,
`templates`, and `seeds`. Entries use stable identity ordering; set-like
metadata is sorted; JSON keys are sorted; and each compact or pretty export is
UTF-8 with one final newline.

Catalogue bytes do not contain build time, package version, Git revision, local
paths, or derived counts. A client derives counts from the two entry arrays.
Release and deployment systems own software identity separately.

The repository writer emits only schema 2. During the transition, the external
public site must accept existing schema 1 documents and new schema 2 documents.
Schema 1 reader support can be removed after the public site is deployed with a
schema 2 catalogue and no served catalogue still uses schema 1. This repository
does not retain a second writer or internal schema-specific model for that
external read transition.

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
- `TaskSnapshotRef` identifies runnable task material with either a full Git
  commit and repository-relative task path or one detached task-package
  `ArtifactRef`;
- a dataset execution reference binds the selected tasks to a full Git commit
  and manifest path, or to one verified detached-bundle `ArtifactRef`; and
- world builds identify exact executable source artifacts, profiles identify
  exact task-owned data, and task-owned run records bind replay state.

Do not infer a revision from a mutable directory name.

Task review data is separate from `TaskSnapshotRef`. An internal run plan can
embed one `ReviewSnapshot` or reference one retained review artifact. A
declared stage graph uses the stable review profile ID. It does not copy a
review-sidecar digest into the task reference.

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
The internal application values are `LifecycleTrial` and
`LifecycleExecution`. They are ordinary in-memory values, not persisted
schemas. `run_lifecycle_trial()` converts one execution and its verifier result
to the normal protected `TrialRecord`; persistence is an explicit optional
effect. `run_lifecycle_experiment()` returns the records that it creates, so a
caller does not read the ledger to recover its immediate results.

`EvidenceCheckpointSpec.depends_on` is only an earlier-checkpoint acceptance
precondition inside the declared list order. It does not provide graph
scheduling, branching, or parallel execution. Conditional evidence is an
experimental staged-evidence capability with no registered task consumer.
The current restriction against mixing conditional evidence and operations is
host implementation policy for this subtype, not finite-lifecycle meaning.

## Run plans and published run packages

`RunPlan` is the plain internal execution value. It contains one `RunManifest`,
the ordered exact task references, the compiled Harness, the compiled execution
program, and optional separated review data. It validates task, Harness,
program, provider-route, budget, verifier, and review relationships. It has no
bundle ID, package digest, self-digest, provider-specific task identity, or
copied task-package hash.

`PublishedRunPackage` schema 1 contains one `RunPlan` and the `ArtifactRef` for
each retained `TrialRecord`. Publication builds one deterministic `tar.zst`
archive that also contains every directly or transitively referenced artifact.
The archive is published once and receives one outer `ArtifactRef`. Import
checks the canonical manifest, member paths, duplicate and unreferenced bytes,
artifact IDs, sizes, SHA-256 digests, trial IDs, and run relationships before it
writes to an empty ledger.

`aec-bench run export <run-id> --output <path>` copies the one published archive.
`aec-bench run import <path>` verifies and imports it. These commands do not
reconstruct a package from mutable run directories.

The provider route belongs to `RunManifest`. It does not change task identity.

## Trial and episode records

The current `RunManifest` records shared run identity once: source, dataset,
agent configuration, execution environment, provider route, evaluation
regime, and expected evidence authorities. Each `TrialRecord`
references that manifest by `run_id`. It records execution, evaluation, and
evidence status separately. It does not persist a generic completeness flag.
Publication eligibility is derived from these statuses, required evidence,
task kind, dataset identity, source reconstruction, and the selected policy.

`TrialOutput` distinguishes ordinary termination from host truncation and
records the current completion, stop, or failure reason when one exists.
`CostRecord` is the aggregate usage and cost authority. Optional forensic
material uses `TrialExtensionRef`; its absence does not change a structurally
valid execution from `completed` to partial.

An artifact-task recipe receives only the tracked `AttemptRunner`. It cannot
receive the task package, runtime, official verifier, or verifier result. Each
fresh attempt has a separate workspace. A child copies its parent workspace
and does not change the parent. `attempt_id` and `parent_attempt_id` identify
this trial-local attempt structure; evolution `candidate_id` does not.

Best-of-K remains inside one `PlannedTrial`. Repetitions remain separate
trials. Candidate and selector evidence uses one `TrialExtensionRef`, and
`CostRecord` aggregates every candidate and selector call. If no candidate can
be selected, the trial has failed execution and evaluation status and no
`EvaluationResult`. Evaluation summaries report evaluated and unevaluated
record counts separately.

Lifecycle episode requests/results and world-session records are operational
protocol records. They do not replace `TrialRecord`. Finalization validates and
references their durable artifacts from the canonical trial evidence. Actor
invocation evidence is one `AuthorityEvidenceRef` published only after
quiescent close. World or lifecycle causal evidence uses a separate authority
reference. The shared trial record does not copy requests, correlation maps,
snapshots, transitions, temporal facts, or replay models. DeepSeek evidence is
one provider-manifest `ArtifactRef`; provider-specific claims stay in that
manifest. Lifecycle request and run-state readers accept only the current
shapes and do not migrate prior local run directories.

A finite lifecycle uses `lifecycle_id` and checkpoint identity. It does not use
`world_id`. A harness-program study groups exact task snapshots with
`task_set_id` and `task_set_sha256`; these fields do not identify an interactive
world.

Trial records are append-only evidence once accepted. Internal builders and
temporary run directories remain replaceable implementation.

A world action and a provider session are not trials. The dam, pump, and pump
Harbor trial functions each return one `TrialRecord` with `task_kind="world"`.
The record keeps provider, actor-authority, world, usage, timing, output, and
evaluation facts separate. A returned record cannot reference a session
artifact that cleanup removed.

The reader requires `schema_version = 2`. It rejects missing or unsupported
versions. It does not guess the shape of historical records.

The current trajectory is entry-only JSONL. The writer does not emit a format
header, and the reader does not select or decode historical versions. Ordinary
adapter runs use it as the ordered interaction authority. Exact provider or
sealed transcripts remain separate only when their producing boundary needs
them.

## Evaluation regimes

`EvaluationRegimeEnvelope` schema 1 contains one `EvaluationRegime`. The
published envelope receives one `ArtifactRef`. Its artifact digest is the only
compatibility identity. Repository-specific artifact IDs can differ; equal
verified bytes remain compatible.

The regime embeds its budget and outcome-affecting policies as plain values.
These nested policies do not carry schema versions or self-digests. A critic
has one stable critic ID, embedded configuration, and either an exact Git
revision plus repository entry point or one external `ArtifactRef`. It does not
have separate version, generation, implementation-hash, or policy-hash
identities. A semantic change to a critic, budget, or policy changes the
canonical envelope bytes. Local paths, publication labels, comments, and event
times are not regime content.

Hidden acceptance cases and scoring policy stay outside the public regime.
The regime contains only their salted named commitment. Current authoring can
generate a 256-bit random salt, which stays in the authority-owned escrow with
the exact hidden manifest. Retirement-time reveal must verify that commitment.
Candidate, split, and task-verifier assignments use a separate
`EvaluationAssignment`; they do not change public policy.

Worlds continue to own state transitions and domain evaluation evidence. An
evaluation regime can define eligibility, scoring, aggregation, and acceptance
for that evidence. It does not copy World state or transition authority.

The legacy migration reader resolves and verifies every component before it
publishes a regime. A missing or mismatched component leaves the source plan
read-only. `aec-bench evaluation regime show` and `diff` resolve published
artifacts and report semantic policy paths.

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

`DatasetManifest` schema 2 contains a stable `dataset_id`, a description, task
IDs with portable repository-relative paths and task kinds, and optional
generation replay inputs. It contains no human version, creation time,
self-hash, per-task hash, provider route, or transport identity.

A resolved dataset has exactly one authoritative identity:

- `RepositoryDatasetRef` uses a full Git commit and manifest path. Publication
  and execution reject dirty, untracked, ignored, or missing relevant paths.
- `BundleDatasetRef` uses one `ArtifactRef` for a deterministic archive. The
  digest is outside the bytes it authenticates. Readers reject traversal,
  links, duplicate paths, missing tasks, and undeclared task content.

`DatasetPublication` assigns a human label and real event time to an immutable
reference. Labels support discovery only. Interactive `dataset_id` or
`dataset_id@label` input resolves before execution; persisted experiment and
trial data use only the exact reference or its documented transitional key.
`latest` is not a persisted selector. Dataset manifests, references, bundles,
and publication events cannot be overwritten.

`DatasetTaskEntry.task_kind` selects the concrete artifact, lifecycle, or world
task loader. A world entry points to its `world.toml` task package. Dataset
construction writes task kind from the concrete task family; arbitrary task
metadata cannot change it.

The named schema-1 migration reader reports `fully_verified`,
`partially_verified`, or `invalid`. Only a fully verified manifest, including
its historical top-level and declared task hashes, can become a schema-2
publication.

## Generated-task replay

`GenerationManifest` schema 1 is an optional sidecar at the generated output
root. It records one shared template source, one relative configuration
reference, and the seed, instance index, difficulty, tool mode, and task
visibility needed for each generated task. Clean built-in templates in a Git
checkout use one full Git revision. A set that includes external, modified, or
installed-package templates uses one immutable `ArtifactRef` for a deterministic
source archive.

Runnable task directories do not contain the sidecar fields. The task loader,
validator, execution paths, evaluation paths, and catalogue do not read the
sidecar. `aec-bench generate replay` resolves the retained source, writes to a
separate directory, and compares all runtime task files. Artifact reads verify
size and SHA-256 before extraction. Archive extraction rejects traversal,
links, duplicate paths, and unsupported member types. Replay does not overwrite
an existing output directory unless the user supplies `--overwrite`.

## Evolution workspace candidate lineage

An evolution workspace separates source, candidate identity, lineage, and
display labels:

- `WorkspaceCandidateVersion.candidate_id` identifies one domain candidate.
- `source_revision` is the full Git commit that identifies its exact source.
- `parent_candidate_id` records explicit evolutionary lineage. It does not come
  from the Git parent, label order, a timestamp, or a naming convention.
- `label` is an optional immutable Git tag for people. Creating the same label
  at the same commit is idempotent. A label at another commit is an error.

Candidate metadata is stored in the `aec-bench-evolution` Git notes reference.
The metadata does not store a generated historical time. Reports call Git for
the commit time when they need to display it.

`WorkspaceManifest.schema_version` is the only workspace compatibility
version. Current writers emit integer schema `1`. The reader explicitly maps
the old release-style manifest value `0.1.0` to schema `1` and rejects other
legacy values.

A legacy tag is not enough to prove a candidate. `WorkspaceMigrationPlan`
must give each candidate ID, label, confirmed full source revision, and parent
candidate ID. `aec-bench evolve migrate-workspace` reports a missing label, a
moved label, an unknown parent, duplicate source assignment, or a missing
confirmed revision. It also replaces legacy label fields in `archive.json` and
`graveyard.json`. It registers no candidate and writes no sidecar when the plan
is ambiguous.

## Evolution candidate and evidence contracts

`WorkspaceSnapshot.candidate_id` identifies one exact candidate material. It is
distinct from `trial_id` and from an attempt ID. `CandidateChecks` plans one
candidate-independent `CandidateEvaluationBatch`, runs it, enriches its
observations when configured, and returns one `EvaluatedCandidate`.
`CandidateAssessment` is an evolution-owned projection. `TrialRecord` remains
the evidence authority.

Parent and child are separate `EvaluatedCandidate` values. They MUST use the
same ordered `evaluation_case_ids` for comparison, and a parent record MUST NOT
be used as child evidence or vice versa. `TrialRecord` remains the evidence
authority for execution and evaluation facts; `CandidateAssessment` does not
replace it.

Proposal work changes scratch material only. A submitted `CandidateProposal` carries
the exact child snapshot and mutation summary, or an explicit abstention carries
no child. The application applies a canonical workspace commit only after the
trusted search policy accepts the evaluated child. QD archive entries and
graveyard entries MUST resolve to the exact candidate snapshot they name.
Archive insertion distinguishes a new cell, an improved cell, and rejection.
The archive agent and strategy bandit are search-policy inputs and feedback;
they do not own candidate scores or evaluation validity.

### Bounded agentic variation

One AVO proposal call creates one fresh `RevisionEvaluation`
and one call-local `AVOState`. The boundary plans one fixed,
candidate-independent `CandidateEvaluationBatch`; the batch MUST contain only
`Visibility.PUBLIC` tasks and it MUST be planned once. The selected parent is
checked first at revision `0`. Later scratch revisions use the
same ordered evaluation cases. A `RevisionAttempt` binds the exact
revision, `WorkspaceSnapshot`, mutation, hypothesis, and revision evidence.
The submitted result MUST be the current evaluated revision. A non-submitted
`CandidateProposal` MUST contain no child, mutation, or attempt.

`ProposalUsage` is the one usage value for one proposal call. Model requests,
tools, revision evaluations, and advisor interventions are separate
counters. A reported free call uses cost `0.0`; `None` means that the provider
or evaluator did not report a price. When a configured token or cost limit
needs an unknown value, the AVO budget returns an `*_unknown` exhaustion reason
and does not continue. `EvolutionCycleRecord.evolver_usage` retains the full
usage value. A total cost projection remains unknown when any used cost plane
is unknown.

`AVOAdviceRequest` is a read-only projection of the current AVO call. It
contains only the selected goal, parent ID, strategy, bounded structured
attempt summaries, projected remaining AVO budget, and a deterministic trigger
reason. The advisor has no tools and cannot evaluate, edit scratch, or
change outer selection, parent, strategy, goal, budget, `EvolutionState`,
`QDState`, archive, graveyard, lineage, or manager decisions. Its validated
advice or confirmed failure is retained in `AVOState` and its checkpoint so it
can affect a later main-agent context in the same call. Advice is not a field
of `CandidateProposal`.

AVO memory contains at most the bounded `AVOMemoryEntry` facts selected by the
deterministic retention policy. Entries identify their source variation and
attempt. The application may pass `CandidateProposal.memory` to a later
`CandidateProposalRequest`; memory does not become search policy or shared
swarm state.

Checkpoint schema `2` is the sole validated resume authority for one durable
AVO call. Its identity covers the run and AVO call IDs, parent material,
selection, revision-case order, budget, model and advisor identities,
check/tool configuration, request context, and current scratch material.
Resume MUST reject a mismatch before a new external effect. A checkpoint with
an incomplete model, revision-check, compaction, or advisor effect MUST be
reconciled before retry. Terminal checkpoints restore the recorded
`CandidateProposal` without another model or evaluator call. The protected wire
schema keeps its existing `variation_id`, `development_case_ids`,
`development_evaluation`, `supervisor_model_identity`, and `supervisor_request`
names.

The maintained [provider-free AVO qualification protocol](../src/aec_bench/experimentation/qualification/avo_protocol.py)
pins the historic EF-03 baseline source, exact task splits, model route,
outer budgets, AVO inner budgets, seeds, and separate process and outcome
measures. Validation proves the comparison design only. It is not execution
evidence or a performance claim. A paid or hosted qualification run needs
explicit approval for the route and its cost.

`SwarmAssignment` contains exact parent and inspiration snapshots. A swarm
agent returns `SwarmAgentResult` with a proposal and exact agent usage only. The
usage includes agent model cost, revision-evaluation cost, and the parent
analysis evaluation owned by that agent step. Selection checks compare both
parent and submitted child and bind the resulting `TrialRecord`
values before archive, graveyard, budget, or reducer effects. `SwarmState` is
immutable decision state. The manager owns concurrency and effect application;
the event log is a report of those effects, not an alternative state authority.
These internal selector and swarm values are not new public compatibility
promises.

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

Prime lifecycle export schema 3 retains each public lifecycle as one tar
`ArtifactRef`. It records the generated package version, independent Prime
protocol versions, and one `ProviderAdapterIdentity`. Clean source uses one
full Git revision. Dirty or non-Git source uses one retained source snapshot.
The package does not persist an absolute repository root, source inventory,
lifecycle-spec digest, or a second raw package digest. The reader keeps schema
2 support for existing local packages.

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

Each new DeepSeek trial writes one `aec-bench/deepseek-evidence/3` manifest.
The manifest keeps the adapter package and reconstructive source identity,
model, separate SDK and runtime distribution identities, reported runtime
version, limits, execution status, composition modes, optional plugins,
qualification reference, and redaction actions readable. Each retained file
has one `ArtifactRef` in the authenticated artifact table. Claim references
must equal one complete table reference. One package-lock reference covers the
installed plugin set.

`RuntimeExecutionAttestation` schema v2 names the `provider_evidence` trial
role. `TrialRecord` stores the exact manifest `ArtifactRef` once under that
role. The trial builder and Harbor importer verify the adapter-supplied
reference against the manifest bytes before attachment. The independent
DeepSeek evidence-v2 reader remains available; evidence v1 is not interpreted
as v2 or v3.

The manifest has three composition attestation levels:

- `declared` identifies the exact AEC composition, Cordis input, and system
  prompt that AEC supplied before launch;
- `resolved_runtime` identifies the composition that the active DeepSeek
  runtime resolved;
- `model_visible` identifies the complete prompt, history, tool, parameter,
  and dynamic context surface for model requests.

Each level is `complete`, `partial`, or `unavailable`. A `complete` level must
reference retained artifacts. An `unavailable` level must give a reason and
must not reference inferred artifacts. Unknown future fields survive manifest
read and write. The importer does not accept the superseded internal v1
manifest as v2.

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

The package owns one versioned provider and feature matrix at
`src/aec_bench/adapters/deepseek_harness/profiles/qualification-matrix.json`.
Matrix schema 2 records one cell for each provider route and feature. Each cell
contains the exact adapter package and source, SDK distribution and report,
runtime distribution and report, evidence level, status, content-addressed
evidence, event time, or reason. Keyless protocol proof and credentialed
live-provider proof are different cells. A provider route is `qualified` only
when every required cell is qualified for the exact version set. A trial with
a different source or version is `unqualified`, even when its protocol tests
passed. The reader keeps qualification schema 1 support.

The initial matrix records both the Azure and official DeepSeek routes as
`partial`. It does not claim retained live-provider evidence. Release owners
must add content-addressed live evidence before they change either route to
`qualified`.

The pinned SDK path does not expose a canonical resolved composition or the
complete model-visible request surface. The manifest records both levels as
`unavailable` with a reason. The exact Cordis input, system prompt, AEC native
tool manifest, plugin build, and plugin package lock remain declared evidence.
They do not become resolved-runtime or model-visible evidence.

The supported dependency profiles are:

| Profile | Installation | Required check |
| --- | --- | --- |
| `core` | `uv sync --frozen` | Public CLI, optional-boundary, and core lint gates |
| `all-adapters` | `uv sync --frozen --extra execution --extra deepseek-harness --extra morph --extra local-agents --extra prime --extra prime-agent` | Adapter suites collect and run without undeclared imports |
| `all-extras` | `uv sync --frozen --all-extras` | `uv run pytest --collect-only -q tests/` has no collection errors |
| `release-qualification` | `all-extras` plus the locked DeepSeek Node toolchain | Focused DeepSeek, actor-conformance, pump-world, plugin test, and reproducible plugin-build gates pass |

The release CI job implements the last two rows. It does not use provider
credentials and cannot satisfy a live-provider matrix cell.

For native-tool runs, the manifest records the exact tool names and copied
plugin artifact. Generic tools supply an explicit `NativeToolDefinition`.
Native world tools are compiled from the frozen
`WorldActorCapabilityCatalogue`: each action keeps its exact name,
description, and input schema, and `world_observe` is the one reserved
observation tool. The compiler accepts object properties, required fields,
boolean `additionalProperties`, scalar and array types, item schemas, enums,
bounds, descriptions, and one nullable `anyOf` union. Other schema keywords
fail before model execution; the compiler does not widen them.

The native world action schema cannot contain `request_id` or `decision_id`.
The endpoint validates task arguments and gives the handler a hidden
`NativeToolInvocation` with the DeepSeek session, tool-call, turn, generation,
cancellation, and trusted request identity. That trusted request identity is
the logical world request ID.

`NativeToolRequestSemantics` identifies the component that owns logical
request admission. The gateway owns replay for generic non-world tools. A
world definition uses `handler-authority`: the gateway validates and forwards
each exact retry, while `ActorInvocationAuthority` owns the actor principal,
frozen catalogue identity, request fingerprint and table, action budget, total
dispatch order, terminal latch, and semantic evidence. A transport correlation
does not change logical world-action identity.

One DeepSeek transport instance owns one private decision cursor. A successful
`world_observe` sets it without using the action budget. An action atomically
consumes it and can replace it only with a `next_observation` returned to the
model. A stale decision clears it. An unknown action outcome freezes new calls
until exact reconciliation. A terminal or truncated result closes the cursor
and returns the generic `conclude-turn` disposition. This cursor coordinates
model-visible information; it is not world state.

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

A single-session world trial references the sealed actor stream with
`aec-bench/actor-invocation-evidence/1`. A multi-session pump trial references
an ordered manifest of sealed session streams with
`aec-bench/actor-invocation-manifest/1`. The manifest does not replace the
task-owned world event stream.

A DeepSeek native world trial also retains
`native-world-tool-surface.json`. This record contains the complete canonical
catalogue, the action-to-public-tool mapping, the exact model-facing tool
manifest, the catalogue SHA-256, and the public tool-surface SHA-256. Each
segment manifest also binds a `segment-snapshot` of
`actor-invocation-evidence.jsonl` and `actor-correlation.jsonl`. The
correlation artifact maps DeepSeek session and tool-call identities to the
matching actor evidence sequences. The complete session-owned actor stream is
final only after the shared authority closes. The treatment record identifies
the presentation mode as `deepseek-native`.
Deterministic conformance tests run the same stale, accepted, duplicate,
conflict, and terminal script through `WorldActorEndpoint` and the compiled
DeepSeek tools. They compare shared authority and world semantics, not
provider-specific process events.

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

`ArtifactRef` binds a repository artifact ID, media type, byte size, and
SHA-256 for independently retained bytes. `ArtifactRepository` derives the
storage locator from the digest and verifies the locator, size, and digest on
every read. Its canonical model encoding uses JSON field aliases, sorted object
keys, stable set order, preserved list order, UTF-8, compact separators, and
one final newline. It rejects non-finite numbers.

Kernel, Harness, execution-program, evaluation, stage, task-snapshot, and
run-plan models do not carry a generic self-digest. They use stable domain
references, direct embedded-value validation, named commitments, or one
`ArtifactRef` when bytes are retained independently. A schema that still emits
self-addressed JSON must use the explicit legacy base until its owner migrates
the format. The legacy reader validates the old digest and returns a plain
migrated model without that field.

`TrialRecord` uses `ArtifactRef` for retained input, output, provider,
authority, and extension bytes. The ledger verifies every reference before it
returns a resolved record. Some current lifecycle and study-specific extension
contracts still use `ArtifactReference` until their owners adopt `ArtifactRef`.

`AuthorityEvidenceRef` adds the authority kind and evidence protocol to one
`ArtifactRef`. A quiescent `ActorInvocationAuthority` close returns one such
reference for its final semantic evidence stream. An unsettled close does not
publish a final reference. The existing DeepSeek evidence-v2 path remains
supported during this conversion.

A reference is valid only when the owning protocol verifies the referenced
bytes and their relationship to the parent record. A path string alone is not
artifact integrity. Do not collapse task evidence, provider output, world
snapshots, and dataset entries into one global evidence model merely because
they all contain hashes.

Detailed lifecycle rules live in
[Staged evidence and publication](protocols/staged-evidence-and-publication.md).

## Public presentation and inspection vocabulary

Current Web API responses use one vocabulary for identity, integrity,
compatibility, qualification, labels, and event time:

- stable domain IDs, such as `dataset_id`, `trial_id`, and `candidate_id`,
  identify domain objects and URL targets;
- `label` and `release_label` are human display and discovery values, not
  authoritative identity;
- `source_revision` is the full Git commit for repository source;
- `ArtifactRef.sha256` identifies exact retained bytes and appears through an
  explicit integrity inspection, not routine navigation;
- `schema_version`, `protocol_version`, and `package_version` select an
  independently evolving reader, protocol, or installed package;
- `qualification_status`, `evidence_level`, and `qualified_at` describe one
  exact provider and runtime qualification claim; and
- named event times, such as `reviewed_at`, `occurred_at`, `authored_at`, and
  `verified_at`, state which event the time records.

Routine dataset and trial views do not return full artifact digests. A trial
evidence view returns authority kind, protocol, artifact ID, media type, byte
size, and separate integrity and content links. The integrity route reads the
stored bytes, verifies the `ArtifactRef`, and then returns the full SHA-256,
size, and verification time. Provider qualification uses the same split:
routine cells show the exact adapter, SDK, and runtime version set, evidence
level, qualification status, event time or reason, and evidence references;
full evidence digests stay behind explicit integrity inspection.

The technical evidence, content, integrity, and provider-qualification routes
require internal access. Current API schemas use the v2 vocabulary. Evolution
inspection paths require an exact `candidate_id`; human labels are for display
and discovery only. There is no current response field named generic `version`,
`timestamp`, `content_hash`, or `content_sha256` in these Web contracts.

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
