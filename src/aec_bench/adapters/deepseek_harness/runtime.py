# ABOUTME: Owns the isolated DeepSeek SDK worker process and its trial evidence files.
# ABOUTME: Enforces a scrubbed environment, whole-process-group timeout, and validated worker results.

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, cast
from urllib.parse import urlsplit, urlunsplit

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.deepseek_harness.commit_endpoint import (
    OUTPUT_COMMIT_SOCKET_ENV,
    OUTPUT_COMMIT_TOKEN_ENV,
    OutputCommitEndpoint,
    resolve_trial_output_path,
)
from aec_bench.adapters.deepseek_harness.config import (
    OUTPUT_COMMIT_PLUGIN_ID,
    OUTPUT_COMMIT_PLUGIN_VERSION,
    TOOL_GATEWAY_PLUGIN_ID,
    TOOL_GATEWAY_PLUGIN_VERSION,
    DeepSeekHarnessSettings,
    baseline_cordis_template,
    deepseek_output_commit_configuration,
    deepseek_system_prompt,
    harness_provider_route,
    output_commit_plugin_path,
    request_max_tokens,
    request_timeout_seconds,
    tool_gateway_cordis_template,
    tool_gateway_plugin_path,
    treatment_record,
    validate_deepseek_request,
)
from aec_bench.adapters.deepseek_harness.events import (
    DeepSeekRunProjection,
    notification_envelope_parts,
    reduce_deepseek_notifications,
)
from aec_bench.adapters.deepseek_harness.evidence import (
    DeepSeekAdapterIdentity,
    DeepSeekCompositionIdentity,
    DeepSeekEvidenceArtifact,
    DeepSeekEvidenceManifest,
    DeepSeekExecutionIdentity,
    DeepSeekModelIdentity,
    DeepSeekPluginIdentity,
    DeepSeekRedactedFile,
    DeepSeekRedactionAudit,
    verify_deepseek_evidence_manifest,
)
from aec_bench.adapters.deepseek_harness.tool_gateway import (
    TOOL_GATEWAY_MANIFEST_ENV,
    TOOL_GATEWAY_SOCKET_ENV,
    TOOL_GATEWAY_TOKEN_ENV,
    NativeTool,
    ToolGatewayEndpoint,
)
from aec_bench.adapters.output_commit import read_output_completion_content, validate_stable_output_commit
from aec_bench.contracts.output_completion import OutputCommitAttestation, OutputCompletionContract
from aec_bench.contracts.validators import NonEmptyStr, StrictModel

_PASSTHROUGH_ENVIRONMENT = (
    "LANG",
    "LC_ALL",
    "PATH",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
)
_PROVIDER_KEY_ENV = "DSH_API_KEY"
_PROVIDER_URL_ENV = "DSH_BASE_URL"
_AZURE_KEY_ENV = "AZURE_OPENAI_API_KEY"
_AZURE_ENDPOINT_ENV = "AZURE_OPENAI_ENDPOINT"
_DEEPSEEK_KEY_ENV = "DEEPSEEK_API_KEY"
_DEEPSEEK_ENDPOINT_ENV = "DEEPSEEK_BASE_URL"
_DEEPSEEK_DEFAULT_ENDPOINT = "https://api.deepseek.com"


class DeepSeekHarnessRuntimeError(RuntimeError):
    """Raised when the worker or SDK cannot produce a valid result."""


class DeepSeekHarnessRuntimeTimeout(DeepSeekHarnessRuntimeError):
    """Raised only after the complete worker process group has stopped."""


class DeepSeekRuntime(Protocol):
    def run(self, request: AdapterRequest) -> DeepSeekHarnessRun: ...


class DeepSeekWorkerResult(StrictModel):
    session_id: NonEmptyStr
    final_response: str
    finish_reason: str | None
    sdk_version: NonEmptyStr
    runtime_distribution_version: NonEmptyStr
    runtime_reported_version: str | None = None


@dataclass(frozen=True)
class DeepSeekHarnessPaths:
    root: Path
    request: Path
    result: Path
    notifications: Path
    root_events: Path
    stderr: Path
    system_prompt: Path
    cordis_input: Path
    runtime_record: Path
    composition: Path
    manifest: Path
    redaction_audit: Path
    commit_evidence: Path
    tool_gateway_evidence: Path
    output_commit_plugin: Path
    tool_gateway_plugin: Path
    home: Path
    temporary: Path
    sessions: Path


@dataclass(frozen=True)
class DeepSeekHarnessRun:
    session_id: str
    final_response: str
    finish_reason: str | None
    sdk_version: str
    runtime_distribution_version: str
    runtime_reported_version: str | None
    timeout_seconds: int
    max_tokens: int | None
    projection: DeepSeekRunProjection
    notifications_path: Path
    stderr_path: Path
    evidence_manifest_sha256: str | None = None
    optional_plugins: tuple[DeepSeekPluginIdentity, ...] = ()
    native_tools: tuple[str, ...] = ()
    output_commit_mode: str = "disabled"
    completion_commit: OutputCommitAttestation | None = None
    commit_error: str | None = None
    root_events_path: Path | None = None
    sessions_path: Path | None = None
    manifest_path: Path | None = None
    composition_path: Path | None = None
    system_prompt_path: Path | None = None
    cordis_path: Path | None = None
    commit_evidence_path: Path | None = None
    tool_gateway_evidence_path: Path | None = None


class DeepSeekHarnessProcessRuntime:
    """Run the official SDK inside one AEC-owned, isolated worker process."""

    def __init__(
        self,
        *,
        settings: DeepSeekHarnessSettings,
        workspace: Path,
        worker_command: tuple[str, ...] | None = None,
        native_tools: Mapping[str, NativeTool] | None = None,
    ) -> None:
        self.settings = settings
        self.workspace = workspace.resolve()
        self.worker_command = worker_command or (
            sys.executable,
            "-m",
            "aec_bench.adapters.deepseek_harness.worker",
        )
        self.native_tools = dict(native_tools or {})
        self.paths = _deepseek_paths(self.workspace, trial_id=f"run-{uuid.uuid4().hex}")
        self._has_run = False

    def run(self, request: AdapterRequest) -> DeepSeekHarnessRun:
        if self._has_run:
            raise DeepSeekHarnessRuntimeError("one DeepSeek Harness runtime instance can execute only one trial")
        self._has_run = True
        native_tool_names = frozenset(self.native_tools)
        validate_deepseek_request(request, native_tool_names=native_tool_names)
        contract, commit_required = deepseek_output_commit_configuration(request)
        timeout_seconds = request_timeout_seconds(request)
        max_tokens = request_max_tokens(request)
        self._prepare_directories()
        plugins = self._write_evidence_inputs(request)
        environment = build_deepseek_worker_environment(
            workspace=self.workspace,
            settings=self.settings,
            paths=self.paths,
        )
        self._write_composition_record(
            request,
            environment=environment,
            plugins=plugins,
        )
        self.paths.request.write_text(
            json.dumps(
                _worker_request_payload(
                    self.settings,
                    self.workspace,
                    self.paths,
                    request,
                    max_tokens=max_tokens,
                ),
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        commit_endpoint = self._commit_endpoint(contract, commit_required=commit_required)
        tool_gateway = self._tool_gateway()
        for endpoint in (commit_endpoint, tool_gateway):
            if endpoint is not None:
                endpoint.start()
                environment.update(endpoint.connection_environment())
        command = (
            *self.worker_command,
            str(self.paths.request),
            str(self.paths.result),
            str(self.paths.notifications),
        )
        started_at = datetime.now(UTC)
        timed_out = False
        try:
            with self.paths.stderr.open("w", encoding="utf-8") as stderr:
                process = subprocess.Popen(
                    command,
                    cwd=self.workspace,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=stderr,
                    stderr=stderr,
                    text=True,
                    start_new_session=True,
                )
                try:
                    process.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    _stop_process_group(process)
                else:
                    _stop_process_group(process)
        finally:
            for endpoint in (commit_endpoint, tool_gateway):
                if endpoint is not None:
                    endpoint.close()
            self._retire_transient_directories()

        finished_at = datetime.now(UTC)
        self._redact_secret_values(environment)
        if timed_out:
            error = f"DeepSeek Harness exceeded timeout_sec={timeout_seconds}"
            self._write_failure_evidence(
                error=error,
                exit_code=process.returncode,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                commit_required=commit_required,
                plugins=plugins,
                started_at=started_at,
                finished_at=finished_at,
            )
            raise DeepSeekHarnessRuntimeTimeout(error)

        if process.returncode != 0:
            error = f"DeepSeek Harness worker failed with exit code {process.returncode}"
            self._write_failure_evidence(
                error=error,
                exit_code=process.returncode,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                commit_required=commit_required,
                plugins=plugins,
                started_at=started_at,
                finished_at=finished_at,
            )
            raise DeepSeekHarnessRuntimeError(f"{error}; see {self.paths.stderr}")
        if not self.paths.result.is_file():
            self._write_failure_evidence(
                error="DeepSeek Harness worker exited without a result document",
                exit_code=process.returncode,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                commit_required=commit_required,
                plugins=plugins,
                started_at=started_at,
                finished_at=finished_at,
            )
            raise DeepSeekHarnessRuntimeError("DeepSeek Harness worker exited without a result document")
        if not self.paths.notifications.is_file():
            self._write_failure_evidence(
                error="DeepSeek Harness worker exited without raw notifications",
                exit_code=process.returncode,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                commit_required=commit_required,
                plugins=plugins,
                started_at=started_at,
                finished_at=finished_at,
            )
            raise DeepSeekHarnessRuntimeError("DeepSeek Harness worker exited without raw notifications")

        try:
            worker_result = DeepSeekWorkerResult.model_validate_json(self.paths.result.read_text(encoding="utf-8"))
            notifications = _read_notifications(self.paths.notifications)
        except ValueError as exc:
            error = f"invalid DeepSeek Harness worker evidence: {exc}"
            self._write_failure_evidence(
                error=error,
                exit_code=process.returncode,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                commit_required=commit_required,
                plugins=plugins,
                started_at=started_at,
                finished_at=finished_at,
            )
            raise DeepSeekHarnessRuntimeError(error) from exc

        projection = reduce_deepseek_notifications(worker_result.session_id, notifications)
        completion_commit, commit_error = self._finalize_output_commit(
            commit_endpoint,
            contract=contract,
            session_id=worker_result.session_id,
            model_turns=projection.root_model_calls,
            notifications=notifications,
        )
        self._write_success_evidence(
            worker_result=worker_result,
            notifications=notifications,
            exit_code=process.returncode,
            commit_required=commit_required,
            completion_commit=completion_commit,
            commit_error=commit_error,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            plugins=plugins,
            projection=projection,
            started_at=started_at,
            finished_at=finished_at,
        )
        return DeepSeekHarnessRun(
            session_id=worker_result.session_id,
            final_response=worker_result.final_response,
            finish_reason=worker_result.finish_reason,
            sdk_version=worker_result.sdk_version,
            runtime_distribution_version=worker_result.runtime_distribution_version,
            runtime_reported_version=worker_result.runtime_reported_version,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            projection=projection,
            output_commit_mode="required" if commit_required else "disabled",
            completion_commit=completion_commit,
            commit_error=commit_error,
            notifications_path=self.paths.notifications,
            stderr_path=self.paths.stderr,
            evidence_manifest_sha256=_file_sha256(self.paths.manifest),
            optional_plugins=plugins,
            native_tools=tuple(sorted(self.native_tools)),
            root_events_path=self.paths.root_events,
            sessions_path=self.paths.sessions,
            manifest_path=self.paths.manifest,
            composition_path=self.paths.composition,
            system_prompt_path=self.paths.system_prompt,
            cordis_path=self.paths.cordis_input,
            commit_evidence_path=self.paths.commit_evidence if commit_required else None,
            tool_gateway_evidence_path=(self.paths.tool_gateway_evidence if self.native_tools else None),
        )

    def _tool_gateway(self) -> ToolGatewayEndpoint | None:
        if not self.native_tools:
            return None
        return ToolGatewayEndpoint(
            tools=self.native_tools,
            evidence_path=self.paths.tool_gateway_evidence,
        )

    def _commit_endpoint(
        self,
        contract: OutputCompletionContract | None,
        *,
        commit_required: bool,
    ) -> OutputCommitEndpoint | None:
        if not commit_required:
            return None
        if contract is None:
            raise DeepSeekHarnessRuntimeError("required output commitment has no completion contract")
        try:
            candidate_path = resolve_trial_output_path(self.workspace, contract.output_path)
        except ValueError as exc:
            raise DeepSeekHarnessRuntimeError(str(exc)) from exc
        initial_content = read_output_completion_content(contract, candidate_path=candidate_path)
        return OutputCommitEndpoint(
            workspace=self.workspace,
            contract=contract,
            initial_content=initial_content,
            evidence_path=self.paths.commit_evidence,
        )

    def _finalize_output_commit(
        self,
        endpoint: OutputCommitEndpoint | None,
        *,
        contract: OutputCompletionContract | None,
        session_id: str,
        model_turns: int,
        notifications: list[dict[str, Any]],
    ) -> tuple[OutputCommitAttestation | None, str | None]:
        if endpoint is None:
            return None, None
        attestation = endpoint.accepted_attestation
        if attestation is None:
            return None, None
        metadata = endpoint.accepted_metadata
        if metadata is None or metadata.get("deepseek_session_id") != session_id:
            return None, "accepted output commit did not match the root DeepSeek session"
        tool_call_id = metadata.get("deepseek_tool_call_id") if metadata is not None else None
        if not isinstance(tool_call_id, str) or not _has_root_commit_tool_call(
            notifications,
            session_id=session_id,
            tool_call_id=tool_call_id,
        ):
            return None, "accepted output commit did not match a root aec_commit_output call"
        if attestation.commit_turn != model_turns:
            return None, "accepted output commit did not match the final AEC model turn"
        if contract is None:
            return None, "accepted output commit has no completion contract"
        stability_error = validate_stable_output_commit(
            contract,
            attestation,
            candidate_path=endpoint.candidate_path,
        )
        if stability_error is not None:
            return None, stability_error
        return attestation, None

    def _prepare_directories(self) -> None:
        for path in (self.paths.root, self.paths.home, self.paths.temporary, self.paths.sessions):
            path.mkdir(parents=True, exist_ok=True)

    def _retire_transient_directories(self) -> None:
        for path in (self.paths.home, self.paths.temporary):
            if not path.exists():
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(self.paths.root.resolve()):
                raise DeepSeekHarnessRuntimeError(f"DeepSeek transient directory leaves the trial root: {path}")
            shutil.rmtree(path)

    def _write_evidence_inputs(
        self,
        request: AdapterRequest,
    ) -> tuple[DeepSeekPluginIdentity, ...]:
        _contract, commit_required = deepseek_output_commit_configuration(request)
        system_prompt = deepseek_system_prompt(request)
        self.paths.system_prompt.write_text(system_prompt, encoding="utf-8")
        cordis_template = (
            tool_gateway_cordis_template(self.settings.provider)
            if self.native_tools
            else baseline_cordis_template(self.settings.provider)
        )
        shutil.copyfile(cordis_template, self.paths.cordis_input)
        plugins: list[DeepSeekPluginIdentity] = []
        if commit_required:
            source_plugin = output_commit_plugin_path().resolve()
            if not source_plugin.is_file():
                raise DeepSeekHarnessRuntimeError(f"DeepSeek output commit plugin is not built: {source_plugin}")
            self.paths.output_commit_plugin.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_plugin, self.paths.output_commit_plugin)
            with self.paths.cordis_input.open("a", encoding="utf-8") as stream:
                stream.write(
                    f"\n- id: aec-output-commit\n  name: {json.dumps(str(self.paths.output_commit_plugin.resolve()))}\n"
                )
            plugins.append(
                DeepSeekPluginIdentity(
                    plugin_id=OUTPUT_COMMIT_PLUGIN_ID,
                    version=OUTPUT_COMMIT_PLUGIN_VERSION,
                    role="output_commit",
                    artifact_path=self.paths.output_commit_plugin.relative_to(self.paths.root).as_posix(),
                )
            )
        if self.native_tools:
            source_plugin = tool_gateway_plugin_path().resolve()
            if not source_plugin.is_file():
                raise DeepSeekHarnessRuntimeError(f"DeepSeek tool gateway plugin is not built: {source_plugin}")
            self.paths.tool_gateway_plugin.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_plugin, self.paths.tool_gateway_plugin)
            with self.paths.cordis_input.open("a", encoding="utf-8") as stream:
                plugin_path = json.dumps(str(self.paths.tool_gateway_plugin.resolve()))
                stream.write(f"\n- id: aec-tools\n  name: {plugin_path}\n")
            plugins.append(
                DeepSeekPluginIdentity(
                    plugin_id=TOOL_GATEWAY_PLUGIN_ID,
                    version=TOOL_GATEWAY_PLUGIN_VERSION,
                    role="native_tools",
                    artifact_path=self.paths.tool_gateway_plugin.relative_to(self.paths.root).as_posix(),
                )
            )
        return tuple(plugins)

    def _write_composition_record(
        self,
        request: AdapterRequest,
        *,
        environment: Mapping[str, str],
        plugins: tuple[DeepSeekPluginIdentity, ...],
    ) -> None:
        _contract, commit_required = deepseek_output_commit_configuration(request)
        passthrough_names = sorted(
            name for name in _PASSTHROUGH_ENVIRONMENT if name != _PROVIDER_KEY_ENV and name in environment
        )
        secret_names = [_PROVIDER_KEY_ENV] if environment.get(_PROVIDER_KEY_ENV) else []
        if commit_required:
            secret_names.append(OUTPUT_COMMIT_TOKEN_ENV)
        if self.native_tools:
            secret_names.append(TOOL_GATEWAY_TOKEN_ENV)
        owned_names = {name for name in environment if name not in _PASSTHROUGH_ENVIRONMENT}
        if commit_required:
            owned_names.update((OUTPUT_COMMIT_SOCKET_ENV, OUTPUT_COMMIT_TOKEN_ENV))
        if self.native_tools:
            owned_names.update((TOOL_GATEWAY_SOCKET_ENV, TOOL_GATEWAY_TOKEN_ENV, TOOL_GATEWAY_MANIFEST_ENV))
        _write_json(
            self.paths.composition,
            {
                **treatment_record(
                    self.settings,
                    timeout_seconds=request_timeout_seconds(request),
                    max_tokens=request_max_tokens(request),
                    output_commit_required=commit_required,
                    native_tools=tuple(sorted(self.native_tools)),
                ),
                "environment": {
                    "owned_names": sorted(owned_names),
                    "passthrough_names": passthrough_names,
                    "provider_endpoint": _redacted_provider_endpoint(environment.get(_PROVIDER_URL_ENV)),
                    "secret_names": secret_names,
                },
                "plugins": [plugin.model_dump(mode="json") for plugin in plugins],
                "resolved_composition_available": False,
                "resolved_tool_surface_available": False,
            },
        )

    def _redact_secret_values(self, environment: Mapping[str, str]) -> None:
        secrets = {
            "provider_api_key": environment.get(_PROVIDER_KEY_ENV),
            "output_commit_capability": environment.get(OUTPUT_COMMIT_TOKEN_ENV),
            "tool_gateway_capability": environment.get(TOOL_GATEWAY_TOKEN_ENV),
        }
        candidates = [
            self.paths.result,
            self.paths.stderr,
            self.paths.notifications,
            self.paths.commit_evidence,
            self.paths.tool_gateway_evidence,
            *self.paths.sessions.rglob("*.jsonl"),
        ]
        redacted_files: list[DeepSeekRedactedFile] = []
        for path in candidates:
            if not path.is_file():
                continue
            _require_safe_evidence_file(path, root=self.paths.root)
            text = path.read_text(encoding="utf-8", errors="replace")
            replacement_count = 0
            redaction_kinds: list[str] = []
            for kind, secret in secrets.items():
                if not secret:
                    continue
                occurrences = text.count(secret)
                if not occurrences:
                    continue
                text = text.replace(secret, "[REDACTED]")
                replacement_count += occurrences
                redaction_kinds.append(kind)
            if not replacement_count:
                continue
            path.write_text(text, encoding="utf-8")
            redacted_files.append(
                DeepSeekRedactedFile(
                    path=path.relative_to(self.paths.root).as_posix(),
                    redaction_kinds=tuple(sorted(redaction_kinds)),
                    replacement_count=replacement_count,
                )
            )
        audit = DeepSeekRedactionAudit(
            replacement_count=sum(record.replacement_count for record in redacted_files),
            files=tuple(redacted_files),
        )
        _write_json(self.paths.redaction_audit, audit.model_dump(mode="json"))

    def _write_success_evidence(
        self,
        *,
        worker_result: DeepSeekWorkerResult,
        notifications: list[dict[str, Any]],
        exit_code: int | None,
        commit_required: bool,
        completion_commit: OutputCommitAttestation | None,
        commit_error: str | None,
        timeout_seconds: int,
        max_tokens: int | None,
        plugins: tuple[DeepSeekPluginIdentity, ...],
        projection: DeepSeekRunProjection,
        started_at: datetime,
        finished_at: datetime,
    ) -> None:
        _write_root_events(self.paths.root_events, worker_result.session_id, notifications)
        _write_json(
            self.paths.runtime_record,
            {
                "status": "completed",
                "session_id": worker_result.session_id,
                "finish_reason": worker_result.finish_reason,
                "sdk_version": worker_result.sdk_version,
                "runtime_distribution_version": worker_result.runtime_distribution_version,
                "runtime_reported_version": worker_result.runtime_reported_version,
                "runtime_reported_version_available": worker_result.runtime_reported_version is not None,
                "worker_exit_code": exit_code,
                "process_group_retired": True,
                "timeout_sec": timeout_seconds,
                "max_tokens": max_tokens,
                "output_commit_mode": "required" if commit_required else "disabled",
                "output_commit_accepted": completion_commit is not None,
                "output_commit_error": commit_error,
            },
        )
        _write_evidence_manifest(
            paths=self.paths,
            settings=self.settings,
            workspace=self.workspace,
            status="completed",
            worker_result=worker_result,
            projection=projection,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            commit_required=commit_required,
            native_tools=tuple(sorted(self.native_tools)),
            plugins=plugins,
            started_at=started_at,
            finished_at=finished_at,
        )

    def _write_failure_evidence(
        self,
        *,
        error: str,
        exit_code: int | None,
        timeout_seconds: int,
        max_tokens: int | None,
        commit_required: bool,
        plugins: tuple[DeepSeekPluginIdentity, ...],
        started_at: datetime,
        finished_at: datetime,
    ) -> None:
        try:
            notifications = _read_notifications(self.paths.notifications) if self.paths.notifications.is_file() else []
        except ValueError:
            notifications = []
        session_id = _first_session_id(notifications)
        projection = reduce_deepseek_notifications(session_id, notifications) if session_id is not None else None
        if session_id is not None:
            _write_root_events(self.paths.root_events, session_id, notifications)
        _write_json(
            self.paths.runtime_record,
            {
                "status": "failed",
                "error": error,
                "session_id": session_id,
                "worker_exit_code": exit_code,
                "process_group_retired": True,
                "timeout_sec": timeout_seconds,
                "max_tokens": max_tokens,
            },
        )
        _write_evidence_manifest(
            paths=self.paths,
            settings=self.settings,
            workspace=self.workspace,
            status="failed",
            worker_result=None,
            projection=projection,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            commit_required=commit_required,
            native_tools=tuple(sorted(self.native_tools)),
            plugins=plugins,
            started_at=started_at,
            finished_at=finished_at,
        )


def build_deepseek_worker_environment(
    *,
    workspace: Path,
    settings: DeepSeekHarnessSettings,
    source: Mapping[str, str] | None = None,
    paths: DeepSeekHarnessPaths | None = None,
    commit_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the only environment inherited by the SDK and runtime process tree."""
    ambient = os.environ if source is None else source
    provider_key, provider_url = _provider_connection(settings, ambient)
    resolved_paths = paths or _deepseek_paths(workspace.resolve(), trial_id="environment")
    environment = {name: ambient[name] for name in _PASSTHROUGH_ENVIRONMENT if name in ambient}
    environment.update(
        {
            "HOME": str(resolved_paths.home),
            # Harbor uploads the package source instead of installing it into the worker virtual environment.
            "PYTHONPATH": str(Path(__file__).resolve().parents[3]),
            "TMPDIR": str(resolved_paths.temporary),
            "DSH_CORDIS_CONFIG": str(
                resolved_paths.cordis_input.resolve()
                if paths is not None
                else baseline_cordis_template(settings.provider).resolve()
            ),
            "DSH_CWD": str(workspace.resolve()),
            _PROVIDER_KEY_ENV: provider_key,
            _PROVIDER_URL_ENV: provider_url,
            "DSH_MODEL": settings.model,
            "DSH_SESSION_ROOT": str(resolved_paths.sessions),
        }
    )
    if commit_environment is not None:
        environment.update(commit_environment)
    return environment


def _worker_request_payload(
    settings: DeepSeekHarnessSettings,
    workspace: Path,
    paths: DeepSeekHarnessPaths,
    request: AdapterRequest,
    *,
    max_tokens: int | None,
) -> dict[str, Any]:
    return {
        "harness_route": harness_provider_route(settings.provider),
        "model": settings.model,
        "cordis": str(paths.cordis_input.resolve()),
        "workspace": str(workspace),
        "session_root": str(paths.sessions),
        "instruction": request.instruction,
        "system_prompt": deepseek_system_prompt(request),
        "max_tokens": max_tokens,
    }


def _deepseek_paths(workspace: Path, *, trial_id: str) -> DeepSeekHarnessPaths:
    root = workspace / "logs" / "deepseek-harness" / trial_id
    return DeepSeekHarnessPaths(
        root=root,
        request=root / "request.json",
        result=root / "worker-result.json",
        notifications=root / "notifications.all.jsonl",
        root_events=root / "events.root.jsonl",
        stderr=root / "stderr.log",
        system_prompt=root / "system-prompt.txt",
        cordis_input=root / "cordis.input.yml",
        runtime_record=root / "runtime.json",
        composition=root / "composition.json",
        manifest=root / "evidence-manifest.json",
        redaction_audit=root / "redaction-audit.json",
        commit_evidence=root / "output-commit-evidence.jsonl",
        tool_gateway_evidence=root / "tool-gateway-evidence.jsonl",
        output_commit_plugin=root / "plugins" / "output-commit" / "index.js",
        tool_gateway_plugin=root / "plugins" / "tools" / "index.js",
        home=root / "runtime-home",
        temporary=root / "tmp",
        sessions=root / "sessions",
    )


def _read_notifications(path: Path) -> list[dict[str, Any]]:
    notifications: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"notification line {line_number} must contain an object")
        notifications.append(cast(dict[str, Any], value))
    return notifications


def _write_root_events(path: Path, session_id: str, notifications: list[dict[str, Any]]) -> None:
    root_notifications: list[dict[str, Any]] = []
    for notification in notifications:
        envelope = notification_envelope_parts(notification)
        if envelope is None:
            continue
        method, payload = envelope
        if method != "session.event" or payload.get("sessionId") != session_id:
            continue
        root_notifications.append(notification)
    path.write_text(
        "".join(json.dumps(notification, sort_keys=True) + "\n" for notification in root_notifications),
        encoding="utf-8",
    )


def _first_session_id(notifications: list[dict[str, Any]]) -> str | None:
    for notification in notifications:
        envelope = notification_envelope_parts(notification)
        if envelope is None:
            continue
        _method, payload = envelope
        session_id = payload.get("sessionId")
        if isinstance(session_id, str) and session_id:
            return session_id
    return None


def _has_root_commit_tool_call(
    notifications: list[dict[str, Any]],
    *,
    session_id: str,
    tool_call_id: str,
) -> bool:
    for notification in notifications:
        envelope = notification_envelope_parts(notification)
        if envelope is None:
            continue
        method, payload = envelope
        if method != "session.event" or payload.get("sessionId") != session_id:
            continue
        event = payload.get("event")
        if not isinstance(event, dict) or event.get("type") != "tool/call":
            continue
        data = event.get("data")
        if isinstance(data, dict) and data.get("name") == "aec_commit_output" and data.get("callId") == tool_call_id:
            return True
    return False


def _write_evidence_manifest(
    *,
    paths: DeepSeekHarnessPaths,
    settings: DeepSeekHarnessSettings,
    workspace: Path,
    status: Literal["completed", "failed"],
    worker_result: DeepSeekWorkerResult | None,
    projection: DeepSeekRunProjection | None,
    timeout_seconds: int,
    max_tokens: int | None,
    commit_required: bool,
    native_tools: tuple[str, ...],
    plugins: tuple[DeepSeekPluginIdentity, ...],
    started_at: datetime,
    finished_at: datetime,
) -> None:
    artifacts: list[DeepSeekEvidenceArtifact] = []
    roles = {
        paths.request: "worker_request",
        paths.result: "worker_result",
        paths.notifications: "all_session_notifications",
        paths.root_events: "root_session_events",
        paths.stderr: "worker_stderr",
        paths.system_prompt: "system_prompt",
        paths.cordis_input: "cordis_input",
        paths.runtime_record: "runtime_identity",
        paths.composition: "composition_identity",
        paths.redaction_audit: "redaction_audit",
        paths.commit_evidence: "output_commit_evidence",
        paths.tool_gateway_evidence: "tool_gateway_evidence",
        paths.output_commit_plugin: "optional_plugin",
        paths.tool_gateway_plugin: "optional_plugin",
    }
    for session_path in sorted(paths.sessions.rglob("*.jsonl")):
        roles[session_path] = "deepseek_session_jsonl"
    for path, role in roles.items():
        if not path.is_file():
            continue
        _require_safe_evidence_file(path, root=paths.root)
        artifacts.append(
            DeepSeekEvidenceArtifact(
                path=path.relative_to(paths.root).as_posix(),
                role=role,
                sha256=_file_sha256(path),
                size_bytes=path.stat().st_size,
            )
        )
    sdk_version = (
        worker_result.sdk_version if worker_result is not None else _distribution_version("deepseek-harness-sdk")
    )
    runtime_distribution_version = (
        worker_result.runtime_distribution_version
        if worker_result is not None
        else _distribution_version("deepseek-harness-runtime-bin")
    )
    manifest = DeepSeekEvidenceManifest(
        trial_id=paths.root.name,
        generated_at=finished_at,
        adapter=DeepSeekAdapterIdentity(
            aec_bench_version=_distribution_version("aec-bench"),
            python_sdk_version=sdk_version,
            runtime_distribution_version=runtime_distribution_version,
            runtime_reported_version=(worker_result.runtime_reported_version if worker_result is not None else None),
        ),
        composition=DeepSeekCompositionIdentity(
            output_commit_mode="required" if commit_required else "disabled",
            native_tools=native_tools,
        ),
        model=DeepSeekModelIdentity(
            provider=settings.provider,
            harness_route=harness_provider_route(settings.provider),
            requested=settings.requested_model or settings.model,
            resolved=settings.model,
        ),
        execution=DeepSeekExecutionIdentity(
            status=status,
            root_session_id=(
                worker_result.session_id if worker_result is not None else _projection_session_id(projection)
            ),
            child_session_ids=projection.child_session_ids if projection is not None else (),
            workspace=str(workspace),
            started_at=started_at,
            finished_at=finished_at,
            finish_reason=(
                worker_result.finish_reason
                if worker_result is not None
                else projection.last_turn_end_reason
                if projection is not None
                else None
            ),
            aec_model_turns_used=projection.root_model_calls if projection is not None else 0,
            deepseek_root_turns=projection.root_turns if projection is not None else 0,
            tool_calls_started=projection.tool_calls_started if projection is not None else 0,
            tool_calls_completed=projection.tool_calls_completed if projection is not None else 0,
            timeout_sec=timeout_seconds,
            max_tokens=max_tokens,
            process_group_retired=True,
        ),
        plugins=plugins,
        redaction_audit_path=paths.redaction_audit.relative_to(paths.root).as_posix(),
        artifacts=tuple(artifacts),
    )
    _write_json(paths.manifest, manifest.model_dump(mode="json"))
    try:
        verify_deepseek_evidence_manifest(paths.manifest)
    except ValueError as exc:
        raise DeepSeekHarnessRuntimeError(f"invalid DeepSeek evidence receipt: {exc}") from exc


def _distribution_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def _projection_session_id(projection: DeepSeekRunProjection | None) -> str | None:
    return projection.session_id if projection is not None else None


def _redacted_provider_endpoint(value: str | None) -> str:
    if value is None:
        return "provider-default"
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.hostname:
        return "configured-non-url"
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    try:
        port = parsed.port
    except ValueError:
        return "configured-invalid-url"
    netloc = f"{host}:{port}" if port is not None else host
    endpoint = urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    return f"{endpoint}?<redacted>" if parsed.query else endpoint


def _provider_connection(settings: DeepSeekHarnessSettings, source: Mapping[str, str]) -> tuple[str, str]:
    if settings.provider == "azure":
        key = _required_provider_value(source, _AZURE_KEY_ENV)
        endpoint = _required_provider_value(source, _AZURE_ENDPOINT_ENV)
        return key, _azure_openai_v1_endpoint(endpoint)
    if settings.provider == "deepseek":
        key = _required_provider_value(source, _DEEPSEEK_KEY_ENV)
        endpoint = source.get(_DEEPSEEK_ENDPOINT_ENV, "").strip() or _DEEPSEEK_DEFAULT_ENDPOINT
        return key, _absolute_provider_endpoint(endpoint, name=_DEEPSEEK_ENDPOINT_ENV)
    raise DeepSeekHarnessRuntimeError(f"unsupported DeepSeek Harness provider: {settings.provider!r}")


def _required_provider_value(source: Mapping[str, str], name: str) -> str:
    value = source.get(name, "").strip()
    if not value:
        raise DeepSeekHarnessRuntimeError(f"required environment variable is not set: {name}")
    return value


def _azure_openai_v1_endpoint(value: str) -> str:
    """Return the Azure OpenAI-compatible v1 endpoint used by the Harness plugin."""
    normalized = _absolute_provider_endpoint(value, name=_AZURE_ENDPOINT_ENV)
    parsed = urlsplit(normalized)
    path = parsed.path.rstrip("/")
    if not path.endswith("/openai/v1"):
        path = f"{path}/openai/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _absolute_provider_endpoint(value: str, *, name: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise DeepSeekHarnessRuntimeError(f"{name} must be an absolute HTTP or HTTPS URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise DeepSeekHarnessRuntimeError(f"{name} must not contain credentials, a query, or a fragment")
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _require_safe_evidence_file(path: Path, *, root: Path) -> None:
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise DeepSeekHarnessRuntimeError(f"DeepSeek evidence file leaves the trial root: {path}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stop_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    if process.poll() is None:
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if not _process_group_exists(process.pid):
            return
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    if process.poll() is None:
        process.wait()


def _process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
