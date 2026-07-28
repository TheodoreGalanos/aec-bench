# ABOUTME: Specifies the W4-owned hydraulic reference, slope, integration, and margin calculations.
# ABOUTME: Ensures sensitivity composition remains independent of generator and certifier physics code.

import ast
import math
from pathlib import Path

from sensitivity import members, physics

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"


def _anchor_values():
    authority = members.read_w1_authority(W1_DECLARATION.read_bytes())
    return physics.member_values(members.build_member(authority, {}))


def test_independent_operating_point_and_slope_are_finite_and_internal() -> None:
    values = _anchor_values()

    flow = physics.operating_point(
        values,
        depth_m=values["well.h_start"],
        obstruction=0.0,
        clearance_loss=0.0,
    )
    slope = physics.root_slope(
        values,
        flow_m3_s=flow,
        depth_m=values["well.h_start"],
        obstruction=0.0,
        clearance_loss=0.0,
    )

    assert 0.0 < flow < values["pump.Q_0"]
    assert math.isfinite(slope)
    assert slope > 0.0
    assert (
        abs(physics.pump_head(values, flow, 0.0, 0.0) - physics.system_head(values, flow, values["well.h_start"]))
        < 1e-12
    )


def test_rk4_step_doubling_converges_without_candidate_reanchoring() -> None:
    values = _anchor_values()
    arguments = {
        "clearance_loss": 0.0,
        "depth_m": values["well.h_start"],
        "duration_s": 120.0,
        "inflow_m3_s": values["inflow.Q_assess"],
        "obstruction": 0.0,
        "running": True,
    }

    coarse = physics.rk4_advance(values, step_s=2.0, **arguments)
    one_second = physics.rk4_advance(values, step_s=1.0, **arguments)
    half_second = physics.rk4_advance(values, step_s=0.5, **arguments)

    assert abs(one_second.depth_m - half_second.depth_m) < abs(coarse.depth_m - one_second.depth_m)
    assert one_second.depth_m < values["well.h_start"]
    assert one_second.flow_m3_s > values["inflow.Q_assess"]


def test_dynamic_allowance_and_capability_margin_use_preregistered_rules() -> None:
    values = _anchor_values()
    flow = physics.operating_point(
        values,
        depth_m=values["well.h_start"],
        obstruction=0.0,
        clearance_loss=0.0,
    )

    settling = physics.dynamic_settling(
        values,
        flow_m3_s=flow,
        depth_m=values["well.h_start"],
        obstruction=0.0,
        clearance_loss=0.0,
        report_step_s=1,
    )
    capability = physics.capability_interval(
        values,
        flow_m3_s=flow,
        flow_bound_m3_s=1e-6,
        report_step_s=1,
    )

    assert settling["time_constant_s"] > 0.0
    assert settling["settling_time_s"] >= 1
    assert settling["flow_allowance_m3_s"] == 0.001 * flow
    assert settling["depth_allowance_m"] <= 0.010068986195609708
    assert capability["classification"] == "capable"
    assert capability["margin_s"] == 12.0


def test_w4_physics_source_graph_is_independent() -> None:
    tree = ast.parse((B5_ROOT / "sensitivity" / "physics.py").read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots.add(node.module.split(".", 1)[0])

    assert "generator" not in imported_roots
    assert "certifier" not in imported_roots
