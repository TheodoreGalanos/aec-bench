# ABOUTME: Runs meta-harness packets through real PydanticAI model endpoints.
# ABOUTME: Shares endpoint parsing and structured output coercion across intake, world, and operation agents.

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.adapters.pydantic_ai_runtime import (
    agent_run_output,
    run_agent_sync_with_streaming_fallback,
)
from aec_bench.meta_harness.logic_profile import evaluate_logic_profile
from aec_bench.meta_harness.operation_orchestrator import (
    OperationOrchestrationRequest,
    build_operation_orchestration_request,
    run_operation_orchestrator,
    validate_operation_plan,
)
from aec_bench.meta_harness.world_process import (
    build_problem_brief_request,
    build_world_generation_request,
    validate_problem_space_brief,
    validate_world_generation_response,
)

SUPPORTED_PROVIDERS = {
    "auto",
    "openai",
    "anthropic",
    "google",
    "azure",
    "openai_compatible",
    "together",
}
STREAM_MODES = {"never", "auto", "always"}
ENDPOINT_KEYS = {
    "name",
    "model",
    "provider",
    "base_url",
    "base_url_env",
    "api_key",
    "api_key_env",
    "api_version",
    "api_version_env",
    "temperature",
    "max_tokens",
    "stream_mode",
    "input_cost_per_million",
    "output_cost_per_million",
    "cache_read_cost_per_million",
    "cache_write_cost_per_million",
    "request_cost",
}
TOGETHER_PREFIX = "together:"
TOGETHER_BASE_URL = "https://api.together.ai/v1"


@dataclass(frozen=True)
class ModelEndpoint:
    name: str
    model: str
    provider: str = "auto"
    base_url: str | None = None
    base_url_env: str | None = None
    api_key: str | None = None
    api_key_env: str | None = None
    api_version: str | None = None
    api_version_env: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stream_mode: str = "auto"
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    cache_read_cost_per_million: float | None = None
    cache_write_cost_per_million: float | None = None
    request_cost: float | None = None

    def to_public_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "model": self.model,
            "provider": self.provider,
            "stream_mode": self.stream_mode,
        }
        for key in ("base_url", "base_url_env", "api_key_env", "api_version", "api_version_env"):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        if self.temperature is not None:
            result["temperature"] = self.temperature
        if self.max_tokens is not None:
            result["max_tokens"] = self.max_tokens
        for key in (
            "input_cost_per_million",
            "output_cost_per_million",
            "cache_read_cost_per_million",
            "cache_write_cost_per_million",
            "request_cost",
        ):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        if self.api_key:
            result["api_key_present"] = True
        return result


def parse_model_endpoint(spec: str) -> ModelEndpoint:
    text = spec.strip()
    if not text:
        raise ValueError("model endpoint spec cannot be empty")
    if text.startswith("{"):
        return endpoint_from_mapping(json.loads(text))
    if "=" not in text:
        return endpoint_from_mapping({"name": text, "model": text})

    fields: dict[str, str] = {}
    for item in text.split(","):
        if "=" not in item:
            raise ValueError(f"model endpoint field must use key=value: {item!r}")
        key, value = item.split("=", 1)
        fields[key.strip()] = value.strip()
    return endpoint_from_mapping(fields)


def load_model_endpoints(path: Path) -> list[ModelEndpoint]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    items = payload.get("models") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("model endpoint config must be a list or contain a 'models' list")

    endpoints: list[ModelEndpoint] = []
    for item in items:
        if isinstance(item, str):
            endpoints.append(parse_model_endpoint(item))
        elif isinstance(item, dict):
            endpoints.append(endpoint_from_mapping(item))
        else:
            raise ValueError("model endpoint entries must be strings or objects")
    return endpoints


def endpoint_from_mapping(mapping: dict[str, Any]) -> ModelEndpoint:
    unknown = set(mapping) - ENDPOINT_KEYS
    if unknown:
        raise ValueError(f"unknown model endpoint fields: {', '.join(sorted(unknown))}")

    model = _required_string(mapping, "model")
    name = str(mapping.get("name") or model)
    provider = str(mapping.get("provider") or "auto").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported provider: {provider}")

    stream_mode = str(mapping.get("stream_mode") or "auto").strip().lower()
    if stream_mode not in STREAM_MODES:
        raise ValueError(f"unsupported stream_mode: {stream_mode}")

    return ModelEndpoint(
        name=name,
        model=model,
        provider=provider,
        base_url=_optional_string(mapping, "base_url"),
        base_url_env=_optional_string(mapping, "base_url_env"),
        api_key=_optional_string(mapping, "api_key"),
        api_key_env=_optional_string(mapping, "api_key_env"),
        api_version=_optional_string(mapping, "api_version"),
        api_version_env=_optional_string(mapping, "api_version_env"),
        temperature=_optional_float(mapping, "temperature"),
        max_tokens=_optional_int(mapping, "max_tokens"),
        stream_mode=stream_mode,
        input_cost_per_million=_optional_float(mapping, "input_cost_per_million"),
        output_cost_per_million=_optional_float(mapping, "output_cost_per_million"),
        cache_read_cost_per_million=_optional_float(mapping, "cache_read_cost_per_million"),
        cache_write_cost_per_million=_optional_float(mapping, "cache_write_cost_per_million"),
        request_cost=_optional_float(mapping, "request_cost"),
    )


def build_review_model_run_plan(
    world: dict[str, Any],
    run: dict[str, Any],
    endpoints: list[ModelEndpoint],
) -> dict[str, Any]:
    evidence = run.get("evidence", run)
    deterministic = evaluate_logic_profile(world.get("logic_profile", {}), evidence).to_dict()
    return {
        "world_id": world.get("world_id"),
        "world_name": world.get("name"),
        "run_id": run.get("run_id"),
        "task_unit": world.get("task_unit"),
        "review_modes": world.get("logic_profile", {}).get("agentic_review", {}).get("review_modes", []),
        "deterministic_status": deterministic["overall_status"],
        "models": [endpoint.to_public_dict() for endpoint in endpoints],
    }


def run_review_models(
    world: dict[str, Any],
    run: dict[str, Any],
    endpoints: list[ModelEndpoint],
) -> dict[str, Any]:
    request = _review_request(world, run)
    results = []
    for endpoint in endpoints:
        try:
            model_result = run_review_model(request, endpoint)
            reviewed = evaluate_with_review(world, run, model_result["review"])
            results.append(model_result | {"evaluation": reviewed["evaluation"]})
        except Exception as exc:
            results.append({"endpoint": endpoint.to_public_dict(), "status": "error", "error": str(exc)})
    return {
        "run_plan": build_review_model_run_plan(world, run, endpoints),
        "results": results,
        **_aggregate_model_costs(results),
    }


def build_review_request(world: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    from aec_bench.evaluation.llm_reviewer import ReviewResponse

    request = _review_request(world, run)
    return request | {"response_schema": ReviewResponse.model_json_schema()}


def parse_review_response(response_text: str) -> dict[str, Any]:
    return _coerce_review_output(response_text)


def run_review_model(
    request: dict[str, Any],
    endpoint: ModelEndpoint,
) -> dict[str, Any]:
    from aec_bench.evaluation.llm_reviewer import ReviewResponse

    agent = _agent(
        endpoint=endpoint,
        system_prompt=request["system_prompt"],
        output_type=ReviewResponse,
    )
    result = run_agent_sync_with_streaming_fallback(agent, request["user_prompt"], stream_mode=endpoint.stream_mode)
    review = _coerce_review_output(agent_run_output(result))
    usage = _usage_dict(result)
    cost = estimate_model_cost(endpoint, usage)
    return {
        "endpoint": endpoint.to_public_dict(),
        "status": "complete",
        "review": review,
        "usage": usage,
        **({"cost": cost} if cost is not None else {}),
    }


def attach_review_to_run(run: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    updated = json.loads(json.dumps(run))
    updated.setdefault("evidence", {})["agentic_review"] = review
    return updated


def evaluate_with_review(
    world: dict[str, Any],
    run: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    updated_run = attach_review_to_run(run, review)
    evaluation = evaluate_logic_profile(world.get("logic_profile", {}), updated_run["evidence"])
    return {
        "updated_run": updated_run,
        "evaluation": evaluation.to_dict(),
    }


def build_intake_model_run_plan(
    *,
    task_text: str,
    attachments: list[dict[str, Any]] | None = None,
    endpoints: list[ModelEndpoint],
    process_id: str | None = None,
) -> dict[str, Any]:
    request = build_problem_brief_request(
        task_text=task_text,
        attachments=attachments,
        process_id=process_id,
    )
    return {
        "process_id": request["process_id"],
        "stage": request["stage"],
        "status": request["status"],
        "task_text_preview": task_text[:160],
        "attachment_count": len(attachments or []),
        "models": [endpoint.to_public_dict() for endpoint in endpoints],
        "response_schema": request["response_schema"],
    }


def run_intake_models(
    *,
    task_text: str,
    attachments: list[dict[str, Any]] | None = None,
    endpoints: list[ModelEndpoint],
    process_id: str | None = None,
) -> dict[str, Any]:
    request = build_problem_brief_request(
        task_text=task_text,
        attachments=attachments,
        process_id=process_id,
    )
    results = []
    for endpoint in endpoints:
        try:
            results.append(run_intake_model(request=request, endpoint=endpoint))
        except Exception as exc:
            results.append({"endpoint": endpoint.to_public_dict(), "status": "error", "error": str(exc)})
    return {
        "run_plan": build_intake_model_run_plan(
            task_text=task_text,
            attachments=attachments,
            endpoints=endpoints,
            process_id=request["process_id"],
        ),
        "results": results,
        **_aggregate_model_costs(results),
    }


def run_intake_model(
    *,
    request: dict[str, Any],
    endpoint: ModelEndpoint,
) -> dict[str, Any]:
    agent = _agent(
        endpoint=endpoint,
        system_prompt=request["system_prompt"],
        output_type=_problem_space_brief_output_type(),
    )
    result = run_agent_sync_with_streaming_fallback(agent, request["user_prompt"], stream_mode=endpoint.stream_mode)
    brief = coerce_problem_space_brief_output(agent_run_output(result))
    usage = _usage_dict(result)
    cost = estimate_model_cost(endpoint, usage)
    return {
        "endpoint": endpoint.to_public_dict(),
        "status": "complete",
        "problem_space_brief": brief,
        "usage": usage,
        **({"cost": cost} if cost is not None else {}),
    }


def build_world_generation_model_run_plan(
    *,
    brief: dict[str, Any],
    source_world: dict[str, Any] | None = None,
    governance_directive: dict[str, Any] | None = None,
    endpoints: list[ModelEndpoint],
    process_id: str | None = None,
) -> dict[str, Any]:
    request = build_world_generation_request(
        brief=brief,
        source_world=source_world,
        governance_directive=governance_directive,
        process_id=process_id,
    )
    payload = request["request"]["payload"]
    source_summary = payload.get("source_world") or {}
    directive = payload.get("governance_directive") or {}
    return {
        "process_id": request["process_id"],
        "stage": request["stage"],
        "status": request["status"],
        "brief_id": brief.get("brief_id"),
        "source_world_id": source_summary.get("world_id"),
        "governance_target": directive.get("target"),
        "models": [endpoint.to_public_dict() for endpoint in endpoints],
        "response_schema": request["request"]["response_schema"],
    }


def run_world_generation_models(
    *,
    brief: dict[str, Any],
    source_world: dict[str, Any] | None = None,
    governance_directive: dict[str, Any] | None = None,
    endpoints: list[ModelEndpoint],
    process_id: str | None = None,
) -> dict[str, Any]:
    request = build_world_generation_request(
        brief=brief,
        source_world=source_world,
        governance_directive=governance_directive,
        process_id=process_id,
    )
    results = []
    for endpoint in endpoints:
        try:
            results.append(run_world_generation_model(request=request, endpoint=endpoint))
        except Exception as exc:
            results.append({"endpoint": endpoint.to_public_dict(), "status": "error", "error": str(exc)})
    return {
        "run_plan": build_world_generation_model_run_plan(
            brief=brief,
            source_world=source_world,
            governance_directive=governance_directive,
            endpoints=endpoints,
            process_id=request["process_id"],
        ),
        "results": results,
        **_aggregate_model_costs(results),
    }


def run_world_generation_model(
    *,
    request: dict[str, Any],
    endpoint: ModelEndpoint,
) -> dict[str, Any]:
    request_body = request["request"]
    agent = _agent(
        endpoint=endpoint,
        system_prompt=request_body["system_prompt"],
        output_type=_world_generation_output_type(),
    )
    result = run_agent_sync_with_streaming_fallback(
        agent,
        request_body["user_prompt"],
        stream_mode=endpoint.stream_mode,
    )
    response = coerce_world_generation_output(agent_run_output(result))
    usage = _usage_dict(result)
    cost = estimate_model_cost(endpoint, usage)
    return {
        "endpoint": endpoint.to_public_dict(),
        "status": "complete",
        "world_generation_response": response,
        "usage": usage,
        **({"cost": cost} if cost is not None else {}),
    }


def build_operation_model_run_plan(
    *,
    brief: dict[str, Any],
    worlds: list[dict[str, Any]],
    endpoints: list[ModelEndpoint],
    allowed_operations: list[str] | None = None,
) -> dict[str, Any]:
    request = build_operation_orchestration_request(
        brief=brief,
        worlds=worlds,
        allowed_operations=allowed_operations,
    )
    payload = request.payload
    return {
        "brief_id": brief.get("brief_id"),
        "objective": brief.get("objective"),
        "environment_id": payload["environment"]["environment_id"],
        "world_ids": [world.get("world_id") for world in payload["worlds"]],
        "allowed_operations": payload["allowed_operations"],
        "models": [endpoint.to_public_dict() for endpoint in endpoints],
        "response_schema": request.response_schema,
    }


def run_operation_models(
    *,
    brief: dict[str, Any],
    worlds: list[dict[str, Any]],
    endpoints: list[ModelEndpoint],
    allowed_operations: list[str] | None = None,
) -> dict[str, Any]:
    request = build_operation_orchestration_request(
        brief=brief,
        worlds=worlds,
        allowed_operations=allowed_operations,
    )
    results = []
    for endpoint in endpoints:
        try:
            results.append(
                run_operation_model(
                    request=request,
                    brief=brief,
                    worlds=worlds,
                    endpoint=endpoint,
                    allowed_operations=allowed_operations,
                )
            )
        except Exception as exc:
            results.append({"endpoint": endpoint.to_public_dict(), "status": "error", "error": str(exc)})
    return {
        "run_plan": build_operation_model_run_plan(
            brief=brief,
            worlds=worlds,
            endpoints=endpoints,
            allowed_operations=allowed_operations,
        ),
        "results": results,
        **_aggregate_model_costs(results),
    }


def run_operation_model(
    *,
    request: OperationOrchestrationRequest,
    brief: dict[str, Any],
    worlds: list[dict[str, Any]],
    endpoint: ModelEndpoint,
    allowed_operations: list[str] | None = None,
) -> dict[str, Any]:
    agent = _agent(
        endpoint=endpoint,
        system_prompt=request.system_prompt,
        output_type=_operation_plan_output_type(),
    )
    result = run_agent_sync_with_streaming_fallback(agent, request.user_prompt, stream_mode=endpoint.stream_mode)
    operation_plan = coerce_operation_plan_output(
        agent_run_output(result),
        available_world_refs={world.get("world_id") for world in worlds if world.get("world_id")},
    )
    execution = run_operation_orchestrator(
        brief=brief,
        worlds=worlds,
        allowed_operations=allowed_operations,
        operation_plan=operation_plan,
    ).to_dict()
    usage = _usage_dict(result)
    cost = estimate_model_cost(endpoint, usage)
    return {
        "endpoint": endpoint.to_public_dict(),
        "status": execution["status"],
        "operation_plan": operation_plan,
        "execution": execution["execution"],
        "usage": usage,
        **({"cost": cost} if cost is not None else {}),
    }


def coerce_problem_space_brief_output(output: Any) -> dict[str, Any]:
    if isinstance(output, str):
        return coerce_problem_space_brief_output(_extract_json_payload(output))
    if hasattr(output, "model_dump"):
        return coerce_problem_space_brief_output(output.model_dump(exclude_none=True))
    if hasattr(output, "dict"):
        return coerce_problem_space_brief_output(output.dict(exclude_none=True))
    if not isinstance(output, dict):
        output_type = type(output).__name__
        raise RuntimeError(f"model returned unsupported problem brief type: {output_type}")

    brief = output.get("problem_space_brief", output)
    errors = validate_problem_space_brief(brief)
    if errors:
        raise RuntimeError("model returned invalid problem_space_brief: " + "; ".join(errors))
    return brief


def coerce_world_generation_output(output: Any) -> dict[str, Any]:
    if isinstance(output, str):
        return coerce_world_generation_output(_extract_json_payload(output))
    if hasattr(output, "model_dump"):
        return coerce_world_generation_output(output.model_dump(exclude_none=True))
    if hasattr(output, "dict"):
        return coerce_world_generation_output(output.dict(exclude_none=True))
    if not isinstance(output, dict):
        output_type = type(output).__name__
        raise RuntimeError(f"model returned unsupported world generation type: {output_type}")

    errors = validate_world_generation_response(output)
    if errors:
        raise RuntimeError("model returned invalid world generation response: " + "; ".join(errors))
    return output


def coerce_operation_plan_output(
    output: Any,
    *,
    available_world_refs: set[str] | None = None,
) -> dict[str, Any]:
    if isinstance(output, str):
        return coerce_operation_plan_output(
            _extract_json_payload(output),
            available_world_refs=available_world_refs,
        )
    if hasattr(output, "model_dump"):
        return coerce_operation_plan_output(
            output.model_dump(exclude_none=True),
            available_world_refs=available_world_refs,
        )
    if hasattr(output, "dict"):
        return coerce_operation_plan_output(output.dict(exclude_none=True), available_world_refs=available_world_refs)
    if not isinstance(output, dict):
        output_type = type(output).__name__
        raise RuntimeError(f"model returned unsupported operation-plan output type: {output_type}")

    plan = output.get("operation_plan", output)
    refs = available_world_refs if available_world_refs is not None else _declared_world_refs(plan)
    errors = validate_operation_plan(plan, refs)
    if errors:
        raise RuntimeError("model returned invalid operation plan: " + "; ".join(errors))
    return plan


def _review_request(world: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    evidence = run.get("evidence", run)
    deterministic = evaluate_logic_profile(world.get("logic_profile", {}), evidence).to_dict()
    payload = {
        "world_id": world.get("world_id"),
        "world_name": world.get("name"),
        "task_unit": world.get("task_unit"),
        "run_id": run.get("run_id"),
        "logic_profile": world.get("logic_profile", {}),
        "evidence": evidence,
        "deterministic_evaluation": deterministic,
    }
    return {
        "system_prompt": (
            "You are an AEC-Bench meta-harness reviewer. Inspect the supplied world, evidence, "
            "deterministic evaluation, traces, artifacts, and contradictions. Return structured JSON only."
        ),
        "user_prompt": (
            "Review this task-world run. Cite only evidence present in the payload.\n\n"
            "Payload:\n"
            "```json\n"
            f"{json.dumps(payload, indent=2, sort_keys=True)}\n"
            "```"
        ),
        "payload": payload,
    }


def _coerce_review_output(output: Any) -> dict[str, Any]:
    from aec_bench.evaluation.llm_reviewer import ReviewResponse

    if isinstance(output, ReviewResponse):
        return output.model_dump(mode="json", exclude_none=True)
    if hasattr(output, "model_dump"):
        return output.model_dump(mode="json", exclude_none=True)
    if isinstance(output, dict):
        return ReviewResponse.model_validate(output).model_dump(mode="json", exclude_none=True)
    if isinstance(output, str):
        return ReviewResponse.model_validate_json(json.dumps(_extract_json_payload(output))).model_dump(
            mode="json",
            exclude_none=True,
        )
    raise RuntimeError(f"model returned unsupported review output type: {type(output).__name__}")


def _agent(*, endpoint: ModelEndpoint, system_prompt: str, output_type: Any) -> Any:
    Agent = _pydantic_ai_agent_type()
    return Agent(
        build_model_reference(endpoint),
        system_prompt=system_prompt,
        output_type=output_type,
        retries=2,
        model_settings=build_model_settings(endpoint),
    )


def build_model_reference(endpoint: ModelEndpoint) -> Any:
    provider = _effective_provider(endpoint)
    if provider in {"openai_compatible", "azure", "together"}:
        return _build_openai_family_model(endpoint, provider)
    if provider in {"openai", "anthropic", "google"}:
        return _provider_prefixed_model(endpoint.model, provider)
    return endpoint.model


def _build_openai_family_model(endpoint: ModelEndpoint, provider: str) -> Any:
    try:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
    except ImportError as exc:
        raise _missing_pydantic_ai_error() from exc

    if provider == "together":
        model_name = _strip_together_prefix(endpoint.model)
        api_key = _secret_value(endpoint, default_env="TOGETHER_API_KEY")
        if not api_key:
            raise RuntimeError("required environment variable is not set: TOGETHER_API_KEY")
        return OpenAIChatModel(model_name, provider=OpenAIProvider(base_url=TOGETHER_BASE_URL, api_key=api_key))

    if provider == "azure":
        endpoint_url = _configured_value(
            endpoint.base_url,
            endpoint.base_url_env,
            default_env="AZURE_OPENAI_ENDPOINT",
        )
        api_key = _secret_value(endpoint, default_env="AZURE_OPENAI_API_KEY")
        if not endpoint_url:
            raise RuntimeError("required environment variable is not set: AZURE_OPENAI_ENDPOINT")
        if not api_key:
            raise RuntimeError("required environment variable is not set: AZURE_OPENAI_API_KEY")
        if endpoint_url.rstrip("/").lower().endswith("/openai/v1"):
            return OpenAIChatModel(endpoint.model, provider=OpenAIProvider(base_url=endpoint_url, api_key=api_key))
        try:
            from pydantic_ai.providers.azure import AzureProvider
        except ImportError as exc:
            raise _missing_pydantic_ai_error() from exc
        api_version = (
            endpoint.api_version
            or _env(endpoint.api_version_env)
            or os.environ.get("AZURE_OPENAI_API_VERSION")
            or os.environ.get("AGENT_API_VERSION")
            or "2024-10-21"
        )
        return OpenAIChatModel(
            endpoint.model,
            provider=AzureProvider(azure_endpoint=endpoint_url, api_key=api_key, api_version=api_version),
        )

    base_url = _configured_value(endpoint.base_url, endpoint.base_url_env)
    if not base_url:
        raise RuntimeError("openai_compatible endpoints require base_url or base_url_env")
    api_key = _secret_value(endpoint) or "not-needed"
    return OpenAIChatModel(endpoint.model, provider=OpenAIProvider(base_url=base_url, api_key=api_key))


def build_model_settings(endpoint: ModelEndpoint) -> Any | None:
    settings: dict[str, Any] = {}
    if endpoint.temperature is not None:
        settings["temperature"] = endpoint.temperature
    if endpoint.max_tokens is not None:
        settings["max_tokens"] = endpoint.max_tokens
    if not settings:
        return None
    try:
        from pydantic_ai import ModelSettings
    except ImportError as exc:
        raise _missing_pydantic_ai_error() from exc
    return ModelSettings(**settings)


def _problem_space_brief_output_type() -> Any:
    try:
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError("pydantic is required for structured intake outputs") from exc

    class ProblemSpaceBriefOutput(BaseModel):
        brief_id: str = Field(min_length=1)
        objective: str = Field(min_length=1)
        task_request: str = Field(min_length=1)
        constraints: list[str] = Field(default_factory=list)
        attachments: list[dict[str, Any]] = Field(default_factory=list)
        expected_outputs: list[str] = Field(default_factory=list)
        evidence_requirements: list[str] = Field(min_length=1)
        risk_notes: list[str] = Field(default_factory=list)

    class ProblemSpaceBriefEnvelopeOutput(BaseModel):
        problem_space_brief: ProblemSpaceBriefOutput

    return ProblemSpaceBriefEnvelopeOutput


def _world_generation_output_type() -> Any:
    try:
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError("pydantic is required for structured world-generation outputs") from exc

    class WorldCardOutput(BaseModel):
        world_id: str = Field(min_length=1)
        name: str | None = None
        task_unit: str = Field(min_length=1)
        logic_profile: dict[str, Any]
        operation_profile: dict[str, Any]
        operation_handles: dict[str, Any]
        evidence_profile: dict[str, Any] = Field(default_factory=dict)
        governance_profile: dict[str, Any] = Field(default_factory=dict)
        provenance: dict[str, Any] = Field(default_factory=dict)

    class WorldGenerationOutput(BaseModel):
        world: WorldCardOutput
        world_generation_rationale: str | None = None

    return WorldGenerationOutput


def _operation_plan_output_type() -> Any:
    try:
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError("pydantic is required to build structured operation-plan model outputs") from exc

    class OperationPlanStepOutput(BaseModel):
        id: str = Field(min_length=1)
        kind: str
        world_ref: str = Field(min_length=1)
        output_ref: str | None = None
        operation: dict[str, Any] | None = None
        proposal: dict[str, Any] | None = None
        fallback_policy: str | None = None

    class OperationPlanOutput(BaseModel):
        plan_id: str = Field(min_length=1)
        brief_ref: str | None = None
        objective: str = Field(min_length=1)
        steps: list[OperationPlanStepOutput] = Field(min_length=1)
        acceptance_checks: list[str] = Field(default_factory=list)

    class OperationPlanEnvelopeOutput(BaseModel):
        operation_plan: OperationPlanOutput

    return OperationPlanEnvelopeOutput


def _extract_json_payload(response_text: str) -> Any:
    matches = re.findall(r"```json\s*\n(.*?)\n\s*```", response_text, re.DOTALL)
    candidate = matches[-1] if matches else response_text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"model response did not contain valid JSON: {exc}") from exc


def _declared_world_refs(plan: Any) -> set[str]:
    if not isinstance(plan, dict):
        return set()
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return set()
    return {
        step["world_ref"]
        for step in steps
        if isinstance(step, dict) and isinstance(step.get("world_ref"), str) and step["world_ref"].strip()
    }


def _usage_dict(result: Any) -> dict[str, int]:
    usage = getattr(result, "usage", None)
    usage = usage() if callable(usage) else usage
    if usage is None:
        return {}
    return {
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        "requests": getattr(usage, "requests", 0) or 0,
        "cache_read_tokens": getattr(usage, "cache_read_tokens", 0) or 0,
        "cache_write_tokens": getattr(usage, "cache_write_tokens", 0) or 0,
    }


def estimate_model_cost(endpoint: ModelEndpoint, usage: dict[str, int]) -> dict[str, Any] | None:
    estimated = 0.0
    priced = False
    token_rates = [
        ("input_tokens", endpoint.input_cost_per_million),
        ("output_tokens", endpoint.output_cost_per_million),
        ("cache_read_tokens", endpoint.cache_read_cost_per_million),
        ("cache_write_tokens", endpoint.cache_write_cost_per_million),
    ]
    for usage_key, rate in token_rates:
        if rate is None:
            continue
        priced = True
        estimated += (usage.get(usage_key, 0) * rate) / 1_000_000
    if endpoint.request_cost is not None:
        priced = True
        estimated += usage.get("requests", 0) * endpoint.request_cost
    if not priced:
        return None
    return {
        "currency": "USD",
        "estimated_cost_usd": round(estimated, 8),
        "pricing_source": "endpoint_config",
    }


def _aggregate_model_costs(results: list[dict[str, Any]]) -> dict[str, Any]:
    costs = []
    for result in results:
        cost = result.get("cost")
        if isinstance(cost, dict) and isinstance(cost.get("estimated_cost_usd"), int | float):
            costs.append(float(cost["estimated_cost_usd"]))
    if not costs:
        return {}
    return {
        "cost": {
            "currency": "USD",
            "estimated_cost_usd": round(sum(costs), 8),
            "pricing_source": "endpoint_config",
        }
    }


def _pydantic_ai_agent_type() -> Any:
    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        raise _missing_pydantic_ai_error() from exc
    return Agent


def _missing_pydantic_ai_error() -> RuntimeError:
    return RuntimeError("pydantic-ai is required to run meta-harness model endpoints")


def _effective_provider(endpoint: ModelEndpoint) -> str:
    if endpoint.provider == "auto" and endpoint.model.lower().startswith(TOGETHER_PREFIX):
        return "together"
    if endpoint.provider == "openai" and (endpoint.base_url or endpoint.base_url_env):
        return "openai_compatible"
    return endpoint.provider


def _provider_prefixed_model(model: str, provider: str) -> str:
    if ":" in model:
        return model
    return f"{provider}:{model}"


def _strip_together_prefix(model: str) -> str:
    if model.lower().startswith(TOGETHER_PREFIX):
        return model[len(TOGETHER_PREFIX) :]
    return model


def _configured_value(
    explicit: str | None,
    env_name: str | None = None,
    *,
    default_env: str | None = None,
) -> str | None:
    return explicit or _env(env_name) or _env(default_env)


def _secret_value(endpoint: ModelEndpoint, *, default_env: str | None = None) -> str | None:
    return endpoint.api_key or _env(endpoint.api_key_env) or _env(default_env)


def _env(name: str | None) -> str | None:
    if not name:
        return None
    value = os.environ.get(name)
    return value or None


def _required_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _optional_string(mapping: dict[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value.strip() or None


def _optional_float(mapping: dict[str, Any], key: str) -> float | None:
    value = mapping.get(key)
    if value is None or value == "":
        return None
    return float(value)


def _optional_int(mapping: dict[str, Any], key: str) -> int | None:
    value = mapping.get(key)
    if value is None or value == "":
        return None
    return int(value)
