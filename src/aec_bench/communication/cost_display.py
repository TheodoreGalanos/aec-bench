# ABOUTME: Formats an established cost summary for text and HTML reports.
# ABOUTME: Keeps unknown totals distinct from a known zero cost.

from collections.abc import Mapping
from typing import Any


def format_summary_cost(summary: Mapping[str, Any]) -> str:
    total = summary.get("total_cost_usd")
    if total is not None:
        return f"${total:.2f}"
    known = summary.get("known_cost_usd")
    missing = summary.get("n_uncosted")
    if known is not None and missing is not None:
        return f"Unknown (${known:.2f} known; {missing} uncosted)"
    return "Unknown"
