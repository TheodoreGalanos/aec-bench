# A01 — Artifact Structural Transfer Study Protocol

**Status:** Proposed research protocol
**Release:** Learning Studies Release A
**Depends on:** LS-01A through LS-04A and one reviewed `LearningFamilySpec`
**Primary question:** Does experience with one task improve performance on a changed task that preserves the relevant underlying method?
**Claim mode:** Controlled learning comparison

## 1. Purpose

Run the first controlled AEC-Bench study in which prior experience, rather than fixed-candidate breadth, is the independent variable.

The protocol is intentionally simple:

```text
acquisition task
→ declared feedback
→ optional learner-state update
→ structurally related probe
```

compared against the same probe completed cold.

The study does not assume that prior exposure will help. Positive, zero, and negative transfer are all valid outcomes.

## 2. Research question

> When an artifact-task probe changes surface representation or numerical parameters while preserving the governing method, does a learner with relevant prior experience outperform an otherwise matched cold learner?

Secondary questions:

- Is raw prior history sufficient?
- Does explicit structured consolidation improve over raw history?
- Does carrying no learner state eliminate the apparent effect?
- Does any gain come with increased model usage or unnecessary checking?

## 3. Required task-family properties

Select one reviewed family relation with:

- exactly one acquisition member;
- exactly one probe-only target;
- the same governing method or reasoning structure;
- at least one changed surface or parameter dimension;
- no changed causal or applicability condition;
- deterministic or stable task-owned evaluation;
- enough headroom to avoid a cold ceiling;
- no acquisition artifact that reveals the probe’s exact answer.

The family review must state, in plain engineering terms:

1. what knowledge or procedure is expected to transfer;
2. why it remains valid in the probe;
3. what changed;
4. what did not change;
5. how the verifier can distinguish correct transfer from superficial copying.

### Candidate areas for repository audit

These are starting points, not pre-approved study members:

- changed representations or parameter bands within `pump-head-calculation`;
- changed representations or parameter bands within `hazen-williams-friction`;
- changed load or geometry cases within a structural calculation family;
- another generated family with multiple clean, independently verified instances.

Exact task IDs must be frozen in the protocol amendment before the claim-bearing run.

## 4. Preregistered relation

The final family relation must declare:

```text
purpose: transfer
source: acquisition member A
target: probe member B
invariant dimensions: at least the governing method
changed dimensions: surface and/or parameter only
expected direction: unspecified scientifically; positive is the design hypothesis
```

Do not proceed if domain review finds that B requires a materially different method.

## 5. Study arms

Use one common initial `AgentConfig`, model, client, compute policy, timeout, and task evaluator.

### Arm C0 — Cold reset

```text
probe B
```

Treatment: `reset`

Purpose: absolute cold competence and comparator for every learning arm.

### Arm C1 — Sham exposure with reset

```text
acquisition A
→ probe B with reset learner state
```

Treatment: reset between experiences.

Purpose: detect orchestration, temporal, provider, or ordering effects when no declared learner state can carry forward.

This arm may be omitted from the first smoke run but is required for the claim-bearing campaign unless provider isolation is independently proven.

### Arm E1 — Raw history

```text
acquisition A
→ release public evaluation
→ probe B
```

Treatment: `raw-history`

Purpose: measure transfer from direct access to a public record of prior experience without explicit consolidation.

### Arm E2 — Structured memory

```text
acquisition A
→ release public evaluation
→ consolidate into structured memory
→ probe B
```

Treatment: `structured-memory`

Purpose: measure whether explicit compression into reusable memory improves probe behaviour.

### Optional Arm E3 — Explicit harness update

```text
acquisition A
→ release public evaluation
→ consolidate into allowlisted prompt or skill artifact
→ probe B
```

Include only after LS-04A’s harness-update treatment passes isolation and update-authority tests.

## 6. Feedback schedule

The claim-bearing default is:

```text
public-evaluation
```

It may include:

- task validity;
- canonical reward;
- public evaluator breakdown;
- a learner-safe failure category.

It must not include:

- expected probe answer;
- hidden verifier source;
- private holdout content;
- model-generated coaching not declared in the study;
- a task explanation unavailable to ordinary users of the benchmark.

A separate terminal-outcome-only ablation may be added later. Do not vary feedback view within the primary comparison.

## 7. Consolidation operation

Use one fixed operation such as:

```text
update-structured-memory
```

The instruction should ask the learner to preserve:

- the governing method;
- its applicability conditions;
- the checks that demonstrated correctness;
- errors or uncertainties from the acquisition attempt.

It must not instruct the learner about the hidden probe or name its changed values.

The consolidation output is explanatory evidence only. It is not scored as learning.

## 8. Outcome projections

### Primary

One task-owned higher-is-better projection that represents substantive correctness on probe B.

Preferred order:

1. exact task correctness or canonical reward when sufficiently informative;
2. a reviewed calculation-correctness projection;
3. a composite public projection already owned by the evaluator.

### Secondary

- canonical validity;
- false-positive or false-finding count where relevant;
- completion status;
- model calls;
- input and output tokens;
- cost;
- task elapsed time;
- consolidation cost;
- unnecessary checks, only if a task-owned projection exists.

Do not create an informal score solely for this study when the task evaluator already has an appropriate one.

## 9. Measurements

Required:

```text
E1 transfer gain = raw-history probe − cold probe
E2 transfer gain = structured-memory probe − cold probe
C1 sham effect   = reset-after-acquisition probe − cold probe
```

Optional:

```text
structured-memory advantage = E2 − E1
harness-update gain          = E3 − C0
learning efficiency          = gain / acquisition-and-consolidation cost
```

The sham effect should be near zero under correct isolation. A substantial effect triggers an investigation before interpreting E1 or E2.

## 10. Repetitions and run stages

### Stage 1 — Deterministic plumbing proof

- one repetition;
- synthetic or inexpensive model configuration;
- verifies identity, feedback, state, probe discard, and assessment wiring;
- makes no learning claim.

### Stage 2 — Real-model pilot

- three matched repetitions per arm;
- validates task headroom and cost;
- results remain preliminary.

### Stage 3 — Claim-bearing campaign

- at least five matched repetitions per arm;
- ten preferred where model variance and cost permit;
- exact model and provider configuration frozen before the first campaign run;
- arm runs interleaved by repetition.

Do not increase repetition count after inspecting the direction of the primary result without documenting a new campaign.

## 11. Validity requirements

A transfer measurement is controlled only when:

- all arms use the same probe B;
- initial model and harness are equivalent;
- each arm has isolated learner state;
- probe state is discarded;
- only the declared experience, feedback, and treatment differ;
- the acquisition task is absent from C0;
- B remains probe-only;
- no provider-side persistent conversation or cache crosses arms;
- the task evaluator and projection are unchanged;
- repetitions pair exactly.

## 12. Threats and diagnostics

### Cold ceiling

If C0 already performs near perfectly, zero gain is uninterpretable. Select a harder but fair probe or report the ceiling.

### Acquisition failure

A learner cannot be assumed to have acquired the method merely because it saw task A. Report acquisition performance and stratify interpretation without post hoc excluding inconvenient failures.

### Surface leakage

If A and B share phrases, filenames, or output layouts that trivially reveal the solution, the relation is not a clean structural-transfer probe.

### Memory volume confound

Raw history may supply more tokens than structured memory. Report context size and cost; do not attribute every difference to abstraction quality.

### Provider drift

Interleave arms by repetition and record dates, model identity, and client configuration through existing run evidence.

## 13. Preregistration checklist

Before the claim-bearing run, freeze:

- exact acquisition and probe task IDs;
- family relation and domain review;
- all arm definitions;
- feedback view;
- consolidation instruction;
- model, client, and compute configuration;
- repetitions;
- primary projection;
- secondary projections;
- treatment implementations;
- inclusion and exclusion rules;
- planned comparison set;
- ceiling/floor diagnostic thresholds;
- report location.

Use ordinary committed configuration and Git history. Do not add a separate package hash registry.

## 14. Success criteria for the protocol

The study succeeds as a research instrument when:

1. all planned arms and pairs execute with valid evidence;
2. cold competence and acquisition competence are visible;
3. the learner-state difference is inspectable;
4. probe isolation is proven;
5. transfer effects can be calculated without ad hoc record parsing;
6. a zero or negative result can be reported honestly.

A positive transfer gain is not an acceptance criterion for the software.

## 15. Required report

The report must include:

- task-family rationale;
- exact relation;
- arm and feedback diagram;
- acquisition performance;
- cold and exposed probe values by repetition;
- sham effect;
- paired transfer effects;
- learner-state channel summary;
- cost and token summary;
- excluded pairs and reasons;
- validity status;
- representative memory artifacts, redacted where required;
- interpretation and limitations.
