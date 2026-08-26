# ABOUTME: Loads and validates the explicit persisted state of a swarm run.
# ABOUTME: Event logs remain diagnostic records and are not used as state authority.

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aec_bench.contracts.evolution import BehaviourDescriptor, SwarmAgentState, WorkspaceSnapshot
from aec_bench.evolution.archive import QDArchive
from aec_bench.evolution.swarm.budget import BudgetLedger
from aec_bench.evolution.swarm.core import AgentPivotState, PivotState, SwarmState
from aec_bench.evolution.swarm.lineage import LineageTracker
from aec_bench.evolution.swarm.notes import NoteStore
from aec_bench.evolution.swarm.shared_graveyard import SharedGraveyard


@dataclass
class ResumedState:
    """Validated persisted swarm state and its exact supporting material."""

    swarm: SwarmState
    archive: QDArchive
    graveyard: SharedGraveyard
    lineage: LineageTracker
    notes: NoteStore
    budget: BudgetLedger
    candidates: dict[str, WorkspaceSnapshot]
    initial_candidate_id: str
    next_sequence: int

    @property
    def run_id(self) -> str:
        return self.swarm.run_id

    @property
    def total_evals(self) -> int:
        return self.swarm.total_evaluations

    @property
    def best_score(self) -> float:
        return self.swarm.best_score or 0.0

    @property
    def total_cost_usd(self) -> float:
        return self.budget.total_agent_spend


def _required_json(state_dir: Path, name: str) -> object:
    path = state_dir / name
    if not path.exists():
        raise ValueError(f"cannot resume swarm: required persisted file is missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot resume swarm: invalid JSON in {path}: {exc}") from exc


def _load_swarm_state(payload: object, path: Path) -> SwarmState:
    if not isinstance(payload, dict):
        raise ValueError(f"cannot resume swarm: {path} must contain an object")
    try:
        agents = tuple(SwarmAgentState.model_validate(item) for item in payload["agent_states"])
        pivot_payload = payload["pivot_state"]
        if not isinstance(pivot_payload, dict):
            raise TypeError("pivot_state must be an object")
        pivot = PivotState(tuple(AgentPivotState(**item) for item in pivot_payload["agent_states"]))
        return SwarmState(
            run_id=payload["run_id"],
            total_evaluations=payload["total_evaluations"],
            best_candidate_id=payload.get("best_candidate_id"),
            best_score=payload.get("best_score"),
            agent_states=agents,
            recent_scores=tuple(payload.get("recent_scores", ())),
            recent_descriptors=tuple(
                BehaviourDescriptor.model_validate(item) for item in payload.get("recent_descriptors", ())
            ),
            pivot_state=pivot,
            stopped=payload["stopped"],
            stop_reason=payload.get("stop_reason"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"cannot resume swarm: invalid explicit state in {path}: {exc}") from exc


def _load_candidates(payload: object, path: Path) -> tuple[dict[str, WorkspaceSnapshot], str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("snapshots"), list):
        raise ValueError(f"cannot resume swarm: {path} must contain an object with snapshots")
    initial_candidate_id = payload.get("initial_candidate_id")
    if not isinstance(initial_candidate_id, str) or not initial_candidate_id.strip():
        raise ValueError(f"cannot resume swarm: {path} must contain initial_candidate_id")
    candidates: dict[str, WorkspaceSnapshot] = {}
    try:
        for item in payload["snapshots"]:
            snapshot = WorkspaceSnapshot.model_validate(item)
            if snapshot.candidate_id in candidates:
                raise ValueError(f"duplicate candidate material for {snapshot.candidate_id!r}")
            candidates[snapshot.candidate_id] = snapshot
    except (TypeError, ValueError) as exc:
        raise ValueError(f"cannot resume swarm: invalid candidate material in {path}: {exc}") from exc
    if initial_candidate_id not in candidates:
        raise ValueError(f"cannot resume swarm: initial candidate {initial_candidate_id!r} has no exact material")
    return candidates, initial_candidate_id


def _validate_material(
    *,
    state: SwarmState,
    archive: QDArchive,
    graveyard: SharedGraveyard,
    lineage: LineageTracker,
    candidates: dict[str, WorkspaceSnapshot],
) -> None:
    """Reject any persisted identity that cannot resolve to exact material."""
    required: set[str] = set()
    if state.best_candidate_id is not None:
        required.add(state.best_candidate_id)
    for entry in archive.view().entries:
        required.add(entry.snapshot.candidate_id)
        if candidates.get(entry.snapshot.candidate_id) != entry.snapshot:
            raise ValueError(
                f"cannot resume swarm: archive candidate {entry.snapshot.candidate_id!r} has no exact material"
            )
    for graveyard_entry in graveyard.browse_all(limit=graveyard.size):
        required.add(graveyard_entry.candidate_id)
        if (
            graveyard_entry.rejected_snapshot is not None
            and candidates.get(graveyard_entry.candidate_id) != graveyard_entry.rejected_snapshot
        ):
            raise ValueError(
                f"cannot resume swarm: graveyard candidate {graveyard_entry.candidate_id!r} has no exact material"
            )
    for record in lineage.all_records():
        required.add(record.entry_candidate_id)
        if record.parent_candidate_id is not None:
            required.add(record.parent_candidate_id)
    missing = sorted(candidate_id for candidate_id in required if candidate_id not in candidates)
    if missing:
        raise ValueError(f"cannot resume swarm: candidate material is missing for {missing}")
    if state.best_candidate_id is not None and archive.get_entry_by_candidate_id(state.best_candidate_id) is None:
        raise ValueError(f"cannot resume swarm: best candidate {state.best_candidate_id!r} is not archived")


def load_resumed_state(state_dir: Path) -> ResumedState:
    """Load explicit swarm state and validate all persisted candidate identities."""
    state_payload = _required_json(state_dir, "swarm_state.json")
    state = _load_swarm_state(state_payload, state_dir / "swarm_state.json")
    candidates, initial_candidate_id = _load_candidates(
        _required_json(state_dir, "candidates.json"), state_dir / "candidates.json"
    )
    try:
        archive = QDArchive.load(state_dir / "archive.json")
        graveyard = SharedGraveyard.load(state_dir / "graveyard.json")
        lineage = LineageTracker.load(state_dir / "lineage.json")
        notes = NoteStore.load(state_dir / "notes.json")
        budget_payload = _required_json(state_dir, "budget.json")
        if not isinstance(budget_payload, dict):
            raise ValueError("budget must be an object")
        budget = BudgetLedger(
            max_cost_usd=float(budget_payload["max_cost_usd"]),
            eval_budget_usd=float(budget_payload["eval_budget_usd"]),
        )
        agent_spend = budget_payload.get("agent_spend", {})
        if not isinstance(agent_spend, dict):
            raise ValueError("agent_spend must be an object")
        budget.agent_spend.update({str(agent_id): float(amount) for agent_id, amount in agent_spend.items()})
        budget.eval_spend = float(budget_payload["eval_spend"])
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot resume swarm: invalid supporting state: {exc}") from exc
    _validate_material(state=state, archive=archive, graveyard=graveyard, lineage=lineage, candidates=candidates)
    next_sequence = 0
    event_path = state_dir / "events.jsonl"
    if event_path.exists():
        from aec_bench.evolution.swarm.events import SwarmEventReader

        events = SwarmEventReader(event_path).read_all()
        next_sequence = max((event.sequence_number + 1 for event in events), default=0)
    return ResumedState(
        state,
        archive,
        graveyard,
        lineage,
        notes,
        budget,
        candidates,
        initial_candidate_id,
        next_sequence,
    )
