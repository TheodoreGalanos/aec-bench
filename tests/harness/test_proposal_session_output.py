# ABOUTME: Tests verified publication of pooled proposal final output to Harbor.
# ABOUTME: Proves completed bytes bind the receipt and candidate failures publish nothing.

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from aec_bench.harness.proposal_session import run_proposal_session
from aec_bench.harness.proposal_session_output import (
    ProposalSessionOutputError,
    verified_proposal_final_output_path,
)
from tests.harness.test_proposal_ready_set_session import (
    _ready_set_bundle,
    _RecordingProposalEnvironmentPool,
)
from tests.harness.test_proposal_session import _execution_ref


def test_completed_session_resolves_exact_finalizer_output(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _ready_set_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    pool = _RecordingProposalEnvironmentPool(
        root=tmp_path / "pool",
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
        capacity=2,
    )
    session_root = tmp_path / "session"
    receipt = asyncio.run(
        run_proposal_session(
            bundle=bundle,
            execution=execution,
            source_task_root=source_task_root,
            session_root=session_root,
            environment_pool=pool,
        )
    )

    output_path = verified_proposal_final_output_path(
        session_root=session_root,
        receipt=receipt,
    )

    assert output_path is not None
    assert hashlib.sha256(output_path.read_bytes()).hexdigest() == (receipt.final_output_artifact_sha256)


def test_candidate_failure_has_no_publishable_final_output(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _ready_set_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    pool = _RecordingProposalEnvironmentPool(
        root=tmp_path / "pool",
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
        capacity=2,
        failed_node_ids={"assess-a"},
    )
    session_root = tmp_path / "session"
    receipt = asyncio.run(
        run_proposal_session(
            bundle=bundle,
            execution=execution,
            source_task_root=source_task_root,
            session_root=session_root,
            environment_pool=pool,
        )
    )

    assert (
        verified_proposal_final_output_path(
            session_root=session_root,
            receipt=receipt,
        )
        is None
    )


def test_completed_session_rejects_tampered_finalizer_output(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _ready_set_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    pool = _RecordingProposalEnvironmentPool(
        root=tmp_path / "pool",
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
        capacity=2,
    )
    session_root = tmp_path / "session"
    receipt = asyncio.run(
        run_proposal_session(
            bundle=bundle,
            execution=execution,
            source_task_root=source_task_root,
            session_root=session_root,
            environment_pool=pool,
        )
    )
    finalizer = next(
        node
        for node in receipt.node_receipts
        if node.node_id == receipt.plan.compilation.proposal_graph.finalizer.node_id
    )
    assert finalizer.invocation_id is not None
    (session_root / "invocations" / finalizer.invocation_id / "output.bin").write_bytes(b"tampered\n")

    with pytest.raises(ProposalSessionOutputError) as exc_info:
        verified_proposal_final_output_path(
            session_root=session_root,
            receipt=receipt,
        )

    assert exc_info.value.code == "final_output_identity_mismatch"
