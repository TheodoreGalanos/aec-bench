# LS-02B — Controlled Validity and Learning Assessment

**Status:** Proposed
**Type:** Implementation PRD
**Release:** Learning Studies Release A
**Depends on:** LS-01A, LS-01B, and LS-02A
**Blocks:** Release A reports and Gate A
**Primary owner:** `aec_bench.experimentation.learning_studies`
**Repository baseline:** `main`, reviewed 22 August 2026

## 1. Purpose

Determine what a completed study can legitimately claim and calculate learning-level comparisons without redefining task evaluation.

This PRD separates three questions that are often conflated:

1. **Did the task execution succeed?** — answered by the task’s normal evaluation and `TrialRecord`.
2. **Was the study comparison controlled and complete?** — answered by study validity checks.
3. **Did prior experience change later behaviour?** — answered by matched study measurements.

The assessor consumes ordinary trial records, learner-transition receipts, and named task-owned projections. It does not parse arbitrary domain payloads or reward reflection prose.

## 2. Goals

1. Add explicit descriptive, controlled, and invalid assessment outcomes.
2. Validate whether focal and comparator arms differ only in declared learning treatment.
3. Pair repetitions without pretending provider randomness was identically seeded.
4. Calculate transfer, boundary, composition, retention, interference, and efficiency results.
5. Keep cold competence visible beside learning gain.
6. Exclude missing or ineligible pairs rather than imputing them.
7. Preserve per-pair evidence and uncertainty summaries.
8. Require behavioural projections for boundary and composition claims.
9. Add no dense reward or RL-specific advantage model.

## 3. Non-goals

This PRD does not:

- alter canonical task rewards;
- judge task-domain correctness independently;
- infer causal structure from task text;
- parse chain-of-thought or prose for “learning”;
- compare different underlying models as a learning effect;
- provide a leaderboard;
- define adaptive curriculum fitness;
- train or update model weights.

## 4. Assessment validity states

Add:

```python
class LearningComparisonValidity(StrEnum):
    CONTROLLED = "controlled"
    DESCRIPTIVE_ONLY = "descriptive_only"
    INVALID = "invalid"
```

Meanings:

### Controlled

The study supports a bounded claim that prior exposure or its declared learner-state treatment changed performance on a matched probe under the recorded controls.

### Descriptive only

The sequence and outcomes are valid evidence, but one or more required controls are absent. The report may say what happened, not that exposure caused the difference.

### Invalid

Study evidence is missing, contradictory, contaminated, or structurally unusable for the requested measurement.

A whole study may contain measurements with different validity states.

## 5. Named outcome projections

The common assessor never reaches into task-specific evaluation dictionaries by ad hoc path.

Callers supply a mapping:

```python
OutcomeProjection = Callable[[TrialRecord], ProjectionResult]


@dataclass(frozen=True)
class ProjectionResult:
    eligible: bool
    value: float | None
    reason: str | None = None
```

Examples of projection IDs:

```text
canonical-reward
canonical-validity
calculation-correctness
boundary-judgment
safe-operational-outcome
unserved-capacity
```

The task or study integration owns the projection function and its domain meaning.

Rules:

- eligible results contain one finite scalar;
- booleans are normalised to `0.0` or `1.0` by the projection owner;
- ineligible results contain a reason and no value;
- the assessor never converts missing data to zero;
- a projection may use existing public evaluation data or a task-owned extension reference;
- hidden verifier data remains inaccessible unless the task owner deliberately publishes a study-safe projection.

## 6. Measurement contract

Add the following before Release A public use, either to `learning_study.py` or a focused assessment contract module.

```python
class LearningMeasurementKind(StrEnum):
    TRANSFER_GAIN = "transfer_gain"
    BOUNDARY_GAIN = "boundary_gain"
    COMPOSITION_GAIN = "composition_gain"
    RETAINED_GAIN = "retained_gain"
    RETENTION_DECAY = "retention_decay"
    INTERFERENCE_EFFECT = "interference_effect"
    LEARNING_EFFICIENCY = "learning_efficiency"


class ImprovementDirection(StrEnum):
    HIGHER = "higher"
    LOWER = "lower"


class LearningMeasurementSpec(StrictModel):
    measurement_id: NonEmptyStr
    kind: LearningMeasurementKind
    projection_id: NonEmptyStr
    direction: ImprovementDirection
    target_experience_id: NonEmptyStr
    focal_arm_id: NonEmptyStr
    comparator_arm_id: str | None = None
    reference_experience_id: str | None = None
    acquisition_experience_ids: tuple[NonEmptyStr, ...] = ()
    efficiency_denominator_id: str | None = None
```

Interpretation:

- `focal_arm_id` is the exposed, delayed, or interference arm being evaluated.
- `comparator_arm_id` is the cold or matched no-interference arm where required.
- `target_experience_id` is the probe being compared.
- `reference_experience_id` is used for within-arm change, especially retention decay.
- `acquisition_experience_ids` identify the experience cost included in efficiency calculations.

LS-01A should be extended to include:

```python
measurements: tuple[LearningMeasurementSpec, ...] = ()
```

before Release A is considered complete.

## 7. Controlled comparison requirements

A between-arm measurement is controlled only when all of the following are true for every matched pair.

### 7.1 Same initial capability

- same model identifier;
- same provider/client kind;
- same initial system prompt and fixed agent parameters;
- same compute policy and timeout policy;
- same initial harness artifacts;
- independently initialised but equivalent learner state.

### 7.2 Same probe

- same `experience_id` and resolved task ID;
- same task inputs and verifier authority;
- same execution-family adapter;
- same outcome projection;
- same probe feedback isolation.

### 7.3 Declared treatment difference only

Differences must be explained by:

- prior acquisition/practice/interference sequence;
- declared feedback schedule;
- declared learner-state treatment;
- declared consolidation operation.

Undeclared differences in model, budget, tools, task content, verifier, or host policy downgrade the measurement.

### 7.4 Arm isolation

- no shared writable learner artifact;
- no cross-arm feedback;
- no reused state ID;
- no probe-generated state committed into later measurement steps;
- no hidden evaluation data leaked into the focal learner.

### 7.5 Matched repetition

The focal and comparator arm runs share the same repetition number.

This pairing controls study organisation and temporal ordering. It does not claim identical stochastic sampling unless the provider separately supports and records it.

## 8. Descriptive downgrades

A requested controlled measurement becomes descriptive only when evidence remains usable but a causal control is absent, for example:

- no cold comparator arm;
- different budgets between arms;
- non-equivalent initial prompts;
- sequential runs separated by an uncontrolled model or provider change;
- adaptive task selection in one arm;
- a probe committed learner state before another measured step;
- task variants are related only by author assertion without the required family review.

The report must state the exact downgrade reason.

## 9. Invalid measurements

A measurement is invalid when:

- the target probe did not run in one required arm;
- a trial or state reference is corrupt;
- arm isolation failed;
- probe evaluation leaked before completion;
- the outcome projection is unavailable for every pair;
- focal and comparator records refer to different resolved probe tasks unexpectedly;
- state lineage is incomplete;
- a result was manually altered after study completion;
- relation or measurement references do not match the compiled plan.

## 10. Pair construction

For each measurement:

1. select the focal arm run for repetition `r`;
2. select the comparator arm run for the same `r`, if required;
3. locate the exact target experience step in each;
4. validate trial and state evidence;
5. apply the named outcome projection;
6. include the pair only if both projected values are eligible;
7. retain exclusions with explicit reasons.

Do not rematch a failed repetition to another repetition merely to increase sample size.

## 11. Effect calculation

Let:

- `F_r` be the focal value;
- `C_r` be the comparator value;
- `R_r` be an earlier reference value in the same arm.

Normalise improvement direction:

```text
higher is better: effect = F_r - C_r
lower is better:  effect = C_r - F_r
```

Thus a positive effect always means better focal performance.

### 11.1 Transfer gain

```text
exposed probe versus cold probe
```

after the declared acquisition experience.

### 11.2 Boundary gain

```text
boundary-correct focal projection versus cold projection
```

The projection should encode correct withholding or adaptation of the familiar method. Do not infer this from model prose.

A separate task-owned misuse projection may report negative-transfer rate directly.

### 11.3 Composition gain

```text
A+B acquisition arm versus cold composition probe
```

Additional A-only and B-only arms may diagnose whether the result reflects true composition.

### 11.4 Retained gain

```text
delayed exposed probe versus delayed cold probe
```

This is the primary retention claim because it controls for raw task difficulty.

### 11.5 Retention decay

Within the same focal arm:

```text
immediate probe performance minus delayed probe performance
```

Direction is reported so positive decay means deterioration. This is descriptive unless supported by a matched no-delay design.

### 11.6 Interference effect

```text
post-interference focal probe versus matched no-interference arm
```

A negative normalised effect indicates harmful interference.

### 11.7 Learning efficiency

Mandatory Release A denominator:

```text
number of acquisition and consolidation steps completed
```

Optional denominators may be supplied through named scalar projections over trial and transition evidence:

- model calls;
- input and output tokens;
- monetary cost;
- elapsed time.

Do not add a universal usage schema solely for this metric. Reuse existing usage records and adapter receipts where available.

## 12. Result contracts

Add a compact persisted assessment model.

```python
class PairedMeasurementValue(StrictModel):
    repetition: NonNegativeInt
    focal_trial_id: NonEmptyStr
    comparator_trial_id: str | None
    focal_value: float
    comparator_value: float | None
    normalised_effect: float


class LearningMeasurementResult(StrictModel):
    measurement_id: NonEmptyStr
    kind: LearningMeasurementKind
    validity: LearningComparisonValidity
    projection_id: NonEmptyStr
    included_pairs: tuple[PairedMeasurementValue, ...]
    excluded_repetitions: tuple[ExcludedPair, ...]
    focal_mean: float | None
    comparator_mean: float | None
    mean_effect: float | None
    median_effect: float | None
    effect_range: tuple[float, float] | None
    confidence_interval_95: tuple[float, float] | None
    diagnostics: tuple[str, ...]
```

The top-level study result references these measurement results alongside the execution evidence from LS-02A.

## 13. Uncertainty summaries

Always retain and display individual paired effects.

For `n` included pairs:

- `n = 0`: no aggregate effect;
- `n = 1`: report the single effect, no interval;
- `2 <= n < 5`: report mean, median, and range, no confidence interval;
- `n >= 5`: additionally report a deterministic 95% paired bootstrap percentile interval using only the Python standard library and a fixed documented sampling seed.

The interval is descriptive evidence about the observed repetitions, not a guarantee of broad population generalisation.

## 14. Absolute competence remains visible

Every report must place these side by side:

```text
cold probe performance
focal probe performance
normalised learning effect
```

A large positive gain from a very low baseline does not imply adequate competence.

Likewise, a zero gain at ceiling does not prove learning was absent; the report should flag ceiling and floor conditions when all pair values are near projection bounds supplied by the projection owner.

## 15. Reflection and memory are not outcomes

The assessor must not award learning credit because:

- a memory file is long;
- a consolidation response sounds insightful;
- the model says it learned something;
- a skill file contains preferred terminology.

Such artifacts are explanatory evidence only. Learning is measured through later behaviour on declared probes.

## 16. Assessment API

Conceptually:

```python
def assess_learning_study(
    *,
    spec: LearningStudySpec,
    plan: CompiledLearningStudy,
    execution: RecordedStudyExecution,
    projections: Mapping[str, OutcomeProjection],
    efficiency_projections: Mapping[str, EfficiencyProjection] = {},
) -> LearningStudyAssessment:
    ...
```

The function is deterministic and performs no model call.

## 17. File changes

Expected additions:

```text
src/aec_bench/experimentation/learning_studies/assessment.py
tests/experimentation/learning_studies/test_assessment.py
```

Expected modifications:

```text
src/aec_bench/contracts/learning_study.py
src/aec_bench/contracts/learning_study_evidence.py
```

Do not modify task evaluators in this PRD. LS-04A and study-family work supply projections.

## 18. Test matrix

### Valid controlled comparisons

- transfer gain with several matched repetitions;
- higher-is-better projection;
- lower-is-better projection;
- boundary projection;
- retained gain;
- interference comparator;
- composition with A+B arm.

### Downgrade tests

- no control arm;
- different agent configuration;
- different compute budget;
- unmatched probe task;
- adaptive sequence;
- probe state committed.

### Invalid tests

- missing trial reference;
- corrupt state lineage;
- cross-arm state ID;
- leaked probe feedback;
- all projections ineligible;
- wrong repetition pairing.

### Missing-data tests

- one ineligible pair excluded with reason;
- no imputation;
- aggregate `n` reflects included pairs only;
- arm mean does not silently combine unmatched records.

### Statistical summary tests

- exact per-pair effects;
- direction normalisation;
- range and median;
- deterministic bootstrap for `n >= 5`;
- no interval for very small `n`.

### Regression tests

- canonical task reward unchanged;
- existing evaluation result unchanged;
- no reflection prose parser introduced.

## 19. Acceptance criteria

LS-02B is complete when:

1. Every requested measurement is labelled controlled, descriptive only, or invalid with reasons.
2. Controlled comparisons require matched cold or no-interference controls and equivalent probe conditions.
3. Per-repetition effects are preserved and aggregated without imputation.
4. Cold competence and focal competence remain visible beside learning gain.
5. Boundary and composition claims rely on task-owned behavioural projections.
6. Retained gain and retention decay are reported as distinct quantities.
7. Probe contamination and incomplete lineage invalidate affected measurements.
8. The assessor does not alter canonical task evaluation or add RL rewards.

## 20. Agent handoff

The implementation agent should return:

- final measurement contract;
- controlled-comparison checklist encoded in validation;
- projection API and at least three concrete test projections;
- excluded-pair behaviour;
- statistical summary implementation;
- examples of controlled, descriptive-only, and invalid reports;
- confirmation that task rewards and reflection artifacts are not reinterpreted.
