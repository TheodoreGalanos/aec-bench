# ABOUTME: High-level architecture for the Python aec-bench platform.
# ABOUTME: Defines domains, boundaries, contracts, and dependency rules without changing the core architecture.

# AEC-Bench Python Architecture

This document defines the architecture for the Python implementation of aec-bench. The domain model and dependency rules are unchanged from the main architecture; this version only adjusts implementation assumptions for Python.

Parent documents: [TECHNOLOGY_CHOICE.md](TECHNOLOGY_CHOICE.md), [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md).

---

## Objective Stack

All design decisions resolve against this hierarchy. When objectives conflict, higher-priority objectives win.

```
validity > reproducibility > coverage > cost > throughput
```

- **Validity**: Results reflect real agent capability, not benchmark artefacts.
- **Reproducibility**: Any result can be reconstructed from its recorded inputs.
- **Coverage**: The benchmark spans meaningful AEC domain breadth and depth.
- **Cost**: Experiments are affordable enough to run frequently.
- **Throughput**: New tasks, agents, and models can be onboarded quickly.

---

## Domains

The system is divided into seven domains with strict dependency rules: one foundational layer and six operational domains. Dependencies flow downward. Nothing flows upward except through the explicit feedback loop.

Data adaptation is still not a separate eighth domain. It is a cross-domain workflow built from Contracts, Tasks, Harness, Evaluation, and Feedback.

```
            Contracts
         /              \
      Tasks          Adapters
         \              /
              Harness
                 |
             Evaluation
             /        \
   Communication    Feedback
```

### 1. Contracts

The foundation that everything else depends on. Python implements these as Pydantic models and explicit validation helpers.

Key contracts:

- `TaskDefinition`
- `AgentOutput`
- `TrialRecord`
- `EvaluationResult`
- `ExperimentManifest`

### 2. Tasks

Task definitions, lifecycle state, visibility classification, and registry/query logic. Tasks remain data, not code.

### 3. Adapters

Provider-neutral agent integration points. Adapters translate protocol only. They do not hold task logic or benchmark policy.

### 4. Harness

Execution orchestration, container lifecycle, staging, scheduling, and trial persistence.

### 5. Evaluation

Everything that happens after trial execution: verifier result ingestion, trace extraction, behavioral analysis, aggregation, and confidence metadata.

### 6. Communication

Dashboards, reports, exports, and trace views rendered from evaluation outputs and joined trial data.

### 7. Feedback

Structured expert review, calibration, adjudication, and anti-contamination-aware annotation flows.

---

## Cross-Cutting Concerns

These are provider-shaped capabilities, not separate domains:

- **Storage**
- **Compute**
- **Credentials**
- **Observability**
- **Immutable ledger**
- **Configuration**

The Python implementation should expose each through a narrow boundary, not through ad hoc imports across the codebase.

---

## Dependency Rule

Dependencies flow downward through the stack:

1. Contracts depend on nothing.
2. Tasks and Adapters both depend on Contracts and remain independent of each other.
3. Harness depends on Tasks, Adapters, and ledger primitives.
4. Evaluation depends on harness outputs and trial records.
5. Communication and Feedback depend on evaluation outputs.
6. Nothing flows upward except through explicit, structured feedback.

---

## Python Interpretation

The architecture stays the same; the Python translation changes only the implementation substrate:

- Pydantic replaces Elixir contract constructors.
- `asyncio` and explicit orchestration replace OTP supervision semantics.
- FastAPI, Jinja2, and HTMX replace Phoenix/LiveView.
- SQLAlchemy and Alembic replace Ecto where structured persistence is needed.
- JSON/JSONL trial artefacts remain the earliest ledger implementation.

The key question is not whether Python matches BEAM semantics. The key question is whether Python can preserve the architectural guarantees. This plan assumes yes, so long as those guarantees are made explicit in contracts, tests, and provenance rules.

---

## Current Translation State

The following Python planning docs exist now:

- [TECHNOLOGY_CHOICE.md](TECHNOLOGY_CHOICE.md)
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- [IMPLEMENTATION_WORK_ITEMS.md](IMPLEMENTATION_WORK_ITEMS.md)
- [INVARIANTS.md](INVARIANTS.md)
- [CONTRACTS.md](CONTRACTS.md)
- [tasks-guide.md](tasks-guide.md)
- [adapters-guide.md](adapters-guide.md)
- [harness-guide.md](harness-guide.md)
- [evaluation-guide.md](evaluation-guide.md)
- [communication-guide.md](communication-guide.md)
- [feedback-guide.md](feedback-guide.md)
- [implementation/contracts.md](implementation/contracts.md)
- [implementation/tasks.md](implementation/tasks.md)
- [implementation/adapters.md](implementation/adapters.md)
- [implementation/harness.md](implementation/harness.md)
- [implementation/evaluation.md](implementation/evaluation.md)
- [implementation/communication.md](implementation/communication.md)
- [implementation/feedback.md](implementation/feedback.md)

The top-level domain guides and per-domain implementation docs have now been translated into the Python planning surface. The sibling [aec-bench/docs](../../aec-bench/docs) tree remains the original source architecture, but the Python planning tree is now self-contained for implementation planning.
