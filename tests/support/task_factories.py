# ABOUTME: Shared test factories for building valid TaskDefinition instances in aec-bench tests.
# ABOUTME: Keeps task-domain tests focused on behavior rather than repetitive contract setup.

from typing import Any

from aec_bench.contracts.task_definition import (
    Difficulty,
    EnvironmentSpec,
    Lifecycle,
    TaskDefinition,
    ToolSpec,
    VerifierSpec,
    Visibility,
)


def make_task_definition(**overrides: Any) -> TaskDefinition:
    payload = {
        "task_id": "mechanical/heat-load/demo-instance",
        "task_type": "heat-load",
        "domain": "mechanical",
        "category": "reasoning",
        "difficulty": Difficulty.MEDIUM,
        "lifecycle": Lifecycle.ACTIVE,
        "visibility": Visibility.PUBLIC,
        "instruction": "Review the documents and write findings.",
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
        "tags": ["mechanical", "demo"],
        "metadata": {"jurisdiction": "au"},
    }
    payload.update(overrides)
    return TaskDefinition.model_validate(payload)
