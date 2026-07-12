# ABOUTME: Non-negotiable architectural invariants for the Python aec-bench platform.
# ABOUTME: Preserves benchmark validity, reproducibility, and anti-drift rules across the Python implementation.

# Architecture Invariants

These are the non-negotiable rules of the Python implementation. Tooling can change. Frameworks can change. These rules cannot.

Parent document: [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Single Source of Experimental Truth

Every trial must be reproducible from immutable artefacts: task revision, verifier revision, adapter revision, model identifier, prompt inputs, tool config, runtime image, and seed where applicable.

**Any result that cannot be replayed is invalid for reporting.**

Python enforcement direction:
- persist a validated `TrialRecord`,
- reject incomplete records,
- keep the ledger append-only.

---

## 2. Contracts at Boundaries

All domain boundaries are schema-defined and validated. No cross-domain call may rely on informal dict shapes.

Python enforcement direction:
- Pydantic models at boundaries,
- explicit validation before persistence or dispatch,
- deterministic failure messages for malformed payloads.

---

## 3. No Hidden State

All state that affects outcomes must be explicit and persisted in run records. No benchmark-significant behavior may depend on undocumented environment defaults, transient local files, or implicit SDK settings.

Python enforcement direction:
- capture adapter settings, retries, timeouts, and model parameters,
- record environment and container identity,
- keep task/tool configuration explicit.

---

## 4. Task-Adapter Independence

Tasks must not encode assumptions about a particular agent or provider. Adapters must not contain task-specific logic.

**Violations are architecture defects, not shortcuts.**

Python enforcement direction:
- no adapter imports from task-definition code,
- no task-type branching inside providers,
- task-declared tools only.

---

## 5. Evaluation Is a Pipeline, Not a Number

Reward is necessary but insufficient. Every scored run should produce validity checks, metric breakdowns, taxonomy information, and confidence metadata or an explicit marker that confidence is unavailable.

Communication code must not invent metrics that do not exist in evaluation outputs.

Python enforcement direction:
- formal `EvaluationResult`,
- explicit aggregation pipeline,
- report builders that read from evaluation outputs and trial joins only.

---

## 6. Public/Holdout Separation

Public and holdout tasks must remain structurally separate. Holdout-derived feedback can change principles and generators, but not leak exact holdout content into training-visible surfaces.

Python enforcement direction:
- visibility fields in task metadata,
- preserve explicit task visibility in new TrialRecords while accepting missing visibility only for historical parsing;
- treat missing visibility as ineligible for public-calibration or holdout evaluation rather than inferring it from names or storage paths;
- filtering built into query/report surfaces,
- reviewer and export paths respect holdout policy.

---

## 7. Validate Before You Commit

Any new model, adapter, or tool change must be validated on a representative subset before full benchmark execution.

Python enforcement direction:
- smoke manifests,
- documented gate criteria,
- cheap pre-flight validation before expensive runs.

---

## 8. Provider Isolation

Cross-cutting concerns such as compute, storage, credentials, and observability are accessed only via explicit provider interfaces.

Python enforcement direction:
- keep external vendors behind boundary modules,
- avoid direct provider imports in domain logic,
- make backend selection configuration-driven.

---

## 9. Human Judgment Is Structured Data

Expert feedback must be captured as machine-readable, provenanced data. Free text alone is advisory, not authoritative.

Python enforcement direction:
- typed annotation models,
- reviewer identity and calibration metadata,
- adjudication and provenance stored with the annotation record.

---

## 10. Continuous Quality Over Periodic Cleanup

Architectural drift should be corrected continuously through small fixes and automated checks, not deferred to occasional rewrites.

Python enforcement direction:
- linting, typing, and tests in normal workflow,
- domain-specific checks added over time,
- tracked debt with owners, not vague TODO accumulation.

---

## 11. Staged Evidence Is Host-Controlled

For evidence-lifecycle tasks, the host owns file disclosure and checkpoint transitions. Model-visible memory policy must not delete or rewrite audit artifacts, and a prior checkpoint submission is immutable within its run.

Python enforcement direction:
- release only the active checkpoint's declared evidence;
- expose conditional evidence only through public request IDs and a finite host-owned budget sufficient to reach every declared request; never expose hidden resolution paths or expected outcomes;
- bind every boundary-valid evidence request to the active host-owned session and attempt, publish a canonical sequence-addressed and hash-bound transaction before model visibility, and record typed zero-cost rejections without leaking valid alternatives;
- retain acquired conditional evidence and consumed budget across retry and branch inheritance; a derived run cannot unsee evidence visible at its branch point;
- archive and hash submissions before advancing;
- represent revision of an earlier submission as a derived branch;
- persist attempts, interruptions, failures, resumes, revisits, and visibility policy;
- bind every local invocation to an immutable experiment manifest and append-only index entry.
- derive public semantic variants from validated task-specific event contracts rather than arbitrary file patches;
- keep host-side variant identity and lineage hash-bound without leaking it into model-visible evidence;
- refuse non-empty lifecycle materialization targets and validate variant identity against package content before verification or indexing;
- finalize lifecycle sweeps through one append-only core `TrialRecord` per planned invocation;
- snapshot and hash lifecycle inputs and outputs under the ledger before claiming a complete record;
- snapshot and reconcile conditional action records, commit markers, released bytes, public catalogues, workspace projections, action metrics, and interaction-protocol/tool-schema fingerprints;
- bind plan and trial identity to materialized package/spec hashes, the actual registered scorer, and the declared aec-bench source inventory;
- bind each trial to the selected runtime provider and the realized bytes of its active dependency closure, then recapture and reconcile that fingerprint at invocation finalization;
- retain each fresh or persistent attempt in its own session directory, including interrupted attempts with unresolved provider identity;
- require every submitted checkpoint to have one final submitted attempt and durable session ownership before it can contribute reward;
- require every fresh-context session to own exactly one checkpoint, with retries receiving distinct attempt-specific session directories;
- cross the fresh-context environment boundary through strict, hash-captured per-attempt request/result contracts, with host-owned attempt identity published before execution, failed candidates preserved under their owning attempt, and no verifier or reward fields accepted from the environment;
- reconcile attempt/session mode, visibility, per-session turn budget, and requested/actual adapter identity, and keep mismatches as explicit unscored failures;
- derive cross-run lifecycle summaries from core ledger records and their snapshotted historical plan, never mutable run-directory scans or the current planner state;
- give an existing immutable snapshot authority over later mutable source state;
- publish session results, snapshots, and records atomically and fsync-durably through every new ancestor, and recover terminal-session crashes, artifact-only finalization, or a locked shared invocation index from durable evidence without rerunning the agent;
- quarantine a torn terminal session result before publishing a conservative unresolved failure, but reject malformed trajectory history rather than silently truncating or reconstructing it;
- persist the study design with each lifecycle calibration and never make causal claims beyond its budget and ordering controls;
- evaluate holdout generalization only from hash-pinned complete records and immutable snapshot artifacts under an exactly matched selected condition;
- keep holdout-derived transfer summaries build-only until their persistence and publication surfaces enforce internal visibility;
- keep true holdout evidence outside public variant registries and committed packages.

---

## Adapter Reserved Keys

Adapter-internal extraction metadata must use explicit reserved keys and must not leak into benchmark-semantic fields.

- In `lambda_rlm`, `__confidence__` is a reserved top-level extraction key used only for model-emitted confidence during leaf extraction.
- Executors must strip `__confidence__` before persisting semantic extraction payloads or passing extracted data into downstream generation and review prompts.
- Task authors, templates, and downstream consumers must not depend on `__confidence__` as if it were a task field.

---

## Gate Checks

### Enforce Early

| Check | What it validates |
| --- | --- |
| Contract conformance | Boundary payloads satisfy required shapes |
| Trial completeness | TrialRecord has enough provenance to replay outcomes |
| Code quality | Formatter, linter, typing, and tests pass |

### Build Next

| Check | What it validates | Invariant |
| --- | --- | --- |
| Replayability sampling | Historical runs replay within tolerance | #1 |
| Adapter purity | No task-specific branching in adapter code | #4 |
| Leakage guard | Holdout content never appears in public artefacts | #6 |
| Smoke gate | Smoke run passes before full experiment | #7 |
| Report parity | Communication outputs compile from evaluation artefacts only | #5 |

---

## Precedence

When constraints conflict, resolve them with this stack:

```
validity > reproducibility > coverage > cost > throughput
```
