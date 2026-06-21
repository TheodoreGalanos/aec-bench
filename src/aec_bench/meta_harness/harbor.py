# ABOUTME: Executes external Harbor-compatible commands and inspects task artifacts.
# ABOUTME: Provides a generic subprocess task-run boundary alongside native AEC-Bench Harbor workflows.

from __future__ import annotations

import copy
import json
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

DEFAULT_EXPECTED_ARTIFACTS = [
    "job.yaml",
    "agent/input.json",
    "agent/output.md",
    "agent_result.json",
    "result.json",
]


CommandSpec = Sequence[str] | Callable[[dict[str, Any]], Sequence[str]]
ArtifactDirSpec = Path | Callable[[dict[str, Any]], Path]


def run_harbor_command(
    *,
    command: list[str],
    cwd: Path | None = None,
    artifact_dir: Path,
    expected_artifacts: list[str] | None = None,
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    artifacts = _artifact_refs(artifact_dir, expected_artifacts or DEFAULT_EXPECTED_ARTIFACTS)
    result_payload = _read_result_payload(artifact_dir / "result.json")
    command_ok = completed.returncode == 0
    artifact_status = result_payload.get("status") if isinstance(result_payload, dict) else None
    status = artifact_status if command_ok and artifact_status else _status_from_returncode(completed.returncode)
    return {
        "status": status,
        "returncode": completed.returncode,
        "command": list(command),
        "cwd": str(cwd) if cwd else None,
        "artifact_dir": str(artifact_dir),
        "artifacts": artifacts,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "result": result_payload,
    }


def build_harbor_task_run_resolver(
    *,
    command: CommandSpec,
    artifact_dir: ArtifactDirSpec,
    cwd: Path | None = None,
    expected_artifacts: list[str] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def resolve(runtime_result: dict[str, Any]) -> dict[str, Any]:
        resolved_artifact_dir = _resolve_artifact_dir(artifact_dir, runtime_result)
        resolved_artifact_dir.mkdir(parents=True, exist_ok=True)
        harbor_result = run_harbor_command(
            command=list(_resolve_command(command, runtime_result)),
            cwd=cwd,
            artifact_dir=resolved_artifact_dir,
            expected_artifacts=expected_artifacts,
        )
        return harbor_result_to_task_run(harbor_result, runtime_result)

    return resolve


def harbor_result_to_task_run(
    harbor_result: dict[str, Any],
    runtime_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    process_id = (runtime_result or {}).get("process_id") or "process"
    payload = harbor_result.get("result")
    payload = payload if isinstance(payload, dict) else {}
    evidence = {
        "score": _score_from_harbor_result(harbor_result),
        "artifacts": copy.deepcopy(harbor_result.get("artifacts", {})),
        "harbor": {
            "status": harbor_result.get("status"),
            "returncode": harbor_result.get("returncode"),
            "command": copy.deepcopy(harbor_result.get("command")),
            "cwd": harbor_result.get("cwd"),
            "artifact_dir": harbor_result.get("artifact_dir"),
            "stdout": harbor_result.get("stdout", ""),
            "stderr": harbor_result.get("stderr", ""),
        },
    }
    if payload:
        evidence["result"] = copy.deepcopy(payload)
    return {
        "run_id": payload.get("run_id") or f"{process_id}.harbor",
        "evidence": evidence,
    }


def _artifact_refs(artifact_dir: Path, expected_artifacts: list[str]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for relative_path in expected_artifacts:
        path = artifact_dir / relative_path
        if path.exists():
            refs[relative_path] = str(path)
    return refs


def _read_result_payload(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _status_from_returncode(returncode: int) -> str:
    return "complete" if returncode == 0 else "failed"


def _resolve_command(command: CommandSpec, runtime_result: dict[str, Any]) -> Sequence[str]:
    if callable(command):
        return command(runtime_result)
    return command


def _resolve_artifact_dir(
    artifact_dir: ArtifactDirSpec,
    runtime_result: dict[str, Any],
) -> Path:
    if callable(artifact_dir):
        return artifact_dir(runtime_result)
    return artifact_dir


def _score_from_harbor_result(harbor_result: dict[str, Any]) -> dict[str, Any]:
    payload = harbor_result.get("result")
    if isinstance(payload, dict):
        score = payload.get("score")
        if isinstance(score, dict):
            return copy.deepcopy(score)
        if isinstance(payload.get("passed"), bool):
            return {"passed": payload["passed"]}
        reward = payload.get("reward")
        if isinstance(reward, int | float) and not isinstance(reward, bool):
            return {"reward": max(0.0, min(1.0, float(reward)))}

    status = str(harbor_result.get("status", "")).lower()
    returncode = harbor_result.get("returncode")
    if returncode == 0 and status in {"complete", "completed", "passed", "success", "succeeded"}:
        return {"passed": True}
    if returncode != 0 or status in {"error", "failed", "failure"}:
        return {"passed": False}
    return {}
