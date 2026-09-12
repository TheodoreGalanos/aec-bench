# ABOUTME: Runs the public synthetic report through task staging, both drivers, and artifact verification.
# ABOUTME: Proves public guidance and accepted report fields do not award benchmark reward.

from __future__ import annotations

import json
import runpy
import shutil
from pathlib import Path
from typing import Any

import pytest

from aec_bench.adapters.base import SerializedAdapterExecution
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.rubric import DimensionScore
from aec_bench.evaluation.rubric_scorer import score_rubric
from aec_bench.harness.execution_entrypoint import LambdaRlmExecutionDriver, RlmExecutionDriver
from aec_bench.harness.execution_payload import AdapterRequestPayload, ExecutionBundle
from aec_bench.harness.local_runtime import setup_workspace
from aec_bench.tasks.loader import load_task_definition
from aec_bench.templates.report.assets import load_report_assets

TASK = Path(__file__).parents[2] / "tasks/civil/report/synthetic-inspection"


@pytest.mark.parametrize("kind", ["rlm", "lambda-rlm"])
def test_public_example_runs_and_is_independently_scored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    task = load_task_definition(TASK, TASK.parents[2])
    assert task.task_id == "civil/report/synthetic-inspection"
    workspace = Path(setup_workspace(str(TASK), work_root=tmp_path))
    assert not (workspace / "tests").exists()
    text = "inspection recorded 12 items."
    responses = (
        [
            RlmCompletionResponse(
                output_text=(
                    '```repl\nFILL("findings", {"text": "' + text + '"})\n'
                    'FILL("summary", {"text": "' + text + '"})\nSUBMIT()\nanswer="done"\nFINAL_VAR("answer")\n```'
                ),
                input_tokens=10,
                output_tokens=10,
            )
        ]
        if kind == "rlm"
        else [
            RlmCompletionResponse(output_text=json.dumps({"text": text}), input_tokens=10, output_tokens=10)
            for _ in range(3)
        ]
    )
    client = ReplayRlmClient(responses=responses)
    monkeypatch.setattr("aec_bench.harness.execution_entrypoint.make_rlm_client", lambda *args, **kwargs: client)
    driver = (
        RlmExecutionDriver(workspace_dir=workspace)
        if kind == "rlm"
        else LambdaRlmExecutionDriver(workspace_dir=workspace)
    )
    output = workspace / "output.json"
    result = driver.execute(
        ExecutionBundle(
            execution=SerializedAdapterExecution(
                adapter_kind=kind, adapter_name=kind, resolved_model="replay", payload={}
            ),
            request=AdapterRequestPayload(
                instruction=(TASK / "instruction.md").read_text(),
                system_prompt=None,
                tools=[],
                configuration={},
                output_path=str(output),
                output_format="json",
            ),
        )
    )
    assert result.agent_output.status == AgentOutputStatus.COMPLETED, result.agent_output.error_message
    report_assets = result.configuration_record["report_assets"]
    assert report_assets["template"]["sections"][0]["id"] == "findings"
    assert report_assets["rules"]
    assert report_assets["rubric"]["dimensions"][0]["id"] == "evidence"
    assert report_assets["source_ids"] == ["inspection"]
    evaluate = runpy.run_path(str(TASK / "tests/verify.py"))["evaluate"]
    details = evaluate(output.read_text())
    assert details == {"evidence": 1.0, "clarity": 1.0}
    session = load_report_assets(
        workspace / "report_template.toml",
        workspace=workspace,
        source_mapping="sources.toml",
        validation_rules="checks.toml",
    ).session
    rubric = session.rubric
    assert rubric is not None

    def reward(values: dict[str, Any]) -> float:
        return score_rubric(
            rubric=rubric,
            scores=[
                DimensionScore(
                    dimension_id=dim.id,
                    score=values[dim.id] * dim.max_score,
                    max_score=dim.max_score,
                    evidence="Independent artifact check",
                    eval_method_used="automated",
                )
                for dim in rubric.dimensions
            ],
        ).reward

    assert reward(details) == 1.0
    for sid in ("findings", "summary"):
        assert session.fill_section(sid, {"text": "inspection recorded 12 items and 99 others."}).success
    assert session.submit().complete
    wrong = json.dumps(session.submit().sections)
    assert reward(evaluate(wrong)) == pytest.approx(0.3333)
    shutil.rmtree(workspace)
