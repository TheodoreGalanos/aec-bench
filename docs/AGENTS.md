# ABOUTME: Practical agent guide for working in the aec-bench codebase.
# ABOUTME: Reflects established conventions, shared utilities, and domain boundaries from the working implementation.

# AEC-Bench: Agent Guide

This guide is for coding agents working in the **implemented** aec-bench codebase. It reflects conventions established through the working code, not aspirational planning docs.

For architectural context, start with [ARCHITECTURE.md](ARCHITECTURE.md) and [INVARIANTS.md](INVARIANTS.md). For domain-specific guidance, see the domain guide files in `docs/` (e.g., `adapters-guide.md`, `harness-guide.md`, `evaluation-guide.md`).

---

## Package Overview

```text
src/aec_bench/
├── contracts/       # Boundary models (Pydantic). Depends on nothing.
├── tasks/           # Task loading, lifecycle, selection. Depends on contracts.
├── templates/       # Built-in generation templates (ground, electrical). Depends on nothing.
├── generation/      # Template engine, scaffolder, dataset composer. Depends on contracts, templates.
├── agents/          # Agent utility functions (scripts, env, tools, results, providers). Depends on contracts.
├── adapters/        # Provider-neutral model integrations. Depends on contracts.
│   └── tools/       # Tool executors (bash, codes_search).
├── harness/         # Trial orchestration, compute backends. Depends on contracts, tasks, adapters, ledger.
├── ledger/          # Append-only trial persistence. Cross-cutting, depends on contracts only.
├── evaluation/      # Scoring, trace analysis, behavioral classification. Depends on contracts.
│   └── adaptation/  # Task-family variation and acceptance policy.
├── communication/   # Reports, exports, dashboards. Depends on contracts, ledger, evaluation, tasks.
├── feedback/        # Structured human review workflows. Depends on contracts, ledger, tasks.
├── cli/             # Typer CLI commands (generate, evaluate). Depends on generation, evaluation, tasks.
├── tui/             # Textual TUI screens. Depends on tasks, evaluation, communication.
├── web/             # FastAPI routes and templates. Depends on communication, feedback.
│   └── routes/      # Endpoint modules (dashboard, leaderboard, experiment, review, export).
├── providers/       # Vendor integrations (Anthropic LLM client). No internal dependencies.
└── config.py        # Minimal project configuration.
```

**767 tests** across 10 domains. Run with `uv run pytest tests/ -q`.

---

## Dependency Rule

Dependencies flow downward. Never import upward.

```text
contracts
  ├── tasks
  ├── adapters
  │     └── harness
  │           ├── evaluation
  │           │     ├── communication
  │           │     └── feedback
  │           └── ledger (cross-cutting)
  └── web (delivery surface over communication + feedback)
```

**Verified violations to avoid:**
- Feedback must NOT import from communication (use `tasks.loader.load_task_catalog` instead).
- Ledger must NOT import from evaluation (compose query + summarize at the script layer).
- Adapters must NOT import from tasks (they receive `ToolSpec` from contracts).

---

## Model Conventions

### StrictModel — internal contract boundaries

All Pydantic models within the platform use `StrictModel` (from `contracts/validators.py`). It sets `extra="forbid"` to reject unknown fields at construction.

```python
from aec_bench.contracts.validators import StrictModel

class MyBoundaryModel(StrictModel):
    field_a: str
    field_b: int
```

### LenientModel — external data ingestion

Models that parse data from external systems (e.g., Harbor trial results) use `LenientModel`, which sets `extra="allow"` so new upstream fields don't break ingestion.

```python
from aec_bench.contracts.validators import LenientModel

class HarborSomething(LenientModel):
    known_field: str
```

### Frozen dataclasses — internal data structures

Non-boundary data structures (adapter results, report records, trace signals) use `@dataclass(frozen=True)`. These don't need Pydantic validation but benefit from immutability.

---

## Shared Utilities

These live in established locations. Use them instead of writing local copies.

### `contracts/validators.py`

| Function | Purpose |
|---|---|
| `ensure_non_empty_string(value)` | Rejects blank strings |
| `ensure_optional_non_empty_string(value)` | Same but accepts None |
| `ensure_relative_path(value)` | Rejects absolute paths |
| `ensure_optional_relative_path(value)` | Same but accepts None |
| `normalize_workspace_path(path)` | Ensures leading `/` on workspace paths |
| `infer_output_format(output_path)` | Returns format label from file suffix |

### `contracts/jsonl.py`

| Function | Purpose |
|---|---|
| `write_jsonl(path, records)` | Deterministic JSONL write (sort_keys=True) |
| `read_jsonl(path)` | Read JSONL, skip blank lines |

### `evaluation/stats.py`

| Function | Purpose |
|---|---|
| `mean(values)` | None-filtering mean, returns 0.0 for empty |
| `wilson_confidence_interval(successes, trials)` | Wilson score interval |
| `cohen_kappa(left, right)` | Inter-rater agreement |

### `communication/metrics.py`

| Function | Purpose |
|---|---|
| `coerce_int(value, fallback=0)` | Safe int coercion from Any |
| `resolve_agent_name(record)` | Extract display name from TrialRecord |
| `split_task_id(task_id)` | Returns `(task_type, task_name)` from slash-delimited ID |

### `tasks/loader.py`

| Constant/Function | Purpose |
|---|---|
| `WORKSPACE_OUTPUT_PATH_RE` | Regex for `/workspace/...` paths in instructions |
| `extract_workspace_output_paths(instruction)` | Extract + strip punctuation from instruction text |
| `load_task_catalog(tasks_root)` | Build `dict[str, TaskDefinition]` from disk |

### `harness/trial.py`

| Function | Purpose |
|---|---|
| `build_trial_id(experiment_id, task_id, agent_name, repetition)` | Deterministic trial ID |

### `adapters/transcript.py`

| Function | Purpose |
|---|---|
| `initialize_transcript(request)` | Build system+user opening entries from AdapterRequest |

### `adapters/tools/__init__.py`

| Function | Purpose |
|---|---|
| `coerce_timeout(value, default)` | Safe timeout coercion |
| `join_subprocess_output(stdout, stderr)` | Combine and strip subprocess output |
| `run_subprocess_tool(command, cwd, timeout, label)` | Full subprocess execution with error handling |

---

## File Conventions

- Every `.py` file starts with a 2-line `# ABOUTME:` comment explaining what the file does.
- Every file uses type hints on all function signatures (parameters + return).
- Tests mirror the source package structure in `tests/`.
- Test factories live in `tests/support/` (`trial_record_factories.py`, `task_factories.py`, `feedback_factories.py`).

---

## Adapter Rules

Adapters translate protocol only. They do NOT:
- Branch on task type
- Rewrite instructions
- Choose tools
- Score outputs

Tool errors are surfaced back to the model (not swallowed), logged via `logger.warning`, and the conversation loop continues.

---

## Harness Rules

- `build_trial_plan` expects pre-filtered tasks. Callers use `select_manifest_tasks` first.
- Harbor contract models use `LenientModel` (external data).
- `TaskRegistry.reload()` is failure-tolerant — malformed tasks are logged and tracked in `load_errors`.
- Trial completeness is `PARTIAL` unless all provenance fields (adapter_revision, tool_versions, input_files) are present.

---

## Ledger Rules

- Append-only. No update or delete operations.
- `query_trial_records` scopes to experiment directory when `experiment_id` is provided.
- The ledger API layer owns persistence operations only — evaluation logic stays in the evaluation domain.

---

## Testing Conventions

- Use `make_trial_record(**overrides)` and `make_task_definition(**overrides)` from `tests/support/`.
- Real Harbor data tests use `_archive/jobs/2026-03-04__17-57-43` (60 trials, skipped on fresh clones).
- Adapter tests use replay clients (`ReplayDirectClient`, `ReplayToolLoopClient`).
- Property-based tests (Hypothesis) are used for validators and stats primitives.
- Run the full suite: `uv run pytest tests/ -q`
- Lint: `uv run ruff check src/ tests/`
- Type check: `uv run mypy src/aec_bench/contracts/`

---

## Available Skills

Agent skills automate common workflows. Invoke them with `/skill-name` when your
agent environment supports slash commands, or translate each row into that
environment's native skill/prompt mechanism.

| Skill | Purpose | When to Use |
|---|---|---|
| `/add-task` | Interview an expert to create a task seed | When a domain expert wants to add a new benchmark task |
| `/create-template` | Build a generation template from a seed file | Converting a `source_task.json` into a parameterisable template |
| `/hardening-pass` | Quality-gate a template or task instance | Before using a template or task in real benchmarks |
| `/domain-check` | Verify architectural invariants and dependency directions | Before committing cross-domain changes |
| `/meta-harness` | Create or compare a harness candidate against a baseline | When a task needs world design, reviewer evidence, governance, or candidate-vs-baseline comparison |

---

## Invariants (Quick Reference)

| # | Rule | One-line test |
|---|---|---|
| 1 | Single source of truth | Can this trial be replayed from its TrialRecord alone? |
| 2 | Contracts at boundaries | Does every cross-domain boundary validate its payload? |
| 3 | No hidden state | Is every outcome-relevant input persisted? |
| 4 | Task-adapter independence | Would this still work with any task or any adapter? |
| 5 | Evaluation is a pipeline | Does this metric come from evaluation outputs, not invented state? |
| 6 | Public/holdout separation | Could this leak holdout content? |
| 7 | Validate before commit | Has this been smoke-tested on a representative subset? |
| 8 | Provider isolation | Can this code be described without naming a vendor? |
| 9 | Human judgment is structured | Is expert feedback captured as machine-readable data? |
| 10 | Continuous quality | Does this reduce drift instead of adding to it? |

## Objective Stack

When invariants or requirements conflict, higher priority wins.

```
validity > reproducibility > coverage > cost > throughput
```
