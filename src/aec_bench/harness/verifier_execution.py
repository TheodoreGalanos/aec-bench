# ABOUTME: Executes local task verifiers and records strict process receipts.
# ABOUTME: Keeps redaction, bounded output capture, and staged-path adaptation at one boundary.

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Any

from aec_bench.contracts.identity import EntityKind, PortableRelativePath, new_entity_id, resolve_below
from aec_bench.contracts.trial_extensions import (
    ArtifactReference,
    VerifierExecutionReceipt,
    VerifierOutputParseStatus,
)

MAX_CAPTURE_BYTES = 64 * 1024
RUNTIME_TRANSFORM_VERSION = 1
VERIFIER_PROTOCOL_VERSION = 1
_CONTAINER_ROOT_PATTERN = re.compile(r'(?<![\w.-])/(?:workspace|tests|logs)(?=/|(?=["\'\s]))')
_SECRET_ARGUMENT_NAMES = frozenset({"--api-key", "--password", "--secret", "--token"})


@dataclass(frozen=True)
class VerifierExecution:
    """Receipt and parsed compatibility payloads from one verifier invocation."""

    receipt: VerifierExecutionReceipt
    reward_payload: dict[str, Any] | None
    details_payload: dict[str, Any] | None


def execute_verifier(
    *,
    verifier_path: Path,
    workspace: Path,
    output_path: Path,
    reward_path: Path,
    details_path: Path | None,
    verifier_key: str,
    verifier_version: int,
    runtime_transform_version: int,
    cancelled: bool = False,
    timeout_seconds: int = 120,
) -> VerifierExecution:
    """Run one verifier and persist a strict receipt inside the workspace."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    started_at = datetime.now(UTC)
    started = time.monotonic()
    workspace = workspace.resolve()
    verifier_path = resolve_below(workspace, _workspace_relative_path(verifier_path, workspace))
    output_path = resolve_below(workspace, _workspace_relative_path(output_path, workspace))
    reward_path = resolve_below(workspace, _workspace_relative_path(reward_path, workspace))
    if details_path is not None:
        details_path = resolve_below(workspace, _workspace_relative_path(details_path, workspace))
    receipt_path = resolve_below(workspace, PortableRelativePath("logs/verifier/receipt.json"))
    reward_path.parent.mkdir(parents=True, exist_ok=True)
    command = _command_for(verifier_path=verifier_path, output_path=output_path, reward_path=reward_path)
    command_name = Path(command[0]).name
    arguments = redact_verifier_arguments(command[1:], workspace=workspace)

    if cancelled:
        execution = _build_execution(
            verifier_key=verifier_key,
            verifier_version=verifier_version,
            runtime_transform_version=runtime_transform_version,
            started_at=started_at,
            duration_seconds=time.monotonic() - started,
            command_name=command_name,
            arguments=arguments,
            exit_code=None,
            timed_out=False,
            cancelled=True,
            stdout=b"",
            stderr=b"",
            workspace=workspace,
            reward_path=reward_path,
            failure_kind="cancelled",
            failure_message="verifier execution was cancelled before start",
        )
        _persist_receipt(receipt_path, execution.receipt)
        return VerifierExecution(receipt=execution.receipt, reward_payload=None, details_payload=None)

    env = {**os.environ, "PYTHONPATH": str(workspace)}
    stdout = b""
    stderr = b""
    timed_out = False
    exit_code: int | None = None
    failure_kind: str | None = None
    failure_message: str | None = None
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=env,
            timeout=timeout_seconds,
            capture_output=True,
            check=False,
        )
        stdout = _bytes(completed.stdout)
        stderr = _bytes(completed.stderr)
        exit_code = completed.returncode
        if exit_code != 0:
            failure_kind = "non_zero_exit"
            failure_message = f"verifier exited with code {exit_code}"
        elif not reward_path.exists() and verifier_path.suffix == ".py":
            fallback = [sys.executable, str(verifier_path), str(workspace)]
            command = fallback
            command_name = Path(command[0]).name
            arguments = redact_verifier_arguments(command[1:], workspace=workspace)
            fallback_result = subprocess.run(
                fallback,
                cwd=workspace,
                env=env,
                timeout=timeout_seconds,
                capture_output=True,
                check=False,
            )
            command_name = Path(command[0]).name
            arguments = redact_verifier_arguments(command[1:], workspace=workspace)
            stdout += _bytes(fallback_result.stdout)
            stderr += _bytes(fallback_result.stderr)
            exit_code = fallback_result.returncode
            if exit_code != 0:
                failure_kind = "non_zero_exit"
                failure_message = f"verifier exited with code {exit_code}"
    except subprocess.TimeoutExpired as error:
        stdout = _bytes(error.stdout)
        stderr = _bytes(error.stderr)
        exit_code = None
        timed_out = True
        failure_kind = "timeout"
        failure_message = f"verifier exceeded {timeout_seconds} seconds"
    except FileNotFoundError:
        exit_code = None
        failure_kind = "verifier_not_found"
        failure_message = "verifier process could not start"
    except OSError:
        exit_code = None
        failure_kind = "execution_error"
        failure_message = "verifier process could not start"

    duration_seconds = time.monotonic() - started
    reward_payload, parse_status = _read_reward(reward_path)
    details_payload = _read_details(details_path)
    if not timed_out and exit_code == 0:
        if parse_status is VerifierOutputParseStatus.MISSING:
            failure_kind = "missing_reward"
            failure_message = "verifier did not produce its reward artifact"
        elif parse_status is VerifierOutputParseStatus.MALFORMED:
            failure_kind = "malformed_reward"
            failure_message = "verifier reward artifact did not validate"
    execution = _build_execution(
        verifier_key=verifier_key,
        verifier_version=verifier_version,
        started_at=started_at,
        duration_seconds=duration_seconds,
        command_name=command_name,
        arguments=arguments,
        exit_code=exit_code,
        timed_out=timed_out,
        cancelled=False,
        stdout=stdout,
        stderr=stderr,
        workspace=workspace,
        reward_path=reward_path,
        details_path=details_path,
        runtime_transform_version=runtime_transform_version,
        output_parse_status=parse_status,
        failure_kind=failure_kind,
        failure_message=failure_message,
    )
    _persist_receipt(receipt_path, execution.receipt)
    return VerifierExecution(
        receipt=execution.receipt,
        reward_payload=reward_payload,
        details_payload=details_payload,
    )


def localise_staged_verifier_paths(*, workspace: Path, verifier_root: Path) -> int:
    """Rewrite container roots only inside the staged verifier directory."""

    workspace = workspace.resolve()
    root = verifier_root.resolve()
    if not root.is_relative_to(workspace):
        raise ValueError("staged verifier directory must be inside the workspace")
    replacements = {
        "/workspace": str(workspace),
        "/tests": str(workspace / "tests"),
        "/logs": str(workspace / "logs"),
    }
    for path in sorted((*verifier_root.rglob("*.py"), *verifier_root.rglob("*.sh"))):
        if path.is_symlink():
            raise ValueError("staged verifier files must not be symlinks")
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("staged verifier transformation escaped its verifier directory")
        content = path.read_text(encoding="utf-8")
        localised = _CONTAINER_ROOT_PATTERN.sub(lambda match: replacements[match.group(0)], content)
        if localised != content:
            path.write_text(localised, encoding="utf-8")
    return RUNTIME_TRANSFORM_VERSION


def redact_verifier_arguments(arguments: Sequence[str], *, workspace: Path) -> tuple[str, ...]:
    """Apply the explicit persistence redaction policy to verifier arguments."""

    workspace_text = str(workspace.resolve())
    redacted: list[str] = []
    redact_next = False
    for argument in arguments:
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
        elif argument in _SECRET_ARGUMENT_NAMES:
            redacted.append(argument)
            redact_next = True
        elif any(argument.startswith(f"{name}=") for name in _SECRET_ARGUMENT_NAMES):
            name = argument.split("=", 1)[0]
            redacted.append(f"{name}=<redacted>")
        elif argument == workspace_text or argument.startswith(f"{workspace_text}{os.sep}"):
            redacted.append("<workspace-path>")
        elif Path(argument).is_absolute():
            redacted.append("<absolute-path>")
        else:
            redacted.append(argument)
    return tuple(redacted)


def _command_for(*, verifier_path: Path, output_path: Path, reward_path: Path) -> list[str]:
    if verifier_path.suffix == ".py":
        return [sys.executable, str(verifier_path), "--input", str(output_path), "--output", str(reward_path)]
    return ["bash", str(verifier_path)]


@dataclass(frozen=True)
class _BuiltExecution:
    receipt: VerifierExecutionReceipt


def _build_execution(
    *,
    verifier_key: str,
    verifier_version: int,
    runtime_transform_version: int,
    started_at: datetime,
    duration_seconds: float,
    command_name: str,
    arguments: tuple[str, ...],
    exit_code: int | None,
    timed_out: bool,
    cancelled: bool,
    stdout: bytes,
    stderr: bytes,
    workspace: Path,
    reward_path: Path,
    details_path: Path | None = None,
    output_parse_status: VerifierOutputParseStatus = VerifierOutputParseStatus.NOT_CHECKED,
    failure_kind: str | None = None,
    failure_message: str | None = None,
) -> _BuiltExecution:
    finished_at = datetime.now(UTC)
    stdout_path, stdout_truncated = _write_output(workspace, "stdout.log", stdout)
    stderr_path, stderr_truncated = _write_output(workspace, "stderr.log", stderr)
    receipt = VerifierExecutionReceipt(
        receipt_id=new_entity_id(EntityKind.RECEIPT),
        verifier_key=verifier_key,
        verifier_version=verifier_version,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=max(0.0, duration_seconds),
        command_name=command_name,
        arguments=arguments,
        exit_code=exit_code,
        timed_out=timed_out,
        cancelled=cancelled,
        stdout_artifact=_artifact_reference(stdout_path, workspace, "verifier_stdout"),
        stderr_artifact=_artifact_reference(stderr_path, workspace, "verifier_stderr"),
        reward_artifact=_artifact_reference(reward_path, workspace, "verifier_reward"),
        details_artifact=_artifact_reference(details_path, workspace, "verifier_details"),
        output_parse_status=output_parse_status,
        failure_kind=failure_kind,
        failure_message=failure_message,
        runtime_transform_version=runtime_transform_version,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
    )
    return _BuiltExecution(receipt=receipt)


def _write_output(workspace: Path, name: str, content: bytes) -> tuple[Path | None, bool]:
    path = resolve_below(workspace, PortableRelativePath(f"logs/verifier/{name}"))
    if not content:
        path.unlink(missing_ok=True)
        return None, False
    path.parent.mkdir(parents=True, exist_ok=True)
    truncated = len(content) > MAX_CAPTURE_BYTES
    if truncated:
        content = content[:MAX_CAPTURE_BYTES]
    path.write_bytes(content)
    return path, truncated


def _artifact_reference(path: Path | None, workspace: Path, kind: str) -> ArtifactReference | None:
    if path is None or not path.is_file():
        return None
    resolved = path.resolve()
    if not resolved.is_relative_to(workspace):
        raise ValueError("verifier artifact must remain inside the workspace")
    return ArtifactReference(
        kind=kind,
        path=resolved.relative_to(workspace).as_posix(),
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        media_type="text/plain" if resolved.suffix == ".log" else "application/json",
    )


def _read_reward(path: Path) -> tuple[dict[str, Any] | None, VerifierOutputParseStatus]:
    if not path.is_file():
        return None, VerifierOutputParseStatus.MISSING
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, VerifierOutputParseStatus.MALFORMED
    if not isinstance(payload, dict) or isinstance(payload.get("reward"), bool):
        return None, VerifierOutputParseStatus.MALFORMED
    reward = payload.get("reward")
    if not isinstance(reward, int | float) or not isfinite(float(reward)) or not 0.0 <= float(reward) <= 1.0:
        return None, VerifierOutputParseStatus.MALFORMED
    return payload, VerifierOutputParseStatus.VALID


def _read_details(details: Path | None) -> dict[str, Any] | None:
    if details is None or not details.is_file():
        return None
    try:
        payload = json.loads(details.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _bytes(value: bytes | str | None) -> bytes:
    if value is None:
        return b""
    return value if isinstance(value, bytes) else value.encode("utf-8", errors="replace")


def _persist_receipt(path: Path, receipt: VerifierExecutionReceipt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _workspace_relative_path(path: Path, workspace: Path) -> PortableRelativePath:
    raw = str(path)
    workspace_prefix = str(workspace)
    if raw.startswith(f"{workspace_prefix}{os.sep}"):
        raw = raw.removeprefix(f"{workspace_prefix}{os.sep}")
    elif raw.startswith("/workspace/"):
        raw = raw.removeprefix("/workspace/")
    elif raw.startswith("/logs/"):
        raw = raw.removeprefix("/logs/")
    elif Path(raw).is_absolute():
        raise ValueError("verifier path must resolve inside the workspace")
    return PortableRelativePath(raw.replace(os.sep, "/"))
