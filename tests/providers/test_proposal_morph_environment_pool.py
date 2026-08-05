# ABOUTME: Tests Morph's production factory for independently provisioned proposal leases.
# ABOUTME: Uses the existing in-process provider operations to prove identities and cleanup.

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path

import pytest
from harbor.models.trial.paths import TrialPaths  # type: ignore[import-untyped]

from aec_bench.harness.proposal_runtime_archive import ProposalRuntimeArchive
from aec_bench.providers.proposal_morph import (
    ProposalCandidateInvocationTransition,
    ProposalMorphBoundaryError,
    ProposalMorphHarborEnvironment,
)
from tests.providers.test_proposal_morph_harbor import (
    RecordingProposalMorphOperations,
    _environment_config,
    _MorphObject,
    _runtime_archive,
)


def test_morph_environment_factory_provisions_independent_pool_and_cleans_it(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    isolated_operations: list[_UniqueProposalMorphOperations] = []

    def operations_factory(slot: int) -> _UniqueProposalMorphOperations:
        operations = _UniqueProposalMorphOperations(
            identity_slot=slot,
            snapshot=_MorphObject(f"snapshot-pool-{slot:03d}"),
            instance=_MorphObject(f"instance-pool-{slot:03d}"),
        )
        isolated_operations.append(operations)
        return operations

    environment = _outer_environment(
        tmp_path=tmp_path,
        runtime=runtime,
        isolated_operations_factory=operations_factory,
    )
    asyncio.run(environment.start(force_build=False))
    transitions: list[ProposalCandidateInvocationTransition] = []

    async def exercise() -> None:
        async with environment.create_isolated_environment_pool(
            capacity=2,
            receipt_root=tmp_path / "session" / "environment-pool",
            expected_runtime_archive_sha256=runtime.archive_sha256,
            expected_runtime_archive_content_sha256=runtime.content_sha256,
        ) as pool:
            async with AsyncExitStack() as leases:
                first = await leases.enter_async_context(
                    pool.lease(invocation_id="001.first"),
                )
                second = await leases.enter_async_context(
                    pool.lease(invocation_id="002.second"),
                )
                transitions.extend(
                    await asyncio.gather(
                        first.reset_candidate_container_for_invocation(
                            invocation_id="001.first",
                            expected_runtime_digest=runtime.archive_sha256,
                        ),
                        second.reset_candidate_container_for_invocation(
                            invocation_id="002.second",
                            expected_runtime_digest=runtime.archive_sha256,
                        ),
                    )
                )

    asyncio.run(exercise())

    assert len(isolated_operations) == 2
    assert len({transition.previous_container_identity for transition in transitions}) == 2
    assert len({transition.current_container_identity for transition in transitions}) == 2
    assert all(operations.scrub_calls == 1 for operations in isolated_operations)
    assert all(operations.stop_instance_calls == 1 for operations in isolated_operations)
    assert all(operations.delete_snapshot_calls == 1 for operations in isolated_operations)
    manifest = json.loads(
        (tmp_path / "session" / "environment-pool" / "pool-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["capacity"] == 2
    assert manifest["runtime_archive_sha256"] == runtime.archive_sha256
    assert manifest["runtime_archive_content_sha256"] == runtime.content_sha256
    assert [item["trial_instance_identity"] for item in manifest["environments"]] == [
        "instance-pool-000",
        "instance-pool-001",
    ]
    asyncio.run(environment.stop(delete=True))


def test_morph_environment_rejects_custom_operations_without_isolated_factory(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    environment = _outer_environment(
        tmp_path=tmp_path,
        runtime=runtime,
        isolated_operations_factory=None,
    )
    asyncio.run(environment.start(force_build=False))

    with pytest.raises(
        ProposalMorphBoundaryError,
        match="isolated operations factory",
    ):
        environment.create_isolated_environment_pool(
            capacity=2,
            receipt_root=tmp_path / "session" / "environment-pool",
            expected_runtime_archive_sha256=runtime.archive_sha256,
            expected_runtime_archive_content_sha256=runtime.content_sha256,
        )

    asyncio.run(environment.stop(delete=True))


def test_morph_environment_pool_rejects_runtime_archive_rebinding(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    factory_calls: list[int] = []

    def operations_factory(slot: int) -> _UniqueProposalMorphOperations:
        factory_calls.append(slot)
        return _UniqueProposalMorphOperations(identity_slot=slot)

    environment = _outer_environment(
        tmp_path=tmp_path,
        runtime=runtime,
        isolated_operations_factory=operations_factory,
    )
    asyncio.run(environment.start(force_build=False))

    with pytest.raises(
        ProposalMorphBoundaryError,
        match="runtime archive binding",
    ):
        environment.create_isolated_environment_pool(
            capacity=2,
            receipt_root=tmp_path / "session" / "environment-pool",
            expected_runtime_archive_sha256="f" * 64,
            expected_runtime_archive_content_sha256=runtime.content_sha256,
        )

    assert factory_calls == []
    asyncio.run(environment.stop(delete=True))


def _outer_environment(
    *,
    tmp_path: Path,
    runtime: ProposalRuntimeArchive,
    isolated_operations_factory: (Callable[[int], RecordingProposalMorphOperations] | None),
) -> ProposalMorphHarborEnvironment:
    environment_dir = tmp_path / "task" / "environment"
    environment_dir.mkdir(parents=True, exist_ok=True)
    (environment_dir / "Dockerfile").write_text(
        "FROM python:3.13-slim\n",
        encoding="utf-8",
    )
    trial_paths = TrialPaths(tmp_path / "trial")
    trial_paths.mkdir()
    return ProposalMorphHarborEnvironment(
        environment_dir=environment_dir,
        environment_name="proposal-session",
        session_id="trial",
        trial_paths=trial_paths,
        task_env_config=_environment_config(),
        operations=RecordingProposalMorphOperations(),
        isolated_operations_factory=isolated_operations_factory,
        runtime_archive_path=runtime.path,
        runtime_archive_sha256=runtime.archive_sha256,
        runtime_archive_content_sha256=runtime.content_sha256,
    )


@dataclass
class _UniqueProposalMorphOperations(RecordingProposalMorphOperations):
    identity_slot: int = 0

    def start_proposal_container(self, *, role: str, **kwargs: object) -> str:
        del kwargs
        if role == "verifier" and self.failing_step == "start_verifier":
            raise RuntimeError("simulated verifier container start failure")
        self.current_container_identity = f"container-pool-{self.identity_slot:03d}-{role}"
        self.events.append(f"start_container:{role}")
        return self.current_container_identity
