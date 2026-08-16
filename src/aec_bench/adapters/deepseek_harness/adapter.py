# ABOUTME: Maps one official DeepSeek Harness SDK run into the provider-neutral adapter result.
# ABOUTME: Preserves raw runtime evidence and does not claim verifier-owned task completion.

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from aec_bench.adapters.base import (
    AdapterCompletionReason,
    AdapterFailureKind,
    AdapterRequest,
    AdapterResult,
    AdapterStopReason,
    initialize_transcript,
)
from aec_bench.adapters.deepseek_harness.config import (
    DeepSeekHarnessSettings,
    deepseek_output_commit_configuration,
    deepseek_system_prompt,
    request_max_tokens,
    request_timeout_seconds,
    treatment_record,
    validate_deepseek_request,
)
from aec_bench.adapters.deepseek_harness.runtime import (
    DeepSeekHarnessProcessRuntime,
    DeepSeekHarnessRun,
    DeepSeekHarnessRuntimeError,
    DeepSeekHarnessRuntimeTimeout,
    DeepSeekRuntime,
)
from aec_bench.adapters.deepseek_harness.tool_gateway import NativeToolDefinition
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus


class DeepSeekHarnessAdapter:
    """Run one qualified DeepSeek Harness treatment in an isolated workspace."""

    def __init__(
        self,
        *,
        settings: DeepSeekHarnessSettings,
        workspace: str | Path,
        runtime: DeepSeekRuntime | None = None,
        native_tools: Sequence[NativeToolDefinition] | None = None,
        adapter_name: str = "deepseek_harness",
    ) -> None:
        self._settings = settings
        self._workspace = Path(workspace).resolve()
        self._native_tool_names = frozenset(tool.name for tool in native_tools or ())
        self._runtime = runtime or DeepSeekHarnessProcessRuntime(
            settings=settings,
            workspace=self._workspace,
            native_tools=native_tools,
        )
        self._adapter_name = adapter_name

    def execute(self, request: AdapterRequest) -> AdapterResult:
        resolved_request = replace(request, system_prompt=deepseek_system_prompt(request))
        validate_deepseek_request(resolved_request, native_tool_names=self._native_tool_names)
        try:
            run = self._runtime.run(resolved_request)
        except DeepSeekHarnessRuntimeTimeout as exc:
            return self._failed_result(
                resolved_request,
                failure_kind=AdapterFailureKind.TIMEOUT,
                error=str(exc),
            )
        except DeepSeekHarnessRuntimeError as exc:
            return self._failed_result(
                resolved_request,
                failure_kind=AdapterFailureKind.PROVIDER_ERROR,
                error=str(exc),
            )

        transcript = initialize_transcript(resolved_request)
        transcript.extend(run.projection.transcript)
        direct_output = _has_direct_output(self._workspace, resolved_request.output_path)
        status, failure_kind, stop_reason, error = _outcome(
            run,
            candidate_available=(
                direct_output or bool(run.final_response.strip()) or run.completion_commit is not None
            ),
            native_tool_activity=bool(self._native_tool_names) and run.projection.tool_calls_completed > 0,
        )
        raw_output_text = None if direct_output else run.final_response
        completion_commit = run.completion_commit if status is AgentOutputStatus.COMPLETED else None

        return AdapterResult(
            adapter_name=self._adapter_name,
            resolved_model=self._settings.model,
            configuration_record=_configuration_record(self._settings, run),
            agent_output=AgentOutput(
                status=status,
                output_path=request.output_path,
                output_format=request.output_format,
                error_message=error,
            ),
            transcript=transcript,
            failure_kind=failure_kind,
            stop_reason=stop_reason,
            completion_reason=(
                AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED if completion_commit is not None else None
            ),
            completion_commit=completion_commit,
            turns_used=run.projection.root_model_calls,
            raw_output_text=raw_output_text,
            provider_error=error if failure_kind is AdapterFailureKind.PROVIDER_ERROR else None,
            usage_model_calls=run.projection.root_model_calls,
            usage_input_tokens=run.projection.usage_input_tokens,
            usage_output_tokens=run.projection.usage_output_tokens,
            usage_cache_read_tokens=run.projection.usage_cache_read_tokens,
            maximum_input_tokens_in_one_call=run.projection.maximum_input_tokens_in_one_call,
            maximum_output_tokens_in_one_call=run.projection.maximum_output_tokens_in_one_call,
        )

    def adapter_name(self) -> str:
        return self._adapter_name

    def resolved_model(self) -> str:
        return self._settings.model

    def _failed_result(
        self,
        request: AdapterRequest,
        *,
        failure_kind: AdapterFailureKind,
        error: str,
    ) -> AdapterResult:
        status = AgentOutputStatus.FAILED
        if failure_kind is AdapterFailureKind.TIMEOUT and _has_direct_output(self._workspace, request.output_path):
            status = AgentOutputStatus.PARTIAL
        _contract, commit_required = deepseek_output_commit_configuration(request)
        configuration_record = treatment_record(
            self._settings,
            timeout_seconds=request_timeout_seconds(request),
            max_tokens=request_max_tokens(request),
            output_commit_required=commit_required,
            native_tools=tuple(sorted(self._native_tool_names)),
        )
        if isinstance(self._runtime, DeepSeekHarnessProcessRuntime):
            configuration_record.update(
                {
                    "manifest_path": str(self._runtime.paths.manifest),
                    "notifications_path": str(self._runtime.paths.notifications),
                    "root_events_path": str(self._runtime.paths.root_events),
                    "sessions_path": str(self._runtime.paths.sessions),
                    "stderr_path": str(self._runtime.paths.stderr),
                }
            )
            if self._runtime.paths.manifest.is_file():
                configuration_record["evidence_manifest_sha256"] = _file_sha256(self._runtime.paths.manifest)
        return AdapterResult(
            adapter_name=self._adapter_name,
            resolved_model=self._settings.model,
            configuration_record=configuration_record,
            agent_output=AgentOutput(
                status=status,
                output_path=request.output_path,
                output_format=request.output_format,
                error_message=error,
            ),
            transcript=initialize_transcript(request),
            failure_kind=failure_kind,
            provider_error=error if failure_kind is AdapterFailureKind.PROVIDER_ERROR else None,
        )


def _outcome(
    run: DeepSeekHarnessRun,
    *,
    candidate_available: bool,
    native_tool_activity: bool,
) -> tuple[AgentOutputStatus, AdapterFailureKind | None, AdapterStopReason | None, str | None]:
    finish_reason = run.finish_reason or run.projection.last_turn_end_reason
    if finish_reason == "completed" and run.projection.idle_seen:
        if not candidate_available:
            return (
                AgentOutputStatus.PARTIAL if native_tool_activity else AgentOutputStatus.EMPTY,
                AdapterFailureKind.MISSING_OUTPUT,
                None,
                "DeepSeek Harness completed without a candidate output",
            )
        if run.output_commit_mode == "required" and run.completion_commit is None:
            return (
                AgentOutputStatus.PARTIAL,
                AdapterFailureKind.MISSING_OUTPUT,
                None,
                run.commit_error or "DeepSeek Harness completed without an accepted output commit",
            )
        return AgentOutputStatus.COMPLETED, None, None, None
    if finish_reason == "max-tokens":
        return (
            AgentOutputStatus.PARTIAL,
            AdapterFailureKind.TOKEN_BUDGET_REACHED,
            AdapterStopReason.TOKEN_BUDGET,
            "DeepSeek Harness reached the configured output-token limit",
        )
    if finish_reason is None:
        error = "DeepSeek Harness stopped without a root turn/end reason"
    elif finish_reason == "completed":
        error = "DeepSeek Harness reported completion before the root session became idle"
    else:
        error = f"DeepSeek Harness stopped with reason: {finish_reason}"
    return AgentOutputStatus.FAILED, AdapterFailureKind.PROVIDER_ERROR, None, error


def _configuration_record(settings: DeepSeekHarnessSettings, run: DeepSeekHarnessRun) -> dict[str, object]:
    record: dict[str, object] = {
        **treatment_record(
            settings,
            timeout_seconds=run.timeout_seconds,
            max_tokens=run.max_tokens,
            output_commit_required=run.output_commit_mode == "required",
            native_tools=run.native_tools,
        ),
        "sdk_version": run.sdk_version,
        "runtime_distribution_version": run.runtime_distribution_version,
        "runtime_reported_version": run.runtime_reported_version,
        "root_session_id": run.session_id,
        "root_steps": run.projection.root_steps,
        "root_turns": run.projection.root_turns,
        "tool_calls_started": run.projection.tool_calls_started,
        "tool_calls_completed": run.projection.tool_calls_completed,
        "child_session_ids": list(run.projection.child_session_ids),
        "unknown_event_types": list(run.projection.unknown_event_types),
        "optional_plugins": [plugin.model_dump(mode="json") for plugin in run.optional_plugins],
        "notifications_path": str(run.notifications_path),
        "stderr_path": str(run.stderr_path),
    }
    if run.evidence_manifest_sha256 is not None:
        record["evidence_manifest_sha256"] = run.evidence_manifest_sha256
    if run.tool_gateway_close_report is not None:
        record["tool_gateway_close"] = {
            "quiescent": run.tool_gateway_close_report.quiescent,
            "unsettled_request_ids": list(run.tool_gateway_close_report.unsettled_request_ids),
            "unknown_outcome_request_ids": list(run.tool_gateway_close_report.unknown_outcome_request_ids),
            "closed_at": run.tool_gateway_close_report.closed_at.isoformat(),
        }
    for field_name in (
        "root_events_path",
        "sessions_path",
        "manifest_path",
        "composition_path",
        "system_prompt_path",
        "cordis_path",
        "commit_evidence_path",
        "tool_gateway_evidence_path",
    ):
        path = getattr(run, field_name)
        if path is not None:
            record[field_name] = str(path)
    return record


def _has_direct_output(workspace: Path, requested_path: str) -> bool:
    path = Path(requested_path)
    if path.is_absolute() and path.parts[:2] == ("/", "workspace"):
        path = workspace.joinpath(*path.parts[2:])
    elif not path.is_absolute():
        path = workspace / path
    return path.is_file() and path.stat().st_size > 0


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
