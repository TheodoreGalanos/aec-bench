# ABOUTME: Minimal contract models for Harbor trial artifacts consumed by Python ingestion.
# ABOUTME: Validates the Harbor result shape the importer relies on without broad Harbor coupling.

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError, field_validator

from aec_bench.contracts.validators import LenientModel, ensure_non_empty_string


class HarborArtifactContractError(Exception):
    pass


class HarborTaskConfig(LenientModel):
    path: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return ensure_non_empty_string(value)


class HarborAgentConfig(LenientModel):
    name: str
    model_name: str
    import_path: str | None = None
    kwargs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "model_name")
    @classmethod
    def validate_required_strings(cls, value: str) -> str:
        return ensure_non_empty_string(value)


class HarborEnvironmentConfig(LenientModel):
    type: str

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        return ensure_non_empty_string(value)


class HarborTrialConfig(LenientModel):
    task: HarborTaskConfig
    agent: HarborAgentConfig
    environment: HarborEnvironmentConfig
    job_id: str

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value: str) -> str:
        return ensure_non_empty_string(value)


class HarborAgentInfo(LenientModel):
    name: str
    version: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return ensure_non_empty_string(value)


class HarborAgentResult(LenientModel):
    n_input_tokens: int | None = None
    n_cache_tokens: int | None = None
    n_output_tokens: int | None = None
    cost_usd: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HarborStageTiming(LenientModel):
    started_at: datetime
    finished_at: datetime


class HarborTrialResult(LenientModel):
    trial_name: str
    task_checksum: str
    config: HarborTrialConfig
    agent_info: HarborAgentInfo
    agent_result: HarborAgentResult
    exception_info: dict[str, Any] | None = None
    started_at: datetime
    finished_at: datetime
    environment_setup: HarborStageTiming | None = None
    agent_setup: HarborStageTiming | None = None
    agent_execution: HarborStageTiming | None = None
    verifier: HarborStageTiming | None = None

    @field_validator("trial_name", "task_checksum")
    @classmethod
    def validate_required_strings(cls, value: str) -> str:
        return ensure_non_empty_string(value)


def read_harbor_trial_result(path: Path | str) -> HarborTrialResult:
    resolved = Path(path)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return HarborTrialResult.model_validate(payload)
    except ValidationError as exc:
        raise HarborArtifactContractError(str(exc)) from exc
