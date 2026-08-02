# ABOUTME: Exposes the ASW-8 v4 world through one strict installed JSON request surface.
# ABOUTME: Keeps actor actions separate from host-only review, failure, and boundary controls.

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Literal, Self, cast

from pydantic import BaseModel, JsonValue, model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.contracts.world_interface import (
    WorldActorBinding,
    WorldActorObservation,
    WorldInterfaceError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    validate_pump_station_actor_arguments_v2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_evaluation import (
    evaluate_coupled_run,
    verify_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run import (
    PumpStationCoupledCommand,
    PumpStationCoupledRun,
    PumpStationCoupledRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PumpStationCommonBoundaryRequest,
    PumpStationOperationsBoundaryReviewRequest,
    PumpStationProcessOutcomeRequest,
    project_coupled_actor_view,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_temporal import (
    create_coupled_root_with_temporal_repository,
    execute_coupled_temporal_action,
    verify_coupled_temporal_repository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    canonical_stewardship_value,
    stewardship_content_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    ProposalContext,
)

PUMP_STATION_COUPLED_LOCAL_INTERFACE_VERSION = "pump-station.local-interface.v2"


class PumpStationCoupledLocalRequest(ContentAddressedModel):
    """One strict actor or host request for the installed ASW-8 surface."""

    schema_version: str = PUMP_STATION_COUPLED_LOCAL_INTERFACE_VERSION
    operation: Literal[
        "start",
        "observe",
        "actor_action",
        "handover",
        "operations_review",
        "process_outcome",
        "common_boundary",
        "verify",
        "evaluate",
    ]
    run_id: NonEmptyStr | None = None
    world_branch_id: NonEmptyStr | None = None
    request_id: NonEmptyStr | None = None
    action_name: NonEmptyStr | None = None
    arguments: dict[str, Any] | None = None
    agent_tenure_id: NonEmptyStr | None = None
    session_id: NonEmptyStr | None = None
    binding: WorldActorBinding | None = None
    from_agent_tenure_id: NonEmptyStr | None = None
    to_agent_tenure_id: NonEmptyStr | None = None
    operations_review: PumpStationOperationsBoundaryReviewRequest | None = None
    process_outcome: PumpStationProcessOutcomeRequest | None = None
    common_boundary: PumpStationCommonBoundaryRequest | None = None

    @model_validator(mode="after")
    def validate_operation_fields(self) -> Self:
        """Require one exact field set for the selected operation."""
        if self.schema_version != PUMP_STATION_COUPLED_LOCAL_INTERFACE_VERSION:
            raise ValueError("unsupported pump-station coupled local interface version")
        if self.operation == "start":
            if self.run_id is None or self.world_branch_id is None:
                raise ValueError("ASW-8 start requires run and branch identities")
            if any(
                value is not None
                for value in (
                    self.request_id,
                    self.action_name,
                    self.arguments,
                    self.agent_tenure_id,
                    self.session_id,
                    self.binding,
                    self.from_agent_tenure_id,
                    self.to_agent_tenure_id,
                    self.operations_review,
                    self.process_outcome,
                    self.common_boundary,
                )
            ):
                raise ValueError("ASW-8 start contains unrelated fields")
            return self
        if self.operation == "handover":
            if any(
                value is None
                for value in (
                    self.request_id,
                    self.from_agent_tenure_id,
                    self.to_agent_tenure_id,
                )
            ) or any(
                value is not None
                for value in (
                    self.run_id,
                    self.world_branch_id,
                    self.action_name,
                    self.arguments,
                    self.agent_tenure_id,
                    self.session_id,
                    self.binding,
                    self.operations_review,
                    self.process_outcome,
                    self.common_boundary,
                )
            ):
                raise ValueError("ASW-8 handover requires exact source and target tenures")
            return self
        if self.run_id is not None or self.world_branch_id is not None:
            raise ValueError("ASW-8 resume operations resolve identity from the manifest")
        if self.operation == "actor_action":
            if self.request_id is None or self.action_name is None or self.arguments is None or self.binding is None:
                raise ValueError("ASW-8 actor action requires request, action, arguments, and binding")
            if any(
                value is not None
                for value in (
                    self.agent_tenure_id,
                    self.session_id,
                    self.from_agent_tenure_id,
                    self.to_agent_tenure_id,
                    self.operations_review,
                    self.process_outcome,
                    self.common_boundary,
                )
            ):
                raise ValueError("ASW-8 actor action contains host control")
            return self
        if self.operation == "observe":
            if (
                self.agent_tenure_id is None
                or self.session_id is None
                or any(
                    value is not None
                    for value in (
                        self.request_id,
                        self.action_name,
                        self.arguments,
                        self.binding,
                        self.from_agent_tenure_id,
                        self.to_agent_tenure_id,
                        self.operations_review,
                        self.process_outcome,
                        self.common_boundary,
                    )
                )
            ):
                raise ValueError("ASW-8 observation requires exact tenure and session identities")
            return self
        selected_controls = tuple(
            value
            for value in (
                self.operations_review,
                self.process_outcome,
                self.common_boundary,
            )
            if value is not None
        )
        if self.operation in {"operations_review", "process_outcome", "common_boundary"}:
            if len(selected_controls) != 1 or any(
                value is not None
                for value in (
                    self.request_id,
                    self.action_name,
                    self.arguments,
                    self.agent_tenure_id,
                    self.session_id,
                    self.binding,
                    self.from_agent_tenure_id,
                    self.to_agent_tenure_id,
                )
            ):
                raise ValueError("ASW-8 host control requires exactly its selected control record")
            selected_name = {
                "operations_review": self.operations_review,
                "process_outcome": self.process_outcome,
                "common_boundary": self.common_boundary,
            }[self.operation]
            if selected_name is None:
                raise ValueError("ASW-8 host control record differs from its operation")
            return self
        if any(
            value is not None
            for value in (
                self.request_id,
                self.action_name,
                self.arguments,
                self.agent_tenure_id,
                self.session_id,
                self.binding,
                self.from_agent_tenure_id,
                self.to_agent_tenure_id,
                *selected_controls,
            )
        ):
            raise ValueError("ASW-8 read operation contains mutation fields")
        return self


def execute_coupled_local_request(
    *,
    run_root: Path,
    request: PumpStationCoupledLocalRequest,
    host_authority_id: str | None = None,
) -> dict[str, Any]:
    """Execute one strict request and return canonical transport-safe evidence."""
    if request.operation == "start":
        assert request.run_id is not None
        assert request.world_branch_id is not None
        run = create_coupled_root_with_temporal_repository(
            run_root,
            run_id=request.run_id,
            world_branch_id=request.world_branch_id,
        )
        return _result(request.operation, run, payload=project_coupled_actor_view(run.state))
    repository = PumpStationCoupledRunRepository(Path(run_root))
    run = repository.open()
    verify_coupled_temporal_repository(run_root, run)
    if request.operation == "observe":
        assert request.agent_tenure_id is not None
        assert request.session_id is not None
        return _result(
            request.operation,
            run,
            payload=_actor_observation(
                run,
                agent_tenure_id=request.agent_tenure_id,
                session_id=request.session_id,
            ),
        )
    if request.operation == "verify":
        return _result(request.operation, run, payload=verify_coupled_run(run))
    if request.operation == "evaluate":
        return _result(request.operation, run, payload=evaluate_coupled_run(run))
    if request.operation == "actor_action":
        assert request.request_id is not None
        assert request.action_name is not None
        assert request.arguments is not None
        assert request.binding is not None
        arguments = validate_pump_station_actor_arguments_v2(
            request.action_name,
            request.arguments,
        )
        expected_command = PumpStationCoupledCommand.actor(
            request.request_id,
            request.action_name,
            arguments,
        )
        request_status = _actor_request_status(run_root, request)
        recovered = _recover_published_command(
            repository,
            run,
            expected_command,
        )
        if recovered is not None:
            if request_status != "exact":
                raise WorldInterfaceError(
                    "actor-request-evidence",
                    "published command has no exact actor request",
                )
            return _result(
                request.operation,
                recovered,
                payload=recovered.receipts[-1],
            )
        expected_binding = _actor_observation(
            run,
            agent_tenure_id=request.binding.agent_tenure_id,
            session_id=request.binding.session_id,
        ).binding
        if request.binding != expected_binding:
            raise WorldInterfaceError(
                "actor-binding",
                "actor request does not match the current observed information set",
            )
        if request_status == "missing":
            _publish_actor_request(run_root, request)
        if request.action_name in {"search_evidence", "fetch_evidence"}:
            result = execute_coupled_temporal_action(
                run_root=run_root,
                run=run,
                request_id=request.request_id,
                action_name=request.action_name,
                arguments=arguments,
                agent_tenure_id=request.binding.agent_tenure_id,
                session_id=request.binding.session_id,
            )
            return _result(request.operation, run, payload=result)
        updated = run.apply_actor(
            request_id=request.request_id,
            action_name=request.action_name,
            arguments=arguments,
            proposal_context=(
                ProposalContext(
                    proposal_id=request.request_id,
                    agent_tenure_id=request.binding.agent_tenure_id,
                    based_on_sequence=request.binding.sequence,
                    base_view_id=request.binding.actor_view_id,
                    information_set_id=request.binding.information_set_id,
                    reason=str(arguments["reason"]),
                )
            ),
        )
    elif request.operation == "handover":
        assert request.request_id is not None
        assert request.from_agent_tenure_id is not None
        assert request.to_agent_tenure_id is not None
        expected_command = PumpStationCoupledCommand.handover(
            request.request_id,
            request.from_agent_tenure_id,
            request.to_agent_tenure_id,
        )
        recovered = _recover_published_command(repository, run, expected_command)
        if recovered is not None:
            return _result(
                request.operation,
                recovered,
                payload=recovered.receipts[-1],
            )
        updated = run.handover(
            handover_id=request.request_id,
            from_tenure_id=request.from_agent_tenure_id,
            to_tenure_id=request.to_agent_tenure_id,
        )
    else:
        if host_authority_id is None:
            raise ValueError("ASW-8 host control requires a host authority identity")
        selected = {
            "operations_review": request.operations_review,
            "process_outcome": request.process_outcome,
            "common_boundary": request.common_boundary,
        }[request.operation]
        assert selected is not None
        authority = getattr(
            selected,
            "operations_authority_id",
            getattr(selected, "authority_id", None),
        )
        if authority != host_authority_id:
            raise ValueError("ASW-8 host authority differs from the control record")
        if request.operation == "operations_review":
            assert request.operations_review is not None
            updated = run.apply_review(request.operations_review)
        elif request.operation == "process_outcome":
            assert request.process_outcome is not None
            updated = run.apply_process_outcome(request.process_outcome)
        else:
            assert request.common_boundary is not None
            updated = run.apply_common_boundary(request.common_boundary)
    repository.append(updated)
    return _result(
        request.operation,
        updated,
        payload=updated.receipts[-1],
    )


def _recover_published_command(
    repository: PumpStationCoupledRunRepository,
    run: PumpStationCoupledRun,
    expected: PumpStationCoupledCommand,
) -> PumpStationCoupledRun | None:
    matches = tuple(
        (index, command) for index, command in enumerate(run.commands) if command.request_id == expected.request_id
    )
    if not matches:
        return None
    if len(matches) != 1 or matches[0][1] != expected:
        raise ValueError("ASW-8 request id is already bound to different command content")
    return repository.open_generation(matches[0][0] + 1)


def _actor_observation(
    run: PumpStationCoupledRun,
    *,
    agent_tenure_id: str,
    session_id: str,
) -> WorldActorObservation:
    view = project_coupled_actor_view(run.state)
    actor_view_id = stewardship_content_id(view, record_profile="v4")
    binding = WorldActorBinding(
        task_world_id="wastewater-pump-station-stewardship.v1",
        session_id=session_id,
        run_id=run.manifest.run_id,
        episode_id=run.manifest.episode_id,
        world_branch_id=run.manifest.world_branch_id,
        sequence=run.state.sequence,
        state_id=run.state.state_id,
        commit_id=run.state.state_id,
        agent_tenure_id=agent_tenure_id,
        actor_view_id=actor_view_id,
        information_set_id=stewardship_content_id(
            (
                run.manifest.run_id,
                run.manifest.world_branch_id,
                run.state.sequence,
                run.state.state_id,
                actor_view_id,
                agent_tenure_id,
                session_id,
            ),
            record_profile="v4",
        ),
    )
    return WorldActorObservation(
        binding=binding,
        view=cast(
            dict[str, JsonValue],
            canonical_stewardship_value(view, record_profile="v4"),
        ),
    )


def _actor_request_status(
    run_root: Path,
    request: PumpStationCoupledLocalRequest,
) -> str:
    directory = Path(run_root) / "actor-requests"
    if not directory.exists():
        return "missing"
    expected = request.model_dump_json(exclude_none=True, by_alias=True).encode("utf-8") + b"\n"
    for path in directory.glob("*.json"):
        try:
            value = json.loads(path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WorldInterfaceError("actor-request-evidence", str(error)) from error
        if value.get("request_id") != request.request_id:
            continue
        if path.read_bytes() != expected:
            raise ValueError("ASW-8 request id is already bound to different actor request content")
        return "exact"
    return "missing"


def _publish_actor_request(
    run_root: Path,
    request: PumpStationCoupledLocalRequest,
) -> None:
    directory = Path(run_root) / "actor-requests"
    directory.mkdir(mode=0o700, exist_ok=True)
    payload = request.model_dump_json(exclude_none=True, by_alias=True).encode("utf-8") + b"\n"
    destination = directory / f"{request.content_sha256}.json"
    if destination.exists():
        if destination.read_bytes() != payload:
            raise WorldInterfaceError("actor-request-evidence", destination.name)
        return
    temporary = directory / f".{destination.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)


def _result(
    operation: str,
    run: PumpStationCoupledRun,
    *,
    payload: object,
) -> dict[str, Any]:
    serialized_payload = (
        payload.model_dump(mode="json")
        if isinstance(payload, BaseModel)
        else canonical_stewardship_value(payload, record_profile="v4")
    )
    return {
        "schema_version": PUMP_STATION_COUPLED_LOCAL_INTERFACE_VERSION,
        "operation": operation,
        "run_id": run.manifest.run_id,
        "world_branch_id": run.manifest.world_branch_id,
        "sequence": run.state.sequence,
        "state_id": run.state.state_id,
        "payload": serialized_payload,
    }


__all__ = (
    "PUMP_STATION_COUPLED_LOCAL_INTERFACE_VERSION",
    "PumpStationCoupledLocalRequest",
    "execute_coupled_local_request",
)
