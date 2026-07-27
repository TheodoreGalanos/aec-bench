# ABOUTME: Specifies independent W4 member construction, preconditions, and minimum interaction coverage.
# ABOUTME: Requires exact bound selection without importing generator or certifier member helpers.

import ast
from pathlib import Path

import pytest
from sensitivity import catalogue, members

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
PROBE_DECLARATION = B5_ROOT / "declarations" / "w4-probe-catalogue.json"


def test_builds_all_oat_members_in_lexical_probe_order() -> None:
    authority = members.read_w1_authority(W1_DECLARATION.read_bytes())
    probes = catalogue.read_probe_catalogue(PROBE_DECLARATION.read_bytes())

    results = members.build_oat_results(authority, probes)

    assert [item["probe_id"] for item in results] == probes["oat_probe_ids"]
    assert len(results) == 68
    assert all(item["terminal_state"] in {"probe-pass", "probe-precondition-reject"} for item in results)
    assert all(item["promotable"] is False for item in results)
    selected = next(item for item in results if item["probe_id"] == "OAT.system.D.upper")
    values = members.member_values(selected["member"])
    assert values["system.D"] == members.Decimal("0.190")
    assert selected["member"]["member_content_id"] == members.member_content_id(selected["member"])


def test_interactions_supply_required_non_anchor_coverage_or_explicit_rejection() -> None:
    authority = members.read_w1_authority(W1_DECLARATION.read_bytes())
    probes = catalogue.read_probe_catalogue(PROBE_DECLARATION.read_bytes())

    results = members.build_interaction_results(authority, probes)
    by_id = {item["probe_id"]: item for item in results}

    assert list(by_id) == [
        "INT.00.anchor",
        "INT.01.hydraulic-supporting",
        "INT.02.hydraulic-opposing",
        "INT.03.primary-dominant",
        "INT.04.secondary-dominant",
    ]
    assert by_id["INT.00.anchor"]["terminal_state"] == "probe-pass"
    assert any(
        by_id[probe_id]["terminal_state"] == "probe-pass"
        for probe_id in (
            "INT.01.hydraulic-supporting",
            "INT.02.hydraulic-opposing",
        )
    )
    assert any(
        by_id[probe_id]["terminal_state"] == "probe-pass"
        for probe_id in (
            "INT.03.primary-dominant",
            "INT.04.secondary-dominant",
        )
    )
    assert all(item["case_ids"] for item in results)


def test_rejects_unknown_or_fixed_bound_selection() -> None:
    authority = members.read_w1_authority(W1_DECLARATION.read_bytes())

    with pytest.raises(members.MemberProbeError, match="unknown parameter"):
        members.build_member(authority, {"unknown.value": "upper"})
    with pytest.raises(members.MemberProbeError, match="fixed parameter"):
        members.build_member(authority, {"system.Re_min": "lower"})


def test_sensitivity_member_role_does_not_import_generator_or_certifier() -> None:
    tree = ast.parse((B5_ROOT / "sensitivity" / "members.py").read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots.add(node.module.split(".", 1)[0])

    assert "generator" not in imported_roots
    assert "certifier" not in imported_roots
