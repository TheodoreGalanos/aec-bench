# ABOUTME: Guide for the Python evaluation domain covering scoring, trace analysis, expert review, and confidence.
# ABOUTME: Defines the layered evaluation pipeline and the role of human and automated judgment.

# Evaluation Guide

Evaluation is everything that happens after execution. It turns verifier outputs and transcripts into structured assessments of capability. The core rule remains: evaluation is a pipeline, not a number.

Parent document: [ARCHITECTURE.md](ARCHITECTURE.md).
Data shapes: [CONTRACTS.md](CONTRACTS.md).
Rules: [INVARIANTS.md](INVARIANTS.md).

---

## Evaluation Layers

### Layer 1: Mechanical verification

Produced by the verifier during the trial:

- reward,
- validity,
- details breakdown.

### Layer 2: Trace analysis

Mechanical extraction from transcripts:

- turn count,
- tool call count,
- tool error count,
- specific tool usage,
- output production,
- first error,
- token usage,
- duration,
- transcript format metadata.

### Layer 3: Human review

Structured expert annotation:

- pass/fail/defer,
- emergent error categories,
- rationale notes,
- rubric assessment for qualitative tasks.

### Layer 4: Automated judgment

Calibrated judges may automate selected subjective dimensions once human agreement is strong enough.

### Layer 5: LLM reviewer

The LLM reviewer is a post-verifier meta-evaluation stage. It consumes the
completed run evidence, verifier output, artifacts, traces, and the materialized
task-world profile, then writes structured findings under `logs/reviewer/` for
local runs or `reviewer/` inside Harbor trial directories.

The reviewer does not replace verifier reward. It answers a different question:
whether the verifier result is interpretable under the current task-world
schema, or whether the run should be treated as a verifier-language, evidence,
schema, governance, containment, or model-failure finding.

Task-world profiles may be supplied by a task sidecar such as `world.yaml`; when
absent, evaluation derives a conservative default profile from the task path,
instruction, verifier artifacts, output, and trace channels. The materialized
profile is persisted as `world_profile.json` beside the reviewer request.

---

## Mechanical Verification Boundary

The verifier belongs to the task. Evaluation consumes verifier output and adds enrichment later. Evaluation should never overwrite the original verifier result; it adds structured context around it.

The LLM reviewer follows the same boundary. It can flag verifier
miscalibration, missing evidence, or event candidates, but it never edits
`reward.json` or `details.json`.

### Conditional-evidence diagnostics

Evidence-request actions are not directly scored and the request protocol does not own reward. They can change later observations and thereby influence a submission that the task verifier scores. Lifecycle operational metrics derive boundary-valid request actions, first successful releases, repeated releases, typed rejections, consumed budget, and released artifact count from durable host action records rather than model prose. Malformed tool calls remain trajectory evidence but are not lifecycle request actions. The invocation manifest separately binds the versioned request protocol and exact model-visible tool schema.

These values diagnose information-gathering behavior and action efficiency. A successful request is not automatically a useful request, and fewer actions are not automatically better. Reward remains task-owned until a task verifier defines what evidence and engineering consequences were sufficient.

### Descriptive holdout generalization

Lifecycle transfer evaluation is a post-verifier evidence contract, not another execution stage. It reads hash-pinned immutable `TrialRecord` and snapshot artifacts, requires explicit public-calibration and holdout visibility, and checks an exact selected execution condition before reporting target reward. PR21 now derives that condition through a preregistered public-only selector and freezes requested/resolved runtime identity plus the lifecycle-operation protocol and full tool schema before holdout mounting. Version-4 action snapshots additionally reconcile the public request catalogue, action history, canonical transaction bytes, workspace projections, action metrics, and interaction-protocol/tool-schema fingerprints. Partial records, incomplete verification, shared source/target package identity, condition drift, missing action evidence, or artifact tampering produce `not_evaluable` with explicit reasons.

The result describes holdout generalization under a condition selected on public calibration evidence. It does not report a causal effect, winner, or cross-run learner transfer, and semantic-transition metrics remain optional diagnostics rather than a replacement score. The current API is build-only because generic evaluation persistence does not yet enforce a holdout/internal publication boundary. PR20 makes accidental persistence fail closed for sealed packages; it does not turn full-fidelity manifests, `TrialRecord`s, or transfer summaries into redacted public outputs.

---

## Trace Analysis Rules

Trace extraction should be:

- deterministic,
- format-aware,
- mechanical rather than interpretive,
- metadata-preserving rather than transcript-replacing.

Trace signals are diagnostic and triage-oriented. They inform engineering decisions but do not replace canonical reward.

---

## Human Review Rules

Human review is the ground truth layer for qualitative assessment.

Key rules:

- review full transcripts,
- capture structured judgments,
- let categories emerge bottom-up,
- use the reviewed set for taxonomy and judge calibration,
- keep free text advisory unless tied to structured fields.

---

## Automated Judgment Rules

Use judges only when:

- the dimension is clearly defined,
- human agreement is strong enough to imitate,
- the judge is validated against held-out human labels,
- prompt and calibration versioning are explicit.

Prefer binary dimensions over vague multi-axis “overall quality” judgments.

---

## Error Taxonomy and Behavior

The taxonomy should grow bottom-up from reviewed traces. Behavioral evaluation complements reward by describing how the agent worked:

- structured success vs lucky success,
- incomplete-but-sensible behavior vs genuine failure,
- efficient vs wasteful execution patterns.

Behavioral metrics remain diagnostic. They do not replace task correctness.

---

## Confidence

Evaluation should attach confidence metadata when available, including:

- reviewer count,
- inter-rater agreement,
- uncertainty from repetition,
- evaluation completeness.

The system should not pretend a point estimate is the whole truth.
