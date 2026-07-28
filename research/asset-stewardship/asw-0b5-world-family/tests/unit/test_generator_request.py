# ABOUTME: Specifies canonical W2 anchor-member, catalogue, request, and content-identity behavior.
# ABOUTME: Rejects malformed or unauthorized generator inputs before any SWMM rendering or execution.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from generator import request
from repairs import solver_convergence

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
W2_CATALOGUE = B5_ROOT / "declarations" / "w2-case-catalogue.json"
W2_W4_REPAIR = B5_ROOT / "declarations" / "w2-w4-engine-mapping-repair.json"
SOLVER_CONVERGENCE = (
    B5_ROOT / "declarations" / "solver-convergence-amendment.json"
)

ENGINE_IDENTITY = {
    "build_receipt_sha256": "1" * 64,
    "commit": "7952ca837988b1c32f791812eccc9fd64547e093",
    "executable_sha256": "2" * 64,
    "output_library_sha256": "3" * 64,
    "patch_sha256": "522fa1f285b27bfdd614eae79a841e5b9a7892573521d032f78fdbd281dba894",
    "repository": "https://github.com/USEPA/Stormwater-Management-Model.git",
    "settings_id": "asw-0b5.swmm-settings.v3",
    "solver_library_sha256": "4" * 64,
    "version": "5.2.4",
}


def test_anchor_member_and_exact_case_catalogue_are_canonical_and_complete() -> None:
    member = request.anchor_member(W1_DECLARATION.read_bytes())
    repair = request.read_mapping_repair(W2_W4_REPAIR.read_bytes())
    catalogue = request.read_case_catalogue(W2_CATALOGUE.read_bytes())

    assert len(member["parameters"]) == 46
    assert len(member["composites"]) == 3
    assert member["member_content_id"] == request.member_content_id(member)
    assert [case["case_id"] for case in catalogue["cases"]] == list(request.CASE_IDS)
    assert repair["engine_mapping"]["nodes"] == ["O_HGL_A", "O_HGL_B", "WW_B4"]
    assert repair["engine_mapping"]["terminal_duration_guard_s"] == "0.5"
    assert catalogue["authority"]["repair_declaration_sha256"] == request.MAPPING_REPAIR_SHA256
    assert request.canonical_json_bytes(repair) == W2_W4_REPAIR.read_bytes()
    assert request.canonical_json_bytes(catalogue) == W2_CATALOGUE.read_bytes()


def test_solver_convergence_amendment_is_exact_and_changes_no_acceptance_rule() -> None:
    amendment = solver_convergence.read_amendment(
        SOLVER_CONVERGENCE.read_bytes()
    )

    assert amendment["engine_options"] == {
        "HEAD_TOLERANCE": "0.0000001",
        "MAX_TRIALS": 50,
    }
    assert (
        amendment["boundaries"]["adds_source_derived_method_bound"]
        is True
    )
    assert (
        amendment["boundaries"]["changes_preregistered_hard_ceilings"]
        is False
    )
    assert amendment["boundaries"]["changes_physical_model"] is False


def test_builds_and_revalidates_a_path_free_canonical_request() -> None:
    raw = request.build_anchor_request(
        authority_bytes=W1_DECLARATION.read_bytes(),
        catalogue_bytes=W2_CATALOGUE.read_bytes(),
        case_id="G21_OBSTRUCTION_TRIGGER",
        engine_identity=ENGINE_IDENTITY,
        repair_bytes=W2_W4_REPAIR.read_bytes(),
        solver_convergence_bytes=SOLVER_CONVERGENCE.read_bytes(),
    )

    parsed = request.read_request(raw)

    assert parsed["case"]["case_id"] == "G21_OBSTRUCTION_TRIGGER"
    assert parsed["case"]["horizon_s"] == 120
    assert parsed["case"]["mechanism_state"]["pump-a"] == {
        "clearance-loss": "0",
        "obstruction": "0.75",
    }
    assert parsed["authority"]["repair_declaration_sha256"] == request.MAPPING_REPAIR_SHA256
    assert (
        parsed["authority"]["solver_convergence_amendment_sha256"]
        == solver_convergence.AMENDMENT_SHA256
    )
    assert parsed["request_content_id"] == request.request_content_id(parsed)
    assert b"/Users/" not in raw
    assert b"executed_at" not in raw


def test_builds_a_valid_non_anchor_member_request() -> None:
    member = request.anchor_member(W1_DECLARATION.read_bytes())
    for parameter in member["parameters"]:
        if parameter["identity"] == "system.D":
            parameter["value"] = "0.190"
    member["member_content_id"] = request.member_content_id(member)

    raw = request.build_member_request(
        authority_bytes=W1_DECLARATION.read_bytes(),
        catalogue_bytes=W2_CATALOGUE.read_bytes(),
        case_id="G12_CLEAN_ASSESS",
        engine_identity=ENGINE_IDENTITY,
        member=member,
        repair_bytes=W2_W4_REPAIR.read_bytes(),
        solver_convergence_bytes=SOLVER_CONVERGENCE.read_bytes(),
    )

    parsed = request.read_request(raw)
    assert parsed["member"] == member
    assert parsed["case"]["case_id"] == "G12_CLEAN_ASSESS"


@pytest.mark.parametrize(
    ("mutator", "failure_code"),
    [
        (
            lambda value: {**value, "workspace": "/tmp/forbidden"},
            "request-shape",
        ),
        (
            lambda value: {
                **value,
                "member": {
                    **value["member"],
                    "parameters": value["member"]["parameters"][:-1],
                },
            },
            "content-identity",
        ),
        (
            lambda value: {
                **value,
                "member": {
                    **value["member"],
                    "parameters": [
                        (
                            {**parameter, "unit": "s"}
                            if parameter["identity"] == "well.D_w"
                            else parameter
                        )
                        for parameter in value["member"]["parameters"]
                    ],
                },
            },
            "content-identity",
        ),
        (
            lambda value: {
                **value,
                "case": {**value["case"], "horizon_s": 121},
            },
            "content-identity",
        ),
        (
            lambda value: {
                **value,
                "outputs": [*value["outputs"], "electrical_power_kw"],
            },
            "content-identity",
        ),
    ],
)
def test_request_rejects_first_failure_without_repairing_input(
    mutator: object,
    failure_code: str,
) -> None:
    valid = json.loads(
        request.build_anchor_request(
            authority_bytes=W1_DECLARATION.read_bytes(),
            catalogue_bytes=W2_CATALOGUE.read_bytes(),
            case_id="G21_OBSTRUCTION_TRIGGER",
            engine_identity=ENGINE_IDENTITY,
            repair_bytes=W2_W4_REPAIR.read_bytes(),
            solver_convergence_bytes=SOLVER_CONVERGENCE.read_bytes(),
        )
    )
    mutate = mutator
    assert callable(mutate)
    malformed = request.canonical_json_bytes(mutate(valid))

    with pytest.raises(request.GeneratorRequestError, match=failure_code):
        request.read_request(malformed)


def test_recomputed_identity_exposes_later_unit_failure_in_declared_order() -> None:
    parsed = json.loads(
        request.build_anchor_request(
            authority_bytes=W1_DECLARATION.read_bytes(),
            catalogue_bytes=W2_CATALOGUE.read_bytes(),
            case_id="G21_OBSTRUCTION_TRIGGER",
            engine_identity=ENGINE_IDENTITY,
            repair_bytes=W2_W4_REPAIR.read_bytes(),
            solver_convergence_bytes=SOLVER_CONVERGENCE.read_bytes(),
        )
    )
    for parameter in parsed["member"]["parameters"]:
        if parameter["identity"] == "well.D_w":
            parameter["unit"] = "s"
    parsed["member"]["member_content_id"] = request.member_content_id(parsed["member"])
    parsed["request_content_id"] = request.request_content_id(parsed)

    with pytest.raises(request.GeneratorRequestError, match="units"):
        request.read_request(request.canonical_json_bytes(parsed))


def test_mapping_repair_rejects_canonical_but_unapproved_content() -> None:
    altered = json.loads(W2_W4_REPAIR.read_bytes())
    altered["status"] = "draft"

    with pytest.raises(request.GeneratorRequestError, match="mapping-repair"):
        request.read_mapping_repair(request.canonical_json_bytes(altered))
