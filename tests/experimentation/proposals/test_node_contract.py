# ABOUTME: Tests reward-blind structural checking of proposal semantic-node and finalizer outputs.
# ABOUTME: Proves canonical handoffs are emitted only from exact graph-bound evidence.

from __future__ import annotations

import hashlib
import json
from typing import cast

import pytest

from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.output_completion import (
    OutputCommitAttestation,
    OutputCompletionContract,
    evaluate_output_completion,
)
from aec_bench.contracts.proposal_execution.graph import (
    FinalSynthesisSpec,
    NodeEvidenceContract,
    ProposalInputPort,
    ProposalOutputPort,
    ProposalSourceScope,
    SemanticSubtaskSpec,
)
from aec_bench.contracts.proposal_execution_types import ProposalPortKind
from aec_bench.experimentation.proposals.node_contract import (
    ProposalNodeContractCheck,
    ProposalNodeContractError,
    check_finalizer_output,
    check_semantic_node_output,
    semantic_node_output_contract,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _semantic_node(
    *,
    allow_explicit_data_gap: bool = False,
) -> SemanticSubtaskSpec:
    return SemanticSubtaskSpec(
        node_id="analyse",
        objective="Produce graph-bound findings and a decision.",
        source_scope=ProposalSourceScope(source_ids=("source.report",)),
        input_ports=(
            ProposalInputPort(
                input_id="prior",
                kind=ProposalPortKind.FINDING_SET,
            ),
        ),
        output_ports=(
            ProposalOutputPort(
                output_id="findings",
                kind=ProposalPortKind.FINDING_SET,
            ),
            ProposalOutputPort(
                output_id="decision",
                kind=ProposalPortKind.DECISION_RECORD,
            ),
        ),
        evidence_contract=NodeEvidenceContract(
            required_output_ids=("decision", "findings"),
            require_provenance=True,
            allow_explicit_data_gap=allow_explicit_data_gap,
        ),
    )


def _semantic_payload() -> dict[str, object]:
    return {
        "provenance": [
            "source.report",
            _sha("upstream-prior"),
        ],
        "outputs": {
            "findings": [
                {
                    "finding": "The report identifies a capacity constraint.",
                    "source": "source.report",
                },
            ],
            "decision": {
                "status": "review_required",
            },
        },
    }


def _semantic_outputs(payload: dict[str, object]) -> dict[str, object]:
    return dict(cast(dict[str, object], payload["outputs"]))


def _finding_codes(checked: ProposalNodeContractCheck) -> list[str]:
    return cast(list[str], checked.details["finding_codes"])


def _canonical_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _semantic_markdown(payload: object) -> bytes:
    encoded = json.dumps(
        payload,
        allow_nan=True,
        ensure_ascii=False,
        indent=2,
    )
    return f"# Semantic result\n\n```json\n{encoded}\n```\n".encode()


def _finalizer() -> tuple[FinalSynthesisSpec, OutputCompletionContract]:
    contract = OutputCompletionContract(
        schema_version="aecbench.output-completion-contract.v1",
        output_path="/workspace/output.md",
        format="markdown_final_fenced_json",
        required_top_level_keys=("summary",),
        require_single_final_json_block=True,
    )
    return (
        FinalSynthesisSpec(
            node_id="finalize",
            objective="Synthesize the verified proposal handoffs.",
            source_scope=ProposalSourceScope(source_ids=()),
            input_ports=(
                ProposalInputPort(
                    input_id="decision",
                    kind=ProposalPortKind.DECISION_RECORD,
                ),
            ),
            output_completion_contract_sha256=canonical_json_sha256(
                contract.model_dump(mode="json"),
            ),
        ),
        contract,
    )


def _final_output() -> bytes:
    return b'# Final response\n\n```json\n{"summary":"Review complete."}\n```\n'


def _output_commit(
    *,
    output: bytes,
    contract: OutputCompletionContract,
) -> OutputCommitAttestation:
    evaluation = evaluate_output_completion(
        contract,
        output.decode("utf-8"),
    )
    return OutputCommitAttestation(
        schema_version="aecbench.output-commit-attestation.v1",
        mechanism="agent_explicit_output_commit",
        output_path=contract.output_path,
        output_sha256=hashlib.sha256(output).hexdigest(),
        output_size_bytes=len(output),
        completion_contract_sha256=canonical_json_sha256(
            contract.model_dump(mode="json"),
        ),
        completion_evaluation=evaluation,
        initial_output_sha256=None,
        commit_turn=3,
    )


def _check_semantic_payload(
    payload: object,
    *,
    node: SemanticSubtaskSpec | None = None,
) -> ProposalNodeContractCheck:
    contract = semantic_node_output_contract(output_path="/workspace/output.md")
    output = _semantic_markdown(payload)
    evaluation = evaluate_output_completion(
        contract,
        output.decode("utf-8"),
    )
    commit = _output_commit(output=output, contract=contract) if evaluation.complete else None
    return check_semantic_node_output(
        node=node or _semantic_node(),
        output_contract=contract,
        raw_output_bytes=output,
        completion_commit=commit,
        upstream_artifact_ids={"prior": _sha("upstream-prior")},
    )


def test_semantic_node_returns_canonical_per_output_handoffs_and_details() -> None:
    node = _semantic_node()
    checked = _check_semantic_payload(_semantic_payload(), node=node)

    assert checked.satisfied is True
    assert tuple(handoff.output_id for handoff in checked.handoffs) == (
        "decision",
        "findings",
    )
    assert checked.canonical_details_bytes == _canonical_bytes(checked.details)
    assert (
        checked.details_sha256
        == hashlib.sha256(
            checked.canonical_details_bytes,
        ).hexdigest()
    )
    assert checked.details["node_contract_sha256"] == node.evidence_contract.content_sha256
    assert checked.details["finding_codes"] == []
    assert checked.details["completion_reason"] == "complete"
    assert isinstance(checked.details["output_commit_attestation_sha256"], str)
    assert checked.details["required_provenance_ids"] == sorted(
        ("source.report", _sha("upstream-prior")),
    )

    for handoff in checked.handoffs:
        assert handoff.canonical_bytes == _canonical_bytes(
            json.loads(handoff.canonical_bytes),
        )
        assert (
            handoff.artifact_sha256
            == hashlib.sha256(
                handoff.canonical_bytes,
            ).hexdigest()
        )
        payload = json.loads(handoff.canonical_bytes)
        assert payload["producer_node_id"] == node.node_id
        assert payload["output_id"] == handoff.output_id
        assert payload["provenance"] == sorted(
            ("source.report", _sha("upstream-prior")),
        )


@pytest.mark.parametrize(
    ("payload", "finding_code"),
    [
        (
            _semantic_payload() | {"extra": True},
            "top_level_fields_mismatch",
        ),
        (
            {
                **_semantic_payload(),
                "outputs": {
                    "decision": {"status": "review_required"},
                },
            },
            "output_ids_mismatch",
        ),
        (
            {
                **_semantic_payload(),
                "outputs": {
                    **_semantic_outputs(_semantic_payload()),
                    "undeclared": "not graph-bound",
                },
            },
            "output_ids_mismatch",
        ),
        (
            {
                **_semantic_payload(),
                "provenance": [
                    "source.report",
                    _sha("upstream-prior"),
                    "source.report",
                ],
            },
            "provenance_duplicate",
        ),
        (
            {
                **_semantic_payload(),
                "provenance": ["source.report", _sha("unknown-upstream")],
            },
            "provenance_ids_mismatch",
        ),
        (
            {
                **_semantic_payload(),
                "provenance": ["source.report", 7],
            },
            "provenance_entry_invalid",
        ),
        (
            ["not", "an", "object"],
            "completion_final_json_not_object",
        ),
        (
            {
                **_semantic_payload(),
                "outputs": {
                    **_semantic_outputs(_semantic_payload()),
                    "findings": {
                        "explicit_data_gap": {
                            "reason": "The public report omits the model run.",
                        },
                    },
                },
            },
            "explicit_data_gap_forbidden",
        ),
    ],
)
def test_semantic_contract_misses_return_false_without_handoffs(
    payload: object,
    finding_code: str,
) -> None:
    checked = _check_semantic_payload(payload)

    assert checked.satisfied is False
    assert checked.handoffs == ()
    assert finding_code in _finding_codes(checked)
    assert checked.canonical_details_bytes == _canonical_bytes(checked.details)


def test_semantic_contract_accepts_only_the_declared_explicit_data_gap_shape() -> None:
    payload = _semantic_payload()
    outputs = _semantic_outputs(payload)
    outputs["findings"] = {
        "explicit_data_gap": {
            "reason": "The public report omits the model run.",
        },
    }
    payload["outputs"] = outputs

    accepted = _check_semantic_payload(
        payload,
        node=_semantic_node(allow_explicit_data_gap=True),
    )
    assert accepted.satisfied is True
    assert accepted.details["explicit_data_gap_output_ids"] == ["findings"]

    outputs["findings"] = {
        "explicit_data_gap": {
            "reason": "",
            "extra": "not declared",
        },
    }
    rejected = _check_semantic_payload(
        payload,
        node=_semantic_node(allow_explicit_data_gap=True),
    )
    assert rejected.satisfied is False
    assert "explicit_data_gap_invalid" in _finding_codes(rejected)


@pytest.mark.parametrize(
    ("raw", "finding_code"),
    [
        (
            b"\xff",
            "output_not_utf8",
        ),
        (
            b'```json\n{"outputs":{"decision":1,"decision":2,"findings":[]},"provenance":["source.report"]}\n```\n',
            "candidate_json_duplicate_key",
        ),
        (
            b'```json\n{"outputs":{"decision":NaN,"findings":[]},"provenance":["source.report"]}\n```\n',
            "candidate_json_non_finite",
        ),
    ],
)
def test_malformed_semantic_output_is_a_candidate_contract_miss(
    raw: bytes,
    finding_code: str,
) -> None:
    contract = semantic_node_output_contract(output_path="/workspace/output.md")
    commit = None
    try:
        evaluation = evaluate_output_completion(contract, raw.decode("utf-8"))
    except UnicodeDecodeError:
        pass
    else:
        if evaluation.complete:
            commit = _output_commit(output=raw, contract=contract)

    checked = check_semantic_node_output(
        node=_semantic_node(),
        output_contract=contract,
        raw_output_bytes=raw,
        completion_commit=commit,
        upstream_artifact_ids={"prior": _sha("upstream-prior")},
    )

    assert checked.satisfied is False
    assert checked.handoffs == ()
    assert finding_code in _finding_codes(checked)


@pytest.mark.parametrize(
    ("raw", "finding_code"),
    [
        (
            json.dumps(_semantic_payload()).encode("utf-8"),
            "completion_final_json_block_missing",
        ),
        (
            b"not json",
            "completion_final_json_block_missing",
        ),
        (
            _semantic_markdown(_semantic_payload()) + b"trailing content",
            "completion_final_json_block_not_final",
        ),
        (
            _semantic_markdown(_semantic_payload()) + _semantic_markdown(_semantic_payload()),
            "completion_multiple_final_json_blocks",
        ),
        (
            b"```json\nnot json\n```\n",
            "completion_final_json_malformed",
        ),
    ],
)
def test_semantic_node_requires_one_final_fenced_json_object(
    raw: bytes,
    finding_code: str,
) -> None:
    contract = semantic_node_output_contract(output_path="/workspace/output.md")

    checked = check_semantic_node_output(
        node=_semantic_node(),
        output_contract=contract,
        raw_output_bytes=raw,
        completion_commit=None,
        upstream_artifact_ids={"prior": _sha("upstream-prior")},
    )

    assert checked.satisfied is False
    assert checked.handoffs == ()
    assert finding_code in _finding_codes(checked)
    assert "output_commit_missing" in _finding_codes(checked)


@pytest.mark.parametrize(
    "upstream_artifact_ids",
    [
        {},
        {
            "prior": _sha("upstream-prior"),
            "undeclared": _sha("undeclared"),
        },
        {"prior": "not-a-sha"},
    ],
)
def test_invalid_host_upstream_bindings_raise_instead_of_scoring_candidate(
    upstream_artifact_ids: dict[str, str],
) -> None:
    contract = semantic_node_output_contract(output_path="/workspace/output.md")
    output = _semantic_markdown(_semantic_payload())
    with pytest.raises(ProposalNodeContractError) as exc_info:
        check_semantic_node_output(
            node=_semantic_node(),
            output_contract=contract,
            raw_output_bytes=output,
            completion_commit=_output_commit(output=output, contract=contract),
            upstream_artifact_ids=upstream_artifact_ids,
        )

    assert exc_info.value.code == "contract_binding_invalid"


def test_semantic_host_error_precedence_is_stable() -> None:
    node = _semantic_node()
    expected = semantic_node_output_contract(output_path="/workspace/output.md")
    mismatched = expected.model_copy(
        update={"required_top_level_keys": ("outputs",)},
    )
    valid_output = _semantic_markdown(_semantic_payload())
    valid_commit = _output_commit(output=valid_output, contract=expected)
    malformed_output = (
        b'```json\n{"outputs":{"decision":1,"decision":2,"findings":[]},"provenance":["source.report"]}\n```\n'
    )

    with pytest.raises(
        ProposalNodeContractError,
        match="upstream artifact bindings must exactly match",
    ) as upstream_error:
        check_semantic_node_output(
            node=node,
            output_contract=mismatched,
            raw_output_bytes=malformed_output,
            completion_commit=valid_commit,
            upstream_artifact_ids={},
        )
    assert upstream_error.value.code == "contract_binding_invalid"

    with pytest.raises(
        ProposalNodeContractError,
        match="semantic node requires the host-built",
    ) as contract_error:
        check_semantic_node_output(
            node=node,
            output_contract=mismatched,
            raw_output_bytes=malformed_output,
            completion_commit=valid_commit,
            upstream_artifact_ids={"prior": _sha("upstream-prior")},
        )
    assert contract_error.value.code == "contract_binding_invalid"

    with pytest.raises(
        ProposalNodeContractError,
        match="semantic-node output evidence must be exact bytes",
    ) as evidence_error:
        check_semantic_node_output(
            node=node,
            output_contract=expected,
            raw_output_bytes=bytearray(malformed_output),  # type: ignore[arg-type]
            completion_commit=valid_commit,
            upstream_artifact_ids={"prior": _sha("upstream-prior")},
        )
    assert evidence_error.value.code == "host_evidence_invalid"

    with pytest.raises(
        ProposalNodeContractError,
        match="output bytes, completion contract, and commit attestation differ",
    ) as integrity_error:
        check_semantic_node_output(
            node=node,
            output_contract=expected,
            raw_output_bytes=malformed_output,
            completion_commit=valid_commit,
            upstream_artifact_ids={"prior": _sha("upstream-prior")},
        )
    assert integrity_error.value.code == "output_integrity_failure"


def test_semantic_candidate_findings_are_exhaustive_and_canonical() -> None:
    payload = {
        **_semantic_payload(),
        "extra": True,
        "outputs": {
            "decision": {
                "explicit_data_gap": {
                    "reason": "",
                    "extra": "not declared",
                },
            },
            "findings": [],
            "undeclared": "not graph-bound",
        },
        "provenance": ["source.report", "source.report"],
    }

    checked = _check_semantic_payload(payload)

    assert checked.satisfied is False
    assert checked.handoffs == ()
    assert checked.details["finding_codes"] == [
        "explicit_data_gap_invalid",
        "output_ids_mismatch",
        "provenance_duplicate",
        "provenance_ids_mismatch",
        "top_level_fields_mismatch",
    ]


def test_malformed_complete_json_and_missing_commit_remain_candidate_findings() -> None:
    contract = semantic_node_output_contract(output_path="/workspace/output.md")
    output = b'```json\n{"outputs":{"decision":1,"decision":2,"findings":[]},"provenance":["source.report"]}\n```\n'

    checked = check_semantic_node_output(
        node=_semantic_node(),
        output_contract=contract,
        raw_output_bytes=output,
        completion_commit=None,
        upstream_artifact_ids={"prior": _sha("upstream-prior")},
    )

    assert checked.satisfied is False
    assert checked.handoffs == ()
    assert checked.details["finding_codes"] == [
        "candidate_json_duplicate_key",
        "output_commit_missing",
    ]


def test_semantic_node_requires_a_bound_commit_before_emitting_handoffs() -> None:
    contract = semantic_node_output_contract(output_path="/workspace/output.md")
    output = _semantic_markdown(_semantic_payload())

    checked = check_semantic_node_output(
        node=_semantic_node(),
        output_contract=contract,
        raw_output_bytes=output,
        completion_commit=None,
        upstream_artifact_ids={"prior": _sha("upstream-prior")},
    )

    assert checked.satisfied is False
    assert checked.handoffs == ()
    assert checked.details["completion_reason"] == "complete"
    assert checked.details["output_commit_attestation_sha256"] is None
    assert "output_commit_missing" in _finding_codes(checked)


def test_semantic_contract_and_commit_mismatches_raise_host_errors() -> None:
    node = _semantic_node()
    expected = semantic_node_output_contract(output_path="/workspace/output.md")
    output = _semantic_markdown(_semantic_payload())
    commit = _output_commit(output=output, contract=expected)
    mismatched = expected.model_copy(
        update={"required_top_level_keys": ("outputs",)},
    )

    with pytest.raises(ProposalNodeContractError) as binding_error:
        check_semantic_node_output(
            node=node,
            output_contract=mismatched,
            raw_output_bytes=output,
            completion_commit=commit,
            upstream_artifact_ids={"prior": _sha("upstream-prior")},
        )
    assert binding_error.value.code == "contract_binding_invalid"

    with pytest.raises(ProposalNodeContractError) as integrity_error:
        check_semantic_node_output(
            node=node,
            output_contract=expected,
            raw_output_bytes=output + b"tampered",
            completion_commit=commit,
            upstream_artifact_ids={"prior": _sha("upstream-prior")},
        )
    assert integrity_error.value.code == "output_integrity_failure"


def test_finalizer_checks_public_completion_and_commit_without_hidden_verifier() -> None:
    finalizer, contract = _finalizer()
    output = _final_output()
    commit = _output_commit(output=output, contract=contract)

    checked = check_finalizer_output(
        finalizer=finalizer,
        output_contract=contract,
        raw_output_bytes=output,
        completion_commit=commit,
    )

    assert checked.satisfied is True
    assert checked.handoffs == ()
    assert checked.details["hidden_verifier_used"] is False
    assert checked.details["completion_reason"] == "complete"
    assert checked.details["output_commit_attestation_sha256"] == commit.content_sha256
    assert checked.canonical_details_bytes == _canonical_bytes(checked.details)
    assert "reward" not in checked.canonical_details_bytes.decode("utf-8")
    assert "verifier" not in {key for key in checked.details if key != "hidden_verifier_used"}


def test_finalizer_shape_and_missing_commit_are_candidate_contract_misses() -> None:
    finalizer, contract = _finalizer()

    valid_but_uncommitted = check_finalizer_output(
        finalizer=finalizer,
        output_contract=contract,
        raw_output_bytes=_final_output(),
        completion_commit=None,
    )
    assert valid_but_uncommitted.satisfied is False
    assert "output_commit_missing" in _finding_codes(valid_but_uncommitted)

    incomplete = check_finalizer_output(
        finalizer=finalizer,
        output_contract=contract,
        raw_output_bytes=b"# No final JSON block\n",
        completion_commit=None,
    )
    assert incomplete.satisfied is False
    assert "completion_final_json_block_missing" in _finding_codes(incomplete)


def test_finalizer_binding_and_output_integrity_fail_as_host_errors() -> None:
    finalizer, contract = _finalizer()
    output = _final_output()
    commit = _output_commit(output=output, contract=contract)
    wrong_finalizer = finalizer.model_copy(
        update={
            "output_completion_contract_sha256": _sha("other-contract"),
        },
    )

    with pytest.raises(ProposalNodeContractError) as binding_error:
        check_finalizer_output(
            finalizer=wrong_finalizer,
            output_contract=contract,
            raw_output_bytes=output,
            completion_commit=commit,
        )
    assert binding_error.value.code == "contract_binding_invalid"

    with pytest.raises(ProposalNodeContractError) as integrity_error:
        check_finalizer_output(
            finalizer=finalizer,
            output_contract=contract,
            raw_output_bytes=b"tampered",
            completion_commit=commit,
        )
    assert integrity_error.value.code == "output_integrity_failure"
