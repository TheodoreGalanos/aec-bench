# AEC-Bench Learning Studies Programme

**Class:** Research
**Status:** Proposed
**Scope:** Learning-study infrastructure and environment integration up to, but excluding, RL or model-weight training
**Programme prefix:** `LS` — Learning Studies
**Repository basis:** Current `main`, following the recent functional composition work across artifact tasks, lifecycles, worlds, and the meta-harness.

---

## 1. Executive decision

AEC-Bench should add an optional, runtime-neutral **Learning Studies** layer under `experimentation/`.

The layer will:

1. Arrange existing trials into deliberately related sequences.
2. Control what learner state may persist between those trials.
3. Control what feedback becomes visible, and when.
4. Record changes to learner state without interpreting its contents.
5. Compare exposed learners against matched cold controls.
6. Compute named paired differences for structural transfer, applicability, composition, retention, and interference. Cost or learning-efficiency analysis remains study-owned secondary analysis.
7. Reference task-owned causal and hierarchical evidence where environments can provide it.
8. Produce normal study artefacts and reports that may later support RL research, without defining an RL training contract now.

It will **not** become another execution family.

Artifact tasks, finite lifecycles, and Interactive Worlds already have deliberately separate execution semantics. They join at planning, evidence, evaluation, and experimentation rather than through one universal runtime. The learning layer should preserve that architecture and compose their normal `TrialRecord` outputs.

```text
Existing execution families

Artifact task ────────┐
Finite lifecycle ─────┼──> TrialRecord
Interactive world ────┘

                              │
                              ▼

Optional Learning Studies layer

related experiences
→ controlled learner continuity
→ controlled feedback
→ later probes
→ study-level learning assessment
```

The central design rule is:

> **A trial remains the unit of execution. A learning study becomes the unit of learning analysis.**

---

# 2. Why this sequence is correct

The proposed progression is not merely an implementation convenience. Each environment family introduces a distinct learning problem.

## Stage A — Artifact tasks

Artifact tasks provide the cleanest place to establish:

- acquisition versus probe tasks;
- matched cold controls;
- semantic relations between tasks;
- external-memory treatments;
- structured versus unstructured consolidation;
- transfer, boundary, composition, and retention metrics.

They minimise environmental complexity while pressure-testing whether the basic study design is valid.

## Stage B — Finite lifecycles

Lifecycles add:

- temporal staging;
- checkpoints;
- progressive release of evidence;
- feedback timing;
- fresh versus persistent sessions;
- revision and rework;
- progressive withdrawal of scaffolding;
- phase-level analysis.

They teach the common substrate how learning unfolds inside and across structured episodes.

## Stage C — Bounded worlds

The dam-seepage world adds:

- partial observability;
- epistemic actions;
- authoritative state transitions;
- evidence released through action;
- causal and applicability boundaries;
- action-level effects.

It is small enough that causal relations remain interpretable.

## Stage D — Persistent worlds

The pump-stewardship world adds:

- multiple sessions within one journey;
- cross-journey learner continuity;
- persistent world consequences;
- host-owned interventions;
- authority boundaries;
- resources and liabilities;
- skill composition;
- retention and interference;
- counterfactual branches.

It should be integrated only after the simpler layers have clarified what belongs in the common substrate.

## Extraction gates

After each environment family, an explicit substrate revision PRD will decide:

- which concepts have proven common;
- which remain environment-owned;
- which speculative fields should be deleted;
- which contracts may now be stabilised;
- what the next environment genuinely requires.

This follows the repository’s existing architectural preference for functional composition and owner-local semantics rather than speculative universal abstractions. The current meta-harness is a useful precedent: it is runtime-neutral because callers supply evaluation and refinement functions rather than because the core understands every runtime.

---

# 3. Current architectural fit

AEC-Bench already has most of the lower substrate required for learning studies:

| Existing capability | Present ownership |
|---|---|
| Trial planning and deterministic trial identity | Shared planning |
| Artifact execution | Artifact runtime |
| Checkpoint coordination | Lifecycle runtime |
| Actor observation and typed action boundaries | World owner |
| Authoritative transitions | World owner |
| Task evaluation | Task owner |
| Trial evidence references | Shared contracts |
| Optional typed evidence extensions | Extension artefacts |
| Study and qualification policy | `experimentation/` |
| Prompt and skill evolution | Meta-harness and evolution systems |

The canonical `TrialRecord` already supports references to optional extension artefacts, allowing lifecycle- or study-specific evidence to remain outside the shared trial schema. Authority evidence is likewise referenced rather than copied into a universal record.

This means the learning programme does **not** need to:

- enlarge `TrialRecord` into a career history;
- copy world state into shared records;
- establish one global action type;
- merge artifact, lifecycle, and world execution;
- make task definitions aware of learning studies.

There is, however, an immediate vocabulary collision. The repository currently has a lifecycle “transfer” study that describes fixed-candidate holdout generalisation and explicitly states that cross-run learning is unsupported. That should be renamed before introducing actual learning transfer.

---

# 4. Vocabulary

The programme should use the following terms consistently.

| Term | Definition |
|---|---|
| **Trial** | One existing AEC-Bench execution resulting in one normal `TrialRecord`. |
| **Experience** | A trial as positioned within a learning study. “Experience” describes its study role, not a new runtime. |
| **Learning study** | A controlled sequence of experiences used to determine whether prior experience changes later behaviour. |
| **Arm** | One treatment or control sequence within a study. |
| **Acquisition experience** | An experience intended to provide useful knowledge or practice. |
| **Practice experience** | An additional related experience before a probe. |
| **Interference experience** | An experience inserted to test forgetting, conflict, or overgeneralisation. |
| **Probe** | An experience used to measure behaviour after prior exposure. |
| **Cold control** | The same probe completed by an otherwise matched learner without the relevant acquisition experience. |
| **Learner state** | Any permitted state carried between experiences: context, workspace, memory artefacts, or harness artefacts. |
| **Learner transition** | A recorded change from one learner-state snapshot to another. |
| **Feedback release** | A deliberate act of making selected result evidence visible to the learner. |
| **Consolidation** | An explicit between-experience operation that interprets visible experience and may update permitted learner state. |
| **Structural transfer** | Improvement on a changed task caused by prior experience with the same relevant underlying structure. |
| **Boundary judgment** | Correctly withholding or changing a familiar method when its applicability conditions no longer hold. |
| **Composition** | Combining previously encountered components into a novel solution. |
| **Retention** | Preserving useful behaviour after delay or intervening experiences. |
| **Interference** | Degradation or distortion of prior competence caused by later experience. |
| **Generalisation** | Performance by a fixed learner on a changed task, without a prior-experience comparison. |
| **Learning effect** | A controlled difference between an exposed learner and a matched cold control. |

The critical distinction is:

```text
GENERALISATION

fixed learner → changed task
```

versus:

```text
LEARNING TRANSFER

acquisition experience
→ permitted learner update
→ changed probe

compared with

same initial learner
→ changed probe cold
```

---

# 5. Architectural invariants

These invariants apply across every PRD.

## 5.1 Existing execution remains authoritative

Every environment continues to execute through its existing path:

- artifact task runner;
- lifecycle runner;
- world journey runner.

The learning layer supplies study context and receives normal records. It does not reinterpret execution semantics.

## 5.2 Task semantics remain task-owned

The common layer may say:

> “Experience B is intended to preserve the same governing mechanism while changing presentation.”

It may not define what that governing mechanism is.

The task or study author remains responsible for the domain claim.

## 5.3 World state and learner state remain separate

A persistent world and a persistent learner are independent dimensions.

```text
World state:
physical state, resources, liabilities, time, host actions

Learner state:
context, notes, memory, skills, harness artefacts
```

Neither should be smuggled into the other.

## 5.4 Evidence, feedback, and reward are distinct

- **Evidence** is what the task or world records.
- **Feedback** is the selected evidence released to the learner.
- **Measurement** is what the study computes.
- **Reward** is outside the present programme.

A rich evidence item should not automatically become a dense reward.

## 5.5 Learner state may be opaque, but not invisible

The common layer does not inspect or understand learner-state contents.

It does require:

- an identity for each snapshot;
- a parent-state reference;
- one artefact reference for the persisted snapshot;
- a receipt for every committed or discarded transition.

## 5.6 Probes are isolated

By default:

- probe feedback remains hidden until scoring is complete;
- probe-generated state is discarded;
- probe verifier data cannot enter later learner state;
- a study must explicitly opt into post-probe continuation.

## 5.7 Controlled learning claims require controls

A sequence without a cold arm can describe behaviour over time.

It cannot claim that prior experience caused improvement.

## 5.8 No universal action or phase hierarchy

Tasks may optionally project:

- phases;
- decisions;
- actions;
- effects;
- subgoals.

The common substrate may reference these projections but does not define their domain meaning.

## 5.9 Model weights remain fixed

Version 1 permits learning through:

- carried context;
- persistent workspace;
- structured memory;
- explicit prompt or skill updates.

It does not permit model-weight updates.

Every report must identify the adaptation mechanism used.

## 5.10 No unnecessary version or hash machinery

The programme should reuse:

- normal task references;
- existing run and trial identity;
- ordinary artefact publication;
- Git history.

It should not introduce package hashes, content-ID matrices, or per-component version variables merely to describe a study.

---

# 6. Target architecture

```text
LearningStudySpec
  │
  │ author intent:
  │ experiences, arms, relations,
  │ continuity, feedback, measurements
  ▼
compile_learning_study(...)
  │
  │ resolves exact existing tasks,
  │ profiles, planned trials and repetitions
  ▼
LearningStudyPlan
  │
  ├─────────────────────────────────────────────┐
  │                                             │
  ▼                                             ▼
Control arm                                Exposure arm
initial learner state                     cloned initial learner state
  │                                             │
  ▼                                             ▼
existing trial runner                     acquisition trial
  │                                             │
  ▼                                             ▼
TrialRecord                                TrialRecord
                                                │
                                                ▼
                                        feedback release
                                                │
                                                ▼
                                         consolidation
                                                │
                                                ▼
                                          probe trial
                                                │
                                                ▼
                                            TrialRecord
  │                                             │
  └──────────────────────┬──────────────────────┘
                         ▼
                study-level assessor
                         │
                         ▼
       RecordedStudyExecution + LearningStudyAssessment
```

## 6.1 Layers

### Layer 1 — Existing execution owners

Artifact tasks, lifecycles, and worlds remain unchanged wherever possible.

### Layer 2 — Thin environment adapters

Each adapter knows how to:

- initialise an appropriate learner treatment;
- execute one existing planned trial;
- snapshot supported learner-state channels;
- expose permitted task-owned feedback;
- apply an explicit consolidation operation.

### Layer 3 — Runtime-neutral learning-study core

The core knows:

- study order;
- arms;
- state lineage;
- feedback visibility;
- study validity;
- comparisons.

It does not know engineering or world semantics.

### Layer 4 — Task-owned learning evidence

Tasks and worlds may optionally emit additional analytical evidence through existing extension mechanisms.

### Layer 5 — Cross-family assessment and reporting

Study-level reports distinguish:

- competence;
- learning gain;
- negative transfer;
- retention;
- interference;
- composition;
- cost and efficiency.

---

# 7. Core conceptual model

## 7.1 `LearningStudySpec`

The authored research design.

```text
LearningStudySpec
  study_id
  title
  research_question
  fixed agent and compute configuration
  repetitions
  experiences
  arms
  relations
  measurements
```

The protocol form contains family-member selectors and author intent. Loading
resolves these selectors to exact task IDs. Compilation then creates final
trial identities.

## 7.2 `LearningStudyPlan`

The compiled, executable plan.

```text
LearningStudyPlan
  study_run_id
  resolved experiences
  exact task references
  ordinary PlannedTrial values
  arm execution order
  paired repetition identifiers
  learner treatments
  feedback schedule
  expected measurements
```

The plan is immutable once execution starts.

The existing planning API already provides ordinary planned-trial values and allows caller-owned extensions, making it a suitable source rather than something to replace.

## 7.3 Study steps

An arm contains an ordered sequence of three step kinds.

### Experience step

Runs one normal trial.

```text
RunExperience
  experience_id
  planned_trial
  commit_post_state: true | false
```

### Feedback-release step

Makes selected host-held evidence visible.

```text
ReleaseFeedback
  source_experience
  feedback_view_id
```

Not every environment must support every view.

### Consolidation step

Allows the adapter to apply one bounded learner-state operation.

```text
Consolidate
  feedback_step_ids
  operation_id
```

Consolidation is not automatically a benchmark trial. It produces a learner-transition receipt.

## 7.4 Learner continuity

The common contract does not identify learner-state channels. Adapters define
the channel layout, permissions, and treatment behavior. The common runtime
sees only opaque copy-on-write snapshots and explicit transition identity.

| Channel | Possible policy |
|---|---|
| Conversation context | reset, carry |
| Workspace | reset, carry all, carry allowlist |
| Memory artefacts | absent, raw history, structured |
| Harness artefacts | fixed, explicit update |
| Model weights | fixed |

A treatment may combine channels. For example:

```text
structured-ledger treatment

conversation: reset
workspace: carry allowlist
memory artefacts: structured
harness artefacts: fixed
model weights: fixed
```

## 7.5 Learner state lineage

```text
LearnerStateRef
  state_id
  arm_run_id
  parent_state_id
  created_after_step
  treatment_id
  artefact_ref
```

```text
LearnerTransitionReceipt
  state_before
  state_after
  operation
  visible_feedback_refs
  committed
```

A study may discard a state transition, especially after a probe.

## 7.6 Experience relations

Relations belong to the study, not the task.

```text
ExperienceRelation
  source_experiences
  target_experience
  purpose
  invariant_claims
  changed_dimensions
```

### Relation purposes

- `transfer`
- `boundary`
- `composition`

Retention and interference are sequence roles and named measurement questions.
They do not require separate task-relation purposes.

### Changed dimensions

- `surface`
- `parameter`
- `causal`
- `applicability`
- `component`

Examples:

```text
A → B

purpose: transfer
invariant:
  governing load-path method
changed:
  surface, parameter
```

```text
A → C

purpose: boundary
invariant:
  superficial asset presentation
changed:
  causal, applicability
```

For composition:

```text
[A, B] → D

purpose: composition
invariant:
  reusable component methods from A and B
changed:
  novel coordination requirement
```

## 7.7 Study results

```text
RecordedStudyExecution
  study_run_id
  arm_results
  trial_ids

LearningStudyAssessment
  study_run_id
  measurement_results
```

State, feedback, transition, and step evidence remains in its own persisted
records. Assessment retains included pairs, excluded repetitions, validity,
compact means, and diagnostics. These records reference existing `TrialRecord`
values. They do not duplicate them.

---

# 8. Claim and measurement discipline

## 8.1 Evidence-derived comparison validity

The authored protocol does not select a claim mode. The assessor derives one
of `controlled`, `descriptive_only`, or `invalid` from the compiled comparison
shape and explicit execution evidence.

A controlled learning comparison requires:

- a matched cold control;
- the same initial model and harness;
- isolated learner state;
- the same probe task and evaluation;
- matched repetition conditions;
- only the declared treatment differing materially.

It reports an estimated learning effect under those controls.

A within-arm or treatment-to-treatment comparison is descriptive. A failed
isolation, probe, lineage, or hidden-evidence condition is invalid. The
substrate should avoid automatically using stronger causal language.

## 8.2 Named paired differences

The common contract has one paired-difference shape. `measurement_id` and the
selected task-owned projection state the research meaning. Transfer,
retention, interference, composition, and boundary formulas remain protocol
semantics rather than common enum values.

Let:

- \(S_E(P)\) be exposed-arm performance on probe \(P\);
- \(S_C(P)\) be matched cold-control performance;
- \(S_D(P)\) be delayed performance;
- \(S_I(P)\) be performance after interference.

### Transfer gain

\[
G_{\text{transfer}} = S_E(P) - S_C(P)
\]

### Retained gain

\[
G_{\text{retained}} = S_D(P) - S_C(P)
\]

### Retention decay

\[
D_{\text{retention}} = S_E(P_{\text{immediate}}) - S_D(P)
\]

### Interference effect

\[
I = S_I(P) - S_E(P_{\text{matched without interference}})
\]

### Composition gain

\[
G_{\text{composition}}
=
S(P_{\text{composition}} \mid A,B)
-
S(P_{\text{composition}} \mid \text{cold})
\]

### Boundary effect

The study must use a task-owned measure of inappropriate familiar-method application.

```text
boundary success:
  familiar method correctly withheld or adapted

negative transfer:
  prior exposure increases inappropriate familiar-method use
```

### Learning efficiency

\[
E_{\text{learning}}
=
\frac{G_{\text{transfer}}}
{\text{acquisition interactions, tokens, cost, or trials}}
\]

Efficiency is secondary to validity and should never hide absolute performance.
It is not a Release A common measurement type. A study can derive it from
pair-level results and execution-owner token, interaction, trial, or cost
evidence when that evidence exists.

## 8.3 Named outcome projections

The common assessor must not parse arbitrary task-specific evaluation fields.

Instead, each study declares named projections such as:

```text
canonical_reward
canonical_validity
calculation_correctness
evidence_quality
safe_operational_outcome
boundary_judgment
```

The relevant evaluation owner supplies the projection.

## 8.4 Stochastic controls

Controlled studies should support:

- paired repetition identifiers;
- explicit evidence that isolated initial learner states are equivalent;
- randomised or interleaved arm order;
- multiple seeds or repetitions;
- ceiling and floor diagnostics.

A single exposed run and a single cold run may be exploratory, but should not support strong conclusions.
Uncertainty analysis remains study-owned until observed repetition counts and a
declared method justify it.

---

# 9. Programme roadmap

| PRD | Title | Main outcome |
|---|---|---|
| **LS-00** | Programme Boundary, Vocabulary, and Semantic Cleanup | Clear ownership and unambiguous terminology |
| **LS-01** | Runtime-Neutral Learning Study Core | Functional study planner and runner |
| **LS-02** | Evidence, Learner-State Lineage, Validity, and Metrics | Trustworthy and resumable study records |
| **LS-03** | Artifact Learning Families and Relation Authoring | Semantic relationships over existing tasks |
| **LS-04** | Artifact Learning Runner and Pilot Studies | First controlled learning results |
| **LS-05** | Substrate Revision Gate A | Task-derived simplification and stabilisation |
| **LS-06** | Lifecycle Learning Adapter and Continuity Treatments | Complete lifecycles as related experiences |
| **LS-07** | Lifecycle Phase Evidence, Feedback, and Scaffolding Studies | Staged and hierarchical learning analysis |
| **LS-08** | Substrate Revision Gate B | Lifecycle-derived common additions |
| **LS-09** | Bounded-World Learning and Dam-Seepage Studies | Epistemic actions and causal boundaries |
| **LS-10** | Substrate Revision Gate C: Action and Effect Evidence | Minimal cross-environment decision evidence |
| **LS-11** | Persistent-World and Cross-Journey Pump Learning | Separate world and learner continuity |
| **LS-12** | Pump Counterfactuals, Composition, Retention, and Interference | Long-horizon causal learning studies |
| **LS-13** | Cross-Family Reporting, Curricula, CLI, and Release | Usable end-to-end learning-study product |

---

# PRD LS-00 — Programme Boundary, Vocabulary, and Semantic Cleanup

## Problem

AEC-Bench has the ingredients for learning studies but lacks a single architectural boundary for them.

It also currently uses “transfer” to describe fixed-candidate holdout generalisation. Introducing actual prior-experience transfer without cleaning this terminology would make results ambiguous. The existing lifecycle study explicitly identifies itself as descriptive holdout generalisation and says cross-run learning is unsupported.

## Decision

Create `experimentation.learning_studies` as the owner of:

- study policy;
- experience relations;
- arm and control design;
- learner continuity declarations;
- feedback schedules;
- study-level assessment;
- study reporting.

Execution owners remain unchanged.

## Required changes

### Rename current lifecycle transfer study

Rename:

```text
experimentation/lifecycle_studies/transfer.py
```

to:

```text
experimentation/lifecycle_studies/holdout_generalization.py
```

Rename its public values accordingly.

Delete the old names rather than adding compatibility aliases.

### Add architecture documentation

Document:

```text
task execution       owned by task/runtime
learning sequence    owned by experimentation
learner state        owned by adapter/treatment
learning evidence    owned by task, referenced by study
learning conclusion  owned by study assessor
```

### Establish terminology

Adopt the vocabulary in Section 4.

## Non-goals

- No runtime implementation.
- No new task fields.
- No changes to `TrialRecord`.
- No persistent learner state yet.
- No new scoring.

## Acceptance criteria

1. The architecture document distinguishes generalisation, adaptation, and learning transfer.
2. No public API uses “transfer” for the old holdout-generalisation study.
3. `experimentation.learning_studies` has a documented ownership boundary.
4. Task, lifecycle, and world packages do not import learning-study policy.
5. Architecture tests enforce the dependency direction.
6. No compatibility layer remains for deleted names.

---

# PRD LS-01 — Runtime-Neutral Learning Study Core

## Problem

AEC-Bench can execute collections of trials, but it cannot represent:

- acquisition and probe roles;
- treatment and cold arms;
- feedback-release steps;
- learner-state transitions;
- relations between experiences;
- study-level learning questions.

## Decision

Implement a small functional study core that composes caller-supplied operations, following the same broad architectural style as the runtime-neutral meta-harness.

## Public persisted contracts

Introduce only contracts that cross a persistence boundary:

```text
LearningStudySpec
LearningStudyPlan
LearnerStateRef
LearnerTransitionReceipt
StudyEvent
RecordedStudyExecution
LearningStudyAssessment
```

Runtime-only helper values should remain frozen dataclasses inside the owner package.

## Core API

Conceptually:

```python
def compile_learning_study(
    spec,
    resolve_experience,
    plan_trial,
) -> LearningStudyPlan:
    ...
```

```python
async def run_learning_study(
    *,
    plan,
    operations,
    observer=None,
    resume=None,
) -> LearningStudyExecution:
    ...
```

Callbacks keep the core independent of:

- artifact runtimes;
- lifecycle sessions;
- world actor endpoints;
- provider implementations;
- workspace formats.

## Study step model

Support three step kinds:

```text
RunExperience
ReleaseFeedback
Consolidate
```

Do not add loops, conditions, or adaptive branching in the first implementation.

An authored study is an explicit finite sequence.

## Arm isolation

Each arm receives a clone of the declared initial learner configuration.

The core must reject:

- shared writable workspace roots across arms;
- reused mutable state objects;
- duplicate trial IDs;
- undeclared feedback release;
- cross-arm parent-state references.

## Probe behaviour

`RunExperience` includes:

```text
commit_post_state: true | false
```

Default:

- acquisition: `true`;
- practice: `true`;
- interference: `true`;
- probe: `false`.

## Deterministic planning

Compilation resolves:

- exact task references;
- exact trial plans;
- arm order;
- repetition pairing;
- initial-state identities;
- expected measurements.

No task discovery occurs after a plan starts executing.

## Non-goals

- No metrics beyond structural validation.
- No persistence or resume yet.
- No environment-specific adapters.
- No adaptive curriculum.
- No mixed-family convenience dispatcher.
- No model-weight update.

## Acceptance criteria

1. A synthetic two-arm study can execute using a fake trial runner.
2. Both arms begin from equivalent but isolated learner states.
3. The exposure arm may acquire and consolidate before a shared probe.
4. The cold arm runs the same probe without acquisition.
5. Probe state is discarded by default.
6. Every experience returns one ordinary `TrialRecord`.
7. The core has no imports from artifact tasks, lifecycles, or worlds.
8. Invalid relation references and step ordering fail before execution.
9. Functional APIs do not require a universal runtime class hierarchy.

---

# PRD LS-02 — Evidence, Learner-State Lineage, Validity, and Metrics

## Problem

A learning result is uninterpretable unless the system can establish:

- what each learner had seen;
- what state persisted;
- what feedback was released;
- whether control and exposure arms were comparable;
- whether the probe remained isolated;
- whether execution resumed safely after interruption.

## Decision

Add append-only study events, learner-state lineage, study validity checks, and initial comparative metrics.

## Study artefacts

A completed study publishes:

```text
study-spec.json
study-plan.json
study-events.jsonl
study-result.json
optional learning-report.md
```

Learner-state contents remain in their normal artefacts and are referenced.

No parallel hash catalogue is introduced.

## Required study events

```text
study_started
arm_started
learner_initialised
learner_snapshotted
experience_started
experience_completed
feedback_released
consolidation_started
learner_transitioned
consolidation_completed
arm_completed
study_assessed
study_completed
```

Events record identity and references, not copied task payloads.

## Resume

A study may resume from its last valid event when:

- the compiled plan matches;
- all completed trial records are available;
- the latest committed learner-state snapshot is available;
- no expected step has conflicting output.

Completed steps are not rerun.

A half-finished state transition is discarded unless the adapter proves it committed atomically.

## Trial evidence

Task-owned learning evidence should use existing trial-extension mechanisms rather than new top-level `TrialRecord` fields. The trial record already permits typed extension references for optional subsystem evidence.

## Validity checks

### Plan validity

- all references resolve;
- experience roles are consistent with steps;
- measurements reference defined probes;
- composition relations have multiple sources;
- retention relations have an earlier acquisition;
- boundary relations declare the changed applicability or causal dimension.

### Execution validity

- every expected trial occurred once;
- returned task and trial identity match the plan;
- arm state remained isolated;
- state lineage is complete;
- feedback releases follow the declared schedule;
- hidden probe evidence was not released.

### Comparison validity

A controlled comparison requires:

- matched initial learner configuration;
- matched probe;
- matched evaluation;
- matched repetition pair;
- equivalent provider and budget policy unless deliberately varied;
- only declared treatment differences.

If these conditions fail, the result is downgraded to descriptive.

## Core metrics

Implement study-level calculation of:

- transfer gain;
- retained gain;
- retention decay;
- interference effect;
- composition gain;
- boundary effect;
- learning efficiency.

The study receives named scalar projections from the relevant evaluator. It does not inspect arbitrary nested task breakdowns.

## Acceptance criteria

1. A study can stop after any completed step and resume without rerunning it.
2. Missing learner-state ancestry invalidates the affected arm.
3. Releasing probe evaluation before scoring invalidates the learning comparison.
4. Unmatched probes produce descriptive results only.
5. Comparative metrics are computed by matched repetition pair.
6. Aggregate results retain per-pair values and uncertainty summaries.
7. No study evidence is copied into the core `TrialRecord`.
8. Existing records remain loadable without migration.

---

# PRD LS-03 — Artifact Learning Families and Relation Authoring

## Problem

AEC-Bench can generate or materialise task variations, but variation is currently mechanical rather than learning-semantic.

An axis can say:

```text
diameter = [300, 450, 600]
```

but not:

- whether diameter changes only difficulty;
- whether the governing method remains invariant;
- whether a later task is a transfer probe;
- whether a superficially similar task changes the correct method.

The current adaptation contract expresses axes and candidate derivation but does not encode what should transfer between variants.

## Decision

Add a study-owned `LearningFamilySpec` that overlays semantic relationships on existing tasks and generators.

Do not change task definitions or `VariationAxis` in this PRD.

## `LearningFamilySpec`

```text
family_id
description
member selectors
semantic dimensions
invariant claims
candidate relations
holdout policy
```

Member selectors may reference:

- explicit task IDs;
- generated family and variation predicates;
- task profiles;
- difficulty bands.

Compilation resolves them into exact task references.

## Semantic dimension roles

A family may annotate existing axes as:

- surface;
- parameter;
- causal;
- applicability;
- composition component.

These annotations are assertions by the study author. The compiler cannot infer their domain truth.

## Required relation patterns

The first release must express:

### Structural transfer pair

```text
same relevant method
different surface or parameters
```

### Applicability boundary pair

```text
familiar-looking presentation
changed governing condition
familiar method should not be copied
```

### Retention pair

```text
acquisition
intervening experience(s)
delayed related probe
```

### Composition group

```text
two or more acquisition components
one later task requiring novel combination
```

Composition is optional for the first pilot if no suitable family exists.

## Authoring validation

The validator requires:

- at least one written invariant for transfer;
- at least one changed dimension;
- a stated reason the boundary case changes applicability;
- no probe included in acquisition exposure;
- holdout members excluded from learner-visible task catalogues where applicable.

## Non-goals

- No automatic inference of task similarity.
- No embedding-based relation discovery.
- No graph database.
- No global ontology of engineering mechanisms.
- No task-template schema changes.

## Acceptance criteria

1. At least two existing artifact-task families receive learning-family overlays.
2. Each family includes one structural-transfer relation.
3. At least one family includes a genuine applicability boundary.
4. A compiled study plan contains exact tasks rather than unresolved selectors.
5. Learning-family files remain outside task execution packages.
6. Removing the learning overlay leaves the original task runnable and unchanged.
7. The task BRIEF remains the source of runnable task truth.

---

# PRD LS-04 — Artifact Learning Runner and Pilot Studies

## Problem

The common substrate requires a concrete, low-complexity integration before being extended to staged or interactive environments.

Artifact tasks provide isolated workspaces and deterministic verification, but each current trial normally begins without study-controlled cross-trial learner continuity.

## Decision

Implement the first environment adapter using ordinary artifact-task execution.

One learning experience equals one complete artifact trial.

## Supported treatments

### Reset control

```text
context: reset
workspace: reset
memory: absent
harness: fixed
```

### Raw-history treatment

Selected prior task inputs, outputs, and released feedback become available in a designated study workspace.

### Structured-memory treatment

The learner may create or update an explicit memory artefact through a consolidation step.

The common layer records the artefact but does not prescribe its contents.

### Explicit harness-update treatment

A consolidation step may update allowlisted prompt or skill artefacts.

Model weights remain fixed.

## Workspace isolation

Each arm receives:

- a separate root;
- separate task workspaces;
- separate memory and harness artefacts;
- no visibility into another arm’s outputs.

Only declared carry-forward artefacts may cross experience boundaries.

## Feedback views

Initially support:

- terminal validity;
- canonical reward;
- evaluator breakdown;
- task-owned failure explanation where already available.

Holdout verifier internals remain hidden.

## Pilot suite

### Pilot A — Structural transfer

```text
acquisition:
  familiar representation of method M

probe:
  different names, values, or document form
  same governing method M
```

### Pilot B — Applicability boundary

```text
acquisition:
  method M is appropriate

boundary probe:
  superficially related problem
  changed governing condition
  method M is inappropriate or incomplete
```

### Pilot C — Retention

```text
acquisition
→ unrelated or competing artifact task
→ delayed related probe
```

### Pilot D — Composition

Where feasible:

```text
learn component A
learn component B
probe requiring A + B
```

## Study design

Every pilot includes:

- cold control;
- exposed arm;
- matched probe;
- paired repetitions;
- at least reset and structured-memory treatments;
- explicit state-transition receipts.

## Acceptance criteria

1. A cold and exposed arm can execute through the ordinary artifact runtime.
2. The adapter returns normal `TrialRecord` values.
3. Structured memory persists only through declared artefacts.
4. Probe feedback remains hidden until scoring.
5. The report separates cold competence from learning gain.
6. At least one pilot demonstrates measurable positive, zero, or negative transfer without the system presupposing the outcome.
7. At least one boundary pilot reports inappropriate-method application separately from general task score.
8. No changes are required to artifact task semantics or verifiers.

---

# PRD LS-05 — Substrate Revision Gate A

## Problem

The initial substrate was designed before real artifact studies. It will almost certainly contain fields that are unnecessary and omit concepts that become obvious during use.

Continuing directly into lifecycle work would turn provisional task assumptions into permanent common abstractions.

## Decision

Pause feature expansion and perform a task-derived substrate revision.

## Required review

For every common field or enum:

1. Which real study used it?
2. Did two distinct task families use it?
3. Could it remain study-local?
4. Did it constrain an environment unnecessarily?
5. Did it improve validity or merely add description?

## Promotion rule

A concept may become stable common substrate only when:

- at least two real task families require it; or
- it is essential for study validity, isolation, or persistence.

## Deletion rule

Delete:

- unused relation variants;
- speculative learner channels;
- unused feedback views;
- unused metadata fields;
- generic wrappers that merely rename existing values.

Do not retain aliases.

## Decisions to make

- Whether `LearningFamilySpec` remains experimentation-local or becomes a persisted contract.
- Whether semantic dimension roles are sufficiently stable.
- Whether experience roles need more than acquisition, practice, interference, and probe.
- Whether feedback release should remain an explicit step.
- Whether state-transition receipts contain the minimum useful fields.
- Whether artifact pilots need richer task-owned evidence.

## Deliverables

- Gate report;
- updated architecture decision;
- simplified contracts;
- migrated pilot specifications;
- updated public API;
- no compatibility layer.

## Acceptance criteria

1. Every stable common concept is supported by actual pilot usage or a stated validity requirement.
2. All unused speculative fields are deleted.
3. Artifact pilots still reproduce after simplification.
4. The common package remains independent of artifact task implementation.
5. Lifecycle integration begins only after this gate passes.

---

# PRD LS-06 — Lifecycle Learning Adapter and Continuity Treatments

## Problem

Finite lifecycles already coordinate checkpoints, evidence release, fresh or persistent execution, and one final `TrialRecord`. They are therefore well suited to learning studies, but two distinct kinds of continuity must not be conflated:

1. continuity inside a lifecycle;
2. learner continuity between complete lifecycles.

AEC-Bench currently retains one complete trial record for a lifecycle even when several checkpoint interactions occur.

## Decision

Implement a lifecycle adapter in which one study experience equals one complete lifecycle trial.

The first Release B increment implements exact lifecycle target resolution and
a reset-only local binding for `fresh_context` with `artifact_memory`. It uses
the existing lifecycle compiler and `run_lifecycle_trial()` path to return one
normal record. Structured memory, terminal feedback, and checkpoint analysis
remain later Release B work.

The second Release B increment adds adapter-owned reset and structured-memory
treatments. Learner snapshots contain only `memory/` and `feedback/` and use
copy-on-write transitions. An optional local-harness input exposes a validated
memory projection as read-only `learner_context/` without adding it to lifecycle
state, evidence, visibility policy, or verifier input. Feedback projector
content and lifecycle outcome projections remain LS-06C work.

The third Release B increment adds one drainage-owned public feedback view and
task-owned drainage gate extraction. Study-owned L01 glue supplies the explicit
projection mapping, derives assessment facts from persisted state and transition
evidence, and runs the cold, reset-after-acquisition, and structured-memory arms
through the common recorder and assessor. Missing projection evidence is
ineligible. Relation review remains an explicit assessor input. The
[deterministic L01 evidence](l01-deterministic-evidence.md) proves composition
and isolation only; it is not a model-learning result.

## Continuity matrix

| Within-lifecycle execution | Between-lifecycle learner state | Interpretation |
|---|---|---|
| Fresh sessions | Reset | Cold lifecycle competence |
| Persistent session | Reset after lifecycle | Within-episode context benefit |
| Fresh sessions | Carried memory | External-memory support |
| Persistent session | Carried memory | Combined contextual and cross-episode continuity |

The study must record both axes independently.

## Existing lifecycle visibility policies

Where available, the adapter should reuse existing distinctions such as:

- persistent context;
- artefact memory;
- raw evidence only;
- current release only.

These are already represented in lifecycle-related extension evidence and should not be duplicated under new names.

## Initial feedback support

The first lifecycle integration releases feedback only after the complete lifecycle.

Checkpoint-level feedback is deferred to LS-07.

## Lifecycle state isolation

The learning layer may preserve learner state between lifecycles.

It may not preserve hidden lifecycle state unless the lifecycle study explicitly defines a continuing domain scenario.

## Initial studies

Use both current lifecycle families where suitable:

- stormwater design;
- structural review.

Study patterns should include:

- first lifecycle as acquisition;
- changed later lifecycle as transfer probe;
- reset versus carried-memory treatments;
- fresh versus persistent checkpoint sessions;
- an applicability or review-boundary case.

## Acceptance criteria

1. One complete lifecycle maps to one experience and one normal `TrialRecord`.
2. Within-lifecycle session persistence and between-lifecycle learner persistence are independently configured.
3. Lifecycle hidden state cannot leak into learner memory.
4. Both lifecycle families can be executed through the same study core.
5. Cold and exposed arms use the same probe lifecycle.
6. Results distinguish within-episode context effects from cross-episode learning effects.
7. No common lifecycle base class is introduced.

---

# PRD LS-07 — Lifecycle Phase Evidence, Feedback, and Scaffolding Studies

## Problem

Complete-lifecycle outcomes reveal whether the final process succeeded, but not:

- which phase improved;
- where feedback changed behaviour;
- whether rework was avoided;
- whether the learner became better at seeking evidence;
- whether scaffolding transferred into independent performance.

## Decision

Allow lifecycle owners to emit optional, task-owned learning evidence for meaningful phases and checkpoints.

## `LifecycleLearningEvidence`

Conceptually:

```text
lifecycle phases
checkpoint-to-phase mapping
evidence requested
evidence released
submission accepted or rejected
constraints satisfied
rework events
revisited decisions
recovery actions
phase outcomes
```

The payload remains lifecycle-owned and is published as a typed extension artefact.

## Phase principles

A phase is:

- meaningful to the lifecycle;
- larger than individual model tokens;
- potentially composed of several checkpoints;
- optional;
- not part of the common lifecycle runtime.

Examples may include:

```text
interpret evidence
establish design basis
develop calculation
respond to review
issue final submission
```

The common study layer references phase IDs without interpreting them.

## Feedback schedules

Add support for:

- no feedback;
- terminal-only feedback;
- immediate checkpoint feedback;
- delayed checkpoint feedback;
- summary feedback after a phase.

The lifecycle adapter remains responsible for safely projecting feedback to the learner.

## Scaffolding studies

Support study designs such as:

```text
guided acquisition lifecycle
→ reduced-guidance practice lifecycle
→ independent probe lifecycle
```

Guidance may include:

- additional evidence prompts;
- explicit checkpoints;
- review comments;
- worked examples;
- structured checklists.

The probe must remove the relevant support.

## Reflection and consolidation

After a lifecycle, the study may ask the learner to:

- identify failed assumptions;
- record applicability conditions;
- update a reusable checklist;
- revise a skill or prompt;
- record unresolved uncertainty.

The state transition is measured by later behaviour, not by the apparent quality of the reflection prose.

## Lifecycle measurements

In addition to final task outcomes:

- phase completion;
- evidence-seeking quality;
- rework count;
- repeated-error rate;
- recovery after rejected submission;
- transfer after scaffold withdrawal;
- unnecessary-checking cost;
- retained review response quality.

## Acceptance criteria

1. At least two lifecycle owners emit task-owned phase evidence.
2. The common layer can group evidence by phase without understanding domain semantics.
3. Immediate and delayed feedback studies produce different declared schedules.
4. A guided-to-independent study includes a matched cold independent probe.
5. Reflective text is never scored as learning without later behavioural evidence.
6. Existing lifecycle evaluation remains authoritative.
7. No phase-level reward is added.

---

# PRD LS-08 — Substrate Revision Gate B

## Problem

Lifecycle integration introduces temporal concepts that may tempt the programme to universalise:

- phases;
- checkpoints;
- rework;
- evidence requests;
- scaffold levels.

Some will generalise to worlds and artifact tasks. Others should remain lifecycle-specific.

## Decision

Perform a second extraction gate before adding worlds.

## Questions to resolve

### Hierarchical evidence

Do multiple environment owners need a common reference envelope such as:

```text
LearningUnitRef
  unit_id
  unit_kind
  parent_unit_id
  authority
  evidence_ref
```

The envelope may identify a phase, decision, or action while leaving its payload task-owned.

### Feedback schedule

Did explicit feedback-release steps remain useful, or can some cases be simplified?

### Learner continuity

Gate A found no common artifact learner-state channels. Which lifecycle
requirements, if any, cannot remain adapter-owned?

### Outcome projections

Can named outcome projections remain function callbacks, or is a persisted registry identity needed?

### Study relations

Did lifecycle studies require any relation purpose not covered by:

- transfer;
- boundary;
- composition?

## Promotion rule

A hierarchical concept enters the common layer only when:

- at least one artifact study and one lifecycle study use it; or
- it is required for upcoming world evidence and can be demonstrated against existing evidence.

## Acceptance criteria

1. Lifecycle-only semantics remain lifecycle-owned.
2. A common hierarchical reference is added only if supported by real consumers.
3. Redundant continuity fields are removed.
4. The artifact and lifecycle suites rerun after migration.
5. World integration receives a documented minimal substrate rather than a collection of lifecycle assumptions.

---

# PRD LS-09 — Bounded-World Learning and Dam-Seepage Studies

## Problem

Artifact and lifecycle studies cannot fully test:

- action-dependent information acquisition;
- bounded observation;
- authoritative state transitions;
- causal cue learning;
- inappropriate action under changed conditions.

The dam-seepage world offers these properties in a compact, deterministic environment.

## Decision

Integrate the dam world before the more complex pump world.

One complete dam-world trial remains one experience.

## Dam learning family

Construct controlled profiles across dimensions such as:

### Surface

- sensor names;
- asset labels;
- units;
- evidence ordering;
- presentation wording.

### Parameters

- reading magnitudes;
- timing;
- threshold margins.

### Causal structure

- reliable versus unreliable instrument;
- visual evidence present or absent;
- persistent versus isolated threshold exceedance.

### Applicability

- escalation justified;
- more evidence required;
- routine surveillance sufficient.

### Observability

- relevant evidence initially visible;
- evidence released only after an epistemic action;
- evidence available at a cost.

## Study patterns

### Structural transfer

Experience with unreliable instrumentation should transfer to a changed presentation governed by the same reliability issue.

### Applicability boundary

Prior escalation experience should not cause escalation where:

- instrumentation is reliable;
- persistence conditions are absent;
- visual evidence does not support the alert.

### Epistemic-control transfer

Prior experience should improve the choice between:

- checking the measurement system;
- inspecting the downstream area;
- requesting confirmation;
- escalating immediately.

### Retention

A delayed related probe follows unrelated or conflicting monitoring cases.

## Task-owned action evidence

The dam owner may emit:

```text
actor action
pre-action evidence state
post-action evidence state
accepted or rejected
information released
decision relevance
terminal consequence
```

Optional analytical labels may identify an action as:

- epistemic;
- instrumental;
- control;
- social or authority-related.

These labels do not alter action execution.

## Acceptance criteria

1. Dam profiles express surface, causal, and applicability changes, including changes in available evidence.
2. At least one structural-transfer and one negative-transfer study execute.
3. The same typed world actions remain authoritative.
4. The study can determine whether an action revealed relevant evidence.
5. A familiar but inappropriate escalation is measured separately from generic failure.
6. Learner memory remains separate from hidden world state.
7. No universal world action union is introduced.
8. The dam world remains runnable outside learning studies.

---

# PRD LS-10 — Substrate Revision Gate C: Action and Effect Evidence

## Problem

World integration introduces action-level causal evidence. A naïve response would be to create a universal action schema or dense progress score.

That would conflict with the existing world architecture, where each world owns its state, actions, observation, transition, and evaluation semantics.

## Decision

Extract only a minimal common envelope for referencing task-owned learning units and effects.

## Proposed common envelope

Only if supported by dam and earlier lifecycle evidence:

```text
LearningUnitRef
  unit_id
  unit_kind
  parent_unit_id
  authority
  evidence_ref
```

Possible `unit_kind` values remain structural:

- phase;
- decision;
- action;
- feedback event.

They do not imply domain semantics.

## Task-owned effect payloads

A task or world may describe:

- information acquired;
- constraint opened or satisfied;
- liability created or resolved;
- resource consumed;
- future option enabled or removed;
- action reversibility;
- accepted or rejected authority outcome.

The common substrate stores an evidence reference, not a global union of these fields.

## Same-state comparison contract

Introduce an optional study-level comparison structure:

```text
EffectComparison
  common_source_state_ref
  alternative_experience_or_branch_refs
  controlled_host_conditions
  named_outcome_projections
```

It does not require every environment to support branching.

## Decision attribution

Every action-level item records its owner:

- actor;
- host;
- environment;
- external process.

Host-owned actions must not be attributed to the actor learner.

## Non-goals

- No generic progress reward.
- No universal liability model.
- No universal state diff.
- No token-level credit.
- No mandatory action annotation.
- No counterfactual runner yet.

## Acceptance criteria

1. The envelope can reference dam action evidence and lifecycle phase evidence.
2. Domain payloads remain owner-local.
3. The common package does not import world action types.
4. Actor and host effects are distinguishable.
5. No generic scalar “progress” field is required.
6. If two environments do not need the proposed envelope, it is not added.

---

# PRD LS-11 — Persistent-World and Cross-Journey Pump Learning

## Problem

The pump world already supports a rich long-horizon journey with fresh Prime sessions, a persistent actor workspace, host-owned Operations controls, resources, work, liabilities, and task-owned evaluation.

However, current persistence primarily supports continuity **within one complete journey**. A learning study must also control what persists between complete journeys.

## Decision

Integrate complete pump journeys as experiences and make world continuity and learner continuity explicitly independent.

## Continuity matrix

| World between journeys | Learner between journeys | Research interpretation |
|---|---|---|
| Reset | Reset | Cold competence |
| Reset | Carry | Transfer to a fresh but related world |
| Carry | Reset | Same world, naïve replacement learner |
| Carry | Carry | Continual stewardship |

This four-cell design is central.

It prevents apparent learning from being confused with:

- the world simply retaining prior repairs;
- the learner seeing a more favourable later state;
- hidden host state carrying across control arms.

## Cross-journey learner state

The study may preserve allowlisted:

- actor ledger;
- notes;
- structured memory;
- selected skill artefacts;
- prompt artefacts.

It may not preserve:

- hidden world state;
- verifier data;
- host-control internals;
- secret paths;
- undeclared provider state.

## Journey identity

Each journey remains:

- one world trial;
- one complete `TrialRecord`;
- one existing task-owned evaluation.

Fresh Prime sessions inside a journey do not become separate study experiences.

## Host actions

Operations controls are exogenous from the actor’s perspective.

The study records them as:

- environment or host interventions;
- potential regime changes;
- events to which the learner must adapt.

They do not receive actor-policy attribution.

## Initial pump studies

### Routine acquisition and changed-world transfer

Acquire one maintenance routine, then apply it in a fresh profile with changed timing or presentation.

### Applicability boundary

A familiar intervention is available but unsafe or unnecessary under changed duty, resource, or evidence conditions.

### Cross-session memory quality

Compare:

- reset;
- raw ledger;
- structured ledger;
- explicit skill consolidation.

### Host interruption adaptation

A host action invalidates part of the learner’s prior plan. Measure whether it detects and revises the plan.

### Composition

Expose component routines separately:

- inspect;
- protect duty;
- reserve resources;
- intervene;
- verify;
- close or hand over.

Later require a novel combination.

## Acceptance criteria

1. A study can preserve learner state between complete pump journeys.
2. World and learner continuity are configured separately.
3. All four continuity cells can be represented.
4. Hidden pump state never enters learner artefacts.
5. Host controls are recorded but not attributed to actor learning.
6. Fresh internal Prime sessions remain part of one journey.
7. A cross-journey transfer study includes a fresh-world cold control.
8. Existing pump journey execution and evaluation remain unchanged outside the adapter.

---

# PRD LS-12 — Pump Counterfactuals, Composition, Retention, and Interference

## Problem

Sequential comparisons reveal that two trajectories differed, but not necessarily which decision caused the difference.

The pump world’s branching and rollout capabilities make controlled same-state alternatives possible. Its long-horizon structure also permits stronger tests of skill composition, retention, and interference.

## Decision

Add optional world-owned counterfactual study support and a suite of advanced pump learning studies.

## Counterfactual set

```text
CounterfactualSet
  source_world_state_ref
  source_actor_observation_ref
  controlled_host_policy
  branches
  named comparisons
```

Each branch contains:

```text
candidate actor action
authoritative transition result
subsequent controlled rollout
task-owned outcome projections
```

The agent need not see all branches during execution.

Counterfactual evidence may be released later as feedback in a designated treatment.

## Required controls

Branches must share:

- the same authoritative source state;
- the same decision boundary;
- equivalent host policy;
- equivalent evaluation;
- equivalent rollout horizon or declared stopping conditions.

## Initial counterfactual studies

### Inspect versus intervene

Compare early information gathering with immediate intervention.

### Reserve resources now versus later

Measure service, option value, and later work feasibility.

### Provisional closure versus verified closure

Measure whether apparently successful work leaves unresolved liabilities.

### Continue plan versus replan after host intervention

Measure response to invalidated assumptions.

### Defer versus act

Measure short-term operational safety against later backlog or liability.

## Hierarchical analysis

Where the pump owner can project it, retain a task-owned hierarchy such as:

```text
journey
  ├── establish safe operation
  ├── acquire evidence
  ├── prepare work
  ├── execute intervention
  ├── verify
  └── close or hand over
```

Actions are associated with phases for analysis.

The hierarchy does not become a universal world lifecycle.

## Retention and interference studies

### Retention

```text
acquire routine
→ several unrelated journeys
→ delayed structurally related probe
```

### Similar-case interference

A later superficially similar case requires a different intervention.

### Conflicting-policy interference

A changed resource or authority regime makes a prior routine inapplicable.

### Composition retention

Test whether separately acquired components can still be composed after delay.

## Measurements

In addition to terminal validity:

- unserved capacity;
- liabilities created and resolved;
- work correctly closed;
- verification performed;
- resources conserved;
- unnecessary interventions;
- information acquired;
- future options preserved;
- recovery after host intervention;
- inappropriate routine reuse.

These remain task-owned named projections.

## Acceptance criteria

1. Counterfactual branches prove a common source state.
2. Host controls remain fixed or their differences are declared.
3. Actor actions and host actions receive separate attribution.
4. Counterfactual evidence is published as an optional study artefact.
5. At least one study compares an epistemic action with immediate intervention.
6. At least one study measures interference from a superficially similar case.
7. At least one composition probe requires previously separate component routines.
8. Hierarchical evidence is analytical only and does not alter canonical reward.
9. The common substrate remains usable by environments without branching.

---

# PRD LS-13 — Cross-Family Reporting, Curricula, CLI, and Release

## Problem

After integration across tasks, lifecycles, and worlds, study outputs must be understandable without reading raw trial records and event logs.

The programme also needs a controlled way to author curricula without prematurely introducing RL or self-modifying training loops.

## Decision

Provide one cross-family reporting model, a focused CLI, reusable study templates, and two clearly separated curriculum modes.

## CLI

```text
aec-bench learning validate <spec>
aec-bench learning plan <spec>
aec-bench learning run <plan>
aec-bench learning resume <study-run>
aec-bench learning report <study-run>
aec-bench learning compare <study-run>...
```

The CLI calls the same functional APIs used programmatically.

## Report structure

### Study design

- research question;
- claim mode;
- arms;
- experience relations;
- learner treatments;
- feedback schedule;
- repetitions;
- validity conditions.

### Competence versus learning

Always display separately:

- cold probe performance;
- exposed probe performance;
- estimated gain;
- absolute ceiling or floor;
- invalid or unmatched pairs.

### Transfer matrix

Rows are acquisition experiences or families.

Columns are probes.

Cells show:

- cold performance;
- exposed performance;
- estimated gain;
- relation purpose;
- confidence or repetition count.

### Retention view

Display:

- immediate gain;
- delayed gain;
- intervening experiences;
- decay;
- interference.

### Boundary view

Display:

- familiar-method activation;
- appropriate withholding or adaptation;
- negative-transfer rate.

### Composition view

Display:

- component acquisition;
- cold composition performance;
- exposed composition performance;
- missing or failed components.

### Learner-state lineage

Show:

```text
initial state
→ experience change
→ feedback release
→ consolidation change
→ probe state
```

without exposing protected contents.

### Efficiency

Display:

- acquisition trials;
- model calls;
- tokens;
- monetary cost;
- elapsed simulated or wall time where relevant;
- gain per selected denominator.

## Study templates

Provide helper builders rather than new runtime classes:

```text
transfer study
boundary study
retention study
interference study
composition study
scaffolding study
same-state counterfactual study
```

A builder produces an ordinary `LearningStudySpec`.

## Curriculum modes

### Controlled curriculum

- completely authored or deterministically generated in advance;
- supports controlled learning comparisons;
- sequence fixed in the compiled plan.

### Adaptive curriculum

- chooses the next experience from a predeclared finite candidate pool;
- uses a preregistered scheduling rule;
- records every selection reason;
- produces descriptive developmental results by default.

An adaptive curriculum may later be assessed on fixed held-out probes, but its internal trajectory should not be treated as a clean causal comparison.

## Cross-family studies

The final release should demonstrate that the same substrate can coordinate:

- an artifact-task study;
- a lifecycle study;
- a dam-world study;
- a pump-world study.

A single arm need not mix execution families in the first public release. The result and reporting model must nevertheless support all families.

## Future RL seam

The programme should publish sufficient evidence for later RL work:

- ordered trials;
- observations and actions where task-owned;
- state transitions;
- feedback releases;
- learner transitions;
- named outcomes;
- hierarchy and counterfactual evidence where available.

It should not yet define:

- policy-gradient advantages;
- token rewards;
- rollout-training datasets;
- trainer APIs;
- weight-update lineage;
- an RL-specific environment protocol.

Those decisions should be made only after the experience substrate demonstrates valid learning studies.

## Acceptance criteria

1. All study types can be validated, planned, run, resumed, and reported.
2. Reports distinguish competence from learning.
3. Reports never label descriptive sequences as controlled learning effects.
4. Artifact, lifecycle, dam, and pump results use one report model.
5. Controlled and adaptive curricula are visibly distinguished.
6. A complete study bundle can be inspected without accessing hidden verifier data.
7. No RL framework becomes a package dependency.
8. The release documentation explains how future training systems may consume evidence without making that interface stable yet.

---

# 10. Coverage map

## 10.1 Learning dimensions by environment

| Dimension | Artifact tasks | Lifecycles | Dam world | Pump world |
|---|---|---|---|---|
| **Structural variation** | Primary: controlled task families | Changed process and evidence forms | Changed presentation and causal cues | Changed profiles, timing, resources, faults |
| **Causal legibility** | Final verifier and failure analysis | Phase and checkpoint consequences | Direct action–observation effects | Persistent operational effects and liabilities |
| **Hierarchical evidence** | Optional task decomposition | Phases and checkpoints | Decisions and actions | Journey, phase, action, host intervention |
| **Consolidation** | Memory and harness artefacts | Context, artefact memory, reflection | Cross-trial memory | Cross-session and cross-journey memory |
| **Bounded observation** | Usually document/workspace boundary | Evidence-release boundary | Strong | Strong |
| **Typed actions** | Usually tool and file operations | Checkpoint submissions | Strong task-owned catalogue | Rich task-owned catalogue |
| **Persistent consequences** | Mostly within output artefact | Within lifecycle | Bounded episode | Strong across long journey |
| **Authority and other actors** | Limited | Reviewer or coordinator roles | Escalation authority | Actor versus Operations authority |
| **Recoverable failure** | Revision after verifier feedback | Rework and resubmission | Changed response after evidence | Rejection, interruption, recovery, handover |
| **Transfer studies** | Cleanest starting point | Process and scaffold transfer | Cue and applicability transfer | Long-horizon compositional transfer |
| **Retention and interference** | Simple cross-task sequence | Cross-lifecycle sequence | Controlled monitoring cases | Persistent, operationally realistic sequence |
| **Counterfactual comparison** | Alternative submissions | Alternative branches where supported | Small same-state variants | Strong branching and rollout support |

## 10.2 PRD coverage by core dimension

| Dimension | Principal PRDs |
|---|---|
| Structural variation | LS-03, LS-04, LS-09, LS-11 |
| Causal legibility | LS-07, LS-09, LS-10, LS-12 |
| Hierarchical evidence | LS-07, LS-08, LS-10, LS-12 |
| Consolidation | LS-02, LS-04, LS-06, LS-11 |
| Controlled transfer | LS-02, LS-04, LS-09, LS-11 |
| Applicability and negative transfer | LS-03, LS-04, LS-09, LS-12 |
| Composition | LS-03, LS-04, LS-11, LS-12 |
| Retention and interference | LS-02, LS-04, LS-07, LS-12 |
| Authority and exogenous control | LS-09, LS-10, LS-11, LS-12 |
| Curriculum and reporting | LS-13 |

---

# 11. Suggested package ownership

The exact file layout should remain modest.

```text
src/aec_bench/
  contracts/
    learning_study.py

  experimentation/
    learning_studies/
      __init__.py
      values.py
      planning.py
      runtime.py
      validation.py
      assessment.py
      recording.py
      reporting.py

      artifact_tasks.py
      lifecycles.py
      worlds.py
```

Task-owned evidence remains with its owner:

```text
tasks/<family>/learning_evidence.py
lifecycles/<lifecycle>/learning_evidence.py
worlds/monitoring/dam_seepage/learning_evidence.py
worlds/stewardship/wastewater_pump_station/learning_evidence.py
```

This maintains dependency direction:

```text
task/world owner
  does not import study policy

learning adapter
  imports existing public execution API

learning core
  imports shared records and contracts only
```

The current world and lifecycle experiment functions already follow a simple functional pattern in which caller-supplied trial execution produces ordered normal records. The adapters should build on those entry points rather than create parallel runners.

---

# 12. What must not be built

The programme should explicitly reject the following designs.

## No `LearningTask` base class

A normal task becomes an experience through study placement. It does not need a second identity.

## No fourth execution runtime

A learning study orchestrates existing executions.

## No universal world or lifecycle state

The study references authoritative evidence and named projections.

## No global action union

Action semantics remain task-owned.

## No mandatory phase model

Phases are optional task-owned analytical projections.

## No learner-state database before it is needed

Artefact references and explicit lineage are sufficient initially.

## No automatic similarity inference

Task relations are authored and reviewable.

## No generic dense progress reward

Learning evidence remains evidence until a later training design deliberately converts it.

## No append-only memory assumption

A useful learner may revise, replace, compress, or delete prior memory.

## No hidden self-modification

Every committed harness or memory update receives a transition receipt.

## No RL dependency

The programme stops at controlled experience, adaptation, evidence, and assessment.

---

# 13. Release sequence

## Release A — Foundation and artifact studies

Includes:

- LS-00;
- LS-01;
- LS-02;
- LS-03;
- LS-04;
- LS-05.

Exit condition:

> AEC-Bench can demonstrate controlled learning transfer, a boundary case, and retention using ordinary artifact tasks and fixed model weights.

## Release B — Lifecycle learning

Includes:

- LS-06;
- LS-07;
- LS-08.

Exit condition:

> AEC-Bench can distinguish within-lifecycle context effects, cross-lifecycle learner continuity, feedback timing, and scaffold transfer.

## Release C — Bounded-world learning

Includes:

- LS-09;
- LS-10.

Exit condition:

> AEC-Bench can measure whether prior experience improves epistemic action selection and applicability judgment in an authoritative interactive world.

## Release D — Persistent-world learning

Includes:

- LS-11;
- LS-12.

Exit condition:

> AEC-Bench can separate world persistence from learner persistence and evaluate composition, retention, interference, host interruption, and controlled counterfactual alternatives.

## Release E — Productisation

Includes:

- LS-13.

Exit condition:

> The same study language and report model work across all execution families without altering their task semantics.

---

# 14. Programme definition of done

The programme is complete when AEC-Bench can answer all of the following questions with controlled evidence:

1. Did prior experience improve later performance relative to a cold learner?
2. Did the learner transfer the relevant structure rather than memorise presentation?
3. Did it correctly recognise where a familiar method stopped applying?
4. Could it combine previously acquired components in a novel task?
5. Did useful behaviour survive intervening experiences?
6. Did later experience interfere with or distort earlier competence?
7. What learner state was permitted to persist?
8. What feedback did the learner actually receive?
9. Which environment decisions or phases contributed to the outcome?
10. Were host or external actions incorrectly attributed to the learner?
11. Did improvement come from raw history, structured memory, harness updates, or persistent context?
12. Can the study be replayed, resumed, and independently inspected?
13. Can the same concepts be applied to tasks, lifecycles, bounded worlds, and persistent worlds without forcing them into one runtime?
14. Can future RL work consume the resulting evidence without the current programme having prejudged its algorithm?

The target state is therefore:

```text
AEC-Bench today

rich tasks and worlds
+ authoritative evidence
+ strong trial evaluation
+ outer-loop experimentation
```

```text
AEC-Bench after the programme

rich tasks and worlds
+ deliberately related experiences
+ controlled learner continuity
+ explicit feedback schedules
+ transfer and boundary probes
+ retention and interference studies
+ hierarchical and causal evidence
+ cross-family learning assessment
```

The core architectural insight is:

> **The learning substrate should not own what an experience means. It should own the controlled relationship between experiences, the learner continuity between them, and the evidence required to determine what changed.**

That keeps the layer optional, preserves the current task and environment architecture, and gives AEC-Bench a path from isolated capability evaluation to rigorous study of how agents acquire durable competence.
