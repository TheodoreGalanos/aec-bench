# ABOUTME: Registers the pump-station world and its exact ASW-8 RS1 profile.
# ABOUTME: Reuses certified profile loaders without creating another pump execution path.

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import TypeAdapter

from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.continual_world import ContinualWorldDefinitionSpec, ContinualWorldProfileRef
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.world_interface import (
    WorldControlCapabilityCatalogue,
    WorldControlRequest,
)
from aec_bench.contracts.world_session import WorldSessionRequest
from aec_bench.harness.world_session import open_world_session
from aec_bench.task_world_templates.continual.actor_session import ActorWorldSession
from aec_bench.task_world_templates.continual.definition import (
    ContinualWorldDefinition,
    ContinualWorldHarborBridgeIdentity,
    ContinualWorldHarborSessionResult,
    LoadedContinualWorldProfile,
    python_source_sha256,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    reference_package_reader,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PumpStationCoupledWorldState,
    create_asw_8_world_state,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    coupled_pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_models import (
    ReferencePackage,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_REFERENCE_SYSTEM_ID,
    PumpStationReferenceSystem,
    load_reference_system,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
)

PUMP_STATION_CONTINUAL_DEFINITION_VERSION = "1"
PUMP_STATION_RS1_PROFILE_VERSION = "1"


@dataclass(frozen=True)
class PumpStationContinualProfile:
    """Validated RS1 data and opening state supplied by the registered pump port."""

    reference_system: PumpStationReferenceSystem
    station_package: ReferencePackage
    model: PumpStationCoupledModel
    opening_state: PumpStationCoupledWorldState


@dataclass(frozen=True, slots=True)
class PumpStationContinualExecutionPort:
    """Bind registered actor and host-control calls to the canonical pump owners."""

    def open_actor_session(
        self,
        *,
        profile: LoadedContinualWorldProfile,
        run_root: Path,
        package_root: Path | None,
        request: WorldSessionRequest,
    ) -> ActorWorldSession:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
            PumpStationWorldSessionFactory,
        )

        profile_ref = _execution_profile_ref(profile)
        return cast(
            ActorWorldSession,
            open_world_session(
                request,
                PumpStationWorldSessionFactory(
                    run_root,
                    profile_ref=profile_ref,
                    package_root=package_root,
                ),
            ),
        )

    def control_capabilities(
        self,
        *,
        profile: LoadedContinualWorldProfile,
        run_root: Path,
        package_root: Path | None,
        authorised_principal_ids: tuple[str, ...],
        authority_id: str,
    ) -> WorldControlCapabilityCatalogue:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_control import (
            PumpStationWorldControl,
        )

        profile_ref = _execution_profile_ref(profile)
        return PumpStationWorldControl(
            run_root,
            authorised_principal_ids=authorised_principal_ids,
            profile_ref=profile_ref,
            package_root=package_root,
        ).capabilities(authority_id)

    def execute_control(
        self,
        *,
        profile: LoadedContinualWorldProfile,
        run_root: Path,
        package_root: Path | None,
        authorised_principal_ids: tuple[str, ...],
        request_payload: Mapping[str, object],
    ) -> object:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
            PumpStationBoundControlRequest,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_control import (
            PumpStationEvidenceControlRequest,
            PumpStationWorldControl,
        )

        profile_ref = _execution_profile_ref(profile)
        request: WorldControlRequest | PumpStationEvidenceControlRequest | PumpStationBoundControlRequest = TypeAdapter(
            WorldControlRequest | PumpStationEvidenceControlRequest | PumpStationBoundControlRequest
        ).validate_python(dict(request_payload))
        return PumpStationWorldControl(
            run_root,
            authorised_principal_ids=authorised_principal_ids,
            profile_ref=profile_ref,
            package_root=package_root,
        ).execute(request)


@dataclass(frozen=True, slots=True)
class PumpStationContinualEvaluationPort:
    """Evaluate registered pump runs through the task-owned evaluator."""

    def evaluate_run(
        self,
        *,
        profile: LoadedContinualWorldProfile,
        run_root: Path,
        imported_artifact_sha256: tuple[str, ...],
        evaluation_scope: Literal["complete_journey", "bounded_continuation"],
    ) -> object:
        from aec_bench.evaluation.stewardship import evaluate_pump_station_reference_run
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
            PumpStationWorldRun,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
            PumpStationWorldRunRepository,
        )

        _execution_profile_ref(profile)
        repository = PumpStationWorldRunRepository(run_root)
        run = PumpStationWorldRun.resume_reference_system(
            repository=repository,
            snapshot=repository.current_snapshot(),
        )
        return evaluate_pump_station_reference_run(
            run,
            imported_artifact_sha256=imported_artifact_sha256,
            evaluation_scope=evaluation_scope,
        )


@dataclass(frozen=True, slots=True)
class PumpStationContinualHarborPort:
    """Keep every pump Harbor stage and controller choice inside the task port."""

    execution_kinds: tuple[str, ...] = (
        "stewardship_world_session",
        "stewardship_review_session",
    )

    @property
    def default_max_turns(self) -> int:
        """Return the task-owned model turn limit from its canonical session owner."""

        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
            PUMP_STATION_MODEL_MAX_TURNS,
        )

        return PUMP_STATION_MODEL_MAX_TURNS

    def validate_configuration(
        self,
        *,
        configuration: Mapping[str, Any],
        model_name: str,
    ) -> None:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
            PUMP_STATION_HARBOR_BRIDGE_MODE,
            PUMP_STATION_HARBOR_EXECUTION_KIND,
            PUMP_STATION_REVIEW_HARBOR_BRIDGE_MODE,
            PUMP_STATION_REVIEW_HARBOR_EXECUTION_KIND,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
            PUMP_STATION_MODEL_CONTROLLER_MODE,
            PUMP_STATION_REFERENCE_CONTROLLER_ID,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_controller import (
            PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
        )

        session = configuration.get("world_session")
        if not isinstance(session, dict):
            raise ValueError("pump-station world session bridge configuration differs")
        bridge_mode = session.get("bridge_mode")
        maintenance_review = bridge_mode == PUMP_STATION_REVIEW_HARBOR_BRIDGE_MODE
        expected_execution_kind = (
            PUMP_STATION_REVIEW_HARBOR_EXECUTION_KIND if maintenance_review else PUMP_STATION_HARBOR_EXECUTION_KIND
        )
        if configuration.get("execution_kind") != expected_execution_kind:
            raise ValueError("pump-station world session requires its exact execution kind")
        if bridge_mode not in {
            PUMP_STATION_HARBOR_BRIDGE_MODE,
            PUMP_STATION_REVIEW_HARBOR_BRIDGE_MODE,
        }:
            raise ValueError("pump-station world session bridge configuration differs")
        controller = session.get("controller")
        reference_controller = model_name in {
            PUMP_STATION_REFERENCE_CONTROLLER_ID,
            PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
        }
        if maintenance_review and not reference_controller:
            raise ValueError("pump-station review model runs require the separately approved direct host runner")
        expected_session = {"bridge_mode": bridge_mode}
        if not reference_controller:
            expected_session["controller"] = PUMP_STATION_MODEL_CONTROLLER_MODE
        if session != expected_session:
            raise ValueError("pump-station world session bridge configuration differs")
        if reference_controller and controller is not None:
            raise ValueError("pump-station reference controller cannot use model mode")
        if not reference_controller and not model_name.strip():
            raise ValueError("pump-station model controller requires a model")

    def load_bridge(self, environment_dir: Path) -> object:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
            load_pump_station_harbor_bridge,
        )

        return load_pump_station_harbor_bridge(environment_dir)

    def bridge_identity(self, bridge: object) -> ContinualWorldHarborBridgeIdentity:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
            PumpStationHarborBridge,
        )

        if not isinstance(bridge, PumpStationHarborBridge):
            raise TypeError("pump-station Harbor port received another task bridge")
        return ContinualWorldHarborBridgeIdentity(
            execution_kind=bridge.execution_kind,
            bridge_mode=bridge.bridge_mode,
            manifest_sha256=bridge.export_manifest_sha256,
            output_path=bridge.output_path,
        )

    def uses_model_controller(self, *, bridge: object, model_name: str) -> bool:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
            PumpStationHarborBridge,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
            PUMP_STATION_REFERENCE_CONTROLLER_ID,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_controller import (
            PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
        )

        if not isinstance(bridge, PumpStationHarborBridge):
            raise TypeError("pump-station Harbor port received another task bridge")
        expected_reference_controller = (
            PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID
            if bridge.profile_ref is not None
            else PUMP_STATION_REFERENCE_CONTROLLER_ID
        )
        if (
            model_name
            in {
                PUMP_STATION_REFERENCE_CONTROLLER_ID,
                PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
            }
            and model_name != expected_reference_controller
        ):
            raise ValueError("pump-station reference controller differs from the exported profile")
        return model_name != expected_reference_controller

    def run_session(
        self,
        *,
        bridge: object,
        staging_dir: Path,
        session_identity: str,
        model_name: str,
        max_turns: int,
        registry: object | None,
    ) -> ContinualWorldHarborSessionResult:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
            PumpStationHarborBridge,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
            PUMP_STATION_REFERENCE_CONTROLLER_ID,
            run_pump_station_evidence_health_reference_session,
            run_pump_station_model_session,
            run_pump_station_reference_session,
            run_pump_station_rich_work_reference_session,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_harbor import (
            run_pump_station_review_reference_session,
        )
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_controller import (
            PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
        )

        if not isinstance(bridge, PumpStationHarborBridge):
            raise TypeError("pump-station Harbor port received another task bridge")
        run_dir = staging_dir / "world-session"
        expected_reference_controller = (
            PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID
            if bridge.profile_ref is not None
            else PUMP_STATION_REFERENCE_CONTROLLER_ID
        )
        model_controller = self.uses_model_controller(
            bridge=bridge,
            model_name=model_name,
        )
        if not model_controller:
            if bridge.maintenance_review:
                review_session = run_pump_station_review_reference_session(
                    bridge=bridge,
                    output_dir=run_dir,
                    session_identity=session_identity,
                )
                world_session_id = review_session.observation.session_id
            else:
                reference_runner = (
                    run_pump_station_reference_session
                    if bridge.profile_ref is not None
                    else run_pump_station_evidence_health_reference_session
                    if bridge.evidence_health
                    else run_pump_station_rich_work_reference_session
                    if bridge.rich_work_processes
                    else run_pump_station_reference_session
                )
                world_session = reference_runner(
                    bridge=bridge,
                    output_dir=run_dir,
                    session_identity=session_identity,
                )
                world_session_id = world_session.request.session_id
            output_file = staging_dir / "output.md"
            output_file.write_text(
                (
                    "The deterministic wastewater pump-station closeout review completed.\n"
                    if bridge.maintenance_review
                    else "The deterministic wastewater pump-station session completed.\n"
                ),
                encoding="utf-8",
            )
            return ContinualWorldHarborSessionResult(
                output_dir=run_dir,
                output_file=output_file,
                input_tokens=0,
                output_tokens=0,
                resolved_model=expected_reference_controller,
                session_id=world_session_id,
                status="completed",
            )
        model_session = run_pump_station_model_session(
            bridge=bridge,
            output_dir=run_dir,
            session_identity=session_identity,
            model=model_name,
            max_turns=max_turns,
            registry=registry,
        )
        adapter_result = model_session.adapter_result
        session_status = (
            "completed"
            if adapter_result.agent_output.status is AgentOutputStatus.COMPLETED and model_session.verification.valid
            else "incomplete"
        )
        return ContinualWorldHarborSessionResult(
            output_dir=run_dir,
            output_file=run_dir / "output.md",
            input_tokens=adapter_result.usage_input_tokens or 0,
            output_tokens=adapter_result.usage_output_tokens or 0,
            resolved_model=adapter_result.resolved_model,
            session_id=model_session.request.session_id,
            status=session_status,
        )


def _execution_profile_ref(profile: LoadedContinualWorldProfile) -> ContinualWorldProfileRef:
    profile_value = profile.value
    if not isinstance(profile_value, PumpStationContinualProfile):
        raise TypeError("registered pump execution port received another profile value")
    reference = profile.reference
    if (
        reference.task_world_id != PUMP_STATION_TASK_WORLD_ID
        or reference.profile_id != PUMP_STATION_REFERENCE_SYSTEM_ID
        or reference.profile_version != PUMP_STATION_RS1_PROFILE_VERSION
        or profile_value.reference_system.descriptor_content_id != reference.profile_content_sha256
        or profile_value.station_package.profile_id != profile_value.reference_system.station_data_profile_id
    ):
        raise ValueError("registered pump execution profile content differs")
    return reference


def _validated_profile_data() -> tuple[PumpStationReferenceSystem, ReferencePackage]:
    system = load_reference_system()
    task_world_id = str(system.descriptor.get("task_world_id"))
    if task_world_id != PUMP_STATION_TASK_WORLD_ID:
        raise ValueError("pump reference system task-world identity differs")
    station_binding = system.descriptor.get("station_data")
    if not isinstance(station_binding, Mapping):
        raise ValueError("pump reference system station-data binding is missing")
    package = reference_package_reader.load_reference_package(profile_id=system.station_data_profile_id)
    if package.package_content_id != station_binding.get("package_content_id"):
        raise ValueError("pump reference system station-data binding differs")
    return system, package


def _load_pump_station_profile(reference: ContinualWorldProfileRef) -> LoadedContinualWorldProfile:
    if reference.profile_id != PUMP_STATION_REFERENCE_SYSTEM_ID:
        raise ValueError("pump continual-world profile identity differs")
    system, package = _validated_profile_data()
    task_world_id = str(system.descriptor.get("task_world_id"))
    if task_world_id != reference.task_world_id or system.descriptor_content_id != reference.profile_content_sha256:
        raise ValueError("pump continual-world profile content differs")
    return LoadedContinualWorldProfile(
        reference=reference,
        value=PumpStationContinualProfile(
            reference_system=system,
            station_package=package,
            model=coupled_pump_station_model_from_package(package),
            opening_state=create_asw_8_world_state(),
        ),
    )


def _implementation_content_sha256() -> str:
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
        continual_rollout_adapter,
    )

    adapter_source_sha256 = hashlib.sha256(
        inspect.getsource(continual_rollout_adapter).encode("utf-8"),
    ).hexdigest()
    reference_reader_source_sha256 = hashlib.sha256(
        inspect.getsource(reference_package_reader).encode("utf-8"),
    ).hexdigest()
    return canonical_content_sha256(
        {
            "loaded_profile": python_source_sha256(PumpStationContinualProfile),
            "profile_loader": python_source_sha256(_load_pump_station_profile),
            "profile_validator": python_source_sha256(_validated_profile_data),
            "reference_system_loader": python_source_sha256(load_reference_system),
            "reference_package_reader_module": reference_reader_source_sha256,
            "model_factory": python_source_sha256(coupled_pump_station_model_from_package),
            "opening_state_factory": python_source_sha256(create_asw_8_world_state),
            "branch_adapter_module": adapter_source_sha256,
            "execution_port": python_source_sha256(PumpStationContinualExecutionPort),
            "harbor_port": python_source_sha256(PumpStationContinualHarborPort),
            "evaluation_port": python_source_sha256(PumpStationContinualEvaluationPort),
        }
    )


@cache
def pump_station_continual_world_definition() -> ContinualWorldDefinition:
    """Return the content-pinned pump definition without starting a world run."""
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_rollout_adapter import (
        PumpStationContinualWorldBranchPort,
    )

    system, _ = _validated_profile_data()
    task_world_id = str(system.descriptor.get("task_world_id"))
    profile = ContinualWorldProfileRef(
        task_world_id=task_world_id,
        profile_id=PUMP_STATION_REFERENCE_SYSTEM_ID,
        profile_version=PUMP_STATION_RS1_PROFILE_VERSION,
        profile_content_sha256=system.descriptor_content_id,
    )
    return ContinualWorldDefinition(
        spec=ContinualWorldDefinitionSpec(
            task_world_id=task_world_id,
            definition_version=PUMP_STATION_CONTINUAL_DEFINITION_VERSION,
            implementation_content_sha256=_implementation_content_sha256(),
            profiles=(profile,),
        ),
        profile_loader=_load_pump_station_profile,
        branch_port=PumpStationContinualWorldBranchPort(),
        execution_port=PumpStationContinualExecutionPort(),
        harbor_port=PumpStationContinualHarborPort(),
        evaluation_port=PumpStationContinualEvaluationPort(),
    )
