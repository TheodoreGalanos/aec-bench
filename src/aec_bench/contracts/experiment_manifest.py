# ABOUTME: Contract models for experiment configuration at the planning-to-harness boundary.
# ABOUTME: Defines task selection, agent configuration, compute selection, and run metadata.

from typing import Any

from pydantic import Field, PositiveInt, field_validator, model_validator

from aec_bench.contracts.dataset import DatasetRef
from aec_bench.contracts.identity import EntityIdentity
from aec_bench.contracts.task_definition import Difficulty, Lifecycle, Visibility
from aec_bench.contracts.validators import (
    FrozenStrictModel,
    NonEmptyStr,
    StrictModel,
    ensure_non_empty_string,
    resolve_env_ref,
)


class TaskSelector(StrictModel):
    dataset: DatasetRef | None = None
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    difficulties: list[Difficulty] = Field(default_factory=list)
    lifecycle_filter: list[Lifecycle] = Field(default_factory=lambda: [Lifecycle.ACTIVE])
    visibility_filter: list[Visibility] = Field(default_factory=lambda: [Visibility.PUBLIC])

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
    system_prompt: str | None = None
    system_prompt_file: str | None = None
    n_concurrent: int | None = Field(default=None, ge=1, strict=True, exclude_if=lambda value: value is None)
    concurrency_group: NonEmptyStr | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def validate_concurrency(self) -> "AgentConfig":
        if self.concurrency_group is not None and self.n_concurrent is None:
            raise ValueError("concurrency_group requires n_concurrent")
        if {"n_concurrent", "concurrency_group"} & self.parameters.keys():
            raise ValueError("n_concurrent and concurrency_group belong on the agent configuration, not parameters")
        return self

    @model_validator(mode="after")
    def validate_system_prompt_source(self) -> "AgentConfig":
        if self.system_prompt is not None and self.system_prompt_file is not None:
            raise ValueError("agent config must provide system_prompt or system_prompt_file, not both")
        return self

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


class AgentCondition(FrozenStrictModel):
    """One explicit, versioned requested agent condition.

    ``AgentConfig`` remains the user-facing configuration. A caller supplies
    this stable condition when resolving a ``ResolvedRunSpec``.
    """

    identity: EntityIdentity
    adapter: NonEmptyStr
    model: NonEmptyStr
    client: ClientConfig | None = None
    system_prompt: str | None = None
    tool_versions: dict[str, str] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tool_versions")
    @classmethod
    def validate_tool_versions(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not name.strip() or not version.strip() for name, version in value.items()):
            raise ValueError("agent condition tool names and versions must not be blank")
        return value


class ComputeConfig(StrictModel):
    backend: NonEmptyStr
    stream: bool = False
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

    @model_validator(mode="after")
    def validate_agent_concurrency(self) -> "ExperimentManifest":
        job_limit = int(self.compute.resource_limits.get("n_concurrent_trials", 1))
        groups: dict[str, int] = {}
        for agent in self.agents:
            if agent.n_concurrent is None:
                continue
            if agent.n_concurrent > job_limit:
                raise ValueError("agent n_concurrent cannot exceed compute.resource_limits.n_concurrent_trials")
            if agent.concurrency_group is not None:
                previous = groups.setdefault(agent.concurrency_group, agent.n_concurrent)
                if previous != agent.n_concurrent:
                    raise ValueError("agents in a concurrency_group must use the same n_concurrent")
        return self

    @field_validator("agents")
    @classmethod
    def validate_agents_non_empty(cls, value: list[AgentConfig]) -> list[AgentConfig]:
        if not value:
            msg = "agents list must contain at least one agent configuration"
            raise ValueError(msg)
        return value
