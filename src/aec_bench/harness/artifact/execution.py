# ABOUTME: Owns artifact output normalisation, commit validation, and agent result evidence.
# ABOUTME: Keeps execution-facing output rules outside the filesystem workspace port.

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path

from aec_bench.adapters.base import Adapter, AdapterRequest, AdapterResult
from aec_bench.contracts.canonical_refs import CanonicalRefSet, parse_canonical_refs
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.trial_extensions import ArtifactReference
from aec_bench.evaluation.normalisation import NormalisationResult, normalise_output
from aec_bench.harness.artifact.values import TaskAttempt
from aec_bench.harness.artifact.workspace_port import resolve_workspace_path
from aec_bench.harness.local_runtime import read_instruction
from aec_bench.tasks.instance import ResolvedTaskInstance
from aec_bench.trajectory.writer import TrajectoryWriter
from aec_bench.trials import PlannedTrial


def load_canonical_refs(task_toml_path: Path) -> CanonicalRefSet:
    if not task_toml_path.exists():
        return CanonicalRefSet()
    import tomllib

    data = tomllib.loads(task_toml_path.read_text(encoding="utf-8"))
    return parse_canonical_refs(data.get("canonical_refs", {}))


def apply_normalisation(
    output_path: Path,
    refs: CanonicalRefSet,
    report_path: Path,
    *,
    committed_result: AdapterResult | None = None,
) -> NormalisationResult:
    text = output_path.read_text(encoding="utf-8")
    result = normalise_output(text, refs)
    if result.substitutions_count == 0:
        return result
    if committed_result is not None and committed_result.completion_commit is not None:
        raise ValueError("canonical-reference normalisation cannot change committed output bytes")
    output_path.write_text(result.normalised, encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {
                "substitutions_count": result.substitutions_count,
                "audit_log": [
                    {
                        "matched_text": match.matched_text,
                        "canonical_value": match.canonical_value,
                        "distance": match.distance,
                        "count": match.count,
                    }
                    for match in result.audit_log
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return result


def validate_output_commit(*, result: AdapterResult, output_path: Path, expected_output_path: str) -> None:
    attestation = result.completion_commit
    if attestation is None:
        return
    if attestation.output_path != expected_output_path:
        raise ValueError("output commit path does not match the task expected output path")
    content = output_path.read_bytes()
    if hashlib.sha256(content).hexdigest() != attestation.output_sha256:
        raise ValueError("output commit SHA-256 does not match the attempt output")
    if len(content) != attestation.output_size_bytes:
        raise ValueError("output commit byte size does not match the attempt output")


def write_agent_result(
    *,
    workspace: Path,
    requested_model: str,
    adapter_kind: str,
    result: AdapterResult,
    output_source: str,
) -> None:
    payload = {
        "status": result.agent_output.status.value,
        "model": requested_model,
        "resolved_model": result.resolved_model,
        "adapter": adapter_kind,
        "adapter_configuration": result.configuration_record,
        "model_calls": result.usage_model_calls,
        "input_tokens": result.usage_input_tokens,
        "output_tokens": result.usage_output_tokens,
        "cache_read_tokens": result.usage_cache_read_tokens,
        "cache_write_tokens": result.usage_cache_write_tokens,
        "turns_used": result.turns_used,
        "max_turns": result.max_turns,
        "failure_kind": result.failure_kind.value if result.failure_kind is not None else None,
        "provider_error": result.provider_error,
        "output_source": output_source,
    }
    (workspace / "agent_result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def execute_attempt(
    *,
    task: ResolvedTaskInstance,
    trial: PlannedTrial,
    workspace: Path,
    attempt_id: str,
    parent_attempt_id: str | None,
    instruction: str | None,
    adapter_builder: Callable[..., Adapter] | None,
    constitutional_model: str | None,
    normalise: bool,
) -> TaskAttempt:
    """Execute one adapter call and produce its selector-visible attempt values."""
    request = _build_request(task=task, trial=trial, workspace=workspace, instruction=instruction)
    adapter = _build_adapter(
        trial=trial,
        workspace=workspace,
        adapter_builder=adapter_builder,
        constitutional_model=constitutional_model,
    )
    started = time.monotonic()
    result = adapter.execute(request)
    elapsed_seconds = time.monotonic() - started

    output_path = resolve_workspace_path(workspace, task.task.verifier.expected_output_path)
    output_source = "adapter"
    if output_path.is_file() and output_path.read_text(encoding="utf-8", errors="replace").strip():
        output_source = "direct_write"
    elif result.raw_output_text:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.raw_output_text, encoding="utf-8")
        output_source = "raw_output"
    if normalise and output_path.is_file():
        refs = load_canonical_refs(task.instance_dir / "task.toml")
        if refs.refs:
            apply_normalisation(
                output_path,
                refs,
                workspace / "normalisation_report.json",
                committed_result=result,
            )
    validate_output_commit(
        result=result,
        output_path=output_path,
        expected_output_path=task.task.verifier.expected_output_path,
    )
    write_agent_result(
        workspace=workspace,
        requested_model=trial.agent.model,
        adapter_kind=trial.agent.adapter,
        result=result,
        output_source=output_source,
    )
    selector_visible_output = output_path.read_bytes() if output_path.is_file() else None
    output_reference = (
        ArtifactReference(
            kind="primary_output",
            path=request.output_path,
            sha256=hashlib.sha256(selector_visible_output).hexdigest(),
            media_type="application/octet-stream",
        )
        if selector_visible_output
        else None
    )
    return TaskAttempt(
        attempt_id=attempt_id,
        trial_id=trial.trial_id,
        parent_attempt_id=parent_attempt_id,
        workspace=workspace,
        request=request,
        result=result,
        elapsed_seconds=elapsed_seconds,
        selector_visible_output=selector_visible_output,
        output_reference=output_reference,
    )


def _build_adapter(
    *,
    trial: PlannedTrial,
    workspace: Path,
    adapter_builder: Callable[..., Adapter] | None,
    constitutional_model: str | None,
) -> Adapter:
    builder = adapter_builder
    if builder is None:
        from aec_bench.adapters.local_registry import build_local_adapter

        builder = build_local_adapter
    trajectory_writer = TrajectoryWriter(path=str(workspace / "trajectory.jsonl"))
    return builder(
        adapter_kind=trial.agent.adapter,
        model_name=trial.agent.model,
        workspace=str(workspace),
        trajectory_writer=trajectory_writer,
        constitutional_model=constitutional_model,
    )


def _build_request(
    *,
    task: ResolvedTaskInstance,
    trial: PlannedTrial,
    workspace: Path,
    instruction: str | None,
) -> AdapterRequest:
    selected_instruction = instruction if instruction is not None else read_instruction(str(workspace))
    if not selected_instruction:
        raise ValueError("task workspace does not contain an instruction")
    system_prompt = trial.agent.system_prompt
    if trial.agent.system_prompt_file is not None:
        system_prompt = resolve_workspace_path(workspace, trial.agent.system_prompt_file).read_text(encoding="utf-8")
    tools: list[ToolSpec] = []
    if trial.agent.adapter == "tool_loop":
        tools = [ToolSpec(name="bash", source="builtin", description="Execute a bash command in the workspace")]
    configuration = dict(trial.agent.parameters)
    timeout = trial.compute.timeout_override or task.task.timeout_seconds
    if trial.agent.adapter == "prime-agent":
        configuration["timeout_seconds"] = timeout
    elif trial.agent.adapter == "deepseek_harness":
        configuration["timeout_sec"] = timeout
    output_path = task.task.verifier.expected_output_path
    return AdapterRequest(
        instruction=selected_instruction,
        system_prompt=system_prompt,
        tools=tools,
        configuration=configuration,
        output_path=output_path,
        output_format="markdown" if Path(output_path).suffix.lower() == ".md" else "jsonl",
    )


__all__ = (
    "apply_normalisation",
    "execute_attempt",
    "load_canonical_refs",
    "validate_output_commit",
    "write_agent_result",
)
