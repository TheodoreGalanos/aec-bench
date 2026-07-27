# ABOUTME: Specifies W4-owned parsing of replayed transfer bytes and threshold-free W3 results.
# ABOUTME: Prevents composition from importing certifier parsers or trusting declared role hashes.

import hashlib

import pytest
from sensitivity import catalogue, inputs


def _role(role: str, value: dict[str, object]) -> dict[str, str]:
    raw = catalogue.canonical_json_bytes(value)
    return {
        "bytes_hex": raw.hex(),
        "role": role,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _bundle() -> bytes:
    roles = [
        _role("request", {"request": "value"}),
        _role("pump-a-original-curve", {"curve": "ao"}),
        _role("pump-a-engine-curve", {"curve": "ae"}),
        _role("pump-b-original-curve", {"curve": "bo"}),
        _role("pump-b-engine-curve", {"curve": "be"}),
        _role("semantic-candidate", {"semantic": "value"}),
    ]
    case = {
        "case_id": "G00_ZERO_STATIC",
        "segments": [{"roles": roles, "segment_id": "single"}],
    }
    return catalogue.canonical_json_bytes(
        {
            "profile_id": "AU-NSW-LH-SYN-SPS-v1",
            "promotable": False,
            "replays": [
                {"cases": [case], "ordinal": 0},
                {"cases": [case], "ordinal": 1},
            ],
            "schema_id": "asw-0b5.certifier-input-bundle.v1",
        }
    )


def _certifier_result(bundle: bytes) -> bytes:
    value = {
        "authorities": {
            "profile_id": "AU-NSW-LH-SYN-SPS-v1",
            "protocol_id": "asw-0b4.independent-certification-protocol.v2",
            "w1_sha256": inputs.W1_PROTOCOL_SHA256,
            "w3_sha256": inputs.W3_PROTOCOL_SHA256,
        },
        "bundle_sha256": hashlib.sha256(bundle).hexdigest(),
        "cases": [
            {
                "case_content_id": "1" * 64,
                "case_id": "G00_ZERO_STATIC",
                "segments": [
                    {
                        "capability": {"classification": "not-applicable"},
                        "residuals": {f"C-R{index:02d}": {"values": ["0"]} for index in range(1, 25)},
                        "segment_id": "single",
                        "terminal_state": "quantitative-pending-w4",
                    }
                ],
                "terminal_state": "quantitative-pending-w4",
            }
        ],
        "checks": [
            {
                "check_id": "C-REPLAY",
                "outcome": "satisfied",
                "stage": "replay-identity",
            }
        ],
        "first_failing_stage": "w4-tolerance-required",
        "promotable": False,
        "residual_register": [
            {
                "check_id": f"C-R{index:02d}",
                "classification": "observed-pending-w4",
                "name": f"residual-{index}",
            }
            for index in range(1, 25)
        ],
        "result_content_id": "",
        "schema_id": "asw-0b5.certifier-result.v1",
        "terminal_state": "quantitative-pending-w4",
    }
    value["result_content_id"] = hashlib.sha256(
        inputs.CERTIFIER_RESULT_DOMAIN
        + catalogue.canonical_json_bytes({key: child for key, child in value.items() if key != "result_content_id"})
    ).hexdigest()
    return catalogue.canonical_json_bytes(value)


def test_reads_exact_replayed_roles_without_certifier_helpers() -> None:
    parsed = inputs.read_transfer_bundle(_bundle())

    assert len(parsed) == 1
    assert parsed[0].case_id == "G00_ZERO_STATIC"
    assert parsed[0].segment_id == "single"
    assert parsed[0].request == {"request": "value"}
    assert parsed[0].semantic == {"semantic": "value"}
    assert tuple(parsed[0].role_sha256) == inputs.ROLE_IDS


def test_rejects_changed_role_hash_and_replay() -> None:
    raw = _bundle()
    value = inputs.read_canonical_object(raw)
    for replay in value["replays"]:
        replay["cases"][0]["segments"][0]["roles"][0]["sha256"] = "0" * 64
    with pytest.raises(inputs.SensitivityInputError, match="role hash"):
        inputs.read_transfer_bundle(catalogue.canonical_json_bytes(value))

    value = inputs.read_canonical_object(raw)
    value["replays"][1]["cases"][0]["segments"][0]["segment_id"] = "changed"
    with pytest.raises(inputs.SensitivityInputError, match="replay differs"):
        inputs.read_transfer_bundle(catalogue.canonical_json_bytes(value))


def test_reads_independently_identified_certifier_result_bound_to_bundle() -> None:
    bundle = _bundle()

    result = inputs.read_certifier_result(
        _certifier_result(bundle),
        bundle_bytes=bundle,
        segments=inputs.read_transfer_bundle(bundle),
    )

    assert result.terminal_state == "quantitative-pending-w4"
    assert result.result_content_id
    assert result.segment_results[("G00_ZERO_STATIC", "single")]["residuals"]["C-R24"]["values"] == ["0"]


def test_rejects_certifier_result_identity_or_segment_drift() -> None:
    bundle = _bundle()
    raw = _certifier_result(bundle)
    changed = inputs.read_canonical_object(raw)
    changed["result_content_id"] = "0" * 64
    with pytest.raises(inputs.SensitivityInputError, match="result identity"):
        inputs.read_certifier_result(
            catalogue.canonical_json_bytes(changed),
            bundle_bytes=bundle,
            segments=inputs.read_transfer_bundle(bundle),
        )

    changed = inputs.read_canonical_object(raw)
    changed["cases"][0]["segments"][0]["segment_id"] = "changed"
    payload = {key: child for key, child in changed.items() if key != "result_content_id"}
    changed["result_content_id"] = hashlib.sha256(
        inputs.CERTIFIER_RESULT_DOMAIN + catalogue.canonical_json_bytes(payload)
    ).hexdigest()
    with pytest.raises(inputs.SensitivityInputError, match="segment inventory"):
        inputs.read_certifier_result(
            catalogue.canonical_json_bytes(changed),
            bundle_bytes=bundle,
            segments=inputs.read_transfer_bundle(bundle),
        )
