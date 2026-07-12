# ABOUTME: Defines conditional-evidence request contracts, catalogue projections, and state validation.
# ABOUTME: Keeps protocol identity and action-history rules independent from lifecycle execution and storage.

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import Field, model_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.meta_harness.evidence_lifecycle_state import (
    CheckpointRunRecord,
    CheckpointRunStatus,
    EvidenceLifecycleRunState,
    EvidenceRequestActionRecord,
    EvidenceRequestOutcome,
    EvidenceRequestRejection,
    LifecycleTransitionKind,
    LifecycleTransitionRecord,
)
from aec_bench.task_world_templates.contracts import EvidenceCheckpointSpec, EvidenceLifecycleSpec


class EvidenceLifecycleError(RuntimeError):
    """Raised when a lifecycle package or checkpoint transition is invalid."""


class EvidenceRequestResolution(StrictModel):
    checkpoint_id: NonEmptyStr
    request_id: NonEmptyStr
    source_path: NonEmptyStr

    @model_validator(mode="after")
    def validate_source_path(self) -> EvidenceRequestResolution:
        path = PurePosixPath(self.source_path)
        expected = ("hidden", "evidence_requests", self.checkpoint_id, self.request_id)
        if path.is_absolute() or ".." in path.parts or path.parts != expected:
            raise ValueError("evidence request source path must match its hidden request identity")
        return self


class EvidenceRequestResolutionManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    lifecycle_id: NonEmptyStr
    resolutions: tuple[EvidenceRequestResolution, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_resolutions(self) -> EvidenceRequestResolutionManifest:
        identities = [(item.checkpoint_id, item.request_id) for item in self.resolutions]
        if len(identities) != len(set(identities)):
            raise ValueError("evidence request resolutions must have unique identities")
        return self


_EVIDENCE_REQUEST_PROTOCOL = {
    "schema_version": "1",
    "tool": {
        "name": "request_evidence",
        "arguments": ["checkpoint_id", "request_id", "reason"],
    },
    "catalog_path": "workspace/checkpoints/<checkpoint_id>/evidence-requests.json",
    "canonical_transaction_path": "evidence_requests/<action_id>",
    "workspace_release_path": "workspace/inbox/<checkpoint_id>/requests/<request_id>",
    "budget_rule": "first_successful_unique_request_consumes_one",
    "duplicate_rule": "already_released_consumes_zero",
    "rejection_rule": "rejections_consume_zero_and_release_nothing",
    "call_validation_rule": "malformed_or_blank_arguments_fail_without_lifecycle_action",
    "rejection_codes": [rejection.value for rejection in EvidenceRequestRejection],
    "state_projection": "catalog_identity_budget_and_released_artifact_hashes",
}


def evidence_request_protocol_identity() -> dict[str, str]:
    """Return the versioned hash of model-visible conditional evidence semantics."""
    encoded = json.dumps(
        _EVIDENCE_REQUEST_PROTOCOL,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "schema_version": str(_EVIDENCE_REQUEST_PROTOCOL["schema_version"]),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def validate_evidence_request_run_state(
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
) -> None:
    """Validate action history against its public catalogue without mutating a run."""
    if state.schema_version == "3" and any(checkpoint.evidence_request_actions for checkpoint in state.checkpoint_runs):
        raise EvidenceLifecycleError("v3 lifecycle state cannot contain evidence request actions")
    _validate_evidence_request_state_contract(state, spec)


def evidence_request_catalog_payload(
    checkpoint: EvidenceCheckpointSpec,
    checkpoint_run: CheckpointRunRecord,
) -> dict[str, Any] | None:
    """Build the model-visible conditional evidence catalogue for one checkpoint."""
    return _evidence_request_catalog(checkpoint, checkpoint_run)


def expected_evidence_request_run_artifact_paths(
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
) -> frozenset[str]:
    """Return every canonical, catalogue, and projection file justified by state."""
    checkpoint_specs = {checkpoint.checkpoint_id: checkpoint for checkpoint in spec.checkpoints}
    expected: set[str] = set()
    for checkpoint in state.checkpoint_runs:
        checkpoint_spec = checkpoint_specs[checkpoint.checkpoint_id]
        if checkpoint_spec.conditional_evidence is not None and checkpoint.status is not CheckpointRunStatus.PENDING:
            expected.add(f"workspace/checkpoints/{checkpoint.checkpoint_id}/evidence-requests.json")
        for action in checkpoint.evidence_request_actions:
            expected.add(f"evidence_requests/{action.action_id}/action.json")
            expected.add(f"evidence_requests/{action.action_id}/committed.json")
            for artifact in action.released_artifacts:
                expected.add(artifact.path)
                expected.add(f"workspace/{artifact.workspace_path}")
    return frozenset(expected)


def is_evidence_request_run_artifact_path(raw_path: str) -> bool:
    """Identify files in namespaces reserved for conditional-evidence provenance."""
    path = PurePosixPath(raw_path)
    parts = path.parts
    if path.is_absolute() or ".." in parts:
        return False
    if parts[:1] == ("evidence_requests",):
        return True
    if len(parts) >= 4 and parts[:2] == ("workspace", "inbox") and parts[3] == "requests":
        return True
    return len(parts) >= 4 and parts[:2] == ("workspace", "checkpoints") and path.name == "evidence-requests.json"


def _validate_evidence_request_state_contract(
    state: EvidenceLifecycleRunState,
    spec: EvidenceLifecycleSpec,
) -> None:
    checkpoint_specs = {checkpoint.checkpoint_id: checkpoint for checkpoint in spec.checkpoints}
    for checkpoint_run in state.checkpoint_runs:
        checkpoint_spec = checkpoint_specs[checkpoint_run.checkpoint_id]
        conditional = checkpoint_spec.conditional_evidence
        expected_budget = conditional.request_budget if conditional is not None else 0
        if checkpoint_run.evidence_request_budget != expected_budget:
            raise EvidenceLifecycleError("evidence request budget does not match the lifecycle contract")

        public_requests = (
            {request.request_id: request for request in conditional.requests} if conditional is not None else {}
        )
        remaining = expected_budget
        history: list[EvidenceRequestActionRecord] = []
        released: dict[str, EvidenceRequestActionRecord] = {}
        for action in checkpoint_run.evidence_request_actions:
            owner = next(
                (
                    attempt
                    for attempt in checkpoint_run.attempts
                    if attempt.attempt_id == action.attempt_id and attempt.session_id == action.session_id
                ),
                None,
            )
            if owner is None:
                raise EvidenceLifecycleError("evidence request action owner is not present in checkpoint attempts")
            pre_state = _evidence_request_projection_sha256(
                state,
                checkpoint_id=checkpoint_run.checkpoint_id,
                evidence_request_budget=expected_budget,
                evidence_request_budget_remaining=remaining,
                actions=history,
            )
            if action.pre_action_state_sha256 != pre_state or action.budget_before != remaining:
                raise EvidenceLifecycleError("evidence request action pre-state does not match its history")

            request = public_requests.get(action.request_id)
            released_ids = set(released)
            if action.outcome == EvidenceRequestOutcome.RELEASED:
                if action.requested_checkpoint_id != checkpoint_run.checkpoint_id or request is None:
                    raise EvidenceLifecycleError("released evidence request is not declared by its checkpoint")
                if action.request_id in released:
                    raise EvidenceLifecycleError("evidence request cannot be released more than once")
                if not set(request.prerequisite_request_ids).issubset(released_ids):
                    raise EvidenceLifecycleError("released evidence request prerequisites are incomplete")
                if remaining < 1:
                    raise EvidenceLifecycleError("released evidence request exceeds its checkpoint budget")
                _validate_released_evidence_artifact_paths(action)
                remaining -= 1
                released[action.request_id] = action
            elif action.outcome == EvidenceRequestOutcome.ALREADY_RELEASED:
                prior = released.get(action.request_id)
                if prior is None or action.released_artifacts != prior.released_artifacts:
                    raise EvidenceLifecycleError("already-released request does not match its original release")
            else:
                _validate_evidence_request_rejection(
                    action,
                    checkpoint_id=checkpoint_run.checkpoint_id,
                    request=request,
                    released_ids=released_ids,
                    remaining_budget=remaining,
                    supports_requests=conditional is not None,
                )

            history.append(action)
            post_state = _evidence_request_projection_sha256(
                state,
                checkpoint_id=checkpoint_run.checkpoint_id,
                evidence_request_budget=expected_budget,
                evidence_request_budget_remaining=remaining,
                actions=history,
            )
            if action.post_action_state_sha256 != post_state or action.budget_after != remaining:
                raise EvidenceLifecycleError("evidence request action post-state does not match its history")
        if checkpoint_run.evidence_request_budget_remaining != remaining:
            raise EvidenceLifecycleError("evidence request remaining budget does not match its history")


def _evidence_request_catalog(
    checkpoint: EvidenceCheckpointSpec,
    checkpoint_run: CheckpointRunRecord,
) -> dict[str, Any] | None:
    conditional = checkpoint.conditional_evidence
    if conditional is None:
        return None
    released_ids = {
        action.request_id
        for action in checkpoint_run.evidence_request_actions
        if action.outcome == EvidenceRequestOutcome.RELEASED
    }
    requests = []
    for request in conditional.requests:
        if request.request_id in released_ids:
            status = "released"
        elif not set(request.prerequisite_request_ids).issubset(released_ids):
            status = "prerequisites_incomplete"
        elif checkpoint_run.evidence_request_budget_remaining == 0:
            status = "budget_exhausted"
        else:
            status = "available"
        requests.append(
            {
                "request_id": request.request_id,
                "title": request.title,
                "description": request.description,
                "prerequisite_request_ids": list(request.prerequisite_request_ids),
                "status": status,
            }
        )
    return {
        "schema_version": "1",
        "checkpoint_id": checkpoint.checkpoint_id,
        "request_budget": checkpoint_run.evidence_request_budget,
        "remaining_budget": checkpoint_run.evidence_request_budget_remaining,
        "requests": requests,
    }


def _validate_released_evidence_artifact_paths(action: EvidenceRequestActionRecord) -> None:
    canonical_prefix = PurePosixPath("evidence_requests") / action.action_id / "artifacts"
    workspace_prefix = PurePosixPath("inbox") / action.checkpoint_id / "requests" / action.request_id
    for artifact in action.released_artifacts:
        canonical = PurePosixPath(artifact.path)
        workspace = PurePosixPath(artifact.workspace_path)
        try:
            canonical_relative = canonical.relative_to(canonical_prefix)
            workspace_relative = workspace.relative_to(workspace_prefix)
        except ValueError as exc:
            raise EvidenceLifecycleError("released evidence artifact path does not match its action") from exc
        if canonical_relative == PurePosixPath(".") or canonical_relative != workspace_relative:
            raise EvidenceLifecycleError("released evidence artifact projections do not match")


def _validate_evidence_request_rejection(
    action: EvidenceRequestActionRecord,
    *,
    checkpoint_id: str,
    request: Any,
    released_ids: set[str],
    remaining_budget: int,
    supports_requests: bool,
) -> None:
    rejection = action.rejection
    valid = False
    if rejection == EvidenceRequestRejection.INACTIVE_CHECKPOINT:
        valid = action.requested_checkpoint_id != checkpoint_id
    elif rejection == EvidenceRequestRejection.NOT_SUPPORTED:
        valid = action.requested_checkpoint_id == checkpoint_id and not supports_requests
    elif rejection == EvidenceRequestRejection.UNKNOWN_REQUEST:
        valid = action.requested_checkpoint_id == checkpoint_id and supports_requests and request is None
    elif rejection == EvidenceRequestRejection.PREREQUISITES_INCOMPLETE:
        valid = (
            action.requested_checkpoint_id == checkpoint_id
            and request is not None
            and not set(request.prerequisite_request_ids).issubset(released_ids)
        )
    elif rejection == EvidenceRequestRejection.BUDGET_EXHAUSTED:
        valid = (
            action.requested_checkpoint_id == checkpoint_id
            and request is not None
            and request.request_id not in released_ids
            and set(request.prerequisite_request_ids).issubset(released_ids)
            and remaining_budget == 0
        )
    if not valid:
        raise EvidenceLifecycleError("evidence request rejection does not match the action state")


def _evidence_request_state_sha256(
    state: EvidenceLifecycleRunState,
    checkpoint_id: str,
) -> str:
    checkpoint = state.checkpoint(checkpoint_id)
    return _evidence_request_projection_sha256(
        state,
        checkpoint_id=checkpoint_id,
        evidence_request_budget=checkpoint.evidence_request_budget,
        evidence_request_budget_remaining=checkpoint.evidence_request_budget_remaining,
        actions=checkpoint.evidence_request_actions,
    )


def _evidence_request_projection_sha256(
    state: EvidenceLifecycleRunState,
    *,
    checkpoint_id: str,
    evidence_request_budget: int,
    evidence_request_budget_remaining: int,
    actions: Sequence[EvidenceRequestActionRecord],
) -> str:
    released = [
        {
            "request_id": action.request_id,
            "released_artifacts": [artifact.model_dump(mode="json") for artifact in action.released_artifacts],
            "budget_after": action.budget_after,
        }
        for action in actions
        if action.outcome == EvidenceRequestOutcome.RELEASED
    ]
    payload = {
        "schema_version": "1",
        "lifecycle_id": state.lifecycle_id,
        "package_sha256": state.package_sha256,
        "checkpoint_id": checkpoint_id,
        "evidence_request_budget": evidence_request_budget,
        "evidence_request_budget_remaining": evidence_request_budget_remaining,
        "released_requests": released,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _branch_action_state_sha256(
    state: EvidenceLifecycleRunState,
    *,
    branch_index: int,
    inherited_only: bool,
) -> str:
    checkpoints = []
    for checkpoint in state.checkpoint_runs[: branch_index + 1]:
        actions = [
            action
            for action in checkpoint.evidence_request_actions
            if not inherited_only or action.inherited_from_parent
        ]
        normalized_actions = []
        for action in actions:
            payload = action.model_dump(mode="json")
            payload.pop("inherited_from_parent")
            normalized_actions.append(payload)
        checkpoints.append(
            {
                "checkpoint_id": checkpoint.checkpoint_id,
                "evidence_request_budget": checkpoint.evidence_request_budget,
                "inherited_budget_after": (actions[-1].budget_after if actions else checkpoint.evidence_request_budget),
                "actions": normalized_actions,
            }
        )
    payload = {
        "schema_version": "1",
        "lifecycle_id": state.lifecycle_id,
        "package_sha256": state.package_sha256,
        "checkpoints": checkpoints,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _checkpoint(spec: EvidenceLifecycleSpec, checkpoint_id: str) -> EvidenceCheckpointSpec:
    for checkpoint in spec.checkpoints:
        if checkpoint.checkpoint_id == checkpoint_id:
            return checkpoint
    raise EvidenceLifecycleError(f"unknown checkpoint in lifecycle state: {checkpoint_id}")


def _append_transition(
    state: EvidenceLifecycleRunState,
    *,
    kind: LifecycleTransitionKind,
    from_checkpoint_id: str | None,
    to_checkpoint_id: str | None,
    reason: str,
) -> None:
    state.transitions.append(
        LifecycleTransitionRecord(
            transition_id=f"transition-{len(state.transitions) + 1:03d}",
            kind=kind,
            from_checkpoint_id=from_checkpoint_id,
            to_checkpoint_id=to_checkpoint_id,
            reason=reason,
        )
    )
