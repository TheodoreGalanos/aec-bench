# ABOUTME: Runs post-verifier LLM review over completed task workspaces and Harbor trials.
# ABOUTME: Persists structured reviewer requests, findings, and summaries as evaluation artifacts.

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml  # type: ignore[import-untyped]
from pydantic import Field, NonNegativeFloat, NonNegativeInt, field_validator

from aec_bench.adapters.pydantic_ai_runtime import (
    agent_run_output,
    run_agent_sync_with_streaming_fallback,
)
from aec_bench.contracts.validators import NonEmptyStr, StrictModel, ensure_non_empty_string
from aec_bench.evaluation.task_world import (
    materialize_harbor_task_world_run,
    materialize_workspace_task_world_run,
)
from aec_bench.meta_harness.logic_profile import evaluate_logic_profile
from aec_bench.meta_harness.model_runner import (
    ModelEndpoint,
    build_model_reference,
    build_model_settings,
)

ReviewerProvider = Literal["auto", "openai", "anthropic", "google", "azure", "openai_compatible", "together"]
ReviewerStatus = Literal["complete", "partial", "error", "skipped"]
StreamMode = Literal["never", "auto", "always"]

_EVENT_CANDIDATE_CATEGORIES = {
    "verifier_language_gap",
    "schema_gap",
    "evidence_gap",
    "governance_gap",
    "containment_gap",
    "event_candidate",
}


class ReviewerEndpointConfig(StrictModel):
    name: NonEmptyStr
    model: NonEmptyStr
    provider: ReviewerProvider = "auto"
    base_url: str | None = None
    base_url_env: str | None = None
    api_key_env: str | None = None
    temperature: float | None = 0.0
    max_tokens: PositiveIntOrNone = None
    stream_mode: StreamMode = "auto"

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        return ensure_non_empty_string(value)

    def public_dict(self) -> dict[str, Any]:
        payload = self.model_dump(exclude_none=True)
        payload.pop("api_key", None)
        return payload


PositiveIntOrNone = NonNegativeInt | None


class ReviewerRunConfig(StrictModel):
    enabled: bool = False
    required: bool = True
    models: list[ReviewerEndpointConfig] = Field(default_factory=list)
    fail_on_error: bool = False


class ReviewFinding(StrictModel):
    id: NonEmptyStr
    category: NonEmptyStr
    evidence_refs: list[NonEmptyStr]
    affected_claims: list[NonEmptyStr]
    confidence: NonNegativeFloat
    proposed_next_action: NonEmptyStr
    repair_targets: list[str] = Field(default_factory=list)
    is_event_candidate: bool | None = None

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if value > 1.0:
            msg = "confidence must be between 0.0 and 1.0"
            raise ValueError(msg)
        return value


class ReviewResponse(StrictModel):
    status: Literal["complete"]
    reviewed_modes: list[NonEmptyStr]
    findings: list[ReviewFinding] = Field(default_factory=list)


class ReviewRequestPacket(StrictModel):
    system_prompt: NonEmptyStr
    user_prompt: NonEmptyStr
    payload: dict[str, Any]
    response_schema: dict[str, Any]


class ReviewerModelResult(StrictModel):
    endpoint: dict[str, Any]
    status: Literal["complete", "error"]
    review: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None
    usage: dict[str, int] | None = None
    error: str | None = None


@dataclass(frozen=True)
class ReviewerRunResult:
    output_dir: Path
    status: ReviewerStatus
    model_results: list[ReviewerModelResult]
    event_candidates: list[str]


@dataclass(frozen=True)
class ReviewerJobResult:
    job_dir: Path
    trial_count: int
    complete_count: int
    error_count: int
    skipped_count: int


def load_reviewer_config(path: Path) -> ReviewerRunConfig:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        payload = {}
    return ReviewerRunConfig.model_validate(payload)


def build_workspace_review_request(*, task_dir: Path, workspace_dir: Path) -> ReviewRequestPacket:
    materialized = materialize_workspace_task_world_run(task_dir=task_dir, workspace_dir=workspace_dir)
    return _review_request_packet(materialized.to_review_payload())


def run_workspace_reviewer(
    *,
    task_dir: Path,
    workspace_dir: Path,
    config: ReviewerRunConfig,
    output_dir: Path | None = None,
) -> ReviewerRunResult:
    resolved_output_dir = output_dir or workspace_dir / "logs" / "reviewer"
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    request = build_workspace_review_request(task_dir=task_dir, workspace_dir=workspace_dir)
    _write_json(resolved_output_dir / "request.json", request.model_dump(mode="json"))
    _write_json(resolved_output_dir / "world_profile.json", request.payload["world"])
    return _run_reviewer_request(
        request=request,
        config=config,
        output_dir=resolved_output_dir,
    )


def run_harbor_job_reviewer(
    *,
    job_dir: Path,
    repo_root: Path,
    config: ReviewerRunConfig,
) -> ReviewerJobResult:
    trial_dirs = sorted(child for child in job_dir.iterdir() if child.is_dir() and (child / "result.json").exists())
    complete_count = 0
    error_count = 0
    skipped_count = 0

    for trial_dir in trial_dirs:
        materialized = materialize_harbor_task_world_run(repo_root=repo_root, trial_dir=trial_dir)
        request = _review_request_packet(materialized.to_review_payload())
        output_dir = trial_dir / "reviewer"
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(output_dir / "request.json", request.model_dump(mode="json"))
        _write_json(output_dir / "world_profile.json", request.payload["world"])
        result = _run_reviewer_request(request=request, config=config, output_dir=output_dir)
        if result.status == "complete":
            complete_count += 1
        elif result.status == "skipped":
            skipped_count += 1
        else:
            error_count += 1

    return ReviewerJobResult(
        job_dir=job_dir,
        trial_count=len(trial_dirs),
        complete_count=complete_count,
        error_count=error_count,
        skipped_count=skipped_count,
    )


def reviewer_config_from_manifest(value: Any) -> ReviewerRunConfig | None:
    if value is None:
        return None
    if isinstance(value, ReviewerRunConfig):
        return value
    if hasattr(value, "model_dump"):
        return ReviewerRunConfig.model_validate(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return ReviewerRunConfig.model_validate(value)
    return None


def _run_reviewer_request(
    *,
    request: ReviewRequestPacket,
    config: ReviewerRunConfig,
    output_dir: Path,
) -> ReviewerRunResult:
    if not config.enabled:
        result = ReviewerRunResult(
            output_dir=output_dir,
            status="skipped",
            model_results=[],
            event_candidates=[],
        )
        _write_summary(result=result, config=config)
        return result

    if not config.models:
        result = ReviewerRunResult(
            output_dir=output_dir,
            status="error" if config.required else "skipped",
            model_results=[],
            event_candidates=[],
        )
        _write_summary(result=result, config=config, error="reviewer enabled but no models were configured")
        if config.fail_on_error:
            raise RuntimeError("reviewer enabled but no models were configured")
        return result

    model_results: list[ReviewerModelResult] = []
    event_candidates: list[str] = []
    for endpoint in config.models:
        endpoint_dir = output_dir / _slug(endpoint.name)
        endpoint_dir.mkdir(parents=True, exist_ok=True)
        try:
            model_result = _run_endpoint(request=request, endpoint=endpoint)
            if model_result.review is not None:
                _write_json(endpoint_dir / "review.json", model_result.review)
            if model_result.evaluation is not None:
                _write_json(endpoint_dir / "evaluation.json", model_result.evaluation)
                event_candidates.extend(model_result.evaluation.get("event_candidates", []))
        except Exception as exc:
            model_result = ReviewerModelResult(
                endpoint=endpoint.public_dict(),
                status="error",
                error=str(exc),
            )
            _write_json(endpoint_dir / "error.json", model_result.model_dump(mode="json", exclude_none=True))
            if config.fail_on_error:
                raise
        model_results.append(model_result)

    complete_count = sum(1 for result in model_results if result.status == "complete")
    if complete_count == len(model_results):
        status: ReviewerStatus = "complete"
    elif complete_count:
        status = "partial"
    else:
        status = "error"
    result = ReviewerRunResult(
        output_dir=output_dir,
        status=status,
        model_results=model_results,
        event_candidates=sorted(set(event_candidates)),
    )
    _write_summary(result=result, config=config)
    return result


def _run_endpoint(*, request: ReviewRequestPacket, endpoint: ReviewerEndpointConfig) -> ReviewerModelResult:
    model_reference = _build_model_reference(endpoint)
    model_settings = _model_settings(endpoint)

    try:
        from pydantic_ai import Agent
    except ImportError as exc:
        msg = "pydantic-ai is required to run LLM reviewer models"
        raise RuntimeError(msg) from exc

    agent = Agent(
        model_reference,
        system_prompt=request.system_prompt,
        output_type=ReviewResponse,
        retries=2,
        model_settings=model_settings,
    )
    result = run_agent_sync_with_streaming_fallback(
        agent,
        request.user_prompt,
        stream_mode=endpoint.stream_mode,
    )
    review = _coerce_review(agent_run_output(result))
    evaluation = _review_evaluation(request.payload, review)
    return ReviewerModelResult(
        endpoint=endpoint.public_dict(),
        status="complete",
        review=review,
        evaluation=evaluation,
        usage=_usage_dict(result),
    )


def _build_model_reference(endpoint: ReviewerEndpointConfig) -> Any:
    return build_model_reference(_model_endpoint(endpoint))


def _model_settings(endpoint: ReviewerEndpointConfig) -> Any | None:
    return build_model_settings(_model_endpoint(endpoint))


def _model_endpoint(endpoint: ReviewerEndpointConfig) -> ModelEndpoint:
    return ModelEndpoint(
        name=endpoint.name,
        model=endpoint.model,
        provider=endpoint.provider,
        base_url=endpoint.base_url,
        base_url_env=endpoint.base_url_env,
        api_key_env=endpoint.api_key_env,
        temperature=endpoint.temperature,
        max_tokens=endpoint.max_tokens,
        stream_mode=endpoint.stream_mode,
    )


def _review_request_packet(payload: dict[str, Any]) -> ReviewRequestPacket:
    payload = dict(payload)
    payload["deterministic_evaluation"] = evaluate_logic_profile(
        payload.get("logic_profile", {}),
        _review_evidence(payload),
    ).to_dict()
    payload_json = json.dumps(payload, indent=2, sort_keys=True)
    system_prompt = (
        "You are an AEC-Bench post-verifier reviewer. The deterministic verifier remains the reward authority, "
        "but you must inspect whether the verifier result is interpretable in light of the materialised task-world "
        "profile, output, artifacts, trace, source authority, and contradiction evidence. Do not invent evidence. "
        "Cite only keys and paths present in the review payload. Return only structured review JSON."
    )
    user_prompt = (
        "Review the completed benchmark run for verifier-language gaps, schema gaps, evidence gaps, "
        "governance gaps, containment gaps, genuine model failures, and event candidates.\n\n"
        "If no issue is found, return status 'complete' with reviewed_modes and an empty findings list.\n\n"
        "Review payload:\n"
        "```json\n"
        f"{payload_json}\n"
        "```"
    )
    return ReviewRequestPacket(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        payload=payload,
        response_schema=ReviewResponse.model_json_schema(),
    )


def _review_evaluation(payload: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    findings = review.get("findings", [])
    evidence = _review_evidence(payload)
    evidence["agentic_review"] = review
    logic_evaluation = evaluate_logic_profile(payload.get("logic_profile", {}), evidence).to_dict()
    event_candidates = [str(candidate.get("id")) for candidate in logic_evaluation["event_candidates"]]
    if isinstance(findings, list):
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            category = finding.get("category")
            if category in _EVENT_CANDIDATE_CATEGORIES or finding.get("is_event_candidate") is True:
                event_candidates.append(str(finding.get("id") or category))
    return {
        "status": "complete",
        "finding_count": len(findings) if isinstance(findings, list) else 0,
        "overall_status": logic_evaluation["overall_status"],
        "event_candidates": sorted(set(event_candidates)),
        "logic_evaluation": logic_evaluation,
    }


def _review_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    excluded_keys = {"world", "logic_profile", "operation_profile", "deterministic_evaluation"}
    return {key: value for key, value in payload.items() if key not in excluded_keys}


def _coerce_review(output: Any) -> dict[str, Any]:
    if isinstance(output, ReviewResponse):
        return output.model_dump(mode="json", exclude_none=True)
    if hasattr(output, "model_dump"):
        return cast(dict[str, Any], output.model_dump(mode="json", exclude_none=True))
    if isinstance(output, dict):
        return ReviewResponse.model_validate(output).model_dump(mode="json", exclude_none=True)
    if isinstance(output, str):
        return ReviewResponse.model_validate_json(_json_from_text(output)).model_dump(mode="json", exclude_none=True)
    msg = f"reviewer returned unsupported output type: {type(output).__name__}"
    raise RuntimeError(msg)


def _json_from_text(text: str) -> str:
    matches = re.findall(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    return matches[-1] if matches else text


def _usage_dict(result: Any) -> dict[str, int]:
    usage = result.usage() if hasattr(result, "usage") else None
    if usage is None:
        return {}
    return {
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        "requests": getattr(usage, "requests", 0) or 0,
        "cache_read_tokens": getattr(usage, "cache_read_tokens", 0) or 0,
        "cache_write_tokens": getattr(usage, "cache_write_tokens", 0) or 0,
    }


def _write_summary(
    *,
    result: ReviewerRunResult,
    config: ReviewerRunConfig,
    error: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "enabled": config.enabled,
        "required": config.required,
        "status": result.status,
        "model_count": len(config.models),
        "complete_count": sum(1 for model_result in result.model_results if model_result.status == "complete"),
        "error_count": sum(1 for model_result in result.model_results if model_result.status == "error"),
        "event_candidates": result.event_candidates,
        "models": [model_result.model_dump(mode="json", exclude_none=True) for model_result in result.model_results],
    }
    if error is not None:
        payload["error"] = error
    _write_json(result.output_dir / "summary.json", payload)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return slug or "reviewer"


def _env(name: str | None) -> str | None:
    if not name:
        return None
    return os.environ.get(name) or None
