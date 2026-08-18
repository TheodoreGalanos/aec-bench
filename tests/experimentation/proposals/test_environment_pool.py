# ABOUTME: Tests the bounded production pool used by ready-set proposal sessions.
# ABOUTME: Proves isolation, fail-closed capacity, cancellation cleanup, and full DAG receipts.

from __future__ import annotations

import asyncio
import hashlib
import json
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.proposal_execution_types import ProposalSessionStatus
from aec_bench.experimentation.proposals.environment_pool import (
    IsolatedProposalEnvironmentIdentity,
    IsolatedProposalEnvironmentPool,
    ProposalEnvironmentPoolError,
)
from aec_bench.experimentation.proposals.session_runtime import run_proposal_session
from tests.experimentation.proposals.test_ready_set_session import (
    _BranchOrderingEnvironment,
    _ready_set_bundle,
)
from tests.experimentation.proposals.test_session import (
    _execution_ref,
    _RecordedTransition,
)


def test_pool_leases_distinct_environments_and_never_waits_past_capacity(
    tmp_path: Path,
) -> None:
    bundle, _source_task_root = _ready_set_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    environments: list[_ManagedBranchEnvironment] = []
    pool = _pool(
        tmp_path=tmp_path,
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
        runtime_archive_content_sha256=execution.runtime_archive_content_sha256,
        environments=environments,
    )

    async def exercise() -> None:
        async with pool:
            async with AsyncExitStack() as leases:
                first = await leases.enter_async_context(
                    pool.lease(invocation_id="001.first"),
                )
                second = await leases.enter_async_context(
                    pool.lease(invocation_id="002.second"),
                )
                assert first is not second
                assert first.session_id != second.session_id
                with pytest.raises(ProposalEnvironmentPoolError) as exc_info:
                    async with pool.lease(invocation_id="003.overflow"):
                        pass
                assert exc_info.value.code == "environment_pool_exhausted"

            with pytest.raises(ProposalEnvironmentPoolError) as exc_info:
                async with pool.lease(invocation_id="001.first"):
                    pass
            assert exc_info.value.code == "environment_lease_replayed"

    asyncio.run(exercise())

    assert len(environments) == 2
    assert all(environment.started for environment in environments)
    assert all(environment.stopped_with_delete is True for environment in environments)
    _assert_content_addressed_json(pool.manifest_path)
    _assert_content_addressed_json(pool.cleanup_receipt_path)
    cleanup = json.loads(pool.cleanup_receipt_path.read_text(encoding="utf-8"))
    for item in cleanup["environments"]:
        artifact_path = pool.receipt_root / item["cleanup_receipt_path"]
        assert artifact_path.is_file()
        assert hashlib.sha256(artifact_path.read_bytes()).hexdigest() == (item["cleanup_receipt_sha256"])
    lease_receipts = sorted(pool.lease_receipts_dir.glob("*.json"))
    assert [json.loads(path.read_text())["invocation_id"] for path in lease_receipts] == [
        "001.first",
        "002.second",
    ]
    assert all(_assert_content_addressed_json(path) for path in lease_receipts)


def test_pool_fails_closed_on_shared_provider_identities_and_cleans_every_slot(
    tmp_path: Path,
) -> None:
    bundle, _source_task_root = _ready_set_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    environments: list[_ManagedBranchEnvironment] = []
    pool = _pool(
        tmp_path=tmp_path,
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
        runtime_archive_content_sha256=execution.runtime_archive_content_sha256,
        environments=environments,
        shared_identities=True,
    )

    with pytest.raises(ProposalEnvironmentPoolError) as exc_info:
        asyncio.run(pool.__aenter__())

    assert exc_info.value.code == "environment_pool_identity_collision"
    assert len(environments) == 2
    assert all(environment.stopped_with_delete is True for environment in environments)
    assert not pool.manifest_path.exists()
    _assert_content_addressed_json(pool.cleanup_receipt_path)


def test_pool_teardown_finishes_after_cancellation(
    tmp_path: Path,
) -> None:
    bundle, _source_task_root = _ready_set_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    environments: list[_ManagedBranchEnvironment] = []
    stop_release = asyncio.Event()
    pool = _pool(
        tmp_path=tmp_path,
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
        runtime_archive_content_sha256=execution.runtime_archive_content_sha256,
        environments=environments,
        stop_release=stop_release,
    )

    async def exercise() -> None:
        await pool.__aenter__()
        closing = asyncio.create_task(pool.__aexit__(None, None, None))
        while not environments or not all(environment.stop_started for environment in environments):
            await asyncio.sleep(0)
        closing.cancel()
        stop_release.set()
        with pytest.raises(asyncio.CancelledError):
            await closing

    asyncio.run(exercise())

    assert all(environment.stopped_with_delete is True for environment in environments)
    _assert_content_addressed_json(pool.cleanup_receipt_path)


def test_ready_set_session_runs_through_production_pool_with_stable_receipts(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _ready_set_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    environments: list[_ManagedBranchEnvironment] = []
    pool = _pool(
        tmp_path=tmp_path,
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
        runtime_archive_content_sha256=execution.runtime_archive_content_sha256,
        environments=environments,
    )

    async def execute() -> Any:
        async with pool:
            return await run_proposal_session(
                bundle=bundle,
                execution=execution,
                source_task_root=source_task_root,
                session_root=tmp_path / "session",
                environment_pool=pool,
            )

    receipt = asyncio.run(execute())

    assert receipt.status is ProposalSessionStatus.COMPLETED
    assert receipt.trial_record_permitted is True
    assert tuple(node.node_id for node in receipt.node_receipts) == (
        "analyse",
        "assess-a",
        "assess-b",
        "finalize",
    )
    assert len(tuple(pool.lease_receipts_dir.glob("*.json"))) == 4
    transitions = tuple(node.container_transition for node in receipt.node_receipts)
    assert all(transition is not None for transition in transitions)
    previous = tuple(transition.previous_container_identity for transition in transitions if transition)
    current = tuple(transition.current_container_identity for transition in transitions if transition)
    assert len(previous) == len(set(previous))
    assert len(current) == len(set(current))


def _pool(
    *,
    tmp_path: Path,
    bundle: Any,
    runtime_archive_sha256: str,
    runtime_archive_content_sha256: str,
    environments: list[_ManagedBranchEnvironment],
    shared_identities: bool = False,
    stop_release: asyncio.Event | None = None,
) -> IsolatedProposalEnvironmentPool:
    branch_b_completed = asyncio.Event()
    completion_order: list[str] = []

    def factory(slot: int) -> _ManagedBranchEnvironment:
        identity_slot = 0 if shared_identities else slot
        environment = _ManagedBranchEnvironment(
            slot=slot,
            identity_slot=identity_slot,
            session_id=f"proposal-pool.slot-{identity_slot:03d}",
            root=tmp_path / "environments" / f"slot-{slot:03d}",
            bundle=bundle,
            runtime_archive_sha256=runtime_archive_sha256,
            runtime_archive_content_sha256=runtime_archive_content_sha256,
            branch_b_completed=branch_b_completed,
            execution_completion_order=completion_order,
            stop_release=stop_release,
        )
        environments.append(environment)
        return environment

    return IsolatedProposalEnvironmentPool(
        capacity=2,
        receipt_root=tmp_path / "pool-receipts",
        expected_runtime_archive_sha256=runtime_archive_sha256,
        expected_runtime_archive_content_sha256=runtime_archive_content_sha256,
        environment_factory=factory,
    )


class _ManagedBranchEnvironment(_BranchOrderingEnvironment):
    def __init__(
        self,
        *,
        slot: int,
        identity_slot: int,
        session_id: str,
        root: Path,
        bundle: Any,
        runtime_archive_sha256: str,
        runtime_archive_content_sha256: str,
        branch_b_completed: asyncio.Event,
        execution_completion_order: list[str],
        stop_release: asyncio.Event | None,
    ) -> None:
        self.slot = slot
        self.identity_slot = identity_slot
        self.session_id = session_id
        self.runtime_archive_content_sha256 = runtime_archive_content_sha256
        self.started = False
        self.stop_started = False
        self.stopped_with_delete: bool | None = None
        self.stop_release = stop_release
        self.cleanup_receipt_path = root / "cleanup.json"
        super().__init__(
            branch_b_completed=branch_b_completed,
            execution_completion_order=execution_completion_order,
            initial_identity=f"container.initial.slot-{identity_slot:03d}",
            root=root,
            bundle=bundle,
            runtime_archive_sha256=runtime_archive_sha256,
            failed_node_ids=set(),
        )

    async def start(self, force_build: bool) -> None:
        assert force_build is False
        self.started = True

    async def stop(self, delete: bool) -> None:
        self.stop_started = True
        if self.stop_release is not None:
            await self.stop_release.wait()
        self.stopped_with_delete = delete
        payload: dict[str, object] = {
            "schema_version": "test.proposal-environment-cleanup.v1",
            "status": "completed",
            "environment_session_id": self.session_id,
            "delete_requested": delete,
        }
        payload["content_sha256"] = canonical_json_sha256(payload)
        self.cleanup_receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.cleanup_receipt_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def isolated_environment_identity(self) -> IsolatedProposalEnvironmentIdentity:
        return IsolatedProposalEnvironmentIdentity(
            environment_session_id=self.session_id,
            runtime_snapshot_identity=f"snapshot.slot-{self.identity_slot:03d}",
            trial_instance_identity=f"instance.slot-{self.identity_slot:03d}",
            candidate_container_identity=self._container_identity,
            runtime_archive_sha256=self.runtime_archive_sha256,
            runtime_archive_content_sha256=self.runtime_archive_content_sha256,
        )

    async def reset_candidate_container_for_invocation(
        self,
        *,
        invocation_id: str,
        expected_runtime_digest: str,
    ) -> _RecordedTransition:
        transition = await super().reset_candidate_container_for_invocation(
            invocation_id=invocation_id,
            expected_runtime_digest=expected_runtime_digest,
        )
        current_identity = f"slot-{self.identity_slot:03d}.{transition.current_container_identity}"
        self._container_identity = current_identity
        payload = json.loads(transition.receipt_path.read_text(encoding="utf-8"))
        payload.pop("content_sha256")
        payload["current_container_identity"] = current_identity
        payload["content_sha256"] = canonical_json_sha256(payload)
        transition.receipt_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return _RecordedTransition(
            invocation_id=transition.invocation_id,
            previous_container_identity=transition.previous_container_identity,
            current_container_identity=current_identity,
            runtime_archive_sha256=transition.runtime_archive_sha256,
            receipt_path=transition.receipt_path,
        )


def _assert_content_addressed_json(path: Path) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    observed = payload.pop("content_sha256")
    assert observed == canonical_json_sha256(payload)
    return True
