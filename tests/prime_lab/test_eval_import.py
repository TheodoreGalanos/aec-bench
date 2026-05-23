# ABOUTME: Tests importing Prime hosted eval samples into aec-bench ledger artefacts.
# ABOUTME: Verifies Prime rollouts can be analysed through the existing behavioral pipeline.

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.evaluation.behavioral import load_behavioral_trace
from aec_bench.ledger.reader import query_trial_records
from aec_bench.prime_lab.eval_import import import_prime_eval_samples

runner = CliRunner()


def _evaluation_payload() -> dict[str, object]:
    return {
        "evaluation_id": "eval-123",
        "name": "prime-smoke",
        "environment_names": ["aec_prime_50_suite"],
        "model_name": "Qwen/Qwen3.5-4B:adapter-123",
        "inference_model": "Qwen/Qwen3.5-4B:adapter-123",
        "is_hosted": True,
        "viewer_url": "https://app.primeintellect.ai/dashboard/evaluations/eval-123",
        "eval_config": {
            "num_examples": 1,
            "rollouts_per_example": 1,
            "env_args": {"split": "eval", "difficulty": "medium"},
            "sampling_args": {"max_tokens": 4096},
        },
    }


def _sample_payload() -> dict[str, object]:
    return {
        "sample_id": "hosted-7",
        "example_id": 0,
        "rollout_number": 1,
        "prompt": [
            {
                "role": "user",
                "content": "Calculate the fault current and write the answer to output.md.",
            }
        ],
        "completion": [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    json.dumps(
                        {
                            "id": "call-run",
                            "type": "function",
                            "function": {
                                "name": "run_command",
                                "arguments": json.dumps(
                                    {
                                        "command": [
                                            "python3",
                                            "/workspace/fault-current_calc.py",
                                        ],
                                        "cwd": "/workspace",
                                    }
                                ),
                            },
                        }
                    )
                ],
                "tool_call_id": "",
            },
            {
                "role": "tool",
                "content": "{'exit_code': 0, 'stdout': '{\"answer\": 42}', 'stderr': ''}",
                "tool_calls": [],
                "tool_call_id": "call-run",
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    json.dumps(
                        {
                            "id": "call-submit",
                            "type": "function",
                            "function": {
                                "name": "submit_answer",
                                "arguments": json.dumps(
                                    {
                                        "path": "output.md",
                                        "content": '# Solution\n\n```json\n{"answer": 42}\n```',
                                    }
                                ),
                            },
                        }
                    )
                ],
                "tool_call_id": "",
            },
            {
                "role": "user",
                "content": "Submitted final answer to output.md.",
                "tool_calls": [],
                "tool_call_id": "",
            },
        ],
        "reward": 1.0,
        "total_time": 12.5,
        "created_at": "2026-05-08T21:13:35.662468Z",
        "info": {
            "task_id": "generated/prime-50-suite/electrical/fault-current/example-1",
            "domain": "electrical",
            "difficulty": "medium",
            "harness_kind": "stateful_workspace",
            "dataset": {
                "name": "prime-50-suite",
                "version": "0.1.0",
                "content_hash": "abc123",
            },
            "timing": {"total_ms": 12500, "generation_ms": 12000, "scoring_ms": 500},
            "token_usage": {"input_tokens": 1000, "output_tokens": 250},
            "metrics": {
                "aec_bench_reward": 1.0,
                "num_turns": 2.0,
                "total_tool_calls": 2.0,
                "run_command_calls": 1.0,
                "submit_answer_calls": 1.0,
            },
            "stop_condition": "has_final_env_response",
            "is_completed": True,
        },
        "aec_bench_reward": 1.0,
    }


def test_import_prime_eval_samples_writes_ledger_record_and_conversation(tmp_path: Path) -> None:
    result = import_prime_eval_samples(
        evaluation=_evaluation_payload(),
        samples=[_sample_payload()],
        ledger_root=tmp_path,
    )

    assert result.experiment_id == "prime-eval-eval-123"
    assert len(result.records) == 1

    records = query_trial_records(tmp_path, experiment_id=result.experiment_id)
    assert len(records) == 1
    record = records[0]
    assert record.trial_id == "prime-eval-123-hosted-7"
    assert record.dataset_id == "prime-50-suite@0.1.0"
    assert record.agent.adapter == "prime-hosted"
    assert record.agent.model == "Qwen/Qwen3.5-4B:adapter-123"
    assert record.evaluation.reward == 1.0
    assert record.outputs.conversation_path is not None
    assert record.outputs.raw_output_path is not None
    assert record.outputs.agent_result is not None
    assert record.outputs.agent_result["submit_answer_calls"] == 1.0

    conversation_path = Path(record.outputs.conversation_path)
    assert conversation_path.exists()
    messages = [json.loads(line) for line in conversation_path.read_text().splitlines()]
    assert messages[1]["tool_calls"][0]["function"]["name"] == "run_command"

    trace = load_behavioral_trace(record)
    assistant_turns = [turn for turn in trace.turns if turn.role == "assistant"]
    assert assistant_turns[0].tool_calls[0].tool_name == "run_command"
    assert assistant_turns[0].tool_results[0].tool_name == "run_command"
    assert assistant_turns[1].tool_calls[0].tool_name == "submit_answer"


def test_import_prime_eval_samples_accepts_explicit_experiment_id(tmp_path: Path) -> None:
    result = import_prime_eval_samples(
        evaluation=_evaluation_payload(),
        samples=[_sample_payload()],
        ledger_root=tmp_path,
        experiment_id="article-prime-behavior",
    )

    assert result.experiment_id == "article-prime-behavior"
    assert (tmp_path / "article-prime-behavior" / "prime-eval-123-hosted-7.json").exists()


def test_import_prime_eval_samples_skips_duplicates_before_rewriting_artifacts(
    tmp_path: Path,
) -> None:
    first = import_prime_eval_samples(
        evaluation=_evaluation_payload(),
        samples=[_sample_payload()],
        ledger_root=tmp_path,
    )
    artifact = next(path for path in first.artifact_paths if path.name == "prime_sample.json")
    artifact.write_text("sentinel", encoding="utf-8")

    second = import_prime_eval_samples(
        evaluation=_evaluation_payload(),
        samples=[_sample_payload()],
        ledger_root=tmp_path,
    )

    assert second.records == []
    assert second.skipped_duplicates == 1
    assert artifact.read_text(encoding="utf-8") == "sentinel"


def test_import_prime_eval_command_reads_saved_json_payloads(tmp_path: Path) -> None:
    evaluation_path = tmp_path / "evaluation.json"
    samples_path = tmp_path / "samples.json"
    evaluation_path.write_text(json.dumps(_evaluation_payload()), encoding="utf-8")
    samples_path.write_text(json.dumps({"samples": [_sample_payload()]}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "import-prime-eval",
            "--evaluation-json",
            str(evaluation_path),
            "--samples-json",
            str(samples_path),
            "--ledger-root",
            str(tmp_path / "ledger"),
            "--experiment",
            "prime-json-import",
        ],
    )

    assert result.exit_code == 0, result.output
    records = query_trial_records(tmp_path / "ledger", experiment_id="prime-json-import")
    assert len(records) == 1
