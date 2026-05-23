# ABOUTME: Tests the compose-mode renderer that assembles report sections from blocks.
# ABOUTME: Stub SlotResolver/BlockGenerator implementations exercise the full block dispatch.

from collections.abc import Mapping, Sequence

import pytest

from aec_bench.contracts.report_template import (
    BoilerplateFragment,
    FillBlock,
    GeneratedBlock,
    VerbatimBlock,
)
from aec_bench.templates.report.composer import (
    FragmentNotFoundError,
    UnresolvedSlotError,
    detect_slots,
    lookup_fragment,
    render_section,
)


class StubResolver:
    """Returns a configured slot dict — no LLM."""

    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)
        self.calls: list[tuple[BoilerplateFragment, tuple[str, ...]]] = []

    def resolve(
        self,
        fragment: BoilerplateFragment,
        sources: Sequence[str],
        task: object = None,  # Idea C: composer passes block.task; stub ignores
    ) -> Mapping[str, str]:
        self.calls.append((fragment, tuple(sources)))
        # Return only configured slots — composer is responsible for spotting gaps.
        return {slot: self._values[slot] for slot in fragment.slots if slot in self._values}


class StubGenerator:
    """Returns a configured response string — no LLM."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def generate(
        self,
        prompt: str,
        sources: Sequence[str],
        task: object = None,
    ) -> str:
        self.calls.append((prompt, tuple(sources)))
        return self._response


# ─── lookup_fragment ───────────────────────────────────────────────────────────


def test_lookup_fragment_resolves_dotted_path():
    fragments = {"the_site": {"condition": {"preamble": "Site is operational."}}}
    assert lookup_fragment(fragments, "the_site.condition.preamble") == "Site is operational."


def test_lookup_fragment_resolves_top_level():
    fragments = {"opening": "Top-level text."}
    assert lookup_fragment(fragments, "opening") == "Top-level text."


def test_lookup_fragment_raises_on_missing_path():
    fragments = {"the_site": {"condition": {"preamble": "x"}}}
    with pytest.raises(FragmentNotFoundError, match="the_site.access.route"):
        lookup_fragment(fragments, "the_site.access.route")


def test_lookup_fragment_flattens_sub_table_into_joined_text():
    """A ref pointing at a sub-table joins all string descendants with paragraph breaks.

    TOML preserves declaration order, so the joined output reflects file order —
    that's the contract authors rely on when they put `heading` first.
    """
    fragments = {
        "general_requirements": {
            "general": {
                "heading": "## 8.1 General",
                "structural_stability": "The Contractor shall ensure stability.",
            },
            "safe_design": {
                "heading": "## 8.2 Safe Design",
                "process": "Design has involved a safe design process.",
                "contractor": "The Contractor shall review and implement.",
            },
        },
    }
    result = lookup_fragment(fragments, "general_requirements")
    assert result == (
        "## 8.1 General\n\n"
        "The Contractor shall ensure stability.\n\n"
        "## 8.2 Safe Design\n\n"
        "Design has involved a safe design process.\n\n"
        "The Contractor shall review and implement."
    )


def test_lookup_fragment_flattens_single_subsection():
    fragments = {
        "the_site": {
            "condition": {
                "heading": "## 7.1 Site Condition",
                "preamble": "Site is operational.",
                "operational": "Site shall remain operational.",
            },
        },
    }
    result = lookup_fragment(fragments, "the_site.condition")
    assert result == ("## 7.1 Site Condition\n\nSite is operational.\n\nSite shall remain operational.")


def test_lookup_fragment_skips_non_string_non_dict_values():
    """Numbers, booleans, lists shouldn't appear in the joined output."""
    fragments = {
        "x": {
            "ok": "kept",
            "skip_int": 42,
            "skip_bool": True,
            "skip_list": ["a", "b"],
        },
    }
    assert lookup_fragment(fragments, "x") == "kept"


def test_lookup_fragment_raises_when_subtable_has_no_strings():
    fragments = {"empty": {"nested": {}}}
    with pytest.raises(FragmentNotFoundError, match="empty"):
        lookup_fragment(fragments, "empty")


def test_lookup_fragment_raises_when_path_is_neither_string_nor_subtable():
    """An int/bool/list at the resolved path can't be rendered."""
    fragments = {"weird": {"value": 42}}
    with pytest.raises(FragmentNotFoundError, match="neither a string nor a sub-table"):
        lookup_fragment(fragments, "weird.value")


# ─── detect_slots ──────────────────────────────────────────────────────────────


def test_detect_slots_finds_double_brace_markers():
    assert detect_slots("Access via the {{base_access_point}}.") == ("base_access_point",)


def test_detect_slots_returns_each_slot_once_in_order():
    text = "{{a}} then {{b}} then {{a}} again."
    assert detect_slots(text) == ("a", "b")


def test_detect_slots_returns_empty_tuple_for_plain_text():
    assert detect_slots("No placeholders here.") == ()


# ─── render_section: verbatim ──────────────────────────────────────────────────


def test_render_verbatim_block_returns_fragment_text_as_is():
    fragments = {"the_site": {"condition": {"preamble": "Site remains operational."}}}
    result, _trace = render_section(
        blocks=[VerbatimBlock(ref="the_site.condition.preamble")],
        fragments=fragments,
        slot_resolver=StubResolver({}),
        block_generator=StubGenerator(""),
    )
    assert result == "Site remains operational."


def test_render_verbatim_block_with_missing_ref_raises_with_block_index():
    with pytest.raises(FragmentNotFoundError, match="block 0"):
        render_section(
            blocks=[VerbatimBlock(ref="missing.path")],
            fragments={},
            slot_resolver=StubResolver({}),
            block_generator=StubGenerator(""),
        )


# ─── render_section: fill ──────────────────────────────────────────────────────


def test_render_fill_block_with_no_slots_skips_resolver():
    fragments = {"clause": "Plain text, no slots."}
    resolver = StubResolver({})
    render_section(
        blocks=[FillBlock(ref="clause")],
        fragments=fragments,
        slot_resolver=resolver,
        block_generator=StubGenerator(""),
    )
    assert resolver.calls == []


def test_render_fill_block_substitutes_slot_values():
    fragments = {"access_route": "Access via the {{base_access_point}}."}
    resolver = StubResolver({"base_access_point": "Pass Office Gate 3"})
    result, _trace = render_section(
        blocks=[FillBlock(ref="access_route", sources=("brief:site",))],
        fragments=fragments,
        slot_resolver=resolver,
        block_generator=StubGenerator(""),
    )
    assert result == "Access via the Pass Office Gate 3."


def test_render_fill_block_passes_sources_to_resolver():
    fragments = {"x": "{{slot_a}}"}
    resolver = StubResolver({"slot_a": "value"})
    render_section(
        blocks=[FillBlock(ref="x", sources=("brief:foo", "design_report:bar"))],
        fragments=fragments,
        slot_resolver=resolver,
        block_generator=StubGenerator(""),
    )
    _fragment, sources = resolver.calls[0]
    assert sources == ("brief:foo", "design_report:bar")


def test_render_fill_block_substitutes_repeated_slots():
    fragments = {"x": "{{name}} shall {{action}} the {{name}}."}
    resolver = StubResolver({"name": "Contractor", "action": "secure"})
    result, _trace = render_section(
        blocks=[FillBlock(ref="x")],
        fragments=fragments,
        slot_resolver=resolver,
        block_generator=StubGenerator(""),
    )
    assert result == "Contractor shall secure the Contractor."


def test_render_fill_block_raises_when_resolver_misses_a_slot():
    fragments = {"x": "{{declared}} and {{missing}}."}
    resolver = StubResolver({"declared": "ok"})
    with pytest.raises(UnresolvedSlotError, match="missing"):
        render_section(
            blocks=[FillBlock(ref="x")],
            fragments=fragments,
            slot_resolver=resolver,
            block_generator=StubGenerator(""),
        )


# ─── render_section: generated ─────────────────────────────────────────────────


def test_render_generated_block_returns_generator_output():
    generator = StubGenerator("Project-specific access constraints text.")
    result, _trace = render_section(
        blocks=[
            GeneratedBlock(
                prompt="Write access constraints for RAAF Base East Sale.",
                sources=("brief:constraints",),
            ),
        ],
        fragments={},
        slot_resolver=StubResolver({}),
        block_generator=generator,
    )
    assert result == "Project-specific access constraints text."
    assert generator.calls == [
        ("Write access constraints for RAAF Base East Sale.", ("brief:constraints",)),
    ]


# ─── render_section: composition ───────────────────────────────────────────────


def test_render_section_concatenates_blocks_with_paragraph_breaks():
    fragments = {
        "preamble": "Preamble text.",
        "clause": "Clause text.",
    }
    result, _trace = render_section(
        blocks=[
            VerbatimBlock(ref="preamble"),
            VerbatimBlock(ref="clause"),
            GeneratedBlock(prompt="anything"),
        ],
        fragments=fragments,
        slot_resolver=StubResolver({}),
        block_generator=StubGenerator("Generated bit."),
    )
    assert result == "Preamble text.\n\nClause text.\n\nGenerated bit."


def test_render_section_with_empty_block_list_returns_empty_string():
    result, _trace = render_section(
        blocks=[],
        fragments={},
        slot_resolver=StubResolver({}),
        block_generator=StubGenerator(""),
    )
    assert result == ""


def test_render_section_full_hybrid_example():
    """The_site shape: verbatim preamble + slot-filled access + generated constraints."""
    fragments = {
        "the_site": {
            "condition": {"preamble": "The Site remains operational throughout."},
            "access": {
                "access_route": "The Contractor shall access via the {{access_point}}.",
            },
        },
    }
    blocks = [
        VerbatimBlock(ref="the_site.condition.preamble"),
        FillBlock(ref="the_site.access.access_route", sources=("brief:site",)),
        GeneratedBlock(prompt="Note any base-specific constraints.", sources=("brief:notes",)),
    ]
    result, _trace = render_section(
        blocks=blocks,
        fragments=fragments,
        slot_resolver=StubResolver({"access_point": "Pass Office Gate 3"}),
        block_generator=StubGenerator("Constraint: night work prohibited."),
    )
    assert result == (
        "The Site remains operational throughout.\n\n"
        "The Contractor shall access via the Pass Office Gate 3.\n\n"
        "Constraint: night work prohibited."
    )


# ─── render_section: composition trace ─────────────────────────────────────────


def test_render_section_trace_captures_block_provenance():
    """Each block produces one trace entry carrying type, ref/prompt, sources, slots."""
    fragments = {
        "preamble": "Static preamble.",
        "access": "Access via the {{gate}}.",
    }
    blocks = [
        VerbatimBlock(ref="preamble"),
        FillBlock(ref="access", sources=("brief:site",)),
        GeneratedBlock(prompt="Closing note.", sources=("brief:notes",)),
    ]
    _text, trace = render_section(
        blocks=blocks,
        fragments=fragments,
        slot_resolver=StubResolver({"gate": "Pass Office"}),
        block_generator=StubGenerator("Closing rendered."),
    )

    assert len(trace) == 3

    assert trace[0].block_type == "verbatim"
    assert trace[0].ref == "preamble"
    assert trace[0].text == "Static preamble."
    assert trace[0].resolved_slots == {}

    assert trace[1].block_type == "fill"
    assert trace[1].ref == "access"
    assert trace[1].sources == ("brief:site",)
    assert trace[1].resolved_slots == {"gate": "Pass Office"}
    assert trace[1].text == "Access via the Pass Office."

    assert trace[2].block_type == "generated"
    assert trace[2].prompt == "Closing note."
    assert trace[2].sources == ("brief:notes",)
    assert trace[2].text == "Closing rendered."


def test_render_section_trace_offsets_slice_back_to_block_text():
    """Invariant: section_text[start:end] == entry.text for every trace entry."""
    fragments = {
        "a": "First block text.",
        "b": "Second block with {{slot}}.",
    }
    blocks = [
        VerbatimBlock(ref="a"),
        FillBlock(ref="b"),
        GeneratedBlock(prompt="gen"),
    ]
    text, trace = render_section(
        blocks=blocks,
        fragments=fragments,
        slot_resolver=StubResolver({"slot": "FILLED"}),
        block_generator=StubGenerator("Third block output."),
    )

    for entry in trace:
        assert text[entry.start_offset : entry.end_offset] == entry.text


def test_render_section_trace_block_indexes_are_sequential():
    fragments = {"a": "A", "b": "B", "c": "C"}
    _text, trace = render_section(
        blocks=[VerbatimBlock(ref="a"), VerbatimBlock(ref="b"), VerbatimBlock(ref="c")],
        fragments=fragments,
        slot_resolver=StubResolver({}),
        block_generator=StubGenerator(""),
    )
    assert [t.block_index for t in trace] == [0, 1, 2]


def test_render_fill_without_slots_records_empty_resolved_slots():
    fragments = {"clause": "No slots at all."}
    _text, trace = render_section(
        blocks=[FillBlock(ref="clause")],
        fragments=fragments,
        slot_resolver=StubResolver({}),
        block_generator=StubGenerator(""),
    )
    assert trace[0].block_type == "fill"
    assert trace[0].resolved_slots == {}
    assert trace[0].text == "No slots at all."


# ─── Task 12: provenance surfaces into BlockTrace ─────────────────────────────


def test_render_section_records_block_provenance_for_generated_block():
    """A generated block's BlockTrace exposes provenance from the generator."""
    from aec_bench.contracts.report_template import GeneratedBlock
    from aec_bench.templates.report.composer import render_section

    class _StubGenerator:
        def __init__(self):
            self.last_provenance: tuple[str, ...] = ()
            self.last_declared_provenance: tuple[str, ...] = ()
            self.last_fetched_provenance: tuple[str, ...] = ()

        def generate(self, prompt, sources, task=None):
            self.last_declared_provenance = tuple(sources)
            self.last_fetched_provenance = ("brief.md#schedule",)  # simulate tool-use
            self.last_provenance = self.last_declared_provenance + self.last_fetched_provenance
            return "generated text"

    class _StubResolver:
        def resolve(self, fragment, sources, task=None):
            return {}

    blocks = (GeneratedBlock(prompt="Write.", sources=("brief.md#scope",)),)
    text, trace = render_section(blocks, {}, _StubResolver(), _StubGenerator())
    assert trace[0].block_type == "generated"
    assert trace[0].declared_provenance == ("brief.md#scope",)
    assert trace[0].fetched_provenance == ("brief.md#schedule",)
    assert trace[0].provenance == ("brief.md#scope", "brief.md#schedule")


def test_render_section_records_slot_provenance_for_fill_block():
    """A fill block's BlockTrace exposes per-slot provenance from the resolver."""
    from aec_bench.contracts.report_template import FillBlock
    from aec_bench.templates.report.composer import render_section

    class _StubResolver:
        def __init__(self):
            self.last_slot_provenance: dict[str, tuple[str, ...]] = {}

        def resolve(self, fragment, sources, task=None):
            self.last_slot_provenance = {slot: tuple(sources) for slot in fragment.slots}
            return {slot: f"VAL_{slot}" for slot in fragment.slots}

    class _StubGenerator:
        def generate(self, prompt, sources, task=None):
            return ""

    fragments = {"fragments": {"intro": "The site is {{site}}."}}
    blocks = (FillBlock(ref="fragments.intro", sources=("brief.md#header",)),)
    text, trace = render_section(blocks, fragments, _StubResolver(), _StubGenerator())
    assert trace[0].block_type == "fill"
    assert trace[0].declared_provenance == ("brief.md#header",)
    assert trace[0].provenance == ("brief.md#header",)
    assert trace[0].slot_provenance == {"site": ("brief.md#header",)}


def test_render_section_with_resolver_lacking_provenance_attrs_uses_defaults():
    """Back-compat: a resolver without last_slot_provenance attr → empty defaults."""
    from aec_bench.contracts.report_template import FillBlock
    from aec_bench.templates.report.composer import render_section

    class _BareResolver:
        def resolve(self, fragment, sources, task=None):
            return {slot: f"v_{slot}" for slot in fragment.slots}

    class _BareGenerator:
        def generate(self, prompt, sources, task=None):
            return ""

    fragments = {"fragments": {"intro": "Hello {{name}}."}}
    blocks = (FillBlock(ref="fragments.intro", sources=("brief.md",)),)
    text, trace = render_section(blocks, fragments, _BareResolver(), _BareGenerator())
    assert trace[0].slot_provenance == {}  # default — resolver had no last_slot_provenance
    assert trace[0].declared_provenance == ("brief.md",)  # composer fills this from block.sources
