# ABOUTME: Projects named drainage-provenance outcomes from the submitted public review artifact.
# ABOUTME: Keeps task-specific boundary and transition semantics with the task evaluation owner.

from __future__ import annotations

import json
import re


def has_correct_downstream_memo_boundary_decision(output_text: str) -> bool:
    """Return whether the public review localises a stale downstream memo correctly."""

    payload = _public_output(output_text)
    if payload is None:
        return False
    matrix = payload.get("review_matrix", {})
    transition = payload.get("transition_decision", {})
    findings = payload.get("findings", ())
    return (
        isinstance(matrix, dict)
        and _matrix_status(matrix, "PRV-03") == "pass"
        and _matrix_status(matrix, "PRV-06") == "fail"
        and isinstance(transition, dict)
        and transition.get("model_run") == "governing"
        and transition.get("model_report") == "governing"
        and transition.get("design_claim") == "unsupported"
        and isinstance(findings, list | tuple)
        and len(findings) == 1
        and _finding_item(findings[0]) == "PRV-06"
        and payload.get("readiness_decision") == "not_ready_to_issue"
    )


def has_upstream_model_invalidation_decision(output_text: str) -> bool:
    """Return whether the public review applies the upstream-invalidation transition."""

    payload = _public_output(output_text)
    if payload is None:
        return False
    matrix = payload.get("review_matrix", {})
    transition = payload.get("transition_decision", {})
    findings = payload.get("findings", ())
    finding_items = (
        {_finding_item(item) for item in findings if isinstance(item, dict)}
        if isinstance(findings, list | tuple)
        else set()
    )
    return (
        isinstance(matrix, dict)
        and _matrix_status(matrix, "PRV-03") == "fail"
        and isinstance(transition, dict)
        and transition.get("model_run") == "non_governing"
        and transition.get("model_report") == "non_governing"
        and "PRV-03" in finding_items
    )


def _public_output(output_text: str) -> dict[str, object] | None:
    matches = re.findall(r"```json\s*\n(.*?)\n\s*```", output_text, re.DOTALL)
    if not matches:
        return None
    try:
        payload = json.loads(matches[-1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _matrix_status(matrix: dict[object, object], item_id: str) -> str:
    entry = matrix.get(item_id)
    return str(entry.get("status", "")).strip().lower() if isinstance(entry, dict) else ""


def _finding_item(finding: object) -> str:
    return str(finding.get("item", "")).strip().upper() if isinstance(finding, dict) else ""


__all__ = (
    "has_correct_downstream_memo_boundary_decision",
    "has_upstream_model_invalidation_decision",
)
