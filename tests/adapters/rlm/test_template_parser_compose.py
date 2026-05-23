# ABOUTME: Tests compose-mode parsing in report_template.toml — block dispatch + validation.
# ABOUTME: Covers the bridge between TOML section definitions and the templates.report composer.

import pytest

from aec_bench.adapters.rlm.template_parser import parse_report_template
from aec_bench.contracts.report_template import (
    FillBlock,
    GeneratedBlock,
    VerbatimBlock,
)

_COMPOSE_TOML = """\
[[sections]]
id = "the_site"
title = "The Site"
generation_mode = "compose"
fields = { site_text = "str" }

[[sections.blocks]]
type = "verbatim"
ref = "the_site.condition.preamble"

[[sections.blocks]]
type = "fill"
ref = "the_site.access.access_route"
sources = ["project_brief:site_information"]

[[sections.blocks]]
type = "generated"
prompt = "Write base-specific access constraints."
sources = ["project_brief:site_constraints"]
"""


def _section_named(schema, name):
    matches = [s for s in schema.sections if s.id == name]
    assert matches, f"section {name!r} not in schema"
    return matches[0]


def test_compose_section_parses_blocks_in_declaration_order():
    schema = parse_report_template(_COMPOSE_TOML)
    section = _section_named(schema, "the_site")
    assert section.generation_mode == "compose"
    assert section.blocks is not None
    assert len(section.blocks) == 3


def test_compose_section_dispatches_each_block_to_the_correct_subtype():
    schema = parse_report_template(_COMPOSE_TOML)
    section = _section_named(schema, "the_site")
    verbatim, fill, generated = section.blocks
    assert isinstance(verbatim, VerbatimBlock)
    assert verbatim.ref == "the_site.condition.preamble"
    assert isinstance(fill, FillBlock)
    assert fill.sources == ("project_brief:site_information",)
    assert isinstance(generated, GeneratedBlock)
    assert generated.prompt == "Write base-specific access constraints."


def test_non_compose_section_has_no_blocks():
    """Backward compatibility — sections without compose mode must not gain a blocks list."""
    toml = """\
[[sections]]
id = "intro"
title = "Introduction"
generation_mode = "transform"
fields = { purpose = "str" }
"""
    schema = parse_report_template(toml)
    section = _section_named(schema, "intro")
    assert section.blocks is None


def test_compose_mode_without_blocks_is_an_error():
    """A section declaring compose mode but providing no blocks is a configuration bug."""
    toml = """\
[[sections]]
id = "broken"
title = "Broken"
generation_mode = "compose"
fields = { x = "str" }
"""
    with pytest.raises(ValueError, match="compose.*blocks"):
        parse_report_template(toml)


def test_blocks_present_without_compose_mode_is_an_error():
    """Blocks belong to compose mode — declaring them on transform/guided is a typo we catch."""
    toml = """\
[[sections]]
id = "wrong_mode"
title = "Wrong"
generation_mode = "transform"
fields = { x = "str" }

[[sections.blocks]]
type = "verbatim"
ref = "x"
"""
    with pytest.raises(ValueError, match="blocks.*compose"):
        parse_report_template(toml)
