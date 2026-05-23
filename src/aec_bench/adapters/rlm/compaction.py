# ABOUTME: Context compaction for the RLM adapter — driven by StatePersistenceParams.
# ABOUTME: Supports three strategies: llm_summary (narrative), state_only (listing), full_reset.

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from aec_bench.adapters.rlm.client import RlmClient, RlmMessage
from aec_bench.contracts.constitution import StatePersistenceParams


@dataclass(frozen=True)
class CompactionResult:
    """Summary text and token usage from a compaction call."""

    summary: str
    input_tokens: int
    output_tokens: int


if TYPE_CHECKING:
    from aec_bench.adapters.rlm.engine import ReplEnvironment
    from aec_bench.adapters.rlm.scratchpad import Scratchpad
    from aec_bench.adapters.rlm.template import ReportTemplate, TemplateStatus

_COMPACTION_SYSTEM = "You summarise AI agent work sessions concisely."


def _build_llm_summary_prompt(
    *,
    variables: dict[str, Any],
    scratchpad: dict[str, Any],
    template_status: TemplateStatus | None,
    params: StatePersistenceParams,
) -> str:
    """Build narrative-focused compaction prompt with full state."""
    parts: list[str] = [
        "Summarise the agent's progress so far. Produce a structured summary with:",
        "1. Documents read — what was read, key facts extracted",
        "2. Extracted data — variable name, contents, importance",
        "3. Work completed — sections filled, key content produced",
        "4. Work remaining — unfilled sections, dependencies not yet met",
        "5. Approach taken — strategies chosen, tools used",
        "6. Known issues — errors encountered, dead ends avoided",
    ]

    parts.append("\n--- Agent State ---")

    if params.preserve_variables:
        if variables:
            parts.append(f"Variables:\n{json.dumps(variables, indent=2, default=str)}")
        else:
            parts.append("Variables: (none)")

    if params.preserve_scratchpad:
        if scratchpad:
            parts.append(f"Scratchpad:\n{json.dumps(scratchpad, indent=2, default=str)}")
        else:
            parts.append("Scratchpad: (empty)")

    if template_status is not None:
        status_dict = {
            "completed": template_status.completed_sections,
            "total": template_status.total_sections,
            "filled_sections": template_status.completed,
            "unlocked": template_status.unlocked,
            "pending": template_status.pending,
        }
        parts.append(f"Template status:\n{json.dumps(status_dict, indent=2)}")

    return "\n".join(parts)


def _build_state_only_prompt(
    *,
    variables: dict[str, Any],
    scratchpad: dict[str, Any],
    template_status: TemplateStatus | None,
    params: StatePersistenceParams,
) -> str:
    """Build minimal listing-only prompt (keys/counts, no values)."""
    parts: list[str] = [
        "List the agent's current state without narrative summary.",
        "Produce a concise inventory of what exists in durable state.",
    ]
    parts.append("\n--- Agent State ---")
    if params.preserve_variables and variables:
        var_names = sorted(variables.keys())
        parts.append(f"Variables: {var_names}")
    if params.preserve_scratchpad and scratchpad:
        keys = sorted(scratchpad.keys())
        parts.append(f"Scratchpad keys: {keys}")
    if template_status is not None:
        completed = template_status.completed_sections
        total = template_status.total_sections
        parts.append(f"Template progress: {completed}/{total}")
    return "\n".join(parts)


def _build_full_reset_prompt(
    *,
    template_status: TemplateStatus | None,
) -> str:
    """Build minimal orientation prompt for conversation reset."""
    parts: list[str] = [
        "The agent's conversation is being reset. Produce a minimal orientation note",
        "for the agent to restart work — one short paragraph.",
    ]
    if template_status is not None:
        completed = template_status.completed_sections
        total = template_status.total_sections
        parts.append(f"Template progress on restart: {completed}/{total}")
    return "\n".join(parts)


def build_compaction_prompt(
    *,
    variables: dict[str, Any],
    scratchpad: dict[str, Any],
    template_status: TemplateStatus | None,
    params: StatePersistenceParams,
) -> str:
    """Build the compaction input prompt per the configured strategy."""
    strategy = params.compaction_strategy
    if strategy == "llm_summary":
        return _build_llm_summary_prompt(
            variables=variables,
            scratchpad=scratchpad,
            template_status=template_status,
            params=params,
        )
    if strategy == "state_only":
        return _build_state_only_prompt(
            variables=variables,
            scratchpad=scratchpad,
            template_status=template_status,
            params=params,
        )
    if strategy == "full_reset":
        return _build_full_reset_prompt(template_status=template_status)
    raise ValueError(f"unknown compaction_strategy: {strategy!r}")


def compact(
    *,
    client: RlmClient,
    model: str,
    repl: ReplEnvironment,
    scratchpad: Scratchpad | None,
    template: ReportTemplate | None,
    params: StatePersistenceParams | None = None,
) -> CompactionResult:
    """Run a compaction call driven by the constitutional state-persistence strategy."""
    resolved_params = params or StatePersistenceParams()
    variables = repl.snapshot_variables() if resolved_params.preserve_variables else {}
    sp = scratchpad.snapshot() if (scratchpad and resolved_params.preserve_scratchpad) else {}
    tpl_status = template.get_status() if template else None

    prompt = build_compaction_prompt(
        variables=variables,
        scratchpad=sp,
        template_status=tpl_status,
        params=resolved_params,
    )

    response = client.generate(
        model=model,
        messages=[RlmMessage(role="user", content=prompt)],
        system_prompt=_COMPACTION_SYSTEM,
    )

    return CompactionResult(
        summary=response.output_text,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )
