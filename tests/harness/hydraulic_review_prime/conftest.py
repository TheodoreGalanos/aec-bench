# ABOUTME: Builds one real active hydraulic-review checkpoint for scoped Prime endpoint tests.
# ABOUTME: Keeps test setup on the current lifecycle and hydraulic operation contracts.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from aec_bench.harness.hydraulic_review_prime.endpoint import HydraulicReviewPrimeLifecycleEndpoint
from aec_bench.lifecycles.runtime.episode import (
    LifecycleEpisodeContext,
    LifecycleEpisodeRequest,
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)
from aec_bench.lifecycles.runtime.lifecycle import open_checkpoint_attempt, prepare_evidence_checkpoint
from aec_bench.lifecycles.runtime.operation_protocol import LifecycleOperationResolver
from aec_bench.lifecycles.stormwater_design.hydraulic_review import (
    build_hydraulic_operation_resolver,
    materialize_hydraulic_review_lifecycle,
)


@dataclass(frozen=True)
class ActiveCheckpoint:
    package: Path
    run: Path
    actor: Path
    resolver: LifecycleOperationResolver
    request: LifecycleEpisodeRequest
    endpoint: HydraulicReviewPrimeLifecycleEndpoint


@pytest.fixture
def active_checkpoint(tmp_path: Path) -> ActiveCheckpoint:
    package = materialize_hydraulic_review_lifecycle(tmp_path / "package")
    run = tmp_path / "run"
    resolver = build_hydraulic_operation_resolver(package, run)
    raw = prepare_evidence_checkpoint(package, run, operation_resolver=resolver)
    context = LifecycleEpisodeContext.from_runtime_context(
        raw,
        visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
    )
    request = LifecycleEpisodeRequest(
        episode_id=f"{context.lifecycle_id}.baseline_analysis.attempt-001",
        lifecycle_id=context.lifecycle_id,
        lifecycle_spec_sha256=context.lifecycle_spec_sha256,
        package_sha256=context.package_sha256,
        checkpoint_id=context.checkpoint_id,
        checkpoint_ids=(context.checkpoint_id,),
        attempt_id="baseline_analysis.attempt-001",
        session_id="baseline_analysis.session-001",
        execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
        memory_visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        requested_adapter="prime-agent",
        requested_model="anthropic/test",
        max_turns_per_session=10,
        title=context.title,
        instruction=context.instruction,
        workspace=context.workspace,
        run_dir=context.run_dir,
        instruction_path=context.instruction_path,
        submission_path=context.submission_path,
        released_files=context.released_files,
        evidence_request_catalog=context.evidence_request_catalog,
        released_evidence_artifacts=context.released_evidence_artifacts,
        operation_catalog=context.operation_catalog,
        current_source=context.current_source,
        visible_operation_artifacts=context.visible_operation_artifacts,
        completed_checkpoint_ids=context.completed_checkpoint_ids,
    )
    open_checkpoint_attempt(
        package,
        run,
        operation_resolver=resolver,
        session_id=request.session_id,
        execution_mode=request.execution_mode.value,
    )
    actor = tmp_path / "actor"
    actor.mkdir()
    endpoint = HydraulicReviewPrimeLifecycleEndpoint(
        package_dir=package,
        run_dir=run,
        request=request,
        operation_resolver=resolver,
        socket_directory=actor / ".lifecycle",
        evidence_file=tmp_path / "endpoint-evidence.jsonl",
    )
    return ActiveCheckpoint(
        package=package,
        run=run,
        actor=actor,
        resolver=resolver,
        request=request,
        endpoint=endpoint,
    )
