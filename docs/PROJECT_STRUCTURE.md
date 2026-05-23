# ABOUTME: Defines the Python project layout for the aec-bench Python implementation.
# ABOUTME: Maps the existing architecture to Python packages, tests, and web modules.

# Project Structure

This document defines the physical layout of the Python version of aec-bench. The architecture remains the same as the Elixir plan; only the language-specific module layout changes.

Parent document: [TECHNOLOGY_CHOICE.md](TECHNOLOGY_CHOICE.md).

---

## Top-Level Layout

The repository root for the Python implementation is a standard `src/`-layout Python project managed by `uv`.

```
aec-bench-python/
├── pyproject.toml                  # Project metadata, dependencies, tool config
├── uv.lock                         # Locked dependencies
├── README.md                       # Project overview
├── .python-version                 # Python version pin if used
│
├── src/
│   └── aec_bench/
│       ├── __init__.py
│       ├── config.py               # App settings and environment loading
│       ├── contracts/              # Domain: Contracts
│       ├── tasks/                  # Domain: Tasks
│       ├── adapters/               # Domain: Adapters
│       ├── harness/                # Domain: Harness
│       ├── evaluation/             # Domain: Evaluation
│       ├── ledger/                 # Cross-cutting: Immutable ledger
│       ├── communication/          # Shared communication logic
│       ├── feedback/               # Feedback domain logic and persistence
│       └── web/                    # FastAPI app, routes, templates
│
├── tests/
│   ├── contracts/
│   ├── tasks/
│   ├── adapters/
│   ├── harness/
│   ├── evaluation/
│   ├── communication/
│   ├── feedback/
│   └── support/
│
├── tasks/                          # Task definitions (data, not Python code)
├── prompts/                        # Shared workflow prompts
├── docs/                           # Python planning docs
└── artefacts/                      # Optional local runtime artefacts and ledgers
```

---

## Core Packages

### Contracts — `src/aec_bench/contracts/`

Pydantic models and validation helpers.

```
contracts/
├── validators.py
├── task_definition.py
├── agent_output.py
├── evaluation_result.py
├── trial_record.py
├── experiment_manifest.py
└── payloads/
    ├── audit_finding.py
    └── calculation_result.py
```

### Tasks — `src/aec_bench/tasks/`

```
tasks/
├── loader.py
├── lifecycle.py
├── selector.py
├── promotion.py
├── instance.py
└── registry.py
```

### Adapters — `src/aec_bench/adapters/`

```
adapters/
├── base.py
├── config.py
├── transcript.py
├── tool_loop.py
├── direct.py
└── tools/
    ├── bash.py
    └── codes_search.py
```

### Harness — `src/aec_bench/harness/`

```
harness/
├── compute.py
├── docker_backend.py
├── backend_registry.py
├── staging.py
├── signals.py
├── trial.py
├── scheduler.py
├── experiment_runner.py
└── progress_tracker.py
```

### Evaluation — `src/aec_bench/evaluation/`

```
evaluation/
├── stats.py
├── mechanical.py
├── trace.py
├── behavioral.py
├── taxonomy.py
├── confidence.py
├── aggregation.py
├── pipeline.py
└── adaptation/
    ├── family.py
    ├── expansion.py
    ├── coordinator.py
    ├── provenance.py
    └── acceptance.py
```

### Ledger — `src/aec_bench/ledger/`

```
ledger/
├── writer.py
├── reader.py
└── api.py
```

### Communication — `src/aec_bench/communication/`

```
communication/
├── metrics.py
├── query.py
├── report_builder.py
└── standalone.py
```

### Feedback — `src/aec_bench/feedback/`

```
feedback/
├── models.py
├── calibration.py
├── adjudication.py
├── assignment.py
├── signals.py
└── annotation_consumer.py
```

### Web Layer — `src/aec_bench/web/`

```
web/
├── app.py
├── dependencies.py
├── routes/
│   ├── dashboard.py
│   ├── leaderboard.py
│   ├── traces.py
│   ├── experiment.py
│   ├── export.py
│   └── review.py
├── templates/
└── static/
```

---

## Testing Layout

Tests mirror the package structure and stay domain-local where possible.

```
tests/
├── contracts/
├── tasks/
├── adapters/
├── harness/
├── evaluation/
├── communication/
├── feedback/
└── support/
```

Pure functions should dominate the early phases. Process-heavy and integration-heavy tests arrive later.

---

## Design Rules

- `tasks/` remains data, not code.
- `TrialRecord` remains the canonical provenance container.
- `EvaluationResult` remains evaluation-focused, not a duplicate task registry.
- Communication renders from evaluation and joined trial data, not invented state.
- Feedback remains structured and separate from raw evaluation execution.

---

## Related Documents

| Document | Purpose |
| --- | --- |
| [TECHNOLOGY_CHOICE.md](TECHNOLOGY_CHOICE.md) | Why Python, package and library choices |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Phased Python implementation plan |
| [IMPLEMENTATION_WORK_ITEMS.md](IMPLEMENTATION_WORK_ITEMS.md) | Ticket-sized Python work items |
