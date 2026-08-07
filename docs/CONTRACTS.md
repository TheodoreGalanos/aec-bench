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
| Experiment manifest | Experiment orchestration | User configuration becomes an executable plan | Internal, except documented CLI/config behavior | [`ExperimentManifest`](../src/aec_bench/contracts/experiment_manifest.py) | Persisted configuration |
| Trial and episode record | Harness and ledger | Execution, verifier, and artifact evidence becomes reportable benchmark evidence | Current persisted record; no retained historical reader | [`TrialRecord`](../src/aec_bench/contracts/trial_record.py) plus the owning episode or world protocol | Persisted and exportable |
| Evaluation result | Evaluation | Verifier output and review evidence become reward, validity, and diagnostics | Protected as part of a persisted trial or published result | [`EvaluationResult`](../src/aec_bench/contracts/evaluation_result.py) | Persisted and externally reported |
| Dataset manifest and identity | Dataset generation and storage | A set of task bytes becomes a named benchmark snapshot | Protected when published; content identity is authoritative | [`DatasetManifest`](../src/aec_bench/contracts/dataset.py) and dataset hashing/storage | Persisted and publishable |
| Adapter and Harbor execution | Adapters and harness | Harness input crosses into local model execution or the supported Harbor workflow and returns untrusted output | Internal adapter values; Harbor result documents are lenient ingestion boundaries | [`AdapterRequest` and `AdapterResult`](../src/aec_bench/adapters/base.py), the [Harbor workflow](../src/aec_bench/harness/harbor_workflow.py), and [Harbor ingestion models](../src/aec_bench/harness/harbor_contract.py) | Internal, cross-process, and external |
| Prime package and evaluation integration | Prime integration | Current public task or lifecycle material becomes an independently installed package; hosted samples return as untrusted provider evidence | Public command and external package behavior; samples normalize into current records | [`exporter.py`](../src/aec_bench/prime_lab/exporter.py), [`lifecycle_exporter.py`](../src/aec_bench/prime_lab/lifecycle_exporter.py), and [`eval_import.py`](../src/aec_bench/prime_lab/eval_import.py) | External package and provider ingestion |
| Artifact and evidence reference | Harness, ledger, and the producing domain | Filesystem or provider output becomes content-bound evidence | Protected when stored in a trial, dataset, freeze, or published record | `ArtifactReference` in [`trial_record.py`](../src/aec_bench/contracts/trial_record.py) and narrower owner-specific references | Persisted reference |
| Visibility classification | Task ownership and evaluation policy | Material enters public, calibration, or holdout handling | Protected | `Visibility` in [`task_definition.py`](../src/aec_bench/contracts/task_definition.py) and visibility checks in persisted records | Persisted and policy-bearing |
| Interactive-world registration and calls | Continual runtime and registered task worlds | An exact executable build/profile is resolved and an actor or host request reaches task-owned behavior | Current unversioned installed calls; task-owned persisted run records | [`continual_world.py`](../src/aec_bench/contracts/continual_world.py), [`world_interface.py`](../src/aec_bench/contracts/world_interface.py), the scoped Prime [`world.py`](../src/aec_bench/prime_agent/world.py) transport, and the [runtime protocol](protocols/interactive-world-runtime.md) | Internal, persisted, and installed JSON |
| Pump functional core | Wastewater pump-station task | Typed pump actions change one canonical current state and observations and scores are derived from it | Ordinary task-owned dataclasses and direct callables | [`coupled_runtime.py`](../src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/coupled_runtime.py), [`stewardship_models.py`](../src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/stewardship_models.py), and task-owned [`evaluation.py`](../src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/evaluation.py) | Internal |

## Task specification

`TaskDefinition` is the validated runnable description of an artifact or
workspace task. It owns task identity, lifecycle, visibility, instruction,
environment, verifier, limits, tools, and task metadata. Task-family payloads
remain task-owned; the global contract does not attempt to model every output.

Executable interactive worlds use their registered world definition and
profile instead of pretending to be a static `TaskDefinition`. Both families
can still enter the same experiment, trial, evaluation, and reporting layers.

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
