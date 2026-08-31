# ABOUTME: Enforces the small dependency boundaries that protect task and contract ownership.
# ABOUTME: Prevents provider SDKs and execution frameworks from leaking into neutral packages.

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.audit_package_dependencies import (
    OwnerDependencyException,
    build_audit,
    load_owner_dependency_policy,
    render_audit_report,
    validate_owner_dependency_exceptions,
    validate_owner_dependency_policy,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src" / "aec_bench"
CONTRACT_ROOT = SOURCE_ROOT / "contracts"
LIFECYCLE_ROOT = SOURCE_ROOT / "lifecycles"
WORLD_ROOT = SOURCE_ROOT / "worlds"
LEARNING_STUDIES_ROOT = SOURCE_ROOT / "experimentation" / "learning_studies"
NEUTRAL_ROOTS = (CONTRACT_ROOT, LIFECYCLE_ROOT, WORLD_ROOT)
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
FORBIDDEN_TASK_DOMAIN_PREFIXES = (
    "aec_bench.adapters",
    "aec_bench.cli",
    "aec_bench.experimentation",
    "aec_bench.harness",
    "aec_bench.prime_agent",
    "aec_bench.prime_lab",
    "aec_bench.providers",
    "aec_bench.tui",
    "aec_bench.web",
)


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


def test_expected_architecture_roots_exist_and_contain_python_sources() -> None:
    missing_or_empty = [
        str(root.relative_to(REPOSITORY_ROOT))
        for root in NEUTRAL_ROOTS
        if not root.is_dir() or not any(root.rglob("*.py"))
    ]

    assert missing_or_empty == []


def test_declared_owner_dependency_policy_covers_the_current_import_graph() -> None:
    audit = build_audit(
        repository_root=REPOSITORY_ROOT,
        commit="test",
        minimal_import_smoke="not-run",
        minimal_import_command="",
    )

    assert audit["owner_dependency_policy_violations"] == []
    assert audit["owner_dependency_policy"] == audit["top_level_package_graph"]


def test_owner_dependency_policy_reports_missing_and_forbidden_edges() -> None:
    owner_graph = {"contracts": {"ledger"}, "ledger": set()}
    policy = {"contracts": set(), "ledger": {"contracts"}}

    assert validate_owner_dependency_policy(owner_graph, policy) == (
        "undeclared owner dependency: contracts -> ledger",
    )


def test_owner_dependency_policy_reports_unknown_owner_and_target() -> None:
    violations = validate_owner_dependency_policy(
        {"contracts": set()},
        {"contracts": {"missing"}, "unknown": set()},
    )

    assert violations == (
        "policy declares unknown owner: unknown",
        "policy declares unknown dependency: contracts -> missing",
    )


def test_owner_dependency_policy_loader_rejects_duplicate_targets(tmp_path: Path) -> None:
    policy_path = tmp_path / "owner_dependencies.toml"
    policy_path.write_text('[owners.contracts]\nmay_depend_on = ["ledger", "ledger"]\n', encoding="utf-8")

    with pytest.raises(ValueError, match="targets must be unique: contracts"):
        load_owner_dependency_policy(policy_path)


def _dependency_fixture(
    tmp_path: Path,
    files: dict[str, str],
    policy: str | None,
) -> Path:
    repository_root = tmp_path / "repository"
    package_root = repository_root / "src" / "aec_bench"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    for relative_path, source in files.items():
        path = package_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    if policy is not None:
        policy_path = repository_root / "scripts" / "owner_dependencies.toml"
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(policy, encoding="utf-8")
    return repository_root


def _audit_fixture(repository_root: Path) -> dict[str, object]:
    return build_audit(
        repository_root=repository_root,
        commit="fixture",
        minimal_import_smoke="not-run",
        minimal_import_command="",
    )


def test_dependency_audit_reports_missing_policy_deterministically(tmp_path: Path) -> None:
    repository_root = _dependency_fixture(tmp_path, {"contracts/value.py": ""}, policy=None)

    audit = _audit_fixture(repository_root)

    assert audit["owner_dependency_policy_violations"] == [
        f"owner dependency policy file is missing: {repository_root / 'scripts' / 'owner_dependencies.toml'}"
    ]


def test_dependency_audit_parses_source_without_importing_it(tmp_path: Path) -> None:
    repository_root = _dependency_fixture(
        tmp_path,
        {"contracts/explosive.py": 'raise RuntimeError("audit must not import source")\n'},
        policy="[owners.contracts]\nmay_depend_on = []\n",
    )

    audit = _audit_fixture(repository_root)

    assert audit["owner_dependency_policy_violations"] == []


def test_dependency_audit_reports_cycle_and_forbidden_edge(tmp_path: Path) -> None:
    repository_root = _dependency_fixture(
        tmp_path,
        {
            "alpha/one.py": "from aec_bench.beta.two import VALUE\n",
            "beta/two.py": "from aec_bench.alpha.one import VALUE\n",
        },
        policy="[owners.alpha]\nmay_depend_on = []\n\n[owners.beta]\nmay_depend_on = []\n",
    )

    audit = _audit_fixture(repository_root)

    assert audit["owner_dependency_policy_violations"] == [
        "undeclared owner import: alpha -> aec_bench.beta.two",
        "undeclared owner import: beta -> aec_bench.alpha.one",
    ]
    assert audit["top_level_strongly_connected_components"] == [["alpha", "beta"]]
    report = render_audit_report(audit)
    assert "alpha -> beta" in report
    assert "Violations:" in report


def test_dependency_audit_rejects_generic_runtime_back_import(tmp_path: Path) -> None:
    repository_root = _dependency_fixture(
        tmp_path,
        {
            "worlds/runtime/runner.py": "from aec_bench.worlds.monitoring.task import VALUE\n",
            "worlds/monitoring/task.py": "VALUE = 1\n",
        },
        policy="[owners.worlds]\nmay_depend_on = []\n",
    )

    audit = _audit_fixture(repository_root)

    assert audit["generic_runtime_back_imports"] == [
        "aec_bench.worlds.runtime.runner -> aec_bench.worlds.monitoring.task",
    ]


def test_dependency_audit_rejects_optional_runtime_in_neutral_owner(tmp_path: Path) -> None:
    repository_root = _dependency_fixture(
        tmp_path,
        {"contracts/provider_boundary.py": "import openai\n"},
        policy="[owners.contracts]\nmay_depend_on = []\n",
    )

    audit = _audit_fixture(repository_root)

    assert audit["optional_dependency_leakage"] == ["aec_bench.contracts.provider_boundary: openai"]


def test_dependency_audit_accepts_a_current_narrow_exception(tmp_path: Path) -> None:
    repository_root = _dependency_fixture(
        tmp_path,
        {
            "alpha/one.py": "from aec_bench.beta.two import VALUE\n",
            "beta/two.py": "VALUE = 1\n",
        },
        """
[owners.alpha]
may_depend_on = []

[owners.beta]
may_depend_on = []

[exceptions.alpha-beta]
source_owner = "alpha"
target_owner = "beta"
import_prefix = "aec_bench.beta.two"
reason = "The current adapter boundary requires this narrow value import."
expiry = "2099-12-31"
owner_approval = "architecture-owner"
""",
    )

    audit = _audit_fixture(repository_root)

    assert audit["owner_dependency_policy_violations"] == []


def test_dependency_audit_exception_does_not_waive_other_imports_on_same_edge(tmp_path: Path) -> None:
    repository_root = _dependency_fixture(
        tmp_path,
        {
            "alpha/one.py": ("from aec_bench.beta.two import VALUE\nfrom aec_bench.beta.three import OTHER\n"),
            "beta/two.py": "VALUE = 1\n",
            "beta/three.py": "OTHER = 2\n",
        },
        """
[owners.alpha]
may_depend_on = []

[owners.beta]
may_depend_on = []

[exceptions.alpha-beta]
source_owner = "alpha"
target_owner = "beta"
import_prefix = "aec_bench.beta.two"
reason = "The current adapter boundary requires this narrow value import."
expiry = "2099-12-31"
owner_approval = "architecture-owner"
""",
    )

    audit = _audit_fixture(repository_root)

    assert audit["owner_dependency_policy_violations"] == [
        "undeclared owner import: alpha -> aec_bench.beta.three",
    ]


def test_dependency_audit_rejects_expired_exception(tmp_path: Path) -> None:
    repository_root = _dependency_fixture(
        tmp_path,
        {
            "alpha/one.py": "from aec_bench.beta.two import VALUE\n",
            "beta/two.py": "VALUE = 1\n",
        },
        """
[owners.alpha]
may_depend_on = []

[owners.beta]
may_depend_on = []

[exceptions.alpha-beta]
source_owner = "alpha"
target_owner = "beta"
import_prefix = "aec_bench.beta.two"
reason = "Expired test exception."
expiry = "2000-01-01"
owner_approval = "architecture-owner"
""",
    )

    audit = _audit_fixture(repository_root)

    assert audit["owner_dependency_policy_violations"] == [
        "exception is expired: alpha -> beta (aec_bench.beta.two)",
        "undeclared owner import: alpha -> aec_bench.beta.two",
    ]


def test_dependency_audit_rejects_broad_exception_prefix(tmp_path: Path) -> None:
    repository_root = _dependency_fixture(
        tmp_path,
        {"alpha/one.py": ""},
        """
[owners.alpha]
may_depend_on = []

[exceptions.broad]
source_owner = "alpha"
target_owner = "alpha"
import_prefix = "aec_bench.alpha"
reason = "Too broad."
review_condition = "Never"
owner_approval = "architecture-owner"
""",
    )

    audit = _audit_fixture(repository_root)

    assert audit["owner_dependency_policy_violations"] == [
        "owner dependency exception import prefix is too broad: broad"
    ]


def test_dependency_audit_rejects_unenforceable_review_condition(tmp_path: Path) -> None:
    repository_root = _dependency_fixture(
        tmp_path,
        {
            "alpha/one.py": "from aec_bench.beta.two import VALUE\n",
            "beta/two.py": "VALUE = 1\n",
        },
        """
[owners.alpha]
may_depend_on = []

[owners.beta]
may_depend_on = []

[exceptions.unenforceable]
source_owner = "alpha"
target_owner = "beta"
import_prefix = "aec_bench.beta.two"
reason = "Free text cannot be checked."
review_condition = "review this later"
owner_approval = "architecture-owner"
""",
    )

    audit = _audit_fixture(repository_root)

    assert audit["owner_dependency_policy_violations"] == [
        "owner dependency exception review condition is invalid: unenforceable"
    ]


@pytest.mark.parametrize(
    ("review_condition", "expected_violations"),
    (
        ("review-by:2099-12-31", []),
        (
            "review-by:2000-01-01",
            [
                "exception review is overdue: alpha -> beta (aec_bench.beta.two)",
                "undeclared owner import: alpha -> aec_bench.beta.two",
            ],
        ),
    ),
)
def test_dependency_audit_enforces_exception_review_date(
    tmp_path: Path,
    review_condition: str,
    expected_violations: list[str],
) -> None:
    repository_root = _dependency_fixture(
        tmp_path,
        {
            "alpha/one.py": "from aec_bench.beta.two import VALUE\n",
            "beta/two.py": "VALUE = 1\n",
        },
        f"""
[owners.alpha]
may_depend_on = []

[owners.beta]
may_depend_on = []

[exceptions.alpha-beta]
source_owner = "alpha"
target_owner = "beta"
import_prefix = "aec_bench.beta.two"
reason = "The dependency is reviewed on a fixed date."
review_condition = "{review_condition}"
owner_approval = "architecture-owner"
""",
    )

    audit = _audit_fixture(repository_root)

    assert audit["owner_dependency_policy_violations"] == expected_violations


def test_dependency_audit_exception_validation_rejects_unknown_owners() -> None:
    exception = OwnerDependencyException(
        source_owner="missing",
        target_owner="unknown",
        import_prefix="aec_bench.unknown.module",
        reason="test",
        expiry=None,
        review_condition="test review",
        owner_approval="owner",
    )

    violations, allowed_edges = validate_owner_dependency_exceptions({"contracts": set()}, {}, (exception,))

    assert violations == ("exception declares unknown source owner: missing -> unknown (aec_bench.unknown.module)",)
    assert allowed_edges == {}


def test_neutral_contracts_and_domains_do_not_import_optional_runtimes() -> None:
    violations = {
        str(source_path.relative_to(REPOSITORY_ROOT)): sorted(imported)
        for neutral_root in NEUTRAL_ROOTS
        for source_path in neutral_root.rglob("*.py")
        if (imported := _top_level_imports(source_path) & OPTIONAL_RUNTIME_ROOTS)
    }

    assert violations == {}


@pytest.mark.parametrize("owner", ("lifecycles", "worlds"))
def test_task_domains_do_not_import_execution_integrations(owner: str) -> None:
    domain_root = SOURCE_ROOT / owner
    violations = {
        str(source_path.relative_to(REPOSITORY_ROOT)): sorted(
            module for module in _aec_bench_imports(source_path) if module.startswith(FORBIDDEN_TASK_DOMAIN_PREFIXES)
        )
        for source_path in domain_root.rglob("*.py")
        if any(module.startswith(FORBIDDEN_TASK_DOMAIN_PREFIXES) for module in _aec_bench_imports(source_path))
    }

    assert violations == {}


@pytest.mark.parametrize(
    ("runtime_root", "forbidden_prefixes"),
    (
        (
            WORLD_ROOT / "runtime",
            (
                "aec_bench.worlds.catalogue",
                "aec_bench.worlds.monitoring",
                "aec_bench.worlds.stewardship",
            ),
        ),
        (
            LIFECYCLE_ROOT / "runtime",
            (
                "aec_bench.lifecycles.catalogue",
                "aec_bench.lifecycles.stormwater_design",
                "aec_bench.lifecycles.structural_review",
            ),
        ),
    ),
)
def test_shared_environment_runtimes_do_not_import_composition_or_concrete_owners(
    runtime_root: Path,
    forbidden_prefixes: tuple[str, ...],
) -> None:
    assert runtime_root.is_dir()
    violations = {
        str(source_path.relative_to(REPOSITORY_ROOT)): sorted(
            module for module in _aec_bench_imports(source_path) if module.startswith(forbidden_prefixes)
        )
        for source_path in runtime_root.rglob("*.py")
        if any(module.startswith(forbidden_prefixes) for module in _aec_bench_imports(source_path))
    }

    assert violations == {}


@pytest.mark.parametrize(
    ("concrete_roots", "catalogue_prefix"),
    (
        ((WORLD_ROOT / "monitoring", WORLD_ROOT / "stewardship"), "aec_bench.worlds.catalogue"),
        (
            (LIFECYCLE_ROOT / "stormwater_design", LIFECYCLE_ROOT / "structural_review"),
            "aec_bench.lifecycles.catalogue",
        ),
    ),
)
def test_concrete_environment_owners_do_not_import_their_composition_catalogue(
    concrete_roots: tuple[Path, ...],
    catalogue_prefix: str,
) -> None:
    violations = {
        str(source_path.relative_to(REPOSITORY_ROOT)): sorted(
            module for module in _aec_bench_imports(source_path) if module.startswith(catalogue_prefix)
        )
        for root in concrete_roots
        for source_path in root.rglob("*.py")
        if any(module.startswith(catalogue_prefix) for module in _aec_bench_imports(source_path))
    }

    assert violations == {}


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


def test_execution_and_task_owners_do_not_import_learning_study_policy() -> None:
    owner_roots = (
        SOURCE_ROOT / "contracts",
        SOURCE_ROOT / "harness",
        SOURCE_ROOT / "tasks",
        SOURCE_ROOT / "lifecycles",
        SOURCE_ROOT / "worlds",
    )
    forbidden = "aec_bench.experimentation.learning_studies"
    violations = {
        str(source_path.relative_to(REPOSITORY_ROOT)): sorted(
            module for module in _aec_bench_imports(source_path) if module.startswith(forbidden)
        )
        for owner_root in owner_roots
        for source_path in owner_root.rglob("*.py")
        if any(module.startswith(forbidden) for module in _aec_bench_imports(source_path))
    }

    assert violations == {}


def test_learning_study_core_does_not_import_execution_families() -> None:
    core_paths = tuple(LEARNING_STUDIES_ROOT / filename for filename in ("planning.py", "runtime.py", "errors.py"))
    forbidden_prefixes = (
        "aec_bench.adapters",
        "aec_bench.harness",
        "aec_bench.lifecycles",
        "aec_bench.providers",
        "aec_bench.tasks",
        "aec_bench.worlds",
    )
    violations = {
        str(source_path.relative_to(REPOSITORY_ROOT)): sorted(
            module for module in _aec_bench_imports(source_path) if module.startswith(forbidden_prefixes)
        )
        for source_path in core_paths
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


def test_removed_prime_actor_endpoint_and_embedded_client_have_no_residue() -> None:
    removed_terms = (
        "Prime" + "ActorEndpoint",
        "Prime" + "ActorEndpointError",
        "prime_actor_" + "endpoint.py",
    )
    scanned_roots = (
        REPOSITORY_ROOT / "src",
        REPOSITORY_ROOT / "tests",
        REPOSITORY_ROOT / "docs",
    )
    this_test = Path(__file__).resolve()
    violations = {
        str(path.relative_to(REPOSITORY_ROOT)): sorted(term for term in removed_terms if term in text)
        for root in scanned_roots
        for path in root.rglob("*")
        if path.is_file()
        and path.resolve() != this_test
        and path.suffix in {".md", ".py", ".toml"}
        and (text := path.read_text(encoding="utf-8"))
        and any(term in text for term in removed_terms)
    }
    prime_world_skill = SOURCE_ROOT / "prime_agent" / "skill_packages" / "aec-world"

    assert violations == {}
    assert sorted(
        path.relative_to(prime_world_skill).as_posix() for path in prime_world_skill.rglob("*") if path.is_file()
    ) == ["SKILL.md"]


def test_generic_world_actor_boundary_has_no_prime_or_aec_runtime_client_dependency() -> None:
    world_actor_root = SOURCE_ROOT / "harness" / "world_actor"
    implementation_paths = tuple(world_actor_root.glob("*.py"))
    provider_imports = {
        str(path.relative_to(REPOSITORY_ROOT)): sorted(
            module for module in _aec_bench_imports(path) if module.startswith("aec_bench.prime_agent")
        )
        for path in implementation_paths
        if any(module.startswith("aec_bench.prime_agent") for module in _aec_bench_imports(path))
    }
    client_root = world_actor_root / "client_package" / "aec_world"
    client_source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(client_root.glob("*.py")))

    assert provider_imports == {}
    assert "aec_bench" not in client_source


def test_package_dependency_audit_rejects_owner_cycles_and_boundary_leaks() -> None:
    audit = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "scripts" / "audit_package_dependencies.py"),
            "--repository-root",
            str(REPOSITORY_ROOT),
            "--check",
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert audit.returncode == 0, audit.stdout + audit.stderr


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
