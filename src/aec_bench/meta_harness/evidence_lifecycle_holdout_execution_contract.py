# ABOUTME: Defines the write-once run-start authority for one claimed sealed holdout execution.
# ABOUTME: Binds the claim and frozen condition to canonical private roots before adapter work begins.

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import field_validator, model_validator

from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.meta_harness.evidence_lifecycle_calibration import FrozenLifecycleCondition
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)


class LifecycleHoldoutRunStart(StrictModel):
    """Authorize one canonical run after the audit claim and before adapter execution."""

    schema_version: Literal["1"] = "1"
    run_start_sha256: NonEmptyStr
    claim_sha256: NonEmptyStr
    calibration_freeze_sha256: NonEmptyStr
    target_freeze_sha256: NonEmptyStr
    selected_condition: FrozenLifecycleCondition
    private_execution_root: NonEmptyStr
    run_dir: NonEmptyStr
    private_ledger_root: NonEmptyStr
    execution_mode: LifecycleExecutionMode
    memory_visibility_policy: LifecycleVisibilityPolicy
    python_version: NonEmptyStr
    status: Literal["authorized"] = "authorized"

    @field_validator(
        "run_start_sha256",
        "claim_sha256",
        "calibration_freeze_sha256",
        "target_freeze_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @model_validator(mode="after")
    def validate_binding(self) -> LifecycleHoldoutRunStart:
        if (
            self.execution_mode is not self.selected_condition.execution_mode
            or self.memory_visibility_policy is not self.selected_condition.memory_visibility_policy
        ):
            raise ValueError("holdout run-start mode does not match the selected condition")
        expected = _canonical_sha256(self.model_dump(mode="json", exclude={"run_start_sha256"}))
        if self.run_start_sha256 != expected:
            raise ValueError("holdout run-start hash does not bind its canonical payload")
        return self


def build_lifecycle_holdout_run_start(
    *,
    claim_sha256: str,
    calibration_freeze_sha256: str,
    target_freeze_sha256: str,
    selected_condition: FrozenLifecycleCondition,
    private_execution_root: str,
    run_dir: str,
    private_ledger_root: str,
    python_version: str,
) -> LifecycleHoldoutRunStart:
    """Build the canonical run-start marker from already validated private authority."""
    payload = {
        "schema_version": "1",
        "claim_sha256": claim_sha256,
        "calibration_freeze_sha256": calibration_freeze_sha256,
        "target_freeze_sha256": target_freeze_sha256,
        "selected_condition": selected_condition.model_dump(mode="json"),
        "private_execution_root": private_execution_root,
        "run_dir": run_dir,
        "private_ledger_root": private_ledger_root,
        "execution_mode": selected_condition.execution_mode.value,
        "memory_visibility_policy": selected_condition.memory_visibility_policy.value,
        "python_version": python_version,
        "status": "authorized",
    }
    return LifecycleHoldoutRunStart.model_validate({**payload, "run_start_sha256": _canonical_sha256(payload)})


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
