# ABOUTME: Specifies W5's fail-closed package gate and immutable V3 refusal.
# ABOUTME: Proves a rejected family creates no payload, package, manifest, or false downstream review.

import ast
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
