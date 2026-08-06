# ABOUTME: Orchestrates fail-closed Harbor proposal evidence import in precedence order.
# ABOUTME: Delegates configuration, boundary, seal, and artifact ownership to focused modules.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.proposal_execution.session import ProposalSessionReceipt
from aec_bench.contracts.proposal_execution_types import ProposalSessionStatus
from aec_bench.harness.harbor_importing.artifact_io import (
    read_required_trial_file,
    required_trial_directory,
)
from aec_bench.harness.harbor_importing.contracts import (
    HarborImportError,
    ImportEvidenceContext,
)
from aec_bench.harness.proposal_session_config import (
    LoadedProposalSessionHostInputs,
    ProposalSessionHostConfigError,
    load_proposal_session_host_inputs,
)

from .artifacts import build_import_evidence
from .boundary import (
    load_boundary_evidence,
    validate_final_output_evidence,
)
from .configuration import (
    validate_proposal_harbor_configuration,
    validate_proposal_session_lineage,
)
from .contracts import ProposalHarborImportEvidence


def load_proposal_import_evidence(
    *,
    context: ImportEvidenceContext,
    required_status: ProposalSessionStatus,
) -> ProposalHarborImportEvidence:
    """Load one complete proposal import while preserving validation precedence."""

    harbor_result = context.harbor_result
    agent_kwargs = harbor_result.config.agent.kwargs
    if agent_kwargs.get("extra_env") != {}:
        raise HarborImportError(
            "proposal import requires an empty serialized extra_env",
        )
    host_inputs = _load_host_inputs(context)
    validate_proposal_harbor_configuration(
        harbor_result=harbor_result,
        host_inputs=host_inputs,
    )
    collected_session_root = required_trial_directory(
        context.trial_dir / "agent" / "proposal-session",
        trial_dir=context.trial_dir,
        label="collected proposal session",
    )
    session_receipt_path = collected_session_root / "session-receipt.json"
    receipt = _load_session_receipt(
        context=context,
        path=session_receipt_path,
    )
    validate_proposal_session_lineage(
        receipt=receipt,
        host_inputs=host_inputs,
        metadata=harbor_result.agent_result.metadata,
    )
    _validate_required_status(
        receipt=receipt,
        required_status=required_status,
    )
    boundary = load_boundary_evidence(
        context=context,
        host_inputs=host_inputs,
        receipt=receipt,
        collected_session_root=collected_session_root,
        session_receipt_path=session_receipt_path,
    )
    validate_final_output_evidence(
        context=context,
        receipt=receipt,
        rotation_path=boundary.rotation_path,
        sealed_artifacts=boundary.sealed_artifacts,
    )
    return build_import_evidence(
        context=context,
        host_inputs=host_inputs,
        receipt=receipt,
        collected_session_root=collected_session_root,
        session_receipt_path=session_receipt_path,
        boundary=boundary,
    )


def _load_host_inputs(
    context: ImportEvidenceContext,
) -> LoadedProposalSessionHostInputs:
    try:
        return load_proposal_session_host_inputs(
            context.harbor_result.config.agent.kwargs.get(
                "proposal_session",
            ),
            environment_dir=(context.task_instance_dir / "environment"),
        )
    except ProposalSessionHostConfigError as error:
        raise HarborImportError(
            f"proposal host configuration is invalid: {error}",
        ) from error


def _load_session_receipt(
    *,
    context: ImportEvidenceContext,
    path: Path,
) -> ProposalSessionReceipt:
    raw = read_required_trial_file(
        path,
        trial_dir=context.trial_dir,
        label="proposal session receipt",
    )
    try:
        return ProposalSessionReceipt.model_validate_json(raw)
    except ValueError as error:
        raise HarborImportError(
            f"proposal session receipt is invalid: {error}",
        ) from error


def _validate_required_status(
    *,
    receipt: ProposalSessionReceipt,
    required_status: ProposalSessionStatus,
) -> None:
    if required_status is ProposalSessionStatus.COMPLETED:
        if receipt.status is not ProposalSessionStatus.COMPLETED or not receipt.trial_record_permitted:
            raise HarborImportError(
                "proposal session does not permit TrialRecord import",
            )
        return
    if receipt.status is not ProposalSessionStatus.CANDIDATE_FAILURE or receipt.trial_record_permitted:
        raise HarborImportError(
            "proposal session is not a candidate failure",
        )


__all__ = ("load_proposal_import_evidence",)
