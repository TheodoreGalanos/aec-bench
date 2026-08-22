# A03 — Artifact Retention and Interference Study Protocol

**Status:** Proposed research protocol
**Release:** Learning Studies Release A
**Depends on:** LS-01A through LS-04A, a reviewed transfer family, and suitable neutral/interference tasks
**Primary question:** Does a learning effect survive intervening experience, and can later experience distort it?
**Claim mode:** Controlled learning comparison

## 1. Purpose

Move beyond immediate transfer.

A learner may perform better on the next related task while still failing to preserve useful knowledge across an extended sequence. Conversely, a later superficially similar task may overwrite or distort the earlier lesson.

This protocol separates:

- immediate transfer;
- retained gain after neutral intervening experience;
- retention decay;
- interference caused by a conflicting later experience.

## 2. Research questions

Primary:

> After acquisition and explicit consolidation, does the learner retain a useful effect on a delayed structurally related probe?

Secondary:

- How much does performance change between immediate and delayed probes?
- Does an unrelated filler task affect retention differently from a structurally similar but conflicting task?
- Does structured memory resist interference better than raw history?
- Does the learner revise memory appropriately when the interfering experience is genuinely informative?

## 3. Required task set

The protocol requires five roles.

### Acquisition A

Teaches or exercises method M.

### Immediate probe P1

A probe-only structural-transfer member governed by M.

### Delayed probe P2

A second probe-only member also governed by M.

P1 and P2 must be pre-calibrated as meaningfully comparable. They need not be identical, but they must share:

- governing method;
- outcome projection;
- broad difficulty band;
- tool and output expectations.

### Neutral intervening task U

An artifact task that:

- consumes a comparable execution slot and approximate budget;
- does not use M;
- does not teach a conflicting rule;
- does not expose P2.

### Interference task I

A task that is deliberately relevant enough to compete with the earlier lesson, for example:

- similar surface with a changed governing method;
- a conflicting applicability condition;
- a related procedure with a different stopping rule.

I must be domain-reviewed. An arbitrary difficult task is not an interference manipulation.

## 4. Probe counterbalancing

P1 and P2 may differ subtly despite calibration.

For the claim-bearing campaign, use two predeclared blocks:

```text
Block X: P1 immediate, P2 delayed
Block Y: P2 immediate, P1 delayed
```

The study compiler does not branch dynamically. Author two finite study plans or two fixed arm variants and combine them in assessment.

Report block effects. Do not hide systematic probe asymmetry inside “retention decay.”

A three-repetition pilot may use one order to control cost, but it cannot support a strong decay interpretation.

## 5. Learner treatment

The primary protocol uses `structured-memory`.

A secondary protocol may repeat the same design with `raw-history`.

Do not mix treatments within the primary retention estimate.

Consolidation occurs once after A using a fixed operation that records:

- method M;
- applicability conditions;
- checks;
- acquisition errors or uncertainty.

After the interfering task, the primary interference arm does **not** reconsolidate unless the research question explicitly concerns memory revision. Otherwise, the experiment tests passive interference on the existing learned state.

A separate revision study may later add:

```text
I → feedback → reconsolidation → P2
```

## 6. Study arms

### Arm C0 — Cold immediate

```text
P1
```

Purpose: cold competence on the immediate probe.

### Arm C1 — Cold delayed with neutral exposure

```text
U
→ P2 with reset learner state
```

Purpose: cold comparator for retained gain while matching the presence of an intervening task.

### Arm C2 — Cold delayed with interference exposure but reset

```text
I
→ P2 with reset learner state
```

Purpose: detect ordering or provider effects from running I when its learner state is not carried.

### Arm E0 — Immediate transfer

```text
A
→ release public evaluation
→ consolidate
→ P1, discard probe state
```

Purpose: establish the immediate learning effect.

### Arm E1 — Neutral retention

```text
A
→ release public evaluation
→ consolidate
→ P1, discard probe state
→ U without adding U to persistent learner state
→ P2, discard probe state
```

The neutral task is executed as a non-committing intervening experience. This preserves the learned state while introducing elapsed interactions and model use.

### Arm E2 — Interference

```text
A
→ release public evaluation
→ consolidate
→ P1, discard probe state
→ I with committed permitted learner-state changes
→ P2, discard probe state
```

The exact state channels I may alter must be preregistered. For the primary study, I may add raw episode history but may not run an explicit consolidation operation.

### Optional Arm E3 — Interference with memory revision

```text
A
→ consolidate
→ P1
→ I
→ release I feedback
→ reconsolidate
→ P2
```

This asks whether explicit revision protects against interference or appropriately updates an obsolete rule.

## 7. State semantics

The immediate probe is non-committing. E1 and E2 continue from the same state that existed before P1.

This is critical:

```text
learned state
  ├── temporary P1 candidate, discarded
  └── intervening experience begins from unchanged learned state
```

The recorder must prove byte-level or artifact-level identity of the committed pre-P1 and post-discard state.

## 8. Outcome projections

Use the same primary higher-is-better projection on P1 and P2.

Required:

- substantive task correctness;
- canonical validity;
- acquisition performance on A.

Recommended secondary projections:

- method selection;
- applicability judgment;
- error type;
- unnecessary checks;
- model usage and cost.

For I, record whether the learner encountered the intended conflicting evidence. Do not assume interference occurred simply because the task ran.

## 9. Measurements

### Immediate transfer gain

```text
E0 on P1 − C0 on P1
```

### Retained gain

```text
E1 on P2 − C1 on P2
```

This is the primary retention measure.

### Retention decay

Within exposed conditions:

```text
E0 or E1 immediate performance − E1 delayed performance
```

Interpret only after counterbalancing P1/P2.

### Interference effect

```text
E2 on P2 − E1 on P2
```

Normalised so positive means the interference arm performed better. A negative effect indicates harmful interference.

### Reset interference control

```text
C2 on P2 − C1 on P2
```

A substantial difference suggests the task order or provider conditions matter even without carried learner state.

### Optional revision effect

```text
E3 on P2 − E2 on P2
```

## 10. Operational definition of delay

Release A measures delay through intervening experiences, not wall-clock waiting.

Report:

- number of intervening trials;
- model calls;
- tokens;
- total interaction cost;
- sequence length.

Do not describe one filler task as long-term retention. This is an initial controlled retention substrate.

Later lifecycle and world studies will supply more realistic temporal delay.

## 11. Repetitions

- one repetition for plumbing;
- three per arm for pilot calibration;
- at least five per arm and counterbalance block for claim-bearing use;
- ten preferred if the interference effect is noisy.

Interleave matched arm runs by repetition and block.

## 12. Validity requirements

- P1 and P2 relation and calibration are frozen before the campaign;
- probe state is discarded;
- U does not expose or exercise M materially;
- I has a reviewed conflict with the earlier lesson;
- cold delayed arms experience matched sequence length where feasible;
- the same learner channels are available across E0, E1, and E2 until the deliberate intervention;
- no feedback from P1 reaches later state;
- P2 remains probe-only;
- assessment reports probe-order block.

## 13. Threats and diagnostics

### Probe asymmetry

Counterbalance and report block effects.

### Neutral task is not neutral

Audit U for shared concepts, procedures, and terminology.

### Interference task simply adds useful breadth

A positive E2 effect may be legitimate generalisation rather than failed interference. Inspect task relation and learner artifacts.

### No actual acquisition

Report A performance and use a preregistered conditional secondary analysis only.

### Memory cannot change during I

If treatment permissions freeze all relevant state, the study tests retrieval after distraction, not interference. State clearly which channels I can alter.

### Context-window confound

Artifact trials use fresh contexts; persistence must come through declared learner artifacts. Verify no provider conversation persists implicitly.

## 14. Preregistration checklist

Freeze:

- A, P1, P2, U, and I task IDs;
- transfer and interference relations;
- P1/P2 counterbalance blocks;
- treatment and channel permissions;
- feedback and consolidation operations;
- all arms;
- primary projection;
- repetitions;
- method for combining blocks;
- conditional analyses;
- model and compute configuration.

## 15. Protocol success criteria

The protocol is successful when it can distinguish:

- immediate gain;
- delayed gain relative to cold;
- change between immediate and delayed performance;
- effect of a conflicting experience relative to neutral delay;
- reset/order artifacts;
- exact learner state present at every point.

No positive retained gain is required for software acceptance.

## 16. Required report

Include:

- full sequence diagram for every arm;
- task relationship review;
- P1/P2 calibration and block effects;
- state lineage around the discarded immediate probe;
- immediate, delayed, cold, and interference outcomes by repetition;
- paired effects;
- acquisition and interference-task performance;
- learner memory before and after I;
- cost and interaction count;
- exclusions and validity;
- limitations of experience-count delay.
