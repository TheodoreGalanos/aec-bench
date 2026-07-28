# ABOUTME: Tests construction and independent checking of the certified reference package.
# ABOUTME: Proves two fresh builds are identical and contain only the four allowed files.

import hashlib
import json
from pathlib import Path

from promotion import package_builder, package_checker
from run_reference_certification import _absence_proof

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = (
    B5_ROOT / "declarations" / "w1-member-authority.json"
)


def _identified(
    value: dict[str, object],
    domain: bytes,
) -> dict[str, object]:
    payload = {
        key: child
        for key, child in value.items()
        if key != "result_content_id"
    }
    raw = (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    value["result_content_id"] = hashlib.sha256(
        domain + raw
    ).hexdigest()
    return value


def _gate_review() -> dict[str, object]:
    return _identified(
        {
            "first_failure": "none",
            "gates": [
                {
                    "criterion_id": f"AG-{index:02d}",
                    "evidence_ids": ["1" * 64],
                    "outcome": "pass",
                }
                for index in range(1, 14)
            ],
            "profile_id": "AU-NSW-LH-SYN-SPS-v1",
            "promotable": False,
            "result_content_id": "",
            "schema_id": "asw-0b5.gate-review.v1",
            "terminal_state": "gate-review-pass",
            "validity": {
                "v0": "pass",
                "v1": "pass",
                "v2": "pass",
                "v3": "pass",
                "v4": "unclaimed",
            },
        },
        b"asw-0b5.gate-review.v1\0",
    )


def _family_pass() -> bytes:
    value = _identified(
        {
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
        },
        b"asw-0b5.family-decision.v2\0",
    )
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _reference_checks() -> list[dict[str, object]]:
    roles = (
        ("zero-flow", "G00_ZERO_STATIC", "C-R13"),
        ("clean", "G12_CLEAN_ASSESS", "C-R18"),
        ("degraded", "G21_OBSTRUCTION_TRIGGER", "C-R18"),
        ("intervention", "G51_CLEAR_A_POST", "C-R19"),
        ("transfer", "G70_TRANSFER", "C-R17"),
        ("ambiguity", "G40_COMBINED_HALF", "C-R20"),
        ("no-maintenance", "G80_NO_MAINTENANCE", "C-R22"),
        ("boundary", "G41_COMBINED_UPPER", "C-R18"),
        ("label-symmetry", "G10_CLEAN_A_BASE", "C-R15"),
    )
    return [
        {
            "check_id": check_id,
            "expected": {
                "classification": "pass",
                "finite_scalar": str(index),
                "unit": "1",
            },
            "input_state_ids": [
                hashlib.sha256(case_id.encode()).hexdigest()
            ],
            "reference_id": f"reference-{role}",
            "role": role,
            "rule_ids": [f"asw-0b4.rule.{role}.v1"],
            "w3_result_content_id": "2" * 64,
            "w4_result_content_id": "3" * 64,
        }
        for index, (role, case_id, check_id) in enumerate(roles)
    ]


def test_compact_references_select_only_nine_falsification_roles() -> None:
    case_ids = (
        "G00_ZERO_STATIC",
        "G10_CLEAN_A_BASE",
        "G11_CLEAN_B_BASE",
        "G12_CLEAN_ASSESS",
        "G21_OBSTRUCTION_TRIGGER",
        "G40_COMBINED_HALF",
        "G41_COMBINED_UPPER",
        "G50_CLEAR_A_PRE",
        "G51_CLEAR_A_POST",
        "G60_REPAIR_PRE",
        "G61_REPAIR_POST",
        "G70_TRANSFER",
        "G80_NO_MAINTENANCE",
    )
    certifier = _identified(
        {
            "cases": [
                {
                    "case_content_id": hashlib.sha256(
                        case_id.encode()
                    ).hexdigest(),
                    "case_id": case_id,
                    "segments": [
                        {
                            "capability": {
                                "drawdown_s": "100",
                                "operating_flow_m3_s": "0.02",
                            }
                        }
                    ],
                }
                for case_id in case_ids
            ],
            "result_content_id": "",
            "schema_id": "asw-0b5.certifier-result.v1",
            "terminal_state": "quantitative-pending-w4",
        },
        b"asw-0b5.certifier-result.v1\0",
    )
    anchor = _identified(
        {
            "evidence": {
                "composable_anchor_checks": {
                    "checks": {
                        "C-R13": {
                            "first_failure": "none",
                            "maximum_ratio": "0",
                            "outcome": "pass",
                        }
                    }
                },
                "relationships": {
                    "checks": {
                        "C-R15": {
                            "compared_series": 12,
                            "first_failure": "none",
                            "outcome": "pass",
                        },
                        "C-R16": {
                            "carry_sha256": "a" * 64,
                            "first_failure": "none",
                            "outcome": "pass",
                        },
                        "C-R18": {
                            "boundary_fragile_count": 0,
                            "first_failure": "none",
                            "outcome": "pass",
                        },
                        "C-R19": {
                            "first_failure": "none",
                            "minimum_excess_m3_s": "0.001",
                            "outcome": "pass",
                        },
                        "C-R20": {
                            "evaluated": 9,
                            "first_failure": "none",
                            "outcome": "pass",
                        },
                        "C-R21": {
                            "first_failure": "none",
                            "minimum_excess_m3_s": "0.002",
                            "outcome": "pass",
                        },
                        "C-R22": {
                            "classification_sequence": [
                                "capable",
                                "review-eligible",
                            ],
                            "first_failure": "none",
                            "flow_loss_m3_s": "0.003",
                            "outcome": "pass",
                        },
                    }
                },
            },
            "first_failure": "none",
            "result_content_id": "",
            "schema_id": "asw-0b5.w4-composition-result.v3",
            "terminal_state": "w4-checks-pass",
        },
        b"asw-0b5.w4-composition-result.v3\0",
    )

    result = package_builder.build_compact_reference_checks(
        anchor_result=anchor,
        certifier_result=certifier,
    )

    assert {item["role"] for item in result} == {
        "ambiguity",
        "boundary",
        "clean",
        "degraded",
        "intervention",
        "label-symmetry",
        "no-maintenance",
        "transfer",
        "zero-flow",
    }
    transfer = next(
        item for item in result if item["role"] == "transfer"
    )
    assert transfer["expected"]["content_hash"] == "a" * 64
    no_maintenance = next(
        item for item in result if item["role"] == "no-maintenance"
    )
    assert no_maintenance["expected"]["classification_sequence"] == [
        "capable",
        "review-eligible",
    ]


def test_two_fresh_package_builds_are_identical_and_conform(
    tmp_path: Path,
) -> None:
    arguments = {
        "authority_bytes": W1_DECLARATION.read_bytes(),
        "family_result_bytes": _family_pass(),
        "gate_review": _gate_review(),
        "generation_id": "5" * 64,
        "reference_checks": _reference_checks(),
    }

    first = package_builder.build_certified_reference_package(
        target=tmp_path / "first",
        **arguments,
    )
    second = package_builder.build_certified_reference_package(
        target=tmp_path / "second",
        **arguments,
    )

    assert sorted(path.name for path in first.root.iterdir()) == [
        "physical-member.json",
        "physical-reference-checks.json",
        "promotion-manifest.json",
        "public-profile.json",
    ]
    assert first.package_content_id == second.package_content_id
    assert first.manifest_content_id == second.manifest_content_id
    for name in (
        "physical-member.json",
        "physical-reference-checks.json",
        "promotion-manifest.json",
        "public-profile.json",
    ):
        assert (first.root / name).read_bytes() == (
            second.root / name
        ).read_bytes()

    report = package_checker.check_package(first.root)

    assert report["terminal_state"] == "package-conformance-pass"
    assert report["package_content_id"] == first.package_content_id
    assert report["manifest_content_id"] == (
        first.manifest_content_id
    )
    assert report["compact_reference_count"] == 9
    assert len(report["result_content_id"]) == 64
    assert first.rights_review["terminal_state"] == "rights-review-pass"
    assert first.visibility_review["terminal_state"] == (
        "visibility-review-pass"
    )


def test_checker_rejects_an_extra_file(tmp_path: Path) -> None:
    built = package_builder.build_certified_reference_package(
        authority_bytes=W1_DECLARATION.read_bytes(),
        family_result_bytes=_family_pass(),
        gate_review=_gate_review(),
        generation_id="5" * 64,
        reference_checks=_reference_checks(),
        target=tmp_path / "package",
    )
    (built.root / "extra.json").write_text("{}\n", encoding="utf-8")

    try:
        package_checker.check_package(built.root)
    except package_checker.PackageConformanceError as error:
        assert "root inventory" in str(error)
    else:
        raise AssertionError("extra package file was accepted")


def test_package_passes_with_research_solver_and_network_blocked(
    tmp_path: Path,
) -> None:
    built = package_builder.build_certified_reference_package(
        authority_bytes=W1_DECLARATION.read_bytes(),
        family_result_bytes=_family_pass(),
        gate_review=_gate_review(),
        generation_id="5" * 64,
        reference_checks=_reference_checks(),
        target=tmp_path / "package",
    )

    proof, conformance = _absence_proof(
        engine_receipt=tmp_path / "engine" / "receipt.json",
        package_root=built.root,
        workspace=tmp_path / "absence",
    )

    assert proof["terminal_state"] == "absence-proof-pass"
    assert proof["network_access"] == "denied"
    assert proof["forbidden_dependencies_absent"] == [
        "certifier",
        "generator",
        "network",
        "research-tree",
        "swmm",
    ]
    assert conformance["terminal_state"] == "package-conformance-pass"
