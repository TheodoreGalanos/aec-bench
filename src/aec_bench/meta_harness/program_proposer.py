# ABOUTME: Invokes one frozen program-proposer session and parses only inert decomposition JSON.
# ABOUTME: Preserves raw responses and usage while withholding compiler, verifier, and outcome feedback.

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol, Self, runtime_checkable

from pydantic import Field, NonNegativeInt, field_validator, model_validator

from aec_bench.adapters.direct import (
    DirectClient,
    DirectCompletionRequest,
    DirectCompletionResponse,
)
from aec_bench.contracts.authority import (
    AuthorityPrincipal,
    AuthorityPrincipalKind,
)
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.pricing import estimate_cost_usd, match_pricing
from aec_bench.contracts.program_proposal import (
    CandidateGenerationManifest,
    DecompositionProblemView,
    ProgramCandidateKind,
    ProgramCandidateRef,
)
from aec_bench.contracts.program_proposer import FrozenProgramProposerPolicy
from aec_bench.contracts.proposal_execution import ProposedDecompositionGraph
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.meta_harness.proposal_freeze import ProposalArtifact


class ProgramProposalTurnStatus(StrEnum):
    """Closed outcome of one turn inside a frozen proposer invocation."""

    ACCEPTED = "accepted"
    GRAMMAR_REJECTED = "grammar_rejected"
    PROVIDER_FAILED = "provider_failed"
    USAGE_EVIDENCE_MISSING = "usage_evidence_missing"
    BUDGET_EXHAUSTED = "budget_exhausted"


class ProgramProposalInvocationStatus(StrEnum):
    """Terminal outcome of one complete frozen proposer invocation."""

    COMPLETED = "completed"
    GRAMMAR_EXHAUSTED = "grammar_exhausted"
    PROVIDER_FAILED = "provider_failed"
    USAGE_EVIDENCE_INCOMPLETE = "usage_evidence_incomplete"
    BUDGET_EXHAUSTED = "budget_exhausted"


@runtime_checkable
class BoundedProgramProposalClient(Protocol):
    """Optional direct-client extension for enforceable per-request limits."""

    def complete_bounded(
        self,
        request: DirectCompletionRequest,
        *,
        timeout_seconds: float,
        max_output_tokens: int,
    ) -> DirectCompletionResponse: ...


class ProgramProposalTurnReceipt(ContentAddressedModel):
    """Exact raw response and metered usage for one grammar-bounded turn."""

    schema_version: Literal["aecbench.program-proposal-turn-receipt.v1"] = "aecbench.program-proposal-turn-receipt.v1"
    turn_index: int = Field(ge=1, le=4)
    request_sha256: str
    raw_response: bytes
    raw_response_sha256: str
    status: ProgramProposalTurnStatus
    model_calls: NonNegativeInt | None
    input_tokens: NonNegativeInt | None
    output_tokens: NonNegativeInt | None
    cache_read_tokens: NonNegativeInt | None
    cache_write_tokens: NonNegativeInt | None
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    wall_time_seconds: float = Field(ge=0)
    provider_error: NonEmptyStr | None = None

    @field_validator("request_sha256", "raw_response_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if hashlib.sha256(self.raw_response).hexdigest() != self.raw_response_sha256:
            raise ValueError("raw proposer response SHA-256 does not match its exact bytes")
        usage_complete = (
            self.model_calls is not None
            and self.input_tokens is not None
            and self.output_tokens is not None
            and self.estimated_cost_usd is not None
        )
        if self.status is ProgramProposalTurnStatus.USAGE_EVIDENCE_MISSING:
            if usage_complete:
                raise ValueError("missing-usage turn cannot carry complete usage")
        elif self.status is not ProgramProposalTurnStatus.PROVIDER_FAILED and not usage_complete:
            raise ValueError("proposer turn requires complete token and cost evidence")
        if self.status is ProgramProposalTurnStatus.PROVIDER_FAILED:
            if self.provider_error is None:
                raise ValueError("provider-failed proposer turn requires an error")
        elif self.provider_error is not None:
            raise ValueError("only provider-failed proposer turns may carry provider errors")
        return self


class ProgramProposalArtifact(ContentAddressedModel):
    """Canonical proposal bytes and the exact candidate reference they realize."""

    schema_version: Literal["aecbench.program-proposal-artifact.v1"] = "aecbench.program-proposal-artifact.v1"
    reference: ProgramCandidateRef
    graph: ProposedDecompositionGraph
    content: bytes

    @model_validator(mode="after")
    def validate_artifact(self) -> Self:
        if self.reference.kind is not ProgramCandidateKind.PROPOSAL:
            raise ValueError("generated program artifact must have proposal candidate kind")
        if hashlib.sha256(self.content).hexdigest() != self.reference.candidate_artifact_sha256:
            raise ValueError("generated program artifact bytes do not match their candidate reference")
        try:
            parsed = ProposedDecompositionGraph.model_validate_json(self.content)
        except ValueError as error:
            raise ValueError("generated program artifact bytes do not contain an inert proposal graph") from error
        if parsed != self.graph:
            raise ValueError("generated program artifact bytes differ from their parsed graph")
        if (
            self.reference.candidate_id != self.graph.candidate_id
            or self.reference.generation_coordinate_id != self.graph.generation_coordinate_id
        ):
            raise ValueError("generated program artifact reference does not bind its graph coordinate")
        return self


class ProgramProposalInvocation(ContentAddressedModel):
    """Complete result of one policy-pinned proposer session over one public view."""

    schema_version: Literal["aecbench.program-proposal-invocation.v1"] = "aecbench.program-proposal-invocation.v1"
    invocation_id: NonEmptyStr
    status: ProgramProposalInvocationStatus
    policy_sha256: str
    problem_view_sha256: str
    candidate_manifest_sha256: str
    model_id: NonEmptyStr
    policy_checkpoint_sha256: str
    grammar_sha256: str
    turns: tuple[ProgramProposalTurnReceipt, ...] = Field(min_length=1, max_length=4)
    artifacts: tuple[ProgramProposalArtifact, ...] = ()
    total_model_calls: NonNegativeInt
    total_input_tokens: NonNegativeInt
    total_output_tokens: NonNegativeInt
    total_cache_read_tokens: NonNegativeInt
    total_cache_write_tokens: NonNegativeInt
    total_observed_tokens: NonNegativeInt
    total_estimated_cost_usd: float = Field(ge=0)
    total_wall_time_seconds: float = Field(ge=0)
    usage_evidence_complete: bool

    @field_validator(
        "policy_sha256",
        "problem_view_sha256",
        "candidate_manifest_sha256",
        "policy_checkpoint_sha256",
        "grammar_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("artifacts")
    @classmethod
    def canonicalize_artifacts(
        cls,
        value: tuple[ProgramProposalArtifact, ...],
    ) -> tuple[ProgramProposalArtifact, ...]:
        identities = tuple(artifact.reference.candidate_id for artifact in value)
        if len(identities) != len(set(identities)):
            raise ValueError("generated program artifacts must have unique candidate identities")
        return tuple(sorted(value, key=lambda artifact: artifact.reference.candidate_id))

    @model_validator(mode="after")
    def validate_invocation(self) -> Self:
        if tuple(turn.turn_index for turn in self.turns) != tuple(range(1, len(self.turns) + 1)):
            raise ValueError("proposer turn indices must be contiguous")
        known_model_calls = sum(turn.model_calls or 0 for turn in self.turns)
        known_input = sum(turn.input_tokens or 0 for turn in self.turns)
        known_output = sum(turn.output_tokens or 0 for turn in self.turns)
        known_cache_read = sum(turn.cache_read_tokens or 0 for turn in self.turns)
        known_cache_write = sum(turn.cache_write_tokens or 0 for turn in self.turns)
        known_cost = sum(turn.estimated_cost_usd or 0.0 for turn in self.turns)
        known_provider_wall = sum(turn.wall_time_seconds for turn in self.turns)
        expected_usage_complete = all(
            turn.model_calls is not None
            and turn.input_tokens is not None
            and turn.output_tokens is not None
            and turn.estimated_cost_usd is not None
            for turn in self.turns
        )
        if (
            self.total_model_calls != known_model_calls
            or self.total_input_tokens != known_input
            or self.total_output_tokens != known_output
            or self.total_cache_read_tokens != known_cache_read
            or self.total_cache_write_tokens != known_cache_write
            or self.total_observed_tokens != known_input + known_output
            or abs(self.total_estimated_cost_usd - known_cost) > 1e-12
            or self.total_wall_time_seconds + 1e-9 < known_provider_wall
            or self.usage_evidence_complete is not expected_usage_complete
        ):
            raise ValueError("proposer invocation totals do not match its exact turn receipts")

        terminal = self.turns[-1].status
        expected_terminal = {
            ProgramProposalInvocationStatus.COMPLETED: ProgramProposalTurnStatus.ACCEPTED,
            ProgramProposalInvocationStatus.GRAMMAR_EXHAUSTED: ProgramProposalTurnStatus.GRAMMAR_REJECTED,
            ProgramProposalInvocationStatus.PROVIDER_FAILED: ProgramProposalTurnStatus.PROVIDER_FAILED,
            ProgramProposalInvocationStatus.USAGE_EVIDENCE_INCOMPLETE: (
                ProgramProposalTurnStatus.USAGE_EVIDENCE_MISSING
            ),
            ProgramProposalInvocationStatus.BUDGET_EXHAUSTED: ProgramProposalTurnStatus.BUDGET_EXHAUSTED,
        }[self.status]
        if terminal is not expected_terminal:
            raise ValueError("proposer invocation status does not match its terminal turn")
        if self.status is ProgramProposalInvocationStatus.COMPLETED:
            if len(self.artifacts) != 2:
                raise ValueError("completed proposer invocation requires exactly two artifacts")
            if not self.usage_evidence_complete:
                raise ValueError("completed proposer invocation requires complete usage evidence")
            if any(turn.status is not ProgramProposalTurnStatus.GRAMMAR_REJECTED for turn in self.turns[:-1]):
                raise ValueError("only grammar rejection may precede an accepted proposal turn")
        elif self.artifacts:
            raise ValueError("failed proposer invocation cannot release candidate artifacts")
        if self.status is ProgramProposalInvocationStatus.GRAMMAR_EXHAUSTED and len(self.turns) != 4:
            raise ValueError("grammar-exhausted proposer invocation requires all four turns")
        return self


class _ProgramProposalEnvelope(FrozenStrictModel):
    """Strict inert root object accepted from the proposer."""

    plans: tuple[ProposedDecompositionGraph, ...] = Field(min_length=2, max_length=2)


def program_proposal_grammar_bytes() -> bytes:
    """Return the exact inert JSON grammar exposed to every program proposer."""

    return json.dumps(
        _ProgramProposalEnvelope.model_json_schema(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def program_proposal_grammar_sha256() -> str:
    """Return the content identity of the only accepted proposal envelope grammar."""

    return hashlib.sha256(program_proposal_grammar_bytes()).hexdigest()


def preflight_program_proposal_invocation(
    *,
    policy: FrozenProgramProposerPolicy,
    problem_view: DecompositionProblemView,
    candidate_manifest: CandidateGenerationManifest,
) -> None:
    """Validate every deterministic proposer input before reserving a provider effect."""

    _normalized_invocation_inputs(
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=candidate_manifest,
    )


def generate_frozen_program_proposals(
    *,
    invocation_id: str,
    policy: FrozenProgramProposerPolicy,
    problem_view: DecompositionProblemView,
    candidate_manifest: CandidateGenerationManifest,
    client: DirectClient,
    clock: Callable[[], float] = time.monotonic,
) -> ProgramProposalInvocation:
    """Run one bounded proposer session without exposing compile or evaluation feedback."""

    started_at = clock()
    (
        selected_policy,
        selected_view,
        selected_manifest,
        system_prompt,
    ) = _normalized_invocation_inputs(
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=candidate_manifest,
    )

    initial_instruction = _initial_instruction(
        policy=selected_policy,
        problem_view=selected_view,
        candidate_manifest=selected_manifest,
    )
    correction_instruction = _correction_instruction(initial_instruction)
    turns: list[ProgramProposalTurnReceipt] = []

    for turn_index in range(1, selected_policy.max_turns + 1):
        turn_started_at = clock()
        elapsed_before_turn = max(0.0, turn_started_at - started_at)
        known_tokens = sum((turn.input_tokens or 0) + (turn.output_tokens or 0) for turn in turns)
        remaining_wall_time = max(0.0, selected_policy.max_wall_time_seconds - elapsed_before_turn)
        remaining_output_tokens = max(0, selected_policy.max_observed_tokens - known_tokens)
        request = DirectCompletionRequest(
            model=selected_policy.model_id,
            instruction=initial_instruction if turn_index == 1 else correction_instruction,
            system_prompt=system_prompt,
            configuration={
                "max_output_tokens": remaining_output_tokens,
                "temperature": 0.0,
                "timeout_seconds": remaining_wall_time,
            },
        )
        request_sha256 = canonical_content_sha256(
            {
                "model": request.model,
                "instruction": request.instruction,
                "system_prompt": request.system_prompt,
                "configuration": request.configuration,
            }
        )
        if remaining_wall_time <= 0.0 or remaining_output_tokens <= 0:
            turn = ProgramProposalTurnReceipt(
                turn_index=turn_index,
                request_sha256=request_sha256,
                raw_response=b"",
                raw_response_sha256=hashlib.sha256(b"").hexdigest(),
                status=ProgramProposalTurnStatus.BUDGET_EXHAUSTED,
                model_calls=0,
                input_tokens=0,
                output_tokens=0,
                cache_read_tokens=0,
                cache_write_tokens=0,
                estimated_cost_usd=0.0,
                wall_time_seconds=0.0,
            )
            turns.append(turn)
            return _invocation_result(
                invocation_id=invocation_id,
                status=ProgramProposalInvocationStatus.BUDGET_EXHAUSTED,
                policy=selected_policy,
                problem_view=selected_view,
                candidate_manifest=selected_manifest,
                turns=tuple(turns),
                artifacts=(),
                total_wall_time_seconds=max(0.0, clock() - started_at),
            )

        try:
            response = _complete_with_limits(
                client=client,
                request=request,
                timeout_seconds=remaining_wall_time,
                max_output_tokens=remaining_output_tokens,
            )
        except Exception as error:
            response = _transport_failure_response(error)
        turn_elapsed = max(0.0, clock() - turn_started_at)
        response = _normalize_provider_response(response)
        raw_response = response.output_text.encode("utf-8")

        receipt_status, estimated_cost = _preparse_turn_status(
            response=response,
            policy=selected_policy,
            prior_turns=tuple(turns),
            total_elapsed=max(0.0, clock() - started_at),
        )
        artifacts: tuple[ProgramProposalArtifact, ...] = ()
        if receipt_status is None:
            parsed_graphs = _parse_bound_graphs(
                raw_response=raw_response,
                policy=selected_policy,
                problem_view=selected_view,
                candidate_manifest=selected_manifest,
            )
            if parsed_graphs is None:
                receipt_status = ProgramProposalTurnStatus.GRAMMAR_REJECTED
            else:
                receipt_status = ProgramProposalTurnStatus.ACCEPTED
                artifacts = _proposal_artifacts(parsed_graphs)

        turn = ProgramProposalTurnReceipt(
            turn_index=turn_index,
            request_sha256=request_sha256,
            raw_response=raw_response,
            raw_response_sha256=hashlib.sha256(raw_response).hexdigest(),
            status=receipt_status,
            model_calls=response.usage_model_calls,
            input_tokens=response.usage_input_tokens,
            output_tokens=response.usage_output_tokens,
            cache_read_tokens=response.usage_cache_read_tokens,
            cache_write_tokens=response.usage_cache_write_tokens,
            estimated_cost_usd=estimated_cost,
            wall_time_seconds=turn_elapsed,
            provider_error=_provider_error(response),
        )
        turns.append(turn)

        terminal_status = _terminal_invocation_status(
            turn_status=receipt_status,
            turn_index=turn_index,
            max_turns=selected_policy.max_turns,
        )
        if terminal_status is not None:
            return _invocation_result(
                invocation_id=invocation_id,
                status=terminal_status,
                policy=selected_policy,
                problem_view=selected_view,
                candidate_manifest=selected_manifest,
                turns=tuple(turns),
                artifacts=(artifacts if terminal_status is ProgramProposalInvocationStatus.COMPLETED else ()),
                total_wall_time_seconds=max(0.0, clock() - started_at),
            )

    raise AssertionError("bounded proposer loop ended without a terminal result")


def _complete_with_limits(
    *,
    client: DirectClient,
    request: DirectCompletionRequest,
    timeout_seconds: float,
    max_output_tokens: int,
) -> DirectCompletionResponse:
    if isinstance(client, BoundedProgramProposalClient):
        return client.complete_bounded(
            request,
            timeout_seconds=timeout_seconds,
            max_output_tokens=max_output_tokens,
        )
    return client.complete(request)


def _transport_failure_response(error: Exception) -> DirectCompletionResponse:
    try:
        error_text = str(error).strip()
    except Exception:
        error_text = ""
    detail = f": {error_text}" if error_text else ""
    model_calls = _safe_exception_usage(error, "usage_model_calls")
    input_tokens = _safe_exception_usage(error, "usage_input_tokens")
    output_tokens = _safe_exception_usage(error, "usage_output_tokens")
    cache_read_tokens = _safe_exception_usage(error, "usage_cache_read_tokens")
    cache_write_tokens = _safe_exception_usage(error, "usage_cache_write_tokens")
    return DirectCompletionResponse(
        output_text="",
        error_message=f"provider transport raised {type(error).__name__}{detail}",
        usage_model_calls=model_calls,
        usage_input_tokens=input_tokens,
        usage_output_tokens=output_tokens,
        usage_cache_read_tokens=cache_read_tokens,
        usage_cache_write_tokens=cache_write_tokens,
    )


@dataclass(frozen=True, slots=True)
class _NormalizedProviderUsage:
    """Validated optional usage dimensions reported by one direct response."""

    model_calls: int | None
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_write_tokens: int | None


def _normalize_provider_response(response: object) -> DirectCompletionResponse:
    issues: list[str] = []
    output_text = _normalized_output_text(response, issues)
    error_message = _normalized_error_message(response, issues)
    usage = _normalized_provider_usage(response, issues)
    timed_out = _normalized_timeout(response, issues)

    malformed_error = f"provider returned malformed response: {'; '.join(dict.fromkeys(issues))}" if issues else None
    if malformed_error is not None:
        error_message = malformed_error
    elif error_message is not None and not error_message.strip():
        error_message = "provider reported an unspecified failure"

    return DirectCompletionResponse(
        output_text=output_text,
        error_message=error_message,
        usage_model_calls=usage.model_calls,
        usage_input_tokens=usage.input_tokens,
        usage_output_tokens=usage.output_tokens,
        usage_cache_read_tokens=usage.cache_read_tokens,
        usage_cache_write_tokens=usage.cache_write_tokens,
        timed_out=timed_out,
    )


def _normalized_output_text(response: object, issues: list[str]) -> str:
    value = _safe_response_attribute(response, "output_text", issues)
    if not isinstance(value, str):
        issues.append("output_text must be a string")
        return ""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        issues.append("output_text must be valid UTF-8")
        return ""
    return value


def _normalized_error_message(response: object, issues: list[str]) -> str | None:
    value = _safe_response_attribute(response, "error_message", issues)
    if value is None:
        return None
    if not isinstance(value, str):
        issues.append("error_message must be a string or null")
        return None
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        issues.append("error_message must be valid UTF-8")
        return None
    return value


def _normalized_provider_usage(
    response: object,
    issues: list[str],
) -> _NormalizedProviderUsage:
    return _NormalizedProviderUsage(
        model_calls=_normalized_optional_usage(
            response,
            "usage_model_calls",
            issues,
            missing_default=1,
        ),
        input_tokens=_normalized_required_usage(
            response,
            "usage_input_tokens",
            issues,
        ),
        output_tokens=_normalized_required_usage(
            response,
            "usage_output_tokens",
            issues,
        ),
        cache_read_tokens=_normalized_optional_usage(
            response,
            "usage_cache_read_tokens",
            issues,
        ),
        cache_write_tokens=_normalized_optional_usage(
            response,
            "usage_cache_write_tokens",
            issues,
        ),
    )


def _normalized_optional_usage(
    response: object,
    name: str,
    issues: list[str],
    *,
    missing_default: int | None = None,
) -> int | None:
    try:
        value = getattr(response, name)
    except AttributeError:
        return missing_default
    except Exception as error:
        issues.append(f"{name} could not be read ({type(error).__name__})")
        return None
    return _normalized_usage_value(value, name=name, issues=issues)


def _normalized_required_usage(
    response: object,
    name: str,
    issues: list[str],
) -> int | None:
    value = _safe_response_attribute(response, name, issues)
    return _normalized_usage_value(value, name=name, issues=issues)


def _normalized_usage_value(
    value: object,
    *,
    name: str,
    issues: list[str],
) -> int | None:
    normalized = _known_nonnegative_int(value)
    if value is not None and normalized is None:
        issues.append(f"{name} must be a non-negative integer or null")
    return normalized


def _normalized_timeout(response: object, issues: list[str]) -> bool:
    value = _safe_response_attribute(response, "timed_out", issues)
    if not isinstance(value, bool):
        issues.append("timed_out must be a boolean")
        return False
    return value


def _safe_response_attribute(
    response: object,
    name: str,
    issues: list[str],
) -> object:
    try:
        return getattr(response, name)
    except Exception as error:
        issues.append(f"{name} could not be read ({type(error).__name__})")
        return None


def _known_nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _safe_exception_usage(error: Exception, name: str) -> int | None:
    try:
        value = getattr(error, name, None)
    except Exception:
        return None
    return _known_nonnegative_int(value)


def _validate_invocation_bindings(
    *,
    policy: FrozenProgramProposerPolicy,
    problem_view: DecompositionProblemView,
    candidate_manifest: CandidateGenerationManifest,
) -> None:
    if candidate_manifest.problem_view_sha256 != problem_view.content_sha256:
        raise ValueError("candidate generation manifest does not bind the public problem view")
    if candidate_manifest.proposal_policy_sha256 != policy.content_sha256:
        raise ValueError("candidate generation manifest does not bind the frozen proposal policy")
    if candidate_manifest.policy_checkpoint_sha256 != policy.policy_checkpoint_sha256:
        raise ValueError("candidate generation manifest does not bind the frozen policy checkpoint")
    if candidate_manifest.expected_candidate_count != policy.expected_plan_count:
        raise ValueError("candidate generation count does not match the frozen proposer policy")


def _normalized_invocation_inputs(
    *,
    policy: FrozenProgramProposerPolicy,
    problem_view: DecompositionProblemView,
    candidate_manifest: CandidateGenerationManifest,
) -> tuple[
    FrozenProgramProposerPolicy,
    DecompositionProblemView,
    CandidateGenerationManifest,
    str,
]:
    selected_policy = FrozenProgramProposerPolicy.model_validate(
        policy.model_dump(mode="python"),
    )
    selected_view = DecompositionProblemView.model_validate(
        problem_view.model_dump(mode="python"),
    )
    selected_manifest = CandidateGenerationManifest.model_validate(
        candidate_manifest.model_dump(mode="python"),
    )
    _validate_invocation_bindings(
        policy=selected_policy,
        problem_view=selected_view,
        candidate_manifest=selected_manifest,
    )
    if selected_policy.grammar_sha256 != program_proposal_grammar_sha256():
        raise ValueError("frozen proposer policy carries an unrecognized grammar identity")
    try:
        system_prompt = selected_policy.instruction_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("frozen proposer instruction bytes must be valid UTF-8") from error
    return (
        selected_policy,
        selected_view,
        selected_manifest,
        system_prompt,
    )


def _initial_instruction(
    *,
    policy: FrozenProgramProposerPolicy,
    problem_view: DecompositionProblemView,
    candidate_manifest: CandidateGenerationManifest,
) -> str:
    payload = {
        "request_kind": "zero_shot_decomposition",
        "problem_view": problem_view.model_dump(mode="json"),
        "candidate_generation": {
            "manifest_id": candidate_manifest.manifest_id,
            "coordinates": [coordinate.model_dump(mode="json") for coordinate in candidate_manifest.coordinates],
            "expected_plan_count": candidate_manifest.expected_candidate_count,
        },
        "required_bindings": {
            "problem_view_sha256": problem_view.content_sha256,
            "proposal_policy_sha256": policy.content_sha256,
            "policy_checkpoint_sha256": policy.policy_checkpoint_sha256,
            "grammar_sha256": policy.grammar_sha256,
            "output_completion_contract_sha256": canonical_content_sha256(
                problem_view.output_contract.model_dump(mode="json")
            ),
        },
        "output_envelope": {
            "json_schema": json.loads(program_proposal_grammar_bytes()),
        },
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _correction_instruction(initial_instruction: str) -> str:
    payload = json.loads(initial_instruction)
    payload["grammar_correction"] = (
        "The previous response did not satisfy the frozen JSON grammar. "
        "Return a complete replacement envelope only; no diagnostic details are available."
    )
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _preparse_turn_status(
    *,
    response: DirectCompletionResponse,
    policy: FrozenProgramProposerPolicy,
    prior_turns: tuple[ProgramProposalTurnReceipt, ...],
    total_elapsed: float,
) -> tuple[ProgramProposalTurnStatus | None, float | None]:
    if response.error_message is not None or response.timed_out:
        estimated = _estimated_response_cost(response=response, model=policy.model_id)
        return ProgramProposalTurnStatus.PROVIDER_FAILED, estimated
    estimated_cost = _estimated_response_cost(response=response, model=policy.model_id)
    if response.usage_input_tokens is None or response.usage_output_tokens is None or estimated_cost is None:
        return ProgramProposalTurnStatus.USAGE_EVIDENCE_MISSING, estimated_cost
    observed_tokens = (
        sum((turn.input_tokens or 0) + (turn.output_tokens or 0) for turn in prior_turns)
        + response.usage_input_tokens
        + response.usage_output_tokens
    )
    observed_cost = sum(turn.estimated_cost_usd or 0.0 for turn in prior_turns) + estimated_cost
    if (
        observed_tokens > policy.max_observed_tokens
        or observed_cost > policy.max_cost_usd
        or total_elapsed > policy.max_wall_time_seconds
    ):
        return ProgramProposalTurnStatus.BUDGET_EXHAUSTED, estimated_cost
    return None, estimated_cost


def _provider_error(response: DirectCompletionResponse) -> str | None:
    if response.error_message is not None:
        return response.error_message
    if response.timed_out:
        return "provider request timed out"
    return None


def _estimated_response_cost(
    *,
    response: DirectCompletionResponse,
    model: str,
) -> float | None:
    if response.usage_input_tokens is None or response.usage_output_tokens is None:
        return None
    cache_read_tokens = response.usage_cache_read_tokens or 0
    cache_write_tokens = response.usage_cache_write_tokens or 0
    pricing = match_pricing(model)
    if pricing is None:
        return None
    if (cache_read_tokens > 0 and "cache_read" not in pricing) or (
        cache_write_tokens > 0 and "cache_write" not in pricing
    ):
        return None
    return estimate_cost_usd(
        model,
        input_tokens=response.usage_input_tokens,
        output_tokens=response.usage_output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )


def _parse_bound_graphs(
    *,
    raw_response: bytes,
    policy: FrozenProgramProposerPolicy,
    problem_view: DecompositionProblemView,
    candidate_manifest: CandidateGenerationManifest,
) -> tuple[ProposedDecompositionGraph, ...] | None:
    try:
        envelope = _ProgramProposalEnvelope.model_validate_json(raw_response)
    except ValueError:
        return None
    expected_coordinates = {
        coordinate.candidate_id: coordinate.coordinate_id for coordinate in candidate_manifest.coordinates
    }
    observed_coordinates = {graph.candidate_id: graph.generation_coordinate_id for graph in envelope.plans}
    if observed_coordinates != expected_coordinates:
        return None
    if any(
        graph.problem_view_sha256 != problem_view.content_sha256
        or graph.proposal_policy_sha256 != policy.content_sha256
        or graph.policy_checkpoint_sha256 != policy.policy_checkpoint_sha256
        or graph.proposal_grammar_sha256 != policy.grammar_sha256
        for graph in envelope.plans
    ):
        return None
    return tuple(sorted(envelope.plans, key=lambda graph: graph.candidate_id))


def _proposal_artifacts(
    graphs: tuple[ProposedDecompositionGraph, ...],
) -> tuple[ProgramProposalArtifact, ...]:
    artifacts = []
    for graph in graphs:
        content = json.dumps(
            graph.model_dump(mode="json", exclude={"content_sha256"}),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        reference = ProgramCandidateRef(
            candidate_id=graph.candidate_id,
            kind=ProgramCandidateKind.PROPOSAL,
            candidate_artifact_sha256=hashlib.sha256(content).hexdigest(),
            generation_coordinate_id=graph.generation_coordinate_id,
        )
        artifacts.append(
            ProgramProposalArtifact(
                reference=reference,
                graph=graph,
                content=content,
            )
        )
    return tuple(artifacts)


def _terminal_invocation_status(
    *,
    turn_status: ProgramProposalTurnStatus,
    turn_index: int,
    max_turns: int,
) -> ProgramProposalInvocationStatus | None:
    mapping = {
        ProgramProposalTurnStatus.ACCEPTED: ProgramProposalInvocationStatus.COMPLETED,
        ProgramProposalTurnStatus.PROVIDER_FAILED: ProgramProposalInvocationStatus.PROVIDER_FAILED,
        ProgramProposalTurnStatus.USAGE_EVIDENCE_MISSING: (ProgramProposalInvocationStatus.USAGE_EVIDENCE_INCOMPLETE),
        ProgramProposalTurnStatus.BUDGET_EXHAUSTED: ProgramProposalInvocationStatus.BUDGET_EXHAUSTED,
    }
    terminal = mapping.get(turn_status)
    if terminal is not None:
        return terminal
    if turn_index == max_turns:
        return ProgramProposalInvocationStatus.GRAMMAR_EXHAUSTED
    return None


def _invocation_result(
    *,
    invocation_id: str,
    status: ProgramProposalInvocationStatus,
    policy: FrozenProgramProposerPolicy,
    problem_view: DecompositionProblemView,
    candidate_manifest: CandidateGenerationManifest,
    turns: tuple[ProgramProposalTurnReceipt, ...],
    artifacts: tuple[ProgramProposalArtifact, ...],
    total_wall_time_seconds: float,
) -> ProgramProposalInvocation:
    total_model_calls = sum(turn.model_calls or 0 for turn in turns)
    total_input_tokens = sum(turn.input_tokens or 0 for turn in turns)
    total_output_tokens = sum(turn.output_tokens or 0 for turn in turns)
    total_cache_read_tokens = sum(turn.cache_read_tokens or 0 for turn in turns)
    total_cache_write_tokens = sum(turn.cache_write_tokens or 0 for turn in turns)
    return ProgramProposalInvocation(
        invocation_id=invocation_id,
        status=status,
        policy_sha256=policy.content_sha256,
        problem_view_sha256=problem_view.content_sha256,
        candidate_manifest_sha256=candidate_manifest.content_sha256,
        model_id=policy.model_id,
        policy_checkpoint_sha256=policy.policy_checkpoint_sha256,
        grammar_sha256=policy.grammar_sha256,
        turns=turns,
        artifacts=artifacts,
        total_model_calls=total_model_calls,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_cache_read_tokens=total_cache_read_tokens,
        total_cache_write_tokens=total_cache_write_tokens,
        total_observed_tokens=total_input_tokens + total_output_tokens,
        total_estimated_cost_usd=sum(turn.estimated_cost_usd or 0.0 for turn in turns),
        total_wall_time_seconds=total_wall_time_seconds,
        usage_evidence_complete=all(
            turn.model_calls is not None
            and turn.input_tokens is not None
            and turn.output_tokens is not None
            and turn.estimated_cost_usd is not None
            for turn in turns
        ),
    )


def proposal_artifacts_for_freeze(
    *,
    invocation: ProgramProposalInvocation,
    producer: AuthorityPrincipal,
    producer_process_id: str,
) -> tuple[ProposalArtifact, ...]:
    """Convert one successful invocation into exact model-origin freeze artifacts."""

    selected = ProgramProposalInvocation.model_validate(invocation.model_dump(mode="python"))
    if selected.status is not ProgramProposalInvocationStatus.COMPLETED:
        raise ValueError("only a completed proposer invocation can realize freeze artifacts")
    if len(selected.artifacts) != 2:
        raise ValueError("freeze conversion requires exactly two completed proposal artifacts")
    if producer.kind is not AuthorityPrincipalKind.MODEL:
        raise ValueError("proposer freeze artifacts require a MODEL principal")
    return tuple(
        ProposalArtifact(
            reference=artifact.reference,
            content=artifact.content,
            producer=producer,
            producer_process_id=producer_process_id,
            invocation_id=selected.invocation_id,
        )
        for artifact in selected.artifacts
    )
