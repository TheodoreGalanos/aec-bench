# ABOUTME: Checks reward-blind structural contracts for proposal semantic-node and finalizer outputs.
# ABOUTME: Emits canonical handoff evidence without consulting hidden answers or task verifiers.

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from pydantic import JsonValue

from aec_bench.contracts.harness_kernel import (
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.output_completion import (
    OutputCommitAttestation,
    OutputCompletionContract,
    OutputCompletionEvaluation,
    evaluate_output_completion,
)
from aec_bench.contracts.proposal_execution.graph import FinalSynthesisSpec, SemanticSubtaskSpec


class ProposalNodeContractError(RuntimeError):
    """Host-side contract evidence failure that cannot be scored as candidate invalidity."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class CanonicalProposalHandoff:
    """Canonical bytes and identity for one graph-bound semantic output."""

    output_id: str
    artifact_sha256: str
    canonical_bytes: bytes


@dataclass(frozen=True)
class ProposalNodeContractCheck:
    """Reward-blind structural result suitable for proposal-session evidence persistence."""

    satisfied: bool
    details: dict[str, JsonValue]
    canonical_details_bytes: bytes
    handoffs: tuple[CanonicalProposalHandoff, ...] = ()

    @property
    def details_sha256(self) -> str:
        """Return the byte identity of the canonical contract-check details."""
        return hashlib.sha256(self.canonical_details_bytes).hexdigest()


@dataclass(frozen=True)
class _SemanticOutputsInspection:
    outputs: dict[str, JsonValue] | None = None
    present_output_ids: tuple[str, ...] = ()
    explicit_data_gap_output_ids: tuple[str, ...] = ()
    finding_codes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class _SemanticProvenanceInspection:
    provenance: tuple[str, ...] | None = None
    present_provenance_ids: tuple[str, ...] = ()
    finding_codes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class _SemanticPayloadInspection:
    present_top_level_fields: tuple[str, ...] = ()
    outputs: dict[str, JsonValue] | None = None
    present_output_ids: tuple[str, ...] = ()
    provenance: tuple[str, ...] | None = None
    present_provenance_ids: tuple[str, ...] = ()
    explicit_data_gap_output_ids: tuple[str, ...] = ()
    finding_codes: frozenset[str] = frozenset()


class _DuplicateJsonKey(ValueError):
    pass


class _NonFiniteJsonNumber(ValueError):
    pass


_FINAL_JSON_BLOCK = re.compile(
    r"^[ \t]*```json[ \t]*\r?\n(?P<body>.*?)^[ \t]*```[ \t]*(?:\r?\n|$)",
    flags=re.DOTALL | re.IGNORECASE | re.MULTILINE,
)


def semantic_node_output_contract(*, output_path: str) -> OutputCompletionContract:
    """Build the fixed-H0 public completion contract for semantic-node output."""
    return OutputCompletionContract(
        schema_version="aecbench.output-completion-contract.v1",
        output_path=output_path,
        format="markdown_final_fenced_json",
        required_top_level_keys=("outputs", "provenance"),
        require_single_final_json_block=True,
    )


def check_semantic_node_output(
    *,
    node: SemanticSubtaskSpec,
    output_contract: OutputCompletionContract,
    raw_output_bytes: bytes,
    completion_commit: OutputCommitAttestation | None,
    upstream_artifact_ids: Mapping[str, str],
) -> ProposalNodeContractCheck:
    """Check one semantic result against only its public graph-bound contract."""
    upstream = _validated_upstream_artifacts(
        node=node,
        upstream_artifact_ids=upstream_artifact_ids,
    )
    output_contract_sha256 = _validated_semantic_contract_sha256(
        output_contract,
    )
    raw_output_bytes = _require_semantic_output_bytes(raw_output_bytes)
    output_sha256 = hashlib.sha256(raw_output_bytes).hexdigest()
    output_size_bytes = len(raw_output_bytes)
    output_text, evaluation = _evaluate_semantic_output(
        output_contract=output_contract,
        raw_output_bytes=raw_output_bytes,
    )
    expected_output_ids = list(node.evidence_contract.required_output_ids)
    expected_provenance_ids = sorted(
        {
            *node.source_scope.source_ids,
            *upstream.values(),
        },
    )
    finding_codes: set[str] = set()
    completion_finding = _semantic_completion_finding(evaluation)
    if completion_finding is not None:
        finding_codes.add(completion_finding)
    commit_finding = _semantic_commit_finding(
        completion_commit=completion_commit,
        output_contract=output_contract,
        output_contract_sha256=output_contract_sha256,
        output_sha256=output_sha256,
        output_size_bytes=output_size_bytes,
        evaluation=evaluation,
    )
    if commit_finding is not None:
        finding_codes.add(commit_finding)
    inspection = _inspect_semantic_payload(
        node=node,
        output_text=output_text,
        evaluation=evaluation,
        expected_output_ids=expected_output_ids,
        expected_provenance_ids=expected_provenance_ids,
    )
    finding_codes.update(inspection.finding_codes)
    handoffs = _semantic_handoffs(
        node=node,
        inspection=inspection,
        expected_output_ids=expected_output_ids,
        expected_provenance_ids=expected_provenance_ids,
        finding_codes=finding_codes,
    )
    details = _semantic_contract_details(
        node=node,
        output_contract=output_contract,
        output_contract_sha256=output_contract_sha256,
        output_sha256=output_sha256,
        output_size_bytes=output_size_bytes,
        evaluation=evaluation,
        completion_commit=completion_commit,
        expected_output_ids=expected_output_ids,
        expected_provenance_ids=expected_provenance_ids,
        inspection=inspection,
        finding_codes=finding_codes,
        handoffs=handoffs,
    )
    return _contract_check(
        satisfied=not finding_codes,
        details=details,
        handoffs=handoffs,
    )


def _validated_semantic_contract_sha256(
    output_contract: OutputCompletionContract,
) -> str:
    expected_output_contract = semantic_node_output_contract(
        output_path=output_contract.output_path,
    )
    if output_contract != expected_output_contract:
        raise ProposalNodeContractError(
            "contract_binding_invalid",
            "semantic node requires the host-built outputs/provenance completion contract",
        )
    return canonical_content_sha256(output_contract.model_dump(mode="json"))


def _require_semantic_output_bytes(raw_output_bytes: bytes) -> bytes:
    if not isinstance(raw_output_bytes, bytes):
        raise ProposalNodeContractError(
            "host_evidence_invalid",
            "semantic-node output evidence must be exact bytes",
        )
    return raw_output_bytes


def _evaluate_semantic_output(
    *,
    output_contract: OutputCompletionContract,
    raw_output_bytes: bytes,
) -> tuple[str | None, OutputCompletionEvaluation | None]:
    try:
        output_text = raw_output_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None, None
    return output_text, evaluate_output_completion(output_contract, output_text)


def _semantic_completion_finding(
    evaluation: OutputCompletionEvaluation | None,
) -> str | None:
    if evaluation is None:
        return "output_not_utf8"
    if not evaluation.complete:
        return f"completion_{evaluation.reason.value}"
    return None


def _semantic_commit_finding(
    *,
    completion_commit: OutputCommitAttestation | None,
    output_contract: OutputCompletionContract,
    output_contract_sha256: str,
    output_sha256: str,
    output_size_bytes: int,
    evaluation: OutputCompletionEvaluation | None,
) -> str | None:
    if completion_commit is None:
        return "output_commit_missing"
    if not _semantic_commit_matches(
        completion_commit=completion_commit,
        output_contract=output_contract,
        output_contract_sha256=output_contract_sha256,
        output_sha256=output_sha256,
        output_size_bytes=output_size_bytes,
        evaluation=evaluation,
    ):
        raise ProposalNodeContractError(
            "output_integrity_failure",
            "semantic-node output bytes, completion contract, and commit attestation differ",
        )
    return None


def _semantic_commit_matches(
    *,
    completion_commit: OutputCommitAttestation,
    output_contract: OutputCompletionContract,
    output_contract_sha256: str,
    output_sha256: str,
    output_size_bytes: int,
    evaluation: OutputCompletionEvaluation | None,
) -> bool:
    return (
        completion_commit.output_path == output_contract.output_path
        and completion_commit.output_sha256 == output_sha256
        and completion_commit.output_size_bytes == output_size_bytes
        and completion_commit.completion_contract_sha256 == output_contract_sha256
        and evaluation is not None
        and completion_commit.completion_evaluation == evaluation
    )


def _inspect_semantic_payload(
    *,
    node: SemanticSubtaskSpec,
    output_text: str | None,
    evaluation: OutputCompletionEvaluation | None,
    expected_output_ids: list[str],
    expected_provenance_ids: list[str],
) -> _SemanticPayloadInspection:
    if evaluation is None or not evaluation.complete:
        return _SemanticPayloadInspection()
    if output_text is None:
        raise ProposalNodeContractError(
            "host_evidence_invalid",
            "completed semantic-node evaluation requires decoded output text",
        )
    parsed, parse_finding = _parse_candidate_json(_final_json_body(output_text))
    if parse_finding is not None:
        return _SemanticPayloadInspection(
            finding_codes=frozenset((parse_finding,)),
        )
    if not isinstance(parsed, dict):
        raise ProposalNodeContractError(
            "host_evidence_invalid",
            "completed semantic-node output did not contain a JSON object",
        )
    return _inspect_semantic_object(
        node=node,
        payload=parsed,
        expected_output_ids=expected_output_ids,
        expected_provenance_ids=expected_provenance_ids,
    )


def _inspect_semantic_object(
    *,
    node: SemanticSubtaskSpec,
    payload: dict[str, JsonValue],
    expected_output_ids: list[str],
    expected_provenance_ids: list[str],
) -> _SemanticPayloadInspection:
    finding_codes: set[str] = set()
    present_top_level_fields = tuple(sorted(payload))
    if set(payload) != {"outputs", "provenance"}:
        finding_codes.add("top_level_fields_mismatch")
    outputs = _inspect_semantic_outputs(
        value=payload.get("outputs"),
        expected_output_ids=expected_output_ids,
        allow_explicit_data_gap=node.evidence_contract.allow_explicit_data_gap,
    )
    provenance = _inspect_semantic_provenance(
        value=payload.get("provenance"),
        expected_provenance_ids=expected_provenance_ids,
    )
    finding_codes.update(outputs.finding_codes)
    finding_codes.update(provenance.finding_codes)
    return _SemanticPayloadInspection(
        present_top_level_fields=present_top_level_fields,
        outputs=outputs.outputs,
        present_output_ids=outputs.present_output_ids,
        provenance=provenance.provenance,
        present_provenance_ids=provenance.present_provenance_ids,
        explicit_data_gap_output_ids=outputs.explicit_data_gap_output_ids,
        finding_codes=frozenset(finding_codes),
    )


def _inspect_semantic_outputs(
    *,
    value: JsonValue | None,
    expected_output_ids: list[str],
    allow_explicit_data_gap: bool,
) -> _SemanticOutputsInspection:
    if not isinstance(value, dict):
        return _SemanticOutputsInspection(
            finding_codes=frozenset(("outputs_object_required",)),
        )
    outputs = value
    present_output_ids = tuple(sorted(outputs))
    finding_codes: set[str] = set()
    if present_output_ids != tuple(expected_output_ids):
        finding_codes.add("output_ids_mismatch")
    explicit_data_gap_output_ids: list[str] = []
    for output_id in sorted(set(outputs) & set(expected_output_ids)):
        gap_state = _explicit_data_gap_state(outputs[output_id])
        if gap_state == "invalid":
            finding_codes.add("explicit_data_gap_invalid")
        elif gap_state == "valid":
            explicit_data_gap_output_ids.append(output_id)
            if not allow_explicit_data_gap:
                finding_codes.add("explicit_data_gap_forbidden")
    return _SemanticOutputsInspection(
        outputs=outputs,
        present_output_ids=present_output_ids,
        explicit_data_gap_output_ids=tuple(explicit_data_gap_output_ids),
        finding_codes=frozenset(finding_codes),
    )


def _inspect_semantic_provenance(
    *,
    value: JsonValue | None,
    expected_provenance_ids: list[str],
) -> _SemanticProvenanceInspection:
    if not isinstance(value, list):
        return _SemanticProvenanceInspection(
            finding_codes=frozenset(("provenance_array_required",)),
        )
    if any(not isinstance(item, str) or not item.strip() for item in value):
        return _SemanticProvenanceInspection(
            finding_codes=frozenset(("provenance_entry_invalid",)),
        )
    provenance = tuple(cast(str, item) for item in value)
    finding_codes: set[str] = set()
    if len(provenance) != len(set(provenance)):
        finding_codes.add("provenance_duplicate")
    present_provenance_ids = tuple(sorted(set(provenance)))
    if present_provenance_ids != tuple(expected_provenance_ids):
        finding_codes.add("provenance_ids_mismatch")
    return _SemanticProvenanceInspection(
        provenance=provenance,
        present_provenance_ids=present_provenance_ids,
        finding_codes=frozenset(finding_codes),
    )


def _semantic_handoffs(
    *,
    node: SemanticSubtaskSpec,
    inspection: _SemanticPayloadInspection,
    expected_output_ids: list[str],
    expected_provenance_ids: list[str],
    finding_codes: set[str],
) -> tuple[CanonicalProposalHandoff, ...]:
    if finding_codes or inspection.outputs is None or inspection.provenance is None:
        return ()
    output_kinds = {output.output_id: output.kind.value for output in node.output_ports}
    return tuple(
        _canonical_handoff(
            node=node,
            output_id=output_id,
            output_kind=output_kinds[output_id],
            value=inspection.outputs[output_id],
            provenance_ids=expected_provenance_ids,
        )
        for output_id in expected_output_ids
    )


def _semantic_contract_details(
    *,
    node: SemanticSubtaskSpec,
    output_contract: OutputCompletionContract,
    output_contract_sha256: str,
    output_sha256: str,
    output_size_bytes: int,
    evaluation: OutputCompletionEvaluation | None,
    completion_commit: OutputCommitAttestation | None,
    expected_output_ids: list[str],
    expected_provenance_ids: list[str],
    inspection: _SemanticPayloadInspection,
    finding_codes: set[str],
    handoffs: tuple[CanonicalProposalHandoff, ...],
) -> dict[str, JsonValue]:
    return {
        "schema_version": "aecbench.proposal-semantic-contract-check.v1",
        "check_kind": "semantic_node",
        "node_id": node.node_id,
        "node_contract_sha256": node.evidence_contract.content_sha256,
        "output_completion_contract_sha256": output_contract_sha256,
        "satisfied": not finding_codes,
        "finding_codes": _json_strings(sorted(finding_codes)),
        "output_path": output_contract.output_path,
        "output_sha256": output_sha256,
        "output_size_bytes": output_size_bytes,
        "completion_reason": (evaluation.reason.value if evaluation is not None else "output_not_utf8"),
        "present_completion_top_level_keys": _json_strings(
            evaluation.present_top_level_keys if evaluation is not None else (),
        ),
        "missing_completion_top_level_keys": _json_strings(
            evaluation.missing_top_level_keys if evaluation is not None else (),
        ),
        "final_json_block_count": (evaluation.final_json_block_count if evaluation is not None else 0),
        "output_commit_attestation_sha256": (
            completion_commit.content_sha256 if completion_commit is not None else None
        ),
        "required_top_level_fields": _json_strings(("outputs", "provenance")),
        "present_top_level_fields": _json_strings(
            inspection.present_top_level_fields,
        ),
        "required_output_ids": _json_strings(expected_output_ids),
        "present_output_ids": _json_strings(inspection.present_output_ids),
        "required_provenance_ids": _json_strings(expected_provenance_ids),
        "present_provenance_ids": _json_strings(
            inspection.present_provenance_ids,
        ),
        "explicit_data_gap_allowed": node.evidence_contract.allow_explicit_data_gap,
        "explicit_data_gap_output_ids": _json_strings(
            inspection.explicit_data_gap_output_ids,
        ),
        "handoff_artifact_sha256s": _json_string_mapping(
            {handoff.output_id: handoff.artifact_sha256 for handoff in handoffs},
        ),
        "hidden_verifier_used": False,
    }


def check_finalizer_output(
    *,
    finalizer: FinalSynthesisSpec,
    output_contract: OutputCompletionContract,
    raw_output_bytes: bytes | None,
    completion_commit: OutputCommitAttestation | None,
) -> ProposalNodeContractCheck:
    """Check only public final-output completion and commit integrity."""
    output_contract_sha256 = canonical_content_sha256(
        output_contract.model_dump(mode="json"),
    )
    if finalizer.output_completion_contract_sha256 != output_contract_sha256:
        raise ProposalNodeContractError(
            "contract_binding_invalid",
            "finalizer does not bind the supplied public output-completion contract",
        )
    output_text, output_sha256, output_size_bytes = _decoded_final_output(
        raw_output_bytes,
    )
    evaluation = evaluate_output_completion(output_contract, output_text)
    finding_codes: set[str] = set()
    if not evaluation.complete:
        finding_codes.add(f"completion_{evaluation.reason.value}")
    if completion_commit is None:
        finding_codes.add("output_commit_missing")
    else:
        if (
            raw_output_bytes is None
            or output_sha256 is None
            or completion_commit.output_path != output_contract.output_path
            or completion_commit.output_sha256 != output_sha256
            or completion_commit.output_size_bytes != output_size_bytes
            or completion_commit.completion_contract_sha256 != output_contract_sha256
            or completion_commit.completion_evaluation != evaluation
        ):
            raise ProposalNodeContractError(
                "output_integrity_failure",
                "finalizer output bytes, completion contract, and commit attestation differ",
            )
    details: dict[str, JsonValue] = {
        "schema_version": "aecbench.proposal-finalizer-contract-check.v1",
        "check_kind": "finalizer",
        "node_id": finalizer.node_id,
        "node_contract_sha256": output_contract_sha256,
        "satisfied": not finding_codes,
        "finding_codes": _json_strings(sorted(finding_codes)),
        "output_path": output_contract.output_path,
        "output_sha256": output_sha256,
        "output_size_bytes": output_size_bytes,
        "completion_reason": evaluation.reason.value,
        "present_top_level_keys": _json_strings(
            evaluation.present_top_level_keys,
        ),
        "missing_top_level_keys": _json_strings(
            evaluation.missing_top_level_keys,
        ),
        "final_json_block_count": evaluation.final_json_block_count,
        "output_commit_attestation_sha256": (
            completion_commit.content_sha256 if completion_commit is not None else None
        ),
        "hidden_verifier_used": False,
    }
    return _contract_check(
        satisfied=not finding_codes,
        details=details,
        handoffs=(),
    )


def _validated_upstream_artifacts(
    *,
    node: SemanticSubtaskSpec,
    upstream_artifact_ids: Mapping[str, str],
) -> dict[str, str]:
    expected_input_ids = {input_port.input_id for input_port in node.input_ports}
    if set(upstream_artifact_ids) != expected_input_ids:
        raise ProposalNodeContractError(
            "contract_binding_invalid",
            "upstream artifact bindings must exactly match semantic-node input ports",
        )
    validated: dict[str, str] = {}
    for input_id, artifact_id in upstream_artifact_ids.items():
        if not isinstance(artifact_id, str):
            raise ProposalNodeContractError(
                "contract_binding_invalid",
                "upstream artifact identities must be SHA-256 strings",
            )
        try:
            validate_sha256(artifact_id)
        except ValueError as error:
            raise ProposalNodeContractError(
                "contract_binding_invalid",
                f"upstream artifact identity for {input_id!r} is invalid: {error}",
            ) from error
        validated[input_id] = artifact_id
    return validated


def _parse_candidate_json(
    candidate_json: str,
) -> tuple[JsonValue | None, str | None]:
    try:
        parsed = json.loads(
            candidate_json,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
        )
        _canonical_json_bytes(parsed)
    except _DuplicateJsonKey:
        return None, "candidate_json_duplicate_key"
    except _NonFiniteJsonNumber:
        return None, "candidate_json_non_finite"
    except json.JSONDecodeError:
        return None, "candidate_json_malformed"
    except ValueError:
        return None, "candidate_json_non_finite"
    except (UnicodeEncodeError, TypeError):
        return None, "candidate_json_not_canonicalizable"
    return cast(JsonValue, parsed), None


def _final_json_body(output_text: str) -> str:
    matches = tuple(_FINAL_JSON_BLOCK.finditer(output_text))
    if len(matches) != 1:
        raise ProposalNodeContractError(
            "host_evidence_invalid",
            "completed semantic-node output did not contain exactly one final JSON block",
        )
    return matches[0].group("body")


def _reject_duplicate_keys(
    pairs: list[tuple[str, JsonValue]],
) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _reject_nonfinite_constant(value: str) -> None:
    raise _NonFiniteJsonNumber(f"non-finite JSON number {value!r}")


def _explicit_data_gap_state(value: JsonValue) -> str:
    if not isinstance(value, dict) or "explicit_data_gap" not in value:
        return "absent"
    if set(value) != {"explicit_data_gap"}:
        return "invalid"
    gap = value["explicit_data_gap"]
    if (
        not isinstance(gap, dict)
        or set(gap) != {"reason"}
        or not isinstance(gap["reason"], str)
        or not gap["reason"].strip()
    ):
        return "invalid"
    return "valid"


def _canonical_handoff(
    *,
    node: SemanticSubtaskSpec,
    output_id: str,
    output_kind: str,
    value: JsonValue,
    provenance_ids: list[str],
) -> CanonicalProposalHandoff:
    payload: dict[str, JsonValue] = {
        "schema_version": "aecbench.proposal-node-handoff.v1",
        "producer_node_id": node.node_id,
        "node_contract_sha256": node.evidence_contract.content_sha256,
        "output_id": output_id,
        "output_kind": output_kind,
        "value": value,
        "provenance": _json_strings(provenance_ids),
    }
    encoded = _canonical_json_bytes(payload)
    return CanonicalProposalHandoff(
        output_id=output_id,
        artifact_sha256=hashlib.sha256(encoded).hexdigest(),
        canonical_bytes=encoded,
    )


def _decoded_final_output(
    raw_output_bytes: bytes | None,
) -> tuple[str | None, str | None, int]:
    if raw_output_bytes is None:
        return None, None, 0
    return _decoded_output(raw_output_bytes, output_kind="finalizer")


def _decoded_output(
    raw_output_bytes: bytes,
    *,
    output_kind: str,
) -> tuple[str, str, int]:
    if not isinstance(raw_output_bytes, bytes):
        raise ProposalNodeContractError(
            "malformed_candidate_output",
            f"{output_kind} output evidence must be exact bytes",
        )
    try:
        output_text = raw_output_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProposalNodeContractError(
            "malformed_candidate_output",
            f"{output_kind} output is not UTF-8: {error}",
        ) from error
    return (
        output_text,
        hashlib.sha256(raw_output_bytes).hexdigest(),
        len(raw_output_bytes),
    )


def _contract_check(
    *,
    satisfied: bool,
    details: dict[str, JsonValue],
    handoffs: tuple[CanonicalProposalHandoff, ...],
) -> ProposalNodeContractCheck:
    encoded = _canonical_json_bytes(details)
    return ProposalNodeContractCheck(
        satisfied=satisfied,
        details=details,
        canonical_details_bytes=encoded,
        handoffs=handoffs,
    )


def _json_strings(values: Iterable[str]) -> list[JsonValue]:
    return [value for value in values]


def _json_string_mapping(
    values: Mapping[str, str],
) -> dict[str, JsonValue]:
    return {key: value for key, value in values.items()}


def _canonical_json_bytes(payload: Any) -> bytes:
    _reject_nonfinite_numbers(payload)
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


def _reject_nonfinite_numbers(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite numbers are not JSON")
    if isinstance(value, dict):
        for nested in value.values():
            _reject_nonfinite_numbers(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_nonfinite_numbers(nested)
