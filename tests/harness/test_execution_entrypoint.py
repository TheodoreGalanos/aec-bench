# ABOUTME: Tests for the backend-side execution entrypoint in aec-bench Python.
# ABOUTME: Covers dispatch from serialized bundles to direct, tool-loop, RLM, and lambda-RLM.

from pathlib import Path

from aec_bench.adapters.base import SerializedAdapterExecution
from aec_bench.adapters.direct import DirectCompletionResponse, ReplayDirectClient
from aec_bench.adapters.tool_loop import (
    ReplayToolLoopClient,
    ToolLoopCompletionResponse,
)
from aec_bench.contracts.task_definition import ToolSpec
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


def test_execution_entrypoint_runs_rlm_bundle_and_writes_result(tmp_path: Path) -> None:
    """RLM driver should build an RlmAdapter from the bundle and execute it."""
    from unittest.mock import patch

    from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse

    replay_client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text="```repl\nFINAL_VAR('result: done')\n```",
                input_tokens=10,
                output_tokens=20,
            ),
        ]
    )

    with patch(
        "aec_bench.harness.execution_entrypoint.make_rlm_client",
        return_value=replay_client,
    ):
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
                    system_prompt=None,
                    tools=[],
                    configuration={},
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
        assert result.raw_output_text == "```repl\nFINAL_VAR('result: done')\n```"


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
                    configuration={},
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
