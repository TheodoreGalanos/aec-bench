# ABOUTME: Tests for the ReportTemplate active REPL object.
# ABOUTME: Verifies fill state tracking, dependency enforcement, progress, and submission.

from __future__ import annotations

from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.contracts.repl import DependencyTreeSchema, OutputField, TreeSection


def _make_simple_tree() -> DependencyTreeSchema:
    return DependencyTreeSchema(
        sections=[
            TreeSection(
                id="background",
                title="Background",
                fields={
                    "context": OutputField(
                        name="context",
                        dtype="str",
                        description="Context",
                    )
                },
                depends_on=[],
                generation_mode="transform",
                writing_guidance=["Describe the project context"],
            ),
            TreeSection(
                id="design",
                title="Design",
                fields={
                    "features": OutputField(
                        name="features",
                        dtype="str",
                        description="Key features",
                    )
                },
                depends_on=["background"],
                generation_mode="guided",
            ),
            TreeSection(
                id="risks",
                title="Risks",
                fields={
                    "risk_table": OutputField(
                        name="risk_table",
                        dtype="str",
                        description="Risk register",
                    )
                },
                depends_on=["design"],
            ),
        ]
    )


def test_initial_status_shows_all_pending() -> None:
    tpl = ReportTemplate(_make_simple_tree())
    status = tpl.get_status()
    assert status.total_sections == 3
    assert status.completed_sections == 0
    assert "background" in status.unlocked


def test_fill_section_succeeds_when_deps_met() -> None:
    tpl = ReportTemplate(_make_simple_tree())
    result = tpl.fill_section("background", {"context": "Project in Sydney"})
    assert result.success
    assert tpl.get_status().completed_sections == 1


def test_fill_section_fails_when_deps_not_met() -> None:
    tpl = ReportTemplate(_make_simple_tree())
    result = tpl.fill_section("design", {"features": "New intersection"})
    assert not result.success
    assert "background" in result.error.lower()


def test_fill_section_unlocks_dependents() -> None:
    tpl = ReportTemplate(_make_simple_tree())
    tpl.fill_section("background", {"context": "Project in Sydney"})
    status = tpl.get_status()
    assert "design" in status.unlocked
    assert "risks" not in status.unlocked


def test_get_dependencies() -> None:
    tpl = ReportTemplate(_make_simple_tree())
    deps = tpl.get_dependencies("risks")
    assert deps == ["design"]


def test_get_section_context_returns_filled_data() -> None:
    tpl = ReportTemplate(_make_simple_tree())
    tpl.fill_section("background", {"context": "Sydney project"})
    ctx = tpl.get_section_context("design")
    assert "background" in ctx
    assert ctx["background"]["context"] == "Sydney project"


def test_get_section_context_empty_when_deps_not_filled() -> None:
    tpl = ReportTemplate(_make_simple_tree())
    ctx = tpl.get_section_context("design")
    assert ctx == {}


def test_get_writing_guidance() -> None:
    tpl = ReportTemplate(_make_simple_tree())
    guidance = tpl.get_writing_guidance("background")
    assert "Describe the project context" in guidance


def test_submit_when_all_complete() -> None:
    tpl = ReportTemplate(_make_simple_tree())
    tpl.fill_section("background", {"context": "Sydney"})
    tpl.fill_section("design", {"features": "Intersection upgrade"})
    tpl.fill_section("risks", {"risk_table": "Utility conflicts"})
    result = tpl.submit()
    assert result.complete
    assert len(result.sections) == 3


def test_submit_when_incomplete() -> None:
    tpl = ReportTemplate(_make_simple_tree())
    tpl.fill_section("background", {"context": "Sydney"})
    result = tpl.submit()
    assert not result.complete
    assert len(result.gaps) == 2


def test_fill_unknown_section_returns_error() -> None:
    tpl = ReportTemplate(_make_simple_tree())
    result = tpl.fill_section("nonexistent", {"x": 1})
    assert not result.success
    assert "unknown" in result.error.lower()


def test_refill_section_overwrites() -> None:
    tpl = ReportTemplate(_make_simple_tree())
    tpl.fill_section("background", {"context": "Old"})
    tpl.fill_section("background", {"context": "New"})
    ctx = tpl.get_section_context("design")
    assert ctx["background"]["context"] == "New"
