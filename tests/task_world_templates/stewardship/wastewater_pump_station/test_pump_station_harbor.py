# ABOUTME: Tests pump-station Harbor export, deterministic reference execution, and verification.
# ABOUTME: Exercises real task physics and durable artifacts without a model-provider call.

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from harbor.models.job.config import JobConfig

from aec_bench.adapters.base import AdapterFailureKind, AdapterRequest, AdapterResult
from aec_bench.adapters.transcript import (
    TranscriptEntry,
    TranscriptRole,
    initialize_transcript,
)
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.task_world_templates.harbor_exporting.constants import (
    RUNTIME_DEPENDENCIES,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_job import (
    build_pump_station_harbor_job_config,
    validate_pump_station_harbor_backend_for_execution,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    run_pump_station_model_session,
    run_pump_station_reference_session,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_verifier import (
    verify_pump_station_harbor_run,
)


def test_exported_harbor_task_runs_and_verifies_reference_session(tmp_path: Path) -> None:
    task_dir = tmp_path / "tasks" / "stewardship" / "wastewater-pump-station"
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=Path(__file__).resolve().parents[4],
    )
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")
    run_dir = tmp_path / "world-session"

    completed = run_pump_station_reference_session(
        bridge=bridge,
        output_dir=run_dir,
        session_identity="local-harbor-1",
    )
    verification = verify_pump_station_harbor_run(
        run_dir=run_dir,
        export_manifest_path=exported.manifest_path,
        package_dir=exported.package_dir,
    )

    manifest = json.loads(exported.manifest_path.read_text(encoding="utf-8"))
    inventory = json.loads((run_dir / "artifact-inventory.json").read_text(encoding="utf-8"))
    verifier_script = (exported.task_dir / "tests" / "test.sh").read_text(encoding="utf-8")
    dockerfile = (exported.task_dir / "environment" / "Dockerfile").read_text(encoding="utf-8")
    reward_path = tmp_path / "verifier" / "reward.json"
    details_path = tmp_path / "verifier" / "details.json"
    shell_environment = dict(os.environ)
    shell_environment.update(
        {
            "AEC_BENCH_WORLD_SESSION_DIR": str(run_dir),
            "AEC_BENCH_EXPORT_MANIFEST": str(exported.manifest_path),
            "AEC_BENCH_REFERENCE_PACKAGE_DIR": str(exported.package_dir),
            "AEC_BENCH_VERIFIER_RUNTIME": str(exported.verifier_runtime_wheel_path),
            "AEC_BENCH_REWARD_PATH": str(reward_path),
            "AEC_BENCH_DETAILS_PATH": str(details_path),
        }
    )
    shell_result = subprocess.run(
        [str(exported.task_dir / "tests" / "test.sh")],
        env=shell_environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert manifest["execution_kind"] == "stewardship_world_session"
    assert manifest["agent_surface"]["dependencies"] == list(RUNTIME_DEPENDENCIES)
    assert manifest["bridge"]["controller_modes"] == [
        "deterministic_reference",
        "model_tool_loop",
    ]
    assert "deterministic reference controller" not in (task_dir / "instruction.md").read_text(encoding="utf-8").lower()
    assert completed.result.snapshot.sequence == 12
    assert verification["valid"] is True
    assert inventory["transition_count"] == 12
    assert shell_result.returncode == 0, shell_result.stderr
    assert json.loads(reward_path.read_text(encoding="utf-8")) == {"reward": 1.0}
    assert '--verifier-runtime "$VERIFIER_RUNTIME"' in verifier_script
    assert " ".join(RUNTIME_DEPENDENCIES) in dockerfile
    assert not any("research/" in item["path"] for item in inventory["artifacts"])


def test_harbor_job_config_is_local_provider_free_and_collects_world_evidence(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "tasks" / "stewardship" / "wastewater-pump-station"
    export_pump_station_harbor_task(
        task_dir,
        project_root=Path(__file__).resolve().parents[4],
    )

    config = build_pump_station_harbor_job_config(
        task_dir=task_dir,
        jobs_dir=tmp_path / "jobs",
    )
    validated = JobConfig.model_validate(config)
    serialized = json.dumps(config, sort_keys=True)

    assert validated.environment.type.value == "docker"
    assert config["n_attempts"] == 1
    assert config["agents"][0]["kwargs"] == {
        "adapter": "tool_loop",
        "execution_kind": "stewardship_world_session",
        "world_session": {"bridge_mode": "wastewater_pump_station_reference"},
    }
    assert config["artifacts"] == [
        {
            "source": "/workspace/world-session",
            "destination": "agent/world-session",
        },
        {
            "source": "/workspace/output.md",
            "destination": "agent/output.md",
        },
    ]
    assert "API_KEY" not in serialized
    assert "provider" not in serialized.lower()


@pytest.mark.parametrize(
    ("backend", "expected_environment"),
    [
        (
            "modal",
            {
                "type": "modal",
                "force_build": False,
                "delete": True,
            },
        ),
        (
            "morph",
            {
                "import_path": ("aec_bench.providers.morph_harbor:MorphHarborEnvironment"),
                "force_build": False,
                "delete": True,
                "kwargs": {"compute_backend": "morph"},
            },
        ),
    ],
)
def test_harbor_job_config_prepares_remote_backend_without_provider_calls(
    tmp_path: Path,
    backend: str,
    expected_environment: dict[str, object],
) -> None:
    task_dir = tmp_path / backend / "tasks" / "stewardship" / "wastewater-pump-station"
    export_pump_station_harbor_task(
        task_dir,
        project_root=Path(__file__).resolve().parents[4],
    )

    config = build_pump_station_harbor_job_config(
        task_dir=task_dir,
        jobs_dir=tmp_path / backend / "jobs",
        backend=backend,
    )
    validated = JobConfig.model_validate(config)
    serialized = json.dumps(config, sort_keys=True)

    assert config["environment"] == expected_environment
    assert validated.agents[0].model_name == ("deterministic-reference-controller")
    assert config["agents"][0]["kwargs"]["execution_kind"] == ("stewardship_world_session")
    assert config["artifacts"][0]["source"] == "/workspace/world-session"
    assert "API_KEY" not in serialized


def test_harbor_job_config_prepares_model_controller_without_credentials(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "tasks" / "stewardship" / "wastewater-pump-station"
    export_pump_station_harbor_task(
        task_dir,
        project_root=Path(__file__).resolve().parents[4],
    )

    config = build_pump_station_harbor_job_config(
        task_dir=task_dir,
        jobs_dir=tmp_path / "jobs",
        backend="modal",
        model_name="au.anthropic.claude-sonnet-4-6",
        max_turns=30,
    )
    serialized = json.dumps(config, sort_keys=True)

    assert config["agents"] == [
        {
            "name": "pump-station-model-controller",
            "import_path": "agents.entrypoint_agent:EntrypointAgent",
            "model_name": "au.anthropic.claude-sonnet-4-6",
            "kwargs": {
                "adapter": "tool_loop",
                "execution_kind": "stewardship_world_session",
                "max_turns": 30,
                "world_session": {
                    "bridge_mode": "wastewater_pump_station_reference",
                    "controller": "model",
                },
            },
        }
    ]
    assert "AWS_BEARER_TOKEN_BEDROCK" not in serialized
    assert "MORPH_API_KEY" not in serialized
    assert "MODAL_TOKEN" not in serialized


def test_modal_execution_preflight_accepts_internet_isolation() -> None:
    validate_pump_station_harbor_backend_for_execution("modal")


def test_morph_execution_preflight_accepts_internet_isolation() -> None:
    validate_pump_station_harbor_backend_for_execution("morph")


def test_model_session_uses_closed_world_tools_and_writes_verified_evidence(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "tasks" / "stewardship" / "wastewater-pump-station"
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=Path(__file__).resolve().parents[4],
    )
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")
    run_dir = tmp_path / "model-world-session"

    completed = run_pump_station_model_session(
        bridge=bridge,
        output_dir=run_dir,
        session_identity="model-controller-1",
        model="bedrock-test-model",
        max_turns=30,
        registry=_ReferenceModelRegistry(),
    )

    inventory = json.loads((run_dir / "artifact-inventory.json").read_text(encoding="utf-8"))
    agent_result = json.loads((run_dir / "agent-result.json").read_text(encoding="utf-8"))
    verification = verify_pump_station_harbor_run(
        run_dir=run_dir,
        export_manifest_path=exported.manifest_path,
        package_dir=exported.package_dir,
    )

    assert completed.result.snapshot.sequence == 12
    assert completed.verification.valid is True
    assert inventory["controller_id"] == "bedrock-test-model"
    assert inventory["transition_count"] == 12
    assert agent_result["input_tokens"] == 20
    assert agent_result["output_tokens"] == 10
    assert verification["valid"] is True


def test_harbor_verifier_rejects_failed_model_controller_with_empty_valid_chain(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "tasks" / "stewardship" / "wastewater-pump-station"
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=Path(__file__).resolve().parents[4],
    )
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")
    run_dir = tmp_path / "failed-model-world-session"

    completed = run_pump_station_model_session(
        bridge=bridge,
        output_dir=run_dir,
        session_identity="failed-model-controller",
        model="bedrock-test-model",
        max_turns=30,
        registry=_FailedModelRegistry(),
    )

    assert completed.verification.valid is True
    assert completed.result.snapshot.sequence == 0
    with pytest.raises(
        ValueError,
        match="pump-station model controller did not complete",
    ):
        verify_pump_station_harbor_run(
            run_dir=run_dir,
            export_manifest_path=exported.manifest_path,
            package_dir=exported.package_dir,
        )


class _ReferenceModelRegistry:
    def build(
        self,
        *,
        adapter_kind: str,
        model_name: str,
        workspace: str,
        **kwargs: object,
    ) -> _ReferenceModelAdapter:
        assert adapter_kind == "tool_loop"
        assert model_name == "bedrock-test-model"
        assert Path(workspace).is_dir()
        assert kwargs["enable_bash"] is False
        native_tools = kwargs["native_tools"]
        assert isinstance(native_tools, tuple)
        return _ReferenceModelAdapter(native_tools)


class _FailedModelRegistry:
    def build(self, **kwargs: object) -> _FailedModelAdapter:
        return _FailedModelAdapter()


class _FailedModelAdapter:
    def execute(self, request: AdapterRequest) -> AdapterResult:
        return AdapterResult(
            adapter_name="tool_loop",
            resolved_model="bedrock-test-model",
            configuration_record={"max_turns": 30},
            agent_output=AgentOutput(
                status=AgentOutputStatus.FAILED,
                output_path=request.output_path,
                output_format=request.output_format,
                error_message="provider failed",
            ),
            transcript=initialize_transcript(request),
            failure_kind=AdapterFailureKind.PROVIDER_ERROR,
            max_turns=30,
            provider_error="provider failed",
        )


class _ReferenceModelAdapter:
    def __init__(self, native_tools: tuple[object, ...]) -> None:
        self._tools = {tool.__name__: tool for tool in native_tools if callable(tool) and hasattr(tool, "__name__")}

    def execute(self, request: AdapterRequest) -> AdapterResult:
        assert "request provisional closure before post-maintenance verification" in (
            request.instruction
        )
        reason = "Exercise the model-controller tool boundary."
        self._tools["observe_pump_station"]()
        self._tools["request_conditional_deferral"]("proposal-01", reason, "pump-a")
        self._tools["transfer_duty"]("proposal-02", reason)
        self._tools["request_inspection"]("proposal-03", reason, "pump-a")
        inspected = json.loads(self._tools["continue_operation"]("proposal-04", reason))
        inspection_id = _evidence_id_from_transition(inspected, "inspection")
        self._tools["continue_operation"]("proposal-05", reason)
        self._tools["request_obstruction_clearance"](
            "proposal-06",
            reason,
            "pump-a",
            inspection_id,
        )
        self._tools["continue_operation"]("proposal-07", reason)
        checked = json.loads(self._tools["continue_operation"]("proposal-08", reason))
        check_id = _evidence_id_from_transition(checked, "functional_checks")
        returned = json.loads(
            self._tools["request_provisional_return"](
                "proposal-09",
                reason,
                "pump-a",
                check_id,
            )
        )
        work_order_id = returned["view"]["current_state"]["work_orders"][0]["work_order_id"]
        self._tools["request_provisional_closure"](
            "proposal-10",
            reason,
            work_order_id,
        )
        self._tools["request_post_maintenance_verification"](
            "proposal-11",
            reason,
            "pump-a",
        )
        self._tools["continue_operation"]("proposal-12", reason)
        transcript = initialize_transcript(request)
        transcript.append(
            TranscriptEntry(
                role=TranscriptRole.ASSISTANT,
                content="The model-controlled stewardship session is complete.",
            )
        )
        return AdapterResult(
            adapter_name="tool_loop",
            resolved_model="bedrock-test-model",
            configuration_record={"max_turns": 30},
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=transcript,
            turns_used=1,
            max_turns=30,
            raw_output_text=("The model-controlled wastewater pump-station session completed.\n"),
            usage_model_calls=1,
            usage_input_tokens=20,
            usage_output_tokens=10,
        )


def _evidence_id_from_transition(
    transition: dict[str, object],
    kind: str,
) -> str:
    view = transition["view"]
    assert isinstance(view, dict)
    state = view["current_state"]
    assert isinstance(state, dict)
    evidence = state["evidence"]
    assert isinstance(evidence, list)
    match = next(item for item in evidence if item["kind"] == kind)
    return str(match["evidence_id"])
