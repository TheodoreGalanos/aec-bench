# ABOUTME: Tests for the backend-side execution entrypoint in aec-bench Python.
# ABOUTME: Covers dispatch from serialized bundles to direct, tool-loop, RLM, and lambda-RLM.

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aec_bench.adapters.base import AdapterResult, SerializedAdapterExecution
from aec_bench.adapters.direct import DirectCompletionResponse, ReplayDirectClient
from aec_bench.adapters.direct_providers import BedrockDirectClient
from aec_bench.adapters.tool_loop import (
    ReplayToolLoopClient,
    ToolLoopCompletionResponse,
)
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.provider_broker import (
    ProviderBrokerCallPlane,
    ProviderBrokerReceipt,
    ProviderBrokerStatus,
)
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.trajectory import MetaHarnessTrajectoryContext, read_trajectory
from aec_bench.harness import execution_entrypoint as execution_entrypoint_module
from aec_bench.harness.execution_entrypoint import (
    default_execution_driver_registry,
    run_execution_bundle,
)
from aec_bench.harness.execution_payload import (
    AdapterRequestPayload,
    ExecutionBundle,
    read_execution_result,
    write_execution_bundle,
)


def _meta_harness_context() -> dict[str, object]:
    return {
        "kernel_ref": {"kernel_id": "kernel.fixed", "version": "1"},
        "harness_ref": {"instance_id": "hx-review"},
        "program_ref": {"program_id": "px-review", "version": "1"},
        "plan_run_id": "bundle-review",
        "program_node_id": "node.review",
        "binding_ids": ["binding.agent", "binding.tools"],
        "repair_iteration": 2,
        "attempt": 1,
        "motif_ids": ["motif.decompose"],
    }


def _assert_execution_events_have_meta_harness_lineage(
    trajectory_path: Path,
    expected_payload: dict[str, object],
) -> None:
    expected = MetaHarnessTrajectoryContext.model_validate(expected_payload)
    execution_entries = [entry for entry in read_trajectory(trajectory_path) if entry.step > 0]

    assert execution_entries
    assert all(entry.meta_harness == expected for entry in execution_entries)
    assert execution_entries[0].meta_harness is not None
    assert execution_entries[0].meta_harness.program_node_id == "node.review"
    assert execution_entries[0].meta_harness.binding_ids == ("binding.agent", "binding.tools")
    assert execution_entries[0].meta_harness.harness_ref.instance_id == "hx-review"
    assert execution_entries[0].meta_harness.program_ref.program_id == "px-review"
    assert execution_entries[0].meta_harness.plan_run_id == "bundle-review"


def test_execution_entrypoint_runs_direct_bundle_and_writes_result(
    tmp_path: Path,
) -> None:
    bundle_path = write_execution_bundle(
        path=tmp_path / "bundle.json",
        bundle=ExecutionBundle(
            execution=SerializedAdapterExecution(
                adapter_kind="direct",
                adapter_name="direct",
                resolved_model="gpt-5.4",
                payload={
                    "client": ReplayDirectClient(
                        response=DirectCompletionResponse(
                            output_text='{"findings": []}',
                        )
                    )
                    .serialize_client()
                    .__dict__
                },
            ),
            request=AdapterRequestPayload(
                instruction="Review the task.",
                system_prompt=None,
                tools=[],
                configuration={},
                output_path="/workspace/output.jsonl",
                output_format="jsonl",
            ),
        ),
    )

    result_path = run_execution_bundle(
        bundle_path=bundle_path,
        result_path=tmp_path / "result.json",
        registry=default_execution_driver_registry(workspace_dir=tmp_path),
    )
    result = read_execution_result(result_path)

    assert result.adapter_name == "direct"
    assert result.raw_output_text == '{"findings": []}'


def test_execution_entrypoint_materializes_raw_output_text(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    bundle_path = write_execution_bundle(
        path=tmp_path / "bundle.json",
        bundle=ExecutionBundle(
            execution=SerializedAdapterExecution(
                adapter_kind="direct",
                adapter_name="direct",
                resolved_model="replay-direct",
                payload={
                    "client": ReplayDirectClient(
                        response=DirectCompletionResponse(
                            output_text='## Answer\n\n```json\n{"reward": 1.0}\n```',
                        )
                    )
                    .serialize_client()
                    .__dict__
                },
            ),
            request=AdapterRequestPayload(
                instruction="Solve the task.",
                system_prompt=None,
                tools=[],
                configuration={},
                output_path=str(output_path),
                output_format="markdown",
            ),
        ),
    )

    run_execution_bundle(
        bundle_path=bundle_path,
        result_path=tmp_path / "result.json",
        registry=default_execution_driver_registry(workspace_dir=tmp_path),
    )

    assert output_path.read_text(encoding="utf-8") == '## Answer\n\n```json\n{"reward": 1.0}\n```'


def test_direct_execution_emits_program_node_lineage_trajectory(tmp_path: Path) -> None:
    context = _meta_harness_context()
    output_path = tmp_path / "output.md"
    bundle_path = write_execution_bundle(
        path=tmp_path / "bundle.json",
        bundle=ExecutionBundle(
            execution=SerializedAdapterExecution(
                adapter_kind="direct",
                adapter_name="entrypoint",
                resolved_model="replay-direct",
                payload={
                    "client": ReplayDirectClient(response=DirectCompletionResponse(output_text="done"))
                    .serialize_client()
                    .__dict__
                },
            ),
            request=AdapterRequestPayload(
                instruction="Execute the compiled node.",
                system_prompt=None,
                tools=[],
                configuration={"meta_harness_context": context},
                output_path=str(output_path),
                output_format="markdown",
            ),
        ),
    )

    run_execution_bundle(
        bundle_path=bundle_path,
        result_path=tmp_path / "result.json",
        registry=default_execution_driver_registry(workspace_dir=tmp_path),
    )

    _assert_execution_events_have_meta_harness_lineage(
        tmp_path / "trajectory.jsonl",
        context,
    )


def test_execution_entrypoint_runs_tool_loop_bundle_and_writes_result(
    tmp_path: Path,
) -> None:
    bundle_path = write_execution_bundle(
        path=tmp_path / "bundle.json",
        bundle=ExecutionBundle(
            execution=SerializedAdapterExecution(
                adapter_kind="tool_loop",
                adapter_name="tool-loop",
                resolved_model="gpt-5.4-mini",
                payload={
                    "client": ReplayToolLoopClient(
                        responses=[
                            ToolLoopCompletionResponse(
                                output_text='{"findings": []}',
                                done=True,
                            )
                        ]
                    )
                    .serialize_client()
                    .__dict__
                },
            ),
            request=AdapterRequestPayload(
                instruction="Review the task.",
                system_prompt=None,
                tools=[
                    ToolSpec(
                        name="bash",
                        source="environment/bash.sh",
                        description="Run shell commands.",
                    ).model_dump(mode="json")
                ],
                configuration={"max_turns": 4},
                output_path="/workspace/output.jsonl",
                output_format="jsonl",
            ),
        ),
    )

    result_path = run_execution_bundle(
        bundle_path=bundle_path,
        result_path=tmp_path / "result.json",
        registry=default_execution_driver_registry(workspace_dir=tmp_path),
    )
    result = read_execution_result(result_path)

    assert result.adapter_name == "tool-loop"
    assert result.raw_output_text == '{"findings": []}'


def test_execution_entrypoint_runs_pydantic_ai_alias_bundle_and_writes_result(
    tmp_path: Path,
) -> None:
    """pydantic_ai should dispatch through the same tool-loop execution driver."""
    bundle_path = write_execution_bundle(
        path=tmp_path / "bundle.json",
        bundle=ExecutionBundle(
            execution=SerializedAdapterExecution(
                adapter_kind="pydantic_ai",
                adapter_name="pydantic_ai",
                resolved_model="gpt-5.4-mini",
                payload={
                    "client": ReplayToolLoopClient(
                        responses=[
                            ToolLoopCompletionResponse(
                                output_text='{"findings": []}',
                                done=True,
                            )
                        ]
                    )
                    .serialize_client()
                    .__dict__
                },
            ),
            request=AdapterRequestPayload(
                instruction="Review the task.",
                system_prompt=None,
                tools=[],
                configuration={"max_turns": 4},
                output_path="/workspace/output.jsonl",
                output_format="jsonl",
            ),
        ),
    )

    result_path = run_execution_bundle(
        bundle_path=bundle_path,
        result_path=tmp_path / "result.json",
        registry=default_execution_driver_registry(workspace_dir=tmp_path),
    )
    result = read_execution_result(result_path)

    assert result.adapter_name == "pydantic_ai"
    assert result.raw_output_text == '{"findings": []}'


def test_execution_entrypoint_runs_direct_bundle_without_serialized_client(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Direct Harbor bundles may omit payload; the driver should derive the client from model."""

    class _StubDirectClient:
        def complete(self, request):  # noqa: ANN001
            return DirectCompletionResponse(output_text=f"model={request.model}")

    monkeypatch.setattr(
        execution_entrypoint_module,
        "_default_direct_client_for_model",
        lambda model_name: _StubDirectClient(),
    )

    bundle_path = write_execution_bundle(
        path=tmp_path / "bundle.json",
        bundle=ExecutionBundle(
            execution=SerializedAdapterExecution(
                adapter_kind="direct",
                adapter_name="direct",
                resolved_model="gpt-5.4",
                payload={},
            ),
            request=AdapterRequestPayload(
                instruction="Review the task.",
                system_prompt=None,
                tools=[],
                configuration={},
                output_path="/workspace/output.jsonl",
                output_format="jsonl",
            ),
        ),
    )

    result_path = run_execution_bundle(
        bundle_path=bundle_path,
        result_path=tmp_path / "result.json",
        registry=default_execution_driver_registry(workspace_dir=tmp_path),
    )
    result = read_execution_result(result_path)

    assert result.adapter_name == "direct"
    assert result.raw_output_text == "model=gpt-5.4"


def test_default_direct_client_uses_bedrock_for_regional_anthropic_model() -> None:
    client = execution_entrypoint_module._default_direct_client_for_model("au.anthropic.claude-sonnet-4-6")

    assert isinstance(client, BedrockDirectClient)


def test_execution_entrypoint_runs_pydantic_ai_bundle_without_serialized_client(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Pydantic-backed Harbor bundles may omit payload; the driver should build a client."""
    replay_client = ReplayToolLoopClient(
        responses=[
            ToolLoopCompletionResponse(
                output_text='{"findings": []}',
                done=True,
            )
        ]
    )

    monkeypatch.setattr(
        execution_entrypoint_module,
        "_default_tool_loop_client_for_model",
        lambda model_name, workspace_dir, *, tools: replay_client,
    )

    bundle_path = write_execution_bundle(
        path=tmp_path / "bundle.json",
        bundle=ExecutionBundle(
            execution=SerializedAdapterExecution(
                adapter_kind="pydantic_ai",
                adapter_name="pydantic_ai",
                resolved_model="gpt-5.4-mini",
                payload={},
            ),
            request=AdapterRequestPayload(
                instruction="Review the task.",
                system_prompt=None,
                tools=[],
                configuration={"max_turns": 4},
                output_path="/workspace/output.jsonl",
                output_format="jsonl",
            ),
        ),
    )

    result_path = run_execution_bundle(
        bundle_path=bundle_path,
        result_path=tmp_path / "result.json",
        registry=default_execution_driver_registry(workspace_dir=tmp_path),
    )
    result = read_execution_result(result_path)

    assert result.adapter_name == "pydantic_ai"
    assert result.raw_output_text == '{"findings": []}'


@pytest.mark.parametrize(
    ("selected_tools", "expected_bash"),
    [
        ((), False),
        (
            (
                ToolSpec(
                    name="bash",
                    source="environment/tools/bash.sh",
                    description="Execute a task-declared shell command.",
                ),
            ),
            True,
        ),
    ],
)
def test_default_tool_loop_client_exposes_only_the_selected_task_tool_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selected_tools: tuple[ToolSpec, ...],
    expected_bash: bool,
) -> None:
    captured: dict[str, object] = {}

    class _CapturedClient:
        def __init__(
            self,
            model_name: str,
            workspace: str,
            *,
            enable_bash: bool,
        ) -> None:
            captured.update(
                {
                    "model_name": model_name,
                    "workspace": workspace,
                    "enable_bash": enable_bash,
                }
            )

    monkeypatch.setattr(
        "aec_bench.adapters.tool_loop_local.PydanticAiToolLoopClient",
        _CapturedClient,
    )

    execution_entrypoint_module._default_tool_loop_client_for_model(
        "claude-test-model",
        tmp_path,
        tools=list(selected_tools),
    )

    assert captured == {
        "model_name": "claude-test-model",
        "workspace": str(tmp_path),
        "enable_bash": expected_bash,
    }


@pytest.mark.parametrize(
    ("prompt_cache", "with_advisor", "expected_cache_flags"),
    (
        (None, False, [True, False]),
        (False, False, [False, False]),
        (False, True, [False, False, False]),
    ),
)
def test_execution_entrypoint_runs_rlm_bundle_and_writes_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prompt_cache: bool | None,
    with_advisor: bool,
    expected_cache_flags: list[bool],
) -> None:
    """RLM driver should execute the exact compiled prompt and task workspace."""
    from aec_bench.adapters.rlm.client import RlmCompletionResponse

    class CapturingRlmClient:
        def __init__(self) -> None:
            self.system_prompts: list[str | None] = []

        def generate(self, *, model, messages, system_prompt, temperature=None):  # noqa: ANN001
            del model, messages, temperature
            self.system_prompts.append(system_prompt)
            return RlmCompletionResponse(
                output_text="```repl\nFINAL_VAR(TASK_SENTINEL)\n```",
                input_tokens=10,
                output_tokens=20,
            )

    (tmp_path / "repl_commands.py").write_text(
        "# ABOUTME: Provides a task-local command used by the execution-entrypoint test.\n"
        "# ABOUTME: Proves the compiled RLM workspace reaches the adapter.\n"
        "def init_commands(*, repl_env, **_kwargs):\n"
        "    repl_env.inject_object('TASK_SENTINEL', 'result: done', protected=True)\n",
        encoding="utf-8",
    )
    if with_advisor:
        (tmp_path / "rlm.toml").write_text(
            '[template]\ntier = "flat"\n\n[advisor]\nmodel = "claude-advisor-test"\n',
            encoding="utf-8",
        )
    capturing_client = CapturingRlmClient()
    cache_flags: list[bool] = []
    meta_harness_context = _meta_harness_context()

    def build_rlm_client(_model_name: str, *, cache: bool = True) -> CapturingRlmClient:
        cache_flags.append(cache)
        return capturing_client

    monkeypatch.setattr(
        execution_entrypoint_module,
        "make_rlm_client",
        build_rlm_client,
    )
    configuration: dict[str, object] = {"meta_harness_context": meta_harness_context}
    if prompt_cache is not None:
        configuration["prompt_cache"] = prompt_cache
    bundle_path = write_execution_bundle(
        path=tmp_path / "bundle.json",
        bundle=ExecutionBundle(
            execution=SerializedAdapterExecution(
                adapter_kind="rlm",
                adapter_name="rlm",
                resolved_model="claude-sonnet-4-20250514",
                payload={},
            ),
            request=AdapterRequestPayload(
                instruction="Calculate voltage drop.",
                system_prompt="Apply the compiled task-specific review policy.",
                tools=[],
                configuration=configuration,
                output_path="/workspace/output.md",
                output_format="markdown",
            ),
        ),
    )

    result_path = run_execution_bundle(
        bundle_path=bundle_path,
        result_path=tmp_path / "result.json",
        registry=default_execution_driver_registry(workspace_dir=tmp_path),
    )
    result = read_execution_result(result_path)

    assert result.adapter_name == "rlm"
    assert cache_flags == expected_cache_flags
    assert result.raw_output_text == "```repl\nFINAL_VAR(TASK_SENTINEL)\n```"
    assert all(entry.content is None or "NameError" not in entry.content for entry in result.transcript)
    assert capturing_client.system_prompts
    assert capturing_client.system_prompts[0] is not None
    assert "Apply the compiled task-specific review policy." in capturing_client.system_prompts[0]
    _assert_execution_events_have_meta_harness_lineage(
        tmp_path / "trajectory.jsonl",
        meta_harness_context,
    )


def test_execution_entrypoint_wires_broker_planes_to_rlm_call_roles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The broker main plane serves turns while every nested call uses auxiliary."""
    from aec_bench.adapters.rlm import initialiser as rlm_initialiser

    model = "bedrock:anthropic.claude-sonnet-test"
    now = datetime.now(UTC)
    receipt = ProviderBrokerReceipt(
        broker_id="broker.wiring",
        policy_sha256="a" * 64,
        status=ProviderBrokerStatus.COMPLETED,
        calls=(),
        denied_calls=0,
        total_calls=0,
        total_input_tokens=0,
        total_output_tokens=0,
        total_cache_read_tokens=0,
        total_cache_write_tokens=0,
        total_cost_usd=0.0,
        started_at=now,
        finished_at=now,
    )

    class PlaneClient:
        def __init__(self, plane: ProviderBrokerCallPlane) -> None:
            self.call_plane = plane
            self.finalize_count = 0
            self.siblings: list[PlaneClient] = []

        def for_call_plane(
            self,
            plane: ProviderBrokerCallPlane,
        ) -> "PlaneClient":
            sibling = PlaneClient(plane)
            self.siblings.append(sibling)
            return sibling

        def finalize(self) -> ProviderBrokerReceipt:
            self.finalize_count += 1
            return receipt

    main_client = PlaneClient(ProviderBrokerCallPlane.MAIN)
    monkeypatch.setattr(
        execution_entrypoint_module.BrokeredRlmClient,
        "from_environment",
        classmethod(lambda cls: main_client),
    )
    captured: dict[str, object] = {}
    adapter_result = AdapterResult(
        adapter_name="rlm",
        resolved_model=model,
        configuration_record={},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path=str(tmp_path / "output.md"),
            output_format="markdown",
        ),
        transcript=[],
        raw_output_text="done",
    )

    def build_adapter(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(execute=lambda _request: adapter_result)

    monkeypatch.setattr(rlm_initialiser, "build_rlm_adapter", build_adapter)
    (tmp_path / "rlm.toml").write_text(
        (f'[template]\ntier = "flat"\n\n[advisor]\nmodel = "{model}"\nenabled = true\n'),
        encoding="utf-8",
    )
    bundle = ExecutionBundle(
        execution=SerializedAdapterExecution(
            adapter_kind="rlm",
            adapter_name="rlm",
            resolved_model=model,
            payload={},
        ),
        request=AdapterRequestPayload(
            instruction="Run one broker-wired task.",
            system_prompt=None,
            tools=[],
            configuration={},
            output_path=str(tmp_path / "output.md"),
            output_format="markdown",
        ),
    )

    result = execution_entrypoint_module.RlmExecutionDriver(
        workspace_dir=tmp_path,
    ).execute(bundle)

    assert len(main_client.siblings) == 1
    auxiliary_client = main_client.siblings[0]
    assert main_client.call_plane is ProviderBrokerCallPlane.MAIN
    assert auxiliary_client.call_plane is ProviderBrokerCallPlane.AUXILIARY
    assert captured["client"] is main_client
    assert captured["subcall_client"] is auxiliary_client
    assert captured["compaction_client"] is auxiliary_client
    assert captured["advisor_client"] is auxiliary_client
    assert main_client.finalize_count == 1
    assert result.configuration_record["provider_broker"]["receipt"] == receipt.model_dump(
        mode="json",
    )


def test_execution_entrypoint_roundtrips_an_explicit_output_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real RLM driver should persist evidence for the exact committed artifact."""
    from aec_bench.adapters.rlm.client import RlmCompletionResponse

    output_path = tmp_path / "output.md"
    output_text = '# Review\n\n```json\n{"summary": {"status": "complete"}}\n```\n'

    class CommitRlmClient:
        def generate(self, *, model, messages, system_prompt, temperature=None):  # noqa: ANN001
            del model, messages, system_prompt, temperature
            return RlmCompletionResponse(
                output_text=(f"```repl\nopen({str(output_path)!r}, 'w').write({output_text!r})\nCOMMIT_OUTPUT()\n```"),
                input_tokens=10,
                output_tokens=20,
            )

    monkeypatch.setattr(
        execution_entrypoint_module,
        "make_rlm_client",
        lambda _model_name, *, cache=True: CommitRlmClient(),
    )
    contract = {
        "schema_version": "aecbench.output-completion-contract.v1",
        "output_path": str(output_path),
        "format": "markdown_final_fenced_json",
        "required_top_level_keys": ["summary"],
        "require_single_final_json_block": True,
    }
    bundle_path = write_execution_bundle(
        path=tmp_path / "commit-bundle.json",
        bundle=ExecutionBundle(
            execution=SerializedAdapterExecution(
                adapter_kind="rlm",
                adapter_name="rlm",
                resolved_model="claude-sonnet-4-20250514",
                payload={},
            ),
            request=AdapterRequestPayload(
                instruction="Write and commit the final review artifact.",
                system_prompt=None,
                tools=[],
                configuration={
                    "output_completion_contract": contract,
                    "output_completion_commit": True,
                    "prompt_cache": False,
                },
                output_path=str(output_path),
                output_format="markdown",
            ),
        ),
    )

    result_path = run_execution_bundle(
        bundle_path=bundle_path,
        result_path=tmp_path / "commit-result.json",
        registry=default_execution_driver_registry(workspace_dir=tmp_path),
    )
    result = read_execution_result(result_path)

    assert result.completion_reason is not None
    assert result.completion_reason.value == "output_contract_committed"
    assert result.completion_commit is not None
    assert result.completion_commit.output_sha256 == hashlib.sha256(output_text.encode()).hexdigest()
    assert result.completion_commit.output_size_bytes == len(output_text.encode())
    assert result.completion_commit.commit_turn == 1
    assert output_path.read_text(encoding="utf-8") == output_text


_LAMBDA_RLM_CONFIG_TOML = """
[template]
tier = "dependency_tree"
definition = "report_template.toml"

[review]
enabled = false
"""

_LAMBDA_RLM_TEMPLATE_TOML = """
[[sections]]
id = "background"
title = "Background"
depends_on = []
generation_mode = "transform"
writing_guidance = ["Carry language verbatim"]
input_mapping = ["brief:Description"]

[[sections.fields]]
name = "context"
dtype = "str"
"""


def test_execution_entrypoint_runs_lambda_rlm_bundle_and_writes_result(
    tmp_path: Path,
) -> None:
    """Lambda-RLM driver should build a LambdaRlmAdapter and execute the full pipeline."""
    import json
    from unittest.mock import patch

    from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse

    # Set up workspace with config and template files
    (tmp_path / "lambda-rlm.toml").write_text(_LAMBDA_RLM_CONFIG_TOML)
    (tmp_path / "report_template.toml").write_text(_LAMBDA_RLM_TEMPLATE_TOML)
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir()
    (docs_dir / "brief.md").write_text("Princes Highway project brief.")

    replay_client = ReplayRlmClient(
        responses=[
            # extract phase for "background"
            RlmCompletionResponse(
                output_text=json.dumps({"context": "Princes Highway"}),
                input_tokens=300,
                output_tokens=80,
            ),
            # generate phase for "background" (review disabled)
            RlmCompletionResponse(
                output_text="The project is located on Princes Highway.",
                input_tokens=400,
                output_tokens=100,
            ),
        ]
    )
    meta_harness_context = _meta_harness_context()

    with patch(
        "aec_bench.harness.execution_entrypoint.make_rlm_client",
        return_value=replay_client,
    ):
        bundle_path = write_execution_bundle(
            path=tmp_path / "bundle.json",
            bundle=ExecutionBundle(
                execution=SerializedAdapterExecution(
                    adapter_kind="lambda_rlm",
                    adapter_name="lambda-rlm",
                    resolved_model="claude-sonnet-4-20250514",
                    payload={},
                ),
                request=AdapterRequestPayload(
                    instruction="Write the proposal.",
                    system_prompt=None,
                    tools=[],
                    configuration={"meta_harness_context": meta_harness_context},
                    output_path="/workspace/output.md",
                    output_format="markdown",
                ),
            ),
        )

        result_path = run_execution_bundle(
            bundle_path=bundle_path,
            result_path=tmp_path / "result.json",
            registry=default_execution_driver_registry(workspace_dir=tmp_path),
        )
        result = read_execution_result(result_path)

        assert result.adapter_name == "lambda-rlm"
        assert result.raw_output_text is not None
        assert len(result.raw_output_text) > 0
        _assert_execution_events_have_meta_harness_lineage(
            tmp_path / "trajectory.jsonl",
            meta_harness_context,
        )


@pytest.mark.parametrize("adapter_kind", ["rlm", "lambda_rlm"])
def test_recursive_execution_drivers_fail_closed_on_invalid_meta_harness_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    adapter_kind: str,
) -> None:
    invalid_context = _meta_harness_context()
    del invalid_context["program_node_id"]
    bundle = ExecutionBundle(
        execution=SerializedAdapterExecution(
            adapter_kind=adapter_kind,
            adapter_name=adapter_kind,
            resolved_model="claude-sonnet-4-20250514",
            payload={},
        ),
        request=AdapterRequestPayload(
            instruction="Execute one compiled program node.",
            system_prompt=None,
            tools=[],
            configuration={"meta_harness_context": invalid_context},
            output_path="/workspace/output.md",
            output_format="markdown",
        ),
    )

    def fail_if_client_is_built(*args: object, **kwargs: object) -> None:
        raise AssertionError("invalid lineage must be rejected before client construction")

    monkeypatch.setattr(execution_entrypoint_module, "make_rlm_client", fail_if_client_is_built)

    with pytest.raises(ValidationError, match="program_node_id"):
        default_execution_driver_registry(workspace_dir=tmp_path).resolve(adapter_kind).execute(bundle)

    assert not (tmp_path / "trajectory.jsonl").exists()


def test_recursive_execution_writer_preserves_legacy_events_without_lineage(tmp_path: Path) -> None:
    writer = execution_entrypoint_module._build_trajectory_writer(
        workspace_dir=tmp_path,
        configuration={},
    )
    writer.new_step()
    writer.thinking("Execute a legacy run without a compiled meta-harness bundle.")
    writer.close()

    entries = read_trajectory(tmp_path / "trajectory.jsonl")

    assert len(entries) == 1
    assert entries[0].meta_harness is None


def test_default_execution_registry_exposes_documented_adapter_aliases(
    tmp_path: Path,
) -> None:
    """Execution registry should accept the adapter names exposed to users."""
    registry = default_execution_driver_registry(workspace_dir=tmp_path)

    assert registry.resolve("lambda-rlm") is registry.resolve("lambda_rlm")
    assert registry.resolve("pydantic_ai") is registry.resolve("tool_loop")
