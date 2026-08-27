# ABOUTME: Provides the public entry point for one bounded AVO candidate proposal.
# ABOUTME: Validates composition inputs and delegates effects to an isolated AVO session.

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from aec_bench.contracts.evolution import ProposalUsage
from aec_bench.evolution.advice import AVOAdvisorRunner
from aec_bench.evolution.agent_protocol import (
    ApprovedKnowledgeSource,
    AVOCommand,
    AVOContext,
    AVOResponse,
    AVORunner,
    AVOTool,
    MutationInput,
    PydanticAIAVORunner,
)
from aec_bench.evolution.analysis import GraduatedScope
from aec_bench.evolution.avo_session import AVOSession
from aec_bench.evolution.avo_tools import (
    CandidateAbstentionResult,
    CandidateCheckResult,
    CandidateEditResult,
    CandidateRestoreResult,
    CandidateSubmissionResult,
)
from aec_bench.evolution.cancellation import (
    AVOCancellationCode,
    AVOCancellationReason,
    AVOCancellationSignal,
)
from aec_bench.evolution.checkpoint import AVOCheckpoint, AVOConfigurationIdentity
from aec_bench.evolution.core import AVOBudget, CandidateProposal, CandidateProposalRequest, ProposalStatus
from aec_bench.evolution.resume import (
    configuration_identity_for_request,
    evaluation_batch_digest,
    load_resumable_checkpoint,
    terminal_result_from_checkpoint,
)
from aec_bench.evolution.revision import RevisionEvaluation
from aec_bench.evolution.sanitiser import CompactionLLM
from aec_bench.evolution.workspace import Workspace, scratch_workspace_from


def run_avo(
    request: CandidateProposalRequest,
    source: Workspace,
    child_candidate_id: str,
    *,
    revision_evaluation: RevisionEvaluation,
    agent_runner: AVORunner,
    advisor_runner: AVOAdvisorRunner | None = None,
    budget: AVOBudget | None = None,
    knowledge_source: ApprovedKnowledgeSource | None = None,
    compaction_llm: CompactionLLM | None = None,
    development_evaluation_cost_usd: float | None = None,
    variation_id: str | None = None,
    avo_checkpoint_path: Path | None = None,
    configuration_identity: AVOConfigurationIdentity | None = None,
    cancellation_signal: AVOCancellationSignal | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> CandidateProposal:
    """Run one bounded, self-directed proposal call in isolated scratch.

    ``agent_runner`` is the provider composition seam. It receives an
    ``AVOContext`` and must return one validated ``AVOCommand`` per model
    request. A PydanticAI adapter can be supplied by production composition;
    tests can provide a deterministic callable without a provider.
    """
    if not isinstance(request, CandidateProposalRequest):
        raise TypeError("request must be a CandidateProposalRequest")
    if not isinstance(source, Workspace):
        raise TypeError("source must be a Workspace")
    if not isinstance(revision_evaluation, RevisionEvaluation):
        raise TypeError("revision_evaluation must be a RevisionEvaluation")
    if not callable(agent_runner):
        raise TypeError("agent_runner must be callable")
    if advisor_runner is not None and not callable(advisor_runner):
        raise TypeError("advisor_runner must be callable")
    if cancellation_signal is None:
        cancellation_signal = AVOCancellationSignal()
    if not isinstance(cancellation_signal, AVOCancellationSignal):
        raise TypeError("cancellation_signal must be an AVOCancellationSignal")
    if budget is None:
        budget = AVOBudget()
    if not isinstance(budget, AVOBudget):
        raise TypeError("budget must be an AVOBudget")
    if advisor_runner is None and budget.max_supervisor_interventions > 0:
        raise ValueError("advisor_runner is required when supervisor interventions are enabled")
    if development_evaluation_cost_usd is not None and development_evaluation_cost_usd < 0:
        raise ValueError("development_evaluation_cost_usd must be non-negative")
    if avo_checkpoint_path is not None:
        if not isinstance(avo_checkpoint_path, Path):
            raise TypeError("avo_checkpoint_path must be a Path")
        if configuration_identity is None:
            raise ValueError("configuration_identity is required when checkpointing is enabled")
    if variation_id is None:
        variation_id = f"{request.run_id}:variation-{request.cycle}:child-{child_candidate_id}"
    if cancellation_signal.cancelled and avo_checkpoint_path is None:
        # Do not even plan a development batch when cancellation is already
        # known and there is no durable authority to publish.
        cancellation_signal.raise_if_cancelled()
    planned_batch = None
    if avo_checkpoint_path is not None or request.scope is not GraduatedScope.SKIP:
        planned_batch = revision_evaluation.plan()
    effective_configuration_identity = (
        None
        if configuration_identity is None
        else configuration_identity_for_request(
            configuration_identity,
            request,
            development_evaluation_cost_usd=development_evaluation_cost_usd,
            development_batch_identity=(None if planned_batch is None else evaluation_batch_digest(planned_batch)),
        )
    )
    resume_checkpoint: AVOCheckpoint | None = None
    if avo_checkpoint_path is not None and avo_checkpoint_path.exists():
        assert planned_batch is not None
        assert effective_configuration_identity is not None
        resume_checkpoint = load_resumable_checkpoint(
            avo_checkpoint_path,
            run_id=request.run_id,
            variation_id=variation_id,
            parent_snapshot=request.parent.snapshot,
            final_child_candidate_id=child_candidate_id,
            selection=request.selection,
            development_case_ids=planned_batch.evaluation_case_ids,
            budget=budget,
            configuration_identity=effective_configuration_identity,
        )
        if resume_checkpoint.terminal_result is not None:
            if resume_checkpoint.terminal_result.status is ProposalStatus.CANCELLED:
                cancellation_signal.cancel(
                    AVOCancellationReason(
                        code=resume_checkpoint.terminal_result.cancellation_code or AVOCancellationCode.REQUESTED,
                        detail=resume_checkpoint.terminal_result.reasoning,
                    )
                )
                cancellation_signal.raise_if_cancelled()
            return terminal_result_from_checkpoint(resume_checkpoint)
    if request.scope is GraduatedScope.SKIP and avo_checkpoint_path is None and not cancellation_signal.cancelled:
        return CandidateProposal(
            status=ProposalStatus.ABSTAINED,
            child=None,
            mutation=None,
            reasoning="Proposal scope does not permit a mutation.",
            usage=ProposalUsage(),
            memory=request.memory,
        )

    with scratch_workspace_from(source, request.parent.snapshot, child_candidate_id) as scratch:
        controller = AVOSession(
            request=request,
            scratch=scratch,
            child_candidate_id=child_candidate_id,
            revision_evaluation=revision_evaluation,
            budget=budget,
            knowledge_source=knowledge_source,
            compaction_llm=compaction_llm,
            development_evaluation_cost_usd=development_evaluation_cost_usd,
            variation_id=variation_id,
            clock=clock,
            avo_checkpoint_path=avo_checkpoint_path,
            configuration_identity=effective_configuration_identity,
            resume_checkpoint=resume_checkpoint,
            cancellation_signal=cancellation_signal,
            advisor_runner=advisor_runner,
        )
        return controller.run(agent_runner)


__all__ = (
    "CandidateAbstentionResult",
    "AVOCommand",
    "AVOContext",
    "AVOResponse",
    "AVORunner",
    "AVOTool",
    "ApprovedKnowledgeSource",
    "CandidateCheckResult",
    "MutationInput",
    "CandidateEditResult",
    "PydanticAIAVORunner",
    "CandidateRestoreResult",
    "CandidateSubmissionResult",
    "run_avo",
)
