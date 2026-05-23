# ABOUTME: Deterministic skill seeding from detected behavioral patterns.
# ABOUTME: Maps known anti-pattern names to pre-authored SkillEntry templates.

from __future__ import annotations

from collections.abc import Sequence

from aec_bench.contracts.evolution import SkillEntry
from aec_bench.evolution.analysis import BehavioralPattern

# Static mapping of behavioral pattern names to the skill template each pattern warrants.
_PATTERN_SKILLS: dict[str, SkillEntry] = {
    "blind_action": SkillEntry(
        name="verification-checkpoint",
        description="Insert verification steps between consecutive calculations",
        body=(
            "## Verification Checkpoint Protocol\n\n"
            "After every 2-3 calculation steps, STOP and verify:\n\n"
            "1. Re-read the requirement you are addressing\n"
            "2. Check your intermediate values against expected ranges\n"
            "3. Verify units are consistent throughout\n"
            "4. Only proceed once you are confident the intermediate result is correct\n\n"
            "A wrong intermediate value will cascade through all subsequent calculations."
        ),
    ),
    "no_verification": SkillEntry(
        name="mandatory-verification",
        description="Always verify final output before submitting",
        body=(
            "## Mandatory Final Verification\n\n"
            "Before writing your final output, you MUST:\n\n"
            "1. Re-read the original instruction to confirm all required fields are present\n"
            "2. Check each output value is within a physically reasonable range\n"
            "3. Verify compliance flags match the calculated values\n"
            "4. Confirm the output JSON field names match exactly what was requested\n\n"
            "Never submit without completing this checklist."
        ),
    ),
    "analysis_paralysis": SkillEntry(
        name="action-forcing",
        description="Force execution after reasoning — do not deliberate endlessly",
        body=(
            "## Action-Forcing Protocol\n\n"
            "If you have spent 2+ turns reasoning without executing a tool call:\n\n"
            "1. STOP deliberating\n"
            "2. Identify the single most important unknown\n"
            "3. Execute one concrete action to resolve it\n"
            "4. Re-assess after seeing the result\n\n"
            "Thinking without acting is wasted computation. Execute, observe, adjust."
        ),
    ),
    "redundant_verification": SkillEntry(
        name="progressive-verification",
        description="Verify once per computation step, not repeatedly",
        body=(
            "## Progressive Verification Protocol\n\n"
            "After each computation step, verify ONCE:\n"
            "1. Check the result is within expected range\n"
            "2. Confirm units are correct\n"
            "3. Move to the next step\n\n"
            "Do NOT re-verify the same result. Multiple checks on the same value "
            "waste turns without adding confidence. Verify, record, proceed."
        ),
    ),
    "no_exploration": SkillEntry(
        name="read-before-act",
        description="Read and understand the task before executing any calculations",
        body=(
            "## Read Before Act Protocol\n\n"
            "Before ANY calculation or tool use:\n"
            "1. Read the full task instruction\n"
            "2. Identify all required output fields\n"
            "3. Note available tools and their usage\n"
            "4. Plan your approach\n\n"
            "Starting execution before understanding the task leads to wrong methods, "
            "missed fields, and wasted computation."
        ),
    ),
}


def compute_seed_skills(
    patterns: Sequence[BehavioralPattern],
    existing_skill_names: set[str],
    budget_remaining: int | None = None,
) -> list[SkillEntry]:
    """Return the set of skills to seed based on detected behavioral patterns.

    For each pattern (in order), look up its corresponding skill template.
    Skip patterns with no known mapping. Skip templates already present in the
    workspace. Stop early once budget_remaining is reached (if provided).
    """
    seeds: list[SkillEntry] = []

    for pattern in patterns:
        if budget_remaining is not None and len(seeds) >= budget_remaining:
            break

        template = _PATTERN_SKILLS.get(pattern.name)
        if template is None:
            continue

        if template.name in existing_skill_names:
            continue

        seeds.append(template)

    return seeds
