# ABOUTME: Provisions one Morph runtime snapshot, instance, and initialized candidate container.
# ABOUTME: Returns provider state only after success and rolls back every partial resource.

from __future__ import annotations

from functools import partial
from pathlib import Path

from aec_bench.providers.morph_cloud import MorphCommandResult

from .async_ops import run_provisioning_call
from .boundary import ProposalMorphBoundaryError, ProposalMorphState
from .cleanup import delete_snapshot_errors, teardown_errors
from .constants import REMOTE_LOGS_DIR, REMOTE_TESTS_DIR, REMOTE_WORKSPACE_DIR
from .operations import ProposalMorphHarborOperations


async def provision_environment(
    *,
    operations: ProposalMorphHarborOperations,
    dockerfile_path: Path,
    context_dir: Path,
    runtime_archive_path: Path,
    runtime_archive_sha256: str,
    runtime_archive_content_sha256: str,
    runtime_packages: tuple[str, ...],
) -> ProposalMorphState:
    """Create all provider resources atomically from the caller's perspective."""

    async def cleanup_cancelled_snapshot(snapshot: object | None) -> list[Exception]:
        if snapshot is None:
            return []
        return await delete_snapshot_errors(
            operations=operations,
            snapshot=snapshot,
        )

    snapshot = await run_provisioning_call(
        partial(
            operations.build_proposal_runtime_snapshot,
            dockerfile_path=dockerfile_path,
            context_dir=context_dir,
            runtime_archive_path=runtime_archive_path,
            runtime_archive_sha256=runtime_archive_sha256,
            runtime_archive_content_sha256=runtime_archive_content_sha256,
            runtime_packages=runtime_packages,
        ),
        label="runtime snapshot build",
        cancel_cleanup=cleanup_cancelled_snapshot,
    )
    instance: object | None = None
    try:
        instance = await _start_instance(
            operations=operations,
            snapshot=snapshot,
        )
        identity = await _start_candidate_container(
            operations=operations,
            snapshot=snapshot,
            instance=instance,
        )
        await _initialize_candidate_container(
            operations=operations,
            snapshot=snapshot,
            instance=instance,
        )
        return ProposalMorphState(
            snapshot=snapshot,
            instance=instance,
            container_identity=identity,
        )
    except Exception as error:
        cleanup_errors = (
            await delete_snapshot_errors(
                operations=operations,
                snapshot=snapshot,
            )
            if instance is None
            else await teardown_errors(
                operations=operations,
                snapshot=snapshot,
                instance=instance,
                delete=True,
            )
        )
        if cleanup_errors:
            raise BaseExceptionGroup(
                "proposal Morph Harbor start and rollback failed",
                [error, *cleanup_errors],
            ) from error
        raise


async def _start_instance(
    *,
    operations: ProposalMorphHarborOperations,
    snapshot: object,
) -> object:
    async def cleanup_cancelled_instance(
        provisioned_instance: object | None,
    ) -> list[Exception]:
        if provisioned_instance is None:
            return await delete_snapshot_errors(
                operations=operations,
                snapshot=snapshot,
            )
        return await teardown_errors(
            operations=operations,
            snapshot=snapshot,
            instance=provisioned_instance,
            delete=True,
        )

    return await run_provisioning_call(
        partial(operations.start_instance, snapshot=snapshot),
        label="instance start",
        cancel_cleanup=cleanup_cancelled_instance,
    )


async def _start_candidate_container(
    *,
    operations: ProposalMorphHarborOperations,
    snapshot: object,
    instance: object,
) -> str:
    async def cleanup_cancelled_container(
        _identity: str | None,
    ) -> list[Exception]:
        return await teardown_errors(
            operations=operations,
            snapshot=snapshot,
            instance=instance,
            delete=True,
        )

    identity = await run_provisioning_call(
        partial(
            operations.start_proposal_container,
            instance=instance,
            role="candidate.initial",
            workspace_dir=REMOTE_WORKSPACE_DIR,
            logs_dir=REMOTE_LOGS_DIR,
            tests_dir=REMOTE_TESTS_DIR,
        ),
        label="candidate-container start",
        cancel_cleanup=cleanup_cancelled_container,
    )
    if not identity:
        raise ProposalMorphBoundaryError("proposal candidate container has no provider identity")
    return identity


async def _initialize_candidate_container(
    *,
    operations: ProposalMorphHarborOperations,
    snapshot: object,
    instance: object,
) -> None:
    async def cleanup_cancelled_initialization(
        _result: MorphCommandResult | None,
    ) -> list[Exception]:
        return await teardown_errors(
            operations=operations,
            snapshot=snapshot,
            instance=instance,
            delete=True,
        )

    result = await run_provisioning_call(
        partial(
            operations.run_container_command_result,
            instance=instance,
            command=(
                "bash",
                "-lc",
                "mkdir -p /logs/agent /logs/verifier /logs/artifacts /workspace",
            ),
        ),
        label="candidate-container initialization",
        cancel_cleanup=cleanup_cancelled_initialization,
    )
    if result.exit_code != 0:
        raise RuntimeError(f"proposal candidate container initialization failed: {result.stderr.strip()}")
