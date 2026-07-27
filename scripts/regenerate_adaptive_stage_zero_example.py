# ABOUTME: Rebinds the checked-in adaptive stage-zero example to the current fixed kernel and task bytes.
# ABOUTME: Recomputes the preregistration manifest and reward-blind applicability without executing Harbor.

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, cast

from aec_bench.meta_harness.factorial_candidates import FactorialCandidateFactoryRequest
from aec_bench.meta_harness.factorial_experiment import (
    FactorialExperimentSplit,
    prepare_factorial_experiment_spec,
)
from aec_bench.meta_harness.kernel_catalogue import KernelRuntimeRegistry, default_kernel_registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate the checked-in adaptive stage-zero example spec.")
    parser.add_argument(
        "--spec",
        default="tests/fixtures/meta_harness/adaptive-stage-zero.example.json",
    )
    parser.add_argument("--tasks-root", default="tasks")
    arguments = parser.parse_args()
    path = Path(arguments.spec)
    payload = json.loads(path.read_text(encoding="utf-8"))
    registry = default_kernel_registry()
    requests = tuple(
        FactorialCandidateFactoryRequest.model_validate(_rebind_request(item, registry=registry))
        for item in payload["candidate_requests"]
    )
    spec = prepare_factorial_experiment_spec(
        candidate_requests=requests,
        registry=registry,
        tasks_root=Path(arguments.tasks_root),
        policy_id=str(payload["policy_id"]),
        randomization_seed=int(payload["study_manifest"]["randomization_seed"]),
        harness_generator_sha256=str(payload["harness_generator_sha256"]),
        program_generator_sha256=str(payload["program_generator_sha256"]),
        split=cast(FactorialExperimentSplit, payload["split"]),
        confidence_level=float(payload["confidence_level"]),
        bootstrap_replicates=int(payload["bootstrap_replicates"]),
        bootstrap_seed=int(payload["bootstrap_seed"]),
    )
    path.write_text(
        json.dumps(spec.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _rebind_request(
    source: dict[str, Any],
    *,
    registry: KernelRuntimeRegistry,
) -> dict[str, Any]:
    payload = copy.deepcopy(source)
    payload.pop("content_sha256", None)
    payload["kernel_ref"] = registry.manifest.ref.model_dump(mode="json")
    for key in ("fixed_harness_recipe", "learned_harness_recipe"):
        recipe = payload[key]
        recipe.pop("content_sha256", None)
        for binding in recipe["bindings"]:
            capability_id = binding["capability_ref"]["capability_id"]
            binding["capability_ref"] = registry.capability(capability_id).ref.model_dump(mode="json")
    for key in ("fixed_program", "learned_program"):
        payload[key].pop("content_sha256", None)
    return payload


if __name__ == "__main__":
    main()
