# ABOUTME: Interprets generated problem-model process evidence for candidate comparison.
# ABOUTME: Keeps the process score definition with the evaluation owner.

from __future__ import annotations

from typing import Any


def score_process_result(result: dict[str, Any]) -> dict[str, Any]:
    evidence = _evidence(result)
    verifier_reward = _verifier_reward(evidence)
    logic_certified = 1.0 if result.get("logic_evaluation", {}).get("overall_status") == "certified" else 0.0
    review = evidence.get("agentic_review", {}) if isinstance(evidence, dict) else {}
    review_complete = 1.0 if review.get("status") in {"complete", "certified"} else 0.0
    evidence_completeness = _evidence_completeness(evidence)
    governance_churn_penalty = _governance_churn_penalty(result)
    unresolved_wait_penalty = 0.1 if str(result.get("status", "")).startswith("awaiting_") else 0.0
    value = (
        0.55 * verifier_reward
        + 0.20 * logic_certified
        + 0.15 * review_complete
        + 0.10 * evidence_completeness
        - governance_churn_penalty
        - unresolved_wait_penalty
    )
    value = max(0.0, min(1.0, value))
    return {
        "value": round(value, 6),
        "components": {
            "verifier_reward": verifier_reward,
            "logic_certified": logic_certified,
            "review_complete": review_complete,
            "evidence_completeness": evidence_completeness,
            "governance_churn_penalty": governance_churn_penalty,
            "unresolved_wait_penalty": unresolved_wait_penalty,
        },
    }


def _evidence(result: dict[str, Any]) -> dict[str, Any]:
    task_run = result.get("task_run") or {}
    evidence = task_run.get("evidence", task_run) if isinstance(task_run, dict) else {}
    return evidence if isinstance(evidence, dict) else {}


def _verifier_reward(evidence: dict[str, Any]) -> float:
    score = evidence.get("score", {})
    if not isinstance(score, dict):
        return 0.0
    reward = score.get("reward")
    if isinstance(reward, int | float):
        return max(0.0, min(1.0, float(reward)))
    if score.get("passed") is True:
        return 1.0
    if score.get("passed") is False:
        return 0.0
    return 0.0


def _evidence_completeness(evidence: dict[str, Any]) -> float:
    checks = [
        bool(evidence.get("score")),
        bool(evidence.get("artifacts")),
        bool(evidence.get("agentic_review")),
    ]
    return sum(1 for item in checks if item) / len(checks)


def _governance_churn_penalty(result: dict[str, Any]) -> float:
    governance = result.get("governance", {})
    decision = governance.get("decision", {}) if isinstance(governance, dict) else {}
    if result.get("status") == "accepted_for_world_generation":
        return 0.05
    if decision.get("scope") in {"world_schema", "world_generator"}:
        return 0.05
    return 0.0


__all__ = ("score_process_result",)
