---
name: domain-check
description: Verify that code changes respect aec-bench architectural invariants and domain boundaries. Use when modifying files under src/aec_bench/, adding new modules, changing contracts or data shapes, working across multiple domains, or before committing changes. Also trigger when the user asks to "check domains", "verify architecture", "validate invariants", or "review boundaries".
---

# Domain Check

Verify that a set of changes respects aec-bench's architectural invariants and domain boundaries before they land.

This skill exists because aec-bench has strict dependency rules between domains and 10 non-negotiable invariants. A change that looks correct in isolation can violate cross-domain contracts, import in the wrong direction, or leak holdout data. This check catches those problems before they become entrenched.

## When to Use

- Before committing changes that touch `src/aec_bench/` code
- After implementing a feature that spans multiple domains
- When reviewing someone else's changes to the platform
- When you're unsure whether a change respects the architecture
- Proactively, as a sanity check during development

## Process

### Step 1: Identify the Changeset

Determine what has changed. Use one of these approaches depending on context:

- **Staged changes**: Run `git diff --cached --name-only` to see what's about to be committed
- **Unstaged changes**: Run `git diff --name-only` plus `git ls-files --others --exclude-standard` for new files
- **Specific files**: The user may point you to specific files or a PR
- **Working session**: If you've been making changes during this session, you already know what changed

List every changed file. You need the complete set to detect cross-domain issues.

### Step 2: Map Changes to Domains

For each changed file, determine which domain it belongs to using this mapping:

| Path pattern | Domain |
|---|---|
| `src/aec_bench/contracts/` | Contracts |
| `src/aec_bench/tasks/` | Tasks |
| `src/aec_bench/templates/` | Templates |
| `src/aec_bench/generation/` | Generation |
| `src/aec_bench/agents/` | Agents |
| `src/aec_bench/adapters/` | Adapters |
| `src/aec_bench/harness/` | Harness |
| `src/aec_bench/evaluation/` | Evaluation |
| `src/aec_bench/communication/` | Communication |
| `src/aec_bench/feedback/` | Feedback |
| `src/aec_bench/ledger/` | Cross-cutting (Ledger) |
| `src/aec_bench/providers/` | Cross-cutting (Providers) |
| `src/aec_bench/cli/` | CLI (depends on generation, evaluation, tasks) |
| `src/aec_bench/tui/` | TUI (depends on tasks, evaluation, communication) |
| `src/aec_bench/web/` | Web (depends on communication, feedback) |
| `docs/` | Documentation (check for doc-code drift) |
| `tests/` | Tests (check they mirror source package structure) |
| `tasks/` | Task definitions (check task-adapter independence) |
| `seeds/` | Seed files (skill-to-skill interface, no library dependency) |

If a change touches files in multiple domains, that's a signal to check dependency directions carefully.

### Step 3: Read the Relevant Domain Docs

For each domain touched, read the corresponding guide from `references/domain-routing.md`. This step is important — you need the design intent to judge whether the changes are correct, not just whether they run.

Read the **guide** for each affected domain.

### Step 4: Run Invariant Checks

Check each of the 10 invariants that could be affected by the changeset. Not all invariants apply to every change — focus on the ones relevant to the domains touched.

Read the full invariant details from `references/invariants-compact.md`.

For each applicable invariant, answer the one-line test:

| # | One-line test | Check if domain touched... |
|---|---|---|
| 1 | Can this trial be reproduced from its TrialRecord alone? | Harness, Contracts |
| 2 | Does every cross-domain call validate against a contract? | Any cross-domain change |
| 3 | Is every input that affects outcomes persisted in the run record? | Adapters, Harness, Agents |
| 4 | Does this task work with ANY adapter? Does this adapter work with ANY task? | Tasks, Adapters, Agents |
| 5 | Does this metric compile from evaluation outputs, not invented data? | Evaluation, Communication |
| 6 | Could holdout content leak through this change? | Communication, Feedback |
| 7 | Has this been smoke-tested on a representative subset? | Any new feature |
| 8 | Can you describe what this code does without naming a vendor? | Providers, Harness, Agents |
| 9 | Is expert feedback captured as machine-readable, provenanced data? | Feedback |
| 10 | Does this change pay down drift or add to it? | Any change |

### Step 5: Check Dependency Directions

This is the most common source of architectural violations. Verify that no changed file imports "upward" in the dependency graph:

```
Contracts (depends on nothing)
  |
  +-- Tasks (depends on Contracts only)
  +-- Templates (depends on nothing — pure computation)
  +-- Adapters (depends on Contracts only)
  +-- Agents (depends on Contracts only)
  |
  +-- Generation (depends on Contracts, Templates)
  |
  +-- Harness (depends on Tasks, Adapters, Contracts, Ledger)
        |
        +-- Evaluation (depends on Harness outputs, Contracts)
              |
              +-- Communication (depends on Evaluation, Contracts, Ledger, Tasks)
              +-- Feedback (depends on Contracts, Ledger, Tasks)

Cross-cutting:
  Ledger (depends on Contracts only)
  Providers (no internal dependencies)
  CLI (depends on Generation, Evaluation, Tasks)
  TUI (depends on Tasks, Evaluation, Communication)
  Web (depends on Communication, Feedback)
```

Specifically check for these known violation patterns:

- Does any adapter `import` or `from ... import` anything from `aec_bench.tasks`?
- Does any task module reference `aec_bench.adapters`?
- Does Evaluation import from Communication or Feedback?
- Does Harness import from Evaluation?
- Does anything outside `providers/` import directly from a vendor SDK?
- Does Feedback import from Communication? (Use `tasks.loader.load_task_catalog` instead)
- Does Ledger import from Evaluation? (Compose at the script layer)
- Do Adapters import from Tasks? (They receive `ToolSpec` from Contracts)

For Python code, look for `import` and `from X import Y` statements that cross boundaries. Use grep or AST-based search to find violations.

### Step 6: Check Contract Compliance

If the change modifies any contract model or adds a new data shape:

1. Does it use `StrictModel` (from `contracts/validators.py`) for internal boundary models?
2. Does it use `LenientModel` for external data ingestion (e.g., Harbor results)?
3. Does it use `@dataclass(frozen=True)` for non-boundary data structures?
4. Are all fields typed?
5. Does the change maintain backward compatibility with existing consumers?
6. Is the contract documented in `docs/CONTRACTS.md`?

If the change uses a contract (as a consumer):

1. Does it construct models through the validated constructor, not raw dict unpacking?
2. Does it handle validation errors explicitly?
3. Does it use the shared validators from `contracts/validators.py` (e.g., `ensure_non_empty_string`, `ensure_relative_path`)?

### Step 7: Produce the Report

Output a structured findings report. Be specific — name the file, the line, the invariant, and the fix.

**Format:**

```
## Domain Check Report

### Domains Touched
- [list domains]

### Invariant Results

| # | Invariant | Status | Notes |
|---|---|---|---|
| 1 | Single source of truth | PASS / FAIL / N/A | detail |
| ... | ... | ... | ... |

### Dependency Check
- [list any upward imports found, or "All dependencies flow downward"]

### Contract Check
- [list any contract violations, or "All contracts properly used"]

### Findings

**[FINDING-1]** severity: high/medium/low
- File: `path/to/file.py:line`
- Invariant: #N
- Issue: [what's wrong]
- Fix: [what to do]

### Summary
- X invariants checked, Y passed, Z failed
- N findings (H high, M medium, L low)
```

If there are zero findings, say so clearly — a clean check is valuable information.

## Reference Files

Read these as needed during the check:

- `references/domain-routing.md` — Which docs to read for each domain
- `references/invariants-compact.md` — All 10 invariants with their one-line tests and enforcement details
