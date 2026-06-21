# ABOUTME: Tests for the post-verifier LLM reviewer artifact contract.
# ABOUTME: Exercises request construction and provider-error persistence without fake model output.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.evaluation.llm_reviewer import (
    ReviewerEndpointConfig,
    ReviewerRunConfig,
    _build_model_reference,
    build_workspace_review_request,
    load_reviewer_config,
    run_workspace_reviewer,
)


def test_build_workspace_review_request_captures_verifier_and_artifact_evidence(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "task"
    workspace = tmp_path / "workspace"
    verifier_dir = workspace / "logs" / "verifier"
    task_dir.mkdir()
    verifier_dir.mkdir(parents=True)
    (task_dir / "instruction.md").write_text("Calculate the retaining wall checks.", encoding="utf-8")
    (task_dir / "world.yaml").write_text(
        """
world_id: aecbench.retaining_wall.review
name: Retaining wall calculation review
task_unit: Calculate and verify retaining wall checks.
logic_profile:
  closure_gates:
    - id: verifier_reward_available
      evidence_key: verifier.reward
      expected: present
      authority: verifier_artifact
      failure_effect: review_blocked
  construction_gates: []
  containment_gates: []
  event_triggers: []
  agentic_review:
    required: true
    review_modes:
      - verifier_result
      - output_artifacts
operation_profile:
  subset_axes:
    - calculation_fields
  difference_axes:
    - artifact_channel
  projection_axes:
    - verifier_authority
  product_axes:
    - task_family
  extension_policy: Promote verifier/artifact disagreements into repair candidates.
""".strip(),
        encoding="utf-8",
    )
    (workspace / "output.md").write_text("The answer is complete.", encoding="utf-8")
    (workspace / "agent_result.json").write_text(
        json.dumps({"status": "completed", "model": "solver-model"}),
        encoding="utf-8",
    )
    (verifier_dir / "reward.json").write_text(json.dumps({"reward": 0.0}), encoding="utf-8")
    (verifier_dir / "details.json").write_text(
        json.dumps({"calculation_fields": {"score": 0.0}}),
        encoding="utf-8",
    )
    (workspace / "rewrite_integrity_report.json").write_text(
        json.dumps({"artifact_preserved": True}),
        encoding="utf-8",
    )

    request = build_workspace_review_request(task_dir=task_dir, workspace_dir=workspace)

    assert request.payload["verifier"]["reward"]["reward"] == 0.0
    assert request.payload["verifier"]["details"]["calculation_fields"]["score"] == 0.0
    assert request.payload["world"]["world_id"] == "aecbench.retaining_wall.review"
    assert request.payload["deterministic_evaluation"]["overall_status"] == "invalid"
    assert request.payload["deterministic_evaluation"]["closure_results"][0]["actual"] == {"reward": 0.0}
    assert request.payload["logic_profile"]["agentic_review"]["review_modes"] == [
        "verifier_result",
        "output_artifacts",
    ]
    assert "rewrite_integrity_report.json" in request.payload["artifacts"]["root_json"]
    assert "Do not invent evidence" in request.system_prompt


def test_run_workspace_reviewer_writes_provider_error_without_fake_review(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "task"
    workspace = tmp_path / "workspace"
    task_dir.mkdir()
    workspace.mkdir()
    (task_dir / "instruction.md").write_text("Do the task.", encoding="utf-8")
    (workspace / "output.md").write_text("Done.", encoding="utf-8")

    result = run_workspace_reviewer(
        task_dir=task_dir,
        workspace_dir=workspace,
        config=ReviewerRunConfig(
            enabled=True,
            models=[
                ReviewerEndpointConfig(
                    name="missing-compatible-endpoint",
                    model="reviewer",
                    provider="openai_compatible",
                )
            ],
            fail_on_error=False,
        ),
    )

    reviewer_dir = workspace / "logs" / "reviewer"
    error_path = reviewer_dir / "missing-compatible-endpoint" / "error.json"
    summary = json.loads((reviewer_dir / "summary.json").read_text(encoding="utf-8"))

    assert result.status == "error"
    assert (reviewer_dir / "request.json").exists()
    assert (reviewer_dir / "world_profile.json").exists()
    assert error_path.exists()
    assert "base_url" in json.loads(error_path.read_text(encoding="utf-8"))["error"]
    assert summary["status"] == "error"
    assert "review" not in json.loads(error_path.read_text(encoding="utf-8"))


def test_load_reviewer_config_supports_multiple_model_endpoints(tmp_path: Path) -> None:
    config_path = tmp_path / "reviewer.json"
    config_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "required": True,
                "models": [
                    {"name": "primary", "model": "openai:gpt-5.2"},
                    {
                        "name": "local",
                        "model": "reviewer",
                        "provider": "openai_compatible",
                        "base_url": "http://localhost:11434/v1",
                        "api_key_env": "LOCAL_REVIEWER_API_KEY",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    config = load_reviewer_config(config_path)

    assert config.enabled is True
    assert [model.name for model in config.models] == ["primary", "local"]
    assert config.models[1].provider == "openai_compatible"


def test_reviewer_azure_endpoint_uses_shared_model_router() -> None:
    endpoint = ReviewerEndpointConfig(name="azure", model="deployment", provider="azure")

    try:
        _build_model_reference(endpoint)
    except RuntimeError as exc:
        assert "AZURE_OPENAI_ENDPOINT" in str(exc)
    else:
        raise AssertionError("azure reviewer endpoint should not fall through to a raw model string")
