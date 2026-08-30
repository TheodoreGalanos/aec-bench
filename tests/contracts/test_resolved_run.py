# ABOUTME: Tests resolution of user experiment configuration into one requested run condition.
# ABOUTME: Covers identity joins, exact task references, duplicate rejection, timestamps, and secret boundaries.

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.dataset import BundleDatasetRef
from aec_bench.contracts.experiment_manifest import (
    AgentCondition,
    AgentConfig,
    ComputeConfig,
    ExperimentManifest,
    ReviewerConfig,
    TaskSelector,
)
from aec_bench.contracts.identity import EntityIdentity, EntityKind, new_entity_id
from aec_bench.contracts.resolved_run import ResolvedRunSpec, resolve_run_spec
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef
from aec_bench.contracts.trial_record import AuthorityExpectation, ProviderRoute


def _identity(kind: EntityKind, key: str, version: int = 1) -> EntityIdentity:
    return EntityIdentity(id=new_entity_id(kind), key=key, version=version)


def _snapshot(task_id: str, *, version: int = 1) -> ArtifactTaskSnapshotRef:
    identity = _identity(EntityKind.TASK, task_id, version)
    digest = "a" * 64
    return ArtifactTaskSnapshotRef(
        task_id=task_id,
        task_identity=identity,
        artifact=ArtifactRef(
            artifact_id=f"artifacts/sha256/{digest}",
            sha256=digest,
            size_bytes=1,
            media_type="application/vnd.aec-bench.task-snapshot+tar+zstd",
        ),
    )


def _dataset() -> BundleDatasetRef:
    digest = "b" * 64
    return BundleDatasetRef(
        dataset_id="pump-suite",
        artifact=ArtifactRef(
            artifact_id=f"artifacts/sha256/{digest}",
            sha256=digest,
            size_bytes=1,
            media_type="application/vnd.aec-bench.dataset-bundle+tar+gzip",
        ),
    )


def _manifest(
    *,
    agents: list[AgentConfig] | None = None,
    repetitions: int = 2,
    dataset: BundleDatasetRef | None = None,
    disable_verification: bool = False,
    reviewer: ReviewerConfig | None = None,
) -> ExperimentManifest:
    return ExperimentManifest(
        experiment_id="pump-study",
        name="Pump study",
        tasks=TaskSelector(dataset=dataset, visibility_filter=[Visibility.PUBLIC, Visibility.PRIVATE]),
        agents=agents or [AgentConfig(name="baseline", adapter="direct", model="model-a")],
        compute=ComputeConfig(backend="local", resource_limits={"cpu": 2}),
        repetitions=repetitions,
        disable_verification=disable_verification,
        reviewer=reviewer,
    )


def _condition(agent: AgentConfig, *, model: str | None = None, key: str | None = None) -> AgentCondition:
    return AgentCondition(
        identity=_identity(EntityKind.AGENT_CONDITION, key or agent.name),
        adapter=agent.adapter,
        model=model or agent.model,
        client=agent.client,
        system_prompt=agent.system_prompt,
        parameters=agent.parameters,
    )


def _conditions(manifest: ExperimentManifest, *, models: list[str] | None = None) -> list[AgentCondition]:
    return [_condition(agent, model=models[index] if models else None) for index, agent in enumerate(manifest.agents)]


def test_resolve_run_spec_retains_requested_json_shape() -> None:
    experiment = _identity(EntityKind.EXPERIMENT, "pump-study", version=3)
    run = _identity(EntityKind.RUN, "pump-study-august")
    manifest = _manifest(
        dataset=_dataset(),
        disable_verification=True,
        reviewer=ReviewerConfig(enabled=True, required=True),
    )
    spec = resolve_run_spec(
        manifest,
        task_releases=[_snapshot("civil/pump-sizing", version=4)],
        agent_conditions=_conditions(manifest),
        experiment_identity=experiment,
        run_identity=run,
        created_at=datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
        created_by="theo",
        expected_authorities=(AuthorityExpectation(authority_kind="provider", protocol="provider/1"),),
        provider_route_request=ProviderRoute(provider="anthropic", route="anthropic-api"),
    )

    assert isinstance(spec, ResolvedRunSpec)
    assert spec.schema_version == 1
    assert spec.experiment_identity == experiment
    assert spec.run_identity == run
    assert spec.run_id == run.id
    assert spec.run_key == run.key
    task_identity = spec.task_releases[0].task_identity
    assert task_identity is not None
    assert task_identity.key == "civil/pump-sizing"
    assert task_identity.version == 4
    assert spec.agent_conditions[0].identity.id.version == 7
    assert spec.agent_conditions[0].model == "model-a"
    assert spec.dataset == manifest.tasks.dataset
    assert spec.repetitions == 2
    assert spec.verification_enabled is False
    assert spec.reviewer == manifest.reviewer
    assert spec.visibility == (Visibility.PUBLIC, Visibility.PRIVATE)
    assert spec.provider_route_request == ProviderRoute(provider="anthropic", route="anthropic-api")
    assert ResolvedRunSpec.model_validate_json(spec.model_dump_json()) == spec


def test_resolve_run_spec_retains_resolved_model_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_NAME", "model-from-environment")
    manifest = _manifest(agents=[AgentConfig(name="baseline", adapter="direct", model="env:MODEL_NAME")])
    spec = resolve_run_spec(
        manifest,
        task_releases=[_snapshot("civil/pump-sizing")],
        agent_conditions=[_condition(manifest.agents[0])],
        experiment_identity=_identity(EntityKind.EXPERIMENT, "pump-study"),
        run_identity=_identity(EntityKind.RUN, "pump-study-run"),
        created_at=datetime.now(UTC),
        created_by="theo",
    )

    assert spec.agent_conditions[0].model == "model-from-environment"


def test_resolve_run_spec_retains_named_secret_environment_reference() -> None:
    manifest = _manifest(
        agents=[
            AgentConfig(
                name="baseline",
                adapter="direct",
                model="model-a",
                parameters={"api_key_env": "MODEL_API_KEY"},
            )
        ]
    )
    spec = resolve_run_spec(
        manifest,
        task_releases=[_snapshot("civil/pump-sizing")],
        agent_conditions=[_condition(manifest.agents[0])],
        experiment_identity=_identity(EntityKind.EXPERIMENT, "pump-study"),
        run_identity=_identity(EntityKind.RUN, "pump-study-run"),
        created_at=datetime.now(UTC),
        created_by="theo",
    )

    assert spec.agent_conditions[0].parameters == {"api_key_env": "MODEL_API_KEY"}


def test_resolve_run_spec_rejects_literal_secret_values() -> None:
    manifest = _manifest(
        agents=[
            AgentConfig(
                name="baseline",
                adapter="direct",
                model="model-a",
                parameters={"api_key": "literal-secret"},
            )
        ]
    )

    with pytest.raises(ValueError, match="secret value"):
        resolve_run_spec(
            manifest,
            task_releases=[_snapshot("civil/pump-sizing")],
            agent_conditions=[_condition(manifest.agents[0])],
            experiment_identity=_identity(EntityKind.EXPERIMENT, "pump-study"),
            run_identity=_identity(EntityKind.RUN, "pump-study-run"),
            created_at=datetime.now(UTC),
            created_by="theo",
        )


def test_resolved_run_spec_rejects_unresolved_task_and_secret_values() -> None:
    manifest = _manifest()
    condition = _condition(manifest.agents[0])
    with pytest.raises(ValidationError, match="task releases must include task identity"):
        ResolvedRunSpec(
            experiment_identity=_identity(EntityKind.EXPERIMENT, "pump-study"),
            run_identity=_identity(EntityKind.RUN, "pump-study-run"),
            run_name="Pump study",
            created_at=datetime.now(UTC),
            created_by="theo",
            task_releases=(
                ArtifactTaskSnapshotRef(
                    task_id="civil/pump-sizing",
                    artifact=ArtifactRef(
                        artifact_id="artifacts/sha256/" + "a" * 64,
                        sha256="a" * 64,
                        size_bytes=1,
                        media_type="application/vnd.aec-bench.task-snapshot+tar+zstd",
                    ),
                ),
            ),
            agent_conditions=(condition,),
            compute=manifest.compute,
            repetitions=manifest.repetitions,
            verification_enabled=True,
            visibility=(Visibility.PUBLIC,),
        )

    with pytest.raises(ValidationError, match="secret value"):
        ResolvedRunSpec(
            experiment_identity=_identity(EntityKind.EXPERIMENT, "pump-study"),
            run_identity=_identity(EntityKind.RUN, "pump-study-run"),
            run_name="Pump study",
            created_at=datetime.now(UTC),
            created_by="theo",
            task_releases=(_snapshot("civil/pump-sizing"),),
            agent_conditions=(condition.model_copy(update={"parameters": {"api_key": "literal-secret"}}),),
            compute=manifest.compute,
            repetitions=manifest.repetitions,
            verification_enabled=True,
            visibility=(Visibility.PUBLIC,),
        )


def test_resolve_run_spec_rejects_unresolved_system_prompt_file() -> None:
    manifest = _manifest(
        agents=[AgentConfig(name="baseline", adapter="direct", model="model-a", system_prompt_file="prompt.txt")]
    )
    with pytest.raises(ValueError, match="unresolved agent system_prompt_file"):
        resolve_run_spec(
            manifest,
            task_releases=[_snapshot("civil/pump-sizing")],
            agent_conditions=[_condition(manifest.agents[0])],
            experiment_identity=_identity(EntityKind.EXPERIMENT, "pump-study"),
            run_identity=_identity(EntityKind.RUN, "pump-study-run"),
            created_at=datetime.now(UTC),
            created_by="theo",
        )


def test_resolve_run_spec_rejects_mismatched_agent_and_seed() -> None:
    manifest = _manifest()
    with pytest.raises(ValueError, match="agent condition model"):
        resolve_run_spec(
            manifest,
            task_releases=[_snapshot("civil/pump-sizing")],
            agent_conditions=[_condition(manifest.agents[0], model="other-model")],
            experiment_identity=_identity(EntityKind.EXPERIMENT, "pump-study"),
            run_identity=_identity(EntityKind.RUN, "pump-study-run"),
            created_at=datetime.now(UTC),
            created_by="theo",
        )

    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        resolve_run_spec(
            manifest,
            task_releases=[_snapshot("civil/pump-sizing")],
            agent_conditions=[_condition(manifest.agents[0])],
            experiment_identity=_identity(EntityKind.EXPERIMENT, "pump-study"),
            run_identity=_identity(EntityKind.RUN, "pump-study-run"),
            created_at=datetime.now(UTC),
            created_by="theo",
            randomization_seed=-1,
        )


def test_resolved_run_spec_rejects_naive_created_at() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        resolve_run_spec(
            _manifest(),
            task_releases=[_snapshot("civil/pump-sizing")],
            agent_conditions=_conditions(_manifest()),
            experiment_identity=_identity(EntityKind.EXPERIMENT, "pump-study"),
            run_identity=_identity(EntityKind.RUN, "pump-study-run"),
            created_at=datetime(2026, 8, 30, 12, 0),
            created_by="theo",
        )


def test_resolve_run_spec_rejects_identity_and_reference_duplicates() -> None:
    experiment = _identity(EntityKind.EXPERIMENT, "pump-study")
    run = _identity(EntityKind.RUN, "pump-study-run")
    snapshot = _snapshot("civil/pump-sizing")

    with pytest.raises(ValidationError, match="task releases must be unique"):
        resolve_run_spec(
            _manifest(),
            task_releases=[snapshot, snapshot],
            agent_conditions=_conditions(_manifest()),
            experiment_identity=experiment,
            run_identity=run,
            created_at=datetime.now(UTC),
            created_by="theo",
        )

    with pytest.raises(ValidationError, match="agent conditions must be unique"):
        duplicate_manifest = _manifest(
            agents=[
                AgentConfig(name="baseline", adapter="direct", model="model-a"),
                AgentConfig(name="baseline", adapter="direct", model="model-b"),
            ]
        )
        resolve_run_spec(
            duplicate_manifest,
            task_releases=[snapshot],
            agent_conditions=_conditions(duplicate_manifest),
            experiment_identity=experiment,
            run_identity=run,
            created_at=datetime.now(UTC),
            created_by="theo",
        )


def test_resolve_run_spec_requires_experiment_key_match_and_distinct_run() -> None:
    with pytest.raises(ValueError, match="experiment identity key"):
        resolve_run_spec(
            _manifest(),
            task_releases=[_snapshot("civil/pump-sizing")],
            agent_conditions=_conditions(_manifest()),
            experiment_identity=_identity(EntityKind.EXPERIMENT, "other-study"),
            run_identity=_identity(EntityKind.RUN, "pump-study-run"),
            created_at=datetime.now(UTC),
            created_by="theo",
        )

    identity = _identity(EntityKind.EXPERIMENT, "pump-study")
    manifest = _manifest()
    with pytest.raises(ValidationError, match="must be distinct"):
        ResolvedRunSpec(
            experiment_identity=identity,
            run_identity=identity,
            run_name="Pump study",
            created_at=datetime.now(UTC),
            created_by="theo",
            task_releases=(_snapshot("civil/pump-sizing"),),
            agent_conditions=(_condition(manifest.agents[0]),),
            compute=ComputeConfig(backend="local"),
            repetitions=1,
            verification_enabled=True,
            visibility=(Visibility.PUBLIC,),
        )
