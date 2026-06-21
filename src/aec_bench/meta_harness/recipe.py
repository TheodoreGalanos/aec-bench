# ABOUTME: Materializes scriptable meta-harness recipes for candidate-vs-baseline evaluation.
# ABOUTME: Provides shared comparison logic for CLI-generated scripts and docs examples.

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from aec_bench.meta_harness.autonomy import score_process_result
from aec_bench.meta_harness.logic_profile import evaluate_logic_profile
from aec_bench.meta_harness.world_process import build_problem_brief_request


def materialize_harness_comparison_recipe(
    *,
    output_dir: Path,
    task_text: str,
    process_id: str | None = None,
    baseline_world: Path | None = None,
    baseline_run: Path | None = None,
    candidate_world: Path | None = None,
    candidate_run: Path | None = None,
    baseline_experiment: Path | None = None,
    candidate_experiment: Path | None = None,
    models_config: Path | None = None,
    reviewer_models_config: Path | None = None,
    operation_models_config: Path | None = None,
    command_prefix: str = "aec-bench",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    task_path = output_dir / "task.md"
    task_path.write_text(task_text.strip() + "\n", encoding="utf-8")

    request = build_problem_brief_request(task_text=task_text, process_id=process_id)
    recipe = _recipe_payload(
        output_dir=output_dir,
        task_path=task_path,
        intake_request=request,
        baseline_world=baseline_world,
        baseline_run=baseline_run,
        candidate_world=candidate_world,
        candidate_run=candidate_run,
        baseline_experiment=baseline_experiment,
        candidate_experiment=candidate_experiment,
        models_config=models_config,
        reviewer_models_config=reviewer_models_config,
        operation_models_config=operation_models_config,
        command_prefix=command_prefix,
    )

    _write_json(output_dir / "recipe.json", recipe)
    _write_text(output_dir / "README.md", _readme(recipe))
    _write_text(output_dir / "compare_candidate.py", _comparison_script())
    script_path = output_dir / "run_recipe.sh"
    _write_text(script_path, _shell_script(recipe))
    script_path.chmod(0o755)

    return {
        "status": "materialized",
        "recipe_id": recipe["recipe_id"],
        "output_dir": str(output_dir),
        "files": {
            "task": str(task_path),
            "recipe": str(output_dir / "recipe.json"),
            "readme": str(output_dir / "README.md"),
            "run_script": str(script_path),
            "comparison_script": str(output_dir / "compare_candidate.py"),
        },
        "next_commands": [step["command"] for step in recipe["steps"]],
    }


def run_harness_comparison_from_files(
    *,
    brief_path: Path,
    baseline_world_path: Path,
    candidate_world_path: Path,
    baseline_run_path: Path,
    candidate_run_path: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    brief = _load_json(brief_path)
    baseline_world = _load_json(baseline_world_path)
    candidate_world = _load_json(candidate_world_path)
    baseline_run = _load_json(baseline_run_path)
    candidate_run = _load_json(candidate_run_path)
    comparison = compare_harness_runs(
        brief=brief,
        baseline_world=baseline_world,
        candidate_world=candidate_world,
        baseline_run=baseline_run,
        candidate_run=candidate_run,
    )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(output_dir / "comparison.json", comparison)
        _write_text(output_dir / "comparison.md", _comparison_markdown(comparison))
    return comparison


def compare_harness_runs(
    *,
    brief: dict[str, Any],
    baseline_world: dict[str, Any],
    candidate_world: dict[str, Any],
    baseline_run: dict[str, Any],
    candidate_run: dict[str, Any],
) -> dict[str, Any]:
    baseline = _evaluation_summary(label="baseline", world=baseline_world, task_run=baseline_run)
    candidate = _evaluation_summary(label="candidate", world=candidate_world, task_run=candidate_run)
    return {
        "status": "complete",
        "brief_ref": brief.get("brief_id"),
        "objective": brief.get("objective"),
        "baseline": baseline,
        "candidate": candidate,
        "deltas": {
            "score_value": round(candidate["score"]["value"] - baseline["score"]["value"], 6),
            "reward": _nullable_delta(candidate["reward"], baseline["reward"]),
            "event_candidates": candidate["event_candidate_count"] - baseline["event_candidate_count"],
            "artifact_count": candidate["artifact_count"] - baseline["artifact_count"],
        },
        "recommendation": _recommendation(baseline, candidate),
    }


def comparison_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare candidate and baseline meta-harness task runs.")
    parser.add_argument("--brief", type=Path, required=True)
    parser.add_argument("--baseline-world", type=Path, required=True)
    parser.add_argument("--candidate-world", type=Path, required=True)
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--candidate-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("comparison"))
    args = parser.parse_args(argv)
    comparison = run_harness_comparison_from_files(
        brief_path=args.brief,
        baseline_world_path=args.baseline_world,
        candidate_world_path=args.candidate_world,
        baseline_run_path=args.baseline_run,
        candidate_run_path=args.candidate_run,
        output_dir=args.output,
    )
    print(json.dumps(comparison, indent=2, sort_keys=True))
    return 0


def _recipe_payload(
    *,
    output_dir: Path,
    task_path: Path,
    intake_request: dict[str, Any],
    baseline_world: Path | None,
    baseline_run: Path | None,
    candidate_world: Path | None,
    candidate_run: Path | None,
    baseline_experiment: Path | None,
    candidate_experiment: Path | None,
    models_config: Path | None,
    reviewer_models_config: Path | None,
    operation_models_config: Path | None,
    command_prefix: str,
) -> dict[str, Any]:
    recipe_id = intake_request["process_id"]
    paths = {
        "brief": "brief.json",
        "candidate_world": _path_or_placeholder(candidate_world, "candidate-world.json"),
        "candidate_run": _path_or_placeholder(candidate_run, "candidate-run.json"),
        "baseline_world": _path_or_placeholder(baseline_world, "baseline-world.json"),
        "baseline_run": _path_or_placeholder(baseline_run, "baseline-run.json"),
        "comparison_output": "comparison",
    }
    steps = _steps(
        task_path=task_path,
        paths=paths,
        baseline_experiment=baseline_experiment,
        candidate_experiment=candidate_experiment,
        models_config=models_config,
        reviewer_models_config=reviewer_models_config,
        operation_models_config=operation_models_config,
        command_prefix=command_prefix,
    )
    return {
        "recipe_id": recipe_id,
        "status": "materialized",
        "output_dir": str(output_dir),
        "task_path": str(task_path),
        "paths": paths,
        "inputs": {
            "baseline_world": str(baseline_world) if baseline_world else None,
            "baseline_run": str(baseline_run) if baseline_run else None,
            "candidate_world": str(candidate_world) if candidate_world else None,
            "candidate_run": str(candidate_run) if candidate_run else None,
            "baseline_experiment": str(baseline_experiment) if baseline_experiment else None,
            "candidate_experiment": str(candidate_experiment) if candidate_experiment else None,
            "models_config": str(models_config) if models_config else None,
            "reviewer_models_config": str(reviewer_models_config) if reviewer_models_config else None,
            "operation_models_config": str(operation_models_config) if operation_models_config else None,
        },
        "intake_request": intake_request,
        "steps": steps,
    }


def _steps(
    *,
    task_path: Path,
    paths: dict[str, str],
    baseline_experiment: Path | None,
    candidate_experiment: Path | None,
    models_config: Path | None,
    reviewer_models_config: Path | None,
    operation_models_config: Path | None,
    command_prefix: str,
) -> list[dict[str, Any]]:
    intake_command = _command(command_prefix, "meta-harness", "intake", "--task-file", str(task_path))
    if models_config is not None:
        intake_command = _command(
            command_prefix,
            "meta-harness",
            "intake-models",
            "--task-file",
            str(task_path),
            "--models-config",
            str(models_config),
        )

    steps: list[dict[str, Any]] = [
        {
            "id": "intake",
            "kind": "meta_harness_stage",
            "description": "Create or review the problem-space brief.",
            "command": intake_command,
            "writes": ["brief.json after extracting or approving problem_space_brief"],
        },
        {
            "id": "world",
            "kind": "meta_harness_stage",
            "description": "Generate or revise the candidate task world.",
            "command": _world_command(command_prefix, paths, models_config),
            "writes": [paths["candidate_world"]],
        },
        {
            "id": "candidate_run",
            "kind": "aec_bench_run",
            "description": "Run the candidate harness through AEC-Bench or provide a candidate task-run artifact.",
            "command": _run_command(command_prefix, candidate_experiment),
            "writes": [paths["candidate_run"]],
        },
        {
            "id": "baseline_run",
            "kind": "aec_bench_run",
            "description": "Run or import the existing baseline harness evidence.",
            "command": _run_command(command_prefix, baseline_experiment),
            "writes": [paths["baseline_run"]],
        },
        {
            "id": "review",
            "kind": "meta_harness_stage",
            "description": "Run post-verifier reviewer stages when reviewer model endpoints are available.",
            "command": _review_command(command_prefix, paths, reviewer_models_config),
            "writes": ["reviewer artifacts or agentic_review evidence"],
        },
        {
            "id": "operation_compare",
            "kind": "meta_harness_stage",
            "description": "Ask the operation orchestrator to plan candidate-vs-baseline comparison operations.",
            "command": _operation_command(command_prefix, paths, operation_models_config),
            "writes": ["operation comparison packet"],
        },
        {
            "id": "compare",
            "kind": "local_script",
            "description": "Compare baseline and candidate evidence using the generated comparison script.",
            "command": [
                "python",
                "compare_candidate.py",
                "--brief",
                paths["brief"],
                "--baseline-world",
                paths["baseline_world"],
                "--candidate-world",
                paths["candidate_world"],
                "--baseline-run",
                paths["baseline_run"],
                "--candidate-run",
                paths["candidate_run"],
                "--output",
                paths["comparison_output"],
            ],
            "writes": ["comparison/comparison.json", "comparison/comparison.md"],
        },
    ]
    return steps


def _world_command(command_prefix: str, paths: dict[str, str], models_config: Path | None) -> list[str]:
    if models_config is not None:
        return _command(
            command_prefix,
            "meta-harness",
            "world-models",
            "--brief",
            paths["brief"],
            "--models-config",
            str(models_config),
        )
    return _command(command_prefix, "meta-harness", "world-request", "--brief", paths["brief"])


def _run_command(command_prefix: str, experiment: Path | None) -> list[str]:
    if experiment is None:
        return _command(command_prefix, "run", "--config", "<experiment.yaml>")
    return _command(command_prefix, "run", "--config", str(experiment))


def _review_command(command_prefix: str, paths: dict[str, str], models_config: Path | None) -> list[str]:
    command = _command(
        command_prefix,
        "meta-harness",
        "review-models",
        "--world",
        paths["candidate_world"],
        "--run",
        paths["candidate_run"],
    )
    if models_config is not None:
        command.extend(["--models-config", str(models_config)])
    else:
        command.append("<reviewer-models>")
    return command


def _operation_command(command_prefix: str, paths: dict[str, str], models_config: Path | None) -> list[str]:
    command = _command(
        command_prefix,
        "meta-harness",
        "operation-orchestrate",
        "--brief",
        paths["brief"],
        "--world",
        paths["baseline_world"],
        "--world",
        paths["candidate_world"],
        "--emit-request",
    )
    if models_config is not None:
        command = _command(
            command_prefix,
            "meta-harness",
            "operation-models",
            "--brief",
            paths["brief"],
            "--world",
            paths["baseline_world"],
            "--world",
            paths["candidate_world"],
            "--models-config",
            str(models_config),
        )
    return command


def _command(command_prefix: str, *parts: str) -> list[str]:
    return [*shlex.split(command_prefix), *parts]


def _evaluation_summary(label: str, world: dict[str, Any], task_run: dict[str, Any]) -> dict[str, Any]:
    evidence = task_run.get("evidence", task_run)
    logic = evaluate_logic_profile(world.get("logic_profile", {}), evidence).to_dict()
    score = score_process_result({"task_run": task_run, "logic_evaluation": logic})
    return {
        "label": label,
        "world_id": world.get("world_id"),
        "run_id": task_run.get("run_id"),
        "logic_status": logic["overall_status"],
        "score": score,
        "reward": _reward(evidence),
        "event_candidate_count": len(logic["event_candidates"]),
        "artifact_count": _artifact_count(evidence.get("artifacts")),
        "logic_evaluation": logic,
    }


def _recommendation(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    score_delta = candidate["score"]["value"] - baseline["score"]["value"]
    event_delta = candidate["event_candidate_count"] - baseline["event_candidate_count"]
    if score_delta > 0 and event_delta <= 0:
        status = "candidate_improved"
    elif score_delta < 0:
        status = "baseline_preferred"
    elif event_delta > 0:
        status = "needs_governance_review"
    else:
        status = "no_clear_change"
    return {
        "status": status,
        "rationale": _recommendation_rationale(status),
    }


def _recommendation_rationale(status: str) -> str:
    rationales = {
        "candidate_improved": "Candidate score improved without increasing event pressure.",
        "baseline_preferred": "Candidate score regressed relative to the baseline.",
        "needs_governance_review": "Candidate surfaced additional event candidates that need governance review.",
        "no_clear_change": "Candidate and baseline are similar on the available evidence.",
    }
    return rationales[status]


def _comparison_markdown(comparison: dict[str, Any]) -> str:
    baseline = comparison["baseline"]
    candidate = comparison["candidate"]
    deltas = comparison["deltas"]
    return (
        "# Meta-Harness Comparison\n\n"
        f"Objective: {comparison.get('objective') or comparison.get('brief_ref') or 'unknown'}\n\n"
        "| Measure | Baseline | Candidate | Delta |\n"
        "|---|---:|---:|---:|\n"
        f"| Score | {baseline['score']['value']} | {candidate['score']['value']} | {deltas['score_value']} |\n"
        f"| Reward | {baseline['reward']} | {candidate['reward']} | {deltas['reward']} |\n"
        f"| Events | {baseline['event_candidate_count']} | {candidate['event_candidate_count']} | "
        f"{deltas['event_candidates']} |\n"
        f"| Artifacts | {baseline['artifact_count']} | {candidate['artifact_count']} | {deltas['artifact_count']} |\n\n"
        f"Recommendation: `{comparison['recommendation']['status']}`\n\n"
        f"{comparison['recommendation']['rationale']}\n"
    )


def _readme(recipe: dict[str, Any]) -> str:
    return (
        "# Meta-Harness Candidate Comparison Recipe\n\n"
        "This directory is a scriptable recipe for creating or revising a candidate task world, "
        "running it against a baseline, and comparing evidence.\n\n"
        "Start with `recipe.json`. Fill any placeholder paths, run the relevant commands, then run:\n\n"
        "```bash\n"
        "python compare_candidate.py --brief brief.json --baseline-world baseline-world.json "
        "--candidate-world candidate-world.json --baseline-run baseline-run.json "
        "--candidate-run candidate-run.json --output comparison\n"
        "```\n\n"
        "The comparison script writes `comparison/comparison.json` and `comparison/comparison.md`.\n"
    )


def _shell_script(recipe: dict[str, Any]) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'cd "$(dirname "$0")"',
        "",
        'echo "Meta-harness recipe: inspect recipe.json, then run the commands you need."',
        "",
    ]
    for step in recipe["steps"]:
        lines.append(f"# {step['id']}: {step['description']}")
        lines.append(" ".join(shlex.quote(part) for part in step["command"]))
        lines.append("")
    return "\n".join(lines)


def _comparison_script() -> str:
    return (
        "# ABOUTME: Project-local wrapper for the meta-harness candidate comparison recipe.\n"
        "# ABOUTME: Delegates to the installed aec_bench library so comparison logic stays shared.\n\n"
        "from __future__ import annotations\n\n"
        "from aec_bench.meta_harness.recipe import comparison_cli\n\n\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(comparison_cli())\n"
    )


def _path_or_placeholder(path: Path | None, placeholder: str) -> str:
    return str(path) if path is not None else placeholder


def _nullable_delta(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline is None:
        return None
    return round(candidate - baseline, 6)


def _reward(evidence: dict[str, Any]) -> float | None:
    score = evidence.get("score")
    if not isinstance(score, dict):
        return None
    reward = score.get("reward")
    if isinstance(reward, int | float) and not isinstance(reward, bool):
        return float(reward)
    if score.get("passed") is True:
        return 1.0
    if score.get("passed") is False:
        return 0.0
    return None


def _artifact_count(artifacts: Any) -> int:
    if isinstance(artifacts, dict | list):
        return len(artifacts)
    return 0


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
