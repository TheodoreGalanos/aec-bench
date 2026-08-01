# ABOUTME: Runs and verifies the pump-station closeout review through Harbor.
# ABOUTME: Preserves source, case, review, token, and independent verifier evidence.

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from aec_bench.adapters.base import AdapterResult
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.harbor_exporting.stable_io import (
    directory_sha256,
    file_sha256,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    PUMP_STATION_HARBOR_EXPORT_SCHEMA_VERSION,
    PUMP_STATION_REVIEW_HARBOR_BRIDGE_MODE,
    PUMP_STATION_REVIEW_HARBOR_EXECUTION_KIND,
    PumpStationHarborBridge,
    is_pump_station_harbor_inventory_artifact,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    PUMP_STATION_REFERENCE_CONTROLLER_ID,
    _execute_rich_work_after_handover,
    _execute_rich_work_until_handover,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review import (
    PUMP_STATION_REVIEW_ISSUE_VERSION_V1,
    PUMP_STATION_REVIEW_PACK_POLICY_V1,
    PUMP_STATION_REVIEW_VISIBILITY_POLICY_V1,
    PumpStationReviewerRole,
    PumpStationReviewIssueClass,
    PumpStationReviewPreparationRequest,
    PumpStationReviewPublicCase,
    PumpStationReviewSubmission,
    PumpStationReviewSubmissionReceipt,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_agent import (
    PumpStationReviewAgentAuthority,
    build_pump_station_review_adapter_request,
    calculate_pump_station_review_spend_microusd,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_control import (
    PUMP_STATION_REVIEW_TASK_ID,
    PumpStationReviewControl,
    PumpStationReviewControlRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_repository import (
    PumpStationReviewCaseRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_session import (
    PUMP_STATION_REVIEW_TOOL_NAMES,
    PumpStationReviewObservation,
    PumpStationReviewSession,
    PumpStationReviewSessionFactory,
    PumpStationReviewSessionOpenMode,
    PumpStationReviewSessionRequest,
    build_reference_review_submission,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_verifier import (
    PumpStationReviewVerificationReport,
    verify_pump_station_review,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    create_structured_handover,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)
from aec_bench.trajectory.writer import TrajectoryWriter

PUMP_STATION_REVIEW_HARBOR_RUN_SCHEMA_VERSION = "aecbench.pump-station-review-harbor-run.v1"


@dataclass(frozen=True, slots=True)
class CompletedPumpStationReviewSession:
    """Complete provider-free closeout review and independent result."""

    public_case: PumpStationReviewPublicCase
    observation: PumpStationReviewObservation
    submission: PumpStationReviewSubmission
    receipt: PumpStationReviewSubmissionReceipt
    verification: PumpStationReviewVerificationReport
    output_dir: Path


@dataclass(frozen=True, slots=True)
class CompletedPumpStationReviewModelSession:
    """Model review, provider evidence, and independent result when present."""

    public_case: PumpStationReviewPublicCase
    observation: PumpStationReviewObservation
    submission: PumpStationReviewSubmission | None
    receipt: PumpStationReviewSubmissionReceipt | None
    verification: PumpStationReviewVerificationReport | None
    adapter_result: AdapterResult
    authority_valid: bool
    agent_result: dict[str, Any]
    output_dir: Path


def _safe_identity(value: str) -> str:
    selected = value.strip()
    if not selected:
        raise ValueError("pump-station review session identity is required")
    return hashlib.sha256(selected.encode("utf-8")).hexdigest()[:20]


def _source_request(identity: str) -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id=f"source-session-{identity}",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=f"source-tenure-{identity}-1",
        run_id=f"source-run-{identity}",
        episode_id=f"source-episode-{identity}",
        world_branch_id=f"source-branch-{identity}",
    )


def _complete_source_history(
    *,
    bridge: PumpStationHarborBridge,
    source_root: Path,
    identity: str,
) -> tuple[WorldSessionRequest, PumpStationWorldSession]:
    start_request = _source_request(identity)
    factory = PumpStationWorldSessionFactory(
        source_root,
        package_root=bridge.package_root,
        evidence_health=True,
    )
    first = factory.open(start_request)
    suspended_snapshot = _execute_rich_work_until_handover(first)
    resume_request = WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id=f"source-session-{identity}-2",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=f"source-tenure-{identity}-2",
        run_id=start_request.run_id,
        episode_id=start_request.episode_id,
        world_branch_id=start_request.world_branch_id,
        start_snapshot=suspended_snapshot,
    )
    second = factory.open(resume_request)
    second.install_structured_handover(
        create_structured_handover(
            second.actor_view,
            from_tenure_id=start_request.agent_tenure_id,
            history=first.actor_history,
            maximum_history_entries=32,
        )
    )
    _execute_rich_work_after_handover(second)
    verification = second.verify()
    if not verification.valid:
        raise ValueError("review source history did not verify")
    return resume_request, second


def _prepare_review_session(
    *,
    bridge: PumpStationHarborBridge,
    destination: Path,
    identity: str,
) -> tuple[
    Path,
    Path,
    PumpStationReviewPublicCase,
    PumpStationReviewObservation,
    PumpStationReviewSession,
]:
    source_root = destination / "source-world"
    review_root = destination / "review-cases"
    source_request, source_session = _complete_source_history(
        bridge=bridge,
        source_root=source_root,
        identity=identity,
    )
    snapshot = source_session.run.snapshot()
    preparation = PumpStationReviewPreparationRequest(
        request_id=f"prepare-review-{identity}",
        source_snapshot=snapshot,
        asset_id=pump_station_model_from_package(bridge.package).asset_id,
        reviewed_component_id="pump-a",
        maintenance_case_id="work-order-pump-a",
        pack_policy=PUMP_STATION_REVIEW_PACK_POLICY_V1,
        issue_class=(PumpStationReviewIssueClass.WRONG_COMPONENT_EVIDENCE_CITATION),
        issue_version=PUMP_STATION_REVIEW_ISSUE_VERSION_V1,
        target_record_id="closeout-record-pump-a",
        cited_component_id="pump-b",
        reviewer_role=PumpStationReviewerRole.ASSET_ENGINEER,
        visibility_policy=PUMP_STATION_REVIEW_VISIBILITY_POLICY_V1,
    )
    control = PumpStationReviewControl(
        source_run_root=source_root,
        review_repository_root=review_root,
        authorised_principal_ids=("harbor-review-control",),
        package_root=bridge.package_root,
    )
    prepared = control.execute(
        PumpStationReviewControlRequest(
            request_id=preparation.request_id,
            operation="prepare_case",
            task_review_id=PUMP_STATION_REVIEW_TASK_ID,
            authority_id="harbor-review-control",
            preparation_request=preparation,
        )
    )
    session_request = PumpStationReviewSessionRequest(
        open_mode=PumpStationReviewSessionOpenMode.OPEN,
        session_id=f"review-session-{identity}",
        case_id=prepared.public_case.case_id,
        public_case_content_sha256=prepared.public_case.content_sha256,
        reviewer_tenure_id=f"review-tenure-{identity}",
    )
    session = PumpStationReviewSessionFactory(review_root).open(session_request)
    observation = session.observe()
    _write_json(
        destination / "source-world-session-request.json",
        source_request.model_dump(mode="json"),
    )
    _write_json(
        destination / "source-world-session-result.json",
        source_session.result.model_dump(mode="json"),
    )
    _write_json(
        destination / "source-verification-report.json",
        asdict(source_session.verify()),
    )
    _write_json(
        destination / "review-session-request.json",
        session_request.model_dump(mode="json"),
    )
    _write_json(
        destination / "review-observation.json",
        observation.model_dump(mode="json"),
    )
    return (
        source_root,
        review_root,
        prepared.public_case,
        observation,
        session,
    )


def run_pump_station_review_reference_session(
    *,
    bridge: PumpStationHarborBridge,
    output_dir: Path,
    session_identity: str,
) -> CompletedPumpStationReviewSession:
    """Execute one provider-free review through the closed reviewer tools."""
    if not bridge.maintenance_review:
        raise ValueError("pump-station Harbor bridge does not enable review")
    identity = _safe_identity(session_identity)
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"review-session output already exists: {destination}")
    destination.mkdir(parents=True)
    source_root, review_root, public_case, observation, session = _prepare_review_session(
        bridge=bridge,
        destination=destination,
        identity=identity,
    )
    submission = build_reference_review_submission(
        public_case,
        review_id=f"review-{identity}",
        reviewer_tenure_id=observation.reviewer_tenure_id,
    )
    receipt = session.submit_review(submission)
    verification = verify_pump_station_review(
        source_run_root=source_root,
        review_repository_root=review_root,
        case_id=public_case.case_id,
        review_id=submission.review_id,
        package_root=bridge.package_root,
    )
    if not verification.valid:
        raise ValueError("deterministic closeout review did not verify")
    _write_json(
        destination / "review-submission.json",
        submission.model_dump(mode="json"),
    )
    _write_json(
        destination / "review-submission-receipt.json",
        receipt.model_dump(mode="json"),
    )
    _write_json(
        destination / "review-verification-report.json",
        verification.model_dump(mode="json"),
    )
    _write_json(
        destination / "artifact-inventory.json",
        _artifact_inventory(
            bridge=bridge,
            output_dir=destination,
            case_id=public_case.case_id,
            review_id=submission.review_id,
        ),
    )
    return CompletedPumpStationReviewSession(
        public_case=public_case,
        observation=observation,
        submission=submission,
        receipt=receipt,
        verification=verification,
        output_dir=destination,
    )


def run_pump_station_review_model_session(
    *,
    bridge: PumpStationHarborBridge,
    output_dir: Path,
    session_identity: str,
    authority: PumpStationReviewAgentAuthority,
    registry: Any | None = None,
) -> CompletedPumpStationReviewModelSession:
    """Run one authority-bound model through only the closed reviewer tools."""
    if not bridge.maintenance_review:
        raise ValueError("pump-station Harbor bridge does not enable review")
    identity = _safe_identity(session_identity)
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"review-session output already exists: {destination}")
    destination.mkdir(parents=True)
    source_root, review_root, public_case, observation, session = _prepare_review_session(
        bridge=bridge,
        destination=destination,
        identity=identity,
    )
    _write_json(
        destination / "agent-authority.json",
        authority.model_dump(mode="json"),
    )
    trajectory = TrajectoryWriter(path=str(destination / "trajectory.jsonl"))
    try:
        resolved_registry = registry or _local_adapter_registry()
        adapter = resolved_registry.build(
            adapter_kind=authority.adapter_id,
            model_name=authority.model_id,
            workspace=str(destination),
            trajectory_writer=trajectory,
            native_tools=session.native_tools,
            enable_bash=authority.bash_enabled,
            cache=authority.cache_enabled,
        )
        adapter_result = adapter.execute(
            build_pump_station_review_adapter_request(
                authority,
                tool_specs=session.tool_specs,
                output_path=str(destination / "output.md"),
            )
        )
    finally:
        trajectory.close()

    repository = PumpStationReviewCaseRepository(review_root)
    review_ids = repository.list_review_ids(public_case.case_id)
    submission: PumpStationReviewSubmission | None = None
    receipt: PumpStationReviewSubmissionReceipt | None = None
    verification: PumpStationReviewVerificationReport | None = None
    if len(review_ids) == 1:
        submission = repository.load_review(review_ids[0])
        receipt = repository.load_review_receipt(review_ids[0])
        verification = verify_pump_station_review(
            source_run_root=source_root,
            review_repository_root=review_root,
            case_id=public_case.case_id,
            review_id=submission.review_id,
            package_root=bridge.package_root,
        )
        _write_json(
            destination / "review-submission.json",
            submission.model_dump(mode="json"),
        )
        _write_json(
            destination / "review-submission-receipt.json",
            receipt.model_dump(mode="json"),
        )
        _write_json(
            destination / "review-verification-report.json",
            verification.model_dump(mode="json"),
        )
    agent_result = _write_review_model_evidence(
        destination=destination,
        authority=authority,
        adapter_result=adapter_result,
        review_count=len(review_ids),
        review_id=None if submission is None else submission.review_id,
        review_content_sha256=(None if submission is None else submission.content_sha256),
        review_verification_valid=(None if verification is None else verification.valid),
    )
    _write_json(
        destination / "artifact-inventory.json",
        _artifact_inventory(
            bridge=bridge,
            output_dir=destination,
            case_id=public_case.case_id,
            review_id=None if submission is None else submission.review_id,
            controller_id=authority.model_id,
            authority_content_sha256=authority.content_sha256,
        ),
    )
    return CompletedPumpStationReviewModelSession(
        public_case=public_case,
        observation=observation,
        submission=submission,
        receipt=receipt,
        verification=verification,
        adapter_result=adapter_result,
        authority_valid=bool(agent_result["authority_valid"]),
        agent_result=agent_result,
        output_dir=destination,
    )


def _local_adapter_registry() -> Any:
    from aec_bench.adapters.local_registry import LocalAdapterRegistry

    return LocalAdapterRegistry()


def _write_review_model_evidence(
    *,
    destination: Path,
    authority: PumpStationReviewAgentAuthority,
    adapter_result: AdapterResult,
    review_count: int,
    review_id: str | None,
    review_content_sha256: str | None,
    review_verification_valid: bool | None,
) -> dict[str, Any]:
    raw_output = adapter_result.raw_output_text or ""
    (destination / "output.md").write_text(raw_output, encoding="utf-8")
    with (destination / "conversation.jsonl").open(
        "w",
        encoding="utf-8",
    ) as handle:
        for entry in adapter_result.transcript:
            handle.write(
                json.dumps(
                    {
                        "role": entry.role.value,
                        "event": entry.event.value,
                        "content": entry.content,
                        "tool_name": entry.tool_name,
                        "tool_call_id": entry.tool_call_id,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    input_tokens = adapter_result.usage_input_tokens
    output_tokens = adapter_result.usage_output_tokens
    cache_read_tokens = adapter_result.usage_cache_read_tokens
    cache_write_tokens = adapter_result.usage_cache_write_tokens
    total_tokens = None if input_tokens is None or output_tokens is None else input_tokens + output_tokens
    estimated_spend_microusd = (
        None
        if input_tokens is None or output_tokens is None
        else calculate_pump_station_review_spend_microusd(
            authority,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens or 0,
            cache_write_tokens=cache_write_tokens or 0,
        )
    )
    authority_issues = _review_agent_authority_issues(
        authority=authority,
        adapter_result=adapter_result,
        total_tokens=total_tokens,
        estimated_spend_microusd=estimated_spend_microusd,
        review_count=review_count,
        review_verification_valid=review_verification_valid,
    )
    payload = {
        "schema_version": "pump-station.review-agent-result.v1",
        "authority_content_sha256": authority.content_sha256,
        "authority_valid": not authority_issues,
        "authority_issues": authority_issues,
        "status": adapter_result.agent_output.status.value,
        "failure_kind": (None if adapter_result.failure_kind is None else adapter_result.failure_kind.value),
        "provider_error": adapter_result.provider_error,
        "provider_id": authority.provider_id,
        "provider_route": authority.provider_route,
        "model": authority.model_id,
        "resolved_model": adapter_result.resolved_model,
        "adapter": authority.adapter_id,
        "adapter_name": adapter_result.adapter_name,
        "configuration_record": adapter_result.configuration_record,
        "provider_call_count": adapter_result.usage_model_calls,
        "turns_used": adapter_result.turns_used,
        "maximum_input_tokens_in_one_call": (adapter_result.maximum_input_tokens_in_one_call),
        "maximum_output_tokens_in_one_call": (adapter_result.maximum_output_tokens_in_one_call),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reported_analysis_tokens": None,
        "analysis_token_reporting": ("not_reported_separately_by_adapter"),
        "analysis_tokens_included_in": "output_tokens",
        "total_tokens": total_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "estimated_spend_microusd": estimated_spend_microusd,
        "spend_currency": authority.spend_currency,
        "review_count": review_count,
        "review_id": review_id,
        "review_content_sha256": review_content_sha256,
        "review_verification_valid": review_verification_valid,
        "trajectory_sha256": file_sha256(destination / "trajectory.jsonl"),
        "conversation_sha256": file_sha256(destination / "conversation.jsonl"),
        "output_sha256": file_sha256(destination / "output.md"),
    }
    _write_json(destination / "agent-result.json", payload)
    return payload


def _review_agent_authority_issues(
    *,
    authority: PumpStationReviewAgentAuthority,
    adapter_result: AdapterResult,
    total_tokens: int | None,
    estimated_spend_microusd: int | None,
    review_count: int,
    review_verification_valid: bool | None,
) -> list[str]:
    issues: list[str] = []
    if adapter_result.agent_output.status is not AgentOutputStatus.COMPLETED:
        issues.append("adapter did not complete")
    if adapter_result.failure_kind is not None:
        issues.append("adapter reported a failure")
    if adapter_result.resolved_model != authority.model_id:
        issues.append("resolved model differs from authority")
    if (
        adapter_result.usage_model_calls is None
        or adapter_result.usage_model_calls < 1
        or adapter_result.usage_model_calls > authority.maximum_provider_calls
    ):
        issues.append("provider call count is absent or outside authority")
    if (
        adapter_result.turns_used is None
        or adapter_result.turns_used < 1
        or adapter_result.turns_used > authority.maximum_model_turns
    ):
        issues.append("model turn count is absent or outside authority")
    if (
        adapter_result.maximum_output_tokens_in_one_call is None
        or adapter_result.maximum_output_tokens_in_one_call > authority.maximum_output_tokens_per_call
    ):
        issues.append("per-call output use is absent or outside authority")
    if authority.maximum_total_tokens is not None and (
        total_tokens is None or total_tokens > authority.maximum_total_tokens
    ):
        issues.append("total token use is absent or outside authority")
    if (adapter_result.usage_cache_read_tokens or 0) != 0 or (adapter_result.usage_cache_write_tokens or 0) != 0:
        issues.append("cache use differs from authority")
    if estimated_spend_microusd is None or estimated_spend_microusd > authority.maximum_estimated_spend_microusd:
        issues.append("estimated spend is absent or outside authority")
    if review_count != 1:
        issues.append("agent did not publish exactly one review")
    if review_verification_valid is not True:
        issues.append("agent review did not pass independent verification")
    return issues


def _artifact_inventory(
    *,
    bridge: PumpStationHarborBridge,
    output_dir: Path,
    case_id: str,
    review_id: str | None,
    controller_id: str = PUMP_STATION_REFERENCE_CONTROLLER_ID,
    authority_content_sha256: str | None = None,
) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or not is_pump_station_harbor_inventory_artifact(
            output_dir,
            path,
        ):
            continue
        payload = path.read_bytes()
        artifacts.append(
            {
                "path": path.relative_to(output_dir).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    return {
        "schema_version": PUMP_STATION_REVIEW_HARBOR_RUN_SCHEMA_VERSION,
        "execution_kind": PUMP_STATION_REVIEW_HARBOR_EXECUTION_KIND,
        "task_world_id": PUMP_STATION_REVIEW_TASK_ID,
        "controller_id": controller_id,
        "export_manifest_sha256": bridge.export_manifest_sha256,
        "verifier_runtime_sha256": bridge.verifier_runtime_sha256,
        "package_content_id": bridge.package.package_content_id,
        "package_manifest_content_id": bridge.package.manifest_content_id,
        "tool_names": list(PUMP_STATION_REVIEW_TOOL_NAMES),
        "case_id": case_id,
        "review_id": review_id,
        "authority_content_sha256": authority_content_sha256,
        "artifacts": artifacts,
    }


def verify_pump_station_harbor_review_run(
    *,
    run_dir: Path,
    export_manifest_path: Path,
    package_dir: Path,
    verifier_runtime_path: Path | None = None,
) -> dict[str, Any]:
    """Independently verify one completed Harbor review session."""
    root = Path(run_dir)
    manifest = _read_json(export_manifest_path)
    bridge_payload = _mapping(manifest.get("bridge"), "bridge")
    if (
        manifest.get("schema_version") != PUMP_STATION_HARBOR_EXPORT_SCHEMA_VERSION
        or manifest.get("execution_kind") != PUMP_STATION_REVIEW_HARBOR_EXECUTION_KIND
        or manifest.get("task_world_id") != PUMP_STATION_REVIEW_TASK_ID
        or bridge_payload.get("mode") != PUMP_STATION_REVIEW_HARBOR_BRIDGE_MODE
        or bridge_payload.get("maintenance_review") is not True
        or tuple(bridge_payload.get("allowed_tools", ())) != PUMP_STATION_REVIEW_TOOL_NAMES
    ):
        raise ValueError("pump-station Harbor review export identity differs")
    package_payload = _mapping(manifest.get("package"), "package")
    package = load_reference_package(package_dir)
    if (
        package.package_content_id != package_payload.get("package_content_id")
        or package.manifest_content_id != package_payload.get("manifest_content_id")
        or directory_sha256(package_dir) != package_payload.get("directory_sha256")
        or file_sha256(package_dir / "promotion-manifest.json") != package_payload.get("manifest_sha256")
    ):
        raise ValueError("pump-station Harbor review package differs")
    verifier_payload = _mapping(manifest.get("verifier"), "verifier")
    if verifier_runtime_path is not None and (
        file_sha256(verifier_runtime_path) != verifier_payload.get("runtime_wheel_sha256")
    ):
        raise ValueError("pump-station Harbor review verifier runtime differs")
    inventory = _read_json(root / "artifact-inventory.json")
    if (
        inventory.get("schema_version") != PUMP_STATION_REVIEW_HARBOR_RUN_SCHEMA_VERSION
        or inventory.get("execution_kind") != PUMP_STATION_REVIEW_HARBOR_EXECUTION_KIND
        or inventory.get("task_world_id") != PUMP_STATION_REVIEW_TASK_ID
        or inventory.get("export_manifest_sha256") != file_sha256(export_manifest_path)
        or inventory.get("verifier_runtime_sha256") != verifier_payload.get("runtime_wheel_sha256")
        or inventory.get("package_content_id") != package.package_content_id
        or inventory.get("package_manifest_content_id") != package.manifest_content_id
        or tuple(inventory.get("tool_names", ())) != PUMP_STATION_REVIEW_TOOL_NAMES
    ):
        raise ValueError("pump-station Harbor review inventory identity differs")
    _verify_inventory(root, inventory)
    session_request = PumpStationReviewSessionRequest.model_validate(_read_json(root / "review-session-request.json"))
    observation = PumpStationReviewObservation.model_validate(_read_json(root / "review-observation.json"))
    submission = PumpStationReviewSubmission.model_validate(_read_json(root / "review-submission.json"))
    receipt = PumpStationReviewSubmissionReceipt.model_validate(_read_json(root / "review-submission-receipt.json"))
    stored_report = PumpStationReviewVerificationReport.model_validate(
        _read_json(root / "review-verification-report.json")
    )
    report = verify_pump_station_review(
        source_run_root=root / "source-world",
        review_repository_root=root / "review-cases",
        case_id=str(inventory.get("case_id")),
        review_id=str(inventory.get("review_id")),
        package_root=package_dir,
    )
    if (
        session_request.case_id != inventory.get("case_id")
        or observation.public_case.case_id != session_request.case_id
        or submission.review_id != inventory.get("review_id")
        or receipt.review_content_sha256 != submission.content_sha256
        or stored_report != report
        or not report.valid
    ):
        raise ValueError("pump-station Harbor review evidence differs")
    controller_id = inventory.get("controller_id")
    if controller_id != PUMP_STATION_REFERENCE_CONTROLLER_ID:
        _verify_model_reviewer(
            root=root,
            inventory=inventory,
            submission=submission,
            report=report,
        )
    return {
        "valid": True,
        "objective_complete": True,
        "reward_owner": "harbor_verifier",
        "task_world_id": PUMP_STATION_REVIEW_TASK_ID,
        "case_id": report.case_id,
        "review_id": report.review_id,
        "source_state_id": report.source_state_id,
    }


def _verify_model_reviewer(
    *,
    root: Path,
    inventory: dict[str, Any],
    submission: PumpStationReviewSubmission,
    report: PumpStationReviewVerificationReport,
) -> None:
    authority = PumpStationReviewAgentAuthority.model_validate(_read_json(root / "agent-authority.json"))
    agent_result = _read_json(root / "agent-result.json")
    input_tokens = _non_negative_integer(
        agent_result.get("input_tokens"),
        "input_tokens",
    )
    output_tokens = _non_negative_integer(
        agent_result.get("output_tokens"),
        "output_tokens",
    )
    cache_read_tokens = _non_negative_integer(
        agent_result.get("cache_read_tokens"),
        "cache_read_tokens",
    )
    cache_write_tokens = _non_negative_integer(
        agent_result.get("cache_write_tokens"),
        "cache_write_tokens",
    )
    provider_calls = _positive_integer(
        agent_result.get("provider_call_count"),
        "provider_call_count",
    )
    turns_used = _positive_integer(
        agent_result.get("turns_used"),
        "turns_used",
    )
    _non_negative_integer(
        agent_result.get("maximum_input_tokens_in_one_call"),
        "maximum_input_tokens_in_one_call",
    )
    maximum_output = _non_negative_integer(
        agent_result.get("maximum_output_tokens_in_one_call"),
        "maximum_output_tokens_in_one_call",
    )
    total_tokens = input_tokens + output_tokens
    spend = calculate_pump_station_review_spend_microusd(
        authority,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )
    controller_id = inventory.get("controller_id")
    if (
        authority.content_sha256 != inventory.get("authority_content_sha256")
        or authority.model_id != controller_id
        or agent_result.get("schema_version") != "pump-station.review-agent-result.v1"
        or agent_result.get("authority_content_sha256") != authority.content_sha256
        or agent_result.get("authority_valid") is not True
        or agent_result.get("authority_issues") != []
        or agent_result.get("status") != "completed"
        or agent_result.get("failure_kind") is not None
        or agent_result.get("resolved_model") != authority.model_id
        or agent_result.get("model") != authority.model_id
        or agent_result.get("provider_id") != authority.provider_id
        or agent_result.get("provider_route") != authority.provider_route
        or agent_result.get("adapter") != authority.adapter_id
        or provider_calls > authority.maximum_provider_calls
        or turns_used > authority.maximum_model_turns
        or maximum_output > authority.maximum_output_tokens_per_call
        or (authority.maximum_total_tokens is not None and total_tokens > authority.maximum_total_tokens)
        or cache_read_tokens != 0
        or cache_write_tokens != 0
        or agent_result.get("total_tokens") != total_tokens
        or agent_result.get("reported_analysis_tokens") is not None
        or agent_result.get("analysis_token_reporting") != "not_reported_separately_by_adapter"
        or agent_result.get("analysis_tokens_included_in") != "output_tokens"
        or agent_result.get("estimated_spend_microusd") != spend
        or spend > authority.maximum_estimated_spend_microusd
        or agent_result.get("spend_currency") != authority.spend_currency
        or agent_result.get("review_count") != 1
        or agent_result.get("review_id") != submission.review_id
        or agent_result.get("review_content_sha256") != submission.content_sha256
        or agent_result.get("review_verification_valid") is not True
        or report.valid is not True
        or agent_result.get("trajectory_sha256") != file_sha256(root / "trajectory.jsonl")
        or agent_result.get("conversation_sha256") != file_sha256(root / "conversation.jsonl")
        or agent_result.get("output_sha256") != file_sha256(root / "output.md")
    ):
        raise ValueError("pump-station model reviewer evidence differs")


def _non_negative_integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"pump-station model reviewer {label} differs")
    return value


def _positive_integer(value: object, label: str) -> int:
    selected = _non_negative_integer(value, label)
    if selected < 1:
        raise ValueError(f"pump-station model reviewer {label} differs")
    return selected


def _verify_inventory(root: Path, inventory: dict[str, Any]) -> None:
    raw_entries = inventory.get("artifacts")
    if not isinstance(raw_entries, list):
        raise ValueError("pump-station Harbor review inventory is not a list")
    expected: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_pump_station_harbor_inventory_artifact(
            root,
            path,
        ):
            continue
        payload = path.read_bytes()
        expected.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    if raw_entries != expected:
        raise ValueError("pump-station Harbor review inventory differs from files")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"pump-station Harbor review {label} must be an object")
    return cast(dict[str, Any], value)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = (
    "CompletedPumpStationReviewModelSession",
    "CompletedPumpStationReviewSession",
    "PUMP_STATION_REVIEW_HARBOR_RUN_SCHEMA_VERSION",
    "run_pump_station_review_model_session",
    "run_pump_station_review_reference_session",
    "verify_pump_station_harbor_review_run",
)
