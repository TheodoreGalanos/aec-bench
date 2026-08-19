# ABOUTME: Defines one separated task-review value for an internal run plan.
# ABOUTME: Keeps review policy and stage graphs outside authoritative task identity.

from __future__ import annotations

from pydantic import field_validator, model_validator

from aec_bench.contracts.stage_execution import DeclaredStageGraph
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


class TaskReviewSnapshot(FrozenStrictModel):
    """One task's embedded review data, separate from the task identity."""

    task_id: NonEmptyStr
    profile_id: NonEmptyStr
    visibility: Visibility
    stage_graph: DeclaredStageGraph | None = None

    @model_validator(mode="after")
    def validate_stage_graph(self) -> TaskReviewSnapshot:
        if self.stage_graph is not None and self.stage_graph.task_id != self.task_id:
            raise ValueError("declared stage graph does not match review task id")
        return self


class ReviewSnapshot(FrozenStrictModel):
    """The one embedded review value for all reviewed tasks in a run plan."""

    tasks: tuple[TaskReviewSnapshot, ...]

    @field_validator("tasks")
    @classmethod
    def validate_tasks(cls, value: tuple[TaskReviewSnapshot, ...]) -> tuple[TaskReviewSnapshot, ...]:
        task_ids = tuple(item.task_id for item in value)
        if not task_ids:
            raise ValueError("review snapshot must include at least one task review")
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("review snapshot task ids must be unique")
        return value


__all__ = ("ReviewSnapshot", "TaskReviewSnapshot")
