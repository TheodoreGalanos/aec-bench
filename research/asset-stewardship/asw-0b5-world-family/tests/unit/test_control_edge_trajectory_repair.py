# ABOUTME: Specifies the exact approved control-edge trajectory amendment boundary.
# ABOUTME: Prevents candidate values, fitted edges, or tolerance changes from entering the repair.

from pathlib import Path

from repairs import control_edge_trajectory

B5_ROOT = Path(__file__).parents[2]
AMENDMENT = (
    B5_ROOT
    / "declarations"
    / "control-edge-trajectory-amendment.json"
)


def test_exact_control_edge_trajectory_amendment_is_accepted() -> None:
    value = control_edge_trajectory.read_amendment(
        AMENDMENT.read_bytes()
    )

    assert value["status"] == "approved-before-fresh-successor-run"
    assert value["boundaries"][
        "candidate_edge_timestamps_allowed_after_c_r12_pass"
    ] is True
    assert value["boundaries"][
        "candidate_depth_or_flow_allowed_as_reference_input"
    ] is False
    assert value["boundaries"]["changes_tolerance_or_hard_ceiling"] is False


def test_changed_control_edge_trajectory_amendment_is_rejected() -> None:
    raw = AMENDMENT.read_bytes()

    try:
        control_edge_trajectory.read_amendment(
            raw.replace(
                b'"changes_tolerance_or_hard_ceiling":false',
                b'"changes_tolerance_or_hard_ceiling":true',
            )
        )
    except control_edge_trajectory.ControlEdgeTrajectoryError as error:
        assert str(error) == "control-edge trajectory amendment bytes differ"
    else:
        raise AssertionError("changed trajectory amendment was accepted")
