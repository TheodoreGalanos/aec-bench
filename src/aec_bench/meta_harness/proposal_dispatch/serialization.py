# ABOUTME: Canonicalizes governed proposal task, Harbor job, and evidence payloads.
# ABOUTME: Validates the recorded job surface without performing provider operations.

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.contracts.task_definition import TaskDefinition

if TYPE_CHECKING:
    from aec_bench.meta_harness.proposal_dispatch.contracts import (
        GovernedProposalDispatch,
    )


def load_canonical_job_json(payload: str) -> dict[str, Any]:
    """Load one canonical Harbor job payload."""

    try:
        decoded = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("governed dispatch Harbor job JSON is invalid") from error
    if not isinstance(decoded, dict):
        raise ValueError("governed dispatch Harbor job JSON must be an object")
    if canonical_json(decoded) != payload:
        raise ValueError("governed dispatch Harbor job JSON must be canonical")
    return decoded


def load_canonical_task_json(payload: str) -> TaskDefinition:
    """Load one canonical derived task payload."""

    try:
        decoded = json.loads(payload)
        task = TaskDefinition.model_validate(decoded)
    except (TypeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("governed dispatch derived task JSON is invalid") from error
    if canonical_json(task.model_dump(mode="json")) != payload:
        raise ValueError("governed dispatch derived task JSON must be canonical")
    return task


def validate_recorded_job_surface(
    *,
    record: GovernedProposalDispatch,
    job: dict[str, Any],
) -> None:
    """Validate the exact one-task, one-agent proposal dispatch surface."""

    if job.get("n_attempts") != 1 or job.get("tasks") != [
        {"path": record.derived_task_path},
    ]:
        raise ValueError("governed dispatch Harbor job task identity differs")
    agents = job.get("agents")
    if not isinstance(agents, list) or len(agents) != 1:
        raise ValueError("governed dispatch Harbor job requires one exact agent")
    agent = agents[0]
    if not isinstance(agent, dict):
        raise ValueError("governed dispatch Harbor job agent is invalid")
    kwargs = agent.get("kwargs")
    if not isinstance(kwargs, dict) or kwargs.get("proposal_session") != record.host_config.model_dump(mode="json"):
        raise ValueError("governed dispatch Harbor job host configuration differs")
    environment = job.get("environment")
    if not isinstance(environment, dict):
        raise ValueError("governed dispatch Harbor job environment is invalid")
    environment_kwargs = environment.get("kwargs")
    expected_runtime = {
        "compute_backend": "morph",
        "runtime_archive_path": record.runtime_archive_path,
        "runtime_archive_sha256": record.runtime_archive_sha256,
        "runtime_archive_content_sha256": (record.runtime_archive_content_sha256),
    }
    if environment_kwargs != expected_runtime:
        raise ValueError("governed dispatch Harbor job runtime identity differs")


def canonical_json(payload: object) -> str:
    """Encode one JSON-compatible payload canonically."""

    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_model_bytes(model: ContentAddressedModel) -> bytes:
    """Encode one content-addressed model in ledger canonical form."""

    return (canonical_json(model.model_dump(mode="json")) + "\n").encode(
        "utf-8",
    )
