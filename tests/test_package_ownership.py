# ABOUTME: Enforces the small dependency boundaries that protect task and contract ownership.
# ABOUTME: Prevents provider SDKs and execution frameworks from leaking into neutral packages.

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
NEUTRAL_ROOTS = (
    REPOSITORY_ROOT / "src" / "aec_bench" / "contracts",
    REPOSITORY_ROOT / "src" / "aec_bench" / "lifecycles",
    REPOSITORY_ROOT / "src" / "aec_bench" / "worlds",
)
OPTIONAL_RUNTIME_ROOTS = {
    "acp",
    "anthropic",
    "boto3",
    "botocore",
    "harbor",
    "modal",
    "morphcloud",
    "openai",
    "pydantic_ai",
    "verifiers",
}


def _top_level_imports(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", maxsplit=1)[0])
    return imported


def _aec_bench_imports(source_path: Path) -> set[str]:
    """Return absolute AEC-Bench module imports without executing the module."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(
                alias.name for alias in node.names if alias.name == "aec_bench" or alias.name.startswith("aec_bench.")
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "aec_bench" or node.module.startswith("aec_bench."):
                imported.add(node.module)
    return imported


def test_neutral_contracts_and_domains_do_not_import_optional_runtimes() -> None:
    violations = {
        str(source_path.relative_to(REPOSITORY_ROOT)): sorted(imported)
        for neutral_root in NEUTRAL_ROOTS
        for source_path in neutral_root.rglob("*.py")
        if (imported := _top_level_imports(source_path) & OPTIONAL_RUNTIME_ROOTS)
    }

    assert violations == {}


@pytest.mark.parametrize("owner", ("lifecycles", "worlds"))
def test_task_domains_do_not_import_provider_adapters(owner: str) -> None:
    domain_root = REPOSITORY_ROOT / "src" / "aec_bench" / owner
    violations: list[str] = []
    for source_path in domain_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
            if (module and module.startswith("aec_bench.providers")) or any(
                name.startswith("aec_bench.providers") for name in names
            ):
                violations.append(str(source_path.relative_to(REPOSITORY_ROOT)))

    assert sorted(set(violations)) == []


def test_contracts_do_not_import_implementation_owners() -> None:
    contracts_root = REPOSITORY_ROOT / "src" / "aec_bench" / "contracts"
    violations = {
        str(source_path.relative_to(REPOSITORY_ROOT)): sorted(
            module for module in _aec_bench_imports(source_path) if not module.startswith("aec_bench.contracts")
        )
        for source_path in contracts_root.rglob("*.py")
        if any(not module.startswith("aec_bench.contracts") for module in _aec_bench_imports(source_path))
    }

    assert violations == {}


@pytest.mark.parametrize(
    ("owner", "forbidden_prefixes"),
    (
        (
            "adapters",
            (
                "aec_bench.experimentation",
                "aec_bench.ledger",
                "aec_bench.lifecycles",
                "aec_bench.worlds",
            ),
        ),
        (
            "evaluation",
            (
                "aec_bench.adapters",
                "aec_bench.experimentation",
                "aec_bench.harness",
                "aec_bench.providers",
            ),
        ),
        (
            "ledger",
            (
                "aec_bench.evaluation",
                "aec_bench.experimentation",
                "aec_bench.providers",
            ),
        ),
        (
            "evolution",
            ("aec_bench.communication",),
        ),
        (
            "harness",
            ("aec_bench.experimentation",),
        ),
        (
            "providers",
            ("aec_bench.experimentation",),
        ),
    ),
)
def test_core_owners_do_not_import_forbidden_owners(
    owner: str,
    forbidden_prefixes: tuple[str, ...],
) -> None:
    owner_root = REPOSITORY_ROOT / "src" / "aec_bench" / owner
    violations = {
        str(source_path.relative_to(REPOSITORY_ROOT)): sorted(
            module for module in _aec_bench_imports(source_path) if module.startswith(forbidden_prefixes)
        )
        for source_path in owner_root.rglob("*.py")
        if any(module.startswith(forbidden_prefixes) for module in _aec_bench_imports(source_path))
    }

    assert violations == {}


def test_proposal_experiments_do_not_import_qualification_experiments() -> None:
    proposals_root = REPOSITORY_ROOT / "src" / "aec_bench" / "experimentation" / "proposals"
    forbidden_prefix = "aec_bench.experimentation.qualification"
    violations = {
        str(source_path.relative_to(REPOSITORY_ROOT)): sorted(
            module for module in _aec_bench_imports(source_path) if module.startswith(forbidden_prefix)
        )
        for source_path in proposals_root.rglob("*.py")
        if any(module.startswith(forbidden_prefix) for module in _aec_bench_imports(source_path))
    }

    assert violations == {}


def test_prime_protocol_does_not_import_execution_or_task_implementations() -> None:
    prime_root = REPOSITORY_ROOT / "src" / "aec_bench" / "prime_agent"
    forbidden_prefixes = (
        "aec_bench.adapters",
        "aec_bench.harness",
        "aec_bench.lifecycles",
        "aec_bench.worlds",
    )
    violations = {
        str(source_path.relative_to(REPOSITORY_ROOT)): sorted(
            module for module in _aec_bench_imports(source_path) if module.startswith(forbidden_prefixes)
        )
        for source_path in prime_root.rglob("*.py")
        if any(module.startswith(forbidden_prefixes) for module in _aec_bench_imports(source_path))
    }

    assert violations == {}


def test_prime_acp_does_not_select_a_task_specific_socket_environment() -> None:
    acp_source = (REPOSITORY_ROOT / "src" / "aec_bench" / "prime_agent" / "acp.py").read_text(encoding="utf-8")

    assert "AEC_BENCH_WORLD_ACTOR_SOCKET" not in acp_source


def test_ordinary_morph_provider_does_not_import_harness_policy() -> None:
    provider_paths = (
        REPOSITORY_ROOT / "src" / "aec_bench" / "providers" / "morph_cloud.py",
        REPOSITORY_ROOT / "src" / "aec_bench" / "providers" / "morph_harbor.py",
    )
    violations = {
        str(source_path.relative_to(REPOSITORY_ROOT)): sorted(
            module for module in _aec_bench_imports(source_path) if module.startswith("aec_bench.harness")
        )
        for source_path in provider_paths
        if any(module.startswith("aec_bench.harness") for module in _aec_bench_imports(source_path))
    }

    assert violations == {}


def test_neutral_harbor_dispatch_does_not_import_ordinary_morph_implementation() -> None:
    dispatch_path = REPOSITORY_ROOT / "src" / "aec_bench" / "harness" / "harbor_dispatch.py"
    forbidden = {
        "aec_bench.providers.morph_cloud",
        "aec_bench.providers.morph_harbor",
    }

    assert _aec_bench_imports(dispatch_path).isdisjoint(forbidden)


def test_neutral_harbor_import_core_does_not_import_task_families() -> None:
    import_path = REPOSITORY_ROOT / "src" / "aec_bench" / "harness" / "harbor_importing" / "core.py"
    forbidden_prefixes = (
        "aec_bench.lifecycles",
        "aec_bench.worlds",
    )

    assert not any(module.startswith(forbidden_prefixes) for module in _aec_bench_imports(import_path))


def test_retired_umbrella_packages_have_no_python_sources() -> None:
    retired_roots = (
        REPOSITORY_ROOT / "src" / "aec_bench" / "experiments",
        REPOSITORY_ROOT / "src" / "aec_bench" / "meta_harness",
        REPOSITORY_ROOT / "src" / "aec_bench" / "task_world_templates",
        REPOSITORY_ROOT / "tests" / "experiments",
        REPOSITORY_ROOT / "tests" / "meta_harness",
        REPOSITORY_ROOT / "tests" / "task_world_templates",
    )

    remaining = sorted(
        str(source_path.relative_to(REPOSITORY_ROOT))
        for retired_root in retired_roots
        for source_path in retired_root.rglob("*.py")
    )

    assert remaining == []


def test_source_owners_have_no_reciprocal_dependencies_below_composition_roots() -> None:
    package_root = REPOSITORY_ROOT / "src" / "aec_bench"
    composition_roots = {
        package_root / "worlds" / "catalogue.py",
    }
    edges: set[tuple[str, str]] = set()
    for source_path in package_root.rglob("*.py"):
        if source_path in composition_roots:
            continue
        source_owner = source_path.relative_to(package_root).parts[0]
        for module in _aec_bench_imports(source_path):
            parts = module.split(".")
            if len(parts) > 1 and parts[1] != source_owner:
                edges.add((source_owner, parts[1]))

    reciprocal = {tuple(sorted((source, target))) for source, target in edges if (target, source) in edges}

    assert reciprocal == set()


@pytest.mark.parametrize(
    "module_name",
    (
        "aec_bench.synthesis",
        "aec_bench.lifecycles.stormwater_design.hydraulics",
    ),
)
def test_neutral_package_initializers_do_not_load_implementation_modules(module_name: str) -> None:
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib, json, sys; "
                f"module_name={module_name!r}; "
                "importlib.import_module(module_name); "
                "prefix=module_name + '.'; "
                "print(json.dumps(sorted(name for name in sys.modules if name.startswith(prefix))))"
            ),
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(probe.stdout) == []
