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

---

## Mechanical Verification Boundary

The verifier belongs to the task. Evaluation consumes verifier output and adds enrichment later. Evaluation should never overwrite the original verifier result; it adds structured context around it.

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
