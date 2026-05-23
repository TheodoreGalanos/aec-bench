# ABOUTME: Execution planner for the lambda-rlm adapter.
# ABOUTME: Builds cost-optimal decomposition plans from template sections and source document sizes.

from __future__ import annotations

import logging
from typing import Any

from aec_bench.adapters.lambda_rlm.combinators import compute_plan_params
from aec_bench.adapters.lambda_rlm.config import PlannerConfig
from aec_bench.adapters.lambda_rlm.state import (
    CompositionOp,
    ExecutionPlan,
    LeafOp,
    ReduceOp,
    SectionPlan,
)

_log = logging.getLogger(__name__)


def build_execution_plan(
    *,
    sections: list[dict[str, Any]],
    source_docs: dict[str, str],
    config: PlannerConfig,
) -> ExecutionPlan:
    """Build a complete execution plan from template sections and source documents.

    Sections are topologically sorted by dependency order. External sections are
    skipped. For each active section, sources are inspected and chunked if they
    exceed the context window.
    """
    ordered = _topological_sort(sections)
    section_plans: dict[str, SectionPlan] = {}
    skipped: list[str] = []

    for sec in ordered:
        gen_mode = sec.get("generation_mode", "transform")
        comp_op = CompositionOp.from_generation_mode(gen_mode)

        if comp_op == CompositionOp.SKIP:
            skipped.append(sec["id"])
            continue

        sources = sec.get("input_mapping", [])
        leaf_ops: list[LeafOp] = []
        reduce_ops: list[ReduceOp] = []

        for source_label in sources:
            source_text = _resolve_source(source_label, source_docs)
            if not source_text:
                _log.debug(
                    "Source %r not found for section %r, skipping",
                    source_label,
                    sec["id"],
                )
                continue

            k_star, tau_star, depth = compute_plan_params(
                source_size_chars=len(source_text),
                context_window_chars=config.context_window_chars,
                max_branching_factor=config.max_branching_factor,
            )

            if depth == 0:
                leaf_ops.append(LeafOp(source=source_label, chunk_index=0, total_chunks=1))
            else:
                total_chunks = k_star**depth
                for i in range(total_chunks):
                    leaf_ops.append(LeafOp(source=source_label, chunk_index=i, total_chunks=total_chunks))
                reduce_ops.append(ReduceOp(source=source_label, inputs_count=total_chunks))

        section_plans[sec["id"]] = SectionPlan(
            section_id=sec["id"],
            generation_mode=gen_mode,
            sources=sources,
            leaf_ops=leaf_ops,
            reduce_ops=reduce_ops,
            composition_op=comp_op,
            estimated_leaf_calls=len(leaf_ops),
            estimated_reduce_calls=len(reduce_ops),
        )

    section_order = [s["id"] for s in ordered if s["id"] not in skipped]

    plan = ExecutionPlan(
        section_order=section_order,
        section_plans=section_plans,
        skipped_sections=skipped,
    )
    _log.info(
        "Execution plan: %d sections, %d skipped, ~%d total LLM calls",
        len(section_order),
        len(skipped),
        plan.total_estimated_calls,
    )
    return plan


def _resolve_source(label: str, source_docs: dict[str, str]) -> str:
    """Resolve a template source label to document content.

    Handles 'doc:section' labels (e.g. 'brief:Description/Background')
    by matching the doc part against discovered document keys.
    """
    if label in source_docs:
        return source_docs[label]
    if ":" in label:
        doc_key = label.split(":")[0]
        if doc_key in source_docs:
            return source_docs[doc_key]
    for key, content in source_docs.items():
        if key.startswith(label) or label.startswith(key):
            return content
    return ""


def _topological_sort(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Topologically sort sections by depends_on edges (Kahn's algorithm)."""
    by_id = {s["id"]: s for s in sections}
    in_degree = {s["id"]: 0 for s in sections}
    dependents: dict[str, list[str]] = {s["id"]: [] for s in sections}

    for sec in sections:
        for dep in sec.get("depends_on", []):
            if dep in by_id:
                in_degree[sec["id"]] += 1
                dependents[dep].append(sec["id"])

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    result: list[dict[str, Any]] = []

    while queue:
        queue.sort()
        current = queue.pop(0)
        result.append(by_id[current])
        for dependent in dependents[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    return result
