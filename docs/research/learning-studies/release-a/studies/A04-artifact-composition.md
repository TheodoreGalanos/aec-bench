# A04 — Artifact Skill Composition Study Protocol

**Status:** Proposed research protocol
**Release:** Learning Studies Release A
**Depends on:** LS-01A through LS-04A and a reviewed multi-source composition relation
**Primary question:** Can separately acquired components be combined in a novel artifact task?
**Claim mode:** Controlled learning comparison

## 1. Purpose

Test whether prior experiences produce reusable components rather than one monolithic task-specific trajectory.

The target probe must require at least two identifiable components that are acquired separately and then coordinated under a new task structure.

The protocol distinguishes:

- general familiarity;
- acquisition of component A;
- acquisition of component B;
- novel composition of A and B;
- order effects;
- integration failure despite correct components.

## 2. Research question

> Does prior experience with components A and B improve performance on a probe that requires their novel coordination, beyond the benefit of either component alone?

Secondary questions:

- Are both components retrieved?
- Does structured memory preserve applicability conditions for each?
- Is integration itself the bottleneck?
- Does acquisition order matter?
- Does raw history support composition as effectively as explicit consolidation?

## 3. Required task set

### Acquisition task A

Exercises component method or skill A in a context where A is central and independently assessable.

### Acquisition task B

Exercises component method or skill B in a context where B is central and independently assessable.

### Composition probe C

Requires both A and B in a novel coordination.

C must not be:

- a literal concatenation of A and B instructions;
- solvable to full credit through A alone;
- solvable to full credit through B alone;
- an exact worked example present in acquisition feedback;
- so difficult that cold and all partial arms floor.

### Candidate areas for repository audit

One promising mechanical sequence to review is:

```text
pump-head-calculation
+
pump-power-calculation
→
pump-power-efficiency or another integrated pump-sizing task
```

Other candidates may combine:

- load determination with capacity checking;
- mass balance with chemical dosing;
- hydraulic calculation with compliance assessment;
- two document-review subskills in one coordinated submission.

These names are candidate task families, not an assertion that current BRIEFs and verifiers already satisfy the composition requirements.

## 4. Composition relation

The `LearningFamilySpec` relation must declare:

```text
purpose: composition
sources: A and B
target: C
component claims: what A contributes and what B contributes
changed dimensions: novel coordination or target context
invariant claims: each component remains valid in C
```

Domain review must identify:

- the observable sub-result attributable to A;
- the observable sub-result attributable to B;
- the integration decision that connects them;
- applicability or unit conversions that could make naïve concatenation wrong.

## 5. Required outcome projections

C’s task owner must provide:

### `component-a-correct`

Whether C’s A-derived sub-result or decision is correct.

### `component-b-correct`

Whether C’s B-derived sub-result or decision is correct.

### `integration-correct`

Whether the components are coordinated correctly.

### `composition-outcome`

The final task-owned score or correctness projection for the complete C result.

All are behavioural projections over submitted artifacts or declared calculations. Do not infer component use from chain-of-thought phrasing.

## 6. Primary study arms

Use one common model, client, agent, compute policy, C probe, and consolidation operation.

### Arm C0 — Cold composition

```text
C
```

Treatment: `reset`

### Arm E-A — A only

```text
A
→ feedback
→ consolidate
→ C
```

Purpose: estimate A’s selective contribution and diagnose whether C is largely solvable through A.

### Arm E-B — B only

```text
B
→ feedback
→ consolidate
→ C
```

Purpose: estimate B’s selective contribution.

### Arm E-AB — A then B

```text
A
→ feedback
→ consolidate
→ B
→ feedback
→ consolidate
→ C
```

### Arm E-BA — B then A

```text
B
→ feedback
→ consolidate
→ A
→ feedback
→ consolidate
→ C
```

Purpose: expose order and recency effects.

### Optional Arm E-AB-Raw

```text
A
→ public history
→ B
→ public history
→ C
```

Purpose: compare raw episodic access with structured component memory.

## 7. Consolidation design

Use one structured-memory format that permits separate component entries and a later integration section.

The consolidation instruction after A or B should record:

- method;
- inputs and outputs;
- units and transformations;
- applicability conditions;
- checks;
- known failure modes;
- how the result may serve as input to another method.

It must not name C or provide a target-specific workflow.

A second consolidation after the other component may update the same memory. The state transition must show whether the first component was preserved, overwritten, or revised.

## 8. Measurements

### Basic composition gain

```text
E-AB on C − C0 on C
E-BA on C − C0 on C
```

using `composition-outcome`.

### Component selectivity

Expected diagnostic pattern:

```text
E-A improves component-a-correct more than component-b-correct
E-B improves component-b-correct more than component-a-correct
```

This is not an acceptance threshold unless preregistered, but it helps establish that the acquisition tasks affected the intended components.

### Incremental composition value

```text
E-AB − E-A
E-AB − E-B
```

and the equivalent for E-BA.

### Descriptive synergy

```text
composition synergy = combined-arm mean − max(A-only mean, B-only mean)
```

Report this as descriptive unless the study includes sufficient matched comparisons and a preregistered analysis.

### Integration effect

Compare `integration-correct` across all arms.

A+B component correctness without integration correctness indicates storage without composition.

### Order effect

```text
E-AB − E-BA
```

Report on all four projections.

## 9. Evidence supporting a composition interpretation

A strong composition result has several converging properties:

1. Combined acquisition improves the full C outcome over cold.
2. Combined acquisition improves over A-only and B-only arms.
3. A-only and B-only arms selectively improve their corresponding component projections.
4. Both component projections and integration projection improve in the combined arm.
5. Memory evidence retains both components rather than replacing one.
6. The target task was not exposed during acquisition or consolidation.

The protocol should not call a result “composition” merely because E-AB beats cold on one scalar.

## 10. Repetitions and order

- one repetition for plumbing;
- three per arm for pilot calibration;
- at least five per arm for a claim-bearing campaign;
- ten preferred if order effects are large.

E-AB and E-BA are required in the claim-bearing campaign unless domain reasoning proves order is structurally meaningful and the study is explicitly about one order.

Interleave matched arm runs by repetition.

## 11. Validity requirements

- A, B, and C are frozen before campaign start;
- C is probe-only;
- all arms execute the exact same C instance;
- A and B feedback do not expose C;
- outcome projections are fixed and task-owned;
- A-only and B-only arms use the same consolidation format as combined arms;
- learner-state channels and budgets are matched;
- probe state is discarded;
- acquisition order is the only difference between E-AB and E-BA;
- no target-specific prompt or skill is added manually.

## 12. Threats and diagnostics

### Target is simple concatenation

If C merely asks for the independent outputs of A and B, the study tests retrieval of two memories, not integration. Require an explicit integration decision.

### One component dominates

If A-only or B-only reaches ceiling, C is not a useful composition probe.

### Unequal acquisition difficulty

Report A and B acquisition performance. Consider balanced variants, but do not post hoc replace tasks after seeing composition results.

### Memory overwrite

Inspect state lineage after the second consolidation. A recency effect may explain order sensitivity.

### Unit and interface mismatch

A genuine composition task often requires translating outputs from one component into inputs for another. Preserve these interface checks in the task-owned integration projection.

### General intelligence rather than learning

Cold competence remains essential. The claim concerns the **difference caused by acquisition**, not whether the model can solve C at all.

## 13. Preregistration checklist

Freeze:

- exact A, B, and C task IDs;
- component and integration claims;
- four required projections;
- all arms and order conditions;
- feedback view;
- consolidation instruction and memory format;
- model and compute configuration;
- repetitions;
- primary and diagnostic comparisons;
- inclusion rules;
- target headroom assessment.

## 14. Protocol success criteria

The protocol is a valid instrument when:

1. A, B, and integration are separately observable in C;
2. cold, A-only, B-only, A+B, and B+A arms run under matched conditions;
3. target content remains hidden during acquisition;
4. learner state shows whether both components survived;
5. reports can distinguish component retrieval from integration;
6. zero, negative, or order-sensitive results remain interpretable.

Positive composition is not required for software acceptance.

## 15. Required report

Include:

- component map and target integration point;
- exact family relation;
- arm sequence diagram;
- acquisition performance on A and B;
- all four C projections by repetition and arm;
- combined versus partial-arm effects;
- order effect;
- memory lineage after each consolidation;
- cold competence;
- cost and token use;
- validity and exclusions;
- interpretation of whether evidence supports composition, mere retrieval, or neither.
