# ABOUTME: Contract models for experiment configuration at the planning-to-harness boundary.
# ABOUTME: Defines task selection, agent configuration, compute selection, and run metadata.

from typing import Any

from pydantic import Field, PositiveInt, field_validator, model_validator

from aec_bench.contracts.task_definition import Difficulty, Lifecycle
from aec_bench.contracts.validators import (
    NonEmptyStr,
    StrictModel,
    ensure_non_empty_string,
    resolve_env_ref,
)


class TaskSelector(StrictModel):
    dataset: str | None = None  # "name" or "name@version"
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    difficulties: list[Difficulty] = Field(default_factory=list)
    lifecycle_filter: list[Lifecycle] = Field(default_factory=lambda: [Lifecycle.ACTIVE])

    @field_validator("lifecycle_filter")
    @classmethod
    def validate_lifecycle_filter(cls, value: list[Lifecycle]) -> list[Lifecycle]:
        forbidden = {Lifecycle.PROPOSED, Lifecycle.RETIRED}
        if any(item in forbidden for item in value):
            msg = "lifecycle_filter cannot include proposed or retired tasks"
            raise ValueError(msg)
        return value


class ClientConfig(StrictModel):
    kind: NonEmptyStr
    settings: dict[str, Any] = Field(default_factory=dict)


class AgentConfig(StrictModel):
    name: NonEmptyStr
    adapter: NonEmptyStr
    model: str
    client: ClientConfig | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    system_prompt_file: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _rewrite_harness_to_adapter(cls, data: Any) -> Any:
        """Accept 'harness' as a user-facing synonym for 'adapter'."""
        if not isinstance(data, dict):
            return data
        has_adapter = "adapter" in data
        has_harness = "harness" in data
        if has_adapter and has_harness:
            msg = "Provide either 'adapter' or 'harness', not both"
            raise ValueError(msg)
        if has_harness:
            data["adapter"] = data.pop("harness")
        return data

    @field_validator("model", mode="before")
    @classmethod
    def resolve_model_env(cls, value: str) -> str:
        return resolve_env_ref(value)

    @field_validator("model")
    @classmethod
    def validate_model_non_empty(cls, value: str) -> str:
        return ensure_non_empty_string(value)


class ComputeConfig(StrictModel):
    backend: NonEmptyStr
    resource_limits: dict[str, Any] = Field(default_factory=dict)
    timeout_override: PositiveInt | None = None


class ReviewerEndpointConfig(StrictModel):
    name: NonEmptyStr
    model: NonEmptyStr
    provider: NonEmptyStr = "auto"
    base_url: str | None = None
    base_url_env: str | None = None
    api_key_env: str | None = None
    temperature: float | None = 0.0
    max_tokens: PositiveInt | None = None
    stream_mode: NonEmptyStr = "auto"

    @field_validator("model")
    @classmethod
    def validate_model_non_empty(cls, value: str) -> str:
        return ensure_non_empty_string(value)


class ReviewerConfig(StrictModel):
    enabled: bool = False
    required: bool = True
    models: list[ReviewerEndpointConfig] = Field(default_factory=list)
    fail_on_error: bool = False


class ExperimentManifest(StrictModel):
    experiment_id: NonEmptyStr
    name: NonEmptyStr
    description: str | None = None
    tasks: TaskSelector
    agents: list[AgentConfig]
    compute: ComputeConfig
    repetitions: PositiveInt = 1
    disable_verification: bool = False
    reviewer: ReviewerConfig | None = None

    @field_validator("agents")
    @classmethod
    def validate_agents_non_empty(cls, value: list[AgentConfig]) -> list[AgentConfig]:
        if not value:
            msg = "agents list must contain at least one agent configuration"
            raise ValueError(msg)
        return value
