# AEC-Bench Learning Studies — Release A PRD Tranche

**Class:** Research
**Status:** Historical — implemented and simplified at Gate A on 22 August 2026
**Baseline reviewed:** `main` as inspected on 22 August 2026
**Parent reference:** `docs/research/learning-studies/programme.md`
**Scope:** Common learning-study substrate, artifact-task integration, first controlled studies, and Gate A
**Explicitly excluded:** Lifecycle integration, Interactive World integration, adaptive curricula, and model-weight/RL training

## Purpose

This directory turns the Learning Studies programme charter into the first set of implementation-ready documents.

The programme charter remains the source of truth for:

- the overall learning architecture;
- the full LS-00 to LS-13 roadmap;
- cross-environment design principles;
- the distinction between trials, experiences, learning studies, and training;
- the long-term coverage map across artifact tasks, lifecycles, bounded worlds, and persistent worlds.

The documents here define only **Release A**. They should be read as a coordinated tranche rather than as independent feature requests.

The current implementation and the
[Gate A decision](../../../adr/learning-studies-gate-a.md) supersede provisional
field and enum details in these PRDs.

## Required reading order

1. `programme.md` — the retained programme charter in the repository.
2. [LS-00 — Programme Boundary and Semantic Cleanup](LS-00-programme-boundary-and-semantic-cleanup.md)
3. [LS-01A — Study Contracts and Compilation](LS-01A-study-contracts-and-compilation.md)
4. [LS-01B — Study Runtime and Arm Isolation](LS-01B-study-runtime-and-arm-isolation.md)
5. [LS-02A — Recording, Learner-State Lineage, and Resume](LS-02A-recording-lineage-and-resume.md)
6. [LS-02B — Controlled Validity and Learning Assessment](LS-02B-controlled-validity-and-learning-assessment.md)
7. [LS-03 — Learning-Family Authoring](LS-03-learning-family-authoring.md)
8. [LS-04A — Artifact Learning Adapter](LS-04A-artifact-learning-adapter.md)
9. The four study protocols under [`studies/`](studies/)
10. [Gate A — Artifact Substrate Extraction](GATE-A-artifact-substrate-extraction.md)

## Documents in this tranche

| Document | Type | Outcome |
|---|---|---|
| LS-00 | Implementation PRD | Establish ownership, vocabulary, package boundary, and remove the existing “transfer” terminology collision |
| LS-01A | Implementation PRD | Define the authored study contract and deterministic compilation into existing `PlannedTrial` values |
| LS-01B | Implementation PRD | Execute compiled study arms with opaque learner state, copy-on-write transitions, and probe isolation |
| LS-02A | Implementation PRD | Persist exact study evidence, learner-state lineage, step commits, and resumable execution |
| LS-02B | Implementation PRD | Validate controlled comparisons and calculate transfer, boundary, retention, interference, composition, and efficiency results |
| LS-03 | Implementation PRD | Author reviewable semantic relationships over existing artifact tasks without changing task semantics |
| LS-04A | Implementation PRD | Bind the common substrate to local artifact-task execution and support reset, history, memory, and explicit harness-update treatments |
| A01 | Study protocol | Structural transfer under changed surface or parameter conditions |
| A02 | Study protocol | Applicability boundary and negative transfer |
| A03 | Study protocol | Immediate transfer, delayed retention, and interference |
| A04 | Study protocol | Novel composition of separately acquired components |
| Gate A | Extraction gate / ADR protocol | Delete speculative substrate, promote demonstrated common concepts, and decide what is ready for lifecycle integration |

## Architectural position

Release A adds an optional orchestration and analysis layer under `aec_bench.experimentation`.

```text
existing task resolution
        ↓
existing PlannedTrial
        ↓
existing artifact execution
        ↓
existing TrialRecord
        ↓
learning-study comparison and evidence
```

It does **not** add:

- a fourth execution runtime;
- a `LearningTask` base class;
- a second task catalogue;
- a universal action, phase, progress, or memory model;
- a replacement for `TrialRecord`;
- hidden self-modification;
- model-weight updates.

The central rule is:

> A trial remains the unit of execution. A learning study becomes the unit of controlled learning analysis.

## Shared implementation constraints

Every PRD in this tranche inherits the following constraints:

1. **Existing execution remains authoritative.** Artifact trials still resolve, execute, verify, and produce ordinary `TrialRecord` values through existing owners.
2. **Experimentation owns study policy.** Task packages do not import learning-study policy.
3. **Task semantics remain task-owned.** A study can assert a relationship between tasks; it cannot redefine either task.
4. **Learner state is distinct from task or world state.** Release A only carries explicitly allowlisted external learner artifacts.
5. **Evidence is not feedback.** Evidence may exist without being released to the learner.
6. **Feedback is not reward.** Release A performs evaluation and comparison, not policy-gradient training.
7. **Controlled claims require matched controls.** Unmatched sequences are descriptive only.
8. **Probes are isolated by default.** Probe-created learner changes are discarded and probe evaluation is hidden until scoring completes.
9. **No compatibility layers.** Obsolete names and paths are removed when their replacement lands.
10. **No new provenance programme.** Reuse existing task, run, trial, artifact, and Git identities. Do not introduce package hashes or per-feature version variables.

## Delivery order and merge boundaries

The recommended merge order is:

```text
PR 1  LS-00
PR 2  LS-01A
PR 3  LS-01B
PR 4  LS-02A
PR 5  LS-02B
PR 6  LS-03
PR 7  LS-04A
PR 8+ artifact learning families and pilot protocols
ADR   Gate A
```

A PR may combine adjacent items only when the resulting review remains bounded. In particular:

- do not combine LS-01A and LS-01B if that hides contract decisions inside runtime code;
- do not combine LS-02A and LS-02B if that conflates evidence integrity with statistical interpretation;
- do not merge Gate A as a feature PR.

## Definition of completion for Release A

Release A is complete when AEC-Bench can run at least two artifact-task learning families and answer, with inspectable evidence:

- what the cold learner did on the probe;
- what the exposed learner did on the same probe;
- exactly what learner state was permitted to persist;
- exactly what feedback was released;
- whether the comparison supports a controlled learning claim or only a descriptive result;
- whether prior experience improved transfer, caused harmful over-application, survived delay, or supported composition;
- how much acquisition experience and model usage the result required.

Completion does **not** require a positive learning result. A valid zero or negative result is scientifically useful.

## Instructions for implementation agents

Before changing code, an agent must:

1. Read the programme charter and the relevant detailed PRD.
2. Re-map every cited repository path against current `main`; these documents describe the reviewed baseline, not a frozen code snapshot.
3. Preserve the owner boundaries in `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`, and `tests/test_package_ownership.py`.
4. Prefer deletion and direct composition over adapters layered on obsolete APIs.
5. Stop and document a real architectural conflict rather than silently broadening the common substrate.
6. Keep later-environment concepts out of Release A unless a current artifact study proves they are required.
