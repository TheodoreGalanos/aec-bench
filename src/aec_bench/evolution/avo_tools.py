# ABOUTME: Defines AVO tool results and pure candidate-material helpers.
# ABOUTME: Keeps mutation, evidence, and memory calculations outside session orchestration.

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from aec_bench.contracts.evolution import MutationSummary, WorkspaceSnapshot
from aec_bench.evolution.agent_protocol import AVOCommand, AVOResponse, MutationInput
from aec_bench.evolution.core import RevisionAttempt
from aec_bench.evolution.memory import AVOMemoryEntry, AVOMemoryOutcome
from aec_bench.evolution.mutation import MutationAction


class AVOToolBudgetExceeded(RuntimeError):
    """Internal signal that a guarded tool cannot start within the budget."""

    def __init__(self, limit: str) -> None:
        super().__init__(f"budget exhausted before tool effect: {limit}")
        self.limit = limit


@dataclass(frozen=True)
class CandidateEditResult:
    """Result from applying one or more typed mutations to scratch."""

    success: bool
    revision: int
    mutation: MutationSummary | None = None
    message: str = ""


@dataclass(frozen=True)
class CandidateCheckResult:
    """Result from evaluating the current scratch revision."""

    success: bool
    revision: int
    attempt: RevisionAttempt | None = None
    message: str = ""


@dataclass(frozen=True)
class CandidateRestoreResult:
    """Result from restoring exact material from a revision attempt."""

    success: bool
    revision: int
    snapshot: WorkspaceSnapshot | None = None
    message: str = ""


@dataclass(frozen=True)
class CandidateSubmissionResult:
    """Result from explicitly selecting the current eligible revision."""

    success: bool
    revision: int
    attempt: RevisionAttempt | None = None
    message: str = ""


@dataclass(frozen=True)
class CandidateAbstentionResult:
    """Result from an explicit agent abstention."""

    terminal: bool
    message: str


def _normalise_response(
    response: AVOCommand | AVOResponse,
) -> tuple[AVOCommand, float | None, int | None, int | None]:
    if isinstance(response, AVOResponse):
        return response.command, response.model_cost_usd, response.input_tokens, response.output_tokens
    if isinstance(response, AVOCommand):
        return response, None, None, None
    raise TypeError("agent runner must return AVOCommand or AVOResponse")


def _normalise_mutations(
    mutation: MutationInput | MutationAction | Mapping[str, Any] | Sequence[MutationInput],
) -> tuple[MutationInput, ...]:
    if isinstance(mutation, MutationInput):
        return (mutation,)
    if isinstance(mutation, MutationAction):
        return (MutationInput.model_validate(_mutation_action_dict(mutation)),)
    if isinstance(mutation, Mapping):
        return (MutationInput.model_validate(mutation),)
    values = tuple(mutation)
    if not values:
        raise ValueError("at least one mutation is required")
    if any(not isinstance(value, MutationInput) for value in values):
        raise TypeError("mutation sequences must contain MutationInput values")
    return values


def _mutation_action_dict(action: MutationAction) -> dict[str, Any]:
    return {
        "type": action.action_type,
        "name": action.skill_name,
        "description": action.skill_description,
        "discipline": action.skill_discipline,
        "body": action.skill_body,
        "content": action.prompt_content,
    }


def _same_material(left: WorkspaceSnapshot, right: WorkspaceSnapshot) -> bool:
    return left.system_prompt == right.system_prompt and left.skills == right.skills


def _material_change_count(parent: WorkspaceSnapshot, current: WorkspaceSnapshot) -> int:
    """Count distinct prompt and skill changes in the current material."""
    changes = int(parent.system_prompt != current.system_prompt)
    parent_skills = {skill.name: skill for skill in parent.skills}
    current_skills = {skill.name: skill for skill in current.skills}
    changes += sum(
        1
        for name in parent_skills.keys() | current_skills.keys()
        if parent_skills.get(name) != current_skills.get(name)
    )
    return changes


def _mutation_summary_for_material(parent: WorkspaceSnapshot, current: WorkspaceSnapshot) -> MutationSummary:
    """Describe the exact cumulative material difference from the parent."""
    parent_skills = {skill.name: skill for skill in parent.skills}
    current_skills = {skill.name: skill for skill in current.skills}
    return MutationSummary(
        prompt_modified=parent.system_prompt != current.system_prompt,
        skills_added=sorted(current_skills.keys() - parent_skills.keys()),
        skills_modified=sorted(
            name for name in parent_skills.keys() & current_skills.keys() if parent_skills[name] != current_skills[name]
        ),
        skills_removed=sorted(parent_skills.keys() - current_skills.keys()),
    )


def _change_summary(mutation: MutationSummary) -> str:
    """Summarise mutation material without retaining model or tool text."""
    changes: list[str] = []
    if mutation.prompt_modified:
        changes.append("system prompt modified")
    if mutation.skills_added:
        changes.append(f"skills added: {', '.join(mutation.skills_added)}")
    if mutation.skills_modified:
        changes.append(f"skills modified: {', '.join(mutation.skills_modified)}")
    if mutation.skills_removed:
        changes.append(f"skills removed: {', '.join(mutation.skills_removed)}")
    return "; ".join(changes) if changes else "no workspace material change"


def _evidence_summary(attempt: RevisionAttempt) -> str:
    """Summarise only the explicit assessment values for structured memory."""
    assessment = attempt.evaluated.assessment
    return (
        f"valid={assessment.valid}; batch_score={assessment.batch_score:.6g}; "
        f"evaluation_cases={len(assessment.evaluation_case_ids)}; trials={len(assessment.trial_ids)}"
    )


def _memory_entry_for_attempt(
    variation_id: str,
    attempt: RevisionAttempt,
    *,
    improved: bool,
) -> AVOMemoryEntry:
    """Build a deterministic fact from one completed development evaluation."""
    assessment = attempt.evaluated.assessment
    if not assessment.valid:
        outcome = AVOMemoryOutcome.INVALID
        failure_category = "invalid_candidate"
        next_direction = "Correct the invalid result before another evaluation."
    elif improved:
        outcome = AVOMemoryOutcome.IMPROVED
        failure_category = None
        next_direction = "Preserve the successful change and test one bounded follow-up."
    else:
        outcome = AVOMemoryOutcome.NOT_IMPROVED
        failure_category = "no_improvement"
        next_direction = "Try a different bounded change direction."
    return AVOMemoryEntry(
        source_variation_id=variation_id,
        source_attempt_id=attempt.attempt_id,
        hypothesis=attempt.hypothesis,
        change_summary=_change_summary(attempt.mutation),
        evidence_summary=_evidence_summary(attempt),
        outcome=outcome,
        failure_category=failure_category,
        next_direction=next_direction,
    )


def _memory_entry_for_evaluation_error(
    *,
    variation_id: str,
    attempt_id: str,
    hypothesis: str,
    mutation: MutationSummary,
) -> AVOMemoryEntry:
    """Build a coarse fact for an evaluator exception without its text."""
    return AVOMemoryEntry(
        source_variation_id=variation_id,
        source_attempt_id=attempt_id,
        hypothesis=hypothesis or "Evaluation hypothesis was not recorded.",
        change_summary=_change_summary(mutation),
        evidence_summary="development evaluation did not produce evidence",
        outcome=AVOMemoryOutcome.EVALUATION_ERROR,
        failure_category="evaluation_error",
        next_direction="Retry the same bounded change only after the evaluator is available.",
    )


def _as_int(value: int | float | None, default: int) -> int:
    return default if value is None else int(value)


def _as_float(value: int | float | None, default: float) -> float:
    return default if value is None else float(value)


def _as_optional_int(value: int | float | None) -> int | None:
    return None if value is None else int(value)
