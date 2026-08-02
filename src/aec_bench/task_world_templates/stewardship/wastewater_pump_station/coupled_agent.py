# ABOUTME: Exposes ASW-8 projection v5 through the exact closed actor tool catalogue.
# ABOUTME: Gives direct and Harbor model runs the same durable installed request path.

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.world_interface import WorldActorBinding
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES_V2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_interface import (
    PumpStationCoupledLocalRequest,
    execute_coupled_local_request,
)


class PumpStationCoupledAgentSession:
    """One bounded agent tenure over a durable ASW-8 root run."""

    def __init__(
        self,
        *,
        run_root: Path,
        agent_tenure_id: str,
        session_id: str,
    ) -> None:
        self._run_root = Path(run_root)
        self._agent_tenure_id = agent_tenure_id
        self._session_id = session_id
        self._binding: WorldActorBinding | None = None

    @classmethod
    def start(
        cls,
        *,
        run_root: Path,
        run_id: str,
        world_branch_id: str,
        agent_tenure_id: str,
        session_id: str,
    ) -> PumpStationCoupledAgentSession:
        """Create one actor-ready ASW-8 root and bind the first tenure."""
        session = cls(
            run_root=run_root,
            agent_tenure_id=agent_tenure_id,
            session_id=session_id,
        )
        execute_coupled_local_request(
            run_root=session._run_root,
            request=PumpStationCoupledLocalRequest(
                operation="start",
                run_id=run_id,
                world_branch_id=world_branch_id,
            ),
        )
        return session

    @property
    def tool_specs(self) -> tuple[ToolSpec, ...]:
        """Return only the observation tool and exact v2 actor actions."""
        names = ("observe_pump_station", *PUMP_STATION_ACTOR_ACTION_NAMES_V2)
        return tuple(
            ToolSpec(
                name=name,
                source="builtin",
                description=getattr(self, name).__doc__ or name.replace("_", " "),
            )
            for name in names
        )

    @property
    def native_tools(self) -> tuple[Callable[..., str], ...]:
        """Return bound functions in the same order as the declared tools."""
        return tuple(getattr(self, spec.name) for spec in self.tool_specs)

    def observe_pump_station(self) -> str:
        """Read the current planning view without latent health or future events."""
        result = self._execute_value(
            PumpStationCoupledLocalRequest(
                operation="observe",
                agent_tenure_id=self._agent_tenure_id,
                session_id=self._session_id,
            )
        )
        self._binding = WorldActorBinding.model_validate(result["payload"]["binding"])
        return self._serialize(result)

    def continue_operation(self, request_id: str, reason: str) -> str:
        """Continue to the next declared decision event for the stated reason."""
        return self._actor(request_id, "continue_operation", reason=reason)

    def request_duty_assignment(
        self,
        request_id: str,
        ordered_pump_ids: tuple[str, ...],
        reason: str,
    ) -> str:
        """Request an ordered eligible pump assignment for visible service."""
        return self._actor(
            request_id,
            "request_duty_assignment",
            ordered_pump_ids=tuple(ordered_pump_ids),
            reason=reason,
        )

    def request_inspection(
        self,
        request_id: str,
        pump_id: str,
        backlog_item_id: str,
        reason: str,
    ) -> str:
        """Request the visible inspection item for one named pump."""
        return self._actor(
            request_id,
            "request_inspection",
            pump_id=pump_id,
            backlog_item_id=backlog_item_id,
            reason=reason,
        )

    def request_obstruction_clearance(
        self,
        request_id: str,
        pump_id: str,
        backlog_item_id: str,
        inspection_evidence_id: str,
        reason: str,
    ) -> str:
        """Request obstruction clearance against named work and inspection evidence."""
        return self._actor(
            request_id,
            "request_obstruction_clearance",
            pump_id=pump_id,
            backlog_item_id=backlog_item_id,
            inspection_evidence_id=inspection_evidence_id,
            reason=reason,
        )

    def request_functional_check(
        self,
        request_id: str,
        pump_id: str,
        backlog_item_id: str,
        reason: str,
    ) -> str:
        """Request one controlled functional check inside the test-only boundary."""
        return self._actor(
            request_id,
            "request_functional_check",
            pump_id=pump_id,
            backlog_item_id=backlog_item_id,
            reason=reason,
        )

    def request_provisional_return(
        self,
        request_id: str,
        pump_id: str,
        functional_check_evidence_id: str,
        reason: str,
    ) -> str:
        """Request provisional return against accepted functional-check evidence."""
        return self._actor(
            request_id,
            "request_provisional_return",
            pump_id=pump_id,
            functional_check_evidence_id=functional_check_evidence_id,
            reason=reason,
        )

    def request_provisional_closure(
        self,
        request_id: str,
        work_order_id: str,
        reason: str,
    ) -> str:
        """Request administrative closure while continuing duties remain visible."""
        return self._actor(
            request_id,
            "request_provisional_closure",
            work_order_id=work_order_id,
            reason=reason,
        )

    def request_post_maintenance_verification(
        self,
        request_id: str,
        pump_id: str,
        backlog_item_id: str,
        reason: str,
    ) -> str:
        """Request independent verification for the exact visible backlog item."""
        return self._actor(
            request_id,
            "request_post_maintenance_verification",
            pump_id=pump_id,
            backlog_item_id=backlog_item_id,
            reason=reason,
        )

    def resume_process(self, request_id: str, process_id: str, reason: str) -> str:
        """Resume one suspended process after all current checks pass."""
        return self._actor(
            request_id,
            "resume_process",
            process_id=process_id,
            reason=reason,
        )

    def cancel_process(self, request_id: str, process_id: str, reason: str) -> str:
        """Cancel one live process and release its unused reservations."""
        return self._actor(
            request_id,
            "cancel_process",
            process_id=process_id,
            reason=reason,
        )

    def request_dependency_waiver(
        self,
        request_id: str,
        process_id: str,
        dependency_id: str,
        evidence_id: str,
        reason: str,
    ) -> str:
        """Request one narrow dependency waiver with named supporting evidence."""
        return self._actor(
            request_id,
            "request_dependency_waiver",
            process_id=process_id,
            dependency_id=dependency_id,
            evidence_id=evidence_id,
            reason=reason,
        )

    def request_condition_check(self, request_id: str, pump_id: str, reason: str) -> str:
        """Request one sensor-based condition check for a named pump."""
        return self._actor(
            request_id,
            "request_condition_check",
            pump_id=pump_id,
            reason=reason,
        )

    def search_evidence(
        self,
        request_id: str,
        query: str,
        scope: str = "all",
        limit: int = 5,
    ) -> str:
        """Search only documentary evidence available to this tenure now."""
        return self._actor(
            request_id,
            "search_evidence",
            query=query,
            scope=scope,
            limit=limit,
        )

    def fetch_evidence(self, request_id: str, reference: str) -> str:
        """Fetch content through an opaque reference from this tenure's search."""
        return self._actor(
            request_id,
            "fetch_evidence",
            reference=reference,
        )

    def _actor(
        self,
        request_id: str,
        action_name: str,
        **arguments: Any,
    ) -> str:
        temporal = action_name in {"search_evidence", "fetch_evidence"}
        if self._binding is None:
            raise ValueError("observe_pump_station must be called before an ASW-8 actor action")
        result = self._execute_value(
            PumpStationCoupledLocalRequest(
                operation="actor_action",
                request_id=request_id,
                action_name=action_name,
                arguments=arguments,
                binding=self._binding,
            )
        )
        if not temporal:
            self._binding = None
        return self._serialize(result)

    def _execute(self, request: PumpStationCoupledLocalRequest) -> str:
        return self._serialize(self._execute_value(request))

    def _execute_value(self, request: PumpStationCoupledLocalRequest) -> dict[str, Any]:
        return execute_coupled_local_request(
            run_root=self._run_root,
            request=request,
        )

    @staticmethod
    def _serialize(result: dict[str, Any]) -> str:
        return json.dumps(
            result,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


__all__ = ("PumpStationCoupledAgentSession",)
