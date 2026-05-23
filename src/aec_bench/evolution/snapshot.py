# ABOUTME: Workspace snapshot serialiser for the evolution domain.
# ABOUTME: Converts a WorkspaceSnapshot into a single markdown string for agent consumption.

from aec_bench.contracts.evolution import SkillEntry, WorkspaceSnapshot

_DOMAIN_KNOWLEDGE_INTRO = (
    "The following skills contain domain-specific knowledge. Reference them when relevant to the task."
)


def _format_skill(skill: SkillEntry) -> str:
    """Format a single skill entry as a markdown section."""
    parts: list[str] = [f"### {skill.name}"]
    parts.append(f"*{skill.description}*")
    parts.append(skill.body)
    return "\n\n".join(parts)


def serialise_snapshot(snapshot: WorkspaceSnapshot) -> str:
    """Convert a WorkspaceSnapshot into a markdown string for agent consumption.

    If the snapshot has no skills, the system prompt is returned as-is.
    Otherwise a '## Domain Knowledge' section is appended with each skill
    formatted as a named, described markdown block, separated by horizontal rules.
    """
    if not snapshot.skills:
        return snapshot.system_prompt

    skill_blocks = "\n\n---\n\n".join(_format_skill(s) for s in snapshot.skills)
    domain_section = f"## Domain Knowledge\n\n{_DOMAIN_KNOWLEDGE_INTRO}\n\n{skill_blocks}"

    return f"{snapshot.system_prompt}\n\n{domain_section}"
