# ABOUTME: Specifies W3 transfer parsing, binary32 decoding, independent hydraulic equations, and source isolation.
# ABOUTME: Keeps certifier behavior fixed without granting it generator, SWMM, raw-artifact, or workspace access.

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from typing import Any

import pytest
from certifier import boundary, candidate, cases, physics
from generator import request, transfer

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"


def _generation_result() -> dict[str, Any]:
    replays = []
    for replay_index in range(2):
        cases: dict[str, Any] = {}
        for case_id in request.CASE_IDS:
            segment_ids = (
                ("segment-a", "segment-b")
                if case_id == "G70_TRANSFER"
                else (
                    tuple(f"checkpoint-{index}" for index in range(4))
                    if case_id == "G80_NO_MAINTENANCE"
                    else ("single",)
                )
            )
            cases[case_id] = {
                "case_id": case_id,
                "request_bytes": request.canonical_json_bytes(
                    {"case_id": case_id}
                ),
                "segments": [
                    {
                        "curve_bytes": {
                            "pump-a-engine": f"{case_id}:{segment_id}:ae".encode(),
                            "pump-a-original": f"{case_id}:{segment_id}:ao".encode(),
                            "pump-b-engine": f"{case_id}:{segment_id}:be".encode(),
                            "pump-b-original": f"{case_id}:{segment_id}:bo".encode(),
                        },
                        "segment_id": segment_id,
                        "semantic_bytes": f"{case_id}:{segment_id}:semantic".encode(),
                    }
                    for segment_id in segment_ids
                ],
            }
        replays.append({"cases": cases, "replay_index": replay_index})
    return {
        "case_ids": list(request.CASE_IDS),
        "replays": replays,
    }


def test_path_free_transfer_bundle_preserves_only_permitted_exact_bytes() -> None:
    raw = transfer.build_certifier_bundle(_generation_result())

    parsed = candidate.read_bundle(raw)

    assert len(parsed) == 46
    assert parsed[0].case_id == "G00_ZERO_STATIC"
    assert parsed[0].replay_ordinal == 0
    assert parsed[0].segment_id == "single"
    assert tuple(parsed[0].roles) == candidate.ROLE_IDS
    assert parsed[0].roles["pump-a-engine-curve"].endswith(b":ae")
    assert b"/Users/" not in raw
    assert b"workspace" not in raw
    assert b".out" not in raw
    assert b".rpt" not in raw


def test_transfer_bundle_rejects_changed_role_bytes_before_parsing_payload() -> None:
    raw = transfer.build_certifier_bundle(_generation_result())
    changed = raw.replace(b"473030", b"473031", 1)

    with pytest.raises(candidate.CandidateError, match="bundle-role"):
        candidate.read_bundle(changed)


@pytest.mark.parametrize(
    ("encoded", "expected"),
    [
        ("00000000", 0.0),
        ("3f800000", 1.0),
        ("3dcccccd", pytest.approx(0.1)),
    ],
)
def test_decodes_exact_finite_binary32(encoded: str, expected: object) -> None:
    assert candidate.decode_binary32(encoded) == expected


@pytest.mark.parametrize("encoded", ["80000000", "7f800000", "7fc00000", "3F800000"])
def test_rejects_noncanonical_binary32(encoded: str) -> None:
    with pytest.raises(candidate.CandidateError, match="semantic-binary32"):
        candidate.decode_binary32(encoded)


def test_independent_physics_validates_anchor_and_reconstructs_both_curve_forms() -> None:
    authority = boundary.read_w1_declaration(W1_DECLARATION.read_bytes())
    member = request.anchor_member(W1_DECLARATION.read_bytes())

    values = physics.validate_member(member, authority)
    original = physics.reconstruct_curve(
        values,
        clearance_loss="0",
        obstruction="0.75",
        representation="asw-0b4.pump3-curve.v1",
    )
    engine = physics.reconstruct_curve(
        values,
        clearance_loss="0",
        obstruction="0.75",
        representation="asw-0b5.net-head-pump3-curve.v1",
    )

    assert original["point_count"] == 33
    assert engine["point_count"] == 33
    assert original["points"][0]["head_m"] == "0.000000000"
    assert engine["points"][0]["head_m"] == "0.000000000"
    assert original["points"][-1]["flow_lps"] == "0.000000"
    assert engine["points"][-1]["flow_lps"] == "0.000000"
    assert float(engine["points"][0]["flow_lps"]) < float(
        original["points"][0]["flow_lps"]
    )


def test_independent_root_and_one_second_rk4_obey_physical_direction() -> None:
    authority = boundary.read_w1_declaration(W1_DECLARATION.read_bytes())
    member = request.anchor_member(W1_DECLARATION.read_bytes())
    values = physics.validate_member(member, authority)
    depth = float(values["well.h_start"])

    clean_flow = physics.operating_point(values, depth, 0.0, 0.0)
    obstructed_flow = physics.operating_point(values, depth, 0.75, 0.0)
    next_depth, reference_flow = physics.rk4_interval(
        values,
        clearance_loss=0.0,
        depth_m=depth,
        inflow_m3_s=float(values["inflow.Q_assess"]),
        obstruction=0.75,
        running=True,
    )

    assert clean_flow > obstructed_flow > 0.0
    assert reference_flow == pytest.approx(obstructed_flow)
    assert next_depth < depth


def test_reconstructs_every_authorized_case_without_generator_catalogue_access() -> None:
    authority = boundary.read_w1_declaration(W1_DECLARATION.read_bytes())
    member = request.anchor_member(W1_DECLARATION.read_bytes())
    values = physics.validate_member(member, authority)

    for case_id in boundary.W2_CASES:
        expected = cases.expected_case(case_id, values)

        assert expected["case_id"] == case_id
        assert cases.validate_case(expected, values) == expected


def test_certifier_source_graph_does_not_import_generator_or_swmm() -> None:
    certifier_root = B5_ROOT / "certifier"
    imported_roots: set[str] = set()
    for path in sorted(certifier_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_roots.add(node.module.split(".", 1)[0])

    assert "generator" not in imported_roots
    assert "swmm" not in imported_roots
    assert importlib.util.find_spec("certifier.candidate") is not None
