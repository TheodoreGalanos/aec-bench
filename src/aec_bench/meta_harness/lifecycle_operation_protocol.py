# ABOUTME: Defines the generic model-visible lifecycle-operation protocol and its stable identity.
# ABOUTME: Keeps host-owned session, storage, verifier, and reward details outside the tool schema.

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from aec_bench.meta_harness.evidence_lifecycle_state import (
    CheckpointRunRecord,
    EvidenceLifecycleRunState,
    LifecycleOperationActionRecord,
    LifecycleOperationDisposition,
    LifecycleOperationOutcome,
    LifecycleOperationRejection,
)
from aec_bench.meta_harness.evidence_request_protocol import EvidenceLifecycleError
from aec_bench.task_world_templates.contracts import (
    EvidenceCheckpointSpec,
    EvidenceLifecycleSpec,
    LifecycleOperationSpec,
)

_LIFECYCLE_OPERATION_PROTOCOL: dict[str, Any] = {
    "schema_version": "1",
    "tool": {
        "name": "execute_operation",
        "arguments": ["checkpoint_id", "operation_id", "visible_source_state_sha256", "reason"],
    },
    "catalog_path": "workspace/checkpoints/<checkpoint_id>/operations.json",
    "canonical_transaction_path": "lifecycle_operations/<action_id>",
    "workspace_projection_path": "workspace/inbox/<checkpoint_id>/operations/<action_id>",
    "budget_rule": "completed_operations_consume_one",
    "reuse_rule": "already_current_consumes_zero_and_reuses_original_artifacts",
    "rejection_rule": "typed_rejections_consume_zero_and_publish_no_result",
    "call_validation_rule": "malformed_or_blank_arguments_fail_without_lifecycle_action",
    "authority_rule": "environment_produces_evidence_only_and_never_reward_or_verifier_results",
}
_LIFECYCLE_OPERATION_ARGUMENTS = (
    "checkpoint_id",
    "operation_id",
    "visible_source_state_sha256",
    "reason",
)
_SIGNATURE_TOOL_SCHEMA_KEYS = frozenset({"name", "signature", "description"})
_PARAMETER_TOOL_SCHEMA_KEYS = frozenset({"name", "parameters", "description"})
_PARAMETER_SCHEMA_KEYS = frozenset({"type", "properties", "required", "additionalProperties", "title"})
_STRING_PROPERTY_SCHEMA_KEYS = frozenset({"type", "title"})


def lifecycle_operation_protocol_identity() -> dict[str, Any]:
    """Return the versioned hash and exact public tool identity."""
    encoded = json.dumps(_LIFECYCLE_OPERATION_PROTOCOL, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema_version": _LIFECYCLE_OPERATION_PROTOCOL["schema_version"],
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "tool": dict(_LIFECYCLE_OPERATION_PROTOCOL["tool"]),
    }


def lifecycle_operation_source_state_bytes(source_state: dict[str, Any]) -> bytes:
    """Encode model-visible source state exactly as the packaged JSON source file."""
    try:
        encoded = json.dumps(
            source_state,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("lifecycle operation source state must be deterministic JSON") from exc
    return (encoded + "\n").encode("utf-8")


def lifecycle_operation_source_identity(
    *,
    source_state: dict[str, Any],
    revision_id: str,
) -> tuple[str, str]:
    """Return the physical and revision-visible hashes for one public source state."""
    if not revision_id.strip():
        raise ValueError("lifecycle operation source revision id must not be blank")
    physical_sha256 = hashlib.sha256(lifecycle_operation_source_state_bytes(source_state)).hexdigest()
    visible_payload = {
        "schema_version": "1",
        "physical_source_state_sha256": physical_sha256,
        "revision_id": revision_id,
    }
    visible_encoded = json.dumps(
        visible_payload,
        allow_nan=False,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return physical_sha256, hashlib.sha256(visible_encoded).hexdigest()


def validate_lifecycle_operation_tool_schema(tool_schema: Sequence[object]) -> None:
    """Require one exact model-visible execute-operation argument contract."""
    operation_tools = [
        tool for tool in tool_schema if isinstance(tool, dict) and tool.get("name") == "execute_operation"
    ]
    if len(operation_tools) != 1:
        raise EvidenceLifecycleError("tool schema must contain exactly one execute_operation entry")
    operation_tool = operation_tools[0]
    has_signature = "signature" in operation_tool
    has_parameters = "parameters" in operation_tool
    if has_signature == has_parameters:
        raise EvidenceLifecycleError(
            "execute_operation tool schema must declare exactly one supported argument representation"
        )
    allowed_tool_keys = _SIGNATURE_TOOL_SCHEMA_KEYS if has_signature else _PARAMETER_TOOL_SCHEMA_KEYS
    description = operation_tool.get("description")
    if not frozenset(operation_tool).issubset(allowed_tool_keys) or (
        "description" in operation_tool and not isinstance(description, str)
    ):
        raise EvidenceLifecycleError("execute_operation tool schema contains unsupported metadata or constraints")
    if has_signature:
        _validate_lifecycle_operation_signature(operation_tool["signature"])
        return
    _validate_lifecycle_operation_parameters(operation_tool["parameters"])


def _validate_lifecycle_operation_signature(raw_signature: object) -> None:
    if not isinstance(raw_signature, str) or not raw_signature.strip():
        raise EvidenceLifecycleError("execute_operation tool schema signature is malformed")
    try:
        parsed = ast.parse(f"def _execute_operation{raw_signature}:\n    pass\n")
    except SyntaxError as exc:
        raise EvidenceLifecycleError("execute_operation tool schema signature is malformed") from exc
    if len(parsed.body) != 1 or not isinstance(parsed.body[0], ast.FunctionDef):
        raise EvidenceLifecycleError("execute_operation tool schema signature is malformed")
    arguments = parsed.body[0].args
    positional = arguments.args
    valid_shape = (
        not arguments.posonlyargs
        and arguments.vararg is None
        and not arguments.kwonlyargs
        and arguments.kwarg is None
        and not arguments.defaults
        and not arguments.kw_defaults
        and tuple(argument.arg for argument in positional) == _LIFECYCLE_OPERATION_ARGUMENTS
        and all(_is_string_annotation(argument.annotation) for argument in positional)
    )
    if not valid_shape:
        raise EvidenceLifecycleError(
            "execute_operation tool schema must declare exactly four ordered required string arguments"
        )


def _validate_lifecycle_operation_parameters(raw_parameters: object) -> None:
    if not isinstance(raw_parameters, dict) or raw_parameters.get("type") != "object":
        raise EvidenceLifecycleError("execute_operation tool schema parameters are malformed")
    title = raw_parameters.get("title")
    if not frozenset(raw_parameters).issubset(_PARAMETER_SCHEMA_KEYS) or (
        "title" in raw_parameters and not isinstance(title, str)
    ):
        raise EvidenceLifecycleError("execute_operation tool schema parameters contain unsupported constraints")
    properties = raw_parameters.get("properties")
    required = raw_parameters.get("required")
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise EvidenceLifecycleError("execute_operation tool schema parameters are malformed")
    valid_shape = (
        frozenset(properties) == frozenset(_LIFECYCLE_OPERATION_ARGUMENTS)
        and tuple(required) == _LIFECYCLE_OPERATION_ARGUMENTS
        and all(_is_unconstrained_string_property(properties[argument]) for argument in _LIFECYCLE_OPERATION_ARGUMENTS)
        and raw_parameters.get("additionalProperties", False) is False
    )
    if not valid_shape:
        raise EvidenceLifecycleError(
            "execute_operation tool schema must declare exactly four required string properties in public order"
        )


def _is_unconstrained_string_property(raw_property: object) -> bool:
    if not isinstance(raw_property, dict) or raw_property.get("type") != "string":
        return False
    title = raw_property.get("title")
    return frozenset(raw_property).issubset(_STRING_PROPERTY_SCHEMA_KEYS) and (
        "title" not in raw_property or isinstance(title, str)
    )


def _is_string_annotation(annotation: ast.expr | None) -> bool:
    return (isinstance(annotation, ast.Name) and annotation.id == "str") or (
        isinstance(annotation, ast.Constant) and annotation.value == "str"
    )


@dataclass(frozen=True)
class LifecycleOperationSourceContext:
    revision_id: str
    package_dir: Path
    physical_source_state_sha256: str
    visible_source_state_sha256: str
    source_state: dict[str, Any]


@dataclass(frozen=True)
class LifecycleOperationPlan:
    operation_id: str
    operation_kind: str
    disposition: LifecycleOperationDisposition
    source_before: LifecycleOperationSourceContext
    source_after: LifecycleOperationSourceContext
    input_projection_sha256: str
    prerequisite_action_ids: tuple[str, ...]
    model_visible_artifact_paths: tuple[str, ...]
    payload: dict[str, Any]


class LifecycleOperationResolver(Protocol):
    package_dir: Path

    def current_source(self, actions: Sequence[LifecycleOperationActionRecord]) -> LifecycleOperationSourceContext: ...

    def plan(
        self,
        operation: LifecycleOperationSpec,
        actions: Sequence[LifecycleOperationActionRecord],
    ) -> LifecycleOperationPlan: ...

    def execute(self, plan: LifecycleOperationPlan, artifact_dir: Path) -> None: ...


class LifecycleOperationPrerequisiteError(EvidenceLifecycleError):
    """Report that an operation lacks a current dependency result."""


def current_lifecycle_operation_action(
    actions: Sequence[LifecycleOperationActionRecord],
    plan: LifecycleOperationPlan,
) -> LifecycleOperationActionRecord | None:
    """Return the canonical completed action matching one current dependency projection."""
    return next(
        (
            action
            for action in reversed(actions)
            if action.operation_id == plan.operation_id
            and action.outcome == LifecycleOperationOutcome.COMPLETED
            and action.input_projection_sha256 == plan.input_projection_sha256
            and action.prerequisite_action_ids == plan.prerequisite_action_ids
        ),
        None,
    )


def validate_lifecycle_operation_run_state(state: EvidenceLifecycleRunState, spec: EvidenceLifecycleSpec) -> None:
    """Replay generic v5 operation ownership, budgets, source continuity, and state hashes."""
    supports_operations = any(checkpoint.conditional_operations is not None for checkpoint in spec.checkpoints)
    if supports_operations and state.schema_version != "5":
        raise EvidenceLifecycleError("operation-capable lifecycle requires v5 state")
    if not supports_operations and state.schema_version == "5":
        raise EvidenceLifecycleError("v5 lifecycle state requires a declared operation catalogue")
    state_checkpoint_ids = [checkpoint.checkpoint_id for checkpoint in state.checkpoint_runs]
    spec_checkpoint_ids = [checkpoint.checkpoint_id for checkpoint in spec.checkpoints]
    if state_checkpoint_ids != spec_checkpoint_ids:
        raise EvidenceLifecycleError("operation checkpoint state does not match the lifecycle contract")

    prior_actions: list[LifecycleOperationActionRecord] = []
    prior_actions_by_id: dict[str, LifecycleOperationActionRecord] = {}
    completed_operation_ids: set[str] = set()
    for checkpoint_run, checkpoint_spec in zip(state.checkpoint_runs, spec.checkpoints, strict=True):
        expected_budget = (
            checkpoint_spec.conditional_operations.operation_budget
            if checkpoint_spec.conditional_operations is not None
            else 0
        )
        if checkpoint_run.operation_budget != expected_budget:
            raise EvidenceLifecycleError("operation budget does not match the lifecycle contract")
        remaining_budget = expected_budget
        for action in checkpoint_run.operation_actions:
            _validate_operation_attempt_owner(checkpoint_run, action)
            operation = _validate_operation_public_contract(
                checkpoint_spec,
                action,
                completed_operation_ids=completed_operation_ids,
            )
            if action.budget_before != remaining_budget:
                raise EvidenceLifecycleError("operation action budget chain does not match the lifecycle contract")
            if prior_actions:
                prior = prior_actions[-1]
                if (
                    action.visible_source_state_before_sha256 != prior.visible_source_state_after_sha256
                    or action.physical_source_state_before_sha256 != prior.physical_source_state_after_sha256
                ):
                    raise EvidenceLifecycleError("operation action source history is not continuous")
            if action.outcome in {
                LifecycleOperationOutcome.REJECTED,
                LifecycleOperationOutcome.ALREADY_CURRENT,
            } and (
                action.visible_source_state_after_sha256 != action.visible_source_state_before_sha256
                or action.physical_source_state_after_sha256 != action.physical_source_state_before_sha256
            ):
                raise EvidenceLifecycleError("zero-cost operation action cannot change the current source")
            if action.disposition is not LifecycleOperationDisposition.ACTIVATED and (
                action.visible_source_state_after_sha256 != action.visible_source_state_before_sha256
                or action.physical_source_state_after_sha256 != action.physical_source_state_before_sha256
            ):
                raise EvidenceLifecycleError("non-activation operation action cannot change the current source")

            if action.outcome is LifecycleOperationOutcome.ALREADY_CURRENT:
                _validate_reused_operation_lineage(action, prior_actions_by_id)
            _validate_operation_prerequisite_lineage(
                action,
                operation=operation,
                prior_actions_by_id=prior_actions_by_id,
                checkpoint_spec=checkpoint_spec,
            )

            source_before = _state_hash_source_context(action, after=False)
            expected_pre = lifecycle_operation_state_sha256(
                state,
                checkpoint_id=action.checkpoint_id,
                source=source_before,
                operation_budget_remaining=remaining_budget,
                actions=prior_actions,
            )
            if action.pre_action_state_sha256 != expected_pre:
                raise EvidenceLifecycleError("operation pre-action state hash does not match generic replay")

            remaining_budget = action.budget_after
            source_after = _state_hash_source_context(action, after=True)
            expected_post = lifecycle_operation_state_sha256(
                state,
                checkpoint_id=action.checkpoint_id,
                source=source_after,
                operation_budget_remaining=remaining_budget,
                actions=[*prior_actions, action],
            )
            if action.post_action_state_sha256 != expected_post:
                raise EvidenceLifecycleError("operation post-action state hash does not match generic replay")

            prior_actions.append(action)
            prior_actions_by_id[action.action_id] = action
            if action.outcome in {
                LifecycleOperationOutcome.COMPLETED,
                LifecycleOperationOutcome.ALREADY_CURRENT,
            }:
                completed_operation_ids.add(action.operation_id)
        if remaining_budget != checkpoint_run.operation_budget_remaining:
            raise EvidenceLifecycleError("remaining operation budget does not match generic replay")


def _validate_operation_attempt_owner(
    checkpoint: CheckpointRunRecord,
    action: LifecycleOperationActionRecord,
) -> None:
    owner = next(
        (
            attempt
            for attempt in checkpoint.attempts
            if attempt.attempt_id == action.attempt_id and attempt.session_id == action.session_id
        ),
        None,
    )
    if owner is None:
        raise EvidenceLifecycleError("operation action has no matching checkpoint attempt owner")
    if owner.inherited_from_parent != action.inherited_from_parent:
        raise EvidenceLifecycleError("operation action inheritance does not match its checkpoint attempt owner")


def _validate_operation_public_contract(
    checkpoint_spec: EvidenceCheckpointSpec,
    action: LifecycleOperationActionRecord,
    *,
    completed_operation_ids: set[str],
) -> LifecycleOperationSpec | None:
    conditional = checkpoint_spec.conditional_operations
    if action.rejection is LifecycleOperationRejection.INACTIVE_CHECKPOINT:
        if action.requested_checkpoint_id == action.checkpoint_id or action.operation_kind != "unknown":
            raise EvidenceLifecycleError("inactive-checkpoint operation rejection is not plausible")
        return None
    if action.requested_checkpoint_id != action.checkpoint_id:
        raise EvidenceLifecycleError("non-inactive operation action targets a different checkpoint")
    if conditional is None:
        if (
            action.outcome is not LifecycleOperationOutcome.REJECTED
            or action.rejection is not LifecycleOperationRejection.NOT_SUPPORTED
            or action.operation_kind != "unknown"
        ):
            raise EvidenceLifecycleError("unsupported-checkpoint operation action is not plausible")
        return None
    operation = next((item for item in conditional.operations if item.operation_id == action.operation_id), None)
    if operation is None:
        if (
            action.outcome is not LifecycleOperationOutcome.REJECTED
            or action.rejection is not LifecycleOperationRejection.UNKNOWN_OPERATION
            or action.operation_kind != "unknown"
        ):
            raise EvidenceLifecycleError("operation action is absent from the public operation catalogue")
        return None
    if action.operation_kind != operation.kind:
        raise EvidenceLifecycleError("operation action kind does not match the public operation catalogue")
    if action.rejection in {
        LifecycleOperationRejection.INACTIVE_CHECKPOINT,
        LifecycleOperationRejection.NOT_SUPPORTED,
        LifecycleOperationRejection.UNKNOWN_OPERATION,
    }:
        raise EvidenceLifecycleError("known operation records an implausible rejection kind")

    prerequisites_complete = set(operation.prerequisite_operation_ids).issubset(completed_operation_ids)
    if not prerequisites_complete and not (
        action.outcome is LifecycleOperationOutcome.REJECTED
        and action.rejection
        in {
            LifecycleOperationRejection.PREREQUISITES_INCOMPLETE,
            LifecycleOperationRejection.STALE_VISIBLE_SOURCE,
        }
    ):
        raise EvidenceLifecycleError("operation action bypasses incomplete public prerequisites")
    if action.rejection is LifecycleOperationRejection.BUDGET_EXHAUSTED and action.budget_before != 0:
        raise EvidenceLifecycleError("budget-exhausted operation rejection retains available budget")
    return operation


def _validate_operation_prerequisite_lineage(
    action: LifecycleOperationActionRecord,
    *,
    operation: LifecycleOperationSpec | None,
    prior_actions_by_id: dict[str, LifecycleOperationActionRecord],
    checkpoint_spec: EvidenceCheckpointSpec,
) -> None:
    if len(action.prerequisite_action_ids) != len(set(action.prerequisite_action_ids)):
        raise EvidenceLifecycleError("operation prerequisite action ids must be unique")
    if action.outcome is LifecycleOperationOutcome.REJECTED:
        if action.prerequisite_action_ids:
            raise EvidenceLifecycleError("rejected operation cannot retain prerequisite actions")
        return
    if operation is None:
        raise EvidenceLifecycleError("successful operation is absent from the public operation catalogue")
    allowed_operation_ids = _operation_prerequisite_closure(checkpoint_spec, operation.operation_id)
    for prerequisite_action_id in action.prerequisite_action_ids:
        prerequisite = prior_actions_by_id.get(prerequisite_action_id)
        if prerequisite is None or prerequisite.outcome is not LifecycleOperationOutcome.COMPLETED:
            raise EvidenceLifecycleError("operation prerequisite does not identify a prior completed action")
        if prerequisite.operation_id not in allowed_operation_ids:
            raise EvidenceLifecycleError("operation prerequisite action is outside the public prerequisite graph")


def _operation_prerequisite_closure(checkpoint_spec: EvidenceCheckpointSpec, operation_id: str) -> set[str]:
    conditional = checkpoint_spec.conditional_operations
    if conditional is None:
        return set()
    operations = {operation.operation_id: operation for operation in conditional.operations}
    closure: set[str] = set()

    def visit(current_id: str) -> None:
        current = operations[current_id]
        for prerequisite_id in current.prerequisite_operation_ids:
            if prerequisite_id in closure:
                continue
            closure.add(prerequisite_id)
            visit(prerequisite_id)

    visit(operation_id)
    return closure


def _validate_reused_operation_lineage(
    action: LifecycleOperationActionRecord,
    prior_actions_by_id: dict[str, LifecycleOperationActionRecord],
) -> None:
    retained = prior_actions_by_id.get(str(action.retained_from_action_id))
    if retained is None or retained.outcome is not LifecycleOperationOutcome.COMPLETED:
        raise EvidenceLifecycleError("reused operation must retain a prior completed action")
    if (
        action.operation_id != retained.operation_id
        or action.operation_kind != retained.operation_kind
        or action.input_projection_sha256 != retained.input_projection_sha256
        or action.prerequisite_action_ids != retained.prerequisite_action_ids
        or action.artifacts != retained.artifacts
    ):
        raise EvidenceLifecycleError("reused operation does not match its retained completed action")


def _state_hash_source_context(
    action: LifecycleOperationActionRecord,
    *,
    after: bool,
) -> LifecycleOperationSourceContext:
    return LifecycleOperationSourceContext(
        revision_id="generic-replay",
        package_dir=Path("."),
        physical_source_state_sha256=(
            action.physical_source_state_after_sha256 if after else action.physical_source_state_before_sha256
        ),
        visible_source_state_sha256=(
            action.visible_source_state_after_sha256 if after else action.visible_source_state_before_sha256
        ),
        source_state={},
    )


def lifecycle_operation_state_sha256(
    state: EvidenceLifecycleRunState,
    *,
    checkpoint_id: str,
    source: LifecycleOperationSourceContext,
    operation_budget_remaining: int,
    actions: Sequence[LifecycleOperationActionRecord],
) -> str:
    """Hash the model-observable operation state without self-referential action hashes."""
    completed = [
        {
            "action_id": action.action_id,
            "operation_id": action.operation_id,
            "input_projection_sha256": action.input_projection_sha256,
            "physical_source_state_after_sha256": action.physical_source_state_after_sha256,
            "visible_source_state_after_sha256": action.visible_source_state_after_sha256,
            "artifacts": [artifact.model_dump(mode="json") for artifact in action.artifacts],
            "budget_after": action.budget_after,
        }
        for action in actions
        if action.outcome == LifecycleOperationOutcome.COMPLETED
    ]
    payload = {
        "schema_version": "1",
        "lifecycle_id": state.lifecycle_id,
        "package_sha256": state.package_sha256,
        "checkpoint_id": checkpoint_id,
        "visible_source_state_sha256": source.visible_source_state_sha256,
        "physical_source_state_sha256": source.physical_source_state_sha256,
        "operation_budget_remaining": operation_budget_remaining,
        "completed_operations": completed,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
