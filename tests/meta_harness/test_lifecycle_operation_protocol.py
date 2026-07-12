# ABOUTME: Tests durable lifecycle-operation records and their public protocol identity.
# ABOUTME: Enforces host ownership, source binding, budget arithmetic, and non-leaking schemas.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.meta_harness.evidence_lifecycle_state import (
    CheckpointRunRecord,
    EvidenceLifecycleRunState,
    LifecycleOperationActionRecord,
    LifecycleOperationArtifact,
    LifecycleOperationDisposition,
    LifecycleOperationOutcome,
    LifecycleOperationRejection,
)
from aec_bench.meta_harness.evidence_request_protocol import EvidenceLifecycleError
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    lifecycle_operation_protocol_identity,
    validate_lifecycle_operation_tool_schema,
)

SHA = "1" * 64


def _artifact() -> LifecycleOperationArtifact:
    return LifecycleOperationArtifact(
        path="lifecycle_operations/operation-000001/artifacts/result.json",
        workspace_path="inbox/analysis/operations/operation-000001/result.json",
        sha256=SHA,
    )


def _completed_action(**updates: object) -> LifecycleOperationActionRecord:
    payload: dict[str, object] = {
        "action_id": "operation-000001",
        "sequence": 1,
        "checkpoint_id": "analysis",
        "requested_checkpoint_id": "analysis",
        "operation_id": "hydrology.design-10yr",
        "operation_kind": "run_hydrology",
        "reason": "Refresh the declared hydrology evidence.",
        "session_id": "analysis.session-001",
        "attempt_id": "analysis.attempt-001",
        "outcome": LifecycleOperationOutcome.COMPLETED,
        "rejection": None,
        "disposition": LifecycleOperationDisposition.COMPUTED,
        "visible_source_state_before_sha256": "2" * 64,
        "visible_source_state_after_sha256": "2" * 64,
        "physical_source_state_before_sha256": "3" * 64,
        "physical_source_state_after_sha256": "3" * 64,
        "input_projection_sha256": "4" * 64,
        "request_sha256": "5" * 64,
        "result_manifest_sha256": "6" * 64,
        "prerequisite_action_ids": (),
        "retained_from_action_id": None,
        "pre_action_state_sha256": "7" * 64,
        "post_action_state_sha256": "8" * 64,
        "artifacts": (_artifact(),),
        "budget_before": 3,
        "budget_consumed": 1,
        "budget_after": 2,
        "inherited_from_parent": False,
    }
    payload.update(updates)
    return LifecycleOperationActionRecord.model_validate(payload)


def test_completed_operation_binds_host_source_dependencies_and_artifacts() -> None:
    action = _completed_action()

    assert action.outcome is LifecycleOperationOutcome.COMPLETED
    assert action.disposition is LifecycleOperationDisposition.COMPUTED
    assert action.session_id == "analysis.session-001"
    assert action.attempt_id == "analysis.attempt-001"
    assert action.budget_consumed == 1
    assert action.artifacts == (_artifact(),)


def test_already_current_operation_reuses_prior_identity_without_budget() -> None:
    action = _completed_action(
        outcome="already_current",
        disposition="reused",
        result_manifest_sha256=None,
        retained_from_action_id="operation-000000",
        budget_consumed=0,
        budget_after=3,
    )

    assert action.outcome is LifecycleOperationOutcome.ALREADY_CURRENT
    assert action.retained_from_action_id == "operation-000000"


def test_rejected_operation_has_no_result_or_artifacts_and_consumes_zero() -> None:
    action = _completed_action(
        outcome="rejected",
        rejection=LifecycleOperationRejection.STALE_VISIBLE_SOURCE,
        disposition=None,
        result_manifest_sha256=None,
        artifacts=(),
        budget_consumed=0,
        budget_after=3,
    )

    assert action.rejection is LifecycleOperationRejection.STALE_VISIBLE_SOURCE
    assert action.artifacts == ()


@pytest.mark.parametrize(
    "updates",
    [
        {"budget_after": 1},
        {"request_sha256": "not-a-hash"},
        {"outcome": "completed", "rejection": "unknown_operation"},
        {"outcome": "completed", "artifacts": ()},
        {"outcome": "already_current", "retained_from_action_id": None},
        {"outcome": "rejected", "rejection": None, "artifacts": ()},
    ],
)
def test_operation_action_rejects_inconsistent_identity_and_outcomes(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _completed_action(**updates)


@pytest.mark.parametrize(
    ("path", "workspace_path"),
    [
        ("../escape", "inbox/analysis/operations/operation-000001/result.json"),
        ("/absolute", "inbox/analysis/operations/operation-000001/result.json"),
        ("lifecycle_operations/operation-000001/artifacts/result.json", "../escape"),
        ("lifecycle_operations/operation-000001/artifacts/result.json", "/absolute"),
    ],
)
def test_operation_artifacts_cannot_escape_canonical_or_workspace_namespaces(
    path: str,
    workspace_path: str,
) -> None:
    with pytest.raises(ValidationError):
        LifecycleOperationArtifact(path=path, workspace_path=workspace_path, sha256=SHA)


def test_v5_state_owns_one_contiguous_operation_history() -> None:
    action = _completed_action()
    state = EvidenceLifecycleRunState(
        schema_version="5",
        lifecycle_id="hydraulic.lifecycle",
        world_id="hydraulic.world",
        lifecycle_spec_sha256=SHA,
        package_sha256="2" * 64,
        checkpoint_runs=[
            CheckpointRunRecord(
                checkpoint_id="analysis",
                operation_budget=3,
                operation_budget_remaining=2,
                operation_actions=[action],
            )
        ],
    )

    assert state.schema_version == "5"
    assert state.checkpoint_runs[0].operation_actions == [action]


def test_v4_state_cannot_smuggle_operation_state() -> None:
    with pytest.raises(ValidationError, match="v4"):
        EvidenceLifecycleRunState(
            schema_version="4",
            lifecycle_id="hydraulic.lifecycle",
            world_id="hydraulic.world",
            lifecycle_spec_sha256=SHA,
            package_sha256="2" * 64,
            checkpoint_runs=[
                CheckpointRunRecord(
                    checkpoint_id="analysis",
                    operation_budget=3,
                    operation_budget_remaining=2,
                    operation_actions=[_completed_action()],
                )
            ],
        )


def test_protocol_identity_binds_one_four_argument_non_authoritative_tool() -> None:
    identity = lifecycle_operation_protocol_identity()

    assert identity["schema_version"] == "1"
    assert len(identity["sha256"]) == 64
    assert identity["tool"] == {
        "name": "execute_operation",
        "arguments": ["checkpoint_id", "operation_id", "visible_source_state_sha256", "reason"],
    }
    encoded = str(identity).lower()
    for forbidden in ("session_id", "attempt_id", "reward", "verifier", "expected_answer", "source_path"):
        assert forbidden not in encoded


@pytest.mark.parametrize(
    "tool",
    [
        {
            "name": "execute_operation",
            "signature": (
                "(checkpoint_id: 'str', operation_id: 'str', "
                "visible_source_state_sha256: 'str', reason: 'str') -> 'str'"
            ),
            "description": "Execute one declared operation.",
        },
        {
            "name": "execute_operation",
            "description": "Execute one declared operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "checkpoint_id": {"type": "string"},
                    "operation_id": {"type": "string"},
                    "visible_source_state_sha256": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": [
                    "checkpoint_id",
                    "operation_id",
                    "visible_source_state_sha256",
                    "reason",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "execute_operation",
            "parameters": {
                "type": "object",
                "properties": {
                    "checkpoint_id": {"type": "string"},
                    "operation_id": {"type": "string"},
                    "reason": {"type": "string"},
                    "visible_source_state_sha256": {"type": "string"},
                },
                "required": [
                    "checkpoint_id",
                    "operation_id",
                    "visible_source_state_sha256",
                    "reason",
                ],
            },
        },
        {
            "name": "execute_operation",
            "description": "Execute one declared lifecycle operation.",
            "parameters": {
                "type": "object",
                "title": "execute_operation_args",
                "properties": {
                    "checkpoint_id": {"title": "Checkpoint Id", "type": "string"},
                    "operation_id": {"title": "Operation Id", "type": "string"},
                    "reason": {"title": "Reason", "type": "string"},
                    "visible_source_state_sha256": {
                        "title": "Visible Source State Sha256",
                        "type": "string",
                    },
                },
                "required": [
                    "checkpoint_id",
                    "operation_id",
                    "visible_source_state_sha256",
                    "reason",
                ],
                "additionalProperties": False,
            },
        },
    ],
)
def test_operation_tool_schema_accepts_local_signature_and_structured_parameters(
    tool: dict[str, object],
) -> None:
    validate_lifecycle_operation_tool_schema([{"name": "list_workspace"}, tool])


@pytest.mark.parametrize(
    "tool",
    [
        {
            "name": "execute_operation",
            "signature": ("(checkpoint_id: 'str', operation_id: 'str', visible_source_state_sha256: 'str') -> 'str'"),
        },
        {
            "name": "execute_operation",
            "signature": (
                "(operation_id: 'str', checkpoint_id: 'str', "
                "visible_source_state_sha256: 'str', reason: 'str') -> 'str'"
            ),
        },
        {
            "name": "execute_operation",
            "signature": (
                "(checkpoint_id: 'str', operation_id: 'str', "
                "visible_source_state_sha256: 'str', reason: 'str', session_id: 'str') -> 'str'"
            ),
        },
        {
            "name": "execute_operation",
            "signature": (
                "(checkpoint_id: 'str', operation_id: 'str', "
                "visible_source_state_sha256: 'str', reason: 'str' = 'optional') -> 'str'"
            ),
        },
        {
            "name": "execute_operation",
            "signature": (
                "(checkpoint_id: 'str', operation_id: 'str', "
                "visible_source_state_sha256: 'bytes', reason: 'str') -> 'str'"
            ),
        },
        {
            "name": "execute_operation",
            "parameters": {
                "type": "object",
                "properties": {
                    "checkpoint_id": {"type": "string"},
                    "operation_id": {"type": "string"},
                    "visible_source_state_sha256": {"type": "string"},
                },
                "required": ["checkpoint_id", "operation_id", "visible_source_state_sha256"],
            },
        },
        {
            "name": "execute_operation",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation_id": {"type": "string"},
                    "checkpoint_id": {"type": "string"},
                    "visible_source_state_sha256": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": [
                    "operation_id",
                    "checkpoint_id",
                    "visible_source_state_sha256",
                    "reason",
                ],
            },
        },
        {
            "name": "execute_operation",
            "parameters": {
                "type": "object",
                "properties": {
                    "checkpoint_id": {"type": "string"},
                    "operation_id": {"type": "string"},
                    "visible_source_state_sha256": {"type": "string"},
                    "reason": {"type": "integer"},
                },
                "required": [
                    "checkpoint_id",
                    "operation_id",
                    "visible_source_state_sha256",
                    "reason",
                ],
            },
        },
        {
            "name": "execute_operation",
            "parameters": {
                "type": "object",
                "properties": {
                    "checkpoint_id": {"type": "string"},
                    "operation_id": {"type": "string"},
                    "visible_source_state_sha256": {"type": "string"},
                    "reason": {"type": "string"},
                    "session_id": {"type": "string"},
                },
                "required": [
                    "checkpoint_id",
                    "operation_id",
                    "visible_source_state_sha256",
                    "reason",
                    "session_id",
                ],
            },
        },
    ],
)
def test_operation_tool_schema_rejects_argument_contract_drift(tool: dict[str, object]) -> None:
    with pytest.raises(EvidenceLifecycleError, match="execute_operation tool schema"):
        validate_lifecycle_operation_tool_schema([tool])


@pytest.mark.parametrize(
    ("scope", "argument", "constraint"),
    [
        ("property", "checkpoint_id", {"enum": []}),
        ("property", "operation_id", {"maxLength": 0}),
        ("property", "visible_source_state_sha256", {"pattern": "^$"}),
        ("property", "reason", {"const": ""}),
        ("object", None, {"maxProperties": 0}),
    ],
)
def test_operation_tool_schema_rejects_semantic_argument_constraints(
    scope: str,
    argument: str | None,
    constraint: dict[str, object],
) -> None:
    properties: dict[str, dict[str, object]] = {
        name: {"type": "string"} for name in ("checkpoint_id", "operation_id", "visible_source_state_sha256", "reason")
    }
    parameters: dict[str, object] = {
        "type": "object",
        "properties": properties,
        "required": [
            "checkpoint_id",
            "operation_id",
            "visible_source_state_sha256",
            "reason",
        ],
    }
    if scope == "property":
        assert argument is not None
        properties[argument].update(constraint)
    else:
        parameters.update(constraint)

    with pytest.raises(EvidenceLifecycleError, match="execute_operation tool schema"):
        validate_lifecycle_operation_tool_schema([{"name": "execute_operation", "parameters": parameters}])


def test_operation_tool_schema_rejects_missing_and_duplicate_entries() -> None:
    with pytest.raises(EvidenceLifecycleError, match="exactly one execute_operation"):
        validate_lifecycle_operation_tool_schema([{"name": "list_workspace"}])

    valid = {
        "name": "execute_operation",
        "signature": (
            "(checkpoint_id: 'str', operation_id: 'str', visible_source_state_sha256: 'str', reason: 'str') -> 'str'"
        ),
    }
    with pytest.raises(EvidenceLifecycleError, match="exactly one execute_operation"):
        validate_lifecycle_operation_tool_schema([valid, dict(valid)])
