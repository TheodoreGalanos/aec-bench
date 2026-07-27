# ABOUTME: Freezes the ASW-0A implementation baseline, source inventory, repository ownership, and dependency guardrails.
# ABOUTME: Records planning authority and known drift without defining a stewardship runtime, schema, or compatibility contract.

# ASW-0A baseline and authority record

| Field | Value |
| --- | --- |
| Stage | `ASW-0A — baseline, PRD durability, and authority census` |
| Status | ASW-0A accepted; ASW-0B1 is the next permitted stage |
| Recorded | 2026-07-27 |
| Scope | Asset Stewardship Worlds programme only |
| Runtime-contract status | This document is not a runtime contract, persisted runtime schema, public API, or compatibility promise |

## Scope

ASW-0A establishes:

- one reproducible post-PR24 implementation baseline;
- the exact source and planning inputs used for subsequent design;
- an authority precedence for resolving conflicts;
- a repository-owner map;
- an approved dependency direction and a no-new-upward-dependency rule;
- an initial register of existing and conceptual boundaries;
- a narrow durability decision for the ASW planning authorities;
- a file allowlist and gate assessment for this stage; and
- one focused removal restoring the repository's existing documentation-ownership
  boundary.

The record distinguishes implemented behavior, normative constraints, staged planning
authority, and supporting research. A file's presence, serializability, content hash,
or prior use does not by itself promote that file into a repository contract.

## Non-goals

ASW-0A does not:

- implement asset state, clocks, deterioration, events, actions, authority,
  obligations, projections, persistence, tools, Harbor execution, or evaluation;
- freeze the pump profile, claims, evidence, rights, software roles, synthetic
  generation protocol, certification protocol, or research design;
- define new schema names, field names, discriminators, registry identifiers,
  CLI commands, persisted layouts, or `TrialRecord` fields;
- change `ARCHITECTURE.md`, `PROJECT_STRUCTURE.md`, `AGENTS.md`, `CONTRACTS.md`,
  `INVARIANTS.md`, implementation code, tests, or existing task packages; the
  sole `docs/` change removes the unreferenced, non-authoritative
  `ssc03-model-selected-intervention.md` survivor rather than changing a
  normative document;
- repair pre-existing dependency cycles or unrelated documentation drift;
- treat lifecycle, proposal-session, task-world-review, adaptive-repair, or
  factorial-study machinery as a persistent maintenance-world implementation;
- promote supporting research notes or the external pump dossier into runtime
  inputs; or
- make a repository-wide test, release-readiness, or benchmark-readiness claim.

## Frozen implementation baseline

| Identity | Value |
| --- | --- |
| Merged pull request | [PR 24 — Add governed adaptive meta-harness](https://github.com/TheodoreGalanos/aec-bench/pull/24) |
| Merge commit | `fdc6215c39add79d4a5549a1bfc058d9baac1b54` |
| Commit tree | `730594c69662369eea08f3e96274dc59778bca38` |
| First parent | `9639eea7115b047ad4c8fddb0479c4b98438aba7` |
| Second parent | `b613335077eb53bfbba64662e0cba2e12a0c6099` |
| ASW branch | `feat/asset-stewardship-asw-0a` |
| ASW worktree | `/Users/theodoros.galanos/LocalProjects/aec-bench/.worktrees/asset-stewardship-asw-0a` |
| Upstream at creation | `origin/main` at `fdc6215c39add79d4a5549a1bfc058d9baac1b54` |

The ASW derivative was created from the exact merged commit. At creation:

- `HEAD` resolved to the merge commit above;
- `HEAD^{tree}` resolved to the tree above;
- the tracked working tree had no modified or deleted paths; and
- the worktree had no untracked source paths.

ASW-0A changes occur only after this identity was captured and only inside the
stage allowlist below.

## Source inventory

### Authority-document Git objects

These object IDs bind the exact normative and operating guidance inspected at the
frozen commit.

| Path | Git object ID |
| --- | --- |
| `docs/AGENTS.md` | `5711f52204f3307438c3842b01c5ea680b438276` |
| `docs/ARCHITECTURE.md` | `ffcd361b568e8b000ff37cc031a541e218c0999b` |
| `docs/CONTRACTS.md` | `a2213ca815a3b619ff99330f5a86d2712c3e0dfd` |
| `docs/INVARIANTS.md` | `749c81fa7cb85a584dca0a0ecd42ee3baafc15aa` |
| `docs/PROJECT_STRUCTURE.md` | `4bf49949b3015992719c506caf76d2d9996f6572` |

### Relevant implementation Git objects

Directory entries are Git tree objects. File entries are Git blob objects.

| Path | Kind | Git object ID |
| --- | --- | --- |
| `src/aec_bench/contracts/` | tree | `bf8ae59381dbddeab9c97fe1e01848ccdb192039` |
| `src/aec_bench/task_world_templates/` | tree | `074c19ebab8d17a990aa65bd6f99ed31c814724f` |
| `src/aec_bench/meta_harness/` | tree | `14ba36b967b3aebb9980215148c8dca0ad3caba3` |
| `src/aec_bench/harness/` | tree | `97d574245c3b274c64fff020d3352901d32de273` |
| `src/aec_bench/evaluation/` | tree | `e886b5521dd80ddb64a9dc108a0c01b923cf841f` |
| `src/aec_bench/providers/` | tree | `6fa6441ca413a8bd0fd2367a3e6225cc711ee21d` |
| `agents/entrypoint_agent.py` | blob | `7ec9092ff3396a8c25af1c614071672da89a3da5` |
| `tests/` | tree | `218cae579e2b1629dbe46c2eed20f6fbd1a08589` |

### Removed baseline-only documentation artifact

| Path | Frozen-baseline blob | History and ASW-0A disposition |
| --- | --- | --- |
| `docs/ssc03-model-selected-intervention.md` | `59307860e26c327e50658752a31442ac28a5a42a` | Added by `f575caa6d0c5a83ce1caffd5eb5ebd1ba72e0227`; already present before PR24; unreferenced in the frozen baseline by tracked code, tests, workflows, README, and Markdown; removed under Theo's explicit direction because PR24's documentation-ownership policy permits only the five normative repository documents |

The removal deletes only a standalone explanatory guide. The implemented
`hydraulic-design-response-lifecycle-review` task, its catalogue registration,
runtime, and tests remain unchanged.

### Pre-promotion ignored planning inputs

These SHA-256 values identify files from the prior adaptive-meta-harness worktree.
They were excluded by the repository-wide `research/` ignore rule and were absent
from the clean ASW derivative at creation. Recording their hashes preserves their
input identity; it does not make every input durable or authoritative.

| Input | SHA-256 | ASW-0A treatment |
| --- | --- | --- |
| `research/asset-stewardship/asset-stewardship-worlds-prd.md` | `4d165a21db39fe310f036906ccc59c223cdba3a7960c39bb4a22d42096528584` | Promote into the narrow durable allowlist; final promoted bytes are recorded separately below |
| `research/asset-stewardship/temporal-evidence-frontier-prd.md` | `88a188695cd8ebcd4bd31e0b93efce07d574c96d6d4c667ccbc31123ea1e41cd` | Promote into the narrow durable allowlist; final promoted bytes are recorded separately below |
| `research/adaptive-meta-harness/notes/fixed-k-adaptive-meta-harness.md` | `d3cc1e9df080f56ce77ba9f2445503dac5a9f0e43b8f1f00d98579d71205b68d` | Supporting precedent only; remains ignored and untracked |
| `research/adaptive-meta-harness/notes/implementation-inventory.md` | `f14610daaaa25ad4b9d0766fdf338fd51c719b02b01a678b8adebb9ac8a015b3` | Supporting implementation audit only; remains ignored and untracked |
| `research/ssc03/notes/interactive-hydraulic-lifecycle.md` | `8b57e29ca0f0e575d15f8cd4420fcc83fd576364afe0215c253fffea0685fd01` | Supporting lifecycle precedent only; remains ignored and untracked |

### External reference

| Path | SHA-256 | Classification |
| --- | --- | --- |
| `/Users/theodoros.galanos/Downloads/duty-standby-pump-reference-asset-research-dossier.md` | `092dc798206bdefa13b1138c955be33399bf24bf66340b4503f928854cb93b39` | Reference-only input for later ASW-0B work; rights and source treatment are deferred to ASW-0B2; not a durable repository input or runtime dependency |

The external dossier is not copied, imported, packaged, or promoted by ASW-0A.

## Working-surface classification

| Class | Frozen-baseline finding | Authority treatment |
| --- | --- | --- |
| Tracked | The complete Git tree `730594c69662369eea08f3e96274dc59778bca38` at commit `fdc6215c39add79d4a5549a1bfc058d9baac1b54` | Reproducible current implementation baseline |
| Modified | None when the ASW derivative was created | No modified path contributes to the baseline |
| Deleted | None when the ASW derivative was created | No deleted path contributes to the baseline |
| Untracked | None when the ASW derivative was created | No untracked path contributes to the baseline |
| Ignored repository-local runtime files | `.venv/`, `.pytest_cache/`, and Python cache directories may be produced locally | Disposable; never source, evidence, or contract authority |
| Ignored research inputs | The five hash-pinned files listed above existed in the prior worktree under ignored `research/` paths | Only the two PRDs and this record are deliberately promoted; support notes remain ignored |
| External | The pump research dossier listed above resides outside the repository | Reference only; cannot affect runtime or claims until later rights/evidence gates accept an explicit derivative |

The explicit ASW-0A delta removes the baseline-only documentation artifact
recorded above. It does not redefine the frozen baseline; it is an allowlisted
repair relative to that baseline.

Any later baseline claim must compare its complete name-status and ignored-surface
classification to this record rather than assuming a clean tree from a branch name.

## Authority precedence

Authority is purpose-specific. When sources disagree, the programme applies this
order and fails closed rather than silently choosing the most convenient source.

1. **Implemented behavior:** the exact Git objects at the frozen commit plus
   deterministic tests and validated persisted artifacts define what the merged
   repository currently does.
2. **Non-negotiable constraints:** `docs/INVARIANTS.md` governs validity,
   reproducibility, contracts, hidden state, task-adapter independence,
   evaluation ownership, holdout separation, provider isolation, and staged
   lifecycle safety.
3. **Boundary semantics:** `docs/CONTRACTS.md` governs existing cross-domain
   payload meanings and compatibility obligations.
4. **Repository intent:** `docs/ARCHITECTURE.md`, `docs/PROJECT_STRUCTURE.md`,
   and `docs/AGENTS.md` govern intended domain ownership and dependency
   direction, subject to the recorded code/document drift below.
5. **ASW staged direction:** once promoted with final hashes, the parent PRD and
   its companion govern the future Asset Stewardship Worlds sequence. They remain
   subordinate to repository invariants and do not retroactively redefine an
   existing contract.
6. **This ASW-0A record:** governs the programme's baseline, owner map,
   dependency guardrail, planning-input durability, and initial boundary
   classifications. It does not govern runtime payloads.
7. **Supporting notes and external research:** ignored notes, dossiers, solver
   outputs, generated material, and experiments are evidence or reference
   candidates only. They have no runtime, API, compatibility, or claim authority.

Neither immutable bytes nor a passing report proves semantic authority. If live
code and normative guidance disagree, the disagreement is recorded and a later
stage must make an explicit architecture decision; ASW code must not exploit the
gap.

## Repository owner map

| Surface | Authoritative responsibility | ASW rule |
| --- | --- | --- |
| `src/aec_bench/contracts/` | Stable cross-domain schemas, validators, canonical identities, and compatibility-bearing references | Add only the minimum boundary exercised by a real same-stage producer and consumer; no asset physics, world policy, or speculative export |
| Top-level `tasks/` and `src/aec_bench/tasks/` | Declarative runnable task data, loading, lifecycle, selection, and registry behavior | Remain data and task management; executable maintenance physics does not live here |
| `src/aec_bench/task_world_templates/` | Task-specific world packages, materialization, task-family execution, and task-owned verification | The first stewardship implementation remains asset-local here; it does not create a new top-level domain |
| `src/aec_bench/harness/` | Provider-neutral orchestration, sessions, adapter execution, Harbor dispatch/import, recovery composition, and `TrialRecord` construction | May consume strict boundary values; owns neither asset physics nor task-verifier or study-metric policy |
| `src/aec_bench/adapters/` | Provider-neutral model protocol translation and task-declared tool execution | No task-type branches, asset semantics, scoring, or stewardship policy |
| `src/aec_bench/providers/` | Vendor-specific compute and transport implementations | Outer implementation only; no asset-world semantics and no dependency from the asset kernel |
| `src/aec_bench/meta_harness/` | Adaptive experiment control, fixed-kernel compilation, lifecycle hosting, governed evidence, and study coordination | May coordinate an approved later experiment; does not own persistent asset truth, clocks, maintenance actions, the task verifier, or ASW study-local schemas |
| `src/aec_bench/ledger/` | Append-only trial persistence and durable publication primitives | Harness/composition supplies persistence; the pure asset kernel does not import a ledger implementation |
| `src/aec_bench/evaluation/` | Post-import validity, metric derivation, aggregation, and confidence over frozen evidence | Consumes immutable evidence and never mutates or calls back into the world |
| `agents/entrypoint_agent.py` | Harbor composition root and explicit dispatch into library execution paths | Thin host dispatch only; no asset physics or evaluation policy |
| `src/aec_bench/cli/` | User-facing composition over library entrypoints | Thin commands only; no independent source of world or study semantics |
| Versioned experiment packages | Study-local manifests, plans, runners, reducers, and reports | Consume frozen harness/evaluation evidence; remain local until a later independent reuse decision |

The following placements are explicitly not approved:

- a new `src/aec_bench/worlds/` package;
- stewardship state or physics in adapters, providers, harness, evaluation,
  `meta_harness`, CLI, or top-level task data;
- asset-local types re-exported from `contracts/__init__.py`;
- a global registry entry before its real integration stage; and
- production imports from research, generated, temporary, staging, mutable-run,
  or external dossier paths.

## Approved dependency direction

The direction below is the ASW programme's approved graph. An arrow reads
"may depend on."

```text
asset-local stewardship kernel
  -> contracts and its own asset-local modules only

harness session, Entrypoint bridge, Harbor export/import
  -> contracts + adapters + ledger primitives + a narrow task-world boundary

evaluation
  -> contracts + immutable TrialRecord/harness outputs

versioned stewardship study
  -> frozen harness/evaluation evidence

CLI and delivery composition
  -> corresponding library entrypoints

meta-harness coordination
  -> approved lower-level experiment surfaces only
```

The asset-local kernel must not import `meta_harness`, harness, evaluation,
adapters, providers, CLI, study code, or vendor SDKs. Evaluation must not call
the world to reconstruct or improve an outcome. Provider selection must not
change asset semantics. The finite `ExecutionProgram` may schedule an evaluation
window; it does not represent simulated time or the asset state machine.

### No-new-upward-dependency rule

Every ASW stage must compare its new imports against the graph above. A new edge
outside the graph is a blocking architecture finding, even when an older module
already contains a similar edge. Existing cycles are recorded legacy exceptions,
not precedent. They may be repaired only in a separately allowed change with its
own compatibility evidence; ASW work must not deepen, generalize, or copy them.

## Documented architecture and import drift

The frozen code and the normative package maps are not fully aligned. ASW-0A
records this drift without repairing or legitimizing it.

| Drift | Representative evidence | ASW consequence |
| --- | --- | --- |
| The seven-domain architecture omits merged task-world and meta-harness surfaces | `docs/ARCHITECTURE.md`; `docs/PROJECT_STRUCTURE.md`; `docs/AGENTS.md` includes task worlds but not the meta-harness | Their existence does not automatically create a reusable domain or authorize a new `worlds` package |
| Task-world lifecycle code imports meta-harness code, while meta-harness code imports task-world contracts | `src/aec_bench/task_world_templates/compiled_world.py`; `src/aec_bench/meta_harness/evidence_request_store.py` | Existing lifecycle coupling is frozen; the stewardship kernel must not copy it |
| Harness proposal-session code imports meta-harness compilation, while meta-harness study runtimes import harness | `src/aec_bench/harness/proposal_session_runtime/preparation.py`; `src/aec_bench/meta_harness/motif_transfer_runtime.py` | Existing experiment coupling is not a stewardship session architecture |
| Harness imports an evaluation reviewer despite the documented Harness-to-Evaluation direction | `src/aec_bench/harness/harbor_workflow.py`; `src/aec_bench/evaluation/llm_reviewer.py` | Stewardship evaluation stays downstream of immutable imported evidence |
| Provider modules import harness modules despite providers being documented as internally independent | `src/aec_bench/providers/proposal_morph_cloud.py`; `src/aec_bench/providers/morph_harbor.py` | Stewardship domain code must remain vendor-independent; provider wiring stays at the outer composition boundary |
| The hydraulic package imports ledger durability despite hydraulics being summarized as contracts-only | `src/aec_bench/task_world_templates/hydraulics/package.py` | Reuse the asset-local ownership precedent, not this persistence dependency; the stewardship kernel remains persistence-agnostic |
| Harbor import currently derives an execution kind from an `adapter` parameter | `src/aec_bench/harness/harbor_importing/registry.py` | Do not copy this conflation; a separate host-owned boundary, if required, is designed and promoted only in its later stage |
| Existing "world" names describe different semantics | `src/aec_bench/contracts/task_world.py`; `src/aec_bench/contracts/run_bundle.py`; `src/aec_bench/meta_harness/world_process.py`; `src/aec_bench/meta_harness/world_runtime.py` | `TaskWorldProfile`, `WorldSnapshotRef`, prose world cards, and finite lifecycle state are not persistent maintenance truth |

Correcting the normative package maps or current import structure may be
worthwhile, but it is outside this stage's allowlist. The focused removal of a
non-authoritative guide does not alter those maps or legitimise any import edge.
No future ASW document may cite this table as approval to preserve a new cycle.

## Seeded boundary register

This register names existing boundaries and only the minimum conceptual seams
required to assign future ownership. Conceptual rows deliberately do not reserve
schema names or fields.

| Boundary | Current producer and consumer | Semantic authority | Persistence and visibility | Maturity | ASW treatment and first possible stage |
| --- | --- | --- | --- | --- | --- |
| `TaskWorldProfile` | Task sidecar/default profile -> evaluation reviewer | Contracts define shape; evaluation owns review use | Public task/review material | Existing repository contract | Preserve as review semantics; do not extend into physical world state |
| `CompositeTaskWorldTemplate` and `EvidenceLifecycleSpec` | Task-world catalogue/materializer -> lifecycle host and verifier | Task-world lifecycle package | Public package plus host/private lifecycle material | Existing lifecycle-specific contract-bearing surface | Freeze through ASW-0 to ASW-4; not the stewardship base |
| `CompiledWorldEnvelope` and `WorldSnapshotRef` | Task-world compiler -> run-bundle/export consumers | Task-world compilation and Contracts respectively | Content-pinned static package identity | Existing repository contracts | Preserve static meaning; a dynamic state reference, if necessary, is a later separate boundary |
| `LifecycleEpisodeRequest` and `LifecycleEpisodeResult` | Lifecycle host -> episode environment -> lifecycle host | Meta-harness lifecycle host | Per-attempt, visibility-controlled evidence | Existing lifecycle-specific repository contract | Preserve checkpoint semantics; do not reinterpret completion as asset termination |
| `ExecutionBundle` and `AdapterResult` | Harness -> Entrypoint/adapter -> harness | Harness owns execution request/result transport; adapters own protocol translation | Run-local then imported execution evidence | Existing repository boundary | Reuse provider-neutral execution behavior only; exact stewardship session seam is deferred to ASW-1/ASW-2C |
| `ImportEvidenceExtension` | Harbor result context -> execution-specific loader -> core importer | Harness import boundary | Host-side import evidence | Existing boundary candidate used by proposal execution | Reuse fail-closed extension pattern only; any stewardship consumer appears with Harbor integration at ASW-2D |
| `TrialRecord` | Harness importer/builder -> ledger -> evaluation | Contracts own schema; harness owns construction; ledger owns append-only storage | Ledger-persisted with explicit visibility | Existing repository contract | No ASW field during ASW-0/ASW-1; minimum additive evidence appears only with its producer/reloader at ASW-2D |
| `EvaluationResult` | Evaluation -> communication/feedback | Evaluation and Contracts | Persisted or derived scored result | Existing repository contract | Stewardship metric additions require imported immutable evidence at ASW-2E |
| Hydraulic source/package/run/verifier values | Hydraulic task-world builder/executor -> independent task verifier | `task_world_templates/hydraulics/` | Public task-family package and run evidence | Existing asset-local/task-family contract | Ownership and independent-verifier precedent only; no shared stewardship ABI |
| Research-to-runtime asset package exchange | Approved promotion evidence -> strict asset-local reader | Asset package and promotion authority | Rights-cleared, content-addressed runtime input; research inputs excluded | Conceptual | Exact artifact design occurs in later ASW-0B work; first production consumer cannot precede ASW-2A0 |
| Asset kernel transition exchange | Asset-local kernel -> asset-local state machine/host composition | Reference-asset package | In-memory until a durable repository exists | Conceptual | No schema in ASW-0A; asset-local producer/consumer may be exercised in ASW-2A |
| World persistence exchange | Asset state machine -> harness-supplied repository -> reloader | Asset package owns semantics; harness owns publication transaction | Immutable host evidence with separate visibility classes | Conceptual | No schema in ASW-0A; first durable producer/reloader may appear at ASW-2B |
| Direct world-session exchange | Harness host session <-> asset-local runtime | Harness owns session; asset package owns world semantics | Run-local then immutable evidence | Conceptual | Exact boundary may be designed at ASW-1 and exercised no earlier than ASW-2C |
| Harbor world-session import exchange | Entrypoint/Harbor output -> strict harness importer | Harness | External-ingestion boundary, then immutable imported evidence | Conceptual | Exact boundary and execution discrimination appear together no earlier than ASW-2D |
| Stewardship evaluation exchange | Imported immutable trial evidence -> evaluation metrics and integrity gates | Evaluation | Derived, recomputable evidence; cannot rewrite verifier outcome | Conceptual | Exact consumer appears no earlier than ASW-2E |
| Continuity-study exchange | Frozen eligible records -> versioned study runner/reducer | Study-local experiment package | Study-local content-addressed artifacts | Conceptual | Remains outside the walking skeleton; no core-contract promotion without later demonstrated reuse |

Before implementing any conceptual row, the later stage must add its real producer,
consumer, authority, validation, compatibility, failure, visibility, persistence,
and test evidence. A field with no same-stage producer or consumer is removed
rather than reserved.

## Durability decision

The former `research/` ignore rule was too broad for the three programme
authorities that must survive worktrees and commits. ASW-0A therefore narrows the
exception to exactly one directory and exactly three Markdown files:

```gitignore
research/*

!research/asset-stewardship/
research/asset-stewardship/*
!research/asset-stewardship/asw-0a-baseline-and-authority.md
!research/asset-stewardship/asset-stewardship-worlds-prd.md
!research/asset-stewardship/temporal-evidence-frontier-prd.md
```

All other research material remains ignored. In particular, the adaptive
meta-harness implementation notes, the SSC-03 lifecycle note, research spikes,
engine investigations, generated files, solver outputs, and the external dossier
do not become tracked implementation inputs.

### Promoted planning-authority identities

| Durable file | Planning role | Final promoted SHA-256 |
| --- | --- | --- |
| `research/asset-stewardship/asset-stewardship-worlds-prd.md` | Parent ASW programme authority | `56d6fe6a9c69796d819a1995ae63a85392ba85a4240df8baa87df99a76678335` |
| `research/asset-stewardship/temporal-evidence-frontier-prd.md` | Conditional companion authority | `6d1bcd4e8ea83993b7e1e93e16e7dc645c79eb8fd4f716db96fcf1be968157e7` |

The ASW-0A record does not embed its own file hash. Its committed Git blob and
containing commit provide its non-self-referential identity. The two PRD
identities above were computed only after their promoted copies were stable.

## First-stage file allowlist

Only these paths may differ from the frozen commit during ASW-0A:

1. `.gitignore`
2. `research/asset-stewardship/asw-0a-baseline-and-authority.md`
3. `research/asset-stewardship/asset-stewardship-worlds-prd.md`
4. `research/asset-stewardship/temporal-evidence-frontier-prd.md`
5. `docs/ssc03-model-selected-intervention.md` (delete only)

Any other tracked, deleted, or untracked source path is a stage failure. Ignored
environment and cache output remains disposable and must not be staged.

## Acceptance evidence

### Merge and focused hydraulic evidence

- PR24 is merged into `main` at
  `fdc6215c39add79d4a5549a1bfc058d9baac1b54`.
- Its exact merge tree is
  `730594c69662369eea08f3e96274dc59778bca38`.
- The PR24 GitHub Actions check
  [`deterministic-hydraulic-world`](https://github.com/TheodoreGalanos/aec-bench/actions/runs/30230854272/job/89869345140)
  succeeded. This is focused evidence for the existing deterministic hydraulic
  precedent, not evidence for a stewardship implementation.

### Documentation-ownership diagnostic and focused repair

The diagnostic was first run against the frozen source and again after the
ASW-0A authority files were reconciled:

```text
uv run pytest tests/docs/test_documentation_ownership.py -q
```

Both baseline runs produced:

```text
1 failed, 2 passed
```

The failure was caused by the tracked
`docs/ssc03-model-selected-intervention.md` path violating the ownership test's
expected surface. Git history shows that the guide was added before PR24, while
PR24 later introduced the narrow ownership test and removed other
non-authoritative guide material. A repository-wide reference audit found no
consumer of the path or its title.

Theo explicitly authorised deletion of the surviving guide. ASW-0A added that
single deletion to its allowlist, left the ownership test and all normative
documents unchanged, and reran the same command. Post-removal result:

```text
3 passed
```

## Gate assessment

| Gate | Assessment |
| --- | --- |
| Reproducible source baseline | Pass: exact commit, parents, tree, branch, worktree, and relevant Git objects recorded |
| Relevant surface classification | Pass: tracked, modified, deleted, untracked, ignored, and external inputs classified |
| Planning-input identity | Pass: five ignored inputs and the external dossier are hash-pinned and authority-classified |
| PRD durability | Pass: both promoted PRD copies are stable and their final SHA-256 identities are recorded |
| Repository ownership | Pass for ASW planning: owner map and exclusions recorded |
| Dependency direction | Pass for ASW planning: approved graph and no-new-upward-dependency rule recorded |
| Boundary discipline | Pass for ASW planning: existing meanings preserved and future seams remain conceptual |
| Focused existing hydraulic evidence | Pass: PR24's deterministic hydraulic-world check succeeded |
| Documentation ownership | Pass after focused root-cause repair: the initial `1 failed, 2 passed` baseline is recorded; the unchanged ownership test now reports `3 passed` |
| Stewardship implementation | Intentionally absent |
| Repository-wide green state | Not claimed |
| ASW-0A final acceptance | Pass: baseline, durability, ownership, dependency, boundary, allowlist, and focused diagnostic gates are satisfied |

ASW-0A acceptance certifies only the baseline, durability decision, ownership,
dependency guardrail, and boundary-register seed. It does not certify the
reference asset, evidence rights, synthetic world, runtime, evaluation, study, or
repository-wide test state. It authorises only separately reviewed ASW-0B1 as
the next stage; no later stage opens by implication.
