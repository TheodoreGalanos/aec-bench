# ABOUTME: Tests for the TaskDefinition contract and its nested task-environment models.
# ABOUTME: These tests define the expected Phase 1 boundary shape for runnable task instances.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.task_definition import (
    Difficulty,
    EnvironmentSpec,
    Lifecycle,
    TaskDefinition,
    ToolSpec,
    VerifierSpec,
    Visibility,
)


def build_task_definition(**overrides: object) -> TaskDefinition:
    payload = {
        "task_id": "electrical/voltage-drop/au-office-fitout",
        "task_type": "voltage-drop",
        "domain": "electrical",
        "category": "reasoning",
        "difficulty": Difficulty.MEDIUM,
        "lifecycle": Lifecycle.ACTIVE,
        "visibility": Visibility.PUBLIC,
        "instruction": "Review the documents and write findings to /workspace/output.jsonl.",
        "environment": EnvironmentSpec(
            dockerfile="environment/Dockerfile",
            compose_file="environment/docker-compose.yaml",
            manifest="environment/manifest.jsonl",
            build_args={"PYTHON_VERSION": "3.13"},
            tools=[
                ToolSpec(
                    name="codes_search",
                    source="environment/codes_search.py",
                    description="Search building-code references.",
                )
            ],
        ),
        "verifier": VerifierSpec(
            script="tests/test.sh",
            expected_output_path="workspace/output.jsonl",
            reward_path="logs/verifier/reward.json",
            details_path="logs/verifier/details.json",
        ),
        "timeout_seconds": 600,
        "tags": ["au", "office-fitout"],
        "metadata": {"jurisdiction": "au"},
    }
    payload.update(overrides)
    return TaskDefinition.model_validate(payload)


# --- Valid construction ---


def test_task_definition_accepts_valid_payload() -> None:
    task = build_task_definition()

    assert task.task_id == "electrical/voltage-drop/au-office-fitout"
    assert task.difficulty is Difficulty.MEDIUM
    assert task.runnable is True
    assert task.environment.tools[0].name == "codes_search"


def test_task_definition_active_is_runnable() -> None:
    task = build_task_definition(lifecycle=Lifecycle.ACTIVE)

    assert task.runnable is True


def test_task_definition_deprecated_is_runnable() -> None:
    task = build_task_definition(lifecycle=Lifecycle.DEPRECATED)

    assert task.runnable is True


# --- Lifecycle runnability ---


def test_task_definition_marks_proposed_as_not_runnable() -> None:
    task = build_task_definition(lifecycle=Lifecycle.PROPOSED)

    assert task.runnable is False


def test_task_definition_marks_retired_as_not_runnable() -> None:
    task = build_task_definition(lifecycle=Lifecycle.RETIRED)

    assert task.runnable is False


# --- Rejection tests ---


def test_task_definition_rejects_blank_instruction() -> None:
    with pytest.raises(ValidationError):
        build_task_definition(instruction="   ")


def test_task_definition_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValidationError):
        build_task_definition(timeout_seconds=0)


def test_task_definition_rejects_negative_timeout() -> None:
    with pytest.raises(ValidationError):
        build_task_definition(timeout_seconds=-1)


def test_task_definition_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        build_task_definition(surprise="oops")


def test_task_definition_rejects_blank_task_id() -> None:
    with pytest.raises(ValidationError):
        build_task_definition(task_id="  ")


def test_task_definition_rejects_blank_domain() -> None:
    with pytest.raises(ValidationError):
        build_task_definition(domain="")


# --- Nested model tests ---


def test_environment_spec_accepts_minimal_fields() -> None:
    env = EnvironmentSpec(dockerfile="Dockerfile")

    assert env.compose_file is None
    assert env.manifest is None
    assert env.build_args == {}
    assert env.tools == []


def test_environment_spec_rejects_absolute_dockerfile() -> None:
    with pytest.raises(ValidationError):
        EnvironmentSpec(dockerfile="/absolute/path/Dockerfile")


def test_tool_spec_rejects_absolute_source() -> None:
    with pytest.raises(ValidationError):
        ToolSpec(name="bash", source="/usr/bin/bash", description="Shell tool")


def test_tool_spec_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        ToolSpec(name="  ", source="tools/tool.py", description="A tool")


def test_verifier_spec_accepts_without_details_path() -> None:
    v = VerifierSpec(
        script="tests/test.sh",
        expected_output_path="workspace/output.jsonl",
        reward_path="logs/verifier/reward.json",
    )

    assert v.details_path is None


def test_verifier_spec_rejects_blank_script() -> None:
    with pytest.raises(ValidationError):
        VerifierSpec(
            script="   ",
            expected_output_path="workspace/output.jsonl",
            reward_path="logs/verifier/reward.json",
        )


# --- Round-trip serialization ---


def test_task_definition_roundtrip_serialization() -> None:
    original = build_task_definition()

    serialized = original.model_dump(mode="json")
    restored = TaskDefinition.model_validate(serialized)

    assert restored == original
    assert restored.environment.tools[0].name == "codes_search"
    assert restored.verifier.details_path == "logs/verifier/details.json"


def test_task_definition_roundtrip_with_empty_optional_collections() -> None:
    original = build_task_definition(
        environment=EnvironmentSpec(dockerfile="Dockerfile"),
        tags=[],
        metadata={},
    )

    serialized = original.model_dump(mode="json")
    restored = TaskDefinition.model_validate(serialized)

    assert restored == original
    assert restored.environment.tools == []
    assert restored.tags == []
    assert restored.metadata == {}


# --- ToolSpec.returns_image ---


def test_tool_spec_returns_image_defaults_false() -> None:
    tool = ToolSpec(name="bash", source="tools/bash.py", description="Run bash")
    assert tool.returns_image is False


def test_tool_spec_returns_image_true() -> None:
    tool = ToolSpec(
        name="chart",
        source="tools/chart.py",
        description="Chart",
        returns_image=True,
    )
    assert tool.returns_image is True


def test_tool_spec_returns_image_in_environment_spec() -> None:
    env = EnvironmentSpec(
        dockerfile="environment/Dockerfile",
        tools=[
            ToolSpec(
                name="chart",
                source="tools/chart.py",
                description="Chart",
                returns_image=True,
            ),
            ToolSpec(name="bash", source="tools/bash.py", description="Bash"),
        ],
    )
    assert env.tools[0].returns_image is True
    assert env.tools[1].returns_image is False
