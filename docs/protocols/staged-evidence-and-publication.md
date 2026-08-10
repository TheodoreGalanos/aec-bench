# ABOUTME: Defines the current host-controlled checkpoint, conditional-evidence, publication, recovery, and calibration protocol.
# ABOUTME: Keeps lifecycle storage and retry mechanics out of global invariants and the boundary-contract index.

# Staged Evidence and Publication

| Field | Value |
| --- | --- |
| Class | Protocol |
| Status | Current |

This protocol applies to public evidence-lifecycle tasks. The host controls
checkpoint release, conditional evidence, submissions, attempts, durable
records, verification, and calibration. The agent controls only its permitted
actions and submitted content.

## Authorities

| Authority | Owns |
| --- | --- |
| Public task package | Ordered checkpoints, release material, public request catalogue, submission shape, and task verifier |
| Lifecycle host | Active checkpoint, budgets, attempt/session identity, workspace projection, archival, recovery, verification, and finalization |
| Episode environment | Model execution and its declared output only |
| Task verifier | Semantic correctness and reward after host validation |
| Ledger and artifact stores | Durable bytes, content identities, and canonical trial evidence |

The model cannot advance a checkpoint, alter prior submissions, choose hidden
evidence paths, invoke the verifier, or write reward.

## Checkpoint contract

`EvidenceCheckpointSpec` declares the public checkpoint order, instruction and
release material, submission destination, required top-level fields, and
optional conditional evidence.

By default, submissions can contain additional task fields. When
`allow_additional_submission_fields` is false, the declared required field set
is exact. Both the model-facing write tool and host archival gate reject missing
or undeclared top-level fields. Neither silently strips or repairs output.

A submitted checkpoint is immutable within its run. Revising accepted content
requires a derived branch with explicit lineage.

## Conditional evidence

`ConditionalEvidenceSpec` publishes a finite request budget and a closed
catalogue of safe request IDs, descriptions, and same-checkpoint prerequisites.
The graph must be acyclic, and every request must be reachable within the
declared budget. Public catalogue entries contain no hidden source path or
expected outcome.

Hidden resolution maps an exact `(checkpoint_id, request_id)` to task-owned
source material. A successful first request consumes one budget unit. Repeated
successful requests and typed rejections consume none. Acquired evidence and
consumed budget persist across retry and branch inheritance; a derived run
cannot unsee evidence visible at its branch point.

Every admitted action receives one globally ordered ID. The host publishes its
canonical transaction under `evidence_requests/<action-id>/` before treating
the workspace projection under
`workspace/inbox/<checkpoint-id>/requests/<request-id>/` as visible. The action
record binds session and attempt, pre/post state identity, outcome or rejection,
budget arithmetic, and every released artifact hash.

Malformed model arguments are bounded tool-call failures and do not create a
lifecycle action. Unknown request IDs, unmet prerequisites, and exhausted
budgets create typed rejections. Missing or changed hidden source material is a
host failure, not a scored model rejection.

## Episode modes

The host supports two distinct modes:

- A fresh-context episode owns exactly one checkpoint. Each retry receives a
  distinct attempt and session directory.
- A persistent-context execution owns one ordered multi-checkpoint session.
  It is not represented as repeated fresh episodes.

`LifecycleEpisodeRequest` binds the package and lifecycle identities, host
allocated episode/attempt/session identity, checkpoint ownership, execution
mode, visibility, requested adapter/model, turn limit, instruction, confined
paths, public request catalogue, and prior acquired-evidence hashes.

`LifecycleEpisodeResult` returns execution-owned facts: the exact request
identity, requested and resolved agent condition, configuration, status,
failure, usage, and checkpoint ownership. It does not accept verifier gates,
expected answers, pass/fail, or reward from the environment.

The host publishes request identity before execution and validates result bytes
before accepting candidate output. Failed candidate submissions remain with
their owning attempt.

### Prime checkpoint execution

The hydraulic-review Prime composition implements the fresh-context episode port. It
starts one fresh Prime ACP process for each checkpoint and gives it one scoped
Unix-socket endpoint. The endpoint privately owns the lifecycle package, run,
checkpoint, session, operation resolver, socket, and capability.

Prime can use only these actor operations:

- inspect endpoint capabilities and the current public checkpoint state;
- list and read actor-visible lifecycle files;
- execute one declared lifecycle operation; and
- offer one checkpoint submission.

The offer is not a lifecycle submission. After a clean Prime end turn, the
host validates the offered bytes, writes the canonical submission, and uses the
existing lifecycle coordinator to advance. Prime cannot select a package, run,
checkpoint, verifier, branch, evaluation, or host control. Aggregate session,
model-call, token, cost, and wall-time limits apply to the complete lifecycle.
They do not reset at a checkpoint.

Same-user execution is development evidence only. Benchmark-valid execution
requires process and file isolation which prevents Prime from reading the
lifecycle repository or host controls outside the scoped endpoint. The Prime
root process and its descendants form one composite actor principal.

## Publication and recovery

Lifecycle state, attempts, conditional actions, submissions, snapshots, and
trial records use their declared immutable or atomic publication rules.
Publication is complete only after required file and parent-directory flushes.
The active state and canonical indexes are reconciled with immutable evidence
before a retry or finalization.

Recovery can adopt an already published matching transaction exactly once,
repair a missing commit marker or derived index, and finish artifact-only
finalization without another model call. It rejects different bytes under the
same identity, foreign session ownership, changed package identity, malformed
trajectory history, or an inconsistent terminal result.

A torn terminal result can be quarantined only when the durable attempt and
trajectory evidence support a conservative unresolved failure. Recovery does
not truncate or invent history. An interrupted effect whose outcome is unknown
remains incomplete until durable evidence resolves it.

## Verification and trial finalization

The host invokes the task verifier only after submission shape, checkpoint
ownership, session state, and archived bytes validate. Complete lifecycle
`TrialRecord` evidence binds:

- the immutable invocation manifest and plan;
- task/package and implementation identity;
- requested and resolved adapter/model identity;
- runtime provider and realized dependency identity;
- execution mode, visibility, limits, and interaction/tool schema;
- every session and attempt used by a submitted checkpoint;
- conditional-action records and acquired evidence;
- verifier result and snapshotted output artifacts; and
- the canonical ledger path and completeness state.

`CompiledLifecycleEnvelope.executable_artifact_sha256` binds the shared
lifecycle contracts, progression runtime, evidence-storage helpers, lifecycle
evaluation, and the selected task's materialisation, task data, calculations,
operations, and verification. Smoke actors, provider integrations, and
experiment drivers are separate execution evidence and are not part of this
task executable identity.

An adapter mismatch, unresolved provider identity, incomplete checkpoint,
missing artifact, or identity drift makes the trial failed or partial. It is not
evidence for the requested condition.

## Calibration and selection

A selectable public calibration run preregisters its variant set, repetitions,
selection rule, tie-break, execution condition, interaction protocol, and
finite spend envelope before execution.

The calibration freeze is derived only after every planned immutable public
record exists and validates against its snapshotted historical manifest, plan,
and interaction identity. Incorrect but complete outcomes remain evidence.
Missing, partial, mismatched, or drifting candidates are ineligible rather than
silently removed from the comparison.

The freeze recomputes the declared winner, hashes the exact input records and
artifacts, and is write-once: a retry can accept identical bytes but cannot
replace different content.

Calibration and transfer studies report the controls and resource envelope
they actually used. A descriptive sequential study does not support a causal
effect claim merely because candidate scores differ.

## Failure semantics

- Task-invalid submissions receive the verifier result after valid host
  archival.
- Model request mistakes receive typed, non-disclosing rejections where the
  public protocol defines them.
- Package corruption, storage failure, session mismatch, provider failure, and
  verifier execution failure are host failures.
- No failure becomes positive reward or a complete trial.
- A retry reuses durable matching evidence; it does not rerun a confirmed task
  effect.

## Implementation and proof

Authoritative implementations include:

- [`EvidenceCheckpointSpec` and `ConditionalEvidenceSpec`](../../src/aec_bench/contracts/evidence_lifecycle.py)
- [lifecycle coordination and recovery](../../src/aec_bench/lifecycles/runtime/lifecycle.py)
- [episode request/result boundary](../../src/aec_bench/lifecycles/runtime/episode.py)
- [structural facade submittal lifecycle](../../src/aec_bench/lifecycles/structural_review/facade_submittal.py)
- [hydraulic-review Prime endpoint](../../src/aec_bench/harness/hydraulic_review_prime/endpoint.py)
- [hydraulic-review Prime lifecycle composition](../../src/aec_bench/harness/hydraulic_review_prime/lifecycle.py)
- [conditional-evidence publication](../../src/aec_bench/lifecycles/runtime/request_store.py)
- [calibration freeze](../../src/aec_bench/experimentation/lifecycle_studies/calibration.py)
- [lifecycle trial finalization](../../src/aec_bench/experimentation/lifecycle_studies/trial_record.py)

Focused proof includes:

- [registered lifecycle conformance](../../tests/lifecycles/test_lifecycle_conformance.py)
- [structural facade lifecycle behaviour](../../tests/lifecycles/structural_review/test_facade_submittal.py)
- [lifecycle state, publication, request, retry, branch, and recovery tests](../../tests/lifecycles/runtime/test_lifecycle.py)
- [episode boundary and attempt-recovery tests](../../tests/lifecycles/runtime/test_episode.py)
- [hydraulic-review Prime endpoint and lifecycle tests](../../tests/harness/hydraulic_review_prime/)
- [calibration and freeze tests](../../tests/experimentation/lifecycle_studies/test_calibration.py)
- [trial-record completeness and visibility tests](../../tests/contracts/test_trial_record.py)
