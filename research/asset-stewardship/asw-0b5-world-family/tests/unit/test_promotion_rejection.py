# ABOUTME: Specifies W5's fail-closed package gate and immutable V3 refusal.
# ABOUTME: Proves a rejected family creates no payload, package, manifest, or false downstream review.

import ast
import hashlib
import json
from pathlib import Path

import pytest
from promotion import decision, package_gate
from sensitivity import family

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
PROBE_DECLARATION = B5_ROOT / "declarations" / "w4-probe-catalogue.json"


def _family_rejection() -> bytes:
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
    return family.family_result_bytes(result)


def _family_pass() -> bytes:
    value = {
        "accepted_member_results": {
            "INT.01.hydraulic-supporting": "1" * 64,
            "INT.02.hydraulic-opposing": "2" * 64,
            "INT.03.primary-dominant": "3" * 64,
        },
        "analytical_inventory_content_id": "4" * 64,
        "anchor_result_content_id": "5" * 64,
        "coverage": {
            "accepted_interaction_count": 3,
            "boundary_probe_count": 11,
            "engine_variant_count": 7,
            "grid_value_count": 32,
            "mutation_count": 30,
            "oat_probe_count": 68,
            "retained_predecessor_rejection_count": 2,
        },
        "engine_result_content_id": "6" * 64,
        "first_failure": "none",
        "mutation_result_content_id": "7" * 64,
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "promotable": False,
        "result_content_id": "",
        "retained_predecessor_rejections": [
            {
                "bundle_sha256": "8" * 64,
                "first_failure": "declared-rejection",
                "probe_id": "INT.01.hydraulic-supporting",
            },
            {
                "bundle_sha256": "9" * 64,
                "first_failure": "declared-rejection",
                "probe_id": "INT.04.secondary-dominant",
            },
        ],
        "schema_id": "asw-0b5.family-decision.v2",
        "selection_amendment_sha256": "a" * 64,
        "terminal_state": "family-w4-checks-pass",
    }
    payload = {
        key: child
        for key, child in value.items()
        if key != "result_content_id"
    }
    canonical = (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    value["result_content_id"] = hashlib.sha256(
        b"asw-0b5.family-decision.v2\0" + canonical
    ).hexdigest()
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def test_rejected_family_cannot_authorize_package_proposal(
    tmp_path: Path,
) -> None:
    target = tmp_path / "package"

    with pytest.raises(
        package_gate.PackageGateError,
        match="family-w4-checks-pass",
    ):
        package_gate.authorize_package_root(
            family_result_bytes=_family_rejection(),
            target=target,
        )

    assert not target.exists()


def test_passing_family_authorizes_one_absent_package_root(
    tmp_path: Path,
) -> None:
    target = tmp_path / "package"

    created = package_gate.authorize_package_root(
        family_result_bytes=_family_pass(),
        target=target,
    )

    assert created == target.resolve()
    assert created.is_dir()
    assert list(created.iterdir()) == []


def test_v3_refusal_is_canonical_immutable_and_names_no_package() -> None:
    result = decision.refuse_v3(_family_rejection())
    raw = decision.promotion_decision_bytes(result)

    assert result["terminal_state"] == "promotion-generation-reject"
    assert result["first_failure"] == "family-member-reject"
    assert result["promotable"] is False
    assert result["manifest_content_ids"] == []
    assert result["package_content_ids"] == []
    assert result["payload_content_ids"] == []
    assert result["downstream_stages"] == {
        "absence_proof": "not-executed-after-generation-reject",
        "gate_review": "not-executed-after-generation-reject",
        "package_conformance": "not-executed-after-generation-reject",
        "rights_review": "not-executed-after-generation-reject",
        "visibility_review": "not-executed-after-generation-reject",
    }
    assert decision.read_promotion_decision(raw) == result
    assert b"/Users/" not in raw
    assert b"/private/" not in raw

    changed = dict(result)
    changed["terminal_state"] = "promotion-v3-issued"
    with pytest.raises(decision.PromotionDecisionError, match="identity"):
        decision.promotion_decision_bytes(changed)


def test_complete_package_evidence_issues_one_immutable_decision() -> None:
    result = decision.issue_certified_reference_package(
        absence_proof_content_id="1" * 64,
        family_result_bytes=_family_pass(),
        gate_review_content_id="2" * 64,
        manifest_content_id="3" * 64,
        package_conformance_content_id="4" * 64,
        package_content_id="5" * 64,
        payload_content_ids=("6" * 64, "7" * 64, "8" * 64),
        rights_review_content_id="9" * 64,
        visibility_review_content_id="a" * 64,
    )
    raw = decision.promotion_decision_bytes(result)

    assert result["terminal_state"] == "promotion-v3-issued"
    assert result["first_failure"] == "none"
    assert result["promotable"] is True
    assert result["manifest_content_ids"] == ["3" * 64]
    assert result["package_content_ids"] == ["5" * 64]
    assert result["payload_content_ids"] == [
        "6" * 64,
        "7" * 64,
        "8" * 64,
    ]
    assert result["v3"] == "issued"
    assert result["v4"] == "unclaimed"
    assert decision.read_promotion_decision(raw) == result


def test_promotion_boundary_imports_no_generation_or_certification_code() -> None:
    for relative in ("promotion/decision.py", "promotion/package_gate.py"):
        tree = ast.parse((B5_ROOT / relative).read_text(encoding="utf-8"))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_roots.add(node.module.split(".", 1)[0])

        assert imported_roots.isdisjoint({"certifier", "generator", "sensitivity"})
