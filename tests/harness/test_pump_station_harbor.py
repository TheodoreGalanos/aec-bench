# ABOUTME: Proves registered pump worlds use the canonical Harbor export, episode host, and verifier.
# ABOUTME: Covers exact profile authority, durable episode evidence, and the integration entrypoint.

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from harbor.models.trial.config import TrialConfig  # type: ignore[import-untyped]

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.adapters.deepseek_harness.native_world_tools import WORLD_OBSERVE_TOOL_NAME
from aec_bench.adapters.deepseek_harness.tool_gateway import (
    NativeCancellation,
    NativeToolInvocation,
    NativeToolRequestSemantics,
)
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.harness.pump_station_harbor.export import (
    PUMP_STATION_HARBOR_BRIDGE_MODE,
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.harness.pump_station_harbor.job import (
    build_pump_station_harbor_job_config,
)
from aec_bench.harness.pump_station_harbor.session import (
    run_pump_station_model_session,
    run_pump_station_reference_session,
)
from aec_bench.harness.pump_station_harbor.verifier import (
    verify_pump_station_harbor_run,
)
from aec_bench.worlds.catalogue import default_interactive_world_catalogue
from aec_bench.worlds.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition import (
    pump_station_continual_world_definition,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_controller import (
    PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import PumpStationWorldRun
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from tests.support.harbor_local_environment import run_harbor_trial

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _native_invocation(request_id: str, tool_name: str) -> NativeToolInvocation:
    return NativeToolInvocation(
        request_id=request_id,
        deepseek_session_id="session-1",
        deepseek_tool_call_id=request_id,
        model_turn=1,
        tool_name=tool_name,
        generation_id="generation-1",
        admitted_at=datetime.now(UTC),
        cancellation=NativeCancellation(),
    )


def test_registered_profile_export_uses_the_canonical_harbor_bridge(
    tmp_path: Path,
) -> None:
    definition = pump_station_continual_world_definition()
    profile_ref = definition.profiles[0]
    exported = export_pump_station_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
        profile_ref=profile_ref,
    )

    bridge = load_pump_station_harbor_bridge(exported.task_dir / "environment")
    manifest = json.loads(exported.manifest_path.read_text(encoding="utf-8"))
    config = build_pump_station_harbor_job_config(
        task_dir=exported.task_dir,
        jobs_dir=tmp_path / "jobs",
        model_name="bedrock:authorised-registered-model",
        max_turns=4,
    )

    assert "schema_version" not in manifest
    assert manifest["world_build"] == asdict(definition.build)
    assert manifest["continual_profile"] == asdict(profile_ref)
    assert bridge.profile_ref == profile_ref
    assert bridge.reference_system_root == exported.task_dir / "tests" / "reference-system"
    assert bridge.allowed_tools == PUMP_STATION_ACTOR_ACTION_NAMES
    assert config["agents"][0]["name"] == "pump-station-model-controller"
    assert config["agents"][0]["kwargs"]["world_session"] == {
        "bridge_mode": PUMP_STATION_HARBOR_BRIDGE_MODE,
        "controller": "model",
    }


def test_registered_profile_builds_a_deepseek_world_session_without_a_false_turn_limit(
    tmp_path: Path,
) -> None:
    exported = export_pump_station_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
        profile_ref=pump_station_continual_world_definition().profiles[0],
    )

    config = build_pump_station_harbor_job_config(
        task_dir=exported.task_dir,
        jobs_dir=tmp_path / "jobs",
        backend="modal",
        model_name="azure:gpt-4.1-mini-standard",
        adapter="deepseek_harness",
        max_world_actions=17,
        max_tokens=4096,
        timeout_sec=600,
    )

    kwargs = config["agents"][0]["kwargs"]
    assert kwargs == {
        "adapter": "deepseek_harness",
        "execution_kind": PUMP_STATION_HARBOR_EXECUTION_KIND,
        "max_tokens": 4096,
        "max_world_actions": 17,
        "timeout_sec": 600,
        "world_session": {
            "bridge_mode": PUMP_STATION_HARBOR_BRIDGE_MODE,
            "controller": "model",
        },
    }
    assert "max_turns" not in kwargs


def test_registered_reference_session_uses_standard_evidence_and_replays_offline(
    tmp_path: Path,
) -> None:
    profile_ref = pump_station_continual_world_definition().profiles[0]
    exported = export_pump_station_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
        profile_ref=profile_ref,
    )
    bridge = load_pump_station_harbor_bridge(exported.task_dir / "environment")
    output_dir = tmp_path / "world-session"

    completed = run_pump_station_reference_session(
        bridge=bridge,
        output_dir=output_dir,
        session_identity="registered-reference",
    )
    verified = verify_pump_station_harbor_run(
        run_dir=output_dir,
        export_manifest_path=bridge.export_manifest_path,
        package_dir=bridge.package_root,
        reference_system_dir=bridge.reference_system_root,
        verifier_runtime_path=bridge.verifier_runtime_path,
    )

    assert completed.request.session_id == "episode.registered-reference"
    assert completed.request.agent_tenure_id == "actor.registered-reference"
    assert completed.request.start_snapshot is not None
    assert completed.request.start_snapshot.sequence == 0
    assert completed.result.snapshot.sequence == 25
    assert completed.verification.valid
    assert verified["valid"] is True
    assert verified["transition_count"] == 25
    assert (output_dir / "world-run" / "temporal-evidence" / "capability.json").is_file()
    assert not (output_dir / "temporal-evidence").exists()
    assert not (output_dir / "evaluation.json").exists()
    assert not (output_dir / "semantic-outcome.json").exists()

    report_path = output_dir / "verification-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["valid"] = False
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact inventory differs"):
        verify_pump_station_harbor_run(
            run_dir=output_dir,
            export_manifest_path=bridge.export_manifest_path,
            package_dir=bridge.package_root,
            reference_system_dir=bridge.reference_system_root,
            verifier_runtime_path=bridge.verifier_runtime_path,
        )


def test_deepseek_model_session_receives_only_actor_tools_and_token_limits(tmp_path: Path) -> None:
    exported = export_pump_station_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
        profile_ref=pump_station_continual_world_definition().profiles[0],
    )
    bridge = load_pump_station_harbor_bridge(exported.task_dir / "environment")
    captured: dict[str, object] = {}

    class FakeAdapter:
        def __init__(self, native_tool_definitions: tuple[Any, ...]) -> None:
            self._definitions = {definition.name: definition for definition in native_tool_definitions}

        def execute(self, request: AdapterRequest) -> AdapterResult:
            captured["request"] = request
            observation = self._definitions[WORLD_OBSERVE_TOOL_NAME].handler(
                _native_invocation("dsh:session-1:observe-1", WORLD_OBSERVE_TOOL_NAME),
                {},
            )
            captured["observation"] = observation.result
            return AdapterResult(
                adapter_name="deepseek_harness",
                resolved_model="gpt-4.1-mini-standard",
                configuration_record=dict(request.configuration),
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path=request.output_path,
                    output_format=request.output_format,
                ),
                transcript=[],
                turns_used=1,
                raw_output_text="Observed the current pump-station state.",
                usage_model_calls=1,
            )

    def build_adapter(**kwargs: object) -> FakeAdapter:
        captured["builder"] = kwargs
        definitions = kwargs["native_tool_definitions"]
        assert isinstance(definitions, tuple)
        return FakeAdapter(definitions)

    completed = run_pump_station_model_session(
        bridge=bridge,
        output_dir=tmp_path / "world-session",
        session_identity="deepseek-world",
        model="azure:gpt-4.1-mini-standard",
        adapter_kind="deepseek_harness",
        max_tokens=4096,
        timeout_sec=600,
        adapter_builder=build_adapter,
    )

    builder = captured["builder"]
    assert isinstance(builder, dict)
    assert builder["adapter_kind"] == "deepseek_harness"
    assert builder["enable_bash"] is False
    assert builder["native_tools"] is None
    native_tool_definitions = builder["native_tool_definitions"]
    assert isinstance(native_tool_definitions, tuple)
    assert tuple(definition.name for definition in native_tool_definitions) == (
        WORLD_OBSERVE_TOOL_NAME,
        *sorted(PUMP_STATION_ACTOR_ACTION_NAMES),
    )
    catalogue = PumpStationEpisodeHost(tmp_path / "catalogue-host").capabilities()
    catalogue_schemas = {action.name: action.input_schema for action in catalogue.actions}
    assert {
        definition.name: definition.parameters_schema for definition in native_tool_definitions[1:]
    } == catalogue_schemas
    assert all("request_id" not in definition.parameters_schema["properties"] for definition in native_tool_definitions)
    assert all(
        definition.request_semantics is NativeToolRequestSemantics.HANDLER_AUTHORITY
        for definition in native_tool_definitions
    )
    assert isinstance(captured["observation"], dict)
    request = captured["request"]
    assert isinstance(request, AdapterRequest)
    assert request.configuration == {"max_tokens": 4096, "timeout_sec": 600}
    assert "max_turns" not in request.configuration
    assert completed.adapter_result.adapter_name == "deepseek_harness"
    evidence = json.loads((completed.output_dir / "agent-result.json").read_text(encoding="utf-8"))
    assert evidence["adapter"] == "deepseek_harness"
    assert evidence["limits"] == {"max_tokens": 4096, "timeout_sec": 600}
    inventory = json.loads((completed.output_dir / "artifact-inventory.json").read_text(encoding="utf-8"))
    assert inventory["controller_id"] == "gpt-4.1-mini-standard"
    inventory_paths = {artifact["path"] for artifact in inventory["artifacts"]}
    assert "actor-invocation-evidence.jsonl" in inventory_paths
    assert "native-world-tool-surface.json" in inventory_paths
    authority_record = completed.adapter_result.configuration_record["actor_invocation_authority"]
    assert authority_record["actor_principal_id"] == "actor.deepseek-world"
    assert authority_record["max_world_actions"] == 90
    assert authority_record["world_action_count"] == 0
    assert authority_record["close"]["complete"] is True
    surface_record = json.loads((completed.output_dir / "native-world-tool-surface.json").read_text(encoding="utf-8"))
    assert surface_record["catalogue_sha256"] == authority_record["catalogue_sha256"]
    assert surface_record["action_mapping"] == [
        {"catalogue_action": action_name, "public_tool": action_name}
        for action_name in sorted(PUMP_STATION_ACTOR_ACTION_NAMES)
    ]
    assert completed.adapter_result.configuration_record["native_world_tools"] == {
        "catalogue_sha256": surface_record["catalogue_sha256"],
        "public_tool_surface_sha256": surface_record["public_tool_surface_sha256"],
        "evidence_path": "native-world-tool-surface.json",
        "presentation_mode": "deepseek-native",
    }
    actor_evidence = [
        json.loads(line)
        for line in (completed.output_dir / "actor-invocation-evidence.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["record_type"] for record in actor_evidence] == [
        "header",
        "capabilities",
        "capabilities",
        "observe",
        "close",
    ]
    assert "Do not stop only because one action was accepted" in request.instruction


def test_tool_loop_model_session_uses_catalogue_compiled_pydantic_tools(tmp_path: Path) -> None:
    exported = export_pump_station_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
        profile_ref=pump_station_continual_world_definition().profiles[0],
    )
    bridge = load_pump_station_harbor_bridge(exported.task_dir / "environment")
    captured: dict[str, object] = {}

    class FakeAdapter:
        def execute(self, request: AdapterRequest) -> AdapterResult:
            captured["request"] = request
            return AdapterResult(
                adapter_name="tool_loop",
                resolved_model="gpt-4.1-mini-standard",
                configuration_record=dict(request.configuration),
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path=request.output_path,
                    output_format=request.output_format,
                ),
                transcript=[],
                turns_used=1,
                raw_output_text="Observed no action requirement.",
                usage_model_calls=1,
            )

    def build_adapter(**kwargs: object) -> FakeAdapter:
        captured["builder"] = kwargs
        return FakeAdapter()

    run_pump_station_model_session(
        bridge=bridge,
        output_dir=tmp_path / "world-session",
        session_identity="tool-loop-world",
        model="azure:gpt-4.1-mini-standard",
        adapter_kind="tool_loop",
        max_turns=4,
        adapter_builder=build_adapter,
    )

    builder = captured["builder"]
    assert isinstance(builder, dict)
    assert builder["native_tool_definitions"] is None
    native_tools = builder["native_tools"]
    assert isinstance(native_tools, tuple)
    assert tuple(tool.name for tool in native_tools) == (
        WORLD_OBSERVE_TOOL_NAME,
        *sorted(PUMP_STATION_ACTOR_ACTION_NAMES),
    )
    catalogue = PumpStationEpisodeHost(tmp_path / "catalogue-host").capabilities()
    assert {tool.name: tool.function_schema.json_schema for tool in native_tools[1:]} == {
        action.name: action.input_schema for action in catalogue.actions
    }
    assert all("request_id" not in tool.function_schema.json_schema.get("properties", {}) for tool in native_tools)
    request = captured["request"]
    assert isinstance(request, AdapterRequest)
    assert request.configuration == {"max_turns": 4}


def test_model_journey_shares_actor_authority_across_segments_and_stops_at_budget(tmp_path: Path) -> None:
    exported = export_pump_station_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
        profile_ref=pump_station_continual_world_definition().profiles[0],
    )
    bridge = load_pump_station_harbor_bridge(exported.task_dir / "environment")
    builds: list[dict[str, object]] = []

    class FakeAdapter:
        def __init__(self, native_tool_definitions: tuple[Any, ...], segment_index: int) -> None:
            self._definitions = {definition.name: definition for definition in native_tool_definitions}
            self._segment_index = segment_index

        def execute(self, request: AdapterRequest) -> AdapterResult:
            if self._segment_index == 0:
                observation = self._definitions[WORLD_OBSERVE_TOOL_NAME].handler(
                    _native_invocation("dsh:session-1:observe-before-actions", WORLD_OBSERVE_TOOL_NAME),
                    {},
                )
                verification = self._definitions["request_post_maintenance_verification"].handler(
                    _native_invocation("dsh:session-1:verification-a", "request_post_maintenance_verification"),
                    {
                        "reason": "Complete the visible verification obligation.",
                        "pump_id": "pump-a",
                        "backlog_item_id": "backlog-a-verification-001",
                    },
                )
                continued = self._definitions["continue_operation"].handler(
                    _native_invocation("dsh:session-1:continue-to-verification", "continue_operation"),
                    {"reason": "Advance to the next declared decision event."},
                )
                assert isinstance(observation.result, dict)
                assert isinstance(verification.result, dict)
                assert isinstance(continued.result, dict)
                assert verification.result["status"] == "applied"
                assert continued.result["status"] == "applied"
            return AdapterResult(
                adapter_name="deepseek_harness",
                resolved_model="gpt-4.1-mini-standard",
                configuration_record=dict(request.configuration),
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path=request.output_path,
                    output_format=request.output_format,
                ),
                transcript=[],
                turns_used=1,
                raw_output_text=f"Segment {self._segment_index} ended.",
                usage_model_calls=1,
            )

    def build_adapter(**kwargs: object) -> FakeAdapter:
        builds.append(kwargs)
        native_tool_definitions = kwargs["native_tool_definitions"]
        assert isinstance(native_tool_definitions, tuple)
        return FakeAdapter(native_tool_definitions, len(builds) - 1)

    completed = run_pump_station_model_session(
        bridge=bridge,
        output_dir=tmp_path / "world-session",
        session_identity="host-continuation",
        model="azure:gpt-4.1-mini-standard",
        adapter_kind="deepseek_harness",
        max_tokens=4096,
        adapter_builder=build_adapter,
    )

    assert completed.segment_count == 2
    assert completed.host_control_count == 1
    assert completed.stop_reason == "actor-or-external-progress-required"
    assert completed.adapter_result.agent_output.status is AgentOutputStatus.PARTIAL
    assert completed.adapter_result.configuration_record["world_host_control_count"] == 1
    authority_record = completed.adapter_result.configuration_record["actor_invocation_authority"]
    assert authority_record["world_action_count"] == 2
    assert authority_record["close"]["complete"] is True
    actor_evidence = [
        json.loads(line)
        for line in (completed.output_dir / "actor-invocation-evidence.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    dispatches = [record for record in actor_evidence if record["record_type"] == "dispatch"]
    assert [record["action_sequence"] for record in dispatches] == [1, 2]
    repository = PumpStationWorldRunRepository(completed.output_dir / "world-run")
    run = PumpStationWorldRun.resume_reference_system(repository=repository, snapshot=repository.current_snapshot())
    assert "restriction-a-run-in-001" not in run.state.active_restriction_ids

    bounded_builds: list[dict[str, object]] = []

    def build_bounded_adapter(**kwargs: object) -> FakeAdapter:
        bounded_builds.append(kwargs)
        native_tool_definitions = kwargs["native_tool_definitions"]
        assert isinstance(native_tool_definitions, tuple)
        return FakeAdapter(native_tool_definitions, len(bounded_builds) - 1)

    bounded = run_pump_station_model_session(
        bridge=bridge,
        output_dir=tmp_path / "bounded-world-session",
        session_identity="bounded-host-continuation",
        model="azure:gpt-4.1-mini-standard",
        adapter_kind="deepseek_harness",
        max_world_actions=2,
        max_tokens=4096,
        adapter_builder=build_bounded_adapter,
    )

    assert bounded.segment_count == 1
    assert bounded.host_control_count == 0
    assert bounded.stop_reason == "max-world-actions"
    bounded_authority = bounded.adapter_result.configuration_record["actor_invocation_authority"]
    assert bounded_authority["world_action_count"] == 2


def test_model_session_preserves_adapter_failure_status(tmp_path: Path) -> None:
    exported = export_pump_station_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
        profile_ref=pump_station_continual_world_definition().profiles[0],
    )
    bridge = load_pump_station_harbor_bridge(exported.task_dir / "environment")

    class FailedAdapter:
        def execute(self, request: AdapterRequest) -> AdapterResult:
            return AdapterResult(
                adapter_name="deepseek_harness",
                resolved_model="gpt-4.1-mini-standard",
                configuration_record=dict(request.configuration),
                agent_output=AgentOutput(
                    status=AgentOutputStatus.FAILED,
                    output_path=request.output_path,
                    output_format=request.output_format,
                ),
                transcript=[],
                raw_output_text="The model request failed.",
            )

    completed = run_pump_station_model_session(
        bridge=bridge,
        output_dir=tmp_path / "world-session",
        session_identity="failed-adapter",
        model="azure:gpt-4.1-mini-standard",
        adapter_kind="deepseek_harness",
        max_tokens=4096,
        adapter_builder=lambda **_: FailedAdapter(),
    )

    assert completed.segment_count == 1
    assert completed.stop_reason == "adapter-failed"
    assert completed.adapter_result.agent_output.status is AgentOutputStatus.FAILED


def test_registered_profile_runs_through_the_real_local_harbor_entrypoint(
    tmp_path: Path,
) -> None:
    catalogue = default_interactive_world_catalogue()
    definition = catalogue.get(PUMP_STATION_TASK_WORLD_ID)
    assert definition is pump_station_continual_world_definition()
    profile_ref = definition.profiles[0]
    exported = export_pump_station_harbor_task(
        tmp_path / "task",
        project_root=PROJECT_ROOT,
        profile_ref=profile_ref,
    )
    trial_name = "registered-pump-world"
    config = TrialConfig.model_validate(
        {
            "task": {"path": str(exported.task_dir)},
            "trial_name": trial_name,
            "trials_dir": str(tmp_path / "trials"),
            "job_id": "3fa79cba-6a9c-4f65-972e-e2bf245f2e9b",
            "agent": {
                "name": "pump-station-reference-controller",
                "import_path": "agents.entrypoint_agent:EntrypointAgent",
                "model_name": PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
                "kwargs": {
                    "adapter": "tool_loop",
                    "execution_kind": PUMP_STATION_HARBOR_EXECUTION_KIND,
                    "world_session": {"bridge_mode": PUMP_STATION_HARBOR_BRIDGE_MODE},
                },
            },
            "environment": {
                "import_path": "tests.support.harbor_local_environment:LocalFilesystemHarborEnvironment",
                "delete": False,
                "kwargs": {"compute_backend": "local"},
            },
            "artifacts": [
                {
                    "source": "/workspace/world-session",
                    "destination": "agent/world-session",
                },
                {
                    "source": "/workspace/output.md",
                    "destination": "agent/output.md",
                },
            ],
        }
    )

    result = asyncio.run(run_harbor_trial(config))

    assert result.exception_info is None
    assert result.agent_result is not None
    assert result.agent_result.metadata["world_session_status"] == "completed"
    assert result.agent_result.metadata["world_session_id"] == "episode.registered-pump-world"
    assert result.verifier_result is not None
    assert result.verifier_result.rewards == {"reward": 1.0}
