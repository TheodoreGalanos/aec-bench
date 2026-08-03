---
name: domain-check
description: Verify that code changes respect aec-bench architectural invariants and domain boundaries. Use when modifying files under src/aec_bench/, adding new modules, changing contracts or data shapes, working across multiple domains, or before committing changes. Also trigger when the user asks to "check domains", "verify architecture", "validate invariants", or "review boundaries".
---

# Domain Check

Check a changeset against the current AEC-Bench architecture, protected
contracts, and benchmark invariants. Judge ownership and behaviour from the
live repository; package paths are signals, not a fixed dependency diagram.

## When to use

- Before a requested commit that changes `src/aec_bench/`
- After a change crosses task, execution, evaluation, persistence, or
  presentation boundaries
- When reviewing a contract or persisted data change
- When the user asks for an architecture, domain, or invariant check

## Process

### 1. Identify the changeset

Choose the relevant view:

- staged: `git diff --cached --name-only`
- unstaged: `git diff --name-only` plus
  `git ls-files --others --exclude-standard`
- branch or pull request: compare with its accepted base
- named files: use the scope supplied by the user

List every changed file. Preserve unrelated working-tree changes.

### 2. Identify ownership and execution family

Use `references/domain-routing.md` to identify the owner of each changed
behaviour. Decide whether the change concerns:

- an artifact or workspace task;
- an interactive world;
- shared identity, orchestration, evaluation, artifact, provider, or
  presentation machinery; or
- a composition root that deliberately connects several owners.

Do not infer a boundary solely from a directory name. Read the changed code,
its callers, its tests, and the current owner document.

### 3. Read the applicable authority

Start with `docs/README.md`. Then read only the authorities relevant to the
change:

- `docs/INVARIANTS.md` for stable benchmark guarantees;
- `docs/CONTRACTS.md` for protected boundary families and compatibility;
- `docs/ARCHITECTURE.md` for current ownership and dependency direction;
- the owning protocol for detailed lifecycle, persistence, or transport rules;
- public documentation for documented commands or supported behaviour.

Proposals and history are context, not current authority.

### 4. Check applicable invariants

Read `references/invariants-compact.md`, then inspect each applicable guarantee.
Do not mark an invariant as passed merely because no file with a familiar
domain name changed. Trace outcome-affecting data across the real call path.

At minimum, ask:

- Is the declared task, condition, execution, and verifier still what the
  result measures?
- Is outcome-affecting identity and provenance recorded?
- Can hidden or holdout material enter actor-visible or public output?
- Do tasks remain provider-neutral and adapters free of task policy?
- Does evaluation remain the scoring and invalidity authority?
- Do errors and incomplete work remain explicit failures?
- Is durable or published evidence handled according to its declared integrity
  contract?

### 5. Check dependency direction

Use imports, construction sites, and runtime calls as evidence. Confirm that:

- foundational contracts do not import orchestration or presentation code;
- task definitions and worlds do not import provider SDKs, adapters, or
  presentation policy;
- adapters translate provider or execution protocols without task-specific
  transitions or scoring;
- evaluation consumes execution evidence and does not depend on reporting to
  define metrics;
- ledger and artifact stores persist/query evidence without owning evaluation
  policy;
- CLI, web, TUI, and other composition roots connect existing owners instead
  of reimplementing their policy;
- an interactive-world change uses the registered definition and ports instead
  of adding another repository, run, replay, rollout, or transport stack.

A composition root importing several domains is not automatically a violation.
The violation is ownership or policy moving in the wrong direction.

### 6. Check contracts and compatibility

For every changed boundary or persisted shape:

1. Identify its owner, trust boundary, compatibility promise, and source of
   truth in `docs/CONTRACTS.md`.
2. Use `StrictModel` for validated internal boundaries and `LenientModel` only
   where an external upstream may add fields.
3. Validate external, persisted, and cross-process data when it enters the
   system.
4. Confirm all outcome-affecting fields are typed and represented in evidence.
5. Preserve documented public APIs, external protocols, published formats, and
   real persisted data unless the user approved a breaking change.
6. For internal or unreleased behaviour, update repository callers directly;
   do not add a compatibility shim by default.
7. Update the owning contract or protocol when its semantics change.

### 7. Verify and report

Run the lowest checks that prove the affected boundary, followed by the
broader configured checks appropriate to the changed files. Never claim a
check passed unless it was run and observed passing.

Report:

```markdown
## Domain Check Report

### Scope and owners
- Changed files and affected owners
- Execution family or composition boundary

### Invariant results
| Invariant | Status | Evidence |
| --- | --- | --- |
| Applicable guarantee | PASS / FAIL / N/A | File, test, or observed behaviour |

### Dependency and contract checks
- Ownership or import findings
- Protected-boundary and compatibility findings

### Findings
**[FINDING-1] severity**
- File: `path:line`
- Authority: invariant, contract, architecture, or protocol
- Issue: concrete mismatch
- Fix: smallest coherent correction

### Verification
- Command and observed result
```

If there are no findings, say so directly and still identify the evidence used.

## References

- `references/domain-routing.md` — routes concerns to current owners and docs
- `references/invariants-compact.md` — compact checks for the stable guarantees
