# ABOUTME: Guide for the Python communication domain covering dashboards, reports, exports, and audience-specific rendering.
# ABOUTME: Keeps communication anchored to evaluation outputs and reproducible derivations.

# Communication Guide

Communication is how evaluation results reach engineers, experts, decision makers, and public readers. The Python plan keeps the same governing rule: communication renders from canonical evaluation and trial data, not from parallel truth sources.

Parent document: [ARCHITECTURE.md](ARCHITECTURE.md).
Data shapes: [CONTRACTS.md](CONTRACTS.md).
Rules: [INVARIANTS.md](INVARIANTS.md).

---

## Single-Source Principle

Every number, chart, and claim must trace back to canonical evaluation data with verifiable lineage. Derived metrics are allowed only when their computation is documented and reproducible.

Communication may read from:

- ledger-backed indexes,
- materialized views,
- query caches,

but only if lineage back to TrialRecord and EvaluationResult remains explicit.

---

## Audiences

### Engineers

Need trial-level inspection, error patterns, traces, and behavioral diagnostics.

### Domain experts

Need engineering-content-first views, rubric context, and review-friendly interfaces.

### Decision makers

Need trustworthy summaries, trends, cost-quality views, and risk framing.

### Public and academic audiences

Need methodology, reproducibility context, public-only leaderboards, and limitations.

---

## Shared Metric Primitives

Communication consumes primitives computed in evaluation, such as:

- reward,
- validity,
- breakdown,
- error taxonomy,
- confidence metadata,
- trial completeness.

Valid derived metrics include things like:

- mean reward,
- perfect-trial rate,
- zero-trial rate,
- cost per trial,
- reward per dollar,
- tokens per turn.

Aggregation rules:

- always state grouping,
- show sample sizes,
- include uncertainty where available,
- separate incomplete evaluation states,
- exclude retired and proposed tasks,
- respect holdout boundaries.

---

## Artefact Types

The main communication artefacts remain:

- interactive tools,
- reports,
- presentations,
- data releases.

Each should record provenance including experiment scope, build time, and data version.

---

## Build Rules

Communication artefacts are built, not hand-maintained.

The pipeline is:

1. load canonical evaluation data,
2. compute documented derived metrics,
3. render the target artefact.

Standalone releases should inline what they need so they remain portable.

Behavioral reporting rule:

- Behavioral and confidence diagnostics may be included in report JSON when they are computed from canonical ledger-backed transcripts through an explicitly requested classifier path.
- Passive report generation must not make hidden provider calls; classifier-backed enrichment should remain opt-in at the script or API boundary.
- Conservative tabular exports may omit behavioral columns even when the JSON export includes them.
- Dedicated behavioral exports may flatten per-trial structural and confidence fields for downstream analysis as long as the export also preserves aggregate summary context and canonical trial identifiers.
