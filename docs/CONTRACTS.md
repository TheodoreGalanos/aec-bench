# ABOUTME: Logical data contracts for Python aec-bench domain boundaries.
# ABOUTME: Defines shapes, constraints, and relationships without binding to a storage or transport format.

# Contracts

These contracts define the data shapes exchanged at domain boundaries in the Python implementation. They are logical schemas, not storage choices. Python will likely implement them with Pydantic models, but the rules here are architectural, not library-specific.

Parent document: [ARCHITECTURE.md](ARCHITECTURE.md).
Related: [INVARIANTS.md](INVARIANTS.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

---

## Core Contracts

### TaskDefinition

**Boundary:** Tasks -> Harness

Describes one runnable task instance.

Required fields:

- `task_id`: globally unique identifier.
- `task_type`: task family identifier.
- `domain`: engineering domain.
- `category`: benchmark category.
- `difficulty`: `easy | medium | hard`.
- `lifecycle`: `proposed | active | deprecated | retired`.
- `visibility`: `public | holdout`.
- `instruction`: fully resolved prompt text.
- `environment`: environment specification.
- `verifier`: verifier specification.
- `timeout_seconds`: execution wall-clock limit.

Optional fields:

- `tags`
- `metadata`

Environment fields:

- `dockerfile`
- `compose_file`
- `manifest`
- `build_args`
- `tools`

Verifier fields:

- `script`
- `expected_output_path`
- `reward_path`
- `details_path`

Constraints:

- `task_id` is globally unique.
- `instruction` is self-contained.
- retired tasks are not runnable.
- holdout tasks do not appear in public-facing outputs.
- `lifecycle` and `visibility` remain independent axes.

### AgentOutput

**Boundary:** Adapters -> Evaluation

Minimal output envelope produced by an adapter.

Required fields:

- `status`: `completed | partial | failed | empty`
- `output_path`
- `output_format`

Optional field:

- `error_message`

The payload itself is task-specific. Python contract code should validate the envelope, not pretend every task family shares one payload shape.

Well-known payloads:

- `AuditFinding`
- `CalculationResult`

### TaskGenomeManifest

**Boundary:** Tasks -> Evolution / Research tooling

Sidecar description of one task as decomposed selective pressures. This is
descriptive metadata over an existing task directory; it does not replace
`TaskDefinition`, `task.toml`, verifier scripts, or runtime task loading.

Required fields:

- `task_id`
- `source_task_path`
- `status`: `extracted | needs_review`
- `domain_frame`
- `scenario`
- `input_bundle`
- `reasoning_moves`
- `pressure_points`
- `output_contract`
- `verifier_contract`
- `difficulty_controls`
- `trajectory_affordances`
- `extraction`

Key rule:

- task genome manifests must include provenance and review metadata for inferred
  pressure points so recombination experiments can distinguish deterministic
  extraction from fields that need lightweight reasoning review.

### TaskGenomeEvidencePacket

**Boundary:** Tasks -> Evolution / LLM decomposition

Bounded evidence packet used to ask a lightweight model to produce or refine a
`TaskGenomeManifest`.

Required fields:

- `task_id`
- `source_task_path`
- `deterministic_manifest`
- `task_toml`
- `instruction_sections`
- `verifier_files`
- `artifact_paths`

Key rule:

- LLM-driven decomposition should consume this bounded packet rather than
  roaming the filesystem, so every semantic claim in the generated manifest can
  trace back to task evidence.

### TrialRecord

**Boundary:** Harness -> Ledger

Immutable, append-only record of one trial.

Required fields:

- `trial_id`
- `experiment_id`
- `timestamp`
- `task`
- `agent`
- `environment`
- `inputs`
- `outputs`
- `evaluation`
- `timing`
- `completeness`: `complete | partial`

Optional field:

- `cost`
- `adaptation`
- `lifecycle_execution`
- `lifecycle_provenance`

Lifecycle records use typed session and provenance contracts. `lifecycle_execution` preserves mode, visibility policy, the per-session turn limit, requested and actual adapter identity, resolved model identity, usage, failures, checkpoint coverage, and hashed per-session artifacts. An actual adapter that differs from the requested condition is an unscored failed execution, never evidence for the requested adapter. Interrupted sessions whose provider-resolved model was never durably observed use the explicit `unresolved` value and force `completeness=partial`; the requested alias is never substituted as resolved provenance. `lifecycle_provenance` binds lifecycle/world identity, package/spec hashes, repository or installed-source content identity, runtime provider and realized dependency-byte identity, the registered task scorer and dispatcher chain, the canonical invocation manifest and sealed index entry, and the snapshotted ablation manifest and expanded plan.

Lifecycle calibration manifests and plans carry a strict `study_design`: `descriptive_calibration`, per-session turn budgets, deterministic sequential plan order, no randomization, no counterbalancing, and `causal_effects_supported=false`. Evaluation artifacts must repeat this contract and expose the resource envelope beside outcomes. They must not promote group differences to causal effects while those controls remain absent.

Key rule:

- a `complete` record must contain enough provenance to support reproducibility claims.
- a complete lifecycle record must reference hashed immutable output artifacts; paths back into a mutable working run are not sufficient.
- lifecycle finalization must reconcile every session, token total, task revision, verification result, and artifact hash against the canonical invocation and its immutable snapshot before publication.
- the planned runtime provider, sorted dependency distributions, and realized dependency-byte fingerprint must exactly match the canonical invocation before publication.
- every submitted lifecycle checkpoint must resolve to exactly one final submitted attempt and a durable session owner.
- every fresh-context session must own exactly one checkpoint; retries use distinct attempt-specific sessions.
- attempt mode, session mode, visibility policy, actual adapter, and per-session turn limit must reconcile with the planned condition before reward attribution.
- the per-invocation index seal is authoritative for crash recovery; the shared discovery index may be reconstructed from valid seals without changing invocation identity.
- immutable snapshot recovery has authority over mutable source package/run aliases once the snapshot exists.
- ledger publication is exclusive, fsync-durable through newly created ancestors, and atomic; an artifact snapshot left before record publication is recoverable without another model call.
- session-result publication is atomic and fsync-durable; a torn result from a terminal persistent session is quarantined and replaced by an unresolved zero-reward failure only when its submitted ownership and complete trajectory validate.
- malformed trajectory history is a conflict and is never truncated or inferred during recovery.

### EvaluationResult

**Boundary:** Evaluation -> Communication, Evaluation -> Feedback

Structured scored result for one trial.

Required content categories:

- reward
- validity status
- score breakdown
- error taxonomy or explicit absence
- confidence metadata or explicit absence

Evaluation note:

- Behavioral analysis can contribute structured entries inside the score breakdown when present, for example bond-type classifications, transition matrices, or structural similarity scores derived from persisted trial transcripts.
- Those behavioral artefacts remain evaluation-owned data: they should be derived from `TrialRecord` provenance, not scraped ad hoc from external job directories after the fact.

### TrajectoryEntry

**Boundary:** Agents → Evaluation, Agents → Communication

Structured record of one event within an agent's execution. Events are grouped into logical steps by the `step` field. Persisted as `trajectory.jsonl` (JSONL format, one entry per line, version header as first line).

Required fields:

- `step`: non-decreasing integer grouping related events (0 = initialisation, 1+ = agent turns)
- `role`: `assistant | tool_call | tool_result | system | user`

Conditional fields (by role):

- `content`: reasoning or prompt text (assistant, system, user)
- `tool_name`: tool identifier (tool_call, tool_result)
- `command`: shell-level invocation string (tool_call)
- `arguments`: structured parameters (tool_call)
- `stdout`: captured output (tool_result)
- `stderr`: captured errors (tool_result)
- `exit_code`: process return code (tool_result)
- `duration_ms`: wall-clock execution time (tool_result)
- `media`: paths to produced artifacts, relative to trial artifacts dir (tool_result)
- `timestamp`: ISO 8601 UTC with Z suffix (all roles, best-effort)

Constraints:

- First line of the file is a version header: `{"version": 1, "format": "aec-bench-trajectory"}`
- `step` values are non-decreasing within a trajectory (multiple entries may share a step)
- Within a step, entries appear in write order: assistant, then (tool_call, tool_result) pairs
- `role` determines which conditional fields are populated
- `exit_code` of 0 indicates success
- Entries are append-only (no retroactive modification)
- File is flushed after each write for crash resilience
- Consumers must tolerate incomplete final steps (tool_call without tool_result = crash/timeout)

Relationship to existing contracts:

- `TrialRecord.outputs.trajectory_path` points to the trajectory artifact
- `TranscriptEntry` (adapters/transcript.py) remains for backward compatibility
- Consumers prefer trajectory when available, fall back to conversation.jsonl
- Role values merge the previous TranscriptRole + TranscriptEvent axes into a single discriminator

### ExperimentManifest

**Boundary:** Experiment configuration -> Harness

Validated description of what to run.

Should include:

- task selection
- adapter selection
- model/configuration
- compute target
- experiment metadata

---

## Python Design Implications

- Boundary models should be explicit Pydantic models.
- Internal helpers can use normal Python types, but cross-domain boundaries should not rely on loose dict conventions.
- JSONL helpers belong in the contract layer only if they preserve contract semantics, not as ad hoc serialization utilities scattered through the codebase.

---

## Contract Rules

- Validate at boundaries, not after persistence.
- Distinguish missing data from empty data.
- Preserve append-only semantics for TrialRecord.
- Keep task-family payload specificity in verifiers and task definitions, not in global adapter logic.
