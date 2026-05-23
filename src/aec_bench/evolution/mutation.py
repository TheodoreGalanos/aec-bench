# ABOUTME: Parses LLM evolver responses into structured mutation action objects.
# ABOUTME: Handles JSON extraction, action type validation, and lenient error collection.

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aec_bench.contracts.evolution import MutationSummary
    from aec_bench.evolution.workspace import Workspace

logger = logging.getLogger(__name__)

# Required fields per action type. Optional fields are accepted but not enforced.
_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "write_skill": ("name", "body"),
    "modify_skill": ("name", "body"),
    "delete_skill": ("name",),
    "modify_prompt": ("content",),
}


@dataclass(frozen=True)
class MutationAction:
    action_type: str
    skill_name: str | None = None
    skill_description: str | None = None
    skill_discipline: str | None = None
    skill_body: str | None = None
    prompt_content: str | None = None


@dataclass(frozen=True)
class ParsedMutationResponse:
    actions: tuple[MutationAction, ...]
    reasoning: str
    parse_errors: tuple[str, ...] = ()


def parse_evolver_response(response: str) -> ParsedMutationResponse:
    """Parse a raw LLM evolver response string into a ParsedMutationResponse.

    Extracts JSON from the response (handles markdown fences and preamble text),
    validates each action, and collects parse errors without raising exceptions.
    """
    json_str = _extract_json(response)

    try:
        payload = json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.debug("Raw JSON extraction (first 500 chars): %s", json_str[:500])
        # Try to repair common LLM JSON issues: unescaped newlines inside strings
        repaired = _repair_json_strings(json_str)
        try:
            payload = json.loads(repaired)
            logger.info("Phase 4: repaired malformed JSON from evolver response")
        except (json.JSONDecodeError, ValueError):
            error_msg = f"Failed to parse JSON from evolver response: {exc}"
            logger.warning(error_msg)
            return ParsedMutationResponse(actions=(), reasoning="", parse_errors=(error_msg,))

    if not isinstance(payload, dict):
        error_msg = "Evolver response JSON is not an object"
        logger.warning(error_msg)
        return ParsedMutationResponse(actions=(), reasoning="", parse_errors=(error_msg,))

    reasoning = str(payload.get("reasoning", ""))
    raw_actions = payload.get("actions", [])

    if not isinstance(raw_actions, list):
        error_msg = "Evolver response 'actions' is not a list"
        logger.warning(error_msg)
        return ParsedMutationResponse(actions=(), reasoning=reasoning, parse_errors=(error_msg,))

    actions: list[MutationAction] = []
    errors: list[str] = []

    for index, raw_action in enumerate(raw_actions):
        action, error = _parse_action(raw_action, index)
        if error is not None:
            logger.warning("Skipping action at index %d: %s", index, error)
            errors.append(error)
        elif action is not None:
            actions.append(action)

    return ParsedMutationResponse(
        actions=tuple(actions),
        reasoning=reasoning,
        parse_errors=tuple(errors),
    )


def _parse_action(raw: object, index: int) -> tuple[MutationAction | None, str | None]:
    """Validate and convert a raw action dict to a MutationAction.

    Returns (action, None) on success or (None, error_message) on failure.
    """
    if not isinstance(raw, dict):
        return None, f"Action at index {index} is not an object"

    action_type = raw.get("type")
    if not isinstance(action_type, str):
        return None, f"Action at index {index} is missing required 'type' field"

    required = _REQUIRED_FIELDS.get(action_type)
    if required is None:
        return None, f"Action at index {index} has unknown type '{action_type}'"

    for field_name in required:
        if field_name not in raw or raw[field_name] is None:
            error = f"Action at index {index} (type='{action_type}') is missing required field '{field_name}'"
            return None, error

    skill_name = _str_or_none(raw.get("name"))
    skill_description = _str_or_none(raw.get("description"))
    skill_discipline = _str_or_none(raw.get("discipline"))
    skill_body = _str_or_none(raw.get("body"))
    prompt_content = _str_or_none(raw.get("content"))

    return (
        MutationAction(
            action_type=action_type,
            skill_name=skill_name,
            skill_description=skill_description,
            skill_discipline=skill_discipline,
            skill_body=skill_body,
            prompt_content=prompt_content,
        ),
        None,
    )


def _repair_json_strings(text: str) -> str:
    """Attempt to repair JSON with unescaped newlines inside string values.

    LLMs frequently produce JSON where string values contain literal newlines
    (e.g. in markdown body fields). This function escapes those newlines so
    json.loads can parse the result.
    """
    # Replace literal newlines inside strings with \\n
    # Strategy: find all string values and escape their contents
    result = []
    in_string = False
    escape_next = False
    for char in text:
        if escape_next:
            result.append(char)
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            result.append(char)
            continue
        if char == '"':
            in_string = not in_string
            result.append(char)
            continue
        if in_string and char == "\n":
            result.append("\\n")
            continue
        if in_string and char == "\t":
            result.append("\\t")
            continue
        result.append(char)
    return "".join(result)


def _extract_json(text: str) -> str:
    """Extract a JSON object string from text that may contain markdown fences or preamble.

    Uses brace-matching rather than regex to handle responses where the JSON
    body itself contains markdown code fences (e.g. skill bodies with ````` blocks).
    """
    # Find the first top-level '{' and match to its closing '}'
    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    # No balanced closing brace found — return from first { to end
    return text[start:]


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


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
