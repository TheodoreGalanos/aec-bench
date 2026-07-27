# ABOUTME: Defines reward-blind task output-completion contracts and structural evaluation.
# ABOUTME: Detects a final fenced JSON object without consulting verifier or expected values.

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, Final, Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel, validate_sha256
from aec_bench.contracts.validators import NonEmptyStr, StrictModel

OUTPUT_COMPLETION_CONTRACT_SCHEMA_VERSION: Final = "aecbench.output-completion-contract.v1"
OUTPUT_COMMIT_ATTESTATION_SCHEMA_VERSION: Final = "aecbench.output-commit-attestation.v1"

_FINAL_JSON_BLOCK = re.compile(
    r"^[ \t]*```json[ \t]*\r?\n(?P<body>.*?)^[ \t]*```[ \t]*(?:\r?\n|$)",
    flags=re.DOTALL | re.IGNORECASE | re.MULTILINE,
)
_LEAKAGE_TOKENS = frozenset({"reward", "rewards", "gold", "golden", "expected"})


class OutputCompletionReason(StrEnum):
    """Structural reason an output does or does not satisfy its completion contract."""

    COMPLETE = "complete"
    OUTPUT_MISSING = "output_missing"
    OUTPUT_EMPTY = "output_empty"
    FINAL_JSON_BLOCK_MISSING = "final_json_block_missing"
    MULTIPLE_FINAL_JSON_BLOCKS = "multiple_final_json_blocks"
    FINAL_JSON_BLOCK_NOT_FINAL = "final_json_block_not_final"
    FINAL_JSON_MALFORMED = "final_json_malformed"
    FINAL_JSON_NOT_OBJECT = "final_json_not_object"
    REQUIRED_TOP_LEVEL_KEYS_MISSING = "required_top_level_keys_missing"


class _FrozenStrictModel(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OutputCompletionContract(_FrozenStrictModel):
    """Task-owned structural completion contract with no answer or verifier content."""

    schema_version: Literal["aecbench.output-completion-contract.v1"]
    output_path: NonEmptyStr
    format: Literal["markdown_final_fenced_json"]
    required_top_level_keys: tuple[NonEmptyStr, ...] = Field(min_length=1)
    require_single_final_json_block: Literal[True]

    @model_validator(mode="before")
    @classmethod
    def reject_recursive_leakage(cls, value: Any) -> Any:
        """Reject verifier- or answer-bearing keys anywhere in an input payload."""
        leaking_key = _find_leakage_key(value)
        if leaking_key is not None:
            raise ValueError(f"reward-blind contract rejects leakage key {leaking_key!r}")
        return value

    @field_validator("required_top_level_keys")
    @classmethod
    def validate_required_top_level_keys(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("required_top_level_keys must be unique")
        for key in value:
            if _is_leakage_key(key):
                raise ValueError(f"reward-blind contract rejects leakage key {key!r}")
        return value


class OutputCompletionEvaluation(_FrozenStrictModel):
    """Purely structural result of evaluating one output document."""

    complete: bool
    reason: OutputCompletionReason
    present_top_level_keys: tuple[str, ...] = ()
    missing_top_level_keys: tuple[str, ...] = ()
    final_json_block_count: int = Field(default=0, ge=0)


class OutputCommitAttestation(ContentAddressedModel):
    """Content-addressed evidence for one explicit, structurally valid output commit."""

    schema_version: Literal["aecbench.output-commit-attestation.v1"]
    mechanism: Literal["agent_explicit_output_commit"]
    output_path: NonEmptyStr
    output_sha256: str
    output_size_bytes: int = Field(ge=1)
    completion_contract_sha256: str
    completion_evaluation: OutputCompletionEvaluation
    initial_output_sha256: str | None
    commit_turn: int = Field(ge=1)

    @field_validator("output_sha256", "completion_contract_sha256")
    @classmethod
    def validate_required_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("initial_output_sha256")
    @classmethod
    def validate_optional_sha256(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @model_validator(mode="after")
    def validate_complete_evaluation(self) -> Self:
        if (
            not self.completion_evaluation.complete
            or self.completion_evaluation.reason is not OutputCompletionReason.COMPLETE
        ):
            raise ValueError("output commit attestation requires a complete structural evaluation")
        if self.initial_output_sha256 == self.output_sha256:
            raise ValueError("committed output SHA-256 must differ from initial output")
        return self


def evaluate_output_completion(
    contract: OutputCompletionContract,
    output_text: str | None,
) -> OutputCompletionEvaluation:
    """Evaluate output shape only; values and task correctness remain verifier-owned."""
    if output_text is None:
        return OutputCompletionEvaluation(
            complete=False,
            reason=OutputCompletionReason.OUTPUT_MISSING,
        )
    if not output_text.strip():
        return OutputCompletionEvaluation(
            complete=False,
            reason=OutputCompletionReason.OUTPUT_EMPTY,
        )

    matches = tuple(_FINAL_JSON_BLOCK.finditer(output_text))
    if not matches:
        return OutputCompletionEvaluation(
            complete=False,
            reason=OutputCompletionReason.FINAL_JSON_BLOCK_MISSING,
        )
    if len(matches) != 1:
        return OutputCompletionEvaluation(
            complete=False,
            reason=OutputCompletionReason.MULTIPLE_FINAL_JSON_BLOCKS,
            final_json_block_count=len(matches),
        )

    final_block = matches[0]
    if output_text[final_block.end() :].strip():
        return OutputCompletionEvaluation(
            complete=False,
            reason=OutputCompletionReason.FINAL_JSON_BLOCK_NOT_FINAL,
            final_json_block_count=1,
        )

    try:
        payload = json.loads(final_block.group("body"))
    except json.JSONDecodeError:
        return OutputCompletionEvaluation(
            complete=False,
            reason=OutputCompletionReason.FINAL_JSON_MALFORMED,
            final_json_block_count=1,
        )
    if not isinstance(payload, dict):
        return OutputCompletionEvaluation(
            complete=False,
            reason=OutputCompletionReason.FINAL_JSON_NOT_OBJECT,
            final_json_block_count=1,
        )

    present_keys = tuple(payload)
    missing_keys = tuple(key for key in contract.required_top_level_keys if key not in payload)
    if missing_keys:
        return OutputCompletionEvaluation(
            complete=False,
            reason=OutputCompletionReason.REQUIRED_TOP_LEVEL_KEYS_MISSING,
            present_top_level_keys=present_keys,
            missing_top_level_keys=missing_keys,
            final_json_block_count=1,
        )
    return OutputCompletionEvaluation(
        complete=True,
        reason=OutputCompletionReason.COMPLETE,
        present_top_level_keys=present_keys,
        final_json_block_count=1,
    )


def _find_leakage_key(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            key_text = str(key)
            if _is_leakage_key(key_text):
                return key_text
            nested_key = _find_leakage_key(nested_value)
            if nested_key is not None:
                return nested_key
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for item in value:
            nested_key = _find_leakage_key(item)
            if nested_key is not None:
                return nested_key
    return None


def _is_leakage_key(key: str) -> bool:
    snake_case = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).lower()
    tokens = tuple(token for token in re.split(r"[^a-z0-9]+", snake_case) if token)
    collapsed = "".join(tokens)
    return any(token in _LEAKAGE_TOKENS or token.startswith("verif") for token in tokens) or "groundtruth" in collapsed
