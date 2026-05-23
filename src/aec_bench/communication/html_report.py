# ABOUTME: Standalone HTML report builder for evaluation artifacts.
# ABOUTME: Generates a self-contained HTML file with inline CSS/JS and embedded data.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aec_bench.evaluation.artifact import EvaluationArtifact


def _reward_color(reward: float) -> str:
    """Return a CSS colour based on the reward value."""
    if reward >= 0.8:
        return "#BFBFBA"  # success
    if reward >= 0.5:
        return "#D4A27F"  # primary / warning
    return "#BF4D43"  # error


def _build_overview_section(summary: dict[str, Any], experiment_id: str) -> str:
    """Build the overview statistics section."""
    n_trials = summary.get("n_trials", 0)
    mean_reward = summary.get("mean_reward", 0.0)
    total_cost = summary.get("total_cost_usd", 0.0)
    return f"""
    <div class="card">
      <h2>Overview</h2>
      <div class="stats-grid">
        <div class="stat">
          <span class="stat-label">Experiment</span>
          <span class="stat-value">{experiment_id}</span>
        </div>
        <div class="stat">
          <span class="stat-label">Total Trials</span>
          <span class="stat-value">{n_trials}</span>
        </div>
        <div class="stat">
          <span class="stat-label">Mean Reward</span>
          <span class="stat-value">{mean_reward:.3f}</span>
        </div>
        <div class="stat">
          <span class="stat-label">Total Cost</span>
          <span class="stat-value">${total_cost:.2f}</span>
        </div>
      </div>
    </div>
    """


def _build_group_table(title: str, group_data: dict[str, dict[str, Any]]) -> str:
    """Build an HTML table for a grouped summary (by adapter or by task prefix)."""
    if not group_data:
        return ""
    rows = []
    for name, metrics in sorted(group_data.items()):
        n = metrics.get("n_trials", 0)
        reward = metrics.get("mean_reward", 0.0)
        cost = metrics.get("total_cost_usd", 0.0)
        color = _reward_color(reward)
        rows.append(
            f'<tr><td>{name}</td><td class="num">{n}</td>'
            f'<td class="num" style="color:{color}">{reward:.3f}</td>'
            f'<td class="num">${cost:.2f}</td></tr>'
        )
    return f"""
    <div class="card">
      <h2>{title}</h2>
      <table>
        <thead>
          <tr><th>Name</th><th>Trials</th><th>Mean Reward</th><th>Cost</th></tr>
        </thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
    </div>
    """


def _build_distribution_section(group_data: dict[str, dict[str, Any]]) -> str:
    """Build a reward distribution section using inline SVG bars."""
    if not group_data:
        return ""
    bar_width = 400
    bar_height = 28
    gap = 6
    items = sorted(group_data.items())
    total_height = len(items) * (bar_height + gap) + 20
    bars = []
    for i, (name, metrics) in enumerate(items):
        reward = metrics.get("mean_reward", 0.0)
        width = max(2, int(reward * bar_width))
        y_pos = i * (bar_height + gap)
        color = _reward_color(reward)
        bars.append(
            f'<g transform="translate(0,{y_pos})">'
            f'<text x="-8" y="{bar_height // 2 + 4}" text-anchor="end" '
            f'fill="#BFBFBA" font-size="13">{name}</text>'
            f'<rect x="0" y="0" width="{width}" height="{bar_height}" '
            f'fill="{color}" rx="3"/>'
            f'<text x="{width + 8}" y="{bar_height // 2 + 4}" '
            f'fill="#BFBFBA" font-size="13">{reward:.3f}</text>'
            f"</g>"
        )
    return f"""
    <div class="card">
      <h2>Reward Distribution</h2>
      <svg width="{bar_width + 200}" height="{total_height}"
           viewBox="-150 -5 {bar_width + 200} {total_height}"
           xmlns="http://www.w3.org/2000/svg">
        {"".join(bars)}
      </svg>
    </div>
    """


def build_evaluation_report(artifact: EvaluationArtifact, output_path: Path) -> Path:
    """Build a standalone HTML evaluation report and write it to output_path.

    The report contains inline CSS, embedded JSON data, and rendered
    tables/charts so it can be opened in any browser without a server.
    """
    summary = artifact.summary
    by_adapter = summary.get("by_adapter", {})
    by_task = summary.get("by_task_prefix", {})

    overview_html = _build_overview_section(summary, artifact.experiment_id)
    adapter_table = _build_group_table("By Adapter", by_adapter)
    task_table = _build_group_table("By Task Prefix", by_task)
    distribution = _build_distribution_section(by_adapter or by_task)

    artifact_json = json.dumps(artifact.model_dump(mode="json"), indent=2, default=str)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>AEC-Bench Evaluation: {artifact.experiment_id}</title>
<style>
  :root {{
    --primary: #D4A27F;
    --bg: #191919;
    --accent: #61AAF2;
    --error: #BF4D43;
    --success: #BFBFBA;
    --card-bg: #222;
    --border: #333;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--success);
    padding: 2rem;
    line-height: 1.5;
  }}
  h1 {{
    color: var(--primary);
    margin-bottom: 1.5rem;
    font-size: 1.8rem;
  }}
  h2 {{
    color: var(--accent);
    margin-bottom: 1rem;
    font-size: 1.3rem;
  }}
  .card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }}
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
  }}
  .stat {{
    display: flex;
    flex-direction: column;
  }}
  .stat-label {{
    font-size: 0.85rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .stat-value {{
    font-size: 1.4rem;
    font-weight: 600;
    color: var(--primary);
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
  }}
  th, td {{
    padding: 0.6rem 1rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }}
  th {{
    color: var(--accent);
    font-weight: 600;
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  td.num {{
    text-align: right;
    font-variant-numeric: tabular-nums;
  }}
  .footer {{
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    font-size: 0.8rem;
    color: #666;
  }}
</style>
</head>
<body>
<h1>AEC-Bench Evaluation Report</h1>

{overview_html}
{adapter_table}
{task_table}
{distribution}

<div class="footer">
  <p>Generated: {artifact.timestamp.isoformat()}</p>
  <p>Framework: aec-bench v{artifact.framework_version}</p>
  <p>Evaluation ID: {artifact.evaluation_id}</p>
</div>

<script type="application/json" id="evaluation-data">
{artifact_json}
</script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
