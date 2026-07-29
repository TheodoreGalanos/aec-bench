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
    WorldExecutionRecord,
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
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    PUMP_STATION_HARBOR_EXECUTION_KIND,
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_verifier import (
    verify_pump_station_harbor_run,
)

_RUN_DIRECTORY_NAME = "world-session"
_REQUEST_NAME = "world-session-request.json"
_RESULT_NAME = "world-session-result.json"
_INVENTORY_NAME = "artifact-inventory.json"
_VERIFICATION_NAME = "verification-report.json"


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
    execution = WorldExecutionRecord(
        execution_kind=PUMP_STATION_HARBOR_EXECUTION_KIND,
        session_id=request.session_id,
        task_world_id=result.task_world_id,
        agent_tenure_id=request.agent_tenure_id,
        adapter="tool_loop",
        resolved_model=model,
        status="completed",
        start_snapshot=start_snapshot,
        end_snapshot=end_snapshot,
        transition_count=transition_count,
        tool_names=bridge.allowed_tools,
    )
    provenance = WorldTrialProvenance(
        world_session_request=references[_REQUEST_NAME],
        world_session_result=references[_RESULT_NAME],
        artifact_inventory=references[_INVENTORY_NAME],
        export_manifest=references["export_manifest"],
        package_manifest=references["package_manifest"],
        verification_report=references[_VERIFICATION_NAME],
    )
    return StewardshipHarborImportEvidence(
        world_execution=execution,
        world_provenance=provenance,
        artifacts=artifacts,
        package_content_id=bridge.package.package_content_id,
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
