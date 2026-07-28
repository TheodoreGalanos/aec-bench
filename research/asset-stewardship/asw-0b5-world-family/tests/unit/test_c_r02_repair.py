# ABOUTME: Specifies the staged C-R02 authority and pinned routing correction.
# ABOUTME: Proves the retained startup shortfall closes without changing its budget.

import json
from decimal import Decimal
from pathlib import Path

import pytest
from repairs import c_r02

B5_ROOT = Path(__file__).parents[2]
AMENDMENT = (
    B5_ROOT
    / "declarations"
    / "w4-c-r02-routing-integration-amendment.json"
)
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
RETAINED_RESULT = (
    B5_ROOT
    / "results"
    / "v3-c-r02-refusal"
    / "w4-composition-result.json"
)


def test_reads_exact_c_r02_routing_integration_amendment() -> None:
    value = c_r02.read_amendment(AMENDMENT.read_bytes())

    assert value["authority"]["engine_commit"] == (
        "7952ca837988b1c32f791812eccc9fd64547e093"
    )
    assert value["failed_execution"]["generation_id"] == (
        "e31e64bd8f696dcb8edaa5bd2ad76f7286223094703f4181c6a203c03c49b2d0"
    )
    assert value["rules"]["C-R02"]["routing_defect_rule"] == (
        "E_route,k=0.5*dt*(Q_net,k-1-Q_net,k)"
    )
    assert value["rules"]["C-R02"]["application"] == (
        "every-report-interval"
    )
    assert value["rules"]["C-R02"]["total_correction_rule"] == (
        "E_total=E_route+E_storage"
    )
    assert value["rules"]["C-R03"]["dependency_rule"] == (
        "intermediate storage representation terms telescope and "
        "cannot be summed as independent errors"
    )
    assert (
        value["boundaries"][
            "candidate_numerical_values_allowed_for_tolerance_or_fitting"
        ]
        is False
    )
    assert (
        value["boundaries"][
            "candidate_semantic_net_flow_allowed_for_exact_engine_identity"
        ]
        is True
    )


def test_rejects_changed_c_r02_amendment_bytes() -> None:
    changed = AMENDMENT.read_bytes().replace(
        b'"first_segment_prior_net_flow_m3_s": "0"',
        b'"first_segment_prior_net_flow_m3_s": "0.005"',
    )

    with pytest.raises(
        c_r02.C_R02RepairError,
        match="amendment bytes differ",
    ):
        c_r02.read_amendment(changed)


def test_trapezoidal_startup_correction_closes_retained_shortfall() -> None:
    authority = json.loads(W1_DECLARATION.read_bytes())
    low_inflow = next(
        Decimal(item["anchor"])
        for item in authority["parameters"]
        if item["identity"] == "inflow.Q_low"
    )
    retained = json.loads(RETAINED_RESULT.read_bytes())
    evidence = retained["evidence"]["mass"][
        "first_failure_evidence"
    ]

    correction = c_r02.trapezoidal_right_end_defect(
        previous_net_flow_m3_s=0.0,
        current_net_flow_m3_s=float(low_inflow),
        interval_s=1.0,
    )
    corrected = Decimal(evidence["raw_residual_m3"]) - Decimal(
        str(correction)
    )

    assert correction == -0.0025
    assert abs(corrected) <= Decimal(evidence["budget_m3"])


def test_trapezoidal_correction_is_zero_for_steady_net_flow() -> None:
    assert (
        c_r02.trapezoidal_right_end_defect(
            previous_net_flow_m3_s=0.005,
            current_net_flow_m3_s=0.005,
            interval_s=1.0,
        )
        == 0.0
    )
