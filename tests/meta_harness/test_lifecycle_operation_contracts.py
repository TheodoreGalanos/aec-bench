# ABOUTME: Tests the generic bounded lifecycle-operation catalogue used by hydraulic interactions.
# ABOUTME: Keeps public operation graphs finite, path-free, and separate from evidence requests.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.task_world_templates.contracts import (
    ConditionalEvidenceSpec,
    ConditionalOperationSpec,
    EvidenceCheckpointSpec,
    EvidenceLifecycleSpec,
    EvidenceRequestSpec,
    LifecycleOperationSpec,
)


def _operation(operation_id: str, *prerequisites: str) -> LifecycleOperationSpec:
    return LifecycleOperationSpec(
        operation_id=operation_id,
        kind=operation_id.split(".", 1)[0],
        title=operation_id,
        description=f"Execute {operation_id} against the visible source state.",
        prerequisite_operation_ids=prerequisites,
    )


def _checkpoint(
    *,
    conditional_operations: ConditionalOperationSpec | None = None,
    conditional_evidence: ConditionalEvidenceSpec | None = None,
) -> EvidenceCheckpointSpec:
    return EvidenceCheckpointSpec(
        checkpoint_id="analysis",
        title="Analysis",
        release_path="releases/analysis",
        instruction_path="instructions/analysis.md",
        submission_path="submissions/analysis.json",
        conditional_operations=conditional_operations,
        conditional_evidence=conditional_evidence,
    )


def test_operation_catalogue_accepts_one_reachable_bounded_graph() -> None:
    catalogue = ConditionalOperationSpec(
        operation_budget=4,
        operations=(
            _operation("source-revision.current"),
            _operation("hydrology.major-100yr", "source-revision.current"),
            _operation("detention-outlet.major-100yr.declared-outlet", "hydrology.major-100yr"),
            _operation("network-hgl.major-100yr.declared-tailwater", "detention-outlet.major-100yr.declared-outlet"),
        ),
    )

    payload = catalogue.model_dump(mode="json")

    assert payload["operation_budget"] == 4
    assert [item["operation_id"] for item in payload["operations"]] == [
        "source-revision.current",
        "hydrology.major-100yr",
        "detention-outlet.major-100yr.declared-outlet",
        "network-hgl.major-100yr.declared-tailwater",
    ]
    assert set(payload["operations"][0]) == {
        "operation_id",
        "kind",
        "title",
        "description",
        "prerequisite_operation_ids",
    }


@pytest.mark.parametrize("operation_id", ["../escape", "/absolute", "has space", "", "a//b"])
def test_operation_ids_must_be_safe_path_segments(operation_id: str) -> None:
    with pytest.raises((ValidationError, ValueError)):
        _operation(operation_id)


def test_operation_catalogue_rejects_duplicate_unknown_and_cyclic_dependencies() -> None:
    with pytest.raises(ValidationError, match="unique"):
        ConditionalOperationSpec(operation_budget=1, operations=(_operation("hydrology.design"),) * 2)

    with pytest.raises(ValidationError, match="unknown"):
        ConditionalOperationSpec(
            operation_budget=1,
            operations=(_operation("hydrology.design", "source-revision.missing"),),
        )

    with pytest.raises(ValidationError, match="cycles"):
        ConditionalOperationSpec(
            operation_budget=2,
            operations=(
                _operation("hydrology.design", "detention.design"),
                _operation("detention.design", "hydrology.design"),
            ),
        )


def test_operation_budget_must_reach_every_prerequisite_chain() -> None:
    with pytest.raises(ValidationError, match="cannot satisfy prerequisites"):
        ConditionalOperationSpec(
            operation_budget=2,
            operations=(
                _operation("source-revision.current"),
                _operation("hydrology.design", "source-revision.current"),
                _operation("detention.design", "hydrology.design"),
            ),
        )


def test_lifecycle_rejects_mixed_evidence_and_operation_protocols() -> None:
    operation_checkpoint = _checkpoint(
        conditional_operations=ConditionalOperationSpec(
            operation_budget=1,
            operations=(_operation("hydrology.design"),),
        )
    )
    evidence_checkpoint = EvidenceCheckpointSpec(
        checkpoint_id="evidence",
        title="Evidence",
        release_path="releases/evidence",
        instruction_path="instructions/evidence.md",
        submission_path="submissions/evidence.json",
        conditional_evidence=ConditionalEvidenceSpec(
            request_budget=1,
            requests=(
                EvidenceRequestSpec(
                    request_id="survey",
                    title="Survey",
                    description="Request the survey.",
                ),
            ),
        ),
    )

    with pytest.raises(ValidationError, match="must not mix"):
        EvidenceLifecycleSpec(
            lifecycle_id="mixed.lifecycle",
            world_id="world.mixed",
            checkpoints=[operation_checkpoint, evidence_checkpoint],
        )


def test_checkpoint_rejects_both_protocols_at_once() -> None:
    with pytest.raises(ValidationError, match="must not declare both"):
        _checkpoint(
            conditional_operations=ConditionalOperationSpec(
                operation_budget=1,
                operations=(_operation("hydrology.design"),),
            ),
            conditional_evidence=ConditionalEvidenceSpec(
                request_budget=1,
                requests=(
                    EvidenceRequestSpec(
                        request_id="survey",
                        title="Survey",
                        description="Request the survey.",
                    ),
                ),
            ),
        )
