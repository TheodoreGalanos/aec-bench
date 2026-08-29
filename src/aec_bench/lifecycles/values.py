# ABOUTME: Defines the ordinary in-memory values used by lifecycle execution composition.
# ABOUTME: Keeps local execution independent from trial recording and persistence effects.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aec_bench.lifecycles.compiled import CompiledLifecycle
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from aec_bench.trials import PlannedTrial

if TYPE_CHECKING:
    from aec_bench.lifecycles.invocation import LifecycleExperimentSweepContext


@dataclass(frozen=True, slots=True)
class LifecycleTrial:
    """Bind one caller-owned planned trial to one compiled lifecycle treatment."""

    planned: PlannedTrial
    compiled: CompiledLifecycle
    run_dir: Path
    execution_mode: LifecycleExecutionMode
    visibility_policy: LifecycleVisibilityPolicy
    sweep_context: LifecycleExperimentSweepContext | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_dir", Path(self.run_dir))
        if (
            self.execution_mode is LifecycleExecutionMode.PERSISTENT_CONTEXT
            and self.visibility_policy is not LifecycleVisibilityPolicy.PERSISTENT_CONTEXT
        ):
            raise ValueError("persistent_context execution requires persistent_context visibility")
        if (
            self.execution_mode is LifecycleExecutionMode.FRESH_CONTEXT
            and self.visibility_policy is LifecycleVisibilityPolicy.PERSISTENT_CONTEXT
        ):
            raise ValueError("fresh_context execution cannot use persistent_context visibility")

    @property
    def package_dir(self) -> Path:
        return self.compiled.package_dir

    @property
    def max_turns_per_session(self) -> int:
        parameters = self.planned.agent.parameters
        raw_value = parameters.get("max_turns_per_session", parameters.get("max_turns"))
        if raw_value is None:
            return 60 if self.execution_mode is LifecycleExecutionMode.PERSISTENT_CONTEXT else 20
        if isinstance(raw_value, bool) or not isinstance(raw_value, int) or raw_value < 1:
            raise ValueError("lifecycle agent max_turns_per_session must be a positive integer")
        return int(raw_value)


@dataclass(frozen=True, slots=True)
class LifecycleExecution:
    """Return lifecycle state and evidence needed for trial finalization."""

    state: dict[str, object]
    agent: dict[str, object]
    tool_schema: tuple[dict[str, Any], ...]


__all__ = ("LifecycleExecution", "LifecycleTrial")
