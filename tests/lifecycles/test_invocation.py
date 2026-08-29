# ABOUTME: Tests versioned lifecycle invocation identity contracts.
# ABOUTME: Keeps historical version 1 manifests distinct from trial-bound version 2 writes.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.lifecycles.compiled import CompiledLifecycleEnvelope
from aec_bench.lifecycles.invocation import (
    LifecycleExperimentManifest,
    LifecycleExperimentMetrics,
    LifecycleExperimentSweepContext,
    LifecycleExperimentTrialContext,
)


def test_manifest_versions_accept_only_their_declared_trial_identity_shape() -> None:
    version_1 = LifecycleExperimentManifest.model_validate(_manifest_payload("1"))
    version_2 = LifecycleExperimentManifest.model_validate(_manifest_payload("2", trial=_trial_context()))

    assert version_1.trial is None
    assert version_2.trial == _trial_context()


@pytest.mark.parametrize(
    ("schema_version", "has_trial", "message"),
    [
        ("1", True, "version 1 cannot contain trial identity"),
        ("2", False, "version 2 requires trial identity"),
    ],
)
def test_manifest_versions_reject_ambiguous_trial_identity_shape(
    schema_version: str,
    has_trial: bool,
    message: str,
) -> None:
    trial = _trial_context() if has_trial else None
    with pytest.raises(ValidationError, match=message):
        LifecycleExperimentManifest.model_validate(_manifest_payload(schema_version, trial=trial))


@pytest.mark.parametrize("raw_value", [True, 1.0, "1"])
def test_invocation_contexts_reject_coercive_repetitions(raw_value: object) -> None:
    with pytest.raises(ValidationError):
        LifecycleExperimentTrialContext.model_validate(
            {**_trial_context().model_dump(mode="json"), "repetition": raw_value}
        )
    with pytest.raises(ValidationError):
        LifecycleExperimentSweepContext.model_validate(
            {
                "sweep_experiment_id": "sweep-001",
                "planned_trial_id": "trial-001",
                "plan_sha256": "a" * 64,
                "condition_id": "fresh_context__artifact_memory",
                "repetition": raw_value,
            }
        )


@pytest.mark.parametrize("raw_value", [True, 1.0, "1"])
def test_invocation_metrics_reject_coercive_integer_counts(raw_value: object) -> None:
    with pytest.raises(ValidationError):
        LifecycleExperimentMetrics.model_validate({**_metrics_payload(), "input_tokens": raw_value})


@pytest.mark.parametrize("raw_value", [True, "1"])
def test_invocation_metrics_reject_coercive_durations_and_cost(raw_value: object) -> None:
    with pytest.raises(ValidationError):
        LifecycleExperimentMetrics.model_validate({**_metrics_payload(), "whole_run_seconds": raw_value})
    with pytest.raises(ValidationError):
        LifecycleExperimentMetrics.model_validate({**_metrics_payload(), "estimated_cost_usd": raw_value})


def _manifest_payload(
    schema_version: str,
    *,
    trial: LifecycleExperimentTrialContext | None = None,
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "experiment_id": "invocation-test",
        "created_at": "2026-08-29T00:00:00Z",
        "repository": {},
        "environment": {},
        "lifecycle": {},
        "verifier": {},
        "model": {},
        "execution": {},
        "interaction": {},
        "outputs": {},
        "trial": None if trial is None else trial.model_dump(mode="json"),
    }


def _trial_context() -> LifecycleExperimentTrialContext:
    return LifecycleExperimentTrialContext(
        trial_id="trial-001",
        planned_experiment_id="experiment-001",
        task_id="lifecycle/template/variant",
        repetition=1,
        run_id="trial-001",
        compiled=CompiledLifecycleEnvelope(
            visibility="public",
            template_id="template",
            lifecycle_id="lifecycle-001",
            variant_id="variant",
            lifecycle_spec_sha256="a" * 64,
            package_sha256="b" * 64,
            executable_artifact_sha256="c" * 64,
        ),
    )


def _metrics_payload() -> dict[str, object]:
    return {
        "checkpoint_count": 1,
        "requests": 1,
        "tool_calls": 1,
        "reads": 1,
        "revisits": 0,
        "retries": 0,
        "failures": 0,
        "input_tokens": 1,
        "output_tokens": 1,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "estimated_cost_usd": 0.0,
        "checkpoint_seconds": {"initial_review": 1.0},
        "whole_run_seconds": 1.0,
    }
