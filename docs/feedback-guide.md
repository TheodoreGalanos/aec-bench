# ABOUTME: Guide for the Python feedback domain covering expert annotation, calibration, and benchmark improvement.
# ABOUTME: Defines how structured human review flows back into evaluation, tasks, and communication without contaminating holdout data.

# Feedback Guide

Feedback is the structured return loop from expert review into the benchmark. It keeps the benchmark aligned with real engineering practice and prevents the system from mistaking verifier quirks for capability.

Parent document: [ARCHITECTURE.md](ARCHITECTURE.md).
Data shapes: [CONTRACTS.md](CONTRACTS.md).
Rules: [INVARIANTS.md](INVARIANTS.md).

---

## What Feedback Is

Feedback includes:

- expert assessment of outputs and traces,
- structured annotations,
- identification of task and verifier defects,
- rubric refinement,
- suggestions for new instances,
- calibration data for automated judgment.

Feedback is not:

- a replacement for verifier scoring,
- an unstructured opinion channel,
- a direct path from comment to code change.

---

## Annotation Workflow

Annotations should record:

- reviewer identity,
- reviewer discipline,
- timestamp,
- pass/fail/defer judgment,
- emergent error categories,
- rationale notes.

Cycle:

1. assign trials,
2. review in context,
3. capture structured annotations,
4. aggregate and measure agreement,
5. adjudicate meaningful disagreements,
6. integrate the adjudicated result.

Unresolved disagreement should be explicit, not silently averaged away.

---

## Calibration and Weighting

Calibration sets should contain:

- clear passes,
- clear fails,
- ambiguous cases.

Reference judgments should be governed, versioned, and revisited when evidence shows they are wrong or stale.

Reviewer weighting can use:

- discipline match,
- calibration performance,
- relevant experience.

The weighting policy should stay transparent and bounded.

---

## What Feedback Produces

To evaluation:

- richer confidence metadata,
- human-derived taxonomy labels,
- rubric signals,
- judge calibration data.

To tasks:

- verifier fixes,
- instruction clarification,
- new instance proposals,
- rubric refinement,
- lifecycle decisions.

To communication:

- clearer distinction between mechanically scored results and expert-reviewed results.

---

## Anti-Contamination

Feedback on holdout tasks is highly sensitive.

Allowed to flow back broadly:

- general capability patterns,
- general error category definitions,
- behavioral observations without holdout specifics.

Not allowed to flow back broadly:

- specific holdout findings,
- holdout verifier logic,
- holdout briefs,
- per-trial holdout annotations.

This should be enforced structurally in export and reporting code, not treated as a polite request people might forget.

---

## Continuous Improvement

Feedback drives a continuous loop:

1. experiments run,
2. evaluation surfaces informative trials,
3. experts annotate,
4. defects and opportunities are identified,
5. benchmark assets improve,
6. the next run benefits from those corrections.
