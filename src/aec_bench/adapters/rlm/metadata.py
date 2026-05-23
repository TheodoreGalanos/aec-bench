# ABOUTME: Iteration metadata extraction and formatting for the RLM adapter.
# ABOUTME: Produces constant-size metadata appended to model history between REPL iterations.

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from aec_bench.adapters.rlm.engine import ExecutionResult

if TYPE_CHECKING:
    from aec_bench.adapters.rlm.template import TemplateStatus


def format_iteration_metadata(
    *,
    result: ExecutionResult | None,
    variables: dict[str, str],
    iteration: int,
    token_budget_pct: float,
    budget_warning_threshold: float = 80.0,
    template_status: TemplateStatus | None = None,
) -> str:
    """Format compact metadata for the model's history between iterations.

    This is what the model sees after each code execution. It includes:
    - Iteration number
    - Execution status (success/error)
    - Variables in scope (names and types only)
    - Truncated stdout summary
    - Token budget warning when threshold is exceeded
    """
    lines: list[str] = []
    lines.append(f"[Iteration {iteration}]")

    if result is not None:
        if result.error:
            lines.append("Status: ERROR")
            error_summary = result.error.strip().split("\n")[-1]
            lines.append(f"Error: {error_summary}")
        else:
            lines.append("Status: OK")

        if result.stdout.strip():
            stdout_preview = textwrap.shorten(result.stdout.strip(), width=200, placeholder="...")
            lines.append(f"Output preview: {stdout_preview}")

        if result.variables_changed:
            lines.append(f"New/changed variables: {', '.join(result.variables_changed)}")
    else:
        lines.append("Status: no code executed")

    if variables:
        var_list = ", ".join(f"{n}: {t}" for n, t in sorted(variables.items()))
        lines.append(f"Variables in scope: {var_list}")

    if template_status is not None:
        lines.append(f"Template: {template_status.completed_sections}/{template_status.total_sections} sections filled")
        if template_status.unlocked:
            lines.append(f"Unlocked sections: {', '.join(template_status.unlocked)}")

    if token_budget_pct >= budget_warning_threshold:
        lines.append(f"WARNING: Token budget {token_budget_pct:.0f}% consumed. Consider finalising results.")

    return "\n".join(lines)
