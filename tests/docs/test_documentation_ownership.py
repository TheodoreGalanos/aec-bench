# ABOUTME: Enforces the repository documentation taxonomy, routing, and relative-link integrity.
# ABOUTME: Keeps current authorities separate from history, public guides, fixtures, and stale guidance.

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"
SKILL_ROOT = REPO_ROOT / "src" / "aec_bench" / "init" / "skill_data"
DOMAIN_CHECK_ROOT = SKILL_ROOT / "domain-check"
EXPECTED_REPOSITORY_DOCS = {
    "AGENTS.md",
    "ARCHITECTURE.md",
    "CONTRACTS.md",
    "INVARIANTS.md",
    "PROVENANCE_POLICY.md",
    "PROJECT_STRUCTURE.md",
    "README.md",
    "adr/learning-studies-gate-a.md",
    "adr/learning-studies-lifecycle-l01-review.md",
    "plans/artifact-task-composition.md",
    "plans/evolution-functional-composition.md",
    "plans/environment-category-contracts.md",
    "plans/lifecycle-functional-composition.md",
    "plans/prime-world-boundary-study.md",
    "plans/repository-architecture-implementation.md",
    "plans/repository-architecture-study.md",
    "protocols/interactive-world-runtime.md",
    "protocols/staged-evidence-and-publication.md",
    "research/learning-studies/l01-deterministic-evidence.md",
    "research/learning-studies/l01-relation-domain-review.md",
    "research/learning-studies/programme.md",
    "research/learning-studies/release-a/GATE-A-artifact-substrate-extraction.md",
    "research/learning-studies/release-a/LS-00-programme-boundary-and-semantic-cleanup.md",
    "research/learning-studies/release-a/LS-01A-study-contracts-and-compilation.md",
    "research/learning-studies/release-a/LS-01B-study-runtime-and-arm-isolation.md",
    "research/learning-studies/release-a/LS-02A-recording-lineage-and-resume.md",
    "research/learning-studies/release-a/LS-02B-controlled-validity-and-learning-assessment.md",
    "research/learning-studies/release-a/LS-03-learning-family-authoring.md",
    "research/learning-studies/release-a/LS-04A-artifact-learning-adapter.md",
    "research/learning-studies/release-a/README.md",
    "research/learning-studies/release-a/studies/A01-artifact-structural-transfer.md",
    "research/learning-studies/release-a/studies/A02-artifact-applicability-boundary.md",
    "research/learning-studies/release-a/studies/A03-artifact-retention-and-interference.md",
    "research/learning-studies/release-a/studies/A04-artifact-composition.md",
    "world-authoring.md",
}
MAINTAINED_INDEX_TARGETS = {
    "AGENTS.md",
    "ARCHITECTURE.md",
    "CONTRACTS.md",
    "INVARIANTS.md",
    "PROVENANCE_POLICY.md",
    "PROJECT_STRUCTURE.md",
    "README.md",
    "adr/learning-studies-gate-a.md",
    "adr/learning-studies-lifecycle-l01-review.md",
    "plans/artifact-task-composition.md",
    "plans/evolution-functional-composition.md",
    "plans/environment-category-contracts.md",
    "plans/lifecycle-functional-composition.md",
    "plans/prime-world-boundary-study.md",
    "plans/repository-architecture-implementation.md",
    "plans/repository-architecture-study.md",
    "protocols/interactive-world-runtime.md",
    "protocols/staged-evidence-and-publication.md",
    "world-authoring.md",
}
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\((?P<target>[^)]+)\)")
FIXED_TEST_COUNT = re.compile(r"\b\d[\d,]*\s+(?:tests?|test cases)\b", re.IGNORECASE)
RETIRED_CONTINUAL_WORLD_DOC = "docs/CONTINUAL_WORLD_RUNTIME.md"


def test_docs_contains_only_maintained_repository_markdown() -> None:
    actual = {path.relative_to(DOCS_ROOT).as_posix() for path in DOCS_ROOT.rglob("*") if path.is_file()}

    assert actual == EXPECTED_REPOSITORY_DOCS


def test_documentation_index_lists_every_maintained_document() -> None:
    indexed_targets = set(_relative_markdown_targets(DOCS_ROOT / "README.md")) & MAINTAINED_INDEX_TARGETS

    assert indexed_targets == MAINTAINED_INDEX_TARGETS


def test_repository_markdown_relative_links_resolve() -> None:
    markdown_files = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "AGENTS.md",
        *sorted(DOCS_ROOT.rglob("*.md")),
        *sorted(SKILL_ROOT.rglob("*.md")),
    ]
    missing: list[str] = []
    for source in markdown_files:
        for target in _relative_markdown_targets(source):
            destination = (source.parent / unquote(target)).resolve()
            if not destination.exists():
                missing.append(f"{source.relative_to(REPO_ROOT)} -> {target}")

    assert missing == []


def test_retired_continual_world_document_is_not_referenced() -> None:
    current_guidance = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "AGENTS.md",
        *sorted(DOCS_ROOT.rglob("*.md")),
        *sorted(SKILL_ROOT.rglob("*.md")),
    ]

    assert not (DOCS_ROOT / "CONTINUAL_WORLD_RUNTIME.md").exists()
    assert all(RETIRED_CONTINUAL_WORLD_DOC not in path.read_text(encoding="utf-8") for path in current_guidance)


def test_agent_guides_do_not_freeze_test_counts() -> None:
    guides = (REPO_ROOT / "AGENTS.md", DOCS_ROOT / "AGENTS.md")

    assert all(FIXED_TEST_COUNT.search(path.read_text(encoding="utf-8")) is None for path in guides)


def test_root_agent_guide_routes_world_authors_to_current_guidance() -> None:
    root_guidance = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    current_guidance = (REPO_ROOT / "AGENTS.md", *sorted(DOCS_ROOT.rglob("*.md")))

    assert "docs/world-authoring.md" in root_guidance
    assert all(
        "WORLD_AUTHORING_GUIDE.md" not in path.read_text(encoding="utf-8")
        and "WORLD_CONFORMANCE_CHECKLIST.md" not in path.read_text(encoding="utf-8")
        for path in current_guidance
    )


def test_installed_domain_check_guidance_uses_current_authorities() -> None:
    guidance = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            DOMAIN_CHECK_ROOT / "SKILL.md",
            DOMAIN_CHECK_ROOT / "references" / "domain-routing.md",
            DOMAIN_CHECK_ROOT / "references" / "invariants-compact.md",
        )
    )

    assert "docs/README.md" in guidance
    assert "docs/protocols/interactive-world-runtime.md" in guidance
    assert "10 invariants" not in guidance
    assert "original 7" not in guidance


def test_packaged_skills_do_not_reference_retired_runtime_paths() -> None:
    guidance_files = [*sorted(SKILL_ROOT.rglob("*.md")), *sorted(SKILL_ROOT.rglob("evals.json"))]
    guidance = "\n".join(path.read_text(encoding="utf-8") for path in guidance_files)
    retired_terms = {
        "96 across 3 domains",
        "Only `import math`",
        "legacy script",
        "script (legacy)",
        "src/aec_bench/continual/",
        "src/aec_bench/task_worlds/",
        "src/aec_bench/providers/ interface",
        "terzaghi_bearing/",
    }

    assert all(term not in guidance for term in retired_terms)


def test_packaged_meta_harness_skill_uses_the_functional_api_boundary() -> None:
    guidance = (SKILL_ROOT / "meta-harness" / "SKILL.md").read_text(encoding="utf-8")
    workflows = (SKILL_ROOT / "meta-harness" / "references" / "experiment-workflows.md").read_text(encoding="utf-8")

    assert "aec_bench.experimentation.meta_harness" in guidance
    assert "aec_bench.experimentation.meta_harness" in workflows
    assert "Always set `max_rounds`" in workflows
    assert "not interactive worlds" in guidance


def test_meta_harness_fixtures_live_outside_docs() -> None:
    fixture_root = REPO_ROOT / "tests" / "fixtures" / "meta_harness"

    assert (fixture_root / "logic-profile" / "aecbench-verifier-event-world.json").is_file()
    assert (fixture_root / "operation-profile" / "orchestrator-plan.json").is_file()
    assert (fixture_root / "world-process" / "problem-space-brief.json").is_file()
    assert not (DOCS_ROOT / "examples").exists()


def test_readme_links_only_to_published_specific_guides() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "https://aecbench.com/docs/advanced/meta-harness-runtime" not in readme
    assert "https://aecbench.com/docs/advanced/prime-lab" in readme
    assert "docs/meta-harness-guide.md" not in readme
    assert "docs/prime-lab-guide.md" not in readme


def _relative_markdown_targets(source: Path) -> tuple[str, ...]:
    targets: list[str] = []
    for match in MARKDOWN_LINK.finditer(source.read_text(encoding="utf-8")):
        raw_target = match.group("target").strip()
        if raw_target.startswith("<") and raw_target.endswith(">"):
            raw_target = raw_target[1:-1]
        else:
            raw_target = raw_target.split(maxsplit=1)[0]
        target = raw_target.split("#", maxsplit=1)[0]
        if not target or target.startswith("/") or urlsplit(target).scheme:
            continue
        targets.append(target)
    return tuple(targets)
