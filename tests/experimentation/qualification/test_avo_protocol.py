# ABOUTME: Tests the immutable provider-free AVO qualification protocol.
# ABOUTME: Proves split isolation, paired configuration identity, run count, and metric separation.

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from aec_bench.contracts.task_definition import Visibility
from aec_bench.experimentation.qualification.avo_protocol import (
    EF03_BASELINE_SOURCE_PATH,
    EF03_BASELINE_SOURCE_REVISION,
    EF03_BASELINE_SOURCE_SHA256,
    AVOOutcomeMeasure,
    AVOProcessMeasure,
    AVOQualificationArm,
    AVOQualificationBaselineReference,
    AVOQualificationInnerBudget,
    AVOQualificationOuterBudget,
    AVOQualificationProtocol,
    AVOQualificationRoute,
    AVOQualificationSplit,
    AVOQualificationSplitName,
)


def _split(name: str, visibility: Visibility, task_refs: tuple[str, ...]) -> AVOQualificationSplit:
    return AVOQualificationSplit(
        name=AVOQualificationSplitName(name),
        visibility=visibility,
        task_set_id=f"set-{name}",
        task_refs=task_refs,
        task_set_sha256=hashlib.sha256(name.encode()).hexdigest(),
    )


def test_protocol_pins_ef03_source_without_resolving_git() -> None:
    reference = AVOQualificationBaselineReference()

    assert reference.source_revision == EF03_BASELINE_SOURCE_REVISION
    assert reference.source_path == EF03_BASELINE_SOURCE_PATH
    assert reference.source_sha256 == EF03_BASELINE_SOURCE_SHA256


def test_protocol_accepts_two_independent_runs_and_is_content_addressed() -> None:
    protocol = _protocol()

    assert protocol.independent_seeds == (11, 29)
    assert protocol.repetitions_per_seed == 1
    assert len(protocol.content_sha256) == 64
    with pytest.raises(ValidationError):
        AVOQualificationProtocol.model_validate(
            protocol.model_dump(mode="python", exclude={"content_sha256"}) | {"independent_seeds": (11,)}
        )


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("development", _split("development", Visibility.PUBLIC, ("dev-c",)), "same development split"),
        ("host_selection", _split("host_selection", Visibility.PUBLIC, ("host-b",)), "same host_selection split"),
        (
            "qualification",
            _split("qualification", Visibility.HOLDOUT, ("qual-b",)),
            "same qualification split",
        ),
        (
            "route",
            AVOQualificationRoute(model="other-model", provider="provider", route="route"),
            "same model, provider, and route",
        ),
        (
            "outer_budget",
            AVOQualificationOuterBudget(
                max_cycles=5,
                batch_size=2,
                improvement_threshold=0.02,
                stagnation_window=3,
                structural_weight=0.3,
                strategy="hill_climb",
            ),
            "same full outer budget",
        ),
    ],
)
def test_protocol_rejects_paired_configuration_identity_drift(
    field: str,
    replacement: object,
    message: str,
) -> None:
    protocol = _protocol()
    avo_payload = protocol.avo.model_dump(mode="python")
    avo_payload[field] = replacement

    with pytest.raises(ValidationError, match=message):
        AVOQualificationProtocol.model_validate(
            protocol.model_dump(mode="python", exclude={"content_sha256"}) | {"avo": avo_payload}
        )


def test_protocol_rejects_noncanonical_or_overlapping_split_membership() -> None:
    with pytest.raises(ValidationError, match="sorted and unique"):
        _split("development", Visibility.PUBLIC, ("dev-b", "dev-a", "dev-a"))

    baseline = _protocol().baseline.model_dump(mode="python")
    baseline["host_selection"] = _split("host_selection", Visibility.PUBLIC, ("dev-a",)).model_dump(mode="python")
    with pytest.raises(ValidationError, match="split task refs must be disjoint"):
        AVOQualificationArm.model_validate(baseline)


@pytest.mark.parametrize(
    ("name", "visibility"),
    [
        ("development", Visibility.HOLDOUT),
        ("host_selection", Visibility.HOLDOUT),
        ("qualification", Visibility.PUBLIC),
    ],
)
def test_split_visibility_matches_its_role(name: str, visibility: Visibility) -> None:
    with pytest.raises(ValidationError, match="split must use"):
        _split(name, visibility, (f"{name}-a",))


def test_protocol_rejects_sealed_material_as_adaptive_feedback() -> None:
    avo_payload = _protocol().avo.model_dump(mode="python")
    avo_payload["adaptive_feedback"] = ("qualification",)

    with pytest.raises(ValidationError):
        AVOQualificationArm.model_validate(avo_payload)


def test_arm_requires_explicit_avo_inner_budget_and_baseline_reference() -> None:
    avo_payload = _protocol().avo.model_dump(mode="python")
    avo_payload["inner_budget"] = None
    with pytest.raises(ValidationError, match="explicit inner budget"):
        AVOQualificationArm.model_validate(avo_payload)

    baseline_payload = _protocol().baseline.model_dump(mode="python")
    baseline_payload["baseline"] = None
    with pytest.raises(ValidationError, match="immutable source reference"):
        AVOQualificationArm.model_validate(baseline_payload)


def test_protocol_keeps_process_and_outcome_measure_sets_separate() -> None:
    protocol_payload = _protocol().model_dump(mode="python", exclude={"content_sha256"})
    protocol_payload["process_measures"] = (AVOOutcomeMeasure.VALIDITY_RATE,)
    with pytest.raises(ValidationError, match="process_measures"):
        AVOQualificationProtocol.model_validate(protocol_payload)

    protocol_payload = _protocol().model_dump(mode="python", exclude={"content_sha256"})
    protocol_payload["outcome_measures"] = (AVOProcessMeasure.MODEL_REQUESTS,)
    with pytest.raises(ValidationError, match="outcome_measures"):
        AVOQualificationProtocol.model_validate(protocol_payload)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("process_measures", tuple(AVOProcessMeasure)[:-1], "process measures must contain the complete canonical"),
        ("outcome_measures", tuple(AVOOutcomeMeasure)[:-1], "outcome measures must contain the complete canonical"),
    ],
)
def test_protocol_requires_complete_canonical_measure_sets(
    field: str,
    replacement: tuple[AVOProcessMeasure, ...] | tuple[AVOOutcomeMeasure, ...],
    message: str,
) -> None:
    protocol_payload = _protocol().model_dump(mode="python", exclude={"content_sha256"})
    protocol_payload[field] = replacement

    with pytest.raises(ValidationError, match=message):
        AVOQualificationProtocol.model_validate(protocol_payload)


def _protocol() -> AVOQualificationProtocol:
    development = _split("development", Visibility.PUBLIC, ("dev-a", "dev-b"))
    host_selection = _split("host_selection", Visibility.PUBLIC, ("host-a", "host-b"))
    qualification = _split("qualification", Visibility.HOLDOUT, ("qual-a", "qual-b"))
    route = AVOQualificationRoute(model="model", provider="provider", route="route")
    outer_budget = AVOQualificationOuterBudget(
        max_cycles=4,
        batch_size=2,
        improvement_threshold=0.02,
        stagnation_window=3,
        structural_weight=0.3,
        strategy="hill_climb",
    )
    common = {
        "route": route,
        "outer_budget": outer_budget,
        "development": development,
        "host_selection": host_selection,
        "qualification": qualification,
    }
    return AVOQualificationProtocol(
        protocol_id="avo-qualification.example",
        baseline=AVOQualificationArm(
            condition="ef03_one_shot",
            **common,
            adaptive_feedback=(),
            baseline=AVOQualificationBaselineReference(),
        ),
        avo=AVOQualificationArm(
            condition="avo",
            **common,
            inner_budget=AVOQualificationInnerBudget(
                max_model_requests=12,
                max_tool_calls=40,
                max_development_evaluations=7,
                max_elapsed_seconds=1800.0,
                max_consecutive_evaluation_errors=2,
                max_stagnant_evaluations=3,
                max_supervisor_interventions=1,
                max_cost_usd=5.0,
            ),
        ),
        independent_seeds=(11, 29),
    )
