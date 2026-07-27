# ABOUTME: Enforces the narrow repository-owned documentation boundary.
# ABOUTME: Keeps public guides, examples, and research records with their actual owners.

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"
EXPECTED_REPOSITORY_DOCS = {
    "AGENTS.md",
    "ARCHITECTURE.md",
    "CONTRACTS.md",
    "INVARIANTS.md",
    "PROJECT_STRUCTURE.md",
}


def test_docs_contains_only_repository_authoritative_markdown() -> None:
    actual = {path.relative_to(DOCS_ROOT).as_posix() for path in DOCS_ROOT.rglob("*") if path.is_file()}

    assert actual == EXPECTED_REPOSITORY_DOCS


def test_meta_harness_fixtures_live_outside_docs() -> None:
    fixture_root = REPO_ROOT / "tests" / "fixtures" / "meta_harness"

    assert (fixture_root / "logic-profile" / "aecbench-verifier-event-world.json").is_file()
    assert (fixture_root / "operation-profile" / "orchestrator-plan.json").is_file()
    assert (fixture_root / "world-process" / "problem-space-brief.json").is_file()
    assert not (DOCS_ROOT / "examples").exists()


def test_readme_routes_public_guides_to_the_documentation_site() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "https://aecbench.com/docs/advanced/meta-harness-runtime" in readme
    assert "https://aecbench.com/docs/advanced/prime-lab" in readme
    assert "docs/meta-harness-guide.md" not in readme
    assert "docs/prime-lab-guide.md" not in readme
