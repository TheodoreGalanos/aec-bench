# ABOUTME: Pure rendering functions for dataset summary cards and detail panes.
# ABOUTME: Used by the Library screen to display dataset and experiment information.

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from aec_bench.contracts.dataset import DatasetManifest
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.tui.widgets.shared import reward_style

# ------------------------------------------------------------------
# Pure rendering functions
# ------------------------------------------------------------------


def _horizontal_bar(value: int, max_value: int, color: str, width: int = 20) -> str:
    """Render a horizontal bar chart segment as Rich markup."""
    if max_value == 0:
        return ""
    bar_len = round(value / max_value * width)
    bar = "\u2501" * bar_len
    return f"[{color}]{bar}[/] {value}"


def render_dataset_card(
    manifest: DatasetManifest,
    all_records: dict[str, list[TrialRecord]],
) -> str:
    """Format a dataset summary card as Rich markup."""
    desc = manifest.description
    dataset_id = f"{manifest.name}@{manifest.version}"
    lines: list[str] = []

    lines.append(f"[bold #D4A27F]{manifest.name}[/] [dim]v{manifest.version}[/]")
    lines.append(f"[dim]{desc.summary}[/]")
    lines.append("")
    lines.append(
        f"  Tasks: [bold]{desc.task_count}[/]  "
        f"Domains: [bold]{len(desc.domains)}[/]  "
        f"Standards: [bold]{len(desc.standards)}[/]  "
        f"Created: [dim]{manifest.created_at.strftime('%Y-%m-%d')}[/]"
    )
    lines.append("")

    if desc.domains:
        lines.append("[bold]Domains[/]")
        max_domain_count = (
            max(sum(1 for t in manifest.tasks if t.domain == d) for d in desc.domains) if manifest.tasks else 1
        )
        for domain in desc.domains:
            count = sum(1 for t in manifest.tasks if t.domain == domain)
            bar = _horizontal_bar(count, max_domain_count, "#61AAF2")
            lines.append(f"  {domain:>12}  {bar}")

    if desc.difficulty_distribution:
        lines.append("")
        lines.append("[bold]Difficulty[/]")
        max_diff = max(desc.difficulty_distribution.values()) if desc.difficulty_distribution else 1
        diff_colors = {"easy": "#61AAF2", "medium": "#D4A27F", "hard": "#BF4D43"}
        for diff, count in desc.difficulty_distribution.items():
            color = diff_colors.get(diff, "#91918D")
            bar = _horizontal_bar(count, max_diff, color)
            lines.append(f"  {diff:>12}  {bar}")

    records = all_records.get(dataset_id, [])
    if records:
        by_exp: dict[str, list[TrialRecord]] = defaultdict(list)
        for r in records:
            by_exp[r.experiment_id].append(r)
        lines.append("")
        lines.append("[bold]Experiments[/]")
        for _exp_id, exp_recs in sorted(by_exp.items()):
            mean = sum(r.evaluation.reward for r in exp_recs) / len(exp_recs)
            model = exp_recs[0].agent.model
            style = reward_style(mean)
            lines.append(f"  [{style}]\u25cf[/] {model} [{style}]{mean:.3f}[/]")

    return "\n".join(lines)


def render_experiment_card(
    manifest: DatasetManifest,
    experiment_id: str,
    records: list[TrialRecord],
) -> str:
    """Format an experiment summary card as Rich markup."""
    if not records:
        return f"[bold]{experiment_id}[/]\n[dim]No trial records.[/dim]"

    rewards = [r.evaluation.reward for r in records]
    n = len(rewards)
    mean = sum(rewards) / n
    passed = sum(1 for r in rewards if r >= 1.0)
    failed = sum(1 for r in rewards if r == 0.0)
    pass_rate = passed / n
    std_dev = (sum((r - mean) ** 2 for r in rewards) / n) ** 0.5
    total_tokens = sum((r.cost.tokens_in or 0) for r in records if r.cost)

    agent_model = records[0].agent.model
    agent_adapter = records[0].agent.adapter
    dataset_ref = f"{manifest.name}@{manifest.version}"

    lines: list[str] = []
    lines.append(f"[bold #D4A27F]{experiment_id}[/]")
    lines.append(f"[dim]on {dataset_ref}[/]")
    lines.append(f"[dim]{agent_adapter} \u00b7 {agent_model} \u00b7 {n} trials[/]")
    lines.append("")

    mean_style = reward_style(mean)
    lines.append(
        f"  Mean: [{mean_style}][bold]{mean:.3f}[/][/]  "
        f"Pass: [{mean_style}]{pass_rate:.0%}[/]  "
        f"Std: [bold]{std_dev:.3f}[/]  "
        f"Tokens: [bold]{total_tokens:,}[/]"
    )
    lines.append("")

    lines.append("[bold]Reward Distribution[/]")
    partial = n - passed - failed
    max_count = max(passed, partial, failed, 1)
    lines.append(f"  {'1.0':>5}  {_horizontal_bar(passed, max_count, '#61AAF2')}")
    if partial > 0:
        lines.append(f"  {'0.x':>5}  {_horizontal_bar(partial, max_count, '#D4A27F')}")
    lines.append(f"  {'0.0':>5}  {_horizontal_bar(failed, max_count, '#BF4D43')}")

    costs = [r.cost.estimated_cost_usd for r in records if r.cost and r.cost.estimated_cost_usd]
    total_cost = sum(costs) if costs else 0.0
    durations = [r.timing.total_seconds for r in records]
    mean_duration = sum(durations) / len(durations) if durations else 0.0
    tokens_per_correct = total_tokens / passed if passed > 0 else 0

    lines.append("")
    lines.append("[bold]Cost & Timing[/]")
    lines.append(
        f"  Est. cost: ${total_cost:.2f}  Mean: {mean_duration:.0f}s  Tokens/correct: {tokens_per_correct:,.0f}"
    )

    if records:
        best = max(records, key=lambda r: r.evaluation.reward)
        worst = min(records, key=lambda r: r.evaluation.reward)
        lines.append("")
        lines.append("[bold]Extremes[/]")
        best_style = reward_style(best.evaluation.reward)
        worst_style = reward_style(worst.evaluation.reward)
        lines.append(
            f"  [{best_style}]\u25b2 Best:[/]  {best.task.task_id} [{best_style}]{best.evaluation.reward:.3f}[/]"
        )
        lines.append(
            f"  [{worst_style}]\u25bc Worst:[/] {worst.task.task_id} [{worst_style}]{worst.evaluation.reward:.3f}[/]"
        )

    return "\n".join(lines)


def render_tasks_detail(manifest: DatasetManifest) -> str:
    """Format the task list detail pane as Rich markup."""
    lines: list[str] = []
    lines.append("[bold]Tasks[/]")
    lines.append("")

    diff_colors = {"easy": "#61AAF2", "medium": "#D4A27F", "hard": "#BF4D43"}

    header = f"  {'Task ID':<35} {'Domain':<12} {'Difficulty':<10} {'Hash':<14}"
    lines.append(f"[bold]{header}[/]")
    lines.append(f"  {'\u2500' * 75}")

    for task in manifest.tasks:
        diff_color = diff_colors.get(task.difficulty, "#91918D")
        lines.append(
            f"  {task.task_id:<35} {task.domain:<12} "
            f"[{diff_color}]{task.difficulty:<10}[/] "
            f"[dim]{task.content_hash[:12]}[/]"
        )

    return "\n".join(lines)


def render_results_detail(
    records: list[TrialRecord],
    manifest: DatasetManifest,
) -> str:
    """Format the results detail pane as Rich markup."""
    if not records:
        return (
            "[dim]No experiment results for this dataset.[/dim]\n"
            "[dim]Run an experiment referencing this dataset first.[/dim]"
        )

    models = {r.agent.model for r in records}

    if len(models) == 1:
        return _render_single_agent_results(records, manifest)
    return _render_multi_agent_results(records, manifest)


def _render_single_agent_results(
    records: list[TrialRecord],
    manifest: DatasetManifest,
) -> str:
    """Format per-task results for a single agent as Rich markup."""
    task_lookup = {t.task_id: t for t in manifest.tasks}
    diff_colors = {"easy": "#61AAF2", "medium": "#D4A27F", "hard": "#BF4D43"}

    lines: list[str] = []
    lines.append("[bold]Per-Task Results[/]")
    lines.append("")

    header = f"  {'Task':<30} {'Domain':<10} {'Diff':<8} {'Reward':>7} {'Tokens':>8} {'Turns':>6}"
    lines.append(f"[bold]{header}[/]")
    lines.append(f"  {'\u2500' * 75}")

    for record in sorted(records, key=lambda r: r.task.task_id):
        task_entry = task_lookup.get(record.task.task_id)
        domain = task_entry.domain if task_entry else "\u2014"
        difficulty = task_entry.difficulty if task_entry else "\u2014"
        diff_color = diff_colors.get(difficulty, "#91918D")

        reward = record.evaluation.reward
        r_style = reward_style(reward)
        tokens = f"{record.cost.tokens_in:,}" if record.cost and record.cost.tokens_in else "\u2014"
        agent_result = record.outputs.agent_result or {}
        turns = str(agent_result.get("turns_used", "\u2014"))

        lines.append(
            f"  {record.task.task_id:<30} {domain:<10} "
            f"[{diff_color}]{difficulty:<8}[/] "
            f"[{r_style}]{reward:>7.3f}[/] "
            f"{tokens:>8} {turns:>6}"
        )

    return "\n".join(lines)


def _render_multi_agent_results(
    records: list[TrialRecord],
    manifest: DatasetManifest,
) -> str:
    """Format agent comparison results as Rich markup."""
    by_model: dict[str, list[TrialRecord]] = defaultdict(list)
    for r in records:
        by_model[r.agent.model].append(r)

    model_means: list[tuple[str, float, int]] = []
    for model, recs in by_model.items():
        mean = sum(r.evaluation.reward for r in recs) / len(recs)
        model_means.append((model, mean, len(recs)))
    model_means.sort(key=lambda x: x[1], reverse=True)

    lines: list[str] = []
    lines.append("[bold]Agent Comparison[/]")
    lines.append("")

    max_mean = max(m for _, m, _ in model_means) if model_means else 1.0
    max_name_len = max(len(m) for m, _, _ in model_means) if model_means else 10

    for model, mean, count in model_means:
        style = reward_style(mean)
        bar_len = round(mean / max(max_mean, 0.001) * 20)
        bar = "\u2501" * bar_len
        lines.append(f"  {model:>{max_name_len}}  [{style}]{bar}[/] [{style}]{mean:.3f}[/] [dim]({count})[/dim]")

    lines.append("")

    all_rewards = [r.evaluation.reward for r in records]
    overall_mean = sum(all_rewards) / len(all_rewards)
    total_tokens = sum((r.cost.tokens_in or 0) for r in records if r.cost)
    best_model = model_means[0][0] if model_means else "\u2014"

    lines.append(
        f"  Best: [bold]{best_model}[/]  "
        f"Overall: [{reward_style(overall_mean)}]{overall_mean:.3f}[/]  "
        f"Tokens: {total_tokens:,}"
    )

    return "\n".join(lines)


def render_integrity_detail(
    manifest: DatasetManifest,
    project_root: Path,
) -> str:
    """Format the integrity check detail pane as Rich markup."""
    from aec_bench.dataset.integrity import verify_dataset_integrity

    result = verify_dataset_integrity(manifest.tasks, project_root=project_root)

    lines: list[str] = []
    lines.append("[bold]Integrity Check[/]")
    lines.append("")

    if result.is_clean:
        lines.append(f"[#61AAF2]\u2713 Clean[/] \u2014 {result.verified}/{len(manifest.tasks)} tasks verified")
    else:
        lines.append(f"[#BF4D43]\u2717 Issues found[/] \u2014 {result.verified}/{len(manifest.tasks)} verified")
        if result.drifted:
            lines.append("")
            lines.append("[bold #D4A27F]Drifted tasks:[/]")
            for task_id in result.drifted:
                lines.append(f"  [#BF4D43]~[/] {task_id}")
        if result.missing:
            lines.append("")
            lines.append("[bold #BF4D43]Missing tasks:[/]")
            for task_id in result.missing:
                lines.append(f"  [#BF4D43]\u2717[/] {task_id}")

    return "\n".join(lines)
