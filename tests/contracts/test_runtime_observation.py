# ABOUTME: Tests typed runtime observations against requested provider conditions.
# ABOUTME: Proves declared resolution is visible while route, family, tool, and limit drift is invalid.

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.identity import EntityKind, new_entity_id
from aec_bench.contracts.runtime_observation import ProviderResolutionMapping, RuntimeObservation, observe_runtime
from aec_bench.contracts.trial_record import ProviderRoute


def _route(provider: str = "azure", route: str = "azure-openai") -> ProviderRoute:
    return ProviderRoute(provider=provider, route=route)


def _kwargs() -> dict[str, object]:
    return {
        "observation_id": new_entity_id(EntityKind.RECEIPT),
        "trial_id": new_entity_id(EntityKind.TRIAL),
        "attempt_id": new_entity_id(EntityKind.ATTEMPT),
        "backend": "harbor",
        "runtime_image": "ghcr.io/aec-bench/runner@sha256:" + "a" * 64,
        "runtime_version": "runner-1.2.0",
        "requested_route": _route(),
        "requested_model": "gpt-4.1-mini",
        "requested_model_family": "gpt-4.1",
        "adapter_version": "adapter-1.0.0",
        "requested_tool_versions": {"shell": "1"},
        "observed_tool_versions": {"shell": "1"},
        "requested_limits": {"max_turns": 20},
        "observed_limits": {"max_turns": 20},
        "resource_observations": {"peak_memory_mb": 512},
        "started_at": datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
    }


def test_expected_dated_resolution_is_complete_and_explicit() -> None:
    values = _kwargs()
    mapping = ProviderResolutionMapping(
        mapping_id="azure-gpt-4.1-dated",
        mapping_version=1,
        requested_route=values["requested_route"],
        resolved_route=values["requested_route"],
        requested_model="gpt-4.1-mini",
        resolved_model="gpt-4.1-mini-2025-04-14",
        requested_model_family="gpt-4.1",
        resolved_model_family="gpt-4.1",
        kind="declared_dated",
    )
    observation = observe_runtime(
        **values,
        resolved_route=values["requested_route"],
        resolved_model="gpt-4.1-mini-2025-04-14",
        resolved_model_family="gpt-4.1",
        resolution=mapping,
    )

    assert observation.status == "complete"
    assert observation.resolution == mapping
    assert RuntimeObservation.model_validate_json(observation.model_dump_json()) == observation


def test_reviewer_fixture_is_a_current_json_contract() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "provider" / "runtime-observation-dated.json"

    observation = RuntimeObservation.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert observation.status == "complete"
    assert observation.resolution is not None
    assert observation.resolution.kind == "declared_dated"


@pytest.mark.parametrize(
    ("field", "value", "mismatch"),
    [
        ("resolved_route", _route("other", "other-route"), "provider_route"),
        ("resolved_model_family", "other-family", "model_family"),
        ("observed_tool_versions", {"shell": "2"}, "tools"),
        ("observed_limits", {"max_turns": 21}, "limits"),
    ],
)
def test_undeclared_runtime_drift_is_invalid(
    field: str,
    value: object,
    mismatch: str,
) -> None:
    values = _kwargs()
    values[field] = value
    if field == "resolved_route":
        values["resolved_model"] = values["requested_model"]
        values["resolved_model_family"] = values["requested_model_family"]
    elif field == "resolved_model_family":
        values["resolved_route"] = values["requested_route"]
        values["resolved_model"] = values["requested_model"]
    else:
        values["resolved_route"] = values["requested_route"]
        values["resolved_model"] = values["requested_model"]
        values["resolved_model_family"] = values["requested_model_family"]
    observation = observe_runtime(**values)

    assert observation.status == "invalid"
    assert mismatch in {item.kind for item in observation.mismatches}


def test_missing_resolved_identity_is_incomplete() -> None:
    values = _kwargs()

    observation = observe_runtime(**values)

    assert observation.status == "incomplete"
    assert observation.mismatches[0].kind == "resolved_identity"


def test_declared_resolution_cannot_replace_a_missing_observed_identity() -> None:
    values = _kwargs()
    mapping = ProviderResolutionMapping(
        mapping_id="azure-gpt-4.1-dated",
        mapping_version=1,
        requested_route=values["requested_route"],
        resolved_route=values["requested_route"],
        requested_model="gpt-4.1-mini",
        resolved_model="gpt-4.1-mini-2025-04-14",
        requested_model_family="gpt-4.1",
        resolved_model_family="gpt-4.1",
        kind="declared_dated",
    )

    with pytest.raises(ValidationError, match="requires a complete observed identity"):
        observe_runtime(**values, resolution=mapping)


def test_missing_identity_with_tool_drift_is_invalid() -> None:
    values = _kwargs()
    values["observed_tool_versions"] = {"shell": "2"}

    observation = observe_runtime(**values)

    assert observation.status == "invalid"
    assert {item.kind for item in observation.mismatches} == {"resolved_identity", "tools"}


def test_partial_identity_with_route_drift_is_invalid() -> None:
    values = _kwargs()
    values["resolved_route"] = _route("other", "other-route")

    observation = observe_runtime(**values)

    assert observation.status == "invalid"
    assert {item.kind for item in observation.mismatches} == {"resolved_identity", "provider_route"}


def test_resolution_mapping_must_match_observed_model_family() -> None:
    values = _kwargs()
    mapping = ProviderResolutionMapping(
        mapping_id="azure-gpt-4.1-dated",
        mapping_version=1,
        requested_route=values["requested_route"],
        resolved_route=values["requested_route"],
        requested_model="gpt-4.1-mini",
        resolved_model="gpt-4.1-mini-2025-04-14",
        requested_model_family="gpt-4.1",
        resolved_model_family="gpt-4.1",
        kind="declared_dated",
    )

    with pytest.raises(ValidationError, match="resolved model family does not match"):
        observe_runtime(
            **values,
            resolved_route=values["requested_route"],
            resolved_model="gpt-4.1-mini-2025-04-14",
            resolved_model_family="different-family",
            resolution=mapping,
        )


def test_direct_model_loading_rejects_untyped_drift() -> None:
    values = _kwargs()
    values.update(
        {
            "resolved_route": _route(),
            "resolved_model": "gpt-4.1-mini-2025-04-14",
            "resolved_model_family": "gpt-4.1",
            "status": "complete",
        }
    )

    with pytest.raises(ValidationError, match="mismatches must exactly describe observed differences"):
        RuntimeObservation.model_validate(values)
