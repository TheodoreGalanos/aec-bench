# LS-00 — Learning Studies Boundary and Semantic Cleanup

**Status:** Proposed
**Type:** Implementation PRD
**Release:** Learning Studies Release A
**Depends on:** Learning Studies programme charter
**Blocks:** LS-01A and every later Learning Studies PRD
**Primary owner:** `aec_bench.experimentation`
**Repository baseline:** `main`, reviewed 22 August 2026

## 1. Purpose

Establish one unambiguous architectural home and vocabulary for Learning Studies before adding contracts or runtime behaviour.

This PRD is deliberately small. It removes a current terminology collision, creates the package and documentation boundary, and adds dependency tests that prevent the new layer from leaking into task execution.

## 2. Current state

AEC-Bench currently has three deliberately separate execution families:

- artifact tasks;
- finite lifecycles;
- Interactive Worlds.

They share planning, evidence, evaluation, and `TrialRecord`, but do not share one low-level runtime. Experimentation policy already sits above execution owners, and the runtime-neutral meta-harness demonstrates the intended dependency direction.

The repository also contains:

```text
src/aec_bench/experimentation/lifecycle_studies/transfer.py
```

That module calls a fixed-candidate holdout comparison “transfer” while explicitly declaring:

- `descriptive_holdout_generalization` interpretation;
- no causal-effect support;
- no cross-run learning support.

That name becomes misleading once AEC-Bench introduces actual prior-experience transfer studies.

## 3. Problem

Without this cleanup, the repository would use **transfer** for two different questions:

```text
Fixed-candidate generalisation
Does one unchanged learner perform on a held-out task?
```

and:

```text
Learning transfer
Does prior experience cause changed performance on a later matched probe?
```

The distinction is foundational. It must be reflected in package names, public symbols, documentation, reports, and tests before the new substrate lands.

A second risk is architectural drift. If no package boundary is established now, learning policy could be added separately inside artifact tasks, lifecycles, and worlds, recreating the duplication the recent repository rationalisation removed.

## 4. Goals

1. Create `aec_bench.experimentation.learning_studies` as the sole owner of cross-trial learning-study policy.
2. Rename the existing lifecycle “transfer” study to holdout generalisation.
3. Define and document the terms used by all later PRDs.
4. Add package-ownership tests before implementation expands.
5. Preserve all existing execution-family boundaries.
6. Delete obsolete names rather than maintaining aliases.

## 5. Non-goals

This PRD does not add:

- learning-study contracts;
- a study runner;
- learner-state persistence;
- task relations;
- artifact-task treatments;
- learning metrics;
- lifecycle or world functionality;
- CLI commands.

## 6. Architectural decision

Create this package:

```text
src/aec_bench/experimentation/learning_studies/
  __init__.py
```

At LS-00, the package contains only module documentation and no runtime API.

Its ownership statement is:

> `aec_bench.experimentation.learning_studies` owns the controlled relationship between existing trials, declared learner continuity between them, feedback-release policy, study validity, and learning-level comparison. It does not own task semantics, task execution, verification, provider execution, or model-weight training.

The intended dependency direction is:

```text
contracts / planning records
          ↑
learning-study core
          ↑
environment-specific learning adapter
          ↑
existing public execution API
```

Forbidden directions are:

```text
task domain ─X→ learning_studies
harness     ─X→ experimentation
contracts   ─X→ experimentation
world owner ─X→ learning-study policy
```

## 7. Required vocabulary

Add a concise vocabulary section to the programme charter or a linked architecture page.

| Term | Required meaning |
|---|---|
| Trial | One existing execution producing one ordinary `TrialRecord` |
| Experience | A trial placed in a learning study; not a new runtime type |
| Learning study | A controlled sequence of experiences and learner-state transitions |
| Arm | One control or treatment sequence in a study |
| Acquisition | An experience intended to supply useful practice or knowledge |
| Practice | An additional related experience before a probe |
| Interference | An experience inserted to test forgetting, conflict, or overgeneralisation |
| Probe | A trial used to measure behaviour after prior exposure |
| Cold control | The same probe completed without the relevant prior experience |
| Learner state | Explicitly permitted state carried between experiences |
| Feedback release | Making selected host-held evidence visible to the learner |
| Consolidation | An explicit operation that may update permitted learner state from visible experience and feedback |
| Generalisation | Performance by an unchanged learner on a changed task |
| Learning transfer | A controlled difference attributable to prior experience under declared controls |
| Retention | Persistence of a learning effect after delay or intervening experience |
| Interference | Degradation or distortion of earlier competence after later experience |
| Composition | Combining previously acquired components in a novel task |

The word **transfer** must not be used for ordinary fixed-candidate holdout evaluation after this PRD.

## 8. Exact semantic cleanup

### 8.1 Module rename

Rename:

```text
src/aec_bench/experimentation/lifecycle_studies/transfer.py
```

to:

```text
src/aec_bench/experimentation/lifecycle_studies/holdout_generalization.py
```

### 8.2 Symbol rename

Rename all public symbols directly:

| Existing | Replacement |
|---|---|
| `LifecycleTransferRecordReference` | `LifecycleHoldoutRecordReference` |
| `LifecycleTransferCondition` | `LifecycleHoldoutCondition` |
| `LifecycleTransferStudyDesign` | `LifecycleHoldoutStudyDesign` |
| `LifecycleTransferEvaluationSpec` | `LifecycleHoldoutEvaluationSpec` |
| `LifecycleTransferCalibrationResult` | `LifecycleHoldoutCalibrationResult` |
| `LifecycleTransferTargetResult` | `LifecycleHoldoutTargetResult` |
| `LifecycleTransferSummary` | `LifecycleHoldoutSummary` |
| `build_lifecycle_transfer_evaluation` | `build_lifecycle_holdout_evaluation` |

Update any related result, parser, builder, or test symbol that follows the same old prefix.

Do not add compatibility aliases or deprecation wrappers.

### 8.3 Persisted wording

Replace persisted identifiers and labels that use transfer for this study, including the evaluation identifier prefix.

Use:

```text
lifecycle-holdout-
```

rather than:

```text
lifecycle-transfer-
```

Existing local experimental outputs do not require a migration layer. Regenerate affected fixtures where the repository owns them.

### 8.4 Documentation and tests

Update:

- `src/aec_bench/experimentation/lifecycle_studies/__init__.py`;
- architecture and lifecycle-study documentation;
- examples;
- imports;
- snapshots and fixtures;
- any CLI help or report text;
- tests that mention lifecycle transfer.

The resulting wording must consistently describe this as **holdout generalisation by a fixed candidate**.

## 9. New documentation boundary

Place the retained programme charter at:

```text
docs/research/learning-studies/programme.md
```

Place detailed PRDs under:

```text
docs/research/learning-studies/release-a/
```

Add a short route from the repository’s main architecture or research index. Do not duplicate the programme charter into several guides.

The package `__init__.py` should point maintainers to the programme charter rather than embedding the full design in source comments.

## 10. Package ownership tests

Extend `tests/test_package_ownership.py` or the current equivalent with rules that prove:

1. Modules under `aec_bench.experimentation.learning_studies` may import shared contracts, planning values, ledger/artifact helpers, and public execution entry points.
2. `aec_bench.contracts` does not import `aec_bench.experimentation.learning_studies`.
3. `aec_bench.harness` does not import `aec_bench.experimentation.learning_studies`.
4. Task-domain packages do not import `aec_bench.experimentation.learning_studies`.
5. Lifecycle and world owners do not import common learning-study policy.
6. Later environment-specific adapters live in or above `experimentation`, never inside task semantics.

The exact import graph should follow current package-ownership conventions rather than introducing a second audit mechanism.

## 11. Implementation sequence

1. Add the documentation route and empty package with its ownership statement.
2. Rename the lifecycle holdout module and public symbols.
3. Update all imports, identifiers, fixtures, examples, and tests.
4. Add package-ownership assertions.
5. Run the full existing lifecycle-study and architecture test suites.
6. Search the repository for remaining misleading uses of “transfer”.
7. Keep legitimate future-facing uses in the programme documents; remove only uses that mean fixed holdout generalisation.

## 12. Failure and compatibility policy

- Old Python imports fail after the rename.
- Old local experimental files using obsolete identifiers are not automatically migrated.
- A test or example that imports an old symbol must be changed, not supported through an alias.
- Any external public-release concern should be raised explicitly in the PR, but the default remains deletion because this repository does not preserve obsolete internal paths speculatively.

## 13. Test matrix

### Unit and import tests

- New module imports successfully.
- Every replacement symbol validates and serialises exactly as its renamed predecessor did, except for deliberate identifier wording.
- Every old symbol import fails.

### Architecture tests

- Forbidden dependency directions fail the ownership audit.
- `learning_studies` can import shared contracts without a cycle.

### Regression tests

- Existing lifecycle holdout study produces the same substantive evaluation under its new name.
- Existing artifact, lifecycle, and world tests remain unchanged in behaviour.

### Repository search test

A bounded test or CI assertion should ensure that these obsolete public names do not reappear. A one-time implementation search is acceptable if the repository avoids source-text assertions.

## 14. Acceptance criteria

LS-00 is complete when:

1. `aec_bench.experimentation.learning_studies` exists with a documented ownership boundary.
2. The programme charter is reachable from repository documentation.
3. The lifecycle study is named holdout generalisation in modules, symbols, persisted identifiers, tests, and prose.
4. No compatibility alias for the old transfer names exists.
5. Package-ownership tests prevent learning policy from entering task, harness, contract, lifecycle-owner, or world-owner packages.
6. All existing execution-family tests pass without semantic change.
7. No implementation contract from LS-01 or later has been prematurely added.

## 15. Agent handoff

The implementation agent should return:

- the exact rename inventory;
- deleted paths and symbols;
- updated documentation routes;
- ownership-test additions;
- full test results;
- any use of “transfer” intentionally retained and why.
