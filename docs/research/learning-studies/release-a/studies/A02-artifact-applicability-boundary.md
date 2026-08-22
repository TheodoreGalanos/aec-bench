# A02 — Artifact Applicability Boundary and Negative-Transfer Protocol

**Status:** Proposed research protocol
**Release:** Learning Studies Release A
**Depends on:** LS-01A through LS-04A and one reviewed boundary relation
**Primary question:** Can the learner recognise when a previously useful method no longer applies?
**Claim mode:** Controlled learning comparison

## 1. Purpose

Test the most important failure mode hidden by ordinary transfer scores:

> Prior success can make a learner worse when a later task looks familiar but changes the conditions under which the learned method is valid.

The study is designed to distinguish:

- useful structural transfer;
- harmless non-transfer;
- harmful over-application of a familiar method.

It therefore evaluates an applicability judgment, not merely final reward.

## 2. Research question

> After successful or partially successful experience with method M, does the learner correctly withhold, modify, or replace M when a later probe changes the governing mechanism or applicability conditions?

Secondary questions:

- Does raw history increase method fixation?
- Does structured memory that records applicability conditions reduce fixation?
- Does acquisition quality predict later over-application?
- Can the learner still recognise the superficial similarity without treating it as decisive?

## 3. Required task-family properties

The reviewed family must contain:

- acquisition task A, where method M is appropriate;
- probe-only boundary task B, where M is wrong, insufficient, or unsafe;
- meaningful surface similarity between A and B;
- a changed causal or applicability dimension;
- a verifier or task-owned projection capable of identifying inappropriate use of M;
- a valid alternative response for B.

The pair must not be merely “harder.” The reason M fails must be specific and reviewable.

### Candidate areas for repository audit

Possible starting points include:

- pressure-loss tasks where a familiar friction-only approach is insufficient because minor losses or another governing contribution becomes material;
- pump calculations where a familiar power calculation is invalid without a changed efficiency or operating-condition treatment;
- structural cases where the same geometry is governed by a different failure mode;
- clean versus issue-bearing review tasks where prior issue detection could create false positives.

Exact tasks require BRIEF and verifier review before use.

## 4. Boundary relation declaration

The final relation must declare:

```text
purpose: boundary
source: acquisition A
target: boundary probe B
invariant: selected surface or representational properties
changed: causal and/or applicability dimension
familiar method: M
required boundary behaviour: withhold, modify, or replace M
```

The protocol amendment must explain:

1. why a competent learner may perceive similarity;
2. which evidence should override that similarity;
3. what observable action or artifact constitutes inappropriate reuse;
4. what correct alternative behaviour looks like.

## 5. Study arms

Use the same initial model, client, agent, compute policy, and probe across arms.

### Arm C0 — Cold boundary

```text
boundary probe B
```

Treatment: `reset`

Purpose: baseline ability to solve B without induced method familiarity.

### Arm C1 — Acquisition with reset

```text
acquisition A
→ boundary probe B with reset state
```

Purpose: detect temporal or provider effects without learner continuity.

### Arm E1 — Raw history

```text
acquisition A
→ release public evaluation
→ boundary probe B
```

Purpose: test whether direct prior history helps or causes fixation.

### Arm E2 — Structured memory

```text
acquisition A
→ release public evaluation
→ consolidate applicability-aware memory
→ boundary probe B
```

The consolidation instruction asks for:

- method M;
- its preconditions;
- disconfirming evidence;
- stopping or switching conditions;
- known failure modes.

It does not reveal B.

### Optional Arm E3 — Procedure-only memory

Consolidate the procedure but deliberately omit applicability prompts.

This is a useful ablation only if ethically and scientifically justified. It tests whether recording procedure without boundaries increases negative transfer.

## 6. Primary behavioural projections

The task owner must provide at least one of these before the study proceeds.

### `boundary-judgment`

Higher-is-better scalar or boolean indicating that the learner correctly withheld, modified, or replaced M.

### `familiar-method-misuse`

Lower-is-better scalar or boolean indicating inappropriate application of M.

The projection must come from submitted artifacts, declared calculations, findings, or tool actions. It must not be inferred from chain-of-thought style or phrases such as “I reconsidered.”

## 7. Secondary outcomes

- canonical reward;
- task validity;
- correctness of the alternative method;
- false-positive count;
- unnecessary work or checking;
- output completeness;
- model usage and cost;
- acquisition performance on A.

A learner that merely avoids M by failing to act should not receive full boundary credit. The projection should distinguish correct switching from non-completion.

## 8. Measurements

Required:

```text
raw-history boundary gain
  = E1 boundary judgment − C0 boundary judgment

structured-memory boundary gain
  = E2 boundary judgment − C0 boundary judgment

raw-history misuse effect
  = C0 misuse − E1 misuse, normalised so positive is improvement

structured-memory misuse effect
  = C0 misuse − E2 misuse
```

Also report:

```text
sham exposure effect = C1 − C0
structured-memory advantage = E2 − E1
```

Negative transfer is present when prior exposure produces a negative normalised boundary effect or a higher misuse rate than cold control.

## 9. Acquisition interpretation

Record whether each focal learner actually executed M correctly on A.

Do not post hoc remove unsuccessful acquisitions from the primary intention-to-treat comparison.

Add a clearly labelled secondary analysis:

```text
boundary performance conditional on successful acquisition
```

only when the success criterion was preregistered. This analysis explains mechanism; it does not replace the primary comparison.

## 10. Repetitions and run stages

Use the same staged pattern as A01:

- one-repetition plumbing proof;
- three-repetition real-model pilot;
- at least five matched repetitions for the claim-bearing campaign;
- ten preferred where practical.

The boundary probe should be calibrated so cold performance is neither near zero nor ceiling. A completely opaque probe cannot reveal induced fixation cleanly.

## 11. Validity requirements

In addition to LS-02B controlled-comparison rules:

- B must remain probe-only;
- acquisition materials cannot name B’s changed condition;
- the boundary projection must be fixed before results are seen;
- C0 and focal arms use the identical B instance;
- structured memory is generated without hidden probe knowledge;
- method misuse is observable in public task evidence;
- the correct alternative remains feasible under the same tool and budget policy.

## 12. Threats and diagnostics

### Different task, not boundary task

If A and B share too little structure, failure to transfer says nothing about applicability judgment. Domain review must defend the similarity.

### Mere difficulty

If B is simply harder, lower focal performance may reflect difficulty rather than negative transfer. The misuse projection is essential.

### Over-specific consolidation

A memory artifact that copies A’s exact values may be more likely to mislead than one that records method conditions. Report memory contents and size.

### Conservative non-action

A learner may avoid M by refusing to solve B. Require a correct alternative or justified escalation where the task permits it.

### False-positive benchmark dynamics

For review tasks, prior issue exposure may increase findings everywhere. Include clean boundary probes where appropriate.

## 13. Preregistration checklist

Freeze:

- exact A and B task IDs;
- method M;
- changed applicability or causal condition;
- correct alternative behaviour;
- boundary and misuse projections;
- acquisition-success projection;
- arm definitions;
- consolidation instruction;
- repetitions;
- model and compute configuration;
- inclusion rules;
- planned secondary conditional analysis;
- report template.

## 14. Protocol success criteria

The protocol is valid when:

1. boundary behavior is directly observable;
2. cold and exposed arms complete the same probe;
3. learner-state differences are exact and isolated;
4. inappropriate method reuse can be separated from generic failure;
5. structured and raw-history treatments are comparable;
6. the result can honestly show positive boundary learning, no effect, or negative transfer.

## 15. Required report

Include:

- why A and B form an applicability boundary;
- method M and its real preconditions;
- arm diagram;
- acquisition success by repetition;
- cold and focal boundary outcomes;
- familiar-method misuse events;
- paired effects;
- memory artifacts and whether they recorded applicability conditions;
- false-positive and non-completion diagnostics;
- cost;
- validity status;
- interpretation of any negative transfer.
