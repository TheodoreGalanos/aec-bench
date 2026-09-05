# ABOUTME: Qualifies hydraulic lineage packages through the local Prime lifecycle environment.
# ABOUTME: Retains deterministic control evidence and actor-visible training demonstrations without model calls.

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import platform
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any

from aec_bench.experimentation.engineering_decisions.definitions import HydraulicExperiment
from aec_bench.experimentation.engineering_decisions.hydraulic_counterfactual import (
    hydraulic_plan,
    run_hydraulic_counterfactual,
)
from aec_bench.experimentation.engineering_decisions.records import publish_record, write_plan
from aec_bench.lifecycles.catalogue import lifecycle_operation_resolver
from aec_bench.lifecycles.runtime.lifecycle import read_lifecycle
from aec_bench.lifecycles.stormwater_design.hydraulic_review import materialize_hydraulic_review_lifecycle
from aec_bench.lifecycles.stormwater_design.hydraulics.lineages import HydraulicLineage
from aec_bench.prime_lab.lifecycle_environment import load_local_lifecycle_environment
from aec_bench.prime_lab.lifecycle_exporter import (
    LifecycleDatasetAssignment,
    PrimeLifecycleExportConfig,
    PrimeLifecyclePackageRecord,
    export_prime_lifecycle_environment,
)
from aec_bench.prime_lab.training import render_train_config, validate_training_handoff


def qualify_hydraulic_training(output: Path, definition: HydraulicExperiment | None = None) -> dict[str, Any]:
    """Generate disjoint public fixtures and exercise the installed Verifiers tool and reward boundary."""
    definition = definition or HydraulicExperiment()
    if {partition.split for partition in definition.partitions} != {"train", "development", "acceptance"}:
        raise ValueError("training qualification requires train, development, and acceptance partitions")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("qualification output directory must be empty")
    _write_json(output / "definition.json", definition.model_dump(mode="json"))
    write_plan(
        output / "reference_trials",
        definition,
        [
            hydraulic_plan(definition.experiment_id, seed, revision, "none")
            for partition in definition.partitions
            if partition.split != "acceptance"
            for seed in partition.seeds
            for revision in definition.revisions
        ],
    )
    assignments = {}
    references = {}
    # Split whole projects before deriving revision siblings. Acceptance stays outside the export.
    for partition in definition.partitions:
        for seed in partition.seeds:
            lineage = HydraulicLineage(seed=seed)
            for revision in definition.revisions:
                destination = output / partition.split / str(seed) / revision
                if partition.split == "acceptance":
                    materialize_hydraulic_review_lifecycle(
                        destination / "package", variant_id=revision, lineage=lineage
                    )
                    continue
                record = run_hydraulic_counterfactual(destination, seed=seed, revision_id=revision)
                publish_record(output / "reference_trials", record)
                package = destination / "package"
                assignment = LifecycleDatasetAssignment(
                    group_id=lineage.lineage_id,
                    split="train" if partition.split == "train" else "eval",
                )
                assignments[package] = assignment
                references[(lineage.lineage_id, revision)] = destination
    exported = export_prime_lifecycle_environment(
        PrimeLifecycleExportConfig(
            name="aec_hydraulic_training",
            package_dirs=tuple(assignments),
            dataset_assignments=assignments,
            output_dir=output / "environments",
            max_turns=128,
        )
    )
    (output / "training.toml").write_text(
        render_train_config(
            environment=exported.environment_id,
            model="Qwen/Qwen3.5-0.8B",
            max_steps=1,
            batch_size=4,
            rollouts_per_example=4,
            max_tokens=2048,
            env_args_list=[{"split": "train"}],
            eval_interval=1,
            eval_num_examples=None,
            eval_rollouts_per_example=1,
            eval_base_model=True,
            adapters_keep_last=1,
        ),
        encoding="utf-8",
    )
    config = tomllib.loads((output / "training.toml").read_text())
    validate_training_handoff(config)
    prime_config = importlib.import_module("prime_cli.commands.rl").RLConfig.model_validate(config)
    if prime_config.eval.to_api_dict() is None:
        raise ValueError("Prime configuration omits evaluation environments from its API request")
    environment = load_local_lifecycle_environment(manifest_path=exported.manifest_path, split="train")
    result = asyncio.run(_qualify(environment, references, output))
    result["runtime"] = {
        "python": platform.python_version(),
        "prime": version("prime"),
        "verifiers": version("verifiers"),
    }
    result["package_requirements"] = tomllib.loads((exported.package_dir / "pyproject.toml").read_text())["project"]
    result["environment_package"] = str(exported.package_dir.relative_to(output))
    result["training_config"] = "accepted_by_installed_prime_cli"
    result["hosted_run"] = "not_run"
    result["weight_update"] = "not_run"
    result["pending_checks"] = [
        "Install the bound AEC-Bench source and generated package in the hosted runtime.",
        "Confirm the hosted Python and Verifiers versions accept the package requirements.",
        "Confirm an exact SFT checkpoint can initialize the RL arm.",
        "Run budgeted training, retain the resulting checkpoint, reload it, and evaluate it.",
    ]
    result["scope"] = "synthetic_deterministic_controls_not_model_learning_or_transfer"
    _write_json(output / "qualification.json", result)
    if not result["local_passed"]:
        raise ValueError(f"local training qualification failed; inspect {output / 'qualification.json'}")
    return result


async def _qualify(environment: Any, references: dict[tuple[str, str], Path], output: Path) -> dict[str, Any]:
    vf = importlib.import_module("verifiers")
    checks = []
    demonstrations = []
    rows = list(environment.get_dataset()) + list(environment.get_eval_dataset())
    for index, row in enumerate(rows):
        record = PrimeLifecyclePackageRecord.model_validate_json(row["info"])
        assignment = record.dataset_assignment
        assert assignment is not None
        reference = references[(assignment.group_id, record.variant_id)]
        state = vf.State(input=dict(row))
        state["trajectory_id"] = f"qualification-{index}"
        state["completion"] = []
        state["trajectory"] = []
        await environment.setup_state(state)
        messages = list(row["prompt"])
        try:
            package, run = reference / "package", reference / "run"
            lifecycle = read_lifecycle(package, run, operation_resolver=lifecycle_operation_resolver(package, run))
            for checkpoint in lifecycle["checkpoint_runs"]:
                checkpoint_id = checkpoint["checkpoint_id"]
                await _call(environment, state, messages, "read_workspace_file", {"path": "instruction.md"})
                if checkpoint["operation_actions"]:
                    await _call(
                        environment,
                        state,
                        messages,
                        "read_workspace_file",
                        {
                            "path": f"checkpoints/{checkpoint_id}/operations.json",
                        },
                    )
                for action in checkpoint["operation_actions"]:
                    await _call(
                        environment,
                        state,
                        messages,
                        "read_workspace_file",
                        {
                            "path": "operations/current-source.json",
                        },
                    )
                    response = await _call(
                        environment,
                        state,
                        messages,
                        "execute_operation",
                        {
                            "checkpoint_id": checkpoint_id,
                            "operation_id": action["operation_id"],
                            "visible_source_state_sha256": action["visible_source_state_before_sha256"],
                            "reason": "Reproduce the public deterministic calculation control.",
                        },
                    )
                    payload = json.loads(response)
                    if payload.get("status") not in {"completed", "already_current"}:
                        raise ValueError(f"Prime rejected control operation: {payload}")
                    for artifact in payload.get("artifacts", []):
                        await _call(environment, state, messages, "read_workspace_file", {"path": artifact["path"]})
                submission = (run / "episodes" / checkpoint_id / "submission.json").read_text()
                await _call(
                    environment,
                    state,
                    messages,
                    "write_checkpoint_submission",
                    {
                        "checkpoint_id": checkpoint_id,
                        "content": submission,
                    },
                )
                await _call(environment, state, messages, "submit_checkpoint", {"checkpoint_id": checkpoint_id})
            await environment.rubric.score_rollout(state)
            passed = state.get("reward") == 1.0 and state.get("lifecycle_reward_status") == "verified"
            checks.append({"group_id": assignment.group_id, "revision": record.variant_id, "passed": passed})
            if assignment.split == "train" and passed:
                demonstrations.append(
                    {
                        "messages": messages,
                        "tools": [
                            {"type": "function", "function": tool.model_dump(exclude_none=True)}
                            for tool in environment.tool_defs
                        ],
                    }
                )
            _write_json(
                output / "prime_controls" / f"{index}.json",
                {
                    "messages": messages,
                    "reward": state.get("reward"),
                    "verification": state.get("lifecycle_verification"),
                },
            )
        finally:
            await environment.rubric.cleanup(state)
    # Start another rollout and verify that previous submissions and progress are absent.
    incomplete = vf.State(input=dict(rows[0]))
    incomplete["trajectory_id"] = "qualification-incomplete"
    incomplete["completion"] = []
    incomplete["trajectory"] = []
    await environment.setup_state(incomplete)
    try:
        workspace = Path(incomplete["workspace_path"])
        isolation_passed = not (workspace / "submissions" / "baseline_analysis.json").exists()
        current = read_lifecycle(
            Path(incomplete["package_dir"]),
            Path(incomplete["run_dir"]),
            operation_resolver=lifecycle_operation_resolver(
                Path(incomplete["package_dir"]), Path(incomplete["run_dir"])
            ),
        )
        isolation_passed = isolation_passed and current["active_checkpoint_id"] == "baseline_analysis"
        await environment.rubric.score_rollout(incomplete)
        incomplete_passed = (
            incomplete.get("reward") == 0.0 and incomplete.get("lifecycle_reward_status") == "incomplete"
        )
    finally:
        await environment.rubric.cleanup(incomplete)
    (output / "training_demonstrations.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in demonstrations),
        encoding="utf-8",
    )
    return {
        "local_passed": all(check["passed"] for check in checks) and incomplete_passed and isolation_passed,
        "controls": checks,
        "incomplete_zero_reward": incomplete_passed,
        "rollout_isolation": isolation_passed,
        "training_demonstrations": len(demonstrations),
    }


async def _call(environment: Any, state: Any, messages: list[dict[str, Any]], name: str, args: dict[str, Any]) -> str:
    call_id = f"control-{len(messages)}"
    messages.append(
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
            ],
        }
    )
    response = await environment.call_tool(name, environment.update_tool_args(name, args.copy(), [], state), call_id)
    if not isinstance(response.content, str):
        raise TypeError("Prime tool response must be text")
    messages.append({"role": "tool", "tool_call_id": call_id, "content": response.content})
    return response.content


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--definition", type=Path, help="HydraulicExperiment JSON with project partitions and revisions."
    )
    args = parser.parse_args()
    definition = HydraulicExperiment.model_validate_json(args.definition.read_text()) if args.definition else None
    print(json.dumps(qualify_hydraulic_training(args.output, definition), indent=2))


if __name__ == "__main__":
    main()
