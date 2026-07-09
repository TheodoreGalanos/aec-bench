# ABOUTME: Tests meta-harness model runner contracts inside AEC-Bench.
# ABOUTME: Covers endpoint parsing, provider-safe run plans, and structured output coercion.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_bench.meta_harness.model_runner import (
    ModelEndpoint,
    build_intake_model_run_plan,
    build_operation_model_run_plan,
    build_review_model_run_plan,
    build_world_generation_model_run_plan,
    coerce_operation_plan_output,
    coerce_problem_space_brief_output,
    coerce_world_generation_output,
    estimate_model_cost,
    load_model_endpoints,
    parse_model_endpoint,
)


def test_parse_and_load_model_endpoints_keep_secrets_out_of_public_dict(tmp_path: Path) -> None:
    config_path = tmp_path / "models.json"
    config_path.write_text(
        json.dumps(
            {
                "models": [
                    "openai:gpt-5.2",
                    {
                        "name": "local",
                        "model": "planner",
                        "provider": "openai_compatible",
                        "base_url": "http://localhost:11434/v1",
                        "api_key": "secret-value",
                        "api_key_env": "LOCAL_API_KEY",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    endpoint = parse_model_endpoint(
        "name=planner,model=planner-model,provider=openai_compatible,"
        "base_url=http://localhost:4000/v1,api_key_env=LOCAL_KEY,temperature=0.2,max_tokens=1200"
    )
    endpoints = load_model_endpoints(config_path)
    public = endpoints[1].to_public_dict()

    assert endpoint.name == "planner"
    assert endpoint.temperature == 0.2
    assert endpoint.max_tokens == 1200
    assert [item.name for item in endpoints] == ["openai:gpt-5.2", "local"]
    assert public["api_key_present"] is True
    assert "api_key" not in public


def test_model_run_plans_summarize_without_full_prompts() -> None:
    endpoints = [ModelEndpoint(name="primary", model="openai:gpt-5.2")]
    world = _world()
    brief = _brief()

    review_plan = build_review_model_run_plan(world, {"run_id": "run.demo", "evidence": {}}, endpoints)
    intake_plan = build_intake_model_run_plan(
        task_text="Create a diagnostic task.",
        attachments=[{"path": "runs/result.json", "kind": "run_artifact"}],
        endpoints=endpoints,
        process_id="process.demo",
    )
    world_plan = build_world_generation_model_run_plan(
        brief=brief,
        source_world=world,
        governance_directive={"target": "world_schema"},
        endpoints=endpoints,
        process_id="process.demo",
    )
    operation_plan = build_operation_model_run_plan(
        brief=brief,
        worlds=[world],
        endpoints=endpoints,
        allowed_operations=["projection", "difference"],
    )

    assert review_plan["deterministic_status"] == "review_required"
    assert intake_plan["task_text_preview"] == "Create a diagnostic task."
    assert world_plan["source_world_id"] == "world.base"
    assert world_plan["governance_target"] == "world_schema"
    assert operation_plan["environment_id"] == "operation_orchestrator"
    assert operation_plan["allowed_operations"] == ["projection", "difference"]
    assert "user_prompt" not in review_plan
    assert "user_prompt" not in intake_plan
    assert "user_prompt" not in world_plan
    assert "user_prompt" not in operation_plan


def test_model_runner_coerces_structured_outputs_and_rejects_invalid_payloads() -> None:
    operation_plan = {
        "plan_id": "plan.demo",
        "objective": "Demo",
        "steps": [
            {
                "id": "project_artifacts",
                "kind": "deterministic_operation",
                "world_ref": "world.base",
                "operation": {"operation": "projection", "axis": "artifact_evidence"},
            }
        ],
        "acceptance_checks": ["operation history exists"],
    }

    assert coerce_problem_space_brief_output({"problem_space_brief": _brief()})["brief_id"] == "brief.demo"
    assert coerce_world_generation_output({"world": _world()})["world"]["world_id"] == "world.base"
    assert coerce_operation_plan_output({"operation_plan": operation_plan})["plan_id"] == "plan.demo"

    with pytest.raises(RuntimeError, match="invalid problem_space_brief"):
        coerce_problem_space_brief_output({"problem_space_brief": {"brief_id": ""}})
    with pytest.raises(RuntimeError, match="invalid world generation response"):
        coerce_world_generation_output({"world": {"world_id": ""}})
    with pytest.raises(RuntimeError, match="invalid operation plan"):
        coerce_operation_plan_output({"operation_plan": {"plan_id": "", "steps": []}})


def test_model_runner_estimates_cost_from_endpoint_pricing() -> None:
    endpoint = ModelEndpoint(
        name="priced",
        model="openai:gpt-5.2",
        input_cost_per_million=2.0,
        output_cost_per_million=8.0,
        cache_read_cost_per_million=0.5,
        cache_write_cost_per_million=1.0,
        request_cost=0.01,
    )

    cost = estimate_model_cost(
        endpoint,
        {
            "input_tokens": 1_000_000,
            "output_tokens": 500_000,
            "cache_read_tokens": 200_000,
            "cache_write_tokens": 100_000,
            "requests": 2,
        },
    )

    assert cost == {
        "currency": "USD",
        "estimated_cost_usd": 6.22,
        "pricing_source": "endpoint_config",
    }


def _brief() -> dict:
    return {
        "brief_id": "brief.demo",
        "objective": "Create diagnostic variants.",
        "task_request": "Create a diagnostic task.",
        "evidence_requirements": ["preserve verifier artifacts"],
    }


def _world() -> dict:
    return {
        "world_id": "world.base",
        "name": "Base World",
        "task_unit": "Complete a calculation.",
        "logic_profile": {
            "closure_gates": [],
            "construction_gates": [],
            "containment_gates": [],
            "agentic_review": {"required": True},
        },
        "operation_profile": {
            "projection_axes": ["artifact_evidence"],
            "difference_axes": ["artifact_evidence"],
        },
        "operation_handles": {"artifact_evidence": {"paths": ["evidence_profile.artifacts"]}},
        "evidence_profile": {"artifacts": ["logs/verifier/details.json"]},
    }
