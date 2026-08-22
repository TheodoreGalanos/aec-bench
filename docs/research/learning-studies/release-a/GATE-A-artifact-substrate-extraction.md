# Gate A — Artifact-Derived Learning Substrate Extraction

**Status:** Required architecture gate
**Type:** Extraction review and ADR protocol
**Release:** After LS-00 through LS-04A and artifact pilots; before lifecycle PRDs are finalised
**Primary owner:** Learning Studies programme maintainers
**Decision authority:** Repository architecture review

## 1. Purpose

Stop feature expansion after the artifact tranche and decide, from real implementation and study evidence, what genuinely belongs in the common Learning Studies substrate.

Gate A prevents the first implementation from becoming permanent merely because it was first.

The gate must be completed before detailed lifecycle implementation begins.

## 2. Core rule

> A concept becomes common because several real studies or a hard validity requirement need it, not because a future environment might use it.

Artifact integration is intentionally the simplest environment. It should reveal:

- which authored study concepts are stable;
- which runtime transitions are essential;
- which learner-state abstractions are portable;
- which treatment concepts are artifact-specific;
- which metric contracts are actually usable;
- which fields and enums were speculative.

## 3. Entry criteria

Gate A begins only when all of the following are available.

### Software evidence

- LS-00 through LS-04A implemented and merged on a clean branch sequence;
- complete unit, architecture, failure, and resume tests;
- at least one successful crash-and-resume run;
- at least one controlled cold/exposure comparison;
- no unresolved cross-arm leakage defect;
- existing artifact-task regression suite passing.

### Study evidence

At least two independently authored artifact learning families.

Required completed pilots:

- A01 structural transfer;
- A02 applicability boundary;
- A03 retention/interference at least through a real-model pilot.

A04 composition should be completed where a valid target family exists. If no defensible composition family exists, the gate must record that result rather than forcing a weak task.

### Operational evidence

- actual run bundle examples;
- learner-state snapshots;
- feedback artifacts;
- consolidation artifacts;
- controlled and downgraded assessment examples;
- cost and storage observations;
- implementation-agent retrospectives.

## 4. Required outputs

Gate A produces:

1. one architecture decision record;
2. a field-by-field substrate review;
3. a deletion and simplification patch;
4. updated Release A examples;
5. an updated programme charter where real findings changed assumptions;
6. the bounded input requirements for detailed lifecycle PRDs;
7. a list of concepts deliberately left adapter-owned.

Suggested ADR path:

```text
docs/adr/learning-studies-gate-a.md
```

Do not create a “v2” package beside the first implementation. Change or delete the provisional API directly before public stabilisation.

## 5. Evidence review method

For every common type, field, enum, callback, and file, answer:

1. Which real study used it?
2. Which second independent study or validity rule also required it?
3. Did the common layer interpret domain semantics it should not own?
4. Could the value remain adapter-local?
5. Did it prevent an actual invalid comparison or merely add description?
6. Was it persisted because resume required it or simply because it was convenient?
7. Did any agent misunderstand or misuse it?
8. Did it make a future lifecycle concept more difficult rather than easier?
9. Can it be deleted without reducing study validity?
10. If retained, is its name still accurate after real use?

Every retained common concept needs a written answer.

## 6. Promotion rule

A provisional concept may remain or become a stable shared contract only when at least one of these is true:

### Demonstrated common use

Two independent real artifact families use it in materially different studies.

### Validity requirement

It is necessary to establish:

- exact execution identity;
- arm isolation;
- probe isolation;
- learner-state lineage;
- feedback visibility;
- controlled comparison;
- safe resume.

### Existing repository boundary

It directly reuses and preserves an already stable shared contract such as `PlannedTrial`, `TrialRecord`, or `ArtifactRef`.

Convenience, anticipated world use, or aesthetic symmetry are not sufficient.

## 7. Deletion rule

Delete before lifecycle integration:

- unused relation purposes;
- unused dimension kinds;
- state fields that no recorder or assessor consumes;
- feedback views without a real safe projector;
- treatment channels used only by speculative tests;
- duplicate identity or timestamp fields;
- generic wrappers that merely rename existing records;
- callbacks that can be ordinary function arguments;
- config options that all real studies set identically;
- compatibility aliases from Release A refactors.

Migration cost inside the unreleased tranche is not a reason to preserve noise.

## 8. Contract-by-contract review

### 8.1 `LearningStudySpec`

Decide:

- Are all experience roles used?
- Does `claim_mode` belong in the authored spec or derive from measurements?
- Is one common `AgentConfig` and `ComputeConfig` sufficient?
- Are relations required in every study or only in family-backed studies?
- Did authors need a description field on every experience?
- Are explicit feedback and consolidation steps clearer than implicit treatment hooks?

### 8.2 Step union

Review:

- `RunExperience`;
- `ReleaseFeedback`;
- `Consolidate`.

Do not add lifecycle-style checkpoint steps at Gate A. Instead decide whether these three operations remained orthogonal and sufficient for artifact studies.

### 8.3 Relation purposes

Review real use of:

- transfer;
- boundary;
- composition;
- retention;
- interference.

If retention and interference are better represented as sequence roles plus transfer/boundary relations, simplify rather than preserving redundant relation kinds.

### 8.4 Dimension kinds

For each of:

- surface;
- parameter;
- causal;
- applicability;
- observability;
- authority or resource;
- regime;
- component;

record actual usage.

Artifact families may not justify `authority_or_resource` or `regime`. Leave them out of the stable common enum unless real families used them. Worlds can later reintroduce demonstrated needs through Gate C.

### 8.5 Learner state

Review:

- full snapshots versus deltas;
- parent lineage;
- changed-channel labels;
- state identity scheme;
- archive format;
- storage overhead;
- whether the common layer needs channel labels at all.

Do not introduce incremental snapshots unless measured storage or resume evidence justifies them.

### 8.6 Feedback

Review:

- whether feedback release needed a first-class step;
- whether feedback artifacts were safely projectable;
- whether source trial and view identity were sufficient;
- whether “terminal outcome,” “public evaluation,” and “task explanation” remained adapter-local as intended.

### 8.7 Consolidation

Review:

- whether separate bounded consolidation was useful;
- whether it was distinguishable from ordinary task execution;
- whether usage evidence was adequate;
- whether memory and harness updates need separate common operation types or remain adapter-owned IDs;
- whether update limits and rollback were sufficient.

### 8.8 Assessment

Review:

- which measurement kinds were actually used;
- whether one generic paired-difference contract would be simpler than several enums;
- whether validity downgrade rules were understandable;
- whether task-owned projections were easy to implement;
- whether confidence intervals were useful at observed repetition counts;
- whether acquisition-success secondary analysis caused post hoc misuse.

### 8.9 Recording and resume

Review:

- staging complexity;
- step receipt versus event-log authority;
- orphan recovery;
- trial-ledger interaction;
- state archive security;
- actual interruption modes.

Simplify only where failure-injection evidence proves a smaller protocol remains safe.

### 8.10 Artifact adapter

Explicitly separate:

```text
common substrate
  study sequence, lineage, validity, assessment

artifact-owned integration
  workspace paths, treatments, feedback projectors,
  consolidation files, selected-snapshot export
```

Do not promote `.aec-bench-learning/` channel layout or local runner details into shared contracts merely because they worked for artifacts.

## 9. Architecture questions for lifecycle readiness

Gate A should answer these questions without designing the lifecycle adapter in detail.

1. Can one complete lifecycle still map cleanly to one `RunExperience` step?
2. Does the common substrate need to know about checkpoints? The default answer should remain no.
3. Which learner-state channels are meaningfully portable beyond artifact workspaces?
4. Can lifecycle visibility policies be mapped by an adapter without changing common state contracts?
5. Does feedback release need to occur only between trials in the common layer, with checkpoint feedback remaining lifecycle-owned?
6. Is the current result model capable of referencing future task-owned phase evidence without adding fields now?
7. Which controls proved necessary to distinguish within-episode context from cross-episode learning?

The gate should produce requirements for LS-06 and LS-07, not their final implementations.

## 10. Study findings required at the gate

For each completed protocol, record:

- whether the software produced a controlled, descriptive, or invalid comparison;
- cold and exposed competence;
- observed transfer or negative transfer;
- learner-state treatment used;
- state size and update frequency;
- feedback view used;
- consolidation behaviour;
- invalid or excluded pairs;
- any leakage or ambiguity discovered;
- whether the family metadata captured the real relationship accurately.

The purpose is architecture extraction, not model marketing.

## 11. Gate decisions

The ADR must assign one of four outcomes to every provisional concept.

### Keep common

Demonstrated shared or validity-critical.

### Keep provisional

Required for the next integration but not yet stable. Must have a named future gate.

### Move to adapter or study protocol

Useful, but not common infrastructure.

### Delete

Unused, redundant, misleading, or speculative.

No “keep just in case” category exists.

## 12. Gate outcomes

### Pass

The substrate is small, evidence-backed, and ready for detailed lifecycle PRDs.

### Pass with required simplification

Lifecycle design may begin only after the deletion/refactor patch merges and all artifact studies rerun.

### Hold

A critical validity or isolation problem remains. Fix and repeat the affected pilots.

### Reject architecture

The current substrate does not support controlled learning claims without coupling to artifact semantics. Rework the boundary before proceeding.

A hold or rejection is a useful programme result, not a failure to complete the roadmap.

## 13. Required regression after gate changes

After every Gate A simplification:

- rerun contract tests;
- rerun runtime isolation tests;
- rerun failure-injection and resume tests;
- rerun at least one controlled A01 study;
- rerun one A02 boundary study;
- verify existing artifact tasks remain unchanged outside learning studies;
- regenerate examples and reports.

Do not claim equivalence from unit tests alone if persisted study bundles changed.

## 14. Acceptance criteria

Gate A is complete when:

1. Every common field and enum has a documented keep, provisional, move, or delete decision.
2. Retained concepts are justified by two studies or a hard validity requirement.
3. Unused speculative fields and aliases are deleted.
4. Artifact-owned workspace and treatment semantics remain outside the common substrate.
5. At least one controlled transfer and one applicability-boundary study rerun after simplification.
6. Resume and probe-isolation tests still pass.
7. The programme charter reflects real findings.
8. Detailed lifecycle PRDs are written from the resulting substrate, not from the pre-gate proposal.

## 15. Gate handoff

The architecture review should return:

- the ADR;
- a contract diff before and after Gate A;
- deleted APIs and paths;
- retained provisional items and their next gate;
- study evidence table;
- storage and cost observations;
- lifecycle integration requirements;
- unresolved research questions;
- a clear pass, pass-with-changes, hold, or reject decision.
