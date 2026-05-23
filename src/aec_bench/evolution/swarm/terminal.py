# ABOUTME: Compact terminal status line for swarm runs.
# ABOUTME: Renders a single updating line with agent count, evals, archive coverage, and budget.

from __future__ import annotations

from aec_bench.contracts.evolution import AgentStatus, SwarmAgentState


def render_status_line(
    agents: list[SwarmAgentState],
    total_evals: int,
    archive_coverage: float,
    archive_size: int,
    archive_total: int,
    best_score: float,
    budget_pct: float,
) -> str:
    """Render a compact single-line status summary for terminal output."""
    active = sum(1 for a in agents if a.status == AgentStatus.ACTIVE)
    total = len(agents)
    cov_pct = int(archive_coverage * 100)
    bud_pct = int(budget_pct * 100)
    return (
        f"agents: {active}/{total} "
        f"| evals: {total_evals} "
        f"| archive: {cov_pct}% ({archive_size}/{archive_total}) "
        f"| best: {best_score:.2f} "
        f"| budget: {bud_pct}%"
    )


def format_event_line(timestamp: str, message: str) -> str:
    """Format a key event for display above the status line."""
    return f"[{timestamp}] {message}"
