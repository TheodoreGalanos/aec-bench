#!/usr/bin/env python3
# ABOUTME: Selects representative tests for source owners changed by a pull request.
# ABOUTME: Runs additive owner evidence without importing the package or relying on shell-generated test paths.

from __future__ import annotations

import argparse
import concurrent.futures
import subprocess
import sys
from pathlib import Path

OWNER_TESTS: dict[str, tuple[str, ...]] = {
    "adapters": ("tests/adapters/test_base_capabilities.py",),
    "agents": ("tests/agents/test_env.py",),
    "catalogue": (
        "tests/cli/test_catalogue_commands.py",
        "tests/worlds/test_generated_catalogue.py",
        "tests/lifecycles/test_generated_catalogue.py",
    ),
    "cli": ("tests/cli/test_output.py",),
    "communication": ("tests/communication/test_behavioral_report.py",),
    "config": ("tests/test_config_resolution.py",),
    "contracts": ("tests/contracts/test_identity.py",),
    "dataset": ("tests/dataset/test_identity_v2.py",),
    "evaluation": ("tests/evaluation/test_artifact.py",),
    "evolution": ("tests/evolution/test_core.py",),
    "execution": ("tests/execution/test_scheduler.py",),
    "experimentation": ("tests/experimentation/test_meta_harness.py",),
    "feedback": ("tests/feedback/test_assignment.py",),
    "generation": ("tests/generation/test_sampler.py",),
    "harness": ("tests/harness/test_artifact_ports.py",),
    "images": ("tests/images/test_extensions.py",),
    "init": ("tests/cli/test_init.py",),
    "ledger": ("tests/ledger/test_evidence_index.py",),
    "lifecycles": ("tests/lifecycles/test_lifecycle_conformance.py",),
    "model_routing": ("tests/adapters/test_provider_routing.py",),
    "prime_agent": ("tests/prime_agent/test_batch.py",),
    "prime_lab": ("tests/prime_lab/test_eval_import.py",),
    "providers": ("tests/providers/test_source_identity.py",),
    "remediation": ("tests/remediation/test_section_resolver.py",),
    "search": ("tests/web/test_search_page.py",),
    "synthesis": ("tests/synthesis/test_engine.py",),
    "tasks": ("tests/tasks/test_loader.py",),
    "templates": ("tests/templates/test_contracts.py",),
    "trajectory": ("tests/trajectory/test_contract.py",),
    "trials": ("tests/harness/test_trial.py",),
    "tui": ("tests/tui/test_app_modes.py",),
    "web": ("tests/web/test_schemas.py",),
    "worlds": ("tests/worlds/test_catalogue.py",),
}
TEST_SHARD_COUNT = 4


def _changed_paths(root: Path, base_revision: str) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", "--diff-filter=ACMR", f"{base_revision}...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(path for path in result.stdout.splitlines() if path)


def _owner_for_source(path: str) -> str | None:
    prefix = "src/aec_bench/"
    if not path.startswith(prefix):
        return None
    relative = path.removeprefix(prefix)
    first_part = relative.split("/", 1)[0]
    if "/" in relative:
        owner = first_part
    else:
        stem = Path(first_part).stem
        owner = "init" if stem == "__init__" else stem
    return owner if owner in OWNER_TESTS else "*"


def _is_test_module(path: str) -> bool:
    candidate = Path(path)
    return (
        path.startswith("tests/")
        and candidate.suffix == ".py"
        and (candidate.name.startswith("test_") or candidate.name.endswith("_test.py"))
    )


def _test_paths(changed_paths: tuple[str, ...]) -> tuple[str, ...]:
    selected: set[str] = set()
    unknown_source_change = False
    for path in changed_paths:
        if path.startswith("tests/"):
            if _is_test_module(path):
                selected.add(path)
            continue
        owner = _owner_for_source(path)
        if owner == "*":
            unknown_source_change = True
        elif owner is not None:
            selected.update(OWNER_TESTS[owner])
    if unknown_source_change:
        return ("tests/",)
    return tuple(sorted(selected))


def _test_shards(paths: tuple[str, ...], shard_count: int = TEST_SHARD_COUNT) -> tuple[tuple[str, ...], ...]:
    count = min(shard_count, len(paths))
    return tuple(tuple(paths[index::count]) for index in range(count))


def _run_test_shard(root: Path, paths: tuple[str, ...]) -> int:
    return subprocess.run([sys.executable, "-m", "pytest", "-q", *paths], cwd=root, check=False).returncode


def _changed_source_paths(changed_paths: tuple[str, ...]) -> tuple[str, ...]:
    """Return changed maintained Python sources for the focused type check."""
    return tuple(sorted(path for path in changed_paths if path.startswith("src/aec_bench/") and path.endswith(".py")))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run representative tests for owners changed since a pull-request base revision."
    )
    parser.add_argument("--base-revision", required=True, help="Git revision at the pull-request base.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    args = parser.parse_args()

    changed_paths = _changed_paths(args.root.resolve(), args.base_revision)
    paths = _test_paths(changed_paths)
    if not paths:
        print("No owner-specific tests selected.")
        return 0
    shards = _test_shards(paths)
    print(f"Running {len(paths)} changed and owner-representative test files in {len(shards)} shards:")
    print(
        "\n".join(f"  shard {index}: {' '.join(shard)}" for index, shard in enumerate(shards, start=1)),
        flush=True,
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(shards)) as executor:
        results = tuple(executor.map(lambda shard: _run_test_shard(args.root, shard), shards))
    if any(result != 0 for result in results):
        return 1

    source_paths = _changed_source_paths(changed_paths)
    if not source_paths:
        print("No changed source files require type checking.")
        return 0
    print("Type-checking changed source files:", " ".join(source_paths))
    return subprocess.run([sys.executable, "-m", "mypy", *source_paths], cwd=args.root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
