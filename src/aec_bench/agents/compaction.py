# ABOUTME: Structured compaction input builder for RLM history summarisation.
# ABOUTME: Extracts trajectory data into a structured format for the compaction LLM.

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any


def build_compaction_input(
    variables: dict[str, Any],
    scratchpad: dict[str, Any],
    template_status: dict[str, Any] | None,
    trajectory_steps: Sequence[dict[str, Any]],
    turn_count: int,
    tokens_used: int,
) -> dict[str, Any]:
    """Build structured input for the compaction agent from REPL + trajectory state."""
    documents_read: list[str] = []
    extract_calls: list[dict[str, Any]] = []
    composition_calls: list[dict[str, Any]] = []
    errors: list[str] = []

    for step in trajectory_steps:
        code = step.get("code", "")
        # Detect document reads
        if "open(" in code and ("/workspace/" in code or "READ(" in code):
            documents_read.append(code.split('"')[1] if '"' in code else code[:100])
        # Detect errors
        if step.get("error"):
            errors.append(step["error"][:200])
        # Categorise sub-calls
        for sc in step.get("subcalls", []):
            if sc.get("type") == "extract":
                extract_calls.append(sc)
            elif sc.get("type") in ("llm_query", "summarise"):
                composition_calls.append(sc)

    return {
        "variables": variables,
        "scratchpad": scratchpad,
        "template_status": template_status,
        "documents_read": documents_read,
        "extract_calls": extract_calls,
        "composition_calls": composition_calls,
        "errors": errors,
        "turn_count": turn_count,
        "tokens_used": tokens_used,
    }


def build_compaction_prompt(compaction_input: dict[str, Any]) -> str:
    """Build the prompt sent to the compaction agent."""
    parts: list[str] = [
        "Summarise the agent's progress so far. Produce a structured summary with these sections:\n",
        "1. **Documents read** — what was read, key facts from each",
        "2. **Extracted data** — variable name, what it contains, why it matters",
        "3. **Work completed** — which template sections filled, key content",
        "4. **Work remaining** — which sections still need filling, their dependencies",
        "5. **Approach taken** — decisions or strategies the agent chose",
        "6. **Known issues** — errors, dead ends, things that didn't work\n",
        "--- Agent State ---\n",
    ]

    variables = compaction_input.get("variables", {})
    if variables:
        var_lines = json.dumps(variables, indent=2, default=str)
        parts.append(f"REPL Variables:\n{var_lines}\n")

    scratchpad = compaction_input.get("scratchpad", {})
    if scratchpad:
        sp_lines = json.dumps(scratchpad, indent=2, default=str)
        parts.append(f"Scratchpad (NOTE'd data):\n{sp_lines}\n")

    tpl = compaction_input.get("template_status")
    if tpl:
        parts.append(
            f"Template: {tpl.get('completed', 0)}/{tpl.get('total', 0)} sections filled. "
            f"Pending: {', '.join(tpl.get('pending', []))}\n"
        )

    docs = compaction_input.get("documents_read", [])
    if docs:
        parts.append(f"Documents read: {', '.join(docs)}\n")

    extracts = compaction_input.get("extract_calls", [])
    if extracts:
        parts.append(f"Extract calls made: {len(extracts)}\n")

    compositions = compaction_input.get("composition_calls", [])
    if compositions:
        parts.append(f"Composition calls (llm_query/summarise): {len(compositions)}\n")

    errors = compaction_input.get("errors", [])
    if errors:
        parts.append(f"Errors encountered: {len(errors)}\n")
        for err in errors[:5]:
            parts.append(f"  - {err}\n")

    parts.append(f"\nTurns used: {compaction_input['turn_count']} | Tokens used: {compaction_input['tokens_used']:,}\n")

    return "\n".join(parts)
