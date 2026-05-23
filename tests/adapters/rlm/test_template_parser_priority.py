# ABOUTME: Tests parse_report_template handling of the dict-form input_mapping with optional priority.
# ABOUTME: Verifies backwards-compat with list form and correctness of priority parsing.

from aec_bench.adapters.rlm.template_parser import parse_report_template


def test_list_form_input_mapping_has_empty_source_priority():
    toml = """
[[sections]]
id = "intro"
title = "Intro"
writing_guidance = ["crisp"]
generation_mode = "prose"
input_mapping = ["design_report:intro"]
"""
    schema = parse_report_template(toml)
    section = schema.sections[0]
    assert section.input_mapping == ("design_report:intro",)
    assert section.source_priority == {}


def test_dict_form_without_priority_still_works():
    toml = """
[[sections]]
id = "intro"
title = "Intro"
writing_guidance = ["crisp"]
generation_mode = "prose"

[sections.input_mapping]
sources = ["design_report:intro", "project_brief:intro"]
"""
    schema = parse_report_template(toml)
    section = schema.sections[0]
    assert section.input_mapping == ("design_report:intro", "project_brief:intro")
    assert section.source_priority == {}


def test_dict_form_with_priority():
    toml = """
[[sections]]
id = "scope"
title = "Scope"
writing_guidance = ["crisp"]
generation_mode = "prose"

[sections.input_mapping]
sources = ["design_report:discipline", "project_brief:site"]

[sections.input_mapping.priority]
"design_report:discipline" = 1
"project_brief:site" = 4
"""
    schema = parse_report_template(toml)
    section = schema.sections[0]
    assert section.input_mapping == ("design_report:discipline", "project_brief:site")
    assert section.source_priority == {
        "design_report:discipline": 1,
        "project_brief:site": 4,
    }


def test_dict_form_priority_with_extra_keys_is_preserved():
    """Priority can reference sources not in the current list; parser preserves them."""
    toml = """
[[sections]]
id = "scope"
title = "Scope"
writing_guidance = ["crisp"]
generation_mode = "prose"

[sections.input_mapping]
sources = ["design_report:discipline"]

[sections.input_mapping.priority]
"design_report:discipline" = 1
"legacy:thing" = 9
"""
    schema = parse_report_template(toml)
    section = schema.sections[0]
    assert section.source_priority["legacy:thing"] == 9


def test_dict_form_supports_arbitrary_tier_counts():
    toml = """
[[sections]]
id = "scope"
title = "Scope"
writing_guidance = ["crisp"]
generation_mode = "prose"

[sections.input_mapping]
sources = ["a:x", "b:x", "c:x", "d:x", "e:x"]

[sections.input_mapping.priority]
"a:x" = 1
"b:x" = 2
"c:x" = 3
"d:x" = 4
"e:x" = 5
"""
    schema = parse_report_template(toml)
    section = schema.sections[0]
    assert len(section.source_priority) == 5
