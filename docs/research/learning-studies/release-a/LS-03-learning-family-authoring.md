# LS-03 — Artifact Learning-Family and Relation Authoring

**Status:** Proposed
**Type:** Implementation PRD
**Release:** Learning Studies Release A
**Depends on:** LS-01A and LS-02B
**Blocks:** Artifact study protocols and LS-04A end-to-end pilots
**Primary owner:** `aec_bench.experimentation.learning_studies`
**Task semantics owner:** Existing task families and their BRIEFs
**Repository baseline:** `main`, reviewed 22 August 2026

## 1. Purpose

Add an optional, reviewable overlay that says how existing tasks are related for a learning study.

AEC-Bench already supports parameterised generation and adaptation axes. Those mechanisms answer:

> Which task variants can be materialised?

A learning study must additionally answer:

> Which properties should remain useful across variants, which properties changed, and what behaviour would demonstrate transfer or harmful over-application?

This PRD adds those semantics without changing task definitions, generators, or execution.

## 2. Design principle

A task remains self-contained and runnable without learning metadata.

```text
existing task family and BRIEF
             │
             ├── ordinary task execution
             │
             └── optional LearningFamilySpec overlay
                    describes study relationships only
```

Deleting the overlay must leave every task and verifier unchanged.

## 3. Goals

1. Name exact existing tasks as members of a learning family.
2. Describe relevant variation dimensions and their learning role.
3. Author directed transfer, boundary, retention, interference, and composition relations.
4. Separate machine-checkable member differences from prose domain claims.
5. Mark probe-only members to reduce acquisition contamination.
6. Resolve family aliases to exact task IDs before study compilation.
7. Use a small TOML format and standard-library parser.
8. Avoid a central graph database or automatic similarity system.

## 4. Non-goals

This PRD does not:

- infer relations from embeddings;
- change `VariationAxis` or `AdaptationSpec`;
- create new task instances;
- establish a universal AEC mechanism ontology;
- score tasks;
- select a curriculum adaptively;
- add task fields to `task.toml`;
- make learning-family membership mandatory.

## 5. Authored file placement

A family file is an explicit input to a study protocol. It is not registered globally.

Maintained repository-owned studies use one task-like protocol directory:

```text
src/aec_bench/experimentation/learning_studies/protocols/<study-id>/
├── study.toml
└── family.toml
```

The generic loader composes `family.toml` into the executable study contract.
Real research configurations may live in a caller-owned project or workspace
and are supplied as a protocol directory path.

Do not add a second repository-wide task catalogue.

## 6. File format

Use TOML, parsed with the standard library’s `tomllib`, because:

- the repository already uses TOML for task and project configuration;
- strict nested data is sufficient;
- no new dependency is required;
- diffs remain readable.

## 7. Contract

Add a provisional strict model in a focused module such as:

```text
src/aec_bench/contracts/learning_family.py
```

Gate A decides whether every part deserves long-term shared-contract status.

### 7.1 Dimension kinds

```python
class LearningDimensionKind(StrEnum):
    SURFACE = "surface"
    PARAMETER = "parameter"
    CAUSAL = "causal"
    APPLICABILITY = "applicability"
    OBSERVABILITY = "observability"
    AUTHORITY_OR_RESOURCE = "authority_or_resource"
    REGIME = "regime"
    COMPONENT = "component"
```

These kinds are study-design vocabulary. They do not control task execution.

### 7.2 Dimension declaration

```python
class LearningDimensionSpec(StrictModel):
    dimension_id: NonEmptyStr
    kind: LearningDimensionKind
    description: NonEmptyStr
```

### 7.3 Family member

```python
class LearningFamilyMember(StrictModel):
    member_id: NonEmptyStr
    task_id: NonEmptyStr
    description: str | None = None
    probe_only: bool = False
    dimension_values: dict[NonEmptyStr, NonEmptyStr]
```

Release A uses exact task IDs only.

Selectors over generated families, difficulties, datasets, or predicates are deferred until exact-task pilots prove they are needed.

### 7.4 Relation

```python
class LearningFamilyRelation(StrictModel):
    relation_id: NonEmptyStr
    purpose: ExperienceRelationPurpose
    source_member_ids: tuple[NonEmptyStr, ...]
    target_member_id: NonEmptyStr
    invariant_dimensions: tuple[NonEmptyStr, ...] = ()
    invariant_claims: tuple[NonEmptyStr, ...]
    changed_dimensions: tuple[NonEmptyStr, ...]
    rationale: NonEmptyStr
```

### 7.5 Family

```python
class LearningFamilySpec(StrictModel):
    family_id: NonEmptyStr
    title: NonEmptyStr
    description: NonEmptyStr
    source_brief_paths: tuple[NonEmptyStr, ...]
    dimensions: tuple[LearningDimensionSpec, ...]
    members: tuple[LearningFamilyMember, ...]
    relations: tuple[LearningFamilyRelation, ...]
```

`source_brief_paths` makes the domain basis reviewable. It is documentary and does not make the learning layer authoritative over the BRIEF.

## 8. Example TOML

```toml
family_id = "example-pipe-method"
title = "Pipe calculation representation transfer"
description = "Tests whether the same governing calculation transfers across presentation changes and is withheld when the governing condition changes."
source_brief_paths = ["tasks/civil/example/BRIEF.md"]

[[dimensions]]
dimension_id = "presentation"
kind = "surface"
description = "How inputs are represented to the agent"

[[dimensions]]
dimension_id = "governing_method"
kind = "causal"
description = "The engineering method required for a correct result"

[[dimensions]]
dimension_id = "diameter_band"
kind = "parameter"
description = "Numerical parameter range"

[[members]]
member_id = "acquisition-a"
task_id = "civil/example/a"
probe_only = false

[members.dimension_values]
presentation = "table"
governing_method = "method-m"
diameter_band = "small"

[[members]]
member_id = "transfer-b"
task_id = "civil/example/b"
probe_only = true

[members.dimension_values]
presentation = "drawing"
governing_method = "method-m"
diameter_band = "large"

[[members]]
member_id = "boundary-c"
task_id = "civil/example/c"
probe_only = true

[members.dimension_values]
presentation = "table"
governing_method = "method-n"
diameter_band = "small"

[[relations]]
relation_id = "a-to-b-transfer"
purpose = "transfer"
source_member_ids = ["acquisition-a"]
target_member_id = "transfer-b"
invariant_dimensions = ["governing_method"]
invariant_claims = ["The same calculation method remains valid despite the representation and value change."]
changed_dimensions = ["presentation", "diameter_band"]
rationale = "Separates method transfer from surface familiarity."

[[relations]]
relation_id = "a-to-c-boundary"
purpose = "boundary"
source_member_ids = ["acquisition-a"]
target_member_id = "boundary-c"
invariant_dimensions = ["presentation", "diameter_band"]
invariant_claims = ["The problem remains superficially similar to acquisition-a."]
changed_dimensions = ["governing_method"]
rationale = "Tests whether prior success causes inappropriate reuse of method-m."
```

## 9. Validation

### 9.1 Identity and reference validation

Reject:

- duplicate dimension, member, or relation IDs;
- unknown dimension references;
- unknown source or target members;
- source equal to target;
- duplicate task ID under different member IDs unless the file explains a deliberate repeated role;
- a family with fewer than two members.

### 9.2 Dimension-value validation

Every member must provide a value for every declared dimension in Release A.

For each relation:

- every `invariant_dimension` has equal values across all sources and target;
- every `changed_dimension` differs between at least one source and the target;
- a dimension cannot be both invariant and changed;
- all dimension IDs resolve.

This validates the authored table, not the underlying engineering claim.

### 9.3 Purpose validation

- transfer: exactly one source, at least one invariant dimension or claim, target ordinarily probe-only;
- boundary: exactly one source and at least one changed dimension of kind `applicability` or `causal`;
- composition: at least two sources and at least one component dimension or explicit component claim;
- retention: one source and one later target that may reference the same task or a structural transfer member;
- interference: one source and one target plus a study protocol that inserts the interfering experience.

### 9.4 Probe holdout validation

A `probe_only` member:

- may appear as a probe target;
- may not appear in an acquisition or practice step;
- may not be included in learner-visible family documentation or consolidation inputs;
- may be resolved by the host when compiling the probe.

The family file itself is host-held unless a study deliberately publishes a safe subset.

## 10. Resolution API

Provide functions such as:

```python
def load_learning_family(path: Path) -> LearningFamilySpec:
    ...


def resolve_learning_family(
    family: LearningFamilySpec,
    resolve_task: Callable[[str], ResolvedTaskInstance],
) -> ResolvedLearningFamily:
    ...


def relation_to_experience_specs(
    family: ResolvedLearningFamily,
    relation_id: str,
) -> ResolvedLearningRelation:
    ...
```

The resolved value contains exact task identities and is used by study-protocol builders. It does not execute tasks or silently generate arms.

## 11. Relationship to `AdaptationSpec`

Do not modify the current adaptation contracts in Release A.

A later helper may author a family from deterministic generated variants, but the separation remains:

```text
AdaptationSpec
  generates or enumerates candidate task variants

LearningFamilySpec
  states what selected variants mean for a learning study
```

An axis name and values are not enough to establish transfer semantics.

## 12. Review workflow

Every family used for a controlled claim requires two reviews:

### Domain review

Confirms:

- invariant claims are technically correct;
- boundary case genuinely changes the method or applicability;
- target task remains fair and fully specified;
- composition task truly requires the declared components.

### Benchmark review

Confirms:

- probe-only content is protected;
- task IDs resolve;
- verifier projections support the planned outcomes;
- no acquisition task exposes the answer to its probe;
- difficulty and ceiling/floor risk are acceptable.

Record reviewer names in the study protocol or PR review, not as a new mandatory family-schema provenance block.

## 13. File changes

Expected additions:

```text
src/aec_bench/contracts/learning_family.py
src/aec_bench/experimentation/learning_studies/families.py
tests/contracts/test_learning_family.py
tests/experimentation/learning_studies/test_families.py
src/aec_bench/experimentation/learning_studies/protocols/<study-id>/family.toml
```

Do not modify:

```text
src/aec_bench/contracts/adaptation.py
task.toml schemas
task generators
```

## 14. Test matrix

### Parsing tests

- valid TOML round-trip;
- unknown fields rejected;
- malformed member table rejected;
- no new YAML/TOML dependency.

### Semantic validation tests

- invariant values match;
- changed values differ;
- boundary changes causal or applicability dimension;
- composition has several sources;
- probe-only member rejected in acquisition role;
- unresolved task ID identifies member.

### Integration tests

- resolved relation produces exact `LearningExperienceSpec` inputs;
- same task remains runnable with family file absent;
- adaptation contracts remain unchanged.

### Security tests

- host family file is not automatically staged into learner workspace;
- probe-only task instruction is not exposed during acquisition or consolidation.

## 15. Acceptance criteria

LS-03 is complete when:

1. A strict TOML family file can describe exact artifact tasks and their learning relationships.
2. Machine-checkable invariant and changed dimensions are validated.
3. Domain meaning remains an authored, reviewable claim rather than an inferred property.
4. Probe-only members cannot enter acquisition or learner-visible materials.
5. Family resolution produces exact task IDs for ordinary study compilation.
6. Existing task, adaptation, generation, and verifier contracts remain unchanged.
7. At least two real artifact families are authored before Gate A.
8. No graph database, embedding search, global ontology, or automatic curriculum is added.

## 16. Agent handoff

The implementation agent should return:

- final TOML schema and examples;
- exact validation rules;
- two candidate real task families found in the repository, with domain-review questions clearly marked;
- proof that probe-only members remain host-held;
- proof that tasks run identically with the overlay removed;
- any dimension kind not used by real families, for deletion at Gate A.
