# ABOUTME: High-level spec for cross-track disagreement analysis over verifier, judge, and behavioural signals.
# ABOUTME: Defines the three comparisons, their interpretation, and the triage output for human review.

# Disagreement Analysis

A proposal for a new evaluation layer that compares the three signal tracks we already compute and surfaces the trials where they disagree. The disagreements — not the agreements — are where open-world capability signal lives.

Parent document: [evaluation-guide.md](evaluation-guide.md).
Related contracts: [CONTRACTS.md](CONTRACTS.md).
Related rules: [INVARIANTS.md](INVARIANTS.md).

---

## Motivation

Our evaluation pipeline currently produces three parallel scores for each trial:

1. **Verifier reward** — mechanical pass/fail from `verify.py`, always computed.
2. **Rubric / judge score** — LLM-as-judge over final output and rationale, opt-in.
3. **Behavioural structural score** — bond-type classification and similarity to an ideal process shape, opt-in.

Each track answers a different question:

| Track | Question it answers |
|---|---|
| Verifier | Is the final answer numerically correct? |
| Judge | Is the final answer methodologically defensible? |
| Behavioural | Did the agent follow a sound process? |

Today these three numbers are computed and reported in isolation. A trial with reward 1.0 is treated as a success regardless of what the transcript shows. A trial with reward 0.0 is treated as a failure regardless of whether the method was correct but the arithmetic slipped.

Open-world evaluations (see [CRUX's framing](https://cruxevals.com/)) argue that **outcome-only scoring misses the most important signal**: whether the agent succeeded for the right reasons. At our scale we cannot afford CRUX-style per-trial expert log review, but we can approximate it by asking where the three tracks disagree and triaging those trials for human attention.

---

## The Three Comparisons

### 1. Verifier vs Judge

Compares numerical correctness against methodological defensibility.

| Verifier | Judge | Profile | Interpretation |
|---|---|---|---|
| Pass | Pass | `aligned_success` | Answer correct, method defensible — trust it. |
| Pass | Fail | `suspected_reward_hack` | Right number, wrong process. Possible fabrication, lucky guess, hardcoded value, or gameable verifier. |
| Fail | Pass | `verifier_miscalibration` | Method sound but verifier rejects. Likely tolerance issue, unit mismatch in verifier, or over-strict equality check. |
| Fail | Fail | `aligned_failure` | Genuine failure in both answer and process. |

**Primary value:** catches reward hacking and verifier miscalibration. This is the analogue of the CRUX iOS experiment finding where the agent fabricated a phone number and Apple approved it anyway — the "verifier" signed off on something the transcript would reveal as wrong.

### 2. Behavioural vs Verifier

Compares process shape against numerical correctness.

| Behavioural | Verifier | Profile | Interpretation |
|---|---|---|---|
| Sound process | Pass | `earned_success` | Process and answer both good. |
| Sound process | Fail | `near_miss` | Correct approach, failed on execution detail (arithmetic slip, unit conversion, final rounding). Candidate for verifier tolerance review. |
| Unsound process | Pass | `lucky_success` | Disordered or shallow process, correct answer. Suggests reward hacking or trivial task. |
| Unsound process | Fail | `aligned_failure` | Bad process, bad answer. |

**Primary value:** separates "understands the problem" from "got the number." Useful for curriculum design — `near_miss` tasks are where models are close to breakthrough.

### 3. Judge vs Behavioural

Compares methodological defensibility against process shape.

| Judge | Behavioural | Profile | Interpretation |
|---|---|---|---|
| Pass | Sound | `coherent` | Methodology and process agree. |
| Pass | Unsound | `post_hoc_rationalisation` | Output looks defensible but transcript doesn't support it. Possible confabulation in final write-up. |
| Fail | Sound | `unexpressed_competence` | Transcript shows sound reasoning but final output loses it. Communication or formatting failure. |
| Fail | Unsound | `aligned_failure` | Bad process, bad write-up. |

**Primary value:** catches the gap between what the agent *did* and what the agent *says it did*. Relevant for AEC deliverables where the report matters as much as the calculation.

---

## Disagreement Profile

Every trial is tagged with a single `DisagreementProfile` derived from the three 2x2s:

```
DisagreementProfile = {
    "verifier_judge": "aligned_success" | "suspected_reward_hack" | "verifier_miscalibration" | "aligned_failure",
    "behavioural_verifier": "earned_success" | "near_miss" | "lucky_success" | "aligned_failure",
    "judge_behavioural": "coherent" | "post_hoc_rationalisation" | "unexpressed_competence" | "aligned_failure",
    "triage_class": "<derived priority tag>",
    "triage_reason": "<short explanation>",
}
```

The `triage_class` collapses the three comparisons into a single priority tag used for review ranking:

- `trust` — all three aligned positive.
- `ignore` — all three aligned negative (known failure, no new information).
- `reward_hack_candidate` — verifier passes but judge or behavioural disagrees.
- `verifier_miscalibration_candidate` — judge and behavioural agree the process is sound but verifier fails.
- `communication_failure` — behavioural sound and judge fails, suggesting write-up issue.
- `ambiguous` — mixed signal not captured above; surface for human review.

---

## Inputs and Dependencies

Disagreement analysis is a **pure function over existing contracts**. It introduces no new data collection.

Required per trial:

- `TrialRecord.evaluation.reward` — verifier output.
- Rubric / judge score — currently opt-in via `llm_judge.py` + `rubric_scorer.py`. Must be run to enable the verifier/judge and judge/behavioural comparisons.
- Behavioural classification — currently opt-in via the behavioural classifier injection point in `pipeline.py`. Must be run to enable the behavioural comparisons.

**Implication:** disagreement analysis is only useful if behavioural and judge tracks are wired into the default evaluation flow, or at minimum run consistently for experiments where this analysis is wanted. See the wiring section below.

---

## Thresholding

Each track produces a continuous or categorical score. To run the 2x2s we need a binary projection per track:

- **Verifier:** `reward >= task.pass_threshold` (defaults to `1.0` for exact-match tasks, task-defined for partial-credit).
- **Judge:** `rubric_result.overall_score >= rubric.pass_threshold` (rubric-defined).
- **Behavioural:** `structural_score >= behavioural.pass_threshold` (default `0.6`, tunable per task category).

Thresholds are stored alongside the disagreement output so downstream consumers can reinterpret. The 2x2 projection is a reporting view, not a replacement for the underlying scores.

---

## Output Shape

A new artefact `disagreement.json` is written per experiment, sibling to existing evaluation artefacts:

```
artefacts/ledger/<experiment>/_evaluations/disagreement.json
```

Structure:

```json
{
  "experiment_id": "...",
  "thresholds": { "verifier": 1.0, "judge": 0.7, "behavioural": 0.6 },
  "profiles": [
    {
      "trial_id": "...",
      "task_id": "...",
      "adapter": "...",
      "profile": { ... DisagreementProfile ... }
    }
  ],
  "summary": {
    "triage_counts": { "trust": 42, "reward_hack_candidate": 3, ... },
    "by_adapter": { ... },
    "by_task_category": { ... }
  },
  "review_queue": [
    { "trial_id": "...", "triage_class": "...", "priority": 1 }
  ]
}
```

The `review_queue` is the practical output: an ordered list of trials where human spot-review is most likely to produce new insight. Priority is assigned by triage class, not by reward.

---

## Pipeline Wiring

The proposal affects the evaluation pipeline in three places:

1. **Make behavioural classification a default layer.** Today it is opt-in via classifier injection in `summarize_evaluation_records`. Move it to run by default when a classifier is configured at the experiment level, and record its presence/absence in the evaluation artefact.

2. **Make judge scoring a first-class layer alongside behavioural.** Today `llm_judge.py` is invoked per-rubric in ad-hoc scripts. Lift it into `pipeline.py` with the same injection pattern as behavioural.

3. **Add `disagreement.py` as the final stage.** Consumes the enriched `TrialRecord` set and writes `disagreement.json`. Does not modify any upstream contract.

Order of execution in `pipeline.py`:

```
verifier (task boundary)
  → trace_summary (mechanical)
  → behavioural (if classifier configured)
  → judge (if rubric configured)
  → disagreement (if both behavioural and judge ran)
  → artefact write
```

Disagreement analysis degrades gracefully: if only one of the optional layers ran, it reports the subset of comparisons it can. If neither ran, it is skipped and reported as skipped in the artefact.

---

## Non-Goals

The following are explicitly out of scope for this spec:

- **New signal collection.** Disagreement analysis is a join over existing tracks. Any new signal (assumption extraction, source citation validation, units auditing) is a separate proposal.
- **Automated remediation.** Flagged trials are surfaced for human review, not auto-corrected.
- **Rubric authoring.** This spec assumes rubrics exist; it does not define how to write them.
- **Behavioural taxonomy revision.** The existing bond-type taxonomy is taken as given.
- **Cross-experiment analysis.** Scope is per-experiment for now; aggregation across experiments is future work.

---

## Success Criteria

The analysis is working when:

1. For every experiment with behavioural and judge layers enabled, `disagreement.json` is produced automatically.
2. The review queue for a sample experiment surfaces at least one trial per triage class with interpretable evidence.
3. Spot review of `suspected_reward_hack` trials confirms the label ≥70% of the time, or the label is recalibrated.
4. `verifier_miscalibration_candidate` trials have driven at least one verifier tolerance fix.
5. The analysis adds less than 5% to overall evaluation runtime (it is a pure join; cost is negligible).

---

## Open Questions

- **Rubric availability.** Not every task has a rubric today. Do we require rubric coverage before enabling judge comparisons, or accept partial coverage and report the subset?
- **Behavioural classifier cost.** The LLM-based turn classifier has non-trivial cost on long trajectories. Is per-trial classification affordable for every experiment, or do we sample?
- **Threshold calibration.** Default thresholds for behavioural structural scores are untuned. Should thresholds be discipline-specific?
- **Human review workflow.** `Annotation` contract exists but no UI exists. Is a CLI-driven review loop sufficient, or do we need a minimal web surface?
- **Feedback into taxonomy.** When a triage class consistently mislabels trials, what is the revision process?
