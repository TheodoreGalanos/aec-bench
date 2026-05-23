# ABOUTME: Tool functions for the evolver agent's investigation-then-action loop.
# ABOUTME: Closures over workspace data that expose traces, skills, history, and mutations.

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from aec_bench.contracts.evolution import EvolutionCycleRecord, EvolutionObservation
from aec_bench.evolution.graveyard import MutationGraveyard
from aec_bench.evolution.prompts import _describe_error_direction


def build_evolver_toolset(
    *,
    observations: Sequence[EvolutionObservation],
    workspace_root: Any,
    history: Sequence[EvolutionCycleRecord],
    current_prompt: str,
    current_skills: Sequence[tuple[str, str]],
    graveyard: MutationGraveyard | None = None,
) -> dict[str, Callable[..., str]]:
    """Build the evolver's investigation tool functions as closures over workspace data.

    Returns a dict mapping tool name to callable. Each tool is a pure function that
    returns a formatted string for the evolver to consume.
    """
    # Index observations by trial_id for fast lookup
    obs_by_trial: dict[str, EvolutionObservation] = {obs.trial.trial_id: obs for obs in observations}

    # Index skills by name for fast lookup
    skills_by_name: dict[str, str] = {name: body for name, body in current_skills}

    def read_trace(trial_id: str) -> str:
        """Return bond sequence, tool calls, errors, reasoning, and field results for a trial."""
        obs = obs_by_trial.get(trial_id)
        if obs is None:
            available = ", ".join(sorted(obs_by_trial.keys())) or "none"
            return f"Trial not found: {trial_id!r}. Available IDs: {available}"

        lines: list[str] = [f"## Trace: {trial_id}"]
        lines.append(f"Discipline: {obs.discipline}")
        lines.append(f"Reward: {obs.trial.evaluation.reward:.3f}")

        digest = obs.enrichment.trace_digest
        if digest is not None:
            lines.append(f"Bond sequence: {digest.bond_sequence}")
            lines.append(
                f"Turns: {digest.turn_count}, Tool calls: {digest.tool_call_count}, Errors: {digest.tool_error_count}"
            )

            if digest.key_actions:
                lines.append("\n### Key Actions")
                for action in digest.key_actions:
                    lines.append(f"- {action}")

            if digest.errors:
                lines.append("\n### Errors")
                for error in digest.errors:
                    lines.append(f"- {error}")

            if digest.agent_reasoning:
                lines.append("\n### Agent Reasoning")
                for reasoning in digest.agent_reasoning:
                    lines.append(f"- {reasoning}")
        else:
            lines.append("No trace digest available.")

        field_scores = obs.enrichment.field_scores
        if field_scores:
            lines.append("\n### Field Results")
            for fs in field_scores:
                status = "PASS" if fs.reward >= 1.0 else "FAIL"
                if fs.reward < 1.0 and fs.expected is not None and fs.actual is not None:
                    direction = _describe_error_direction(fs.expected, fs.actual)
                    lines.append(f"- {fs.field_name}: {status} ({direction})")
                else:
                    lines.append(f"- {fs.field_name}: {status}")

        return "\n".join(lines)

    def read_skill(name: str) -> str:
        """Return the full body of a skill by name."""
        body = skills_by_name.get(name)
        if body is None:
            available = ", ".join(sorted(skills_by_name.keys())) or "none"
            return f"Skill not found: {name!r}. Available skills: {available}"
        return f"## Skill: {name}\n\n{body}"

    def read_prompt() -> str:
        """Return the full current system prompt text."""
        return current_prompt

    def list_history() -> str:
        """Return a markdown table of evolution cycles with score trajectory and mutations."""
        if not history:
            return "No evolution history available."

        lines: list[str] = [
            "## Evolution History",
            "",
            "| Cycle | Score | Structural | Decision | Mutations |",
            "| --- | --- | --- | --- | --- |",
        ]

        for record in history:
            structural = f"{record.structural_score:.2f}" if record.structural_score is not None else "N/A"
            mutation_parts: list[str] = []
            if record.mutation is not None:
                m = record.mutation
                if m.prompt_modified:
                    mutation_parts.append("prompt")
                if m.skills_added:
                    mutation_parts.append(f"+{len(m.skills_added)} skill(s)")
                if m.skills_modified:
                    mutation_parts.append(f"~{len(m.skills_modified)} skill(s)")
                if m.skills_removed:
                    mutation_parts.append(f"-{len(m.skills_removed)} skill(s)")
            mutations_str = ", ".join(mutation_parts) if mutation_parts else "none"
            lines.append(
                f"| {record.cycle} | {record.batch_score:.2f}"
                f" | {structural} | {record.gate_decision} | {mutations_str} |"
            )

        lines.append("")
        lines.append("### Cycle Reasoning")
        for record in history:
            if record.mutation and record.mutation.evolver_reasoning:
                lines.append(f"- **Cycle {record.cycle}**: {record.mutation.evolver_reasoning}")

        return "\n".join(lines)

    def read_cycle(cycle_number: int) -> str:
        """Return detailed info about a specific past cycle."""
        record = next((r for r in history if r.cycle == cycle_number), None)
        if record is None:
            available = ", ".join(str(r.cycle) for r in history) or "none"
            return f"Cycle {cycle_number} not found. Available cycles: {available}"

        lines: list[str] = [f"## Cycle {record.cycle}"]
        lines.append(f"Batch score: {record.batch_score:.3f}")
        if record.structural_score is not None:
            lines.append(f"Structural score: {record.structural_score:.3f}")
        lines.append(f"Gate decision: {record.gate_decision}")
        lines.append(f"Workspace version before: {record.workspace_version_before}")
        lines.append(f"Workspace version after: {record.workspace_version_after}")
        lines.append(f"Timestamp: {record.timestamp.isoformat()}")
        lines.append(f"Trials ({len(record.trial_ids)}): {', '.join(record.trial_ids)}")

        if record.discipline_scores:
            lines.append("\n### Discipline Scores")
            for ds in record.discipline_scores:
                structural_sim = (
                    f", structural similarity: {ds.mean_structural_similarity:.2f}"
                    if ds.mean_structural_similarity is not None
                    else ""
                )
                lines.append(
                    f"- {ds.discipline}: reward={ds.mean_reward:.2f},"
                    f" field pass rate={ds.field_pass_rate:.2f}"
                    f"{structural_sim} ({ds.task_count} tasks)"
                )

        if record.mutation is not None:
            m = record.mutation
            lines.append("\n### Mutations")
            lines.append(f"Prompt modified: {m.prompt_modified}")
            if m.skills_added:
                lines.append(f"Skills added: {', '.join(m.skills_added)}")
            if m.skills_modified:
                lines.append(f"Skills modified: {', '.join(m.skills_modified)}")
            if m.skills_removed:
                lines.append(f"Skills removed: {', '.join(m.skills_removed)}")
            if m.memory_entries_added:
                lines.append(f"Memory entries added: {m.memory_entries_added}")
            if m.evolver_reasoning:
                lines.append(f"\nEvolver reasoning: {m.evolver_reasoning}")
        else:
            lines.append("\n### Mutations\nNo mutations recorded.")

        return "\n".join(lines)

    def field_detail(field_name: str) -> str:
        """Return all observations for a field with PASS/FAIL status and masked error direction.

        Raw expected/actual values are never exposed — only the direction of error.
        """
        matching: list[tuple[EvolutionObservation, float, str | None]] = []

        for obs in observations:
            for fs in obs.enrichment.field_scores:
                if fs.field_name == field_name:
                    direction: str | None = None
                    if fs.reward < 1.0 and fs.expected is not None and fs.actual is not None:
                        direction = _describe_error_direction(fs.expected, fs.actual)
                    matching.append((obs, fs.reward, direction))

        if not matching:
            return f"No observations found for field: {field_name!r}"

        pass_count = sum(1 for _, reward, _ in matching if reward >= 1.0)
        fail_count = len(matching) - pass_count

        lines: list[str] = [
            f"## Field: {field_name}",
            f"Total observations: {len(matching)}, PASS: {pass_count}, FAIL: {fail_count}",
            "",
            "| Trial ID | Status | Error Direction |",
            "| --- | --- | --- |",
        ]

        for obs, reward, direction in matching:
            status = "PASS" if reward >= 1.0 else "FAIL"
            direction_str = direction if direction is not None else "-"
            lines.append(f"| {obs.trial.trial_id} | {status} | {direction_str} |")

        return "\n".join(lines)

    def search_traces(pattern: str) -> str:
        """Search all traces for a pattern (case-insensitive) in actions, errors, and reasoning."""
        pattern_lower = pattern.lower()
        matches: list[str] = []

        for obs in observations:
            digest = obs.enrichment.trace_digest
            if digest is None:
                continue

            trial_id = obs.trial.trial_id
            found_in: list[str] = []

            for action in digest.key_actions:
                if pattern_lower in action.lower():
                    found_in.append(f"action: {action}")

            for error in digest.errors:
                if pattern_lower in error.lower():
                    found_in.append(f"error: {error}")

            for reasoning in digest.agent_reasoning:
                if pattern_lower in reasoning.lower():
                    found_in.append(f"reasoning: {reasoning}")

            for text in found_in:
                if len(matches) >= 30:
                    break
                matches.append(f"[{trial_id}] {text}")

            if len(matches) >= 30:
                break

        if not matches:
            return f"No matches found for pattern: {pattern!r}"

        lines = [f"## Search results for {pattern!r} ({len(matches)} match(es))"]
        lines.extend(matches)
        return "\n".join(lines)

    def read_graveyard(limit: int = 5) -> str:
        """Return recent failed mutations with diagnostic details."""
        if graveyard is None or graveyard.size == 0:
            return "No failed mutations in graveyard."

        entries = graveyard.browse(limit=limit)
        lines: list[str] = [f"## Failed Mutations ({graveyard.size} total, showing {len(entries)})"]

        for entry in entries:
            lines.append(f"\n### Cycle {entry.cycle} — {entry.strategy}")
            score_line = f"Score: {entry.score_before:.3f} → {entry.score_after:.3f} ({entry.failure_reason})"
            lines.append(score_line)
            lines.append(f"Mutation: {entry.mutation_description}")

            if entry.field_failures:
                field_lines = [f"  - {f}: {d}" for f, d in entry.field_failures.items()]
                lines.append("Field failures:\n" + "\n".join(field_lines))

            if entry.detected_patterns:
                lines.append(f"Patterns: {', '.join(entry.detected_patterns)}")

            if entry.mutation_actions:
                action_strs = []
                for a in entry.mutation_actions:
                    if a.get("skill_name"):
                        action_strs.append(f"{a['action_type']}({a['skill_name']})")
                    else:
                        action_strs.append(a["action_type"])
                lines.append(f"Actions: {', '.join(action_strs)}")

            if entry.investigation_summary:
                lines.append(f"Investigation: {entry.investigation_summary}")

        return "\n".join(lines)

    return {
        "read_trace": read_trace,
        "read_skill": read_skill,
        "read_prompt": read_prompt,
        "list_history": list_history,
        "read_cycle": read_cycle,
        "field_detail": field_detail,
        "search_traces": search_traces,
        "read_graveyard": read_graveyard,
    }
