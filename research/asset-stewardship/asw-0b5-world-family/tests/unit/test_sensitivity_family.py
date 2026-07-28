# ABOUTME: Specifies deterministic analytical inventory and exact family aggregation.
# ABOUTME: Retains planned probes and rejected predecessors while testing pass and rejection paths.

import hashlib
import json
from pathlib import Path

import pytest
from sensitivity import catalogue, family, selection_amendment

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
PROBE_DECLARATION = B5_ROOT / "declarations" / "w4-probe-catalogue.json"
SELECTION_AMENDMENT = (
    B5_ROOT
    / "declarations"
    / "family-member-selection-amendment.json"
)


def _identified(
    value: dict[str, object],
    domain: bytes,
) -> dict[str, object]:
    value["result_content_id"] = hashlib.sha256(
        domain
        + catalogue.canonical_json_bytes(
            {
                key: child
                for key, child in value.items()
                if key != "result_content_id"
            }
        )
    ).hexdigest()
    return value


def _passing_evidence() -> tuple[
    dict[str, object],
    dict[str, dict[str, object]],
    dict[str, object],
    dict[str, object],
]:
    anchor_result = _identified(
        {
            "first_failure": "none",
            "promotable": False,
            "result_content_id": "",
            "schema_id": "asw-0b5.w4-composition-result.v3",
            "terminal_state": "w4-checks-pass",
        },
        b"asw-0b5.w4-composition-result.v3\0",
    )
    member_ids = {
        "INT.01.hydraulic-supporting": (
            "3811f8cd17548f8c6b11b524504a9b62c49ab999099ea17e84dda7eac99484c3"
        ),
        "INT.02.hydraulic-opposing": "2" * 64,
        "INT.03.primary-dominant": (
            "915c0289e22b33601647958a74040bdb52c48cd1a6d54e4c9775492513c40953"
        ),
    }
    members = {
        probe_id: _identified(
            {
                "first_failure": "none",
                "member_content_id": member_content_id,
                "probe_id": probe_id,
                "promotable": False,
                "result_content_id": "",
                "schema_id": "asw-0b5.fixed-member-evaluation.v1",
                "terminal_state": "w4-checks-pass",
            },
            b"asw-0b5.fixed-member-evaluation.v1\0",
        )
        for probe_id, member_content_id in member_ids.items()
    }
    engine = _identified(
        {
            "first_failure": "none",
            "promotable": False,
            "result_content_id": "",
            "schema_id": "asw-0b5.engine-variant-evaluation.v1",
            "terminal_state": "engine-variants-pass",
            "variant_ids": [
                "ENG.00.base",
                "ENG.01.curve-16",
                "ENG.02.curve-64",
                "ENG.03.report-2s",
                "ENG.04.route-report-2s",
                "ENG.05.outfall-order-swap",
                "ENG.06.outfall-target-swap",
            ],
        },
        b"asw-0b5.engine-variant-evaluation.v1\0",
    )
    mutation = _identified(
        {
            "first_failure": "none",
            "mutation_count": 30,
            "mutations": {
                f"M{index:02d}": {"outcome": "pass"}
                for index in range(1, 31)
            },
            "promotable": False,
            "result_content_id": "",
            "schema_id": (
                "asw-0b5.mutation-catalogue-evaluation.v1"
            ),
            "terminal_state": "mutation-catalogue-pass",
        },
        b"asw-0b5.mutation-catalogue-evaluation.v1\0",
    )
    return anchor_result, members, engine, mutation


def test_analytical_inventory_retains_complete_probe_and_grid_plan() -> None:
    inventory = family.build_analytical_inventory(
        authority_bytes=W1_DECLARATION.read_bytes(),
        probe_catalogue_bytes=PROBE_DECLARATION.read_bytes(),
    )

    assert len(inventory["oat"]) == 68
    assert len(inventory["interactions"]) == 5
    assert [item["probe_id"] for item in inventory["boundaries"]] == [f"BND.{index:02d}" for index in range(11)]
    assert inventory["grid_cardinalities"] == {
        "flow_observation": 9,
        "intervention": 3,
        "level_observation": 9,
        "progression": 3,
        "resource": 5,
        "runtime_observation": 3,
    }
    assert len(inventory["engine_variants"]) == 7
    assert len(inventory["mutation_ids"]) == 30
    assert all(item["promotable"] is False for item in inventory["oat"])
    assert all(
        item["terminal_state"] == "probe-pass"
        for item in inventory["boundaries"]
    )
    assert inventory["grid_results"]["flow_observation"][
        "evaluated"
    ] == 9
    assert inventory["grid_results"]["level_observation"][
        "evaluated"
    ] == 9
    assert inventory["grid_results"]["runtime_observation"][
        "evaluated"
    ] == 3
    assert inventory["grid_results"]["progression"]["evaluated"] == 3
    assert inventory["grid_results"]["intervention"]["evaluated"] == 3
    assert inventory["grid_results"]["resource"]["evaluated"] == 5
    assert all(
        result["terminal_state"] == "grid-pass"
        for result in inventory["grid_results"].values()
    )


def test_member_selection_amendment_replaces_only_two_declared_roles() -> None:
    declaration = catalogue.read_probe_catalogue(
        PROBE_DECLARATION.read_bytes()
    )

    amended = selection_amendment.apply(
        declaration,
        SELECTION_AMENDMENT.read_bytes(),
    )
    predecessor = {
        item["probe_id"]: item
        for item in declaration["interactions"]
    }
    interactions = {
        item["probe_id"]: item
        for item in amended["interactions"]
    }

    assert interactions["INT.01.hydraulic-supporting"]["selections"] == {
        "inflow.Q_low": "lower",
        "inflow.Q_nominal": "lower",
        "system.K_minor": "lower",
        "system.epsilon": "lower",
    }
    assert interactions["INT.03.primary-dominant"]["selections"] == {
        "mechanism.r_c_runtime": "lower",
        "mechanism.r_o_runtime": "upper",
        "mechanism.r_o_start": "upper",
    }
    assert interactions["INT.02.hydraulic-opposing"] == predecessor[
        "INT.02.hydraulic-opposing"
    ]
    assert interactions["INT.04.secondary-dominant"] == predecessor[
        "INT.04.secondary-dominant"
    ]
    assert selection_amendment.AMENDMENT_SHA256 == (
        "594e507ee5e8e783c80137512bfb918bbc91e5a00692465be0a5c5739b2b1ba5"
    )


def test_amended_inventory_binds_replacement_member_identities() -> None:
    inventory = family.build_amended_analytical_inventory(
        authority_bytes=W1_DECLARATION.read_bytes(),
        probe_catalogue_bytes=PROBE_DECLARATION.read_bytes(),
        selection_amendment_bytes=SELECTION_AMENDMENT.read_bytes(),
    )
    interactions = {
        item["probe_id"]: item
        for item in inventory["interactions"]
    }

    assert inventory["schema_id"] == (
        "asw-0b5.w4-analytical-inventory.v2"
    )
    assert inventory["selection_amendment_sha256"] == (
        selection_amendment.AMENDMENT_SHA256
    )
    assert interactions["INT.01.hydraulic-supporting"]["member"][
        "member_content_id"
    ] == (
        "3811f8cd17548f8c6b11b524504a9b62c49ab999099ea17e84dda7eac99484c3"
    )
    assert interactions["INT.03.primary-dominant"]["member"][
        "member_content_id"
    ] == (
        "915c0289e22b33601647958a74040bdb52c48cd1a6d54e4c9775492513c40953"
    )
    assert all(
        item["terminal_state"] == "probe-pass"
        for item in interactions.values()
    )


def test_anchor_budget_rejection_freezes_family_without_running_siblings() -> None:
    inventory = family.build_analytical_inventory(
        authority_bytes=W1_DECLARATION.read_bytes(),
        probe_catalogue_bytes=PROBE_DECLARATION.read_bytes(),
    )

    result = family.freeze_family_decision(
        analytical_inventory=inventory,
        composition_result_content_id="1" * 64,
        composition_terminal_state="w4-budget-reject",
        composition_first_failure=("C-R08-derived-budget-lower-bound-exceeds-relative-ceiling"),
    )

    assert result["terminal_state"] == "family-member-reject"
    assert result["first_failure"] == "anchor-w4-budget-reject"
    assert result["promotable"] is False
    assert result["execution"]["anchor"] == "w4-budget-reject"
    assert result["execution"]["downstream"] == ("not-executed-after-anchor-rejection")
    assert result["result_content_id"]
    assert family.family_result_bytes(result) == catalogue.canonical_json_bytes(result)


def test_successor_numerical_rejection_freezes_family_without_siblings() -> None:
    inventory = family.build_analytical_inventory(
        authority_bytes=W1_DECLARATION.read_bytes(),
        probe_catalogue_bytes=PROBE_DECLARATION.read_bytes(),
    )

    result = family.freeze_family_decision(
        analytical_inventory=inventory,
        composition_result_content_id="1" * 64,
        composition_terminal_state="w4-numerical-reject",
        composition_first_failure="C-R02-corrected-residual",
    )

    assert result["terminal_state"] == "family-member-reject"
    assert result["first_failure"] == "anchor-w4-numerical-reject"
    assert result["execution"]["anchor"] == "w4-numerical-reject"
    assert result["execution"]["ordered_stop_owner"] == (
        "C-R02-corrected-residual"
    )


def test_family_decision_refuses_non_rejection_or_bad_identity() -> None:
    inventory = family.build_analytical_inventory(
        authority_bytes=W1_DECLARATION.read_bytes(),
        probe_catalogue_bytes=PROBE_DECLARATION.read_bytes(),
    )

    with pytest.raises(family.FamilyDecisionError, match="anchor rejection"):
        family.freeze_family_decision(
            analytical_inventory=inventory,
            composition_result_content_id="1" * 64,
            composition_terminal_state="w4-checks-pass",
            composition_first_failure="none",
        )
    with pytest.raises(family.FamilyDecisionError, match="content identity"):
        family.freeze_family_decision(
            analytical_inventory=inventory,
            composition_result_content_id="bad",
            composition_terminal_state="w4-budget-reject",
            composition_first_failure=("C-R08-derived-budget-lower-bound-exceeds-relative-ceiling"),
        )


def test_complete_evidence_freezes_one_passing_family_decision() -> None:
    inventory = family.build_amended_analytical_inventory(
        authority_bytes=W1_DECLARATION.read_bytes(),
        probe_catalogue_bytes=PROBE_DECLARATION.read_bytes(),
        selection_amendment_bytes=SELECTION_AMENDMENT.read_bytes(),
    )
    anchor_result, members, engine, mutation = _passing_evidence()
    inventory_members = {
        item["probe_id"]: item["member"]["member_content_id"]
        for item in inventory["interactions"]
    }
    members["INT.02.hydraulic-opposing"]["member_content_id"] = (
        inventory_members["INT.02.hydraulic-opposing"]
    )
    members["INT.02.hydraulic-opposing"] = _identified(
        members["INT.02.hydraulic-opposing"],
        b"asw-0b5.fixed-member-evaluation.v1\0",
    )

    result = family.freeze_passing_family_decision(
        analytical_inventory=inventory,
        anchor_result=anchor_result,
        member_results=members,
        engine_result=engine,
        mutation_result=mutation,
        selection_amendment_bytes=SELECTION_AMENDMENT.read_bytes(),
    )

    assert result["schema_id"] == "asw-0b5.family-decision.v2"
    assert result["terminal_state"] == "family-w4-checks-pass"
    assert result["first_failure"] == "none"
    assert result["promotable"] is False
    assert result["coverage"] == {
        "accepted_interaction_count": 3,
        "boundary_probe_count": 11,
        "engine_variant_count": 7,
        "grid_value_count": 32,
        "mutation_count": 30,
        "oat_probe_count": 68,
        "retained_predecessor_rejection_count": 2,
    }
    assert [
        item["probe_id"]
        for item in result["retained_predecessor_rejections"]
    ] == [
        "INT.01.hydraulic-supporting",
        "INT.04.secondary-dominant",
    ]
    assert family.family_result_bytes(result) == (
        catalogue.canonical_json_bytes(result)
    )


def test_passing_family_rejects_missing_member_or_changed_evidence() -> None:
    inventory = family.build_amended_analytical_inventory(
        authority_bytes=W1_DECLARATION.read_bytes(),
        probe_catalogue_bytes=PROBE_DECLARATION.read_bytes(),
        selection_amendment_bytes=SELECTION_AMENDMENT.read_bytes(),
    )
    anchor_result, members, engine, mutation = _passing_evidence()
    inventory_members = {
        item["probe_id"]: item["member"]["member_content_id"]
        for item in inventory["interactions"]
    }
    members["INT.02.hydraulic-opposing"]["member_content_id"] = (
        inventory_members["INT.02.hydraulic-opposing"]
    )
    members["INT.02.hydraulic-opposing"] = _identified(
        members["INT.02.hydraulic-opposing"],
        b"asw-0b5.fixed-member-evaluation.v1\0",
    )
    incomplete = dict(members)
    del incomplete["INT.03.primary-dominant"]

    with pytest.raises(
        family.FamilyDecisionError,
        match="member result inventory",
    ):
        family.freeze_passing_family_decision(
            analytical_inventory=inventory,
            anchor_result=anchor_result,
            member_results=incomplete,
            engine_result=engine,
            mutation_result=mutation,
            selection_amendment_bytes=(
                SELECTION_AMENDMENT.read_bytes()
            ),
        )

    changed_engine = json.loads(json.dumps(engine))
    changed_engine["terminal_state"] = "engine-variants-reject"
    with pytest.raises(
        family.FamilyDecisionError,
        match="engine result identity",
    ):
        family.freeze_passing_family_decision(
            analytical_inventory=inventory,
            anchor_result=anchor_result,
            member_results=members,
            engine_result=changed_engine,
            mutation_result=mutation,
            selection_amendment_bytes=(
                SELECTION_AMENDMENT.read_bytes()
            ),
        )
