# ABOUTME: Validates exact Harbor runtime, fixed-harness, and proposal-session lineage.
# ABOUTME: Rejects any configuration or metadata that drifts from the loaded host bundle.

from __future__ import annotations

from typing import Any

from aec_bench.contracts.harness_instance import AgentBindingConfig
from aec_bench.contracts.proposal_execution.session import ProposalSessionReceipt
from aec_bench.experimentation.proposals.morph.constants import PROPOSAL_MORPH_BACKEND
from aec_bench.experimentation.proposals.session_config import LoadedProposalSessionHostInputs
from aec_bench.harness.harbor_contract import HarborTrialResult
from aec_bench.harness.harbor_importing.contracts import HarborImportError

_PROPOSAL_MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH = (
    "aec_bench.experimentation.proposals.morph.environment:ProposalMorphHarborEnvironment"
)


def validate_proposal_harbor_configuration(
    *,
    harbor_result: HarborTrialResult,
    host_inputs: LoadedProposalSessionHostInputs,
) -> None:
    """Require the exact proposal-only environment, runtime, backend, and model."""

    environment = harbor_result.config.environment
    if environment.import_path != _PROPOSAL_MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH:
        raise HarborImportError(
            "proposal import requires the proposal-only Morph environment",
        )
    runtime = environment.kwargs
    expected_runtime = (
        host_inputs.config.runtime_archive_path,
        host_inputs.config.runtime_archive_sha256,
        host_inputs.config.runtime_archive_content_sha256,
    )
    actual_runtime = (
        runtime.get("runtime_archive_path"),
        runtime.get("runtime_archive_sha256"),
        runtime.get("runtime_archive_content_sha256"),
    )
    if actual_runtime != expected_runtime or runtime.get("compute_backend") != PROPOSAL_MORPH_BACKEND:
        raise HarborImportError(
            "proposal Harbor environment does not bind the exact host runtime",
        )
    agent_configurations = tuple(
        binding.configuration
        for binding in host_inputs.bundle.fixed_harness.bindings
        if isinstance(binding.configuration, AgentBindingConfig)
    )
    if len(agent_configurations) != 1 or harbor_result.config.agent.model_name != agent_configurations[0].model:
        raise HarborImportError(
            "proposal Harbor agent does not bind the exact fixed-H0 model",
        )


def validate_proposal_session_lineage(
    *,
    receipt: ProposalSessionReceipt,
    host_inputs: LoadedProposalSessionHostInputs,
    metadata: dict[str, Any],
) -> None:
    """Require receipt execution and Harbor metadata to bind the same lineage."""

    bundle = host_inputs.bundle
    compilation = bundle.compilation
    execution = receipt.execution
    if (
        receipt.plan != bundle.session_plan
        or execution.source_task_package_sha256 != host_inputs.config.source_task_package_sha256
        or execution.runtime_task_package_sha256 != host_inputs.derived_task_manifest.content_sha256
        or execution.runtime_archive_sha256 != host_inputs.config.runtime_archive_sha256
        or execution.runtime_archive_content_sha256 != host_inputs.config.runtime_archive_content_sha256
        or execution.backend != PROPOSAL_MORPH_BACKEND
    ):
        raise HarborImportError(
            "proposal session receipt does not bind the exact bundle, task, and runtime",
        )
    expected_metadata = {
        "adapter_name": "proposal_session",
        "proposal_session_id": receipt.session_id,
        "proposal_session_receipt_sha256": receipt.content_sha256,
        "proposal_session_status": receipt.status.value,
        "trial_record_permitted": receipt.trial_record_permitted,
        "failure_code": (None if receipt.failure_code is None else receipt.failure_code.value),
        "candidate_id": compilation.candidate_ref.candidate_id,
        "proposal_graph_sha256": (compilation.proposal_graph.content_sha256),
        "compilation_sha256": compilation.content_sha256,
        "session_plan_sha256": bundle.session_plan.content_sha256,
        "reward_owner": "harbor_verifier",
    }
    if any(metadata.get(key) != value for key, value in expected_metadata.items()):
        raise HarborImportError(
            "proposal Harbor metadata does not bind the exact session lineage",
        )


__all__ = (
    "validate_proposal_harbor_configuration",
    "validate_proposal_session_lineage",
)
