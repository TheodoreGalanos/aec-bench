# ABOUTME: Defines immutable contracts and content-bound planning for lifecycle ablation sweeps.
# ABOUTME: Keeps plan identity independent from execution, finalization, and summary orchestration.

from __future__ import annotations

import hashlib
import inspect
import json
import re
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import (
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
    field_validator,
    model_validator,
)

from aec_bench.contracts.experiment_manifest import AgentConfig
from aec_bench.contracts.trial_record import AdaptationProvenance, ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.meta_harness.evidence_lifecycle import evidence_lifecycle_package_identity
from aec_bench.meta_harness.evidence_lifecycle_experiment import (
    repository_provenance,
    runtime_dependency_provenance,
)
from aec_bench.meta_harness.evidence_lifecycle_local import (
    LifecycleVisibilityPolicy,
    run_local_evidence_lifecycle_fresh_context,
)
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.lifecycles import (
    lifecycle_variant_ids,
    lifecycle_variant_metadata,
    registered_lifecycle_verifier,
)
from aec_bench.task_world_templates.materializer import (
    materialize_template_lifecycle,
    verify_template_lifecycle,
)


class LifecycleExecutionMode(StrEnum):
    PERSISTENT_CONTEXT = "persistent_context"
    FRESH_CONTEXT = "fresh_context"


class LifecycleAblationCondition(StrictModel):
    execution_mode: LifecycleExecutionMode
    memory_visibility_policy: LifecycleVisibilityPolicy

    @model_validator(mode="after")
    def validate_mode_policy_pair(self) -> LifecycleAblationCondition:
        if (
            self.execution_mode is LifecycleExecutionMode.PERSISTENT_CONTEXT
            and self.memory_visibility_policy is not LifecycleVisibilityPolicy.PERSISTENT_CONTEXT
        ):
            raise ValueError("persistent_context execution requires persistent_context visibility")
        if (
            self.execution_mode is LifecycleExecutionMode.FRESH_CONTEXT
            and self.memory_visibility_policy is LifecycleVisibilityPolicy.PERSISTENT_CONTEXT
        ):
            raise ValueError("fresh_context execution cannot use persistent_context visibility")
        return self


def _default_conditions() -> tuple[LifecycleAblationCondition, ...]:
    return (
        LifecycleAblationCondition(
            execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
            memory_visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
        ),
        LifecycleAblationCondition(
            execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
            memory_visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        ),
        LifecycleAblationCondition(
            execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
            memory_visibility_policy=LifecycleVisibilityPolicy.RAW_EVIDENCE_ONLY,
        ),
        LifecycleAblationCondition(
            execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
            memory_visibility_policy=LifecycleVisibilityPolicy.CURRENT_RELEASE_ONLY,
        ),
    )


class LifecycleAblationLimits(StrictModel):
    max_trials: PositiveInt
    max_concurrency: Literal[1] = 1
    max_estimated_cost_usd: NonNegativeFloat | None = None


class LifecycleAblationStudyDesign(StrictModel):
    interpretation: Literal["descriptive_calibration"]
    turn_budget_scope: Literal["per_session"]
    execution_order: Literal["deterministic_sequential_plan_order"]
    randomized: Literal[False]
    counterbalanced: Literal[False]
    causal_effects_supported: Literal[False]


class LifecycleAblationManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    experiment_id: NonEmptyStr
    lifecycle_template_id: NonEmptyStr
    variants: tuple[NonEmptyStr, ...]
    agents: tuple[AgentConfig, ...]
    study_design: LifecycleAblationStudyDesign
    conditions: tuple[LifecycleAblationCondition, ...] = Field(default_factory=_default_conditions)
    repetitions: PositiveInt = 1
    output_root: NonEmptyStr
    ledger_root: NonEmptyStr
    limits: LifecycleAblationLimits
    estimated_cost_per_trial_usd: NonNegativeFloat | None = None

    @field_validator("experiment_id")
    @classmethod
    def validate_safe_experiment_id(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) is None:
            raise ValueError("experiment_id must be safe for use as a directory name")
        return value

    @field_validator("variants")
    @classmethod
    def validate_variants(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("variants must not be empty")
        if len(value) != len(set(value)):
            raise ValueError("variant ids must be unique")
        return value

    @field_validator("agents")
    @classmethod
    def validate_agents(cls, value: tuple[AgentConfig, ...]) -> tuple[AgentConfig, ...]:
        if not value:
            raise ValueError("agents must not be empty")
        names = [agent.name for agent in value]
        if len(names) != len(set(names)):
            raise ValueError("agent names must be unique")
        for agent in value:
            if agent.adapter not in {"tool_loop", "pydantic_ai"}:
                raise ValueError("lifecycle ablations require tool_loop or pydantic_ai adapters")
            if agent.client is not None:
                raise ValueError("lifecycle ablations do not yet accept custom client configuration")
            if agent.system_prompt_file is not None:
                raise ValueError("lifecycle ablations use the lifecycle-owned system prompt")
            unknown_parameters = sorted(set(agent.parameters) - {"max_turns_per_session"})
            if unknown_parameters:
                raise ValueError(
                    "unsupported lifecycle agent parameters: "
                    f"{', '.join(unknown_parameters)}; use max_turns_per_session because total trial budgets "
                    "are not controlled"
                )
            max_turns = agent.parameters.get("max_turns_per_session")
            if max_turns is None:
                raise ValueError("lifecycle agent max_turns_per_session is required")
            if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 1:
                raise ValueError("lifecycle agent max_turns_per_session must be a positive integer")
        return value

    @field_validator("conditions")
    @classmethod
    def validate_conditions(
        cls,
        value: tuple[LifecycleAblationCondition, ...],
    ) -> tuple[LifecycleAblationCondition, ...]:
        if not value:
            raise ValueError("conditions must not be empty")
        identities = [(condition.execution_mode, condition.memory_visibility_policy) for condition in value]
        if len(identities) != len(set(identities)):
            raise ValueError("ablation conditions must be unique")
        return value

    @model_validator(mode="after")
    def validate_cost_limit(self) -> LifecycleAblationManifest:
        if self.limits.max_estimated_cost_usd is not None and self.estimated_cost_per_trial_usd is None:
            raise ValueError("estimated_cost_per_trial_usd is required when a cost limit is set")
        return self


class LifecycleRuntimeProvenance(StrictModel):
    adapter: Literal["tool_loop", "pydantic_ai"]
    provider: NonEmptyStr
    distributions: tuple[NonEmptyStr, ...]
    dependency_inventory_sha256: NonEmptyStr

    @field_validator("dependency_inventory_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @model_validator(mode="after")
    def validate_distributions(self) -> LifecycleRuntimeProvenance:
        if not self.distributions:
            raise ValueError("runtime provenance requires dependency distributions")
        if tuple(sorted(set(self.distributions))) != self.distributions:
            raise ValueError("runtime provenance distributions must be sorted and unique")
        return self


class LifecycleAblationTrial(StrictModel):
    trial_id: NonEmptyStr
    variant_id: NonEmptyStr
    adaptation: AdaptationProvenance
    lifecycle_id: NonEmptyStr
    world_id: NonEmptyStr
    spec_sha256: NonEmptyStr
    package_sha256: NonEmptyStr
    agent: AgentConfig
    runtime_provenance: LifecycleRuntimeProvenance
    max_turns_per_session: PositiveInt
    execution_mode: LifecycleExecutionMode
    memory_visibility_policy: LifecycleVisibilityPolicy
    repetition: PositiveInt
    package_dir: NonEmptyStr
    run_dir: NonEmptyStr
    ledger_path: NonEmptyStr

    @field_validator("spec_sha256", "package_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)


class LifecycleAblationCodeProvenance(StrictModel):
    repository_commit: NonEmptyStr
    source_inventory_sha256: NonEmptyStr
    planner_source_sha256: NonEmptyStr
    lifecycle_runtime_source_sha256: NonEmptyStr
    local_runner_source_sha256: NonEmptyStr
    trial_importer_source_sha256: NonEmptyStr
    verifier_entrypoint_qualified_name: NonEmptyStr
    verifier_entrypoint_source_sha256: NonEmptyStr
    verifier_qualified_name: NonEmptyStr
    verifier_source_sha256: NonEmptyStr

    @field_validator(
        "planner_source_sha256",
        "lifecycle_runtime_source_sha256",
        "local_runner_source_sha256",
        "trial_importer_source_sha256",
        "source_inventory_sha256",
        "verifier_entrypoint_source_sha256",
        "verifier_source_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)


class LifecycleAblationPlan(StrictModel):
    schema_version: Literal["1"] = "1"
    experiment_id: NonEmptyStr
    manifest_sha256: NonEmptyStr
    plan_sha256: NonEmptyStr
    study_design: LifecycleAblationStudyDesign
    code_provenance: LifecycleAblationCodeProvenance
    trial_count: NonNegativeInt
    planned_estimated_cost_usd: NonNegativeFloat | None = None
    trials: tuple[LifecycleAblationTrial, ...]

    @model_validator(mode="after")
    def validate_trial_count(self) -> LifecycleAblationPlan:
        if self.trial_count != len(self.trials):
            raise ValueError("trial_count must equal the number of planned trials")
        expected = _canonical_sha256(self.model_dump(mode="json", exclude={"plan_sha256"}))
        if self.plan_sha256 != expected:
            raise ValueError("plan_sha256 must bind the canonical expanded lifecycle plan")
        return self


class LifecycleAblationRunResult(StrictModel):
    schema_version: Literal["1"] = "1"
    experiment_id: NonEmptyStr
    plan_sha256: NonEmptyStr
    run_root: NonEmptyStr
    ledger_root: NonEmptyStr
    planned_trials: NonNegativeInt
    executed_trials: NonNegativeInt
    imported_orphans: NonNegativeInt
    skipped_trials: NonNegativeInt
    failed_trials: NonNegativeInt
    trial_ids: list[NonEmptyStr]
    record_paths: list[NonEmptyStr]
    summary_path: NonEmptyStr


def build_lifecycle_ablation_plan(manifest: LifecycleAblationManifest) -> LifecycleAblationPlan:
    """Expand a validated manifest into stable identities without provider calls."""
    manifest = LifecycleAblationManifest.model_validate(manifest.model_dump(mode="json"))
    try:
        known_variants = set(lifecycle_variant_ids(manifest.lifecycle_template_id))
    except KeyError as exc:
        raise ValueError(f"unknown lifecycle template: {manifest.lifecycle_template_id}") from exc
    unknown = sorted(set(manifest.variants) - known_variants)
    if unknown:
        raise ValueError(f"unknown lifecycle variants for {manifest.lifecycle_template_id}: {', '.join(unknown)}")
    adaptations = {
        variant_id: AdaptationProvenance.model_validate(
            lifecycle_variant_metadata(manifest.lifecycle_template_id, variant_id)["adaptation"]
        )
        for variant_id in manifest.variants
    }
    code_provenance = _ablation_code_provenance(manifest.lifecycle_template_id)
    runtime_provenance = {
        (agent.adapter, agent.model): LifecycleRuntimeProvenance.model_validate(
            runtime_dependency_provenance(
                adapter_kind=agent.adapter,
                model_name=agent.model,
            )
        )
        for agent in manifest.agents
    }
    package_identities: dict[str, dict[str, str]] = {}
    with tempfile.TemporaryDirectory(prefix="aec-bench-lifecycle-plan-") as temporary:
        package_root = Path(temporary)
        template = get_template(manifest.lifecycle_template_id)
        for variant_id in sorted(manifest.variants):
            package = materialize_template_lifecycle(
                template,
                package_root / variant_id,
                variant_id=variant_id,
            )
            package_identities[variant_id] = evidence_lifecycle_package_identity(package)

    manifest_sha256 = _canonical_sha256(manifest.model_dump(mode="json"))
    trials: list[LifecycleAblationTrial] = []
    for variant_id in sorted(manifest.variants):
        for agent in sorted(manifest.agents, key=lambda item: (item.name, item.adapter, item.model)):
            for condition in sorted(
                manifest.conditions,
                key=lambda item: (item.execution_mode.value, item.memory_visibility_policy.value),
            ):
                for repetition_index in range(manifest.repetitions):
                    identity = {
                        "experiment_id": manifest.experiment_id,
                        "lifecycle_template_id": manifest.lifecycle_template_id,
                        "variant_id": variant_id,
                        "adaptation": adaptations[variant_id].model_dump(mode="json"),
                        "code_provenance": code_provenance.model_dump(mode="json"),
                        "study_design": manifest.study_design.model_dump(mode="json"),
                        **package_identities[variant_id],
                        "agent": agent.model_dump(mode="json"),
                        "runtime_provenance": runtime_provenance[(agent.adapter, agent.model)].model_dump(mode="json"),
                        "execution_mode": condition.execution_mode.value,
                        "memory_visibility_policy": condition.memory_visibility_policy.value,
                        "repetition": repetition_index + 1,
                    }
                    trial_id = f"trial-{_canonical_sha256(identity)}"
                    trials.append(
                        LifecycleAblationTrial(
                            trial_id=trial_id,
                            variant_id=variant_id,
                            adaptation=adaptations[variant_id],
                            **package_identities[variant_id],
                            agent=agent,
                            runtime_provenance=runtime_provenance[(agent.adapter, agent.model)],
                            max_turns_per_session=int(agent.parameters["max_turns_per_session"]),
                            execution_mode=condition.execution_mode,
                            memory_visibility_policy=condition.memory_visibility_policy,
                            repetition=repetition_index + 1,
                            package_dir=str(Path(manifest.output_root) / "packages" / variant_id),
                            run_dir=str(Path(manifest.output_root) / "trials" / trial_id),
                            ledger_path=str(Path(manifest.ledger_root) / manifest.experiment_id / f"{trial_id}.json"),
                        )
                    )

    if len({trial.trial_id for trial in trials}) != len(trials):
        raise ValueError("planned lifecycle trial identities are not unique")
    trial_count = len(trials)
    if trial_count > manifest.limits.max_trials:
        raise ValueError(f"planned trial count {trial_count} exceeds max_trials {manifest.limits.max_trials}")
    planned_cost = (
        float(manifest.estimated_cost_per_trial_usd) * trial_count
        if manifest.estimated_cost_per_trial_usd is not None
        else None
    )
    if (
        planned_cost is not None
        and manifest.limits.max_estimated_cost_usd is not None
        and planned_cost > manifest.limits.max_estimated_cost_usd
    ):
        raise ValueError(
            f"planned estimated cost {planned_cost} exceeds limit {manifest.limits.max_estimated_cost_usd}"
        )
    plan_payload = {
        "schema_version": "1",
        "experiment_id": manifest.experiment_id,
        "manifest_sha256": manifest_sha256,
        "study_design": manifest.study_design.model_dump(mode="json"),
        "code_provenance": code_provenance.model_dump(mode="json"),
        "trial_count": trial_count,
        "planned_estimated_cost_usd": planned_cost,
        "trials": [trial.model_dump(mode="json") for trial in trials],
    }
    return LifecycleAblationPlan.model_validate(
        {
            **plan_payload,
            "plan_sha256": _canonical_sha256(plan_payload),
        }
    )


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ablation_code_provenance(template_id: str) -> LifecycleAblationCodeProvenance:
    planner_path = Path(__file__).resolve()
    lifecycle_runtime_path = planner_path.with_name("evidence_lifecycle.py")
    local_runner_path = Path(inspect.getsourcefile(run_local_evidence_lifecycle_fresh_context) or "")
    importer_path = planner_path.with_name("evidence_lifecycle_trial_record.py")
    verifier_entrypoint_path = Path(inspect.getsourcefile(verify_template_lifecycle) or "")
    verifier = registered_lifecycle_verifier(template_id)
    verifier_path = Path(inspect.getsourcefile(verifier) or "")
    paths = {
        "planner_source_sha256": planner_path,
        "lifecycle_runtime_source_sha256": lifecycle_runtime_path,
        "local_runner_source_sha256": local_runner_path,
        "trial_importer_source_sha256": importer_path,
        "verifier_entrypoint_source_sha256": verifier_entrypoint_path,
        "verifier_source_sha256": verifier_path,
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise ValueError(f"lifecycle ablation source provenance is unavailable: {', '.join(missing)}")
    repository = repository_provenance(planner_path.parent)
    return LifecycleAblationCodeProvenance(
        **{name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()},
        repository_commit=str(repository["commit"]),
        source_inventory_sha256=str(repository["source_inventory_sha256"]),
        verifier_entrypoint_qualified_name=(
            f"{verify_template_lifecycle.__module__}.{verify_template_lifecycle.__qualname__}"
        ),
        verifier_qualified_name=f"{verifier.__module__}.{verifier.__qualname__}",
    )
