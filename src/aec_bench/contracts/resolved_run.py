# ABOUTME: Defines the resolved requested condition for one benchmark run.
# ABOUTME: Resolves current experiment configuration without persisting or executing it.

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import Field, PositiveInt, field_validator, model_validator

from aec_bench.contracts.dataset import DatasetRef
from aec_bench.contracts.evaluation_refs import EvaluationRegimeRef
from aec_bench.contracts.experiment_manifest import (
    AgentCondition,
    ComputeConfig,
    ExperimentManifest,
    ReviewerConfig,
)
from aec_bench.contracts.identity import EntityIdentity, EntityKey
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.task_snapshot import TaskSnapshotRef
from aec_bench.contracts.trial_record import AuthorityExpectation, ProviderRoute
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


class ResolvedRunSpec(FrozenStrictModel):
    """One complete requested run condition before execution begins."""

    schema_version: Literal[1] = 1
    experiment_identity: EntityIdentity
    run_identity: EntityIdentity
    run_name: NonEmptyStr
    created_at: datetime
    created_by: NonEmptyStr
    dataset: DatasetRef | None = None
    task_releases: tuple[TaskSnapshotRef, ...]
    agent_conditions: tuple[AgentCondition, ...]
    compute: ComputeConfig
    repetitions: PositiveInt
    verification_enabled: bool
    reviewer: ReviewerConfig | None = None
    randomization_seed: Annotated[int, Field(strict=True, ge=0)] | None = None
    execution_policy_version: PositiveInt = 1
    visibility: tuple[Visibility, ...]
    expected_authorities: tuple[AuthorityExpectation, ...] = ()
    evaluation_regime: EvaluationRegimeRef | None = None
    provider_route_request: ProviderRoute | None = None

    @property
    def experiment_id(self) -> UUID:
        """Return the stable experiment UUID without duplicating it in JSON."""

        return self.experiment_identity.id

    @property
    def run_id(self) -> UUID:
        """Return the stable run UUID without duplicating it in JSON."""

        return self.run_identity.id

    @property
    def run_key(self) -> EntityKey:
        """Return the readable run key from the authoritative identity."""

        return self.run_identity.key

    @field_validator("created_at")
    @classmethod
    def validate_created_at_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("resolved run created_at must include a timezone")
        return value

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, value: tuple[Visibility, ...]) -> tuple[Visibility, ...]:
        if not value:
            raise ValueError("resolved run visibility must include at least one value")
        if len(value) != len(set(value)):
            raise ValueError("resolved run visibility values must be unique")
        return value

    @field_validator("expected_authorities")
    @classmethod
    def validate_authorities(
        cls,
        value: tuple[AuthorityExpectation, ...],
    ) -> tuple[AuthorityExpectation, ...]:
        keys = [(item.authority_kind, item.protocol) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("resolved run authority expectations must be unique")
        return value

    @model_validator(mode="after")
    def validate_identity_relationships(self) -> Self:
        if self.experiment_identity.id == self.run_identity.id:
            raise ValueError("resolved run experiment and run identities must be distinct")
        if not self.task_releases:
            raise ValueError("resolved run requires at least one task release")
        task_keys = [str(reference.task_id) for reference in self.task_releases]
        if len(task_keys) != len(set(task_keys)):
            raise ValueError("resolved run task releases must be unique")
        task_ids = [reference.task_identity.id for reference in self.task_releases]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("resolved run task identities must be unique")
        if not self.agent_conditions:
            raise ValueError("resolved run requires at least one agent condition")
        condition_keys = [str(condition.identity.key) for condition in self.agent_conditions]
        condition_ids = [condition.identity.id for condition in self.agent_conditions]
        if len(condition_keys) != len(set(condition_keys)):
            raise ValueError("resolved run agent conditions must be unique")
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("resolved run agent condition identities must be unique")
        for index, condition in enumerate(self.agent_conditions):
            _reject_secret_values(condition.model_dump(mode="python"), path=f"agent_conditions[{index}]")
        if self.reviewer is not None:
            _reject_secret_values(self.reviewer.model_dump(mode="python"), path="reviewer")
        return self


def resolve_run_spec(
    manifest: ExperimentManifest,
    *,
    task_releases: Sequence[TaskSnapshotRef],
    agent_conditions: Sequence[AgentCondition],
    experiment_identity: EntityIdentity,
    run_identity: EntityIdentity,
    created_at: datetime,
    created_by: str,
    expected_authorities: Sequence[AuthorityExpectation] = (),
    evaluation_regime: EvaluationRegimeRef | None = None,
    provider_route_request: ProviderRoute | None = None,
    randomization_seed: Annotated[int, Field(strict=True, ge=0)] | None = None,
    execution_policy_version: int = 1,
) -> ResolvedRunSpec:
    """Resolve one manifest into an explicit requested run condition."""

    if str(experiment_identity.key) != manifest.experiment_id:
        raise ValueError("experiment identity key must match the manifest experiment_id")
    if not task_releases:
        raise ValueError("resolved run requires at least one task release")
    conditions = tuple(agent_conditions)
    if len(conditions) != len(manifest.agents):
        raise ValueError("resolved run agent conditions must match manifest agents")
    for agent, condition in zip(manifest.agents, conditions, strict=True):
        if str(condition.identity.key) != agent.name:
            raise ValueError("agent condition identity key must match manifest agent name")
        if condition.adapter != agent.adapter:
            raise ValueError("agent condition adapter must match manifest agent adapter")
        if agent.system_prompt_file is not None:
            raise ValueError("resolved run cannot retain unresolved agent system_prompt_file")
        if condition.system_prompt != agent.system_prompt:
            raise ValueError("agent condition system_prompt must match manifest agent system_prompt")
        if condition.client != agent.client:
            raise ValueError("agent condition client must match manifest agent client")
        if condition.parameters != agent.parameters:
            raise ValueError("agent condition parameters must match manifest agent parameters")
        if condition.model != agent.model:
            raise ValueError("agent condition model must match manifest agent model")
        _reject_secret_values(
            condition.model_dump(mode="python"),
            path=f"agent_conditions[{condition.identity.key}]",
        )
    return ResolvedRunSpec(
        experiment_identity=experiment_identity,
        run_identity=run_identity,
        run_name=manifest.name,
        created_at=created_at,
        created_by=created_by,
        dataset=manifest.tasks.dataset,
        task_releases=tuple(task_releases),
        agent_conditions=conditions,
        compute=manifest.compute,
        repetitions=manifest.repetitions,
        verification_enabled=not manifest.disable_verification,
        reviewer=manifest.reviewer,
        randomization_seed=randomization_seed,
        execution_policy_version=execution_policy_version,
        visibility=tuple(manifest.tasks.visibility_filter),
        expected_authorities=tuple(expected_authorities),
        evaluation_regime=evaluation_regime,
        provider_route_request=provider_route_request,
    )


def _reject_secret_values(value: Any, *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            child_path = f"{path}.{key}"
            sensitive_key = key_text in {
                "secret",
                "password",
                "token",
                "api_key",
                "access_token",
                "refresh_token",
                "client_secret",
            } or key_text.endswith(("_secret", "_password", "_token", "_api_key"))
            if sensitive_key and not key_text.endswith("_env"):
                if isinstance(child, str) and child.startswith("env:"):
                    continue
                raise ValueError(f"resolved run cannot retain a secret value at {child_path}")
            _reject_secret_values(child, path=child_path)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for index, child in enumerate(value):
            _reject_secret_values(child, path=f"{path}[{index}]")


__all__ = ("ResolvedRunSpec", "resolve_run_spec")
