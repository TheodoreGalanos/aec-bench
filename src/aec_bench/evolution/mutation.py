# ABOUTME: Defines typed prompt and skill mutations for evolution workspaces.
# ABOUTME: Applies validated mutation actions and reports the material changes.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aec_bench.contracts.evolution import MutationSummary
    from aec_bench.evolution.workspace import Workspace


@dataclass(frozen=True)
class MutationAction:
    action_type: str
    skill_name: str | None = None
    skill_description: str | None = None
    skill_discipline: str | None = None
    skill_body: str | None = None
    prompt_content: str | None = None


def apply_mutations(
    actions: Sequence[MutationAction],
    workspace: Workspace,
) -> MutationSummary:
    """Apply a sequence of parsed mutation actions to a workspace.

    Each action is applied in order. write_skill creates a skill (or modifies it if it
    already exists). modify_skill updates an existing skill (or creates it if missing).
    delete_skill removes a skill silently if absent. modify_prompt overwrites system.md.
    Returns a MutationSummary capturing every change made.
    """
    from aec_bench.contracts.evolution import MutationSummary, SkillEntry  # noqa: F811

    skills_added: list[str] = []
    skills_modified: list[str] = []
    skills_removed: list[str] = []
    prompt_modified = False

    for action in actions:
        if action.action_type == "write_skill":
            existing = workspace.read_skill(action.skill_name or "")
            skill = SkillEntry(
                name=action.skill_name or "",
                description=action.skill_description or "",
                discipline=action.skill_discipline,
                body=action.skill_body or "",
            )
            workspace.write_skill(skill)
            if existing is not None:
                skills_modified.append(skill.name)
            else:
                skills_added.append(skill.name)

        elif action.action_type == "modify_skill":
            name = action.skill_name or ""
            existing = workspace.read_skill(name)
            if existing is not None:
                description = action.skill_description if action.skill_description is not None else existing.description
                discipline = action.skill_discipline if action.skill_discipline is not None else existing.discipline
                skill = SkillEntry(
                    name=name,
                    description=description,
                    discipline=discipline,
                    body=action.skill_body or "",
                )
                workspace.write_skill(skill)
                skills_modified.append(name)
            else:
                skill = SkillEntry(
                    name=name,
                    description=action.skill_description or "",
                    discipline=action.skill_discipline,
                    body=action.skill_body or "",
                )
                workspace.write_skill(skill)
                skills_added.append(name)

        elif action.action_type == "delete_skill":
            name = action.skill_name or ""
            existing = workspace.read_skill(name)
            if existing is not None:
                workspace.delete_skill(name)
                skills_removed.append(name)

        elif action.action_type == "modify_prompt":
            workspace.write_prompt(action.prompt_content or "")
            prompt_modified = True

    return MutationSummary(
        prompt_modified=prompt_modified,
        skills_added=skills_added,
        skills_modified=skills_modified,
        skills_removed=skills_removed,
    )
