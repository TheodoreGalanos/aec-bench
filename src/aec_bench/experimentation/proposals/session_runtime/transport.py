# ABOUTME: Wraps proposal child container reset, upload, execution, and download effects.
# ABOUTME: Translates provider failures into stable proposal-session runtime errors.

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from aec_bench.experimentation.proposals.session_evidence import (
    ProposalCandidateTransitionEvidence,
)

from .contracts import (
    ProposalSessionEnvironment,
    ProposalSessionExecResult,
    ProposalSessionRuntimeError,
)

REMOTE_WORKSPACE = "/workspace"
REMOTE_EXECUTION_BUNDLE = "/workspace/proposal-execution-bundle.json"
REMOTE_EXECUTION_RESULT = "/workspace/agent_result.json"
REMOTE_TRAJECTORY = "/workspace/trajectory.jsonl"
REMOTE_PROVIDER_BROKER_POLICY = "/workspace/provider-broker-policy.json"
REMOTE_PROVIDER_BROKER_RECEIPT = "/workspace/provider-broker-receipt.json"


async def reset_candidate_container(
    *,
    environment: ProposalSessionEnvironment,
    invocation_id: str,
    runtime_archive_sha256: str,
) -> ProposalCandidateTransitionEvidence:
    try:
        return await environment.reset_candidate_container_for_invocation(
            invocation_id=invocation_id,
            expected_runtime_digest=runtime_archive_sha256,
        )
    except Exception as error:
        raise ProposalSessionRuntimeError(
            "container_reset_failed",
            f"proposal candidate container reset failed: {error}",
        ) from error


async def upload_invocation(
    *,
    environment: ProposalSessionEnvironment,
    context_workspace: Path,
    execution_bundle_path: Path,
    provider_broker_policy_path: Path,
) -> None:
    try:
        await environment.upload_dir(
            context_workspace,
            REMOTE_WORKSPACE,
        )
        await environment.upload_file(
            execution_bundle_path,
            REMOTE_EXECUTION_BUNDLE,
        )
        await environment.upload_file(
            provider_broker_policy_path,
            REMOTE_PROVIDER_BROKER_POLICY,
        )
    except Exception as error:
        raise ProposalSessionRuntimeError(
            "child_upload_failed",
            f"proposal child context or execution bundle upload failed: {error}",
        ) from error


async def execute_child(
    *,
    environment: ProposalSessionEnvironment,
    timeout_seconds: int,
    child_environment: Mapping[str, str] | None,
) -> ProposalSessionExecResult:
    try:
        return await environment.exec(
            "python -m aec_bench.harness.provider_broker_bootstrap "
            f"--bundle {REMOTE_EXECUTION_BUNDLE} "
            f"--result {REMOTE_EXECUTION_RESULT} "
            f"--policy {REMOTE_PROVIDER_BROKER_POLICY} "
            "--socket /tmp/aec-broker.sock "
            f"--receipt {REMOTE_PROVIDER_BROKER_RECEIPT}",
            cwd=REMOTE_WORKSPACE,
            env=(dict(child_environment) if child_environment else None),
            timeout_sec=timeout_seconds,
        )
    except Exception as error:
        raise ProposalSessionRuntimeError(
            "child_execution_failed",
            f"proposal child execution failed: {error}",
        ) from error


async def download_required(
    *,
    environment: ProposalSessionEnvironment,
    remote_path: str,
    local_path: Path,
    label: str,
) -> None:
    try:
        await environment.download_file(
            remote_path,
            local_path,
        )
    except FileNotFoundError as error:
        raise ProposalSessionRuntimeError(
            "child_evidence_missing",
            f"proposal {label} is missing",
        ) from error
    except Exception as error:
        raise ProposalSessionRuntimeError(
            "child_download_failed",
            f"proposal {label} could not be downloaded: {error}",
        ) from error


async def download_optional_output(
    *,
    environment: ProposalSessionEnvironment,
    remote_path: str,
    local_path: Path,
) -> bool:
    try:
        await environment.download_file(
            remote_path,
            local_path,
        )
    except FileNotFoundError:
        return False
    except Exception as error:
        raise ProposalSessionRuntimeError(
            "child_download_failed",
            f"proposal child output could not be downloaded: {error}",
        ) from error
    return True
