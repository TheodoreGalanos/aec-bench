# ABOUTME: Provides deterministic typed lifecycle episode environments for test scenarios.
# ABOUTME: Lets tests author submissions while exercising host-owned identity and attempts.

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aec_bench.meta_harness.evidence_lifecycle_episode import (
    InProcessLifecycleEpisodeEnvironment,
    LifecycleEpisodeRequest,
    LifecycleEpisodeResult,
    LifecycleEpisodeUsage,
    LifecycleVisibilityPolicy,
)


def deterministic_episode_environment(
    execute: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
) -> InProcessLifecycleEpisodeEnvironment:
    """Adapt deterministic test work to the strict production episode result contract."""

    def run(request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        configuration = execute(request.model_dump(mode="json"))
        return LifecycleEpisodeResult(
            episode_id=request.episode_id,
            attempt_id=request.attempt_id,
            session_id=request.session_id,
            checkpoint_ids=request.checkpoint_ids,
            execution_mode=request.execution_mode,
            memory_visibility_policy=request.memory_visibility_policy,
            status="completed",
            requested_adapter="deterministic",
            requested_model="gold",
            max_turns_per_session=request.max_turns_per_session,
            adapter="in_process",
            resolved_model="gold",
            configuration=configuration,
            usage=LifecycleEpisodeUsage(),
        )

    return InProcessLifecycleEpisodeEnvironment(
        executor=run,
        memory_visibility_policy=visibility_policy,
    )
