# ABOUTME: Specifies deterministic W3 result vocabulary, first-failure behavior, and non-promotion boundaries.
# ABOUTME: Requires malformed transport to reject without emitting pass, certification, or acceptance claims.

from __future__ import annotations

from pathlib import Path

from certifier import boundary, certification

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"


def test_malformed_transport_emits_deterministic_input_rejection() -> None:
    first = certification.certify_bundle(
        b"{}\n",
        W1_DECLARATION.read_bytes(),
    )
    second = certification.certify_bundle(
        b"{}\n",
        W1_DECLARATION.read_bytes(),
    )

    assert first == second
    assert first["terminal_state"] == "certifier-input-reject"
    assert first["first_failing_stage"] == "bundle-shape"
    assert first["promotable"] is False
    assert first["checks"] == [
        {
            "check_id": "C-INPUT",
            "outcome": "reject",
            "stage": "bundle-shape",
        }
    ]
    assert "result_content_id" in first
    rendered = certification.certification_result_bytes(first)
    assert boundary.canonical_json_bytes(first) == rendered
    assert b'"pass"' not in rendered
    assert b'"accepted"' not in rendered
    assert b'"certified"' not in rendered
