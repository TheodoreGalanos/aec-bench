# ABOUTME: Proves the registered SSC-03 hydraulic operation uses the minimal deterministic world values.
# ABOUTME: Covers conformance, registered routing, boundary codecs, and numerical properties.

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from aec_bench.meta_harness.evidence_lifecycle import (
    execute_lifecycle_operation,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
)
from aec_bench.task_world_templates.continual.world_logic import TransitionResult
from aec_bench.task_world_templates.hydraulics import kernel
from aec_bench.task_world_templates.hydraulics.contracts import (
    HydraulicEngineIdentity,
    HydraulicRunRequest,
    HydraulicSourceState,
    HydraulicTimeStep,
    hydraulic_run_id,
)
from aec_bench.task_world_templates.hydraulics.identity import canonical_json_sha256
from aec_bench.task_world_templates.hydraulics.kernel import (
    depth_from_storage_volume,
    rational_peak_flow,
    storage_volume,
)
from aec_bench.task_world_templates.hydraulics.worlds.ssc03_detention_network import build_source_state
from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_continual_definition import (
    Ssc03HydraulicContinualProfile,
    ssc03_hydraulic_continual_world_definition,
)
from tests.task_world_templates.continual.world_conformance import assert_world_conformance


def _engine() -> HydraulicEngineIdentity:
    source_inventory = {"kernel.py": "1" * 64}
    runtime_dependencies = {"python": "test"}
    return HydraulicEngineIdentity(
        engine_id="test-hydraulic-kernel",
        engine_version="1",
        source_inventory_sha256=source_inventory,
        implementation_sha256=canonical_json_sha256(source_inventory),
        runtime_dependencies=runtime_dependencies,
        runtime_dependency_sha256=canonical_json_sha256(runtime_dependencies),
    )


def _request(source: HydraulicSourceState, *, world_id: str | None = None) -> HydraulicRunRequest:
    selected_world_id = world_id or source.world_id
    engine = _engine()
    fields = {
        "world_id": selected_world_id,
        "scenario_id": "design-10yr",
        "package_sha256": "2" * 64,
        "source_state_sha256": "3" * 64,
        "calculation_input_sha256": "4" * 64,
        "engine": engine,
    }
    return HydraulicRunRequest(run_id=hydraulic_run_id(**fields), **fields)


def _assert_actor_safe(observation: HydraulicTimeStep | None) -> None:
    if observation is None:
        return
    assert not hasattr(observation, "source")
    assert not hasattr(observation, "criteria")
    values = (observation.total_inflow_m3_s, observation.total_outflow_m3_s, observation.storage_m3)
    assert all(math.isfinite(value) for value in values)


def _round_trip_observation(observation: HydraulicTimeStep | None) -> HydraulicTimeStep | None:
    if observation is None:
        return None
    return HydraulicTimeStep.model_validate(observation.model_dump(mode="json"))


def test_ssc03_hydraulic_world_conforms_to_shared_values() -> None:
    source = build_source_state()
    action = _request(source)
    final_state = assert_world_conformance(
        initial_state=lambda seed: kernel.initial_hydraulic_world_state(source, seed=seed),
        observe=lambda state: kernel.observe_hydraulic_world(state, actor_id="hydraulic-reviewer"),
        transition=kernel.transition_hydraulic_world,
        actions=(action,),
        invalid_action=_request(source, world_id="another-world"),
        assert_observation_safe=_assert_actor_safe,
        round_trip_action=lambda value: HydraulicRunRequest.model_validate(value.model_dump(mode="json")),
        round_trip_observation=_round_trip_observation,
        evaluate=kernel.evaluate_hydraulic_world,
    )

    assert not isinstance(final_state, HydraulicSourceState)
    result = kernel.evaluate_hydraulic_world(final_state)
    assert abs(result.continuity_error_m3) <= source.payload.criteria.maximum_continuity_error_m3


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_registered_ssc03_lifecycle_operation_uses_hydraulic_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original = kernel.transition_hydraulic_world

    def record_transition(
        state: kernel.HydraulicWorldState,
        action: HydraulicRunRequest,
    ) -> TransitionResult[kernel.HydraulicWorldState, Any]:
        nonlocal calls
        calls += 1
        return original(state, action)

    monkeypatch.setattr(kernel, "transition_hydraulic_world", record_transition)
    definition = ssc03_hydraulic_continual_world_definition()
    loaded = definition.load_profile(definition.spec.profiles[0])
    assert isinstance(loaded.value, Ssc03HydraulicContinualProfile)
    compiled = loaded.value.compile(tmp_path / "package")
    run = tmp_path / "run"
    prepare_evidence_checkpoint(compiled.package_dir, run)
    open_checkpoint_attempt(
        compiled.package_dir,
        run,
        session_id="baseline.session-001",
        execution_mode="persistent_context",
    )
    visible_source = _read_json(run / "workspace" / "hydraulics" / "current-source.json")
    visible_sha = str(visible_source["visible_source_state_sha256"])
    for operation_id in (
        "hydrology.design-10yr",
        "detention-outlet.design-10yr.declared-outlet",
    ):
        execute_lifecycle_operation(
            compiled.package_dir,
            run,
            checkpoint_id="baseline_analysis",
            operation_id=operation_id,
            visible_source_state_sha256=visible_sha,
            reason=f"Execute {operation_id} against the declared source.",
            session_id="baseline.session-001",
        )

    assert calls == 1


@given(
    depth=st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    bottom_area=st.floats(min_value=1.0, max_value=1_000.0, allow_nan=False, allow_infinity=False),
    area_increase=st.floats(min_value=0.0, max_value=1_000.0, allow_nan=False, allow_infinity=False),
)
def test_stage_storage_inverse_recovers_depth_within_tolerance(
    depth: float,
    bottom_area: float,
    area_increase: float,
) -> None:
    top_area = bottom_area + area_increase
    volume = storage_volume(
        depth_m=depth,
        maximum_depth_m=2.0,
        bottom_area_m2=bottom_area,
        top_area_m2=top_area,
    )

    assert depth_from_storage_volume(
        volume_m3=volume,
        maximum_depth_m=2.0,
        bottom_area_m2=bottom_area,
        top_area_m2=top_area,
    ) == pytest.approx(depth, abs=1e-9)


@given(
    coefficient=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    intensity=st.floats(min_value=0.001, max_value=500.0, allow_nan=False, allow_infinity=False),
    smaller_area=st.floats(min_value=0.001, max_value=100.0, allow_nan=False, allow_infinity=False),
    added_area=st.floats(min_value=0.001, max_value=100.0, allow_nan=False, allow_infinity=False),
)
def test_rational_peak_flow_is_monotonic_in_catchment_area(
    coefficient: float,
    intensity: float,
    smaller_area: float,
    added_area: float,
) -> None:
    lower = rational_peak_flow(
        runoff_coefficient=coefficient,
        rainfall_intensity_mm_h=intensity,
        area_ha=smaller_area,
    )
    upper = rational_peak_flow(
        runoff_coefficient=coefficient,
        rainfall_intensity_mm_h=intensity,
        area_ha=smaller_area + added_area,
    )

    assert lower <= upper
