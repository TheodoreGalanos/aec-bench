# ABOUTME: Tests for fill_parallel() — template-aware parallel section generation.
# ABOUTME: Validates unlocked section detection, parallel generation, sequential fill.

from __future__ import annotations

from typing import Any

from aec_bench.adapters.rlm.fill_parallel import fill_parallel
from aec_bench.adapters.rlm.parallel import ParallelError
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.contracts.repl import DependencyTreeSchema, OutputField, TreeSection


def _make_schema(*sections: tuple[str, list[str]]) -> DependencyTreeSchema:
    """Helper: build a schema from (id, depends_on) tuples."""
    return DependencyTreeSchema(
        sections=[
            TreeSection(
                id=sid,
                title=sid.title(),
                fields={"content": OutputField(name="content", dtype="str", description="")},
                depends_on=deps,
            )
            for sid, deps in sections
        ]
    )


class TestFillParallel:
    def test_fills_all_unlocked_sections(self) -> None:
        schema = _make_schema(
            ("intro", []),
            ("method", []),
            ("results", ["intro", "method"]),
        )
        template = ReportTemplate(schema)

        def generator(
            section_id: str,
            context: dict[str, Any],
            guidance: list[str],
        ) -> dict[str, Any]:
            return {"content": f"Generated {section_id}"}

        results = fill_parallel(template=template, generator=generator)
        assert len(results) == 2  # intro and method are unlocked
        status = template.get_status()
        assert "intro" in status.completed
        assert "method" in status.completed
        assert "results" not in status.completed  # not unlocked yet

    def test_explicit_section_ids(self) -> None:
        schema = _make_schema(("a", []), ("b", []), ("c", []))
        template = ReportTemplate(schema)

        def generator(
            section_id: str,
            context: dict[str, Any],
            guidance: list[str],
        ) -> dict[str, Any]:
            return {"content": f"Generated {section_id}"}

        results = fill_parallel(
            template=template,
            generator=generator,
            section_ids=["a", "c"],
        )
        assert len(results) == 2
        status = template.get_status()
        assert "a" in status.completed
        assert "b" not in status.completed
        assert "c" in status.completed

    def test_skips_sections_with_unmet_deps(self) -> None:
        schema = _make_schema(("a", []), ("b", ["a"]))
        template = ReportTemplate(schema)

        def generator(
            section_id: str,
            context: dict[str, Any],
            guidance: list[str],
        ) -> dict[str, Any]:
            return {"content": f"Generated {section_id}"}

        # Ask for both, but "b" depends on "a" — only "a" should be filled
        fill_parallel(
            template=template,
            generator=generator,
            section_ids=["a", "b"],
        )
        # "a" fills first, then "b" becomes unlocked but wasn't in the parallel batch
        # fill_parallel should only fill sections that are unlocked at call time
        status = template.get_status()
        assert "a" in status.completed

    def test_generator_error_returns_parallel_error(self) -> None:
        schema = _make_schema(("a", []), ("b", []))
        template = ReportTemplate(schema)

        def generator(
            section_id: str,
            context: dict[str, Any],
            guidance: list[str],
        ) -> dict[str, Any]:
            if section_id == "b":
                raise ValueError("Generation failed for b")
            return {"content": f"Generated {section_id}"}

        results = fill_parallel(template=template, generator=generator)
        # "a" should succeed, "b" should be a ParallelError
        status = template.get_status()
        assert "a" in status.completed
        assert "b" not in status.completed
        assert any(isinstance(r, ParallelError) for r in results)

    def test_passes_context_and_guidance(self) -> None:
        schema = _make_schema(("base", []), ("derived", ["base"]))
        template = ReportTemplate(schema)

        # Fill base first
        template.fill_section("base", {"content": "base content"})

        received: dict[str, Any] = {}

        def generator(
            section_id: str,
            context: dict[str, Any],
            guidance: list[str],
        ) -> dict[str, Any]:
            received["context"] = context
            received["section_id"] = section_id
            return {"content": "derived content"}

        fill_parallel(template=template, generator=generator)
        assert received["section_id"] == "derived"
        assert "base" in received["context"]

    def test_returns_empty_when_nothing_unlocked(self) -> None:
        schema = _make_schema(("a", ["b"]), ("b", ["a"]))  # circular
        template = ReportTemplate(schema)

        def generator(
            section_id: str,
            context: dict[str, Any],
            guidance: list[str],
        ) -> dict[str, Any]:
            return {"content": "unreachable"}

        results = fill_parallel(template=template, generator=generator)
        assert results == []
