# ABOUTME: Converts ordered AEC-Bench trajectory entries at the external Harbor ATIF boundary.
# ABOUTME: Preserves domain metadata and unknown observations without inventing usage or agent lineage.

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from harbor.models.trajectories.agent import Agent
from harbor.models.trajectories.metrics import Metrics
from harbor.models.trajectories.observation import Observation
from harbor.models.trajectories.observation_result import ObservationResult
from harbor.models.trajectories.step import Step
from harbor.models.trajectories.subagent_trajectory_ref import SubagentTrajectoryRef
from harbor.models.trajectories.tool_call import ToolCall
from harbor.models.trajectories.trajectory import Trajectory

from aec_bench.contracts.trajectory import TrajectoryEntry, TrajectorySubagentEntry, read_trajectory


def to_atif(
    entries: Sequence[TrajectoryEntry],
    *,
    agent_name: str,
    agent_version: str,
    model_name: str | None = None,
    session_id: str | None = None,
) -> Trajectory:
    """Build an ATIF view in file order. Requires the ``execution`` extra.

    AEC-Bench step numbers are local to an invocation; ATIF step IDs are global
    ordinals. Only adjacent records with the same step and invocation context
    are grouped. Dedicated provider reasoning records supply reasoning text;
    ordinary assistant text keeps its original meaning.
    """
    steps: list[Step] = []
    previous: TrajectoryEntry | None = None
    pending: list[ToolCall] = []
    used_call_ids: set[str] = set()
    children: dict[str, tuple[TrajectorySubagentEntry, list[TrajectoryEntry]]] = {}
    call_steps: dict[str, Step] = {}
    for index, entry in enumerate(entries):
        if entry.subagent is not None:
            child = entry.subagent
            declared, child_entries = children.setdefault(child.trajectory_id, (child, []))
            if (child.parent_tool_call_id, child.agent_name, child.model_name) != (
                declared.parent_tool_call_id,
                declared.agent_name,
                declared.model_name,
            ):
                raise ValueError(f"conflicting subagent identity: {child.trajectory_id!r}")
            child_entries.append(child.entry)
            continue
        if entry.role in {"system", "user"}:
            steps.append(
                Step(
                    step_id=len(steps) + 1,
                    source="system" if entry.role == "system" else "user",
                    message=entry.content or "",
                    timestamp=entry.timestamp,
                    extra=_extra(entry, {"content"}),
                )
            )
            previous = None
            pending = []
            continue
        if entry.role not in {
            "assistant",
            "reasoning",
            "model_response",
            "tool_call",
            "tool_result",
            "error",
            "session",
        }:
            raise ValueError(f"unsupported trajectory role: {entry.role!r}")
        result_step = call_steps.get(entry.tool_call_id or "") if entry.role == "tool_result" else None
        if result_step is None and (
            previous is None
            or (entry.step, entry.call_type, entry.meta_harness)
            != (
                previous.step,
                previous.call_type,
                previous.meta_harness,
            )
        ):
            steps.append(
                Step(
                    step_id=len(steps) + 1,
                    source="agent",
                    message="",
                    timestamp=entry.timestamp,
                    extra={"aec_bench": {"step": entry.step, **_context(entry)}},
                )
            )
            pending = []
        step = result_step or steps[-1]
        if entry.role == "model_response":
            _add_model_response(step, entry)
        elif entry.role == "error":
            assert step.extra is not None
            step.extra["aec_bench"].setdefault("errors", []).append(entry.content)
        elif entry.role == "session":
            assert step.extra is not None
            step.extra["aec_bench"]["session"] = entry.metadata
        elif entry.role == "reasoning":
            assert entry.reasoning is not None and step.extra is not None
            if entry.reasoning.content:
                step.reasoning_content = "\n".join(
                    text for text in (step.reasoning_content, entry.reasoning.content) if text
                )
            step.extra["aec_bench"].setdefault("reasoning_parts", []).append(
                entry.reasoning.model_dump(mode="json", exclude_none=True, exclude={"content"})
            )
        elif entry.role == "assistant":
            step.message = "\n".join(text for text in (str(step.message), entry.content or "") if text)
            if step.extra is not None:
                step.extra["aec_bench"].setdefault("messages", []).append(_metadata(entry, {"content"}))
        elif entry.role == "tool_call":
            call_id = entry.tool_call_id or f"aec-entry-{index + 1}"
            if call_id in used_call_ids:
                raise ValueError(f"duplicate trajectory tool_call_id: {call_id!r}")
            used_call_ids.add(call_id)
            if not entry.tool_name:
                raise ValueError("trajectory tool call requires tool_name")
            call = ToolCall(
                tool_call_id=call_id,
                function_name=entry.tool_name,
                arguments=entry.arguments if entry.arguments is not None else {"command": entry.command or ""},
                extra=_extra(entry, {"tool_call_id", "tool_name", "arguments"}),
            )
            if step.tool_calls is None:
                step.tool_calls = []
            step.tool_calls.append(call)
            pending.append(call)
            call_steps[call_id] = step
        else:
            candidates = [
                call
                for call in pending
                if (
                    call.tool_call_id == entry.tool_call_id
                    if entry.tool_call_id is not None
                    else call.function_name == entry.tool_name
                )
            ]
            source_call_id = (
                entry.tool_call_id
                if result_step is not None
                else (candidates[0].tool_call_id if len(candidates) == 1 else None)
            )
            if len(candidates) == 1:
                pending.remove(candidates[0])
            content = entry.stdout or ""
            if entry.stderr:
                content += ("\n" if content else "") + "stderr:\n" + entry.stderr
            observation = ObservationResult(
                source_call_id=source_call_id,
                content=content,
                extra=_extra(entry, {"stdout"}),
            )
            if step.observation is None:
                step.observation = Observation(results=[])
            step.observation.results.append(observation)
        if result_step is None or result_step is steps[-1]:
            previous = entry
    embedded: list[Trajectory] = []
    calls = {call.tool_call_id: step for step in steps for call in step.tool_calls or []}
    for declared, child_entries in children.values():
        child_trajectory = to_atif(
            child_entries,
            agent_name=declared.agent_name,
            agent_version=agent_version,
            model_name=declared.model_name,
            session_id=session_id,
        )
        child_trajectory.trajectory_id = declared.trajectory_id
        embedded.append(child_trajectory)
        if declared.parent_tool_call_id is None:
            continue
        parent_step = calls.get(declared.parent_tool_call_id)
        if parent_step is None:
            raise ValueError(f"subagent references unknown parent tool call: {declared.parent_tool_call_id!r}")
        if parent_step.observation is None:
            parent_step.observation = Observation(results=[])
        matches = [
            result
            for result in parent_step.observation.results
            if result.source_call_id == declared.parent_tool_call_id
        ]
        if len(matches) > 1:
            raise ValueError(f"subagent parent has ambiguous observations: {declared.parent_tool_call_id!r}")
        if matches:
            observation = matches[0]
        else:
            # The call has started but may not yet have returned. The reference
            # carries no result content and does not imply successful execution.
            observation = ObservationResult(source_call_id=declared.parent_tool_call_id)
            parent_step.observation.results.append(observation)
        if observation.subagent_trajectory_ref is None:
            observation.subagent_trajectory_ref = []
        observation.subagent_trajectory_ref.append(SubagentTrajectoryRef(trajectory_id=declared.trajectory_id))
    # Validate the assembled steps too: assignment to an upstream model does
    # not itself re-run its cross-field validators.
    return Trajectory.model_validate(
        {
            "schema_version": "ATIF-v1.8",
            "session_id": session_id,
            "agent": Agent(name=agent_name, version=agent_version, model_name=model_name).model_dump(),
            "steps": [step.model_dump() for step in steps],
            "subagent_trajectories": [child.model_dump() for child in embedded] or None,
            "extra": {"aec_bench": {"source_format": "trajectory.jsonl"}},
        }
    )


def _add_model_response(step: Step, entry: TrajectoryEntry) -> None:
    assert entry.model_response is not None and step.extra is not None
    if step.llm_call_count is not None:
        raise ValueError("an ATIF step cannot contain two model_response records")
    response = entry.model_response
    step.llm_call_count = 1
    step.model_name = response.model_name
    step.extra["aec_bench"]["model_response"] = response.model_dump(
        mode="json",
        exclude_none=True,
        exclude={"usage"},
    )
    if response.usage is not None:
        usage = response.usage
        step.metrics = Metrics(
            prompt_tokens=usage.input_tokens,
            completion_tokens=usage.output_tokens,
            cached_tokens=usage.cache_read_tokens,
            extra={
                "aec_bench": {
                    "source": response.source,
                    **usage.model_dump(
                        mode="json", exclude_none=True, exclude={"input_tokens", "output_tokens", "cache_read_tokens"}
                    ),
                }
            },
        )


def _context(entry: TrajectoryEntry) -> dict[str, Any]:
    return entry.model_dump(mode="json", exclude_none=True, include={"call_type", "meta_harness"})


def _metadata(entry: TrajectoryEntry, mapped: set[str]) -> dict[str, Any]:
    return entry.model_dump(mode="json", exclude_none=True, exclude=mapped)


def _extra(entry: TrajectoryEntry, mapped: set[str]) -> dict[str, Any]:
    return {"aec_bench": _metadata(entry, mapped)}


def write_atif(trajectory: Trajectory, destination: Path) -> None:
    """Replace a derived ATIF file atomically so viewers never read partial JSON."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(trajectory.model_dump_json(exclude_none=True, indent=2) + "\n")
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def export_atif(
    source: Path,
    destination: Path,
    *,
    agent_name: str,
    agent_version: str,
    model_name: str | None = None,
    session_id: str | None = None,
) -> None:
    """Export one complete source file without changing its authoritative bytes."""
    if source.resolve() == destination.resolve():
        raise ValueError("ATIF source and destination must be different files")
    write_atif(
        to_atif(
            read_trajectory(source),
            agent_name=agent_name,
            agent_version=agent_version,
            model_name=model_name,
            session_id=session_id,
        ),
        destination,
    )
