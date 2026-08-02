# ABOUTME: Imports verified wastewater pump-station world evidence from Harbor trials.
# ABOUTME: Binds one session window and its immutable artifacts to a TrialRecord.

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

from aec_bench.contracts.evaluation_result import (
    EvaluationResult,
    StewardshipEvaluation,
)
from aec_bench.contracts.trial_record import (
    ArtifactReference,
    TemporalWorldExecutionRecord,
    TemporalWorldTrialProvenance,
    WorldExecutionRecord,
    WorldTemporalEvidenceExecution,
    WorldTemporalEvidenceProvenance,
    WorldTrialProvenance,
)
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionRequest,
    WorldSessionResult,
)
from aec_bench.evaluation.stewardship import (
    evaluate_pump_station_stewardship_run,
)
from aec_bench.harness.harbor_importing.artifact_io import (
    artifact_reference,
    read_regular_trial_tree,
    read_required_trial_file,
    required_trial_directory,
)
from aec_bench.harness.harbor_importing.contracts import (
    HarborImportError,
    ImportEvidenceContext,
    ImportEvidenceIntent,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_evaluation import (
    shared_stewardship_evaluation,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_harbor import (
    PUMP_STATION_ASW_8_HARBOR_EXPORT_VERSION,
    load_asw_8_harbor_bridge,
    verify_asw_8_harbor_session,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run import (
    PumpStationCoupledRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_verifier import (
    verify_pump_station_harbor_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    REFERENCE_PROFILE_V2,
    load_reference_package,
)

_RUN_DIRECTORY_NAME = "world-session"
_REQUEST_NAME = "world-session-request.json"
_RESULT_NAME = "world-session-result.json"
_INVENTORY_NAME = "artifact-inventory.json"
_VERIFICATION_NAME = "verification-report.json"
_TEMPORAL_VERIFICATION_NAME = "temporal-verification-report.json"


@dataclass(frozen=True)
class StewardshipHarborImportEvidence:
    """Verified world evidence projected into the generic import contract."""

    world_execution: WorldExecutionRecord
    world_provenance: WorldTrialProvenance
    artifacts: tuple[ArtifactReference, ...]
    package_content_id: str
    evaluation: StewardshipEvaluation

    @property
    def execution_kind(self) -> str:
        """Return the execution kind used to select this extension."""

        return PUMP_STATION_HARBOR_EXECUTION_KIND

    @property
    def adapter_name(self) -> str:
        """Keep the runtime adapter distinct from the world execution kind."""

        return "tool_loop"

    def sanitize_agent_configuration(
        self,
        configuration: dict[str, Any],
    ) -> dict[str, Any]:
        """Remove host-only bridge data and retain verified portable identity."""

        portable = dict(configuration)
        portable.pop("world_session", None)
        portable.pop("extra_env", None)
        portable["execution_kind"] = self.execution_kind
        portable["world_session_evidence"] = {
            "task_world_id": self.world_execution.task_world_id,
            "session_id": self.world_execution.session_id,
            "package_content_id": self.package_content_id,
            "transition_count": self.world_execution.transition_count,
        }
        return portable

    def augment_evaluation(
        self,
        evaluation: EvaluationResult,
    ) -> EvaluationResult:
        """Attach evaluation-owned metrics and enforce hard-gate reward."""

        payload = evaluation.model_dump(mode="python")
        payload["reward"] = evaluation.reward if self.evaluation.valid else 0.0
        payload["stewardship"] = self.evaluation
        return EvaluationResult.model_validate(payload)


class StewardshipImportEvidenceExtension:
    """Load one verified stewardship session from an allowlisted Harbor trial."""

    @property
    def execution_kind(self) -> str:
        """Return the exact execution kind handled by this extension."""

        return PUMP_STATION_HARBOR_EXECUTION_KIND

    def load(
        self,
        *,
        context: ImportEvidenceContext,
        intent: ImportEvidenceIntent,
    ) -> StewardshipHarborImportEvidence:
        """Validate and project the immutable world-session evidence."""

        if intent is not ImportEvidenceIntent.TRIAL_RECORD:
            raise HarborImportError("stewardship world evidence supports TrialRecord import only")
        return _load_stewardship_evidence(context)


def _load_stewardship_evidence(
    context: ImportEvidenceContext,
) -> StewardshipHarborImportEvidence:
    export_manifest_path = context.task_instance_dir / "world-session-export.json"
    try:
        export_manifest = json.loads(export_manifest_path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise HarborImportError(f"stewardship export manifest is invalid: {error}") from error
    if (
        isinstance(export_manifest, dict)
        and export_manifest.get("schema_version") == PUMP_STATION_ASW_8_HARBOR_EXPORT_VERSION
    ):
        return _load_asw_8_stewardship_evidence(context)
    run_dir = _world_run_directory(context)
    read_regular_trial_tree(
        run_dir,
        trial_dir=context.trial_dir,
        label="stewardship world-session evidence",
    )
    try:
        bridge = load_pump_station_harbor_bridge(context.task_instance_dir / "environment")
        verified = verify_pump_station_harbor_run(
            run_dir=run_dir,
            export_manifest_path=bridge.export_manifest_path,
            package_dir=bridge.package_root,
            verifier_runtime_path=bridge.verifier_runtime_path,
        )
    except (OSError, TypeError, ValueError) as error:
        raise HarborImportError(f"stewardship world-session verification failed: {error}") from error
    if verified.get("valid") is not True:
        raise HarborImportError("stewardship world-session is not valid")

    request = WorldSessionRequest.model_validate(
        _read_trial_json(
            run_dir / _REQUEST_NAME,
            context=context,
            label="world-session request",
        )
    )
    result = WorldSessionResult.model_validate(
        _read_trial_json(
            run_dir / _RESULT_NAME,
            context=context,
            label="world-session result",
        )
    )
    inventory = _read_trial_json(
        run_dir / _INVENTORY_NAME,
        context=context,
        label="world-session artifact inventory",
    )
    start_snapshot = StewardshipStateSnapshotRef.model_validate(inventory.get("start_snapshot"))
    end_snapshot = StewardshipStateSnapshotRef.model_validate(inventory.get("end_snapshot"))
    transition_count = _required_non_negative_int(
        inventory.get("transition_count"),
        "world-session transition count",
    )
    model = _verified_model(context)
    artifacts, references = _artifact_evidence(
        context=context,
        run_dir=run_dir,
        inventory=inventory,
        bridge=bridge,
    )
    evaluation = evaluate_pump_station_stewardship_run(
        run_dir=run_dir / "world-run",
        package_root=bridge.package_root,
        imported_artifact_sha256=tuple(sorted({artifact.sha256 for artifact in artifacts})),
    )
    execution_fields = {
        "execution_kind": PUMP_STATION_HARBOR_EXECUTION_KIND,
        "session_id": request.session_id,
        "task_world_id": result.task_world_id,
        "agent_tenure_id": request.agent_tenure_id,
        "adapter": "tool_loop",
        "resolved_model": model,
        "status": "completed",
        "start_snapshot": start_snapshot,
        "end_snapshot": end_snapshot,
        "transition_count": transition_count,
        "tool_names": bridge.allowed_tools,
    }
    provenance_fields = {
        "world_session_request": references[_REQUEST_NAME],
        "world_session_result": references[_RESULT_NAME],
        "artifact_inventory": references[_INVENTORY_NAME],
        "export_manifest": references["export_manifest"],
        "package_manifest": references["package_manifest"],
        "verification_report": references[_VERIFICATION_NAME],
    }
    if bridge.temporal_evidence:
        temporal_execution, temporal_provenance = _temporal_trial_evidence(
            inventory=inventory,
            references=references,
        )
        execution: WorldExecutionRecord = TemporalWorldExecutionRecord.model_validate(
            {**execution_fields, "temporal_evidence": temporal_execution}
        )
        provenance: WorldTrialProvenance = TemporalWorldTrialProvenance.model_validate(
            {**provenance_fields, "temporal_evidence": temporal_provenance}
        )
    else:
        execution = WorldExecutionRecord.model_validate(execution_fields)
        provenance = WorldTrialProvenance.model_validate(provenance_fields)
    return StewardshipHarborImportEvidence(
        world_execution=execution,
        world_provenance=provenance,
        artifacts=artifacts,
        package_content_id=bridge.package.package_content_id,
        evaluation=evaluation,
    )


def _load_asw_8_stewardship_evidence(
    context: ImportEvidenceContext,
) -> StewardshipHarborImportEvidence:
    """Load one ASW-8 Harbor v2 session through independent replay."""
    run_dir = _world_run_directory(context)
    read_regular_trial_tree(
        run_dir,
        trial_dir=context.trial_dir,
        label="ASW-8 world-session evidence",
    )
    try:
        bridge = load_asw_8_harbor_bridge(context.task_instance_dir / "environment")
        verify_asw_8_harbor_session(
            run_dir=run_dir,
            export_manifest=bridge.export_manifest_path,
            package_dir=bridge.package_root,
            reference_system_dir=bridge.reference_system_root,
        )
    except (OSError, TypeError, ValueError) as error:
        raise HarborImportError(f"ASW-8 world-session verification failed: {error}") from error

    request = _read_trial_json(
        run_dir / _REQUEST_NAME,
        context=context,
        label="ASW-8 world-session request",
    )
    result = _read_trial_json(
        run_dir / _RESULT_NAME,
        context=context,
        label="ASW-8 world-session result",
    )
    inventory = _read_trial_json(
        run_dir / _INVENTORY_NAME,
        context=context,
        label="ASW-8 world-session artifact inventory",
    )
    start_snapshot = StewardshipStateSnapshotRef.model_validate(
        _mapping(request.get("start_snapshot"), "ASW-8 start snapshot")
    )
    end_snapshot = StewardshipStateSnapshotRef.model_validate(
        _mapping(result.get("end_snapshot"), "ASW-8 end snapshot")
    )
    transition_count = _required_non_negative_int(
        result.get("transition_count"),
        "ASW-8 transition count",
    )
    if end_snapshot.sequence - start_snapshot.sequence != transition_count:
        raise HarborImportError("ASW-8 transition count differs from its snapshots")
    artifacts, references = _artifact_evidence(
        context=context,
        run_dir=run_dir,
        inventory=inventory,
        bridge=bridge,
    )
    run = PumpStationCoupledRunRepository(run_dir / "world-run").open()
    evaluation = shared_stewardship_evaluation(
        run,
        imported_artifact_sha256=tuple(sorted({artifact.sha256 for artifact in artifacts})),
    )
    model = _verified_model(context)
    temporal_execution, temporal_provenance = _asw_8_temporal_trial_evidence(
        run_dir=run_dir,
        context=context,
        references=references,
    )
    execution = TemporalWorldExecutionRecord(
        execution_kind=PUMP_STATION_HARBOR_EXECUTION_KIND,
        session_id=str(request.get("session_id", "")),
        task_world_id=bridge.task_world_id,
        agent_tenure_id="asw-8-reference-controller-tenure",
        adapter="tool_loop",
        resolved_model=model,
        status="completed",
        start_snapshot=start_snapshot,
        end_snapshot=end_snapshot,
        transition_count=transition_count,
        tool_names=tuple(str(value) for value in result.get("tool_names", ())),
        temporal_evidence=temporal_execution,
    )
    provenance = TemporalWorldTrialProvenance(
        world_session_request=references[_REQUEST_NAME],
        world_session_result=references[_RESULT_NAME],
        artifact_inventory=references[_INVENTORY_NAME],
        export_manifest=references["export_manifest"],
        package_manifest=references["package_manifest"],
        verification_report=references[_VERIFICATION_NAME],
        temporal_evidence=temporal_provenance,
    )
    package = load_reference_package(
        bridge.package_root,
        profile_id=REFERENCE_PROFILE_V2,
    )
    return StewardshipHarborImportEvidence(
        world_execution=execution,
        world_provenance=provenance,
        artifacts=artifacts,
        package_content_id=package.package_content_id,
        evaluation=evaluation,
    )


def _world_run_directory(context: ImportEvidenceContext) -> Path:
    candidates = (
        context.trial_dir / "agent" / _RUN_DIRECTORY_NAME,
        context.trial_dir / "artifacts" / "agent" / _RUN_DIRECTORY_NAME,
    )
    existing = [candidate for candidate in candidates if candidate.exists()]
    if len(existing) != 1:
        raise HarborImportError("Harbor trial must contain exactly one stewardship world-session directory")
    return required_trial_directory(
        existing[0],
        trial_dir=context.trial_dir,
        label="stewardship world-session directory",
    )


def _verified_model(context: ImportEvidenceContext) -> str:
    configured = context.harbor_result.config.agent.model_name
    declared = context.harbor_result.agent_result.metadata.get("model")
    if declared is not None and declared != configured:
        raise HarborImportError("stewardship controller identity differs from the Harbor agent model")
    return configured


def _artifact_evidence(
    *,
    context: ImportEvidenceContext,
    run_dir: Path,
    inventory: dict[str, Any],
    bridge: Any,
) -> tuple[tuple[ArtifactReference, ...], dict[str, ArtifactReference]]:
    raw_entries = inventory.get("artifacts")
    if not isinstance(raw_entries, list):
        raise HarborImportError("world-session artifact inventory must be a list")
    known_kinds = {
        _REQUEST_NAME: "world-session-request",
        _RESULT_NAME: "world-session-result",
        _VERIFICATION_NAME: "world-session-verification",
        _TEMPORAL_VERIFICATION_NAME: "world-temporal-evidence-verification",
    }
    references: dict[str, ArtifactReference] = {}
    artifacts: list[ArtifactReference] = []
    seen_paths: set[str] = set()
    for raw_entry in raw_entries:
        entry = _mapping(raw_entry, "world-session artifact entry")
        relative = _confined_relative_path(entry.get("path"))
        if relative in seen_paths:
            raise HarborImportError(f"world-session artifact is listed twice: {relative}")
        seen_paths.add(relative)
        path = run_dir.joinpath(*PurePosixPath(relative).parts)
        reference = artifact_reference(
            kind=known_kinds.get(relative, "world-session-artifact"),
            path=path,
            repo_root=context.repo_root,
        )
        expected_sha256 = entry.get("sha256")
        expected_size = entry.get("size_bytes")
        if reference.sha256 != expected_sha256 or path.stat().st_size != expected_size:
            raise HarborImportError(f"world-session artifact identity differs: {relative}")
        artifacts.append(reference)
        references[relative] = reference
    for required_name in (_REQUEST_NAME, _RESULT_NAME, _VERIFICATION_NAME):
        if required_name not in references:
            raise HarborImportError(f"world-session artifact inventory lacks {required_name}")
    if bridge.temporal_evidence and _TEMPORAL_VERIFICATION_NAME not in references:
        raise HarborImportError("world-session artifact inventory lacks temporal verification")

    inventory_reference = artifact_reference(
        kind="world-session-inventory",
        path=run_dir / _INVENTORY_NAME,
        repo_root=context.repo_root,
    )
    export_reference = artifact_reference(
        kind="world-export-manifest",
        path=bridge.export_manifest_path,
        repo_root=context.repo_root,
    )
    package_reference = artifact_reference(
        kind="world-package-manifest",
        path=bridge.package_root / "promotion-manifest.json",
        repo_root=context.repo_root,
    )
    runtime_reference = artifact_reference(
        kind="world-verifier-runtime",
        path=bridge.verifier_runtime_path,
        repo_root=context.repo_root,
    )
    artifacts.extend(
        (
            inventory_reference,
            export_reference,
            package_reference,
            runtime_reference,
        )
    )
    references[_INVENTORY_NAME] = inventory_reference
    references["export_manifest"] = export_reference
    references["package_manifest"] = package_reference
    return tuple(artifacts), references


def _temporal_trial_evidence(
    *,
    inventory: dict[str, Any],
    references: dict[str, ArtifactReference],
) -> tuple[WorldTemporalEvidenceExecution, WorldTemporalEvidenceProvenance]:
    temporal = _mapping(
        inventory.get("temporal_evidence"),
        "temporal evidence inventory",
    )
    execution = WorldTemporalEvidenceExecution.model_validate(temporal)
    fixed_paths = {
        "capability": "world-run/temporal-evidence/capability.json",
        "corpus_manifest": "world-run/temporal-evidence/corpus/manifest.json",
        "lineage_manifest": "world-run/temporal-evidence/corpus/lineage.json",
        "availability_schedule": "world-run/temporal-evidence/corpus/availability.json",
        "retrieval_policy": "world-run/temporal-evidence/policies/retrieval.json",
        "access_policy": "world-run/temporal-evidence/policies/access.json",
        "branch_policy": "world-run/temporal-evidence/policies/branch.json",
        "cost_policy": "world-run/temporal-evidence/policies/cost.json",
    }
    missing = tuple(path for path in fixed_paths.values() if path not in references)
    if missing:
        raise HarborImportError("temporal evidence inventory lacks required authority artifacts")
    fixed_references = {name: references[path] for name, path in fixed_paths.items()}
    excluded = {*fixed_paths.values(), _TEMPORAL_VERIFICATION_NAME}
    ledger_artifacts = tuple(
        references[path]
        for path in sorted(references)
        if path.startswith("world-run/temporal-evidence/") and path not in excluded
    )
    provenance = WorldTemporalEvidenceProvenance(
        **fixed_references,
        verification_report=references[_TEMPORAL_VERIFICATION_NAME],
        ledger_artifacts=ledger_artifacts,
    )
    return execution, provenance


def _asw_8_temporal_trial_evidence(
    *,
    run_dir: Path,
    context: ImportEvidenceContext,
    references: dict[str, ArtifactReference],
) -> tuple[WorldTemporalEvidenceExecution, WorldTemporalEvidenceProvenance]:
    """Build shared temporal records from the ASW-8 v2 artifact layout."""
    fixed_paths = {
        "capability": "temporal-evidence/capability.json",
        "corpus_manifest": "temporal-evidence/corpus-manifest.json",
        "lineage_manifest": "temporal-evidence/lineage.json",
        "availability_schedule": "temporal-evidence/availability.json",
        "retrieval_policy": "temporal-evidence/retrieval-policy.json",
        "access_policy": "temporal-evidence/access-policy.json",
        "branch_policy": "temporal-evidence/branch-policy.json",
        "cost_policy": "temporal-evidence/cost-policy.json",
    }
    missing = tuple(path for path in fixed_paths.values() if path not in references)
    if missing:
        raise HarborImportError("ASW-8 temporal evidence lacks required authority artifacts")
    capability = _read_trial_json(
        run_dir / fixed_paths["capability"],
        context=context,
        label="ASW-8 temporal capability",
    )
    temporal_verification = _read_trial_json(
        run_dir / _TEMPORAL_VERIFICATION_NAME,
        context=context,
        label="ASW-8 temporal verification",
    )
    ledger_path = "temporal-evidence/access-ledger.json"
    if ledger_path not in references:
        raise HarborImportError("ASW-8 temporal evidence lacks its access ledger")
    try:
        access_rows = json.loads(
            read_required_trial_file(
                run_dir / ledger_path,
                trial_dir=context.trial_dir,
                label="ASW-8 temporal access ledger",
            )
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HarborImportError("ASW-8 temporal access ledger is invalid") from error
    if not isinstance(access_rows, list):
        raise HarborImportError("ASW-8 temporal access ledger must be a list")
    access_count = _required_non_negative_int(
        temporal_verification.get("access_count"),
        "ASW-8 temporal access count",
    )
    if access_count != len(access_rows):
        raise HarborImportError("ASW-8 temporal access count differs from its ledger")
    execution = WorldTemporalEvidenceExecution(
        profile="deterministic_snapshot",
        capability_id=str(capability.get("content_sha256", "")),
        corpus_snapshot_id=str(capability.get("corpus_snapshot_id", "")),
        retrieval_policy_id=str(capability.get("retrieval_policy_id", "")),
        access_policy_id=str(capability.get("access_policy_id", "")),
        availability_schedule_id=str(capability.get("availability_schedule_id", "")),
        branch_namespace_policy_id=str(capability.get("branch_namespace_policy_id", "")),
        cost_policy_id=str(capability.get("simulated_cost_policy_id", "")),
        access_count=access_count,
        reliance_count=sum(isinstance(row, list) and bool(row) and row[0] == "fetch_evidence" for row in access_rows),
        carrier_count=0,
        verification_report_id=references[_TEMPORAL_VERIFICATION_NAME].sha256,
    )
    provenance = WorldTemporalEvidenceProvenance(
        **{name: references[path] for name, path in fixed_paths.items()},
        verification_report=references[_TEMPORAL_VERIFICATION_NAME],
        ledger_artifacts=(references[ledger_path],),
    )
    return execution, provenance


def _read_trial_json(
    path: Path,
    *,
    context: ImportEvidenceContext,
    label: str,
) -> dict[str, Any]:
    raw = read_required_trial_file(
        path,
        trial_dir=context.trial_dir,
        label=label,
    )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HarborImportError(f"{label} is not valid JSON") from error
    if not isinstance(payload, dict):
        raise HarborImportError(f"{label} must be a JSON object")
    return cast(dict[str, Any], payload)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise HarborImportError(f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _confined_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise HarborImportError("world-session artifact path must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise HarborImportError(f"world-session artifact path is not confined: {value}")
    return value


def _required_non_negative_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise HarborImportError(f"{label} must be a non-negative integer")
    return value


STEWARDSHIP_IMPORT_EVIDENCE_EXTENSION = StewardshipImportEvidenceExtension()


__all__ = (
    "STEWARDSHIP_IMPORT_EVIDENCE_EXTENSION",
    "StewardshipHarborImportEvidence",
    "StewardshipImportEvidenceExtension",
)
