# ABOUTME: Validates proposal import execution, task-review, evidence, and failure lineage.
# ABOUTME: Keeps exact joins and fail-closed terminal checks separate from persistence.

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Literal

from aec_bench.contracts.harness_instance import AgentBindingConfig
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    canonical_json_sha256,
)
from aec_bench.contracts.program_proposal.types import OptimizationSplit, ProgramCandidateKind
from aec_bench.contracts.proposal_execution.graph import MonolithicIncumbentProgram
from aec_bench.contracts.proposal_execution_types import ProposalSessionStatus
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.contracts.trial_record import ArtifactReference, TrialRecord
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.experimentation.proposals.harbor import (
    ProposalHarborDispatchInput,
    build_proposal_harbor_job_config,
)
from aec_bench.experimentation.proposals.harbor_import import ProposalHarborImportEvidence
from aec_bench.experimentation.proposals.proposal_dispatch import (
    GovernedProposalDispatchAuthorization,
)
from aec_bench.experimentation.proposals.proposal_harbor_runtime import (
    ProposalHarborExecutionReceipt,
    ProposalHarborExecutionStatus,
)
from aec_bench.experimentation.proposals.proposal_import_consumption import (
    ProposalImportConsumptionClaim,
    ProposalImportTerminalRecord,
)
from aec_bench.experimentation.proposals.proposal_trial_importing.authority import (
    resolve_unique_event_model,
)
from aec_bench.experimentation.proposals.proposal_trial_importing.contracts import (
    ProposalCandidateFailureRecord,
    ProposalTrialImportError,
    TaskReviewLineage,
)
from aec_bench.experimentation.proposals.proposal_trial_importing.persistence import (
    canonical_json,
    canonical_model_bytes,
    load_session_receipt_from_artifact,
    read_regular_file,
)
from aec_bench.experimentation.proposals.structural_corpus import (
    StructuralSplitManifest,
)
from aec_bench.harness.harbor_dispatch import HarborDispatchError
from aec_bench.ledger.immutable_artifact_store import EvidenceRepository


def sole_trial_dir(
    receipt: ProposalHarborExecutionReceipt,
) -> Path:
    """Resolve the exactly-one completed Harbor trial directory."""
    if (
        receipt.status is not ProposalHarborExecutionStatus.COMPLETED
        or not receipt.trial_record_import_permitted
        or receipt.job_dir is None
        or len(receipt.result_paths) != 1
    ):
        raise ProposalTrialImportError(
            "proposal Harbor execution is not a completed exactly-one-trial import",
        )
    result_path = PurePosixPath(receipt.result_paths[0])
    if len(result_path.parts) != 2 or result_path.name != "result.json":
        raise ProposalTrialImportError(
            "proposal Harbor execution result is not one immediate trial result",
        )
    trial_dir = Path(receipt.job_dir) / result_path.parent.as_posix()
    if not trial_dir.is_dir():
        raise ProposalTrialImportError(
            "proposal Harbor execution trial directory is missing",
        )
    return trial_dir.resolve()


def revalidate_physical_dispatch(
    authorization: GovernedProposalDispatchAuthorization,
) -> None:
    """Recompile the physical Harbor job and reject any task or runtime drift."""
    dispatch = authorization.dispatch
    try:
        task = TaskDefinition.model_validate_json(dispatch.derived_task_json)
        recorded = json.loads(dispatch.harbor_job_config_json)
        if not isinstance(recorded, dict):
            raise ValueError("recorded Harbor job is not an object")
        jobs_dir = recorded.get("jobs_dir")
        if not isinstance(jobs_dir, str) or not jobs_dir:
            raise ValueError("recorded Harbor job has no jobs root")
        candidate = ProposalHarborDispatchInput(
            host_config=dispatch.host_config,
            derived_task_path=Path(dispatch.derived_task_path),
            derived_task=task,
            derived_task_manifest=dispatch.derived_task_manifest,
            repetitions=1,
        )
        observed = build_proposal_harbor_job_config(
            dispatch=candidate,
            jobs_dir=jobs_dir,
        )
    except (HarborDispatchError, OSError, ValueError) as error:
        raise ProposalTrialImportError(
            f"authorized proposal task or runtime changed before import: {error}",
        ) from error
    if canonical_json(observed) != dispatch.harbor_job_config_json:
        raise ProposalTrialImportError(
            "revalidated proposal Harbor job differs from the authorized dispatch",
        )
    attempts = recorded.get("n_attempts")
    if type(attempts) is not int or attempts != 1:
        raise ProposalTrialImportError(
            "governed proposal import requires exactly one Harbor attempt",
        )


def resolve_task_review_lineage(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
) -> TaskReviewLineage:
    """Resolve the exact task-review sidecar and declared surface from frozen ledger evidence."""
    freeze = authorization.dispatch.bundle.compilation.proposal_freeze
    structural = resolve_unique_event_model(
        ledger=ledger,
        event=authorization.freeze_authority_event,
        model_type=StructuralSplitManifest,
        matches_expected=lambda candidate: candidate.content_sha256 == freeze.structural_split_sha256,
        label="structural split",
    )
    selected_sha256 = freeze.selected_structural_item_sha256
    if selected_sha256 is None:
        raise ProposalTrialImportError(
            "structural proposal import has no selected task-review item",
        )
    split = {
        OptimizationSplit.TRAINING: structural.train,
        OptimizationSplit.DEVELOPMENT: structural.dev,
        OptimizationSplit.STRUCTURAL_HOLDOUT: structural.holdout,
    }[freeze.split]
    structural_matches = tuple(
        item for item in split.items if canonical_json_sha256(item.model_dump(mode="json")) == selected_sha256
    )
    if len(structural_matches) != 1:
        raise ProposalTrialImportError(
            "structural proposal import has no unique selected task-review item",
        )
    selected_item = structural_matches[0]
    task_review = selected_item.snapshot.task_review
    if (
        selected_item.task_id != authorization.dispatch.task_id
        or task_review is None
        or task_review.review_sidecar_sha256 != freeze.selected_review_lineage_id
    ):
        raise ProposalTrialImportError(
            "selected structural item lacks the exact authorized task review",
        )
    return TaskReviewLineage(
        review_sidecar_sha256=task_review.review_sidecar_sha256,
        declared_surface_sha256=task_review.declared_surface_sha256,
    )


def validate_exact_import(
    *,
    authorization: GovernedProposalDispatchAuthorization,
    execution: ProposalHarborExecutionReceipt,
    evidence: ProposalHarborImportEvidence,
    record: TrialRecord,
) -> None:
    """Require the Harbor TrialRecord to match the authorized proposal execution."""
    validate_exact_evidence(
        authorization=authorization,
        evidence=evidence,
    )
    bundle = authorization.dispatch.bundle
    expected_model = fixed_harness_model(authorization)
    if (
        execution.dispatch_id != authorization.dispatch.dispatch_id
        or record.task.task_id != authorization.dispatch.task_id
        or record.task.task_revision != authorization.dispatch.task_revision
        or record.agent.adapter != "proposal_session"
        or record.agent.model != expected_model
        or record.environment.compute_backend != "morph"
        or record.outputs.agent_output is None
        or record.outputs.agent_output.status.value != "completed"
        or not record.evaluation.validity.verifier_completed
        or evidence.session_receipt.plan != bundle.session_plan
    ):
        raise ProposalTrialImportError(
            "imported TrialRecord differs from its exact authorized proposal execution",
        )


def validate_exact_evidence(
    *,
    authorization: GovernedProposalDispatchAuthorization,
    evidence: ProposalHarborImportEvidence,
) -> None:
    """Require proposal session evidence to match every authorized binding."""
    bundle = authorization.dispatch.bundle
    compilation = bundle.compilation
    if (
        evidence.candidate_id != compilation.candidate_ref.candidate_id
        or evidence.candidate_artifact_sha256 != compilation.candidate_ref.candidate_artifact_sha256
        or evidence.proposal_graph_sha256 != compilation.proposal_graph.content_sha256
        or evidence.compilation_sha256 != compilation.content_sha256
        or evidence.session_plan_sha256 != bundle.session_plan.content_sha256
        or evidence.session_receipt.plan != bundle.session_plan
        or evidence.session_receipt.execution.source_task_package_sha256
        != authorization.dispatch.source_task_package_sha256
        or evidence.session_receipt.execution.runtime_task_package_sha256
        != authorization.dispatch.derived_task_manifest.content_sha256
        or evidence.session_receipt.execution.runtime_archive_sha256 != authorization.dispatch.runtime_archive_sha256
        or evidence.session_receipt.execution.runtime_archive_content_sha256
        != authorization.dispatch.runtime_archive_content_sha256
        or evidence.session_receipt.execution.evaluation_coordinate != authorization.dispatch.evaluation_coordinate
        or evidence.session_receipt.execution.execution_schedule_sha256
        != authorization.dispatch.execution_schedule_sha256
        or evidence.session_receipt.execution.execution_assignment_sha256
        != authorization.dispatch.execution_assignment_sha256
    ):
        raise ProposalTrialImportError(
            "proposal import evidence differs from the authorized bundle",
        )


def validate_candidate_failure_lineage(
    *,
    authorization: GovernedProposalDispatchAuthorization,
    execution: ProposalHarborExecutionReceipt,
    evidence: ProposalHarborImportEvidence,
    failure_record: ProposalCandidateFailureRecord,
    consumption: ProposalImportConsumptionClaim,
    terminal: ProposalImportTerminalRecord,
    terminal_artifact: ArtifactReference,
) -> None:
    """Require one failure record to bind the exact unscored execution lineage."""
    if (
        failure_record.import_id != consumption.import_id
        or failure_record.dispatch_id != authorization.dispatch.dispatch_id
        or failure_record.dispatch_sha256 != authorization.dispatch.content_sha256
        or failure_record.harbor_execution_receipt_sha256 != execution.content_sha256
        or failure_record.candidate_id != evidence.candidate_id
        or failure_record.candidate_artifact_sha256 != evidence.candidate_artifact_sha256
        or failure_record.proposal_graph_sha256 != evidence.proposal_graph_sha256
        or failure_record.compilation_sha256 != evidence.compilation_sha256
        or failure_record.session_plan_sha256 != evidence.session_plan_sha256
        or failure_record.session_receipt != evidence.session_receipt
        or evidence.session_id != evidence.session_receipt.session_id
    ):
        raise ProposalTrialImportError(
            "candidate-failure record differs from its execution, candidate, compilation, or session lineage",
        )
    if (
        terminal.harbor_execution_receipt_sha256 != execution.content_sha256
        or terminal.dispatch_sha256 != authorization.dispatch.content_sha256
        or terminal.import_id != consumption.import_id
        or terminal.outcome != "candidate_failure"
        or terminal.terminal_artifact != terminal_artifact
        or terminal.trial_record is not None
        or terminal.authority_event_id is not None
        or terminal.authority_event_sha256 is not None
        or failure_record.trial_record_permitted
        or failure_record.scored_import_authority_permitted
        or evidence.session_receipt.trial_record_permitted
    ):
        raise ProposalTrialImportError(
            "candidate-failure terminal claims a TrialRecord or scored authority",
        )


def validate_candidate_failure_artifacts(
    *,
    authorization: GovernedProposalDispatchAuthorization,
    evidence: ProposalHarborImportEvidence,
    failure_record: ProposalCandidateFailureRecord,
    harbor_execution_receipt_path: Path,
    repository: EvidenceRepository,
) -> None:
    """Require complete immutable failure evidence and forbid scored artifacts."""
    bound_evidence = (
        evidence.session_receipt_artifact,
        evidence.cleanup_receipt_artifact,
        evidence.task_package_manifest_artifact,
        evidence.runtime_archive_artifact,
    )
    if any(artifact not in evidence.artifacts for artifact in bound_evidence):
        raise ProposalTrialImportError(
            "candidate-failure evidence omits a bound session, cleanup, task, or runtime artifact",
        )

    preserved = failure_record.artifacts
    for source in evidence.artifacts:
        require_preserved_artifact(
            artifacts=preserved,
            kind=source.kind,
            sha256=source.sha256,
            media_type=source.media_type,
            label=f"candidate-failure evidence {source.kind}",
        )
    preserved_session = require_preserved_artifact(
        artifacts=preserved,
        kind=evidence.session_receipt_artifact.kind,
        sha256=evidence.session_receipt_artifact.sha256,
        media_type=evidence.session_receipt_artifact.media_type,
        label="candidate-failure session receipt",
    )
    if (
        load_session_receipt_from_artifact(
            preserved_session,
            repository=repository,
        )
        != evidence.session_receipt
    ):
        raise ProposalTrialImportError(
            "preserved candidate-failure session receipt differs from its exact evidence",
        )
    require_preserved_artifact(
        artifacts=preserved,
        kind=evidence.cleanup_receipt_artifact.kind,
        sha256=evidence.cleanup_receipt_artifact.sha256,
        media_type=evidence.cleanup_receipt_artifact.media_type,
        label="candidate-failure cleanup receipt",
    )

    bundle = authorization.dispatch.bundle
    compilation = bundle.compilation
    freeze = compilation.proposal_freeze
    expected_models: tuple[tuple[str, FrozenStrictModel], ...] = (
        ("candidate-manifest", freeze.candidate_manifest),
        ("proposal-decomposition-graph", compilation.proposal_graph),
        ("proposal-freeze", freeze),
        ("proposal-compilation", compilation),
        ("proposal-session-plan", bundle.session_plan),
        ("proposal-run-session-bundle", bundle),
        ("proposal-fixed-harness", bundle.fixed_harness),
        ("governed-proposal-dispatch", authorization.dispatch),
    )
    for kind, model in expected_models:
        require_preserved_artifact(
            artifacts=preserved,
            kind=kind,
            sha256=hashlib.sha256(canonical_model_bytes(model)).hexdigest(),
            media_type="application/json",
            label=kind,
        )

    execution_bytes = read_regular_file(
        harbor_execution_receipt_path,
        label="proposal Harbor execution receipt",
    )
    require_preserved_artifact(
        artifacts=preserved,
        kind="proposal_harbor_execution_receipt",
        sha256=hashlib.sha256(execution_bytes).hexdigest(),
        media_type="application/json",
        label="proposal Harbor execution receipt",
    )
    forbidden = {
        "proposal-final-output",
        "proposal-trial-import-receipt",
        "proposal-trial-record",
        "proposal-verifier-details",
        "proposal-verifier-evidence",
        "proposal-verifier-reward",
    }
    claimed = sorted({artifact.kind for artifact in preserved} & forbidden)
    if claimed:
        raise ProposalTrialImportError(
            "candidate-failure record claims TrialRecord or scored import artifacts: " + ", ".join(claimed),
        )


def require_preserved_artifact(
    *,
    artifacts: tuple[ArtifactReference, ...],
    kind: str,
    sha256: str,
    media_type: str,
    label: str,
) -> ArtifactReference:
    """Resolve exactly one preserved artifact by its complete identity."""
    matches = tuple(
        artifact
        for artifact in artifacts
        if artifact.kind == kind and artifact.sha256 == sha256 and artifact.media_type == media_type
    )
    if len(matches) != 1:
        raise ProposalTrialImportError(
            f"candidate-failure preservation does not contain exactly one {label}",
        )
    return matches[0]


def proposal_terminal_status(
    trial_dir: Path,
) -> ProposalSessionStatus:
    """Read the typed proposal terminal status from Harbor result metadata."""
    try:
        payload = json.loads((trial_dir / "result.json").read_bytes())
        metadata = payload["agent_result"]["metadata"]
        raw_status = metadata["proposal_session_status"]
        return ProposalSessionStatus(raw_status)
    except (
        KeyError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        raise ProposalTrialImportError(
            "proposal Harbor result lacks a typed terminal session status",
        ) from error


def program_generator_sha256(
    authorization: GovernedProposalDispatchAuthorization,
) -> str:
    """Resolve the exact proposal or incumbent program-generator identity."""
    candidate = authorization.dispatch.candidate_ref
    freeze = authorization.dispatch.bundle.compilation.proposal_freeze
    if candidate.kind is ProgramCandidateKind.PROPOSAL:
        return freeze.candidate_manifest.proposal_policy_sha256
    graph = authorization.dispatch.bundle.compilation.proposal_graph
    if not isinstance(graph, MonolithicIncumbentProgram):
        raise ProposalTrialImportError(
            "incumbent TrialRecord import requires an exact monolithic incumbent policy",
        )
    if (
        freeze.incumbent_candidate != candidate
        or graph.candidate_id != candidate.candidate_id
        or graph.content_sha256 != candidate.candidate_artifact_sha256
    ):
        raise ProposalTrialImportError(
            "incumbent TrialRecord import differs from the exact frozen incumbent",
        )
    return graph.incumbent_policy_sha256


def meta_split(
    split: OptimizationSplit,
) -> Literal["discovery", "repair_gate", "calibration", "holdout"]:
    """Map proposal optimization splits to the closed TrialRecord vocabulary."""
    if split is OptimizationSplit.CALIBRATION:
        return "calibration"
    if split is OptimizationSplit.TRAINING:
        return "discovery"
    if split is OptimizationSplit.DEVELOPMENT:
        return "repair_gate"
    return "holdout"


def fixed_harness_model(
    authorization: GovernedProposalDispatchAuthorization,
) -> str:
    """Resolve the sole agent model bound by fixed H0."""
    configurations = tuple(
        binding.configuration
        for binding in authorization.dispatch.bundle.fixed_harness.bindings
        if isinstance(binding.configuration, AgentBindingConfig)
    )
    if len(configurations) != 1:
        raise ProposalTrialImportError(
            "proposal fixed H0 does not bind exactly one agent model",
        )
    return configurations[0].model


def bound_tool_versions(
    *,
    record: TrialRecord,
    authorization: GovernedProposalDispatchAuthorization,
) -> dict[str, str]:
    """Merge exact kernel and proposal package identities into environment versions."""
    versions = dict(record.environment.tool_versions or {})
    bundle = authorization.dispatch.bundle
    expected = {
        **{
            f"kernel:{binding.capability_ref.capability_id}": binding.capability_ref.version
            for binding in bundle.fixed_harness.bindings
        },
        "source-task-package": (f"sha256:{authorization.dispatch.source_task_package_sha256}"),
        "runtime-task-package": (f"sha256:{authorization.dispatch.derived_task_manifest.content_sha256}"),
        "proposal-runtime-archive": (
            f"{authorization.dispatch.runtime_archive_content_sha256}"
            f"@sha256:{authorization.dispatch.runtime_archive_sha256}"
        ),
        "proposal-session-plan": (f"sha256:{bundle.session_plan.content_sha256}"),
        "proposal-compilation": (f"sha256:{bundle.compilation.content_sha256}"),
    }
    for name, value in expected.items():
        existing = versions.get(name)
        if existing is not None and existing != value:
            raise ProposalTrialImportError(
                f"Harbor environment version conflicts with proposal runtime: {name}",
            )
        versions[name] = value
    return dict(sorted(versions.items()))
