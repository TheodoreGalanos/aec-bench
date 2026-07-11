# ABOUTME: Drives generated lifecycle environments through the real local Verifiers runtime.
# ABOUTME: Runs outside the repository root and returns only JSON-serialisable integration evidence.

from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any, cast

from aec_bench.meta_harness.evidence_lifecycle import read_evidence_lifecycle_state


def main() -> None:
    environment_id = sys.argv[1]
    request = cast(dict[str, Any], json.load(sys.stdin))
    datasets = importlib.import_module("datasets")
    datasets.disable_progress_bars()
    module = importlib.import_module(f"{environment_id}.environment")
    environment = module.load_environment()
    vf = importlib.import_module("verifiers")

    mutation_path = request.get("mutate_after_load")
    if isinstance(mutation_path, str):
        path = Path(mutation_path)
        path.write_text(path.read_text(encoding="utf-8") + "\nmutated\n", encoding="utf-8")

    dataset_row = dict(environment.dataset[0])
    state = vf.State(input=dataset_row)
    state["task"] = dataset_row
    state["trajectory_id"] = request["trajectory_id"]
    state["completion"] = []
    state["trajectory"] = []
    state["reward"] = None
    state["metrics"] = None
    state["final_env_response"] = None
    try:
        asyncio.run(environment.setup_state(state))
    except Exception as exc:  # noqa: BLE001 - the probe reports the real setup boundary.
        if request.get("capture_setup_error") is True:
            print(json.dumps({"setup_error": type(exc).__name__, "message": str(exc)}, sort_keys=True))
            return
        raise

    temporary_path = Path(state["aec_tempdir"].name)
    try:
        responses = []
        for index, action in enumerate(request.get("actions", [])):
            name = action["name"]
            arguments = environment.update_tool_args(name, dict(action.get("arguments", {})), [], state)
            tool_message = asyncio.run(environment.call_tool(name, arguments, f"probe-{index}"))
            response = tool_message.content
            if not isinstance(response, str):
                raise TypeError("lifecycle tool returned non-text content")
            responses.append(
                {
                    "name": name,
                    "payload": _parse_response(response),
                    "has_final_env_response": state.get("final_env_response") is not None,
                }
            )

        reward = None
        metrics = None
        if request.get("score") is True:
            asyncio.run(environment.rubric.score_rollout(state))
            reward = state.get("reward")
            metrics = state.get("metrics")

        package_dir = Path(cast(str, state["package_dir"]))
        run_dir = Path(cast(str, state["run_dir"]))
        lifecycle = read_evidence_lifecycle_state(package_dir, run_dir)
        result = {
            "responses": responses,
            "reward": reward,
            "metrics": metrics,
            "reward_status": state.get("lifecycle_reward_status"),
            "verification": state.get("lifecycle_verification"),
            "lifecycle": lifecycle,
            "state_type": type(state).__name__,
            "tool_names": [tool.name for tool in environment.tool_defs],
            "tool_parameters": [tool.parameters for tool in environment.tool_defs],
            "run_files": sorted(path.relative_to(run_dir).as_posix() for path in run_dir.rglob("*") if path.is_file()),
        }
    finally:
        asyncio.run(environment.rubric.cleanup(state))

    result["cleanup"] = {
        "state_keys_removed": all(
            key not in state for key in ("aec_tempdir", "lifecycle_workspace_tool", "lifecycle_control_tool")
        ),
        "temporary_directory_exists": temporary_path.exists(),
    }
    print(json.dumps(result, sort_keys=True))


def _parse_response(response: str) -> object:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return response


if __name__ == "__main__":
    main()
