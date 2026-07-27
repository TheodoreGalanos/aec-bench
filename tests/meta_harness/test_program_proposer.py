# ABOUTME: Tests frozen zero-shot proposal generation at the Phase 9.1a provider boundary.
# ABOUTME: Proves exact graph binding, inert JSON, generic grammar retries, and complete usage evidence.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from aec_bench.adapters.direct import (
    DirectCompletionRequest,
    DirectCompletionResponse,
    ReplayDirectClient,
)
from aec_bench.contracts.authority import (
    AuthorityPrincipal,
    AuthorityPrincipalKind,
)
from aec_bench.contracts.harness_instance import HarnessBudget
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.pricing import estimate_cost_usd
from aec_bench.contracts.program_proposal import (
    CandidateGenerationCoordinate,
    CandidateGenerationManifest,
    DecompositionProblemView,
    ProgramCandidateKind,
)
from aec_bench.contracts.program_proposer import FrozenProgramProposerPolicy
from aec_bench.contracts.proposal_execution import ProposedDecompositionGraph
from aec_bench.meta_harness.program_proposer import (
    ProgramProposalInvocationStatus,
    ProgramProposalTurnStatus,
    generate_frozen_program_proposals,
    preflight_program_proposal_invocation,
    program_proposal_grammar_sha256,
    proposal_artifacts_for_freeze,
)


def _sha(value: str | bytes) -> str:
    encoded = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _policy(
    *,
    model_id: str = "au.anthropic.claude-sonnet-4-6",
) -> FrozenProgramProposerPolicy:
    instruction_bytes = (
        b"Return exactly two proposed-decomposition-graph objects in one JSON envelope.\n"
        b"Use only the supplied public problem view. Return JSON only.\n"
    )
    return FrozenProgramProposerPolicy(
        policy_id="proposer.phase9.1a",
        version="1",
        instruction_bytes=instruction_bytes,
        instruction_sha256=_sha(instruction_bytes),
        model_id=model_id,
        policy_checkpoint_sha256=_sha("checkpoint.phase9.1a"),
        grammar_sha256=program_proposal_grammar_sha256(),
    )


def _problem_view(policy: FrozenProgramProposerPolicy) -> DecompositionProblemView:
    del policy
    return DecompositionProblemView.model_validate(
        {
            "problem_id": "problem.calibration.alpha",
            "task_id": "civil/calibration/alpha",
            "task_revision": _sha("task-definition"),
            "public_task_snapshot_sha256": _sha("public-snapshot"),
            "public_instruction": "Review the public drainage evidence and return a decision.",
            "public_sources": [
                {
                    "source_id": "source.review-packet",
                    "opaque_handle": "packet-alpha",
                    "media_type": "text/markdown",
                    "byte_size": 512,
                    "source_sha256": _sha("public-source"),
                }
            ],
            "output_contract": {
                "schema_version": "aecbench.output-completion-contract.v1",
                "output_path": "output.md",
                "format": "markdown_final_fenced_json",
                "required_top_level_keys": ["decision"],
                "require_single_final_json_block": True,
            },
            "fixed_harness": {
                "kernel_sha256": _sha("kernel"),
                "harness_policy_sha256": _sha("h0"),
                "capability_ids": ["context.public", "tool.read"],
                "aggregate_budget": HarnessBudget(
                    max_parallelism=2,
                    max_total_attempts=32,
                    max_agent_turns=32,
                    max_tool_calls=64,
                    max_context_tokens=300_000,
                    max_runtime_seconds=3_600,
                    max_tokens=300_000,
                    max_cost_usd=1.25,
                ).model_dump(mode="json"),
            },
            "public_domain_id": "civil",
            "public_task_family_id": "drainage-calibration",
        }
    )


def _manifest(
    policy: FrozenProgramProposerPolicy,
    problem_view: DecompositionProblemView,
) -> CandidateGenerationManifest:
    return CandidateGenerationManifest(
        manifest_id="candidate-generation.alpha",
        problem_view_sha256=problem_view.content_sha256,
        proposal_policy_sha256=policy.content_sha256,
        policy_checkpoint_sha256=policy.policy_checkpoint_sha256,
        selection_policy_sha256=_sha("no-selection"),
        expected_candidate_count=2,
        coordinates=(
            CandidateGenerationCoordinate(
                coordinate_id="generation.alpha.1",
                candidate_id="candidate.alpha.1",
                seed=101,
            ),
            CandidateGenerationCoordinate(
                coordinate_id="generation.alpha.2",
                candidate_id="candidate.alpha.2",
                seed=202,
            ),
        ),
        stopping_policy_sha256=_sha("stop-after-two"),
    )


def _graph_payload(
    *,
    coordinate: CandidateGenerationCoordinate,
    policy: FrozenProgramProposerPolicy,
    problem_view: DecompositionProblemView,
) -> dict[str, Any]:
    return {
        "candidate_id": coordinate.candidate_id,
        "generation_coordinate_id": coordinate.coordinate_id,
        "problem_view_sha256": problem_view.content_sha256,
        "proposal_policy_sha256": policy.content_sha256,
        "policy_checkpoint_sha256": policy.policy_checkpoint_sha256,
        "proposal_grammar_sha256": policy.grammar_sha256,
        "semantic_subtasks": [
            {
                "node_id": f"extract.{coordinate.seed}",
                "objective": "Extract decision-relevant facts and source provenance.",
                "source_scope": {"source_ids": ["source.review-packet"]},
                "input_ports": [],
                "output_ports": [
                    {
                        "output_id": "facts",
                        "kind": "fact_set",
                    }
                ],
                "evidence_contract": {
                    "required_output_ids": ["facts"],
                    "require_provenance": True,
                    "allow_explicit_data_gap": True,
                },
            }
        ],
        "finalizer": {
            "node_id": f"finalize.{coordinate.seed}",
            "objective": "Synthesize the required final decision from the extracted facts.",
            "source_scope": {"source_ids": []},
            "input_ports": [
                {
                    "input_id": "facts",
                    "kind": "fact_set",
                }
            ],
            "output_completion_contract_sha256": canonical_content_sha256(
                problem_view.output_contract.model_dump(mode="json")
            ),
        },
        "handoffs": [
            {
                "handoff_id": f"handoff.{coordinate.seed}",
                "producer_node_id": f"extract.{coordinate.seed}",
                "producer_output_id": "facts",
                "consumer_node_id": f"finalize.{coordinate.seed}",
                "consumer_input_id": "facts",
            }
        ],
    }


def _valid_response(
    policy: FrozenProgramProposerPolicy,
    problem_view: DecompositionProblemView,
    manifest: CandidateGenerationManifest,
) -> str:
    return json.dumps(
        {
            "plans": [
                _graph_payload(
                    coordinate=coordinate,
                    policy=policy,
                    problem_view=problem_view,
                )
                for coordinate in manifest.coordinates
            ]
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _response(
    output_text: str,
    *,
    model_calls: int | None = 1,
    input_tokens: int | None = 800,
    output_tokens: int | None = 1_200,
    cache_read_tokens: int | None = None,
    cache_write_tokens: int | None = None,
    error_message: str | None = None,
) -> DirectCompletionResponse:
    return DirectCompletionResponse(
        output_text=output_text,
        error_message=error_message,
        usage_model_calls=model_calls,
        usage_input_tokens=input_tokens,
        usage_output_tokens=output_tokens,
        usage_cache_read_tokens=cache_read_tokens,
        usage_cache_write_tokens=cache_write_tokens,
    )


@dataclass
class _RecordingReplayClient:
    """Exercise the real replay response contract while retaining exact requests."""

    replay: ReplayDirectClient
    requests: list[DirectCompletionRequest] = field(default_factory=list)

    def complete(self, request: DirectCompletionRequest) -> DirectCompletionResponse:
        self.requests.append(request)
        return self.replay.complete(request)


@dataclass
class _ManualClock:
    """Expose deterministic provider and parser time without sleeping."""

    now: float = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class _BoundedClient:
    """Record limits delivered through the optional bounded-client surface."""

    response: DirectCompletionResponse
    clock: _ManualClock | None = None
    elapsed_seconds: float = 0.0
    requests: list[DirectCompletionRequest] = field(default_factory=list)
    limits: list[tuple[float, int]] = field(default_factory=list)

    def complete(self, request: DirectCompletionRequest) -> DirectCompletionResponse:
        raise AssertionError("bounded proposer clients must use complete_bounded")

    def complete_bounded(
        self,
        request: DirectCompletionRequest,
        *,
        timeout_seconds: float,
        max_output_tokens: int,
    ) -> DirectCompletionResponse:
        self.requests.append(request)
        self.limits.append((timeout_seconds, max_output_tokens))
        if self.clock is not None:
            self.clock.advance(self.elapsed_seconds)
        return self.response


@dataclass
class _RaisingClient:
    """Raise after receiving a request to represent a transport failure."""

    error: Exception
    requests: list[DirectCompletionRequest] = field(default_factory=list)

    def complete(self, request: DirectCompletionRequest) -> DirectCompletionResponse:
        self.requests.append(request)
        raise self.error


@dataclass
class _MalformedClient:
    """Return an object outside the direct provider response contract."""

    response: object

    def complete(self, request: DirectCompletionRequest) -> DirectCompletionResponse:
        del request
        return self.response  # type: ignore[return-value]


def test_one_frozen_invocation_returns_exactly_two_canonical_bound_artifacts() -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)
    raw_response = _valid_response(policy, problem_view, manifest)
    client = _RecordingReplayClient(
        ReplayDirectClient(response=_response(raw_response)),
    )

    result = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.alpha",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=client,
    )

    assert result.status is ProgramProposalInvocationStatus.COMPLETED
    assert result.policy_sha256 == policy.content_sha256
    assert result.problem_view_sha256 == problem_view.content_sha256
    assert result.candidate_manifest_sha256 == manifest.content_sha256
    assert len(result.turns) == 1
    assert result.turns[0].status is ProgramProposalTurnStatus.ACCEPTED
    assert result.turns[0].raw_response == raw_response.encode("utf-8")
    assert result.turns[0].raw_response_sha256 == _sha(raw_response)
    assert result.total_input_tokens == 800
    assert result.total_output_tokens == 1_200
    assert result.total_observed_tokens == 2_000
    assert result.total_estimated_cost_usd > 0
    assert len(result.artifacts) == 2
    assert {artifact.reference.candidate_id for artifact in result.artifacts} == {
        coordinate.candidate_id for coordinate in manifest.coordinates
    }
    assert all(artifact.reference.kind is ProgramCandidateKind.PROPOSAL for artifact in result.artifacts)
    for artifact in result.artifacts:
        assert hashlib.sha256(artifact.content).hexdigest() == (artifact.reference.candidate_artifact_sha256)
        assert artifact.reference.candidate_artifact_sha256 == (artifact.graph.content_sha256)
        parsed = ProposedDecompositionGraph.model_validate_json(artifact.content)
        assert parsed == artifact.graph
        assert parsed.problem_view_sha256 == problem_view.content_sha256
        assert parsed.proposal_policy_sha256 == policy.content_sha256
        assert parsed.policy_checkpoint_sha256 == policy.policy_checkpoint_sha256
        assert parsed.proposal_grammar_sha256 == policy.grammar_sha256

    assert len(client.requests) == 1
    request = client.requests[0]
    assert request.model == policy.model_id
    assert request.system_prompt == policy.instruction_bytes.decode("utf-8")
    assert problem_view.model_dump_json() not in request.instruction
    public_request = json.loads(request.instruction)
    assert public_request["problem_view"]["content_sha256"] == problem_view.content_sha256
    assert public_request["required_bindings"] == {
        "grammar_sha256": policy.grammar_sha256,
        "output_completion_contract_sha256": canonical_content_sha256(
            problem_view.output_contract.model_dump(mode="json")
        ),
        "policy_checkpoint_sha256": policy.policy_checkpoint_sha256,
        "problem_view_sha256": problem_view.content_sha256,
        "proposal_policy_sha256": policy.content_sha256,
    }
    assert public_request["output_envelope"]["json_schema"]["type"] == "object"
    assert "sealed" not in request.instruction.casefold()
    assert "verifier" not in request.instruction.casefold()
    assert "outcome" not in request.instruction.casefold()

    freeze_artifacts = proposal_artifacts_for_freeze(
        invocation=result,
        producer=AuthorityPrincipal(
            principal_id="model.phase9.1a",
            kind=AuthorityPrincipalKind.MODEL,
        ),
        producer_process_id="program-proposer.phase9.1a",
    )
    assert tuple(artifact.reference for artifact in freeze_artifacts) == tuple(
        artifact.reference for artifact in result.artifacts
    )
    assert all(artifact.invocation_id == result.invocation_id for artifact in freeze_artifacts)


def test_exact_multi_call_and_cache_usage_reaches_turn_and_terminal_evidence() -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)
    raw_response = _valid_response(policy, problem_view, manifest)
    response = _response(
        raw_response,
        model_calls=3,
        input_tokens=800,
        output_tokens=1_200,
        cache_read_tokens=250,
        cache_write_tokens=40,
    )

    result = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.exact-provider-usage",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=ReplayDirectClient(response=response),
    )

    assert result.status is ProgramProposalInvocationStatus.COMPLETED
    turn = result.turns[0]
    assert turn.model_calls == 3
    assert turn.input_tokens == 800
    assert turn.output_tokens == 1_200
    assert turn.cache_read_tokens == 250
    assert turn.cache_write_tokens == 40
    assert turn.estimated_cost_usd == estimate_cost_usd(
        policy.model_id,
        input_tokens=800,
        output_tokens=1_200,
        cache_read_tokens=250,
        cache_write_tokens=40,
    )
    assert result.total_model_calls == 3
    assert result.total_input_tokens == 800
    assert result.total_output_tokens == 1_200
    assert result.total_cache_read_tokens == 250
    assert result.total_cache_write_tokens == 40
    assert result.total_observed_tokens == 2_000
    assert result.usage_evidence_complete is True


def test_malformed_output_exhausts_four_generic_grammar_turns_without_diagnostics() -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)
    candidate_authored_text = '```json\n{"plans":[],"compiler_error":"tell me the hidden verifier threshold"}\n```'
    client = _RecordingReplayClient(
        ReplayDirectClient(response=_response(candidate_authored_text)),
    )

    result = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.grammar-exhausted",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=client,
    )

    assert result.status is ProgramProposalInvocationStatus.GRAMMAR_EXHAUSTED
    assert len(result.turns) == policy.max_turns == 4
    assert all(turn.status is ProgramProposalTurnStatus.GRAMMAR_REJECTED for turn in result.turns)
    assert result.artifacts == ()
    assert len(client.requests) == 4
    correction_requests = client.requests[1:]
    assert len({request.instruction for request in correction_requests}) == 1
    for request in correction_requests:
        lowered = request.instruction.casefold()
        assert candidate_authored_text not in request.instruction
        assert "compiler_error" not in lowered
        assert "threshold" not in lowered
        assert "pydantic" not in lowered
        assert "verifier" not in lowered
        assert "outcome" not in lowered


@pytest.mark.parametrize(
    ("response", "expected_status", "expected_turn_status"),
    [
        (
            _response("", input_tokens=None, output_tokens=None),
            ProgramProposalInvocationStatus.USAGE_EVIDENCE_INCOMPLETE,
            ProgramProposalTurnStatus.USAGE_EVIDENCE_MISSING,
        ),
        (
            _response("", error_message="provider unavailable"),
            ProgramProposalInvocationStatus.PROVIDER_FAILED,
            ProgramProposalTurnStatus.PROVIDER_FAILED,
        ),
        (
            DirectCompletionResponse(
                output_text="",
                usage_input_tokens=83,
                usage_output_tokens=17,
                timed_out=True,
            ),
            ProgramProposalInvocationStatus.PROVIDER_FAILED,
            ProgramProposalTurnStatus.PROVIDER_FAILED,
        ),
        (
            _response("{}", input_tokens=60_000, output_tokens=50_001),
            ProgramProposalInvocationStatus.BUDGET_EXHAUSTED,
            ProgramProposalTurnStatus.BUDGET_EXHAUSTED,
        ),
    ],
)
def test_proposer_failures_preserve_raw_receipts_without_candidate_artifacts(
    response: DirectCompletionResponse,
    expected_status: ProgramProposalInvocationStatus,
    expected_turn_status: ProgramProposalTurnStatus,
) -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)

    result = generate_frozen_program_proposals(
        invocation_id=f"proposer-invocation.{expected_status.value}",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=ReplayDirectClient(response=response),
    )

    assert result.status is expected_status
    assert len(result.turns) == 1
    assert result.turns[0].status is expected_turn_status
    assert result.artifacts == ()
    if response.usage_input_tokens is not None and response.usage_output_tokens is not None:
        assert result.total_input_tokens == response.usage_input_tokens
        assert result.total_output_tokens == response.usage_output_tokens
        assert result.total_estimated_cost_usd > 0


def test_transport_exception_returns_terminal_evidence_instead_of_escaping() -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)
    client = _RaisingClient(error=TimeoutError("socket closed after request submission"))

    result = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.transport-failed",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=client,
    )

    assert result.status is ProgramProposalInvocationStatus.PROVIDER_FAILED
    assert len(client.requests) == 1
    assert len(result.turns) == 1
    turn = result.turns[0]
    assert turn.status is ProgramProposalTurnStatus.PROVIDER_FAILED
    assert turn.raw_response == b""
    assert turn.input_tokens is None
    assert turn.output_tokens is None
    assert turn.estimated_cost_usd is None
    assert turn.provider_error == "provider transport raised TimeoutError: socket closed after request submission"
    assert result.usage_evidence_complete is False
    assert result.artifacts == ()


def test_transport_exception_preserves_exact_reported_provider_usage() -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)
    error = TimeoutError("socket closed after provider retry")
    error.usage_model_calls = 2  # type: ignore[attr-defined]
    error.usage_input_tokens = 377  # type: ignore[attr-defined]
    error.usage_output_tokens = 19  # type: ignore[attr-defined]
    error.usage_cache_read_tokens = 144  # type: ignore[attr-defined]
    error.usage_cache_write_tokens = 12  # type: ignore[attr-defined]

    result = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.metered-transport-failure",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=_RaisingClient(error=error),
    )

    assert result.status is ProgramProposalInvocationStatus.PROVIDER_FAILED
    turn = result.turns[0]
    assert turn.model_calls == 2
    assert turn.input_tokens == 377
    assert turn.output_tokens == 19
    assert turn.cache_read_tokens == 144
    assert turn.cache_write_tokens == 12
    assert turn.estimated_cost_usd == estimate_cost_usd(
        policy.model_id,
        input_tokens=377,
        output_tokens=19,
        cache_read_tokens=144,
        cache_write_tokens=12,
    )
    assert result.total_model_calls == 2
    assert result.total_cache_read_tokens == 144
    assert result.total_cache_write_tokens == 12
    assert result.usage_evidence_complete is True


def test_observed_cache_usage_without_a_price_fails_cost_evidence_closed() -> None:
    policy = _policy(model_id="o3-mini")
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)

    result = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.unpriceable-cache",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=ReplayDirectClient(
            response=_response(
                _valid_response(policy, problem_view, manifest),
                cache_read_tokens=5,
                cache_write_tokens=7,
            )
        ),
    )

    assert result.status is ProgramProposalInvocationStatus.USAGE_EVIDENCE_INCOMPLETE
    turn = result.turns[0]
    assert turn.status is ProgramProposalTurnStatus.USAGE_EVIDENCE_MISSING
    assert turn.cache_read_tokens == 5
    assert turn.cache_write_tokens == 7
    assert turn.estimated_cost_usd is None
    assert result.total_cache_read_tokens == 5
    assert result.total_cache_write_tokens == 7
    assert result.total_estimated_cost_usd == 0.0
    assert result.usage_evidence_complete is False
    assert result.artifacts == ()


def test_provider_failure_precedes_unpriceable_usage_without_losing_evidence() -> None:
    policy = _policy(model_id="o3-mini")
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)

    result = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.failed-unpriceable-cache",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=ReplayDirectClient(
            response=_response(
                "",
                model_calls=2,
                input_tokens=90,
                output_tokens=4,
                cache_read_tokens=5,
                cache_write_tokens=7,
                error_message="provider rejected the request",
            )
        ),
    )

    assert result.status is ProgramProposalInvocationStatus.PROVIDER_FAILED
    turn = result.turns[0]
    assert turn.status is ProgramProposalTurnStatus.PROVIDER_FAILED
    assert turn.provider_error == "provider rejected the request"
    assert turn.model_calls == 2
    assert turn.cache_read_tokens == 5
    assert turn.cache_write_tokens == 7
    assert turn.estimated_cost_usd is None
    assert result.total_model_calls == 2
    assert result.total_cache_read_tokens == 5
    assert result.total_cache_write_tokens == 7
    assert result.usage_evidence_complete is False


def test_malformed_provider_response_fails_closed_but_retains_known_usage_and_cost() -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)

    @dataclass(frozen=True)
    class _MalformedResponse:
        output_text: int = 17
        error_message: None = None
        usage_input_tokens: int = 321
        usage_output_tokens: int = 123
        timed_out: bool = False

    result = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.malformed-response",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=_MalformedClient(response=_MalformedResponse()),
    )

    assert result.status is ProgramProposalInvocationStatus.PROVIDER_FAILED
    turn = result.turns[0]
    assert turn.status is ProgramProposalTurnStatus.PROVIDER_FAILED
    assert turn.raw_response == b""
    assert turn.input_tokens == 321
    assert turn.output_tokens == 123
    assert turn.estimated_cost_usd is not None
    assert turn.provider_error == "provider returned malformed response: output_text must be a string"
    assert result.total_input_tokens == 321
    assert result.total_output_tokens == 123
    assert result.total_estimated_cost_usd == turn.estimated_cost_usd
    assert result.usage_evidence_complete is True


def test_non_utf8_provider_text_is_a_typed_malformed_response() -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)

    result = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.non-utf8-response",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=ReplayDirectClient(
            response=_response(
                "\ud800",
                input_tokens=29,
                output_tokens=1,
            )
        ),
    )

    assert result.status is ProgramProposalInvocationStatus.PROVIDER_FAILED
    assert result.turns[0].raw_response == b""
    assert result.turns[0].provider_error == "provider returned malformed response: output_text must be valid UTF-8"
    assert result.total_observed_tokens == 30
    assert result.total_estimated_cost_usd > 0


def test_blank_provider_error_is_normalized_without_losing_usage() -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)

    result = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.blank-provider-error",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=ReplayDirectClient(
            response=_response(
                "",
                input_tokens=41,
                output_tokens=3,
                error_message="",
            )
        ),
    )

    assert result.status is ProgramProposalInvocationStatus.PROVIDER_FAILED
    assert result.turns[0].provider_error == "provider reported an unspecified failure"
    assert result.total_observed_tokens == 44
    assert result.total_estimated_cost_usd > 0


def test_supported_bounded_client_receives_remaining_deadline_and_output_cap() -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)
    clock = _ManualClock()
    client = _BoundedClient(response=_response(_valid_response(policy, problem_view, manifest)))

    result = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.bounded-client",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=client,
        clock=clock,
    )

    assert result.status is ProgramProposalInvocationStatus.COMPLETED
    assert client.limits == [(600.0, 100_000)]
    assert client.requests[0].configuration == {
        "max_output_tokens": 100_000,
        "temperature": 0.0,
        "timeout_seconds": 600.0,
    }


def test_elapsed_deadline_returns_budget_terminal_with_known_response_usage() -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)
    clock = _ManualClock()
    client = _BoundedClient(
        response=_response(_valid_response(policy, problem_view, manifest)),
        clock=clock,
        elapsed_seconds=601.0,
    )

    result = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.deadline",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=client,
        clock=clock,
    )

    assert result.status is ProgramProposalInvocationStatus.BUDGET_EXHAUSTED
    assert result.total_wall_time_seconds == 601.0
    assert result.total_observed_tokens == 2_000
    assert result.total_estimated_cost_usd > 0
    assert result.artifacts == ()


def test_total_wall_time_covers_setup_and_parsing_not_only_provider_call_span() -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)
    observed_times = iter((0.0, 2.0, 5.0, 7.0, 11.0))

    result = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.whole-wall",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=ReplayDirectClient(response=_response(_valid_response(policy, problem_view, manifest))),
        clock=lambda: next(observed_times),
    )

    assert result.status is ProgramProposalInvocationStatus.COMPLETED
    assert result.turns[0].wall_time_seconds == 3.0
    assert result.total_wall_time_seconds == 11.0


def test_freeze_artifact_conversion_rejects_non_model_producer() -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)
    invocation = generate_frozen_program_proposals(
        invocation_id="proposer-invocation.non-model-producer",
        policy=policy,
        problem_view=problem_view,
        candidate_manifest=manifest,
        client=ReplayDirectClient(response=_response(_valid_response(policy, problem_view, manifest))),
    )

    with pytest.raises(ValueError, match="MODEL principal"):
        proposal_artifacts_for_freeze(
            invocation=invocation,
            producer=AuthorityPrincipal(
                principal_id="human.operator",
                kind=AuthorityPrincipalKind.HUMAN,
            ),
            producer_process_id="program-proposer.phase9.1a",
        )


def test_manifest_policy_mismatch_fails_before_any_provider_request() -> None:
    policy = _policy()
    problem_view = _problem_view(policy)
    manifest_payload = _manifest(policy, problem_view).model_dump(
        mode="python",
        exclude={"content_sha256"},
    )
    manifest_payload["proposal_policy_sha256"] = _sha("different-policy")
    manifest = CandidateGenerationManifest.model_validate(manifest_payload)
    client = _RecordingReplayClient(
        ReplayDirectClient(response=_response("{}")),
    )

    with pytest.raises(ValueError, match="proposal policy"):
        generate_frozen_program_proposals(
            invocation_id="proposer-invocation.invalid-manifest",
            policy=policy,
            problem_view=problem_view,
            candidate_manifest=manifest,
            client=client,
        )

    assert client.requests == []


def test_unrecognized_grammar_identity_fails_before_any_provider_request() -> None:
    valid_policy = _policy()
    policy_payload = valid_policy.model_dump(
        mode="python",
        exclude={"content_sha256"},
    )
    policy_payload["grammar_sha256"] = _sha("unrecognized-grammar")
    policy = FrozenProgramProposerPolicy.model_validate(policy_payload)
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)
    client = _RecordingReplayClient(
        ReplayDirectClient(response=_response("{}")),
    )

    with pytest.raises(ValueError, match="grammar identity"):
        generate_frozen_program_proposals(
            invocation_id="proposer-invocation.invalid-grammar",
            policy=policy,
            problem_view=problem_view,
            candidate_manifest=manifest,
            client=client,
        )

    assert client.requests == []


def test_public_preflight_rejects_non_utf8_policy_before_effect() -> None:
    valid_policy = _policy()
    policy_payload = valid_policy.model_dump(
        mode="python",
        exclude={"content_sha256"},
    )
    instruction_bytes = b"\xff"
    policy_payload.update(
        {
            "instruction_bytes": instruction_bytes,
            "instruction_sha256": _sha(instruction_bytes),
        }
    )
    policy = FrozenProgramProposerPolicy.model_validate(policy_payload)
    problem_view = _problem_view(policy)
    manifest = _manifest(policy, problem_view)

    with pytest.raises(ValueError, match="valid UTF-8"):
        preflight_program_proposal_invocation(
            policy=policy,
            problem_view=problem_view,
            candidate_manifest=manifest,
        )
