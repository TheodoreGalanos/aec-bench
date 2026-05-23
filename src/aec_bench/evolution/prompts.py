# ABOUTME: Prompt builder functions for the evolver LLM in the evolution domain.
# ABOUTME: Constructs system and analysis prompts from workspace and observation data.

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from aec_bench.contracts.evolution import DisciplineScore, WorkspaceManifest
from aec_bench.evolution.analysis import BehavioralPattern, GraduatedScope


def load_evolution_program(workspace_root: Path | None = None) -> str:
    """Load the evolution program document.

    Checks for a workspace-level ``program.md`` first (allows per-workspace
    customisation). Falls back to the default program bundled with the package.
    """
    if workspace_root is not None:
        custom = workspace_root / "program.md"
        if custom.exists():
            return custom.read_text(encoding="utf-8")

    # Load the default program from the package
    default_path = Path(__file__).parent / "default_program.md"
    return default_path.read_text(encoding="utf-8")


_RESPONSE_FORMAT_SECTION = """\
## Response Format

Return your changes as a JSON object:

```json
{
  "actions": [
    {
      "type": "write_skill",
      "name": "skill-name-in-kebab-case",
      "description": "One sentence describing when this skill applies",
      "discipline": "electrical",
      "body": "## Skill Title\\n\\nSkill content in markdown..."
    },
    {
      "type": "modify_prompt",
      "content": "Full updated system prompt text..."
    }
  ],
  "reasoning": "Brief explanation of why these changes address the analysis findings."
}
```

Action types:
- `write_skill` — Create a new skill (requires: name, description, body; optional: discipline)
- `modify_skill` — Update an existing skill (requires: name, body; optional: description)
- `delete_skill` — Remove a skill (requires: name)
- `modify_prompt` — Replace the system prompt (requires: content)

If you determine no changes are needed, return: {"actions": [], "reasoning": "..."}"""


def build_evolver_system_prompt(manifest: WorkspaceManifest) -> str:
    """Return the evolver's system prompt populated from a WorkspaceManifest.

    Describes the workspace structure, available investigation tools, workflow,
    skill format, constraints, and mutation limits the evolver must respect.
    """
    evolvable_layers_str = ", ".join(manifest.evolvable_layers)

    return f"""\
You are an evolution agent that improves an engineering benchmark agent by modifying its workspace.

## Workspace Structure
- prompts/system.md — the agent's system prompt
- skills/{{name}}/SKILL.md — domain-knowledge skills (YAML frontmatter + markdown body)
- memory/*.jsonl — episodic memory (append-only)

## Your Tools — Investigation
Use these tools to diagnose agent failures before proposing changes:

- `read_trace(trial_id)` — Load the full trace for a trial: bond sequence, tool calls, errors, \
reasoning steps, and per-field results. Use this to understand exactly what the agent did and \
where it went wrong.
- `read_skill(name)` — Read the complete body of a skill. Use before modifying a skill to \
understand its current content.
- `read_prompt()` — Read the full current system prompt. Always read before proposing prompt \
changes.
- `list_history()` — Retrieve the score trajectory and mutation summaries from all prior \
evolution cycles. Use this to avoid repeating ineffective changes.
- `read_cycle(cycle_number)` — Get detailed information about a specific past cycle, including \
what changes were made and whether they improved performance.
- `field_detail(field_name)` — Retrieve per-trial failures for a specific field with masked \
error direction (too high / too low). Use to understand the nature of failures without seeing \
exact values.
- `search_traces(pattern)` — Grep across all traces for a specific string or pattern. Use to \
find common errors, tool usage patterns, or reasoning text across multiple trials.

## Workflow
IMPORTANT: You have a strict budget of ~8 tool calls. After investigating, you MUST return
your EvolverResponse with actions. Do not keep calling tools indefinitely.

1. **Read the brief** — Identify the biggest problems (worst fields, lowest disciplines).
2. **Investigate** (3-4 tool calls max) — `field_detail` on the worst field, `read_trace`
   on 1 failing trial, `list_history` to check prior attempts.
3. **Review** (1-2 tool calls) — `read_skill` or `read_prompt` only for what you'll modify.
4. **STOP and return your response** — Return your EvolverResponse with concrete actions.
   Do not make more tool calls after step 3. Decide and commit.

## Skill Format
Skills use YAML frontmatter + markdown body:
---
name: skill-name
description: One sentence describing when this skill applies
discipline: electrical (optional)
---
## Skill content here

## Constraints
- Skills must be under 2000 characters
- Skill budget: {manifest.skill_budget} maximum skills
- Evolvable layers: {evolvable_layers_str}
- FORBIDDEN: timeout handling, package installation tips, generic debugging advice,
  command chaining tips
- REQUIRED: domain-specific engineering knowledge, formulas, standards references,
  verification steps, common pitfalls
- Make TARGETED changes based on the analysis. Quality over quantity.
- If the analysis shows specific failing fields or disciplines, focus there.

## Mutation Limits Per Cycle
The number of actions you may take depends on the scope assigned:

- **MINIMAL** scope: at most 1 action
- **TARGETED** scope: at most 3 actions
- **COMPREHENSIVE** scope: at most 5 actions

Prefer modifying existing skills over creating new ones. Each action should address a specific \
diagnosed failure. If you need more changes than the limit allows, pick the highest-impact ones."""


def build_evolution_analysis_prompt(
    *,
    batch_score: float,
    discipline_scores: Sequence[DisciplineScore],
    patterns: Sequence[BehavioralPattern],
    scope: GraduatedScope,
    field_failure_rates: dict[str, float],
    workspace_skill_count: int,
    workspace_prompt_length: int,
    current_prompt: str = "",
    current_skills: Sequence[tuple[str, str]] = (),
    task_instruction: str = "",
    field_details_map: dict[str, tuple[str, str]] | None = None,
    structural_score: float | None = None,
) -> str:
    """Build the per-cycle user prompt containing analysis data for the evolver.

    Includes batch score summary, per-discipline performance, detected behavioral
    patterns, field failure rates, current workspace state (with full prompt and
    skill contents), task instruction, and scope-specific instructions.
    """
    sections: list[str] = []

    # 1. Batch summary
    sections.append(f"## Batch Summary\nBatch score: {batch_score:.0%}")

    # 2. Per-discipline performance
    if discipline_scores:
        rows = [
            "## Per-Discipline Performance",
            "| Discipline | Tasks | Mean Reward | Field Pass Rate |",
            "| --- | --- | --- | --- |",
        ]
        for ds in discipline_scores:
            rows.append(f"| {ds.discipline} | {ds.task_count} | {ds.mean_reward:.2f} | {ds.field_pass_rate:.2f} |")
        sections.append("\n".join(rows))
    else:
        sections.append("## Per-Discipline Performance\nNo discipline data available.")

    # 3. Detected behavioral patterns
    if patterns:
        pattern_lines = ["## Detected Behavioral Patterns"]
        for p in patterns:
            affected = ", ".join(p.affected_trial_ids)
            pattern_lines.append(
                f"- **{p.name}** (count: {p.count}): {p.description}\n"
                f"  Affected trials: {affected}\n"
                f"  Use query_trace to investigate these trials."
            )
        sections.append("\n".join(pattern_lines))
    else:
        sections.append("## Detected Behavioral Patterns\nNo recurring patterns detected.")

    # 4. Field failure rates (sorted worst first, masked feedback level)
    details = field_details_map or {}
    if field_failure_rates:
        sorted_fields = sorted(field_failure_rates.items(), key=lambda x: x[1], reverse=True)
        field_lines = ["## Field Failure Rates"]
        for field_name, rate in sorted_fields:
            detail = details.get(field_name)
            if detail:
                expected, actual = detail
                direction = _describe_error_direction(expected, actual)
                field_lines.append(f"- **{field_name}**: {rate:.0%} failure rate ({direction})")
            else:
                field_lines.append(f"- {field_name}: {rate:.0%} failure rate")
        sections.append("\n".join(field_lines))
    else:
        sections.append("## Field Failure Rates\nNo field failure data available.")

    # 5. Structural quality section
    if structural_score is not None:
        quality_assessment = (
            "good process discipline"
            if structural_score >= 0.7
            else (
                "the agent's behavioral process needs improvement"
                " — consider prompt changes that encourage verification steps"
            )
        )
        ideal = "Explore \u2192 Deliberate \u2192 Execute \u2192 Verify"
        sections.append(
            f"## Structural Quality\n"
            f"Behavioral process score: {structural_score:.2f} "
            f"(cosine similarity to ideal agent behavior pattern)\n\n"
            f"- 1.0 = agent follows the ideal {ideal} pattern\n"
            f"- 0.0 = agent behavior is chaotic/random\n"
            f"- Current score {structural_score:.2f} suggests "
            f"{quality_assessment}"
        )

    # 6. Task instruction (what the agent is asked to solve)
    if task_instruction:
        # Truncate long instructions to keep the prompt reasonable
        truncated = task_instruction[:2000]
        if len(task_instruction) > 2000:
            truncated += "\n\n[... truncated ...]"
        sections.append(f"## Task Instruction (what the agent sees)\n```\n{truncated}\n```")

    # 7. Current workspace contents
    ws_lines = [
        "## Current Workspace",
        f"{workspace_skill_count} skills, prompt length {workspace_prompt_length} chars",
    ]
    if current_prompt:
        ws_lines.append(f"\n### System Prompt\n```\n{current_prompt}\n```")
    if current_skills:
        ws_lines.append("\n### Skills")
        for skill_name, skill_body in current_skills:
            # Show name + first 200 chars of body
            preview = skill_body[:200]
            if len(skill_body) > 200:
                preview += "..."
            ws_lines.append(f"- **{skill_name}**: {preview}")
    sections.append("\n".join(ws_lines))

    # 8. Scope instructions
    scope_text = _build_scope_instructions(scope, discipline_scores)
    sections.append(f"## Your Scope\n{scope_text}")

    # 9. Response format (always last)
    sections.append(_RESPONSE_FORMAT_SECTION)

    return "\n\n".join(sections)


def build_evolution_brief(
    *,
    batch_score: float,
    discipline_scores: Sequence[DisciplineScore],
    patterns: Sequence[BehavioralPattern],
    scope: GraduatedScope,
    field_failure_rates: dict[str, float],
    workspace_skill_count: int,
    workspace_prompt_length: int,
    skill_names: Sequence[str] = (),
    trial_ids: Sequence[str] = (),
    structural_score: float | None = None,
    graveyard_size: int = 0,
) -> str:
    """Build a slim per-cycle brief for tool-based evolvers.

    Summarises the situation without embedding full prompt text, skill bodies,
    or task instruction text. Directs the evolver to use investigation tools
    (read_trace, field_detail, read_skill, read_prompt) for specifics.
    """
    sections: list[str] = []

    # 1. Batch summary
    sections.append(f"## Batch Summary\nBatch score: {batch_score:.0%}")

    # 2. Per-discipline performance
    if discipline_scores:
        rows = [
            "## Per-Discipline Performance",
            "| Discipline | Tasks | Mean Reward | Field Pass Rate |",
            "| --- | --- | --- | --- |",
        ]
        for ds in discipline_scores:
            rows.append(f"| {ds.discipline} | {ds.task_count} | {ds.mean_reward:.2f} | {ds.field_pass_rate:.2f} |")
        sections.append("\n".join(rows))
    else:
        sections.append("## Per-Discipline Performance\nNo discipline data available.")

    # 3. Detected behavioral patterns
    if patterns:
        pattern_lines = ["## Detected Behavioral Patterns"]
        for p in patterns:
            affected = ", ".join(p.affected_trial_ids)
            pattern_lines.append(f"- **{p.name}** (count: {p.count}): {p.description}\n  Affected trials: {affected}")
        sections.append("\n".join(pattern_lines))
    else:
        sections.append("## Detected Behavioral Patterns\nNo recurring patterns detected.")

    # 4. Field failure rates — names + rates only; full details via tool
    if field_failure_rates:
        sorted_fields = sorted(field_failure_rates.items(), key=lambda x: x[1], reverse=True)
        field_lines = ["## Field Failure Rates"]
        field_lines.append("Use `field_detail(name)` to get specifics on any field's expected vs actual values.")
        for field_name, rate in sorted_fields:
            field_lines.append(f"- {field_name}: {rate:.0%} failure rate")
        sections.append("\n".join(field_lines))
    else:
        sections.append("## Field Failure Rates\nNo field failure data available.")

    # 5. Structural quality
    if structural_score is not None:
        quality_assessment = (
            "good process discipline"
            if structural_score >= 0.7
            else (
                "the agent's behavioral process needs improvement"
                " — consider prompt changes that encourage verification steps"
            )
        )
        ideal = "Explore \u2192 Deliberate \u2192 Execute \u2192 Verify"
        sections.append(
            f"## Structural Quality\n"
            f"Behavioral process score: {structural_score:.2f} "
            f"(cosine similarity to ideal agent behavior pattern)\n\n"
            f"- 1.0 = agent follows the ideal {ideal} pattern\n"
            f"- 0.0 = agent behavior is chaotic/random\n"
            f"- Current score {structural_score:.2f} suggests "
            f"{quality_assessment}"
        )

    # 6. Available trials — IDs only; full traces via tool
    if trial_ids:
        trial_lines = [
            "## Available Trials",
            "Use `read_trace(trial_id)` to inspect a specific agent run.",
        ]
        for tid in trial_ids:
            trial_lines.append(f"- {tid}")
        sections.append("\n".join(trial_lines))
    else:
        sections.append("## Available Trials\nNo trial IDs provided.")

    # 7. Workspace summary — skill names only, no bodies; body via tool
    ws_lines = [
        "## Workspace Summary",
        f"{workspace_skill_count} skills, prompt length {workspace_prompt_length} chars",
        "Use `read_skill(name)` to read a skill body. Use `read_prompt()` to read the full prompt.",
    ]
    if skill_names:
        ws_lines.append("Skills available:")
        for name in skill_names:
            ws_lines.append(f"- {name}")
    sections.append("\n".join(ws_lines))

    # 8. Scope instructions
    scope_text = _build_scope_instructions(scope, discipline_scores)
    sections.append(f"## Your Scope\n{scope_text}")

    # 9. How to proceed
    sections.append(
        "## How to Proceed\n"
        "1. Investigate failing fields using `field_detail(name)` to understand error directions.\n"
        "2. Use `read_trace(trial_id)` on affected trials to see what the agent actually did.\n"
        "3. Check edit history before duplicating work.\n"
        "4. Review the current workspace: `read_prompt()` for the system prompt, "
        "`read_skill(name)` for skill bodies.\n"
        "5. Propose targeted changes via actions."
    )

    # 10. Graveyard teaser
    if graveyard_size > 0:
        sections.append(
            f"## Failed Mutations\n"
            f"{graveyard_size} previous mutation(s) were rejected."
            f" Use `read_graveyard()` to inspect failure details."
        )

    return "\n\n".join(sections)


def _build_scope_instructions(
    scope: GraduatedScope,
    discipline_scores: Sequence[DisciplineScore],
) -> str:
    """Return the scope instruction block based on the graduated scope level.

    For scopes that reference the weakest discipline, the discipline with the
    lowest mean_reward is identified from discipline_scores.
    """
    if scope == GraduatedScope.SKIP:
        return "Performance is excellent and stable. Do not make changes."

    if scope == GraduatedScope.MINIMAL:
        return "Performance is high. You may modify at most 1 skill. No prompt changes."

    weakest = _find_weakest_discipline(discipline_scores)

    if scope == GraduatedScope.TARGETED:
        target = weakest if weakest else "the weakest discipline"
        return f"Focus on the weakest discipline: {target}. Modify skills targeting that discipline only."

    # COMPREHENSIVE
    target = weakest if weakest else "the weakest discipline"
    return (
        f"Performance needs improvement. You may modify the prompt and skills. "
        f"Focus on the weakest discipline ({target}) and the highest-failure fields."
    )


def _describe_error_direction(expected: str, actual: str) -> str:
    """Describe the error direction without revealing exact values.

    Returns a masked description like "agent's value was too high" or
    "agent produced wrong type" — enough for the evolver to understand
    what kind of mistake the agent made without leaking test answers.
    """
    try:
        exp_f = float(expected)
        act_f = float(actual)
    except (ValueError, TypeError):
        return "agent produced incorrect value"

    if exp_f == 0.0:
        return "expected zero but agent produced non-zero" if act_f != 0.0 else "correct"

    ratio = act_f / exp_f if exp_f != 0 else float("inf")
    if ratio > 1.5:
        return "agent's value was significantly too high"
    if ratio > 1.05:
        return "agent's value was slightly too high"
    if ratio < 0.5:
        return "agent's value was significantly too low"
    if ratio < 0.95:
        return "agent's value was slightly too low"
    return "agent's value was close but outside tolerance"


def _find_weakest_discipline(discipline_scores: Sequence[DisciplineScore]) -> str | None:
    """Return the name of the discipline with the lowest mean_reward, or None if empty."""
    if not discipline_scores:
        return None
    return min(discipline_scores, key=lambda ds: ds.mean_reward).discipline
