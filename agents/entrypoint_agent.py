# ABOUTME: Universal Harbor agent — dispatches to library adapters via execution_entrypoint.
# ABOUTME: Replaces per-adapter agent files by serializing an execution bundle and running it.

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shlex
import tarfile
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from harbor.agents.base import BaseAgent

from aec_bench.adapters.deepseek_harness.config import DEEPSEEK_HARNESS_VERSION
from aec_bench.adapters.provider_routing import provider_environment, provider_for_execution
from aec_bench.adapters.rlm.providers import (
    preflight_pydantic_model_configuration,
    resolve_pydantic_provider,
)
from aec_bench.adapters.runtime_limits import configured_positive_int, validate_runtime_limit_contract
from aec_bench.agents.tools import inject_trajectory_writer
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.execution_environment import (
    PYDANTIC_AI_RUNTIME_VERSION,
    PYDANTIC_RUNTIME_VERSION,
    RUNTIME_PYTHON_PACKAGES,
)
from aec_bench.contracts.harness_instance import AgentBindingConfig
from aec_bench.contracts.proposal_execution.session import ProposalSessionExecutionRef, ProposalSessionReceipt
from aec_bench.contracts.proposal_execution_profile import (
    ProposalSchedulingSemantics,
)
from aec_bench.contracts.stage_execution import KernelInstructionOverride
from aec_bench.experimentation.proposals.session_config import (
    LoadedProposalSessionHostInputs,
    load_proposal_session_host_inputs,
)
from aec_bench.experimentation.proposals.session_output import (
    verified_proposal_final_output_path,
)
from aec_bench.experimentation.proposals.session_runtime import (
    ProposalBackend,
    build_proposal_session_execution_ref,
    run_proposal_session,
)
from aec_bench.harness.execution_payload import build_entrypoint_execution_bundle, write_execution_bundle
from aec_bench.harness.harbor_task_export import (
    HARBOR_LIFECYCLE_BRIDGE_MODE,
    HarborLifecycleBridge,
    load_harbor_lifecycle_bridge,
    write_harbor_lifecycle_attestation,
)
from aec_bench.harness.lifecycle_local import (
    DEFAULT_DEEPSEEK_LIFECYCLE_MAX_TOKENS,
    run_local_evidence_lifecycle_session,
)
from aec_bench.harness.pump_station_harbor.export import (
    PUMP_STATION_HARBOR_BRIDGE_MODE,
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    PumpStationHarborBridge,
    load_pump_station_harbor_bridge,
)
from aec_bench.harness.pump_station_harbor.session import (
    PUMP_STATION_MODEL_CONTROLLER_MODE,
    PUMP_STATION_MODEL_MAX_TOKENS,
    PUMP_STATION_MODEL_MAX_TURNS,
    CompletedPumpStationModelSession,
    CompletedPumpStationReferenceSession,
    run_pump_station_model_session,
    run_pump_station_reference_session,
)
from aec_bench.lifecycles.catalogue import lifecycle_operation_resolver
from aec_bench.lifecycles.runtime.episode import LifecycleVisibilityPolicy
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_controller import (
    PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LIBRARY_SOURCE = _PROJECT_ROOT / "src" / "aec_bench"

_SHARED_REMOTE_DIR = "/workspace/.aec-bench"
_BUNDLE_REMOTE_PATH = f"{_SHARED_REMOTE_DIR}/execution-bundle.json"
_LIBRARY_ARCHIVE_REMOTE_PATH = f"{_SHARED_REMOTE_DIR}/aec-bench-library.tar.gz"
_PROPOSAL_RUNTIME_ARCHIVE_REMOTE_PATH = f"{_SHARED_REMOTE_DIR}/proposal-runtime.tar.gz"
_PROPOSAL_SESSION_REMOTE_ROOT = "/workspace/proposal-session"
_LIBRARY_REMOTE_PATH = "/opt/aec_bench/aec_bench"
_RESULT_REMOTE_PATH = "/workspace/agent_result.json"
_RUNTIME_VENV = "/opt/aec-bench-venv"
_RUNTIME_PYTHON = f"{_RUNTIME_VENV}/bin/python"


def _source_archive_filter(member: tarfile.TarInfo) -> tarfile.TarInfo | None:
    member_path = Path(member.name)
    if (
        "__pycache__" in member_path.parts
        or "node_modules" in member_path.parts
        or member_path.suffix in {".pyc", ".pyo"}
    ):
        return None
    return member


_HOST_MODEL_PROVIDER_ENVIRONMENT_NAMES = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "azure": (
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_ENDPOINT",
    ),
    "bedrock": (
        "AWS_ACCESS_KEY_ID",
        "AWS_BEARER_TOKEN_BEDROCK",
        "AWS_CONFIG_FILE",
        "AWS_CONTAINER_AUTHORIZATION_TOKEN",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_DEFAULT_REGION",
        "AWS_PROFILE",
        "AWS_REGION",
        "AWS_ROLE_ARN",
        "AWS_ROLE_SESSION_NAME",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SHARED_CREDENTIALS_FILE",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
    ),
    "openai": ("OPENAI_API_KEY",),
    "together": ("TOGETHER_API_KEY",),
}


class EntrypointAgent(BaseAgent):
    """Universal Harbor agent that dispatches to library adapters.

    Instead of embedding inline Python scripts, this agent uploads the
    aec_bench library source and an execution bundle into the container,
    then invokes ``execution_entrypoint.py`` to run the selected adapter.

    Harbor passes ``AgentConfig.parameters`` as keyword arguments to
    ``__init__``, so adapter selection and other config arrive via kwargs.
    """

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        logger: logging.Logger | None = None,
        mcp_servers: list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            logs_dir=logs_dir,
            model_name=model_name,
            logger=logger,
            mcp_servers=mcp_servers,
            **kwargs,
        )
        # Harbor passes AgentConfig.parameters as kwargs
        self._params: dict[str, Any] = kwargs
        self._runtime_python = "python3"
        self._lifecycle_bridge: HarborLifecycleBridge | None = None
        self._proposal_inputs: LoadedProposalSessionHostInputs | None = None
        self._world_session_bridge: PumpStationHarborBridge | None = None

    @staticmethod
    def name() -> str:
        return "entrypoint"

    def version(self) -> str | None:
        return "1.0.0"

    async def setup(self, environment: Any) -> None:
        if "world_session" in self._params:
            self._validate_world_session_configuration()
            bridge = load_pump_station_harbor_bridge(Path(environment.environment_dir))
            if bridge.execution_kind != self._params.get("execution_kind"):
                raise ValueError("continual-world Harbor bridge execution kind differs")
            self._world_session_bridge = bridge
            return
        if "lifecycle_bridge" in self._params:
            self._validate_lifecycle_configuration()
            self._lifecycle_bridge = load_harbor_lifecycle_bridge(Path(environment.environment_dir))
            return
        if "proposal_session" in self._params:
            await self._setup_proposal_session(environment)
            return

        # 1. Verify Python3 available
        result = await environment.exec("python3 --version")
        if result.return_code != 0:
            raise RuntimeError(f"Python3 not available in sandbox.\nstdout: {result.stdout}\nstderr: {result.stderr}")

        prepared = await environment.exec(f"mkdir -p {_SHARED_REMOTE_DIR}")
        if prepared.return_code != 0:
            raise RuntimeError(
                "Failed to prepare shared aec-bench workspace in sandbox.\n"
                f"stdout: {prepared.stdout}\nstderr: {prepared.stderr}"
            )

        # 2. Upload the library as one archive. Harbor's Modal directory upload
        # sends each file separately and can exhaust the agent setup timeout.
        with tempfile.TemporaryDirectory(prefix="aec-bench-library-") as temp_dir:
            archive_path = Path(temp_dir) / "aec-bench-library.tar.gz"
            with tarfile.open(archive_path, mode="w:gz") as archive:
                archive.add(_LIBRARY_SOURCE, arcname=".", filter=_source_archive_filter)
            await environment.upload_file(str(archive_path), _LIBRARY_ARCHIVE_REMOTE_PATH)

        extraction_script = (
            "import pathlib,shutil,tarfile;"
            f"archive=pathlib.Path({_LIBRARY_ARCHIVE_REMOTE_PATH!r});"
            f"target=pathlib.Path({_LIBRARY_REMOTE_PATH!r});"
            "shutil.rmtree(target,ignore_errors=True);"
            "target.mkdir(parents=True,exist_ok=True);"
            "bundle=tarfile.open(archive,mode='r:gz');"
            "bundle.extractall(target,filter='data');"
            "bundle.close();"
            "archive.unlink()"
        )
        extracted = await environment.exec(f"python3 -c {shlex.quote(extraction_script)}")
        if extracted.return_code != 0:
            raise RuntimeError(
                "Failed to extract aec-bench library source in sandbox.\n"
                f"stdout: {extracted.stdout}\nstderr: {extracted.stderr}"
            )

        # 3. Install the pinned runtime in an isolated environment when the task image does not supply it.
        runtime_check = (
            "from importlib.metadata import version;"
            f"raise SystemExit(version('pydantic') != '{PYDANTIC_RUNTIME_VERSION}' or "
            f"version('pydantic-ai') != '{PYDANTIC_AI_RUNTIME_VERSION}')"
        )
        runtime_packages = list(RUNTIME_PYTHON_PACKAGES)
        if self._params.get("adapter") == "deepseek_harness":
            runtime_check += (
                f";expected='{DEEPSEEK_HARNESS_VERSION}';"
                "raise SystemExit(version('deepseek-harness-sdk') != expected or "
                "version('deepseek-harness-runtime-bin') != expected)"
            )
            runtime_packages.append(f"deepseek-harness-sdk=={DEEPSEEK_HARNESS_VERSION}")
        check = await environment.exec(f"{self._runtime_python} -c {shlex.quote(runtime_check)}")
        if check.return_code != 0:
            prepared_runtime = await environment.exec(
                f"python3 -m venv {_RUNTIME_VENV} || "
                "(apt-get update && apt-get install -y --no-install-recommends python3-venv && "
                f"rm -rf /var/lib/apt/lists/* && python3 -m venv {_RUNTIME_VENV})"
            )
            if prepared_runtime.return_code != 0:
                raise RuntimeError(
                    "Failed to prepare the isolated aec-bench runtime in sandbox.\n"
                    f"stdout: {prepared_runtime.stdout}\nstderr: {prepared_runtime.stderr}"
                )
            self._runtime_python = _RUNTIME_PYTHON
            packages = " ".join(shlex.quote(package) for package in runtime_packages)
            installed = await environment.exec(f"{self._runtime_python} -m pip install --no-cache-dir {packages}")
            if installed.return_code != 0:
                raise RuntimeError(
                    "Failed to install the pinned aec-bench runtime in sandbox.\n"
                    f"stdout: {installed.stdout}\nstderr: {installed.stderr}"
                )

        # 4. Inject trajectory_writer.py
        await inject_trajectory_writer(environment)

    async def _setup_proposal_session(self, environment: Any) -> None:
        self._validate_proposal_configuration()
        proposal_inputs = load_proposal_session_host_inputs(
            self._params["proposal_session"],
            environment_dir=Path(environment.environment_dir),
        )
        agent_bindings = tuple(
            binding.configuration
            for binding in proposal_inputs.bundle.fixed_harness.bindings
            if isinstance(binding.configuration, AgentBindingConfig)
        )
        if len(agent_bindings) != 1:
            raise ValueError("proposal session requires exactly one fixed-H0 agent binding")
        if self.model_name != agent_bindings[0].model:
            raise ValueError("proposal Harbor model must match the exact fixed-H0 agent model")

        python = await environment.exec("python3 --version")
        if python.return_code != 0:
            raise RuntimeError(
                f"Python3 not available in proposal sandbox.\nstdout: {python.stdout}\nstderr: {python.stderr}"
            )
        prepared = await environment.exec(f"mkdir -p {_SHARED_REMOTE_DIR}")
        if prepared.return_code != 0:
            raise RuntimeError(
                "Failed to prepare proposal runtime workspace in sandbox.\n"
                f"stdout: {prepared.stdout}\nstderr: {prepared.stderr}"
            )
        await environment.upload_file(
            str(proposal_inputs.runtime_archive.path),
            _PROPOSAL_RUNTIME_ARCHIVE_REMOTE_PATH,
        )
        install_script = (
            "import hashlib,importlib,pathlib,shutil,sys,tarfile;"
            f"archive=pathlib.Path({_PROPOSAL_RUNTIME_ARCHIVE_REMOTE_PATH!r});"
            f"expected={proposal_inputs.runtime_archive.archive_sha256!r};"
            "observed=hashlib.sha256(archive.read_bytes()).hexdigest();"
            "sys.exit('proposal runtime compressed SHA-256 mismatch') "
            "if observed!=expected else None;"
            "root=pathlib.Path('/opt/aec_bench');"
            "target=root/'aec_bench';"
            "shutil.rmtree(target,ignore_errors=True);"
            "root.mkdir(parents=True,exist_ok=True);"
            "bundle=tarfile.open(archive,mode='r:gz');"
            "bundle.extractall(root,filter='data');"
            "bundle.close();"
            "archive.unlink();"
            "sys.path.insert(0,str(root));"
            "module=importlib.import_module("
            "'aec_bench.harness.execution_entrypoint');"
            "module_path=pathlib.Path(module.__file__).resolve();"
            "sys.exit('proposal runtime import escaped install root') "
            "if not module_path.is_relative_to(root.resolve()) else None"
        )
        installed = await environment.exec(f"python3 -c {shlex.quote(install_script)}")
        if installed.return_code != 0:
            raise RuntimeError(
                "Failed to install the pinned proposal runtime in sandbox.\n"
                f"stdout: {installed.stdout}\nstderr: {installed.stderr}"
            )

        runtime_check = await environment.exec(
            'python3 -c "import pydantic_ai; from importlib.metadata import version; '
            f"raise SystemExit(version('pydantic-ai') != "
            f"'{PYDANTIC_AI_RUNTIME_VERSION}')\""
        )
        if runtime_check.return_code != 0:
            raise RuntimeError(
                "Pinned proposal runtime dependencies are absent or mismatched; "
                "the immutable runtime image must supply them before candidate "
                "containers are created.\n"
                f"stdout: {runtime_check.stdout}\n"
                f"stderr: {runtime_check.stderr}"
            )
        self._proposal_inputs = proposal_inputs

    def _validate_proposal_configuration(self) -> None:
        if self._params.get("adapter") != "proposal_session":
            raise ValueError("proposal session requires the proposal_session adapter")
        if self._params.get("extra_env") not in (None, {}):
            raise ValueError("proposal session does not accept agent-supplied environment variables")
        allowed = {"adapter", "extra_env", "proposal_session"}
        unknown = sorted(set(self._params) - allowed)
        if unknown:
            raise ValueError("unsupported proposal session configuration: " + ", ".join(unknown))
        _reject_serialized_provider_secrets(self._params)

    async def run(
        self,
        instruction: str,
        environment: Any,
        context: Any,
    ) -> None:
        if "world_session" in self._params:
            await self._run_world_session(
                instruction=instruction,
                environment=environment,
                context=context,
            )
            return
        if "lifecycle_bridge" in self._params:
            await self._run_host_lifecycle(instruction=instruction, environment=environment, context=context)
            return
        if "proposal_session" in self._params:
            await self._run_host_proposal_session(
                instruction=instruction,
                environment=environment,
                context=context,
            )
            return

        adapter_kind = self._params.get("adapter", "rlm")
        validate_runtime_limit_contract(
            adapter_kind=str(adapter_kind),
            configuration=self._params,
        )
        timeout_sec = configured_positive_int(self._params, "timeout_sec") or 600
        _reject_serialized_provider_secrets(self._params)
        client_payload = self._params.get("client")
        provider_environment = _provider_environment(
            adapter_kind=str(adapter_kind),
            model_name=self.model_name or "",
            client_payload=client_payload,
        )

        effective_instruction = _kernel_instruction(instruction, self._params)
        bundle = build_entrypoint_execution_bundle(
            instruction=effective_instruction,
            adapter_name=self.name(),
            model_name=self.model_name or "",
            harbor_kwargs=self._params,
        )

        # Write bundle to temp file and upload to container
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".json",
                delete=False,
            ) as tmp:
                tmp_path = tmp.name
            write_execution_bundle(path=Path(tmp_path), bundle=bundle)

            await environment.upload_file(tmp_path, _BUNDLE_REMOTE_PATH)
        finally:
            if tmp_path is not None:
                Path(tmp_path).unlink(missing_ok=True)

        # Execute the entrypoint in the container
        cmd = (
            f"PYTHONPATH=/opt/aec_bench:$PYTHONPATH "
            f"{shlex.quote(self._runtime_python)} -m aec_bench.harness.execution_entrypoint "
            f"--bundle {_BUNDLE_REMOTE_PATH} "
            f"--result {_RESULT_REMOTE_PATH}"
        )
        exec_kwargs: dict[str, Any] = {"timeout_sec": timeout_sec}
        if provider_environment:
            exec_kwargs["env"] = provider_environment
        try:
            exec_result = await environment.exec(cmd, **exec_kwargs)
        finally:
            if adapter_kind == "deepseek_harness":
                try:
                    evidence_result = await environment.exec(
                        "if [ -d /workspace/logs/deepseek-harness ]; then "
                        "mkdir -p /logs/agent/deepseek-harness && "
                        "cp -a /workspace/logs/deepseek-harness/. /logs/agent/deepseek-harness/; "
                        "fi",
                        timeout_sec=min(timeout_sec, 60),
                    )
                    if evidence_result.return_code != 0:
                        self.logger.warning("Failed to publish DeepSeek Harness evidence to Harbor agent logs")
                except Exception:
                    self.logger.warning(
                        "Failed to publish DeepSeek Harness evidence to Harbor agent logs",
                        exc_info=True,
                    )

        # Read result and populate context
        try:
            local_result = Path(tempfile.mktemp(suffix=".json"))
            await environment.download_file(_RESULT_REMOTE_PATH, str(local_result))
            result_data = json.loads(local_result.read_text(encoding="utf-8"))
            local_result.unlink(missing_ok=True)

            context.n_input_tokens = result_data.get("usage_input_tokens", 0) or 0
            context.n_output_tokens = result_data.get("usage_output_tokens", 0) or 0
            context.metadata = {
                "adapter_name": result_data.get("adapter_name", ""),
                "resolved_model": result_data.get("resolved_model", ""),
                "model": result_data.get("resolved_model", ""),
                "failure_kind": result_data.get("failure_kind"),
                "stop_reason": result_data.get("stop_reason"),
                "completion_reason": result_data.get("completion_reason"),
                "completion_assistance": result_data.get("completion_assistance"),
                "completion_commit": result_data.get("completion_commit"),
                "turns_used": result_data.get("turns_used"),
                "max_turns": result_data.get("max_turns"),
                "runtime_execution_attestation": result_data.get("runtime_execution_attestation"),
                "exec_return_code": exec_result.return_code,
            }
        except Exception as exc:
            context.metadata = {
                "error": _redact_environment_values(str(exc), provider_environment),
                "exec_return_code": getattr(exec_result, "return_code", None),
                "exec_stderr": _redact_environment_values(
                    getattr(exec_result, "stderr", ""),
                    provider_environment,
                ),
            }

    async def _run_host_proposal_session(
        self,
        *,
        instruction: str,
        environment: Any,
        context: Any,
    ) -> None:
        del instruction
        self._validate_proposal_configuration()
        inputs = self._proposal_inputs
        if inputs is None:
            raise RuntimeError("proposal session setup has not completed")
        environment_session_id = str(
            getattr(environment, "session_id", ""),
        ).strip()
        if not environment_session_id:
            raise RuntimeError("proposal Harbor environment has no session identity")
        backend_value = str(
            getattr(environment, "compute_backend", ""),
        ).strip()
        if backend_value not in {"docker", "modal", "e2b", "daytona", "morph"}:
            raise RuntimeError(
                "proposal Harbor environment has an unsupported compute backend",
            )
        model = self.model_name or ""
        provider_environment = _provider_environment(
            adapter_kind="rlm",
            model_name=model,
            client_payload=None,
        )
        execution = build_proposal_session_execution_ref(
            inputs=inputs,
            session_id=f"proposal-session.{environment_session_id}",
            environment_session_id=environment_session_id,
            backend=cast(ProposalBackend, backend_value),
        )

        with tempfile.TemporaryDirectory(
            prefix="aec-bench-proposal-session-",
        ) as raw_session:
            session_root = Path(raw_session)
            receipt = await _run_profiled_proposal_session(
                inputs=inputs,
                execution=execution,
                session_root=session_root,
                environment=environment,
                child_environment=provider_environment,
            )
            final_output_path: Path | None = None
            if (
                inputs.bundle.compilation.execution_profile is not None
                and inputs.bundle.compilation.execution_profile.scheduling.semantics
                is ProposalSchedulingSemantics.READY_SET_DATAFLOW
            ):
                final_output_path = verified_proposal_final_output_path(
                    session_root=session_root,
                    receipt=receipt,
                )
            receipt_path = session_root / "session-receipt.json"
            receipt_path.write_text(
                json.dumps(
                    receipt.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            await environment.upload_dir(
                str(session_root),
                _PROPOSAL_SESSION_REMOTE_ROOT,
            )
            if final_output_path is not None:
                await environment.upload_file(
                    str(final_output_path),
                    "/workspace/output.md",
                )

        context.n_input_tokens = sum(
            node.resources.tokens_in or 0 for node in receipt.node_receipts if node.resources is not None
        )
        context.n_output_tokens = sum(
            node.resources.tokens_out or 0 for node in receipt.node_receipts if node.resources is not None
        )
        failure_code = receipt.failure_code.value if receipt.failure_code is not None else None
        context.metadata = {
            "adapter_name": "proposal_session",
            "resolved_model": model,
            "model": model,
            "proposal_session_id": receipt.session_id,
            "proposal_session_receipt_sha256": receipt.content_sha256,
            "proposal_session_status": receipt.status.value,
            "trial_record_permitted": receipt.trial_record_permitted,
            "failure_code": failure_code,
            "candidate_id": (inputs.bundle.compilation.candidate_ref.candidate_id),
            "proposal_graph_sha256": (inputs.bundle.compilation.proposal_graph.content_sha256),
            "compilation_sha256": inputs.bundle.compilation.content_sha256,
            "session_plan_sha256": inputs.bundle.session_plan.content_sha256,
            "reward_owner": "harbor_verifier",
        }

    def _validate_lifecycle_configuration(self) -> None:
        mode = self._params.get("lifecycle_bridge")
        if mode != HARBOR_LIFECYCLE_BRIDGE_MODE:
            raise ValueError(f"unsupported lifecycle bridge mode: {mode!r}")
        adapter_kind = self._params.get("adapter", "tool_loop")
        if adapter_kind not in {"deepseek_harness", "tool_loop", "pydantic_ai"}:
            raise ValueError("host-owned lifecycle bridge requires a supported tool-capable adapter")
        if "client" in self._params:
            raise ValueError("host-owned lifecycle bridge does not accept serialized clients")
        if "tools" in self._params:
            raise ValueError("host-owned lifecycle bridge owns its exact tool allowlist")
        if "system_prompt" in self._params:
            raise ValueError("host-owned lifecycle bridge owns its system prompt")
        if self._params.get("extra_env") not in (None, {}):
            raise ValueError("host-owned lifecycle bridge does not accept agent-supplied environment variables")
        allowed = {"adapter", "extra_env", "lifecycle_bridge", "max_tokens", "max_turns", "timeout_sec"}
        unknown = sorted(set(self._params) - allowed)
        if unknown:
            raise ValueError(f"unsupported host-owned lifecycle configuration: {', '.join(unknown)}")
        validate_runtime_limit_contract(adapter_kind=str(adapter_kind), configuration=self._params)
        if adapter_kind == "deepseek_harness":
            if "max_turns" in self._params:
                raise ValueError("deepseek_harness lifecycle runs cannot enforce max_turns")
            configured_positive_int(self._params, "max_tokens")
        elif "max_tokens" in self._params:
            raise ValueError("max_tokens is supported only for deepseek_harness lifecycle runs")
        _reject_serialized_provider_secrets(self._params)

    def _lifecycle_adapter_builder(self) -> Any:
        from aec_bench.adapters.local_registry import build_local_adapter

        return build_local_adapter

    async def _run_host_lifecycle(
        self,
        *,
        instruction: str,
        environment: Any,
        context: Any,
    ) -> None:
        del instruction
        self._validate_lifecycle_configuration()
        configured_bridge = self._lifecycle_bridge
        if configured_bridge is None:
            raise RuntimeError("host-owned lifecycle bridge setup has not completed")
        current_bridge = load_harbor_lifecycle_bridge(Path(environment.environment_dir))
        if current_bridge != configured_bridge:
            raise ValueError("Harbor lifecycle task provenance changed after agent setup")

        adapter_kind = str(self._params.get("adapter", "tool_loop"))
        model = self.model_name or ""
        if not model.strip():
            raise ValueError("host-owned lifecycle bridge requires a model name")
        provider_environment = _provider_environment(
            adapter_kind=adapter_kind,
            model_name=model,
            client_payload=None,
        )
        max_turns = configured_positive_int(self._params, "max_turns") or 60
        max_tokens = configured_positive_int(self._params, "max_tokens")
        timeout_sec = configured_positive_int(self._params, "timeout_sec")
        if adapter_kind == "deepseek_harness" and max_tokens is None:
            max_tokens = DEFAULT_DEEPSEEK_LIFECYCLE_MAX_TOKENS

        with tempfile.TemporaryDirectory(prefix="aec-bench-harbor-lifecycle-") as raw_run:
            run_dir = Path(raw_run) / "lifecycle-run"
            try:
                result = await asyncio.to_thread(
                    run_local_evidence_lifecycle_session,
                    package_dir=current_bridge.package_dir,
                    run_dir=run_dir,
                    model=model,
                    verifier=None,
                    adapter_kind=adapter_kind,
                    max_turns=max_turns,
                    max_tokens=max_tokens,
                    timeout_sec=timeout_sec,
                    process_id="harbor.lifecycle",
                    adapter_builder=self._lifecycle_adapter_builder(),
                    visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
                    operation_resolver=lifecycle_operation_resolver(current_bridge.package_dir, run_dir),
                    require_adapter_identity_match=True,
                )
            except Exception as exc:
                if run_dir.is_dir():
                    _redact_lifecycle_run(run_dir, provider_environment)
                    write_harbor_lifecycle_attestation(run_dir, current_bridge)
                    await environment.upload_dir(str(run_dir), current_bridge.output_path)
                context.metadata = {
                    "adapter_name": adapter_kind,
                    "bridge_mode": HARBOR_LIFECYCLE_BRIDGE_MODE,
                    "bridge_manifest_sha256": current_bridge.manifest_sha256,
                    "error": _redact_environment_values(str(exc), provider_environment),
                    "reward_owner": "harbor_verifier",
                }
                return

            _redact_lifecycle_run(run_dir, provider_environment)
            write_harbor_lifecycle_attestation(run_dir, current_bridge)
            await environment.upload_dir(str(run_dir), current_bridge.output_path)
            agent_evidence = cast(dict[str, Any], result["evidence"]["agent"])
            usage = cast(dict[str, Any], agent_evidence.get("usage", {}))
            context.n_input_tokens = int(usage.get("input_tokens") or 0)
            context.n_output_tokens = int(usage.get("output_tokens") or 0)
            context.metadata = {
                "adapter_name": agent_evidence.get("adapter_name", adapter_kind),
                "bridge_mode": HARBOR_LIFECYCLE_BRIDGE_MODE,
                "bridge_manifest_sha256": current_bridge.manifest_sha256,
                "lifecycle_status": result["evidence"]["lifecycle"]["status"],
                "reward_owner": "harbor_verifier",
            }

    def _validate_world_session_configuration(self) -> None:
        execution_kind = str(self._params.get("execution_kind") or "").strip()
        if execution_kind != PUMP_STATION_HARBOR_EXECUTION_KIND:
            raise ValueError(f"unsupported world-session execution kind: {execution_kind}")
        adapter_kind = str(self._params.get("adapter", "tool_loop"))
        if adapter_kind not in {"deepseek_harness", "tool_loop"}:
            raise ValueError("continual-world session requires a supported tool-capable adapter")
        if self._params.get("extra_env") not in (None, {}):
            raise ValueError("continual-world session does not accept environment variables")
        if "client" in self._params:
            raise ValueError("continual-world session does not accept serialized clients")
        if "tools" in self._params:
            raise ValueError("continual-world session owns its exact tool allowlist")
        if "system_prompt" in self._params:
            raise ValueError("continual-world session owns its system prompt")
        allowed = {
            "adapter",
            "execution_kind",
            "extra_env",
            "max_tokens",
            "max_turns",
            "timeout_sec",
            "world_session",
        }
        unknown = sorted(set(self._params) - allowed)
        if unknown:
            raise ValueError("unsupported continual-world session configuration: " + ", ".join(unknown))
        validate_runtime_limit_contract(
            adapter_kind=adapter_kind,
            configuration=self._params,
        )
        if adapter_kind == "deepseek_harness":
            if "max_turns" in self._params:
                raise ValueError("deepseek_harness world sessions cannot enforce max_turns")
            configured_positive_int(self._params, "max_tokens")
        elif "max_tokens" in self._params or "timeout_sec" in self._params:
            raise ValueError("max_tokens and timeout_sec are supported only for deepseek_harness world sessions")
        _reject_serialized_provider_secrets(self._params)
        session = self._params.get("world_session")
        if not isinstance(session, dict) or session.get("bridge_mode") != PUMP_STATION_HARBOR_BRIDGE_MODE:
            raise ValueError("pump-station world-session bridge configuration differs")
        model = str(self.model_name or "")
        reference_controller = model == PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID
        expected_session = {"bridge_mode": PUMP_STATION_HARBOR_BRIDGE_MODE}
        if not reference_controller:
            expected_session["controller"] = PUMP_STATION_MODEL_CONTROLLER_MODE
        if session != expected_session:
            raise ValueError("pump-station world-session bridge configuration differs")
        if not reference_controller and not model.strip():
            raise ValueError("pump-station model controller requires a model")

    async def _run_world_session(
        self,
        *,
        instruction: str,
        environment: Any,
        context: Any,
    ) -> None:
        del instruction
        self._validate_world_session_configuration()
        configured_bridge = self._world_session_bridge
        if configured_bridge is None:
            raise RuntimeError("continual-world session setup has not completed")
        current_bridge = load_pump_station_harbor_bridge(Path(environment.environment_dir))
        if current_bridge != configured_bridge:
            raise ValueError("continual-world Harbor task changed after agent setup")
        session_configuration = cast(dict[str, Any], self._params["world_session"])
        if (
            self._params.get("execution_kind") != current_bridge.execution_kind
            or session_configuration.get("bridge_mode") != current_bridge.bridge_mode
        ):
            raise ValueError("continual-world Harbor bridge identity changed after setup")
        session_identity = str(getattr(environment, "session_id", "")).strip()
        if not session_identity:
            raise RuntimeError("continual-world Harbor environment has no session identity")

        adapter_kind = str(self._params.get("adapter", "tool_loop"))
        model = str(self.model_name or "")
        uses_provider = model != PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID
        if not uses_provider:
            provider_environment = {}
        elif adapter_kind == "deepseek_harness":
            provider_environment = _provider_environment(
                adapter_kind=adapter_kind,
                model_name=model,
                client_payload=None,
            )
        else:
            provider_environment = _host_model_provider_environment(model)
        max_turns = configured_positive_int(self._params, "max_turns") or PUMP_STATION_MODEL_MAX_TURNS
        max_tokens = configured_positive_int(self._params, "max_tokens")
        timeout_sec = configured_positive_int(self._params, "timeout_sec")
        if adapter_kind == "deepseek_harness" and max_tokens is None:
            max_tokens = PUMP_STATION_MODEL_MAX_TOKENS
        with tempfile.TemporaryDirectory(prefix="aec-bench-continual-world-harbor-") as raw_run:
            staging = Path(raw_run)
            output_dir = staging / "world-session"
            try:
                completed: CompletedPumpStationModelSession | CompletedPumpStationReferenceSession
                if uses_provider:
                    completed = await asyncio.to_thread(
                        run_pump_station_model_session,
                        bridge=current_bridge,
                        output_dir=output_dir,
                        session_identity=session_identity,
                        model=model,
                        adapter_kind=adapter_kind,
                        max_turns=max_turns,
                        max_tokens=max_tokens,
                        timeout_sec=timeout_sec,
                        adapter_builder=self._lifecycle_adapter_builder(),
                    )
                    adapter_result = completed.adapter_result
                    input_tokens = adapter_result.usage_input_tokens or 0
                    output_tokens = adapter_result.usage_output_tokens or 0
                    resolved_model = adapter_result.resolved_model
                    completed_session_id = completed.request.session_id
                    session_status = (
                        "completed"
                        if adapter_result.agent_output.status is AgentOutputStatus.COMPLETED
                        and completed.journey_status.value == "completed"
                        and completed.verification.valid
                        else "incomplete"
                    )
                    world_segment_count = completed.segment_count
                    world_host_control_count = completed.host_control_count
                    world_stop_reason = completed.stop_reason
                    output_file = output_dir / "output.md"
                else:
                    completed = await asyncio.to_thread(
                        run_pump_station_reference_session,
                        bridge=current_bridge,
                        output_dir=output_dir,
                        session_identity=session_identity,
                    )
                    output_file = staging / "output.md"
                    output_file.write_text(
                        "The deterministic wastewater pump-station episode completed.\n",
                        encoding="utf-8",
                    )
                    input_tokens = 0
                    output_tokens = 0
                    resolved_model = PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID
                    completed_session_id = completed.request.session_id
                    session_status = "completed"
                    world_segment_count = 0
                    world_host_control_count = 0
                    world_stop_reason = "reference-controller"
            except Exception as exc:
                if not uses_provider:
                    raise
                context.metadata = {
                    "adapter_name": adapter_kind,
                    "bridge_mode": current_bridge.bridge_mode,
                    "bridge_manifest_sha256": current_bridge.export_manifest_sha256,
                    "error": _redact_environment_values(
                        str(exc),
                        provider_environment,
                    ),
                    "execution_kind": current_bridge.execution_kind,
                    "model": model,
                    "resolved_model": model,
                    "reward_owner": "harbor_verifier",
                    "world_session_status": "failed",
                }
                return
            await environment.upload_dir(
                str(output_dir),
                current_bridge.output_path,
            )
            permissions = await environment.exec(
                f"chmod -R go-rwx {current_bridge.output_path}",
            )
            if permissions.return_code != 0:
                raise RuntimeError(
                    "continual-world Harbor could not make uploaded evidence host-private.\n"
                    f"stdout: {permissions.stdout}\n"
                    f"stderr: {permissions.stderr}",
                )
            await environment.upload_file(
                str(output_file),
                "/workspace/output.md",
            )

        context.n_input_tokens = input_tokens
        context.n_output_tokens = output_tokens
        context.metadata = {
            "adapter_name": adapter_result.adapter_name if uses_provider else "reference_controller",
            "bridge_mode": current_bridge.bridge_mode,
            "bridge_manifest_sha256": current_bridge.export_manifest_sha256,
            "execution_kind": current_bridge.execution_kind,
            "model": resolved_model,
            "resolved_model": resolved_model,
            "reward_owner": "harbor_verifier",
            "world_session_id": completed_session_id,
            "world_session_status": session_status,
            "world_segment_count": world_segment_count,
            "world_host_control_count": world_host_control_count,
            "world_stop_reason": world_stop_reason,
        }


def _host_model_provider_environment(model_name: str) -> dict[str, str]:
    """Preflight a host-owned model and select local values for error redaction."""

    preflight_pydantic_model_configuration(model_name)
    provider = resolve_pydantic_provider(model_name)
    approved_names = _HOST_MODEL_PROVIDER_ENVIRONMENT_NAMES.get(provider, ())
    return {name: value for name in approved_names if (value := os.environ.get(name, "").strip())}


async def _run_profiled_proposal_session(
    *,
    inputs: LoadedProposalSessionHostInputs,
    execution: ProposalSessionExecutionRef,
    session_root: Path,
    environment: Any,
    child_environment: Mapping[str, str],
) -> ProposalSessionReceipt:
    """Select only the environment ownership declared by the frozen profile."""

    execution_profile = inputs.bundle.compilation.execution_profile
    if execution_profile is None:
        raise RuntimeError(
            "proposal Harbor execution requires a profile-bound compilation",
        )
    if execution_profile.scheduling.semantics is ProposalSchedulingSemantics.SEQUENTIAL_DATAFLOW:
        return await run_proposal_session(
            bundle=inputs.bundle,
            execution=execution,
            source_task_root=inputs.source_task_dir,
            session_root=session_root,
            environment=environment,
            child_environment=child_environment,
        )

    pool_factory = getattr(
        environment,
        "create_isolated_environment_pool",
        None,
    )
    if not callable(pool_factory):
        raise RuntimeError(
            "ready-set proposal execution requires a production isolated environment pool provider",
        )
    pool_context = pool_factory(
        capacity=execution_profile.scheduling.max_parallelism,
        receipt_root=session_root / "environment-pool",
        expected_runtime_archive_sha256=(inputs.runtime_archive.archive_sha256),
        expected_runtime_archive_content_sha256=(inputs.runtime_archive.content_sha256),
    )
    async with pool_context as environment_pool:
        return await run_proposal_session(
            bundle=inputs.bundle,
            execution=execution,
            source_task_root=inputs.source_task_dir,
            session_root=session_root,
            environment_pool=environment_pool,
            child_environment=child_environment,
        )


def _kernel_instruction(instruction: str, parameters: Mapping[str, Any]) -> str:
    """Resolve only a content-addressed fixed-kernel override bound to Harbor's task bytes."""

    payload = parameters.get("kernel_instruction_override")
    if payload is None:
        return instruction
    override = KernelInstructionOverride.model_validate(payload)
    observed = hashlib.sha256(instruction.encode("utf-8")).hexdigest()
    if observed != override.original_instruction_sha256:
        raise ValueError("kernel instruction override does not bind the original instruction")
    return override.effective_instruction


def _provider_environment(
    *,
    adapter_kind: str,
    model_name: str,
    client_payload: Any,
    host_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    provider = provider_for_execution(
        adapter_kind=adapter_kind,
        model_name=model_name,
        client_payload=client_payload,
    )
    return provider_environment(provider, host_environment=host_environment)


def _reject_serialized_provider_secrets(value: Any, *, path: str = "configuration") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            nested_path = f"{path}.{key_text}"
            if _is_secret_value_field(key_text) and nested not in (None, ""):
                raise ValueError(
                    "provider secrets must come from the host environment, not serialized configuration: " + nested_path
                )
            _reject_serialized_provider_secrets(nested, path=nested_path)
    elif isinstance(value, list | tuple):
        for index, nested in enumerate(value):
            _reject_serialized_provider_secrets(nested, path=f"{path}[{index}]")


def _is_secret_value_field(name: str) -> bool:
    normalized = name.strip().lower().replace("-", "_")
    if normalized.endswith("_env"):
        return False
    parts = set(normalized.split("_"))
    return bool(
        {"authorization", "credential", "credentials", "password", "secret", "token"} & parts
        or normalized == "api_key"
        or normalized.endswith("_api_key")
    )


def _redact_environment_values(text: Any, environment: Mapping[str, str]) -> str:
    redacted = str(text)
    for value in sorted(environment.values(), key=len, reverse=True):
        if value:
            redacted = redacted.replace(value, "<redacted>")
    return redacted


def _redact_lifecycle_run(run_dir: Path, environment: Mapping[str, str]) -> None:
    """Remove approved provider secret values from every persisted lifecycle artifact."""
    secret_values = sorted(
        {
            variant.encode("utf-8")
            for value in environment.values()
            if value
            for variant in _serialized_secret_variants(value)
        },
        key=len,
        reverse=True,
    )
    for path in sorted(Path(run_dir).rglob("*")):
        if path.is_symlink():
            raise ValueError(f"lifecycle run contains an unsafe symbolic link: {path}")
        if not path.is_file() or not secret_values:
            continue
        content = path.read_bytes()
        redacted = content
        for secret in secret_values:
            redacted = redacted.replace(secret, b"<redacted>")
        if redacted != content:
            path.write_bytes(redacted)


def _serialized_secret_variants(value: str) -> set[str]:
    """Cover raw and nested JSON-string encodings used by persisted run artifacts."""
    variants = {value}
    frontier = {value}
    for _ in range(3):
        encoded = {
            json.dumps(candidate, ensure_ascii=ensure_ascii)[1:-1]
            for candidate in frontier
            for ensure_ascii in (False, True)
        }
        variants.update(encoded)
        frontier = encoded
    return variants
