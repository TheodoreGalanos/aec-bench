# ABOUTME: Locks the approved pre-W3 composition repair to canonical bytes and predecessor authorities.
# ABOUTME: Prevents quantitative composition from silently changing residual meaning or fitting edge timing.

from pathlib import Path

from certifier import repair

B5_ROOT = Path(__file__).parents[2]
REPAIR_DECLARATION = B5_ROOT / "declarations" / "w3-w4-quantitative-composition-repair.json"


def test_reads_exact_pre_w3_composition_repair_authority() -> None:
    raw = REPAIR_DECLARATION.read_bytes()

    declaration = repair.read_composition_repair(raw)

    assert repair.canonical_json_bytes(declaration) == raw
    assert declaration["authority"] == {
        "engine_mapping_repair_sha256": ("862ef1f5fc70d882d156c0ef9842bb565301344725d2206edfa49c10910576ca"),
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "repair_schema_id": "asw-0b5.quantitative-composition-repair.v1",
        "scope": "research-private",
        "w3_protocol_predecessor_sha256": ("2b0b13a6f9facaf2f0e18f19a5d41069d8e5708a2df77b6dc6d6ed6c9ec65cde"),
        "w4_protocol_predecessor_sha256": ("56502750816efec73ed821ac00ee5ead4ed76ba05e243992f794005980c19b7f"),
    }
    assert declaration["failed_rules"] == [
        "w3-v1:C-R06:candidate-discharge-minus-wet-well-head-as-pump-head",
        "w3-v1:C-R07:candidate-discharge-minus-wet-well-head-as-system-head",
        "w4-v1:C-R12:fixed-one-report-interval-absolute-edge-window",
    ]
    assert declaration["rules"]["C-R04"]["rule_id"] == ("asw-0b5.rule.pinned-swmm-report-inflow.v1")
    assert declaration["rules"]["C-R06"]["rule_id"] == ("asw-0b5.rule.original-pump-system-closure.v1")
    assert declaration["rules"]["C-R07"]["rule_id"] == ("asw-0b5.rule.net-head-static-hgl-closure.v1")
    assert declaration["rules"]["C-R12"]["rule_id"] == ("asw-0b5.rule.formula-derived-edge-window.v1")
    assert declaration["rules"]["C-R12"]["matching"] == [
        "exact-edge-count",
        "exact-edge-order",
        "exact-edge-type",
        "exact-pump-label",
        "absolute-edge-time",
    ]
    assert declaration["rules"]["C-R12"]["forbidden"] == [
        "candidate-fitted-constant",
        "cycle-deletion",
        "duration-only-matching",
        "dynamic-time-warping",
        "many-to-one-matching",
        "phase-reset",
    ]
    assert declaration["boundaries"]["preserve_exact_bytes"] == [
        "w1-member",
        "w2-case",
        "generator-request",
        "original-pump-curve",
        "engine-pump-curve",
        "semantic-candidate",
    ]
    assert declaration["status"] == "approved-pre-w3-repair"


def test_rejects_canonical_but_unapproved_composition_repair() -> None:
    declaration = repair.read_composition_repair(REPAIR_DECLARATION.read_bytes())
    declaration["rules"]["C-R12"]["minimum_report_intervals"] = 2

    try:
        repair.read_composition_repair(repair.canonical_json_bytes(declaration))
    except repair.CompositionRepairError as error:
        assert "content identity differs" in str(error)
    else:
        raise AssertionError("changed repair declaration was accepted")
