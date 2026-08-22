# ABOUTME: Tests the task-like collection of authored Learning Study protocols.
# ABOUTME: Proves strict loading, family composition, stable discovery, and ordinary trial compilation.

import tomllib
from pathlib import Path

import pytest

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study import LearningStudyProtocolSpec, LearningStudySpec
from aec_bench.experimentation.learning_studies.planning import CompiledExperienceStep, compile_learning_study
from aec_bench.experimentation.learning_studies.protocol_collection import (
    BUILTIN_LEARNING_STUDY_PROTOCOLS,
    iter_learning_study_protocol_dirs,
    load_learning_study_protocol,
)
from aec_bench.tasks.loader import load_task_definition

_REPOSITORY_ROOT = Path(__file__).parents[3]
_TASKS_ROOT = _REPOSITORY_ROOT / "tasks"
_AGENT = AgentConfig(name="protocol-test-agent", adapter="direct", model="fixed-test-model")
_COMPUTE = ComputeConfig(backend="local", resource_limits={"memory_mb": 512}, timeout_override=30)


def _resolve_task(task_id: str):  # noqa: ANN202
    return load_task_definition(_TASKS_ROOT / task_id, _TASKS_ROOT)


@pytest.mark.parametrize(
    ("protocol_id", "experience_count", "relation_count", "arm_count"),
    (
        ("a01-artifact-structural-transfer", 2, 1, 2),
        ("a02-artifact-applicability-boundary", 2, 1, 4),
        ("a03-artifact-retention-interference", 5, 3, 6),
        ("a04-artifact-composition", 3, 1, 5),
    ),
)
def test_builtin_protocols_load_and_compile_to_ordinary_trials(
    protocol_id: str,
    experience_count: int,
    relation_count: int,
    arm_count: int,
) -> None:
    protocol_path = BUILTIN_LEARNING_STUDY_PROTOCOLS / protocol_id

    spec = load_learning_study_protocol(protocol_path, agent=_AGENT, compute=_COMPUTE, repetitions=2)
    plan = compile_learning_study(study_run_id=f"{protocol_id}-test", spec=spec, resolve_task=_resolve_task)

    assert spec.study_id == protocol_id
    assert len(spec.experiences) == experience_count
    assert len(spec.relations) == relation_count
    assert len(spec.arms) == arm_count
    assert len(plan.arm_runs) == arm_count * 2
    assert LearningStudySpec.model_validate(spec.model_dump(mode="json", round_trip=True)) == spec
    assert all(
        step.trial.task_id in {item.task_id for item in spec.experiences}
        for arm in plan.arm_runs
        for step in arm.steps
        if isinstance(step, CompiledExperienceStep)
    )


def test_protocol_contract_round_trips_without_runtime_configuration() -> None:
    data = tomllib.loads(
        (BUILTIN_LEARNING_STUDY_PROTOCOLS / "a03-artifact-retention-interference" / "study.toml").read_text(
            encoding="utf-8"
        )
    )

    protocol = LearningStudyProtocolSpec.model_validate(data)

    assert LearningStudyProtocolSpec.model_validate(protocol.model_dump(mode="json", round_trip=True)) == protocol
    assert protocol.experiences[-2].task_id is not None
    assert protocol.experiences[-2].family_member_id is None


def test_protocol_collection_discovery_is_sorted_and_ignores_incomplete_directories(tmp_path: Path) -> None:
    for name in ("z-study", "a-study"):
        path = tmp_path / name
        path.mkdir()
        (path / "study.toml").write_text("study_id = 'placeholder'\n", encoding="utf-8")
        (path / "family.toml").write_text("family_id = 'placeholder'\n", encoding="utf-8")
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "study.toml").write_text("study_id = 'placeholder'\n", encoding="utf-8")

    assert [item.name for item in iter_learning_study_protocol_dirs(tmp_path)] == ["a-study", "z-study"]
    assert iter_learning_study_protocol_dirs(tmp_path / "missing") == ()


def test_protocol_loader_rejects_invalid_family_composition(tmp_path: Path) -> None:
    source = BUILTIN_LEARNING_STUDY_PROTOCOLS / "a01-artifact-structural-transfer"
    family_text = (source / "family.toml").read_text(encoding="utf-8")
    study_text = (source / "study.toml").read_text(encoding="utf-8")

    cases = (
        (
            "unknown-member",
            study_text.replace(
                'family_member_id = "brisbane-office-acquisition"',
                'family_member_id = "unknown-member"',
                1,
            ),
            "unknown family member",
        ),
        (
            "unknown-relation",
            study_text.replace(
                'relation_ids = ["brisbane-office-to-sydney-classroom"]',
                'relation_ids = ["unknown-relation"]',
            ),
            "unknown family relation",
        ),
        (
            "uncovered-probe",
            study_text.replace(
                'relation_ids = ["brisbane-office-to-sydney-classroom"]',
                "relation_ids = []",
            ),
            "probes without selected family relations",
        ),
        (
            "probe-role-mismatch",
            study_text.replace(
                'family_member_id = "sydney-classroom-probe"\nrole = "probe"',
                'family_member_id = "sydney-classroom-probe"\nrole = "practice"',
            ),
            "must use family member",
        ),
    )
    for name, invalid_study, message in cases:
        protocol_path = tmp_path / name
        protocol_path.mkdir()
        (protocol_path / "study.toml").write_text(invalid_study, encoding="utf-8")
        (protocol_path / "family.toml").write_text(family_text, encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            load_learning_study_protocol(protocol_path, agent=_AGENT, compute=_COMPUTE)


def test_protocol_loader_names_a_malformed_study_file(tmp_path: Path) -> None:
    protocol_path = tmp_path / "malformed"
    protocol_path.mkdir()
    (protocol_path / "study.toml").write_text("study_id = [\n", encoding="utf-8")

    with pytest.raises(ValueError, match="could not load learning study protocol"):
        load_learning_study_protocol(protocol_path, agent=_AGENT, compute=_COMPUTE)
