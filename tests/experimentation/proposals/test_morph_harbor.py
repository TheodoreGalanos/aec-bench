# ABOUTME: Proves proposal-only Morph execution crosses a hard candidate-to-verifier container boundary.
# ABOUTME: Covers filtered runtime identity, sealed artifacts, retry integrity, and a live background-watcher attack.

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from harbor.environments.factory import EnvironmentFactory  # type: ignore[import-untyped]
from harbor.models.task.config import EnvironmentConfig  # type: ignore[import-untyped]
from harbor.models.trial.config import (  # type: ignore[import-untyped]
    EnvironmentConfig as TrialEnvironmentConfig,
)
from harbor.models.trial.paths import TrialPaths  # type: ignore[import-untyped]

from aec_bench.contracts.execution_environment import RUNTIME_PYTHON_PACKAGES
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.program_proposal.study import MatchedEvaluationCoordinate
from aec_bench.contracts.proposal_execution.session import (
    ProposalNodeReceipt,
    ProposalSessionExecutionRef,
    ProposalSessionPlan,
    ProposalSessionReceipt,
)
from aec_bench.contracts.proposal_execution_types import (
    ProposalCandidateFailureCode,
    ProposalContractCheckStatus,
    ProposalNodeReceiptStatus,
    ProposalSessionStatus,
)
from aec_bench.experimentation.proposals.morph import (
    PROPOSAL_MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH,
    ProposalMorphBoundaryError,
    ProposalMorphHarborEnvironment,
    load_completed_proposal_morph_cleanup_receipt,
)
from aec_bench.experimentation.proposals.runtime_archive import ProposalRuntimeArchive
from aec_bench.providers.morph_cloud import MorphCommandResult
from tests.contracts.test_proposal_execution import (
    _node_receipts as _proposal_contract_node_receipts,
)
from tests.contracts.test_proposal_execution import (
    _success as _proposal_contract_success,
)


def test_proposal_environment_builds_only_from_the_pinned_runtime_archive(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations()
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )

    _run(environment.start(force_build=False))

    assert operations.builds == [
        {
            "dockerfile_path": environment.environment_dir / "Dockerfile",
            "context_dir": environment.environment_dir,
            "runtime_archive_path": runtime.path,
            "runtime_archive_sha256": runtime.archive_sha256,
            "runtime_archive_content_sha256": runtime.content_sha256,
            "runtime_packages": RUNTIME_PYTHON_PACKAGES,
        }
    ]
    assert "project_src_dir" not in operations.builds[0]


def test_proposal_environment_import_path_constructs_through_harbor(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations()
    environment_dir = tmp_path / "import-task" / "environment"
    environment_dir.mkdir(parents=True)
    (environment_dir / "Dockerfile").write_text(
        "FROM python:3.13-slim\n",
        encoding="utf-8",
    )
    trial_paths = TrialPaths(tmp_path / "import-trial")
    trial_paths.mkdir()

    environment = EnvironmentFactory.create_environment_from_config(
        config=TrialEnvironmentConfig(
            import_path=PROPOSAL_MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH,
            kwargs={
                "operations": operations,
                "runtime_archive_path": runtime.path,
                "runtime_archive_sha256": runtime.archive_sha256,
                "runtime_archive_content_sha256": runtime.content_sha256,
            },
        ),
        environment_dir=environment_dir,
        environment_name="proposal-session",
        session_id="import-trial",
        trial_paths=trial_paths,
        task_env_config=_environment_config(),
    )

    assert isinstance(environment, ProposalMorphHarborEnvironment)


def test_proposal_environment_rejects_runtime_package_override(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)

    with pytest.raises(
        ProposalMorphBoundaryError,
        match="governed runtime lock",
    ):
        _environment(
            tmp_path=tmp_path,
            operations=RecordingProposalMorphOperations(),
            runtime=runtime,
            runtime_packages=("aec-bench @ git+https://example.invalid/repository.git",),
        )


def test_proposal_environment_rotates_before_tests_and_seals_agent_artifacts(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations(
        stopped_artifacts={
            "/workspace/output.md": b"answer\n",
            "/workspace/agent_result.json": b'{"status":"completed"}\n',
            "/workspace/proposal-session/session-receipt.json": b'{"status":"completed"}\n',
        }
    )
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    tests_dir = _tests_dir(tmp_path)
    _run(environment.start(force_build=False))

    _run(environment.upload_dir(tests_dir, "/tests"))

    assert operations.events == [
        "build",
        "start_instance",
        "start_container:candidate.initial",
        "exec:candidate.initial",
        "stop_container:container-candidate.initial",
        "read_stopped_artifacts",
        "reset_mounts",
        "start_container:verifier",
        "write:/workspace/output.md",
        "upload:/tests",
    ]
    assert operations.writes == [
        ("/workspace/output.md", b"answer\n"),
    ]
    assert "/workspace/agent_result.json" not in dict(operations.writes)
    assert not any(path.startswith("/workspace/proposal-session/") for path, _content in operations.writes)

    downloaded = tmp_path / "downloaded-agent-result.json"
    _run(environment.download_file("/workspace/agent_result.json", downloaded))
    assert downloaded.read_bytes() == b'{"status":"completed"}\n'

    proposal_session = tmp_path / "downloaded-session"
    _run(environment.download_dir("/workspace/proposal-session", proposal_session))
    assert (proposal_session / "session-receipt.json").read_bytes() == b'{"status":"completed"}\n'

    manifest = json.loads(environment.seal_manifest_path.read_text(encoding="utf-8"))
    assert [item["path"] for item in manifest["artifacts"]] == [
        "/workspace/agent_result.json",
        "/workspace/output.md",
        "/workspace/proposal-session/session-receipt.json",
    ]
    assert manifest["runtime_archive_sha256"] == runtime.archive_sha256
    receipt = json.loads(environment.rotation_receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "completed"
    assert receipt["candidate_container_identity"] == "container-candidate.initial"
    assert receipt["verifier_container_identity"] == "container-verifier"
    assert receipt["candidate_container_stopped"] is True
    assert receipt["mounts_wiped"] is True
    assert receipt["output_restored"] is True
    assert receipt["tests_uploaded"] is True
    assert receipt["sealed_output_sha256"] == hashlib.sha256(b"answer\n").hexdigest()
    assert "handoff_variant" not in receipt
    assert "candidate_failure_session_receipt_sha256" not in receipt


def test_candidate_failure_session_rotates_without_fabricating_final_output(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    session = _proposal_session_receipt(
        runtime=runtime,
        environment_session_id="trial-default",
        candidate_failure=True,
    )
    receipt_bytes = _proposal_session_receipt_bytes(session)
    operations = RecordingProposalMorphOperations(
        stopped_artifacts={
            "/workspace/proposal-session/session-receipt.json": receipt_bytes,
            "/workspace/proposal-session/artifacts/failure-evidence.json": (b'{"failure":"token_budget_exhausted"}\n'),
        }
    )
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    _run(environment.start(force_build=False))

    _run(environment.upload_dir(_tests_dir(tmp_path), "/tests"))

    assert not any(path == "/workspace/output.md" for path, _content in operations.writes)
    downloaded = tmp_path / "candidate-failure-session"
    _run(environment.download_dir("/workspace/proposal-session", downloaded))
    assert (downloaded / "session-receipt.json").read_bytes() == receipt_bytes
    assert (
        downloaded / "artifacts" / "failure-evidence.json"
    ).read_bytes() == b'{"failure":"token_budget_exhausted"}\n'
    rotation = json.loads(environment.rotation_receipt_path.read_text(encoding="utf-8"))
    assert rotation["status"] == "completed"
    assert rotation["handoff_variant"] == "candidate_failure"
    assert rotation["candidate_failure_session_receipt_sha256"] == session.content_sha256
    assert rotation["output_restored"] is False
    assert rotation["sealed_output_sha256"] is None

    _run(environment.stop(delete=True))

    cleanup = json.loads(environment.cleanup_receipt_path.read_text(encoding="utf-8"))
    assert cleanup["status"] == "completed"
    assert cleanup["handoff_variant"] == "candidate_failure"
    assert cleanup["candidate_failure_session_receipt_sha256"] == session.content_sha256
    loaded = load_completed_proposal_morph_cleanup_receipt(
        environment.cleanup_receipt_path,
        expected_runtime_archive_sha256=runtime.archive_sha256,
        expected_runtime_archive_content_sha256=runtime.content_sha256,
    )
    assert loaded.handoff_variant == "candidate_failure"
    assert loaded.candidate_failure_session_receipt_sha256 == session.content_sha256


@pytest.mark.parametrize(
    ("receipt_kind", "message"),
    (
        ("malformed", "session receipt is invalid"),
        ("tampered", "session receipt is invalid"),
        ("wrong_runtime", "runtime archive"),
        ("wrong_session", "session lineage"),
        ("completed", "candidate-failure"),
    ),
)
def test_outputless_rotation_requires_exact_matching_candidate_failure_receipt(
    tmp_path: Path,
    receipt_kind: str,
    message: str,
) -> None:
    runtime = _runtime_archive(tmp_path)
    if receipt_kind == "malformed":
        receipt_bytes = b"{not-json}\n"
    else:
        session = _proposal_session_receipt(
            runtime=runtime,
            environment_session_id=("different-environment" if receipt_kind == "wrong_session" else "trial-default"),
            candidate_failure=receipt_kind != "completed",
            runtime_archive_sha256=(
                hashlib.sha256(b"different-runtime").hexdigest() if receipt_kind == "wrong_runtime" else None
            ),
        )
        receipt_bytes = _proposal_session_receipt_bytes(session)
        if receipt_kind == "tampered":
            payload = json.loads(receipt_bytes)
            payload["trial_record_permitted"] = True
            receipt_bytes = (json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n").encode()
    operations = RecordingProposalMorphOperations(
        stopped_artifacts={
            "/workspace/proposal-session/session-receipt.json": receipt_bytes,
        }
    )
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    _run(environment.start(force_build=False))

    with pytest.raises(ProposalMorphBoundaryError, match=message):
        _run(environment.upload_dir(_tests_dir(tmp_path), "/tests"))

    assert "upload:/tests" not in operations.events
    rotation = json.loads(environment.rotation_receipt_path.read_text(encoding="utf-8"))
    assert rotation["status"] == "failed"


def test_proposal_environment_retries_only_the_same_tests_payload_without_rotating_again(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations(stopped_artifacts={"/workspace/output.md": b"answer\n"})
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    tests_dir = _tests_dir(tmp_path)
    _run(environment.start(force_build=False))
    _run(environment.upload_dir(tests_dir, "/tests"))

    _run(environment.upload_dir(tests_dir, "/tests"))

    assert operations.events.count("stop_container:container-candidate.initial") == 1
    assert operations.events.count("start_container:verifier") == 1
    assert operations.events.count("upload:/tests") == 2

    (tests_dir / "canary.json").write_text('{"canary":"changed"}\n', encoding="utf-8")
    with pytest.raises(ProposalMorphBoundaryError, match="tests payload changed"):
        _run(environment.upload_dir(tests_dir, "/tests"))
    assert operations.events.count("upload:/tests") == 2


def test_proposal_environment_rejects_mutated_pinned_tests_snapshot(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations(stopped_artifacts={"/workspace/output.md": b"answer\n"})
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    tests_dir = _tests_dir(tmp_path)
    _run(environment.start(force_build=False))
    _run(environment.upload_dir(tests_dir, "/tests"))
    (environment.boundary_dir / "verifier-tests" / "canary.json").write_text(
        '{"canary":"attacker-mutated"}\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ProposalMorphBoundaryError,
        match="pinned proposal verifier tests snapshot changed",
    ):
        _run(environment.upload_dir(tests_dir, "/tests"))

    assert operations.events.count("upload:/tests") == 1


def test_proposal_environment_preserves_verifier_helper_executable_mode(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations(stopped_artifacts={"/workspace/output.md": b"answer\n"})
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    tests_dir = _tests_dir(tmp_path)
    helper = tests_dir / "helper.sh"
    helper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    helper.chmod(0o755)
    _run(environment.start(force_build=False))

    _run(environment.upload_dir(tests_dir, "/tests"))

    pinned_helper = environment.boundary_dir / "verifier-tests" / "helper.sh"
    assert stat.S_IMODE(pinned_helper.stat().st_mode) == 0o755


def test_proposal_environment_resets_candidate_container_between_model_invocations(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations()
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    _run(environment.start(force_build=False))

    transition = _run(
        environment.reset_candidate_container_for_invocation(
            invocation_id="semantic-node-2",
            expected_runtime_digest=runtime.archive_sha256,
        )
    )

    assert transition.invocation_id == "semantic-node-2"
    assert transition.previous_container_identity == "container-candidate.initial"
    assert transition.current_container_identity == "container-candidate.semantic-node-2"
    assert transition.container_identity == "container-candidate.semantic-node-2"
    assert transition.runtime_archive_sha256 == runtime.archive_sha256
    assert operations.events[-3:] == [
        "stop_container:container-candidate.initial",
        "reset_mounts",
        "start_container:candidate.semantic-node-2",
    ]
    receipt = json.loads(transition.receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "completed"
    assert receipt["current_container_identity"] == ("container-candidate.semantic-node-2")
    assert "container_identity" not in receipt
    assert receipt["workspace_wiped"] is True
    assert receipt["candidate_logs_wiped"] is True
    assert receipt["runtime_archive_sha256"] == runtime.archive_sha256

    with pytest.raises(ProposalMorphBoundaryError, match="already has a reset receipt"):
        _run(
            environment.reset_candidate_container_for_invocation(
                invocation_id="semantic-node-2",
                expected_runtime_digest=runtime.archive_sha256,
            )
        )
    with pytest.raises(ProposalMorphBoundaryError, match="runtime digest"):
        _run(
            environment.reset_candidate_container_for_invocation(
                invocation_id="semantic-node-3",
                expected_runtime_digest=hashlib.sha256(b"wrong").hexdigest(),
            )
        )


@pytest.mark.parametrize(
    "failing_step",
    ("stop_container", "read_stopped_artifacts", "reset_mounts", "start_verifier"),
)
def test_proposal_environment_never_uploads_tests_when_rotation_fails(
    tmp_path: Path,
    failing_step: str,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations(
        stopped_artifacts={"/workspace/output.md": b"answer\n"},
        failing_step=failing_step,
    )
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    _run(environment.start(force_build=False))

    with pytest.raises(RuntimeError, match="simulated"):
        _run(environment.upload_dir(_tests_dir(tmp_path), "/tests"))

    assert "upload:/tests" not in operations.events
    receipt = json.loads(environment.rotation_receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["tests_uploaded"] is False
    with pytest.raises(ProposalMorphBoundaryError, match="boundary is broken"):
        _run(environment.exec("true"))


def test_proposal_environment_refuses_to_remove_an_unexpected_container(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations(stopped_artifacts={"/workspace/output.md": b"answer\n"})
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    _run(environment.start(force_build=False))
    operations.current_container_identity = "container-unexpected"

    with pytest.raises(RuntimeError, match="identity changed before removal"):
        _run(environment.upload_dir(_tests_dir(tmp_path), "/tests"))

    assert "upload:/tests" not in operations.events
    receipt = json.loads(environment.rotation_receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["candidate_container_stopped"] is False


def test_proposal_environment_fails_closed_for_missing_or_unexpected_handoff(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    for artifacts, message in (
        (
            {"/workspace/agent_result.json": b"{}\n"},
            "candidate-failure session receipt",
        ),
        (
            {
                "/workspace/output.md": b"answer\n",
                "/workspace/poison.py": b"raise SystemExit('owned')\n",
            },
            "unallowlisted",
        ),
    ):
        operations = RecordingProposalMorphOperations(stopped_artifacts=artifacts)
        environment = _environment(
            tmp_path=tmp_path,
            operations=operations,
            runtime=runtime,
            suffix=hashlib.sha256(repr(artifacts).encode()).hexdigest()[:8],
        )
        _run(environment.start(force_build=False))

        with pytest.raises(ProposalMorphBoundaryError, match=message):
            _run(environment.upload_dir(_tests_dir(tmp_path), "/tests"))

        assert "upload:/tests" not in operations.events


def test_proposal_environment_rejects_noncanonical_remote_paths(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations()
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    _run(environment.start(force_build=False))
    source = tmp_path / "payload.txt"
    source.write_text("payload\n", encoding="utf-8")

    with pytest.raises(ProposalMorphBoundaryError, match="absolute and canonical"):
        _run(environment.upload_file(source, "/workspace/../../tests/canary.json"))

    assert not any(event.startswith("write:/tests") for event in operations.events)


def test_proposal_environment_detects_sealed_artifact_mutation(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations(stopped_artifacts={"/workspace/output.md": b"answer\n"})
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    _run(environment.start(force_build=False))
    _run(environment.upload_dir(_tests_dir(tmp_path), "/tests"))
    (environment.seal_dir / "workspace" / "output.md").write_bytes(b"tamper\n")

    with pytest.raises(ProposalMorphBoundaryError, match="changed after capture"):
        _run(
            environment.download_file(
                "/workspace/output.md",
                tmp_path / "downloaded-output.md",
            )
        )


def test_cancelled_candidate_upload_finishes_before_verifier_rotation(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    write_started = threading.Event()
    release_write = threading.Event()
    operations = RecordingProposalMorphOperations(
        stopped_artifacts={"/workspace/output.md": b"answer\n"},
        blocked_write_path="/workspace/late.txt",
        write_started=write_started,
        release_write=release_write,
    )
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    source = tmp_path / "late.txt"
    source.write_text("candidate bytes\n", encoding="utf-8")

    async def exercise() -> None:
        await environment.start(force_build=False)
        candidate_upload = asyncio.create_task(environment.upload_file(source, "/workspace/late.txt"))
        assert await asyncio.to_thread(write_started.wait, 1.0)
        candidate_upload.cancel()
        verifier_rotation = asyncio.create_task(environment.upload_dir(_tests_dir(tmp_path), "/tests"))
        await asyncio.sleep(0)
        assert not candidate_upload.done()
        assert "stop_container:container-candidate.initial" not in operations.events

        release_write.set()
        with pytest.raises(asyncio.CancelledError):
            await candidate_upload
        await verifier_rotation

    _run(exercise())

    candidate_write_index = operations.events.index("write:/workspace/late.txt")
    candidate_stop_index = operations.events.index("stop_container:container-candidate.initial")
    assert candidate_write_index < candidate_stop_index


def test_concurrent_stop_waits_for_start_and_cleans_provisioned_resources(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    build_started = threading.Event()
    release_build = threading.Event()
    operations = RecordingProposalMorphOperations(
        build_started=build_started,
        release_build=release_build,
    )
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )

    async def exercise() -> None:
        start = asyncio.create_task(environment.start(force_build=False))
        assert await asyncio.to_thread(build_started.wait, 1.0)
        stop = asyncio.create_task(environment.stop(delete=True))
        await asyncio.sleep(0)
        assert not stop.done()

        release_build.set()
        await start
        await stop

    _run(exercise())

    assert operations.scrub_calls == 1
    assert operations.stop_instance_calls == 1
    assert operations.delete_snapshot_calls == 1
    assert environment._state is None
    assert environment._phase.value == "closed"


def test_delete_stop_persists_cleanup_receipt_bound_to_completed_verifier_rotation(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations(stopped_artifacts={"/workspace/output.md": b"answer\n"})
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    _run(environment.start(force_build=False))
    _run(environment.upload_dir(_tests_dir(tmp_path), "/tests"))
    rotation_bytes = environment.rotation_receipt_path.read_bytes()
    rotation = json.loads(rotation_bytes)

    _run(environment.stop(delete=True))

    cleanup = json.loads(environment.cleanup_receipt_path.read_text(encoding="utf-8"))
    assert cleanup["status"] == "completed"
    assert cleanup["delete_requested"] is True
    assert cleanup["boundary_phase_at_stop"] == "verifier"
    assert cleanup["runtime_archive_sha256"] == runtime.archive_sha256
    assert cleanup["runtime_archive_content_sha256"] == runtime.content_sha256
    assert cleanup["runtime_snapshot_identity"] == operations.snapshot.id
    assert cleanup["trial_instance_identity"] == operations.instance.id
    assert cleanup["rotation_receipt_sha256"] == hashlib.sha256(rotation_bytes).hexdigest()
    assert cleanup["rotation_receipt_content_sha256"] == rotation["content_sha256"]
    assert cleanup["rotation_receipt_verified"] is True
    assert cleanup["expected_verifier_container_identity"] == "container-verifier"
    assert cleanup["observed_verifier_container_identity"] == "container-verifier"
    assert cleanup["verifier_container_identity_verified"] is True
    assert cleanup["verifier_container_stopped"] is True
    assert cleanup["verifier_container_scrubbed"] is True
    assert cleanup["trial_instance_scrubbed"] is True
    assert cleanup["trial_instance_stopped"] is True
    assert cleanup["runtime_snapshot_deleted"] is True
    assert cleanup["failure_steps"] == []
    assert "stop_container:container-verifier" in operations.events
    content_sha256 = cleanup.pop("content_sha256")
    assert content_sha256 == canonical_content_sha256(cleanup)
    assert list(environment.boundary_dir.glob(".proposal-cleanup.json.*.tmp")) == []
    loaded = load_completed_proposal_morph_cleanup_receipt(
        environment.cleanup_receipt_path,
        expected_runtime_archive_sha256=runtime.archive_sha256,
        expected_runtime_archive_content_sha256=runtime.content_sha256,
    )
    assert loaded.receipt_path == environment.cleanup_receipt_path
    assert loaded.receipt_sha256 == hashlib.sha256(environment.cleanup_receipt_path.read_bytes()).hexdigest()
    assert loaded.content_sha256 == content_sha256
    assert loaded.verifier_container_identity == "container-verifier"
    environment.rotation_receipt_path.write_bytes(rotation_bytes + b" ")
    with pytest.raises(ProposalMorphBoundaryError, match="rotation receipt identity"):
        load_completed_proposal_morph_cleanup_receipt(
            environment.cleanup_receipt_path,
            expected_runtime_archive_sha256=runtime.archive_sha256,
            expected_runtime_archive_content_sha256=runtime.content_sha256,
        )


def test_stop_without_delete_never_claims_cleanup_or_snapshot_deletion(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations(stopped_artifacts={"/workspace/output.md": b"answer\n"})
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    _run(environment.start(force_build=False))
    _run(environment.upload_dir(_tests_dir(tmp_path), "/tests"))

    _run(environment.stop(delete=False))

    cleanup = json.loads(environment.cleanup_receipt_path.read_text(encoding="utf-8"))
    assert cleanup["status"] == "retained"
    assert cleanup["delete_requested"] is False
    assert cleanup["rotation_receipt_verified"] is True
    assert cleanup["verifier_container_stopped"] is False
    assert cleanup["verifier_container_scrubbed"] is False
    assert cleanup["trial_instance_scrubbed"] is False
    assert cleanup["trial_instance_stopped"] is True
    assert cleanup["runtime_snapshot_deleted"] is False
    assert operations.scrub_calls == 0
    assert operations.delete_snapshot_calls == 0
    with pytest.raises(ProposalMorphBoundaryError, match="is not completed"):
        load_completed_proposal_morph_cleanup_receipt(
            environment.cleanup_receipt_path,
            expected_runtime_archive_sha256=runtime.archive_sha256,
            expected_runtime_archive_content_sha256=runtime.content_sha256,
        )


def test_partial_cleanup_failure_is_persisted_and_never_reported_completed(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations(
        stopped_artifacts={"/workspace/output.md": b"answer\n"},
        teardown_failing_step="delete_snapshot",
    )
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    _run(environment.start(force_build=False))
    _run(environment.upload_dir(_tests_dir(tmp_path), "/tests"))

    with pytest.raises(ExceptionGroup, match="proposal Morph Harbor teardown failed"):
        _run(environment.stop(delete=True))

    cleanup = json.loads(environment.cleanup_receipt_path.read_text(encoding="utf-8"))
    assert cleanup["status"] == "failed"
    assert cleanup["verifier_container_stopped"] is True
    assert cleanup["trial_instance_scrubbed"] is True
    assert cleanup["trial_instance_stopped"] is True
    assert cleanup["runtime_snapshot_deleted"] is False
    assert cleanup["failure_steps"] == ["delete_snapshot"]
    assert operations.scrub_calls == 1
    assert operations.stop_instance_calls == 1
    assert operations.delete_snapshot_calls == 1


def test_cancelled_stop_finishes_cleanup_and_persists_receipt_before_propagating(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    teardown_step_blocked = threading.Event()
    release_teardown_step = threading.Event()
    operations = RecordingProposalMorphOperations(
        stopped_artifacts={"/workspace/output.md": b"answer\n"},
        teardown_blocked_step="scrub_instance",
        teardown_step_blocked=teardown_step_blocked,
        release_teardown_step=release_teardown_step,
    )
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )

    async def exercise() -> None:
        await environment.start(force_build=False)
        await environment.upload_dir(_tests_dir(tmp_path), "/tests")
        stop = asyncio.create_task(environment.stop(delete=True))
        assert await asyncio.to_thread(teardown_step_blocked.wait, 1.0)
        in_flight = json.loads(environment.cleanup_receipt_path.read_text(encoding="utf-8"))
        assert in_flight["status"] == "started"
        assert in_flight["verifier_container_stopped"] is True
        assert in_flight["trial_instance_scrubbed"] is False
        stop.cancel()
        await asyncio.sleep(0)
        assert not stop.done()
        release_teardown_step.set()
        with pytest.raises(asyncio.CancelledError):
            await stop

    _run(exercise())

    cleanup = json.loads(environment.cleanup_receipt_path.read_text(encoding="utf-8"))
    assert cleanup["status"] == "completed"
    assert cleanup["verifier_container_stopped"] is True
    assert cleanup["trial_instance_scrubbed"] is True
    assert cleanup["trial_instance_stopped"] is True
    assert cleanup["runtime_snapshot_deleted"] is True


def test_cleanup_receipt_fails_closed_without_a_completed_verifier_rotation(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphOperations(stopped_artifacts={"/workspace/output.md": b"answer\n"})
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    _run(environment.start(force_build=False))
    _run(environment.upload_dir(_tests_dir(tmp_path), "/tests"))
    rotation = json.loads(environment.rotation_receipt_path.read_text(encoding="utf-8"))
    rotation.pop("content_sha256")
    rotation["status"] = "started"
    rotation["content_sha256"] = canonical_content_sha256(rotation)
    environment.rotation_receipt_path.write_text(
        json.dumps(rotation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ExceptionGroup, match="proposal Morph Harbor teardown failed"):
        _run(environment.stop(delete=True))

    cleanup = json.loads(environment.cleanup_receipt_path.read_text(encoding="utf-8"))
    assert cleanup["status"] == "failed"
    assert cleanup["rotation_receipt_verified"] is False
    assert cleanup["verifier_container_stopped"] is False
    assert cleanup["verifier_container_scrubbed"] is False
    assert cleanup["trial_instance_scrubbed"] is True
    assert cleanup["trial_instance_stopped"] is True
    assert cleanup["runtime_snapshot_deleted"] is True
    assert cleanup["failure_steps"] == ["validate_verifier_rotation"]


def test_cancelled_verifier_rotation_finishes_and_records_completed_receipt(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    upload_started = threading.Event()
    release_upload = threading.Event()
    operations = RecordingProposalMorphOperations(
        stopped_artifacts={"/workspace/output.md": b"answer\n"},
        blocked_upload_path="/tests",
        upload_started=upload_started,
        release_upload=release_upload,
    )
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )

    async def exercise() -> None:
        await environment.start(force_build=False)
        rotation = asyncio.create_task(environment.upload_dir(_tests_dir(tmp_path), "/tests"))
        assert await asyncio.to_thread(upload_started.wait, 1.0)
        rotation.cancel()
        await asyncio.sleep(0)
        assert not rotation.done()
        release_upload.set()
        with pytest.raises(asyncio.CancelledError):
            await rotation
        assert (await environment.exec("true")).return_code == 0

    _run(exercise())

    receipt = json.loads(environment.rotation_receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "completed"
    assert receipt["tests_uploaded"] is True
    assert receipt["verifier_container_identity"] == "container-verifier"


def test_background_watcher_cannot_observe_verifier_canary_after_rotation(
    tmp_path: Path,
) -> None:
    runtime = _runtime_archive(tmp_path)
    operations = LocalProcessProposalMorphOperations(root=tmp_path / "remote")
    environment = _environment(
        tmp_path=tmp_path,
        operations=operations,
        runtime=runtime,
    )
    _run(environment.start(force_build=False))
    output = tmp_path / "output.md"
    output.write_text("answer\n", encoding="utf-8")
    _run(environment.upload_file(output, "/workspace/output.md"))

    watcher = (
        "nohup sh -c 'while [ ! -f /tests/canary.json ]; do sleep 0.005; done; "
        "cp /tests/canary.json /workspace/stolen-canary.json; "
        "printf hacked > /tests/test.sh' >/dev/null 2>&1 &"
    )
    assert _run(environment.exec(watcher)).return_code == 0

    tests_dir = _tests_dir(tmp_path)
    _run(environment.upload_dir(tests_dir, "/tests"))
    result = _run(
        environment.exec(
            "sleep 0.5; "
            "test ! -e /workspace/stolen-canary.json; "
            "grep -q verifier-canary /tests/canary.json; "
            "grep -q '#!/bin/sh' /tests/test.sh"
        )
    )

    assert result.return_code == 0, result.stderr
    assert operations.container_generations == 2
    assert not (operations.root / "workspace" / "stolen-canary.json").exists()
    assert not (environment.seal_dir / "workspace" / "stolen-canary.json").exists()
    _run(environment.stop(delete=True))


def _environment(
    *,
    tmp_path: Path,
    operations: Any,
    runtime: ProposalRuntimeArchive,
    suffix: str = "default",
    runtime_packages: tuple[str, ...] = RUNTIME_PYTHON_PACKAGES,
) -> ProposalMorphHarborEnvironment:
    environment_dir = tmp_path / f"task-{suffix}" / "environment"
    environment_dir.mkdir(parents=True, exist_ok=True)
    (environment_dir / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    trial_paths = TrialPaths(tmp_path / f"trial-{suffix}")
    trial_paths.mkdir()
    return ProposalMorphHarborEnvironment(
        environment_dir=environment_dir,
        environment_name="proposal-session",
        session_id=f"trial-{suffix}",
        trial_paths=trial_paths,
        task_env_config=_environment_config(),
        operations=operations,
        runtime_archive_path=runtime.path,
        runtime_archive_sha256=runtime.archive_sha256,
        runtime_archive_content_sha256=runtime.content_sha256,
        runtime_packages=runtime_packages,
    )


def _runtime_archive(tmp_path: Path) -> ProposalRuntimeArchive:
    path = tmp_path / "proposal-runtime.tar.gz"
    content = b"proposal-runtime\n"
    path.write_bytes(content)
    return ProposalRuntimeArchive(
        path=path,
        members=("aec_bench/__init__.py",),
        content_sha256=hashlib.sha256(b"logical-runtime").hexdigest(),
        archive_sha256=hashlib.sha256(content).hexdigest(),
    )


def _proposal_session_receipt(
    *,
    runtime: ProposalRuntimeArchive,
    environment_session_id: str,
    candidate_failure: bool,
    runtime_archive_sha256: str | None = None,
) -> ProposalSessionReceipt:
    compilation = _proposal_contract_success()
    plan = ProposalSessionPlan(
        session_plan_id="session-plan.provider-boundary",
        compilation=compilation,
        planned_node_ids=compilation.proposal_graph.node_ids,
        topological_order=compilation.proposal_graph.topological_order,
    )
    execution = ProposalSessionExecutionRef(
        session_id=f"proposal-session.{environment_session_id}",
        environment_session_id=environment_session_id,
        backend="morph",
        source_task_package_sha256=(compilation.source_scope_manifest.task_package_sha256),
        runtime_task_package_sha256=hashlib.sha256(b"provider-boundary-runtime-task").hexdigest(),
        runtime_archive_content_sha256=runtime.content_sha256,
        runtime_archive_sha256=runtime_archive_sha256 or runtime.archive_sha256,
        evaluation_coordinate=MatchedEvaluationCoordinate(
            coordinate_id=f"evaluation.provider-boundary.{environment_session_id}",
            task_id=compilation.proposal_freeze.problem_view.task_id,
            task_revision=compilation.proposal_freeze.problem_view.task_revision,
            split=compilation.proposal_freeze.split,
            review_lineage_id=(compilation.proposal_freeze.selected_review_lineage_id),
            seed=3201,
            repetition=1,
        ),
        execution_schedule_sha256=hashlib.sha256(b"execution-schedule").hexdigest(),
        execution_assignment_sha256=hashlib.sha256(b"execution-assignment").hexdigest(),
    )
    rebound: list[ProposalNodeReceipt] = []
    rebound_sha256_by_original: dict[str, str] = {}
    for original in _proposal_contract_node_receipts(plan):
        payload = original.model_dump(mode="json", exclude={"content_sha256"})
        payload["session_id"] = execution.session_id
        payload["session_execution_sha256"] = execution.content_sha256
        payload["upstream_receipt_sha256s"] = tuple(
            sorted(rebound_sha256_by_original[digest] for digest in original.upstream_receipt_sha256s)
        )
        transition = dict(payload["container_transition"])
        transition.pop("content_sha256")
        transition["runtime_archive_sha256"] = execution.runtime_archive_sha256
        payload["container_transition"] = transition
        if candidate_failure and original.node_id == compilation.proposal_graph.finalizer.node_id:
            contract_check = dict(payload["contract_check_result"])
            contract_check.pop("content_sha256")
            contract_check["status"] = ProposalContractCheckStatus.FAILED
            contract_check["failure_code"] = ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED
            payload["status"] = ProposalNodeReceiptStatus.CANDIDATE_FAILURE
            payload["contract_check_result"] = contract_check
            payload["output_artifact_sha256"] = None
            payload["emitted_handoffs"] = ()
            payload["failure_code"] = ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED
        receipt = ProposalNodeReceipt.model_validate(payload)
        rebound.append(receipt)
        rebound_sha256_by_original[original.content_sha256] = receipt.content_sha256

    finalizer = rebound[-1]
    if candidate_failure:
        return ProposalSessionReceipt(
            session_id=execution.session_id,
            execution=execution,
            plan=plan,
            planned_node_ids=plan.planned_node_ids,
            node_receipts=tuple(rebound),
            status=ProposalSessionStatus.CANDIDATE_FAILURE,
            final_output_artifact_sha256=None,
            output_commit_attestation_sha256=None,
            trial_record_permitted=False,
            failure_code=ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
        )
    return ProposalSessionReceipt(
        session_id=execution.session_id,
        execution=execution,
        plan=plan,
        planned_node_ids=plan.planned_node_ids,
        node_receipts=tuple(rebound),
        status=ProposalSessionStatus.COMPLETED,
        final_output_artifact_sha256=finalizer.output_artifact_sha256,
        output_commit_attestation_sha256=hashlib.sha256(b"provider-boundary-output-commit").hexdigest(),
        trial_record_permitted=True,
        failure_code=None,
    )


def _proposal_session_receipt_bytes(receipt: ProposalSessionReceipt) -> bytes:
    return (
        json.dumps(
            receipt.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _tests_dir(tmp_path: Path) -> Path:
    tests_dir = tmp_path / "hidden-tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (tests_dir / "canary.json").write_text('{"canary":"verifier-canary"}\n', encoding="utf-8")
    return tests_dir


def _environment_config() -> EnvironmentConfig:
    return EnvironmentConfig.model_construct(
        build_timeout_sec=600.0,
        docker_image=None,
        cpus=1,
        memory_mb=2048,
        storage_mb=10240,
        gpus=0,
        gpu_types=None,
        allow_internet=True,
        mcp_servers=[],
        memory=None,
        storage=None,
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


@dataclass(frozen=True)
class _MorphObject:
    id: str


@dataclass
class RecordingProposalMorphOperations:
    stopped_artifacts: dict[str, bytes] = field(default_factory=dict)
    failing_step: str | None = None
    snapshot: _MorphObject = field(default_factory=lambda: _MorphObject("snapshot-proposal"))
    instance: _MorphObject = field(default_factory=lambda: _MorphObject("instance-proposal"))
    builds: list[dict[str, Any]] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    writes: list[tuple[str, bytes]] = field(default_factory=list)
    current_container_identity: str | None = None
    blocked_write_path: str | None = None
    write_started: threading.Event | None = None
    release_write: threading.Event | None = None
    blocked_upload_path: str | None = None
    upload_started: threading.Event | None = None
    release_upload: threading.Event | None = None
    build_started: threading.Event | None = None
    release_build: threading.Event | None = None
    teardown_failing_step: str | None = None
    teardown_blocked_step: str | None = None
    teardown_step_blocked: threading.Event | None = None
    release_teardown_step: threading.Event | None = None
    scrub_calls: int = 0
    stop_instance_calls: int = 0
    delete_snapshot_calls: int = 0

    def build_proposal_runtime_snapshot(self, **kwargs: Any) -> object:
        if self.build_started is not None:
            assert self.release_build is not None
            self.build_started.set()
            assert self.release_build.wait(timeout=2.0)
        self.events.append("build")
        self.builds.append(kwargs)
        return self.snapshot

    def start_instance(self, *, snapshot: object) -> object:
        assert snapshot == self.snapshot
        self.events.append("start_instance")
        return self.instance

    def start_proposal_container(self, *, role: str, **kwargs: Any) -> str:
        del kwargs
        if role == "verifier" and self.failing_step == "start_verifier":
            raise RuntimeError("simulated verifier container start failure")
        self.current_container_identity = f"container-{role}"
        self.events.append(f"start_container:{role}")
        return self.current_container_identity

    def run_container_command_result(
        self,
        *,
        instance: object,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> MorphCommandResult:
        del instance, command, workdir, env, timeout_seconds
        role = (self.current_container_identity or "container-unknown").removeprefix("container-")
        self.events.append(f"exec:{role}")
        return MorphCommandResult(exit_code=0, stdout="", stderr="")

    def write_instance_file(self, *, instance: object, remote_path: str, content: bytes) -> None:
        assert instance == self.instance
        if remote_path == self.blocked_write_path:
            assert self.write_started is not None
            assert self.release_write is not None
            self.write_started.set()
            assert self.release_write.wait(timeout=2.0)
        self.events.append(f"write:{remote_path}")
        self.writes.append((remote_path, content))

    def upload_directory(self, *, instance: object, local_path: Path, remote_path: str) -> None:
        assert instance == self.instance
        assert local_path.is_dir()
        if remote_path == self.blocked_upload_path:
            assert self.upload_started is not None
            assert self.release_upload is not None
            self.upload_started.set()
            assert self.release_upload.wait(timeout=2.0)
        self.events.append(f"upload:{remote_path}")

    def stop_trial_container(
        self,
        *,
        instance: object,
        expected_container_identity: str,
    ) -> None:
        assert instance == self.instance
        if self.current_container_identity != expected_container_identity:
            raise RuntimeError("proposal trial container identity changed before removal")
        if self.failing_step == "stop_container":
            raise RuntimeError("simulated candidate container stop failure")
        if (
            expected_container_identity == "container-verifier"
            and self.teardown_failing_step == "stop_verifier_container"
        ):
            raise RuntimeError("simulated verifier container stop failure")
        self.events.append(f"stop_container:{self.current_container_identity}")

    def trial_container_identity(self, *, instance: object) -> str:
        assert instance == self.instance
        assert self.current_container_identity is not None
        return self.current_container_identity

    def read_stopped_trial_artifacts(self, *, instance: object) -> dict[str, bytes]:
        assert instance == self.instance
        if self.failing_step == "read_stopped_artifacts":
            raise RuntimeError("simulated stopped artifact read failure")
        self.events.append("read_stopped_artifacts")
        return dict(self.stopped_artifacts)

    def reset_trial_mounts(self, *, instance: object) -> None:
        assert instance == self.instance
        if self.failing_step == "reset_mounts":
            raise RuntimeError("simulated mount reset failure")
        self.events.append("reset_mounts")

    def read_container_file(self, *, instance: object, remote_path: str) -> bytes | None:
        del instance, remote_path
        return None

    def read_container_directory_archive(self, *, instance: object, remote_path: str) -> bytes | None:
        del instance, remote_path
        return None

    def scrub_trial_instance(self, *, instance: object) -> None:
        del instance
        self.scrub_calls += 1
        self._block_teardown("scrub_instance")
        if self.teardown_failing_step == "scrub_instance":
            raise RuntimeError("simulated trial instance scrub failure")

    def stop_instance(self, *, instance: object) -> None:
        del instance
        self.stop_instance_calls += 1
        self._block_teardown("stop_instance")
        if self.teardown_failing_step == "stop_instance":
            raise RuntimeError("simulated trial instance stop failure")

    def delete_snapshot(self, *, snapshot: object) -> None:
        del snapshot
        self.delete_snapshot_calls += 1
        self._block_teardown("delete_snapshot")
        if self.teardown_failing_step == "delete_snapshot":
            raise RuntimeError("simulated runtime snapshot deletion failure")

    def _block_teardown(self, step: str) -> None:
        if self.teardown_blocked_step != step:
            return
        assert self.teardown_step_blocked is not None
        assert self.release_teardown_step is not None
        self.teardown_step_blocked.set()
        assert self.release_teardown_step.wait(timeout=2.0)


@dataclass
class LocalProcessProposalMorphOperations(RecordingProposalMorphOperations):
    root: Path = Path(".")
    process_groups: list[int] = field(default_factory=list)
    container_generations: int = 0

    def start_proposal_container(self, *, role: str, **kwargs: Any) -> str:
        del kwargs
        self.container_generations += 1
        for name in ("workspace", "logs/agent", "logs/verifier", "logs/artifacts", "tests"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.current_container_identity = f"container-{role}-{self.container_generations}"
        self.events.append(f"start_container:{role}")
        return self.current_container_identity

    def run_container_command_result(
        self,
        *,
        instance: object,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> MorphCommandResult:
        del instance
        raw = command[-1]
        rewritten = self._rewrite(raw)
        cwd = self._path(workdir or "/workspace")
        process = subprocess.Popen(
            ["bash", "-lc", rewritten],
            cwd=cwd,
            env={**os.environ, **(env or {})},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        self.process_groups.append(process.pid)
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        role = (self.current_container_identity or "container-unknown").removeprefix("container-")
        self.events.append(f"exec:{role}")
        return MorphCommandResult(
            exit_code=process.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def write_instance_file(self, *, instance: object, remote_path: str, content: bytes) -> None:
        del instance
        target = self._path(remote_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        self.events.append(f"write:{remote_path}")
        self.writes.append((remote_path, content))

    def upload_directory(self, *, instance: object, local_path: Path, remote_path: str) -> None:
        del instance
        target = self._path(remote_path)
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(local_path, target, dirs_exist_ok=True)
        self.events.append(f"upload:{remote_path}")

    def stop_trial_container(
        self,
        *,
        instance: object,
        expected_container_identity: str,
    ) -> None:
        del instance
        assert self.current_container_identity == expected_container_identity
        for process_group in self.process_groups:
            try:
                os.killpg(process_group, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.process_groups.clear()
        self.events.append(f"stop_container:{self.current_container_identity}")

    def read_stopped_trial_artifacts(self, *, instance: object) -> dict[str, bytes]:
        del instance
        artifacts: dict[str, bytes] = {}
        for path in sorted((self.root / "workspace").rglob("*")):
            if path.is_file():
                artifacts["/workspace/" + path.relative_to(self.root / "workspace").as_posix()] = path.read_bytes()
        self.events.append("read_stopped_artifacts")
        return artifacts

    def reset_trial_mounts(self, *, instance: object) -> None:
        del instance
        for name in ("workspace", "logs", "tests"):
            shutil.rmtree(self.root / name, ignore_errors=True)
        self.events.append("reset_mounts")

    def scrub_trial_instance(self, *, instance: object) -> None:
        assert self.current_container_identity is not None
        self.stop_trial_container(
            instance=instance,
            expected_container_identity=self.current_container_identity,
        )
        shutil.rmtree(self.root, ignore_errors=True)

    def _rewrite(self, command: str) -> str:
        rewritten = command
        for remote in ("/workspace", "/tests", "/logs"):
            rewritten = rewritten.replace(remote, str(self._path(remote)))
        return rewritten

    def _path(self, remote: str) -> Path:
        return self.root.joinpath(*Path(remote).parts[1:])
