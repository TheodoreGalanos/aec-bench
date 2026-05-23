# ABOUTME: Tests for the report_template.toml parser.
# ABOUTME: Verifies that TOML section definitions are correctly parsed into DependencyTreeSchema.
"""Tests for report_template.toml parsing."""

from aec_bench.adapters.rlm.template_parser import (
    parse_report_template,
    parse_report_template_with_rubric,
)
from aec_bench.contracts.repl import DependencyTreeSchema
from aec_bench.contracts.rubric import RubricCriterion

_TEMPLATE_TOML = """\
[meta]
name = "Test Report"
description = "A test template"

[[sections]]
id = "background"
title = "Background"
depends_on = []
generation_mode = "transform"
fields = [
    { name = "context", dtype = "str", description = "Project context" },
]
writing_guidance = ["Describe the project"]
input_mapping = ["brief:Background"]

[[sections]]
id = "design"
title = "Design"
depends_on = ["background"]
generation_mode = "guided"
per_discipline = true
fields = [
    { name = "features", dtype = "str", description = "Key features" },
    { name = "process", dtype = "str", description = "Design process" },
]
writing_guidance = ["Reframe the scope", "Add rationale"]
input_mapping = ["brief:Scope"]
"""


def test_parse_produces_dependency_tree_schema() -> None:
    schema = parse_report_template(_TEMPLATE_TOML)
    assert isinstance(schema, DependencyTreeSchema)
    assert len(schema.sections) == 2


def test_parse_captures_section_metadata() -> None:
    schema = parse_report_template(_TEMPLATE_TOML)
    bg = schema.sections[0]
    assert bg.id == "background"
    assert bg.generation_mode == "transform"
    assert len(bg.writing_guidance) == 1
    assert bg.input_mapping == ("brief:Background",)


def test_parse_captures_dependencies() -> None:
    schema = parse_report_template(_TEMPLATE_TOML)
    design = schema.sections[1]
    assert design.depends_on == ("background",)
    assert design.per_discipline is True


def test_parse_captures_fields() -> None:
    schema = parse_report_template(_TEMPLATE_TOML)
    design = schema.sections[1]
    assert "features" in design.fields
    assert design.fields["features"].dtype == "str"


def test_parse_minimal_section() -> None:
    toml_str = """\
[meta]
name = "Minimal"

[[sections]]
id = "only"
title = "Only Section"
fields = [{ name = "value", dtype = "float", description = "A value" }]
"""
    schema = parse_report_template(toml_str)
    assert len(schema.sections) == 1
    assert schema.sections[0].depends_on == ()
    assert schema.sections[0].generation_mode is None


_TEMPLATE_WITH_RUBRIC = """\
[meta]
name = "Test Report"

[[sections]]
id = "background"
title = "Background"
fields = [{ name = "context", dtype = "str", description = "Context" }]

[rubric]
rollup_strategy = "weighted_mean"

[[rubric.dimensions]]
id = "completeness"
name = "Completeness"
description = "All sections filled"
weight = 1.0
max_score = 10.0
eval_method = "automated"
criteria = ["All sections present", "No gaps"]

[[rubric.dimensions]]
id = "accuracy"
name = "Technical Accuracy"
description = "Calculations correct"
weight = 2.0
max_score = 10.0
eval_method = "llm_judge"
criteria = ["Values correct", "Standards applied"]
"""


def test_parse_with_rubric_returns_schema_and_rubric() -> None:
    schema, rubric = parse_report_template_with_rubric(_TEMPLATE_WITH_RUBRIC)
    assert len(schema.sections) == 1
    assert rubric is not None
    assert len(rubric.dimensions) == 2


def test_parse_rubric_captures_dimension_metadata() -> None:
    _, rubric = parse_report_template_with_rubric(_TEMPLATE_WITH_RUBRIC)
    assert rubric is not None
    completeness = rubric.dimensions[0]
    assert completeness.id == "completeness"
    assert completeness.weight == 1.0
    assert completeness.eval_method == "automated"
    assert len(completeness.criteria) == 2


def test_parse_rubric_captures_rollup_strategy() -> None:
    _, rubric = parse_report_template_with_rubric(_TEMPLATE_WITH_RUBRIC)
    assert rubric is not None
    assert rubric.rollup_strategy == "weighted_mean"


def test_parse_without_rubric_returns_none() -> None:
    toml_str = """\
[meta]
name = "No Rubric"

[[sections]]
id = "only"
title = "Only"
fields = [{ name = "x", dtype = "float", description = "X" }]
"""
    schema, rubric = parse_report_template_with_rubric(toml_str)
    assert len(schema.sections) == 1
    assert rubric is None


_TEMPLATE_WITH_TYPED_CRITERIA = """\
[meta]
name = "Test Report"

[[sections]]
id = "background"
title = "Background"
fields = [{ name = "context", dtype = "str", description = "Context" }]

[rubric]
rollup_strategy = "weighted_mean"

[[rubric.dimensions]]
id = "completeness"
name = "Completeness"
description = "All sections filled"
weight = 1.0
max_score = 10.0
eval_method = "automated"
criteria = [
    { text = "All sections present", category = "essential" },
    { text = "Fields non-empty", category = "important" },
]

[[rubric.dimensions]]
id = "depth"
name = "Technical Depth"
description = "Specificity of content"
weight = 2.0
max_score = 10.0
eval_method = "llm_judge"
criteria = [
    { text = "Specific measurements cited", category = "essential" },
    { text = "Named infrastructure", category = "optional" },
]
"""


def test_parse_typed_criteria_returns_rubric_criterion() -> None:
    _, rubric = parse_report_template_with_rubric(_TEMPLATE_WITH_TYPED_CRITERIA)
    assert rubric is not None
    completeness = rubric.dimensions[0]
    assert len(completeness.criteria) == 2
    assert isinstance(completeness.criteria[0], RubricCriterion)
    assert completeness.criteria[0].text == "All sections present"
    assert completeness.criteria[0].category == "essential"


def test_parse_typed_criteria_preserves_categories() -> None:
    _, rubric = parse_report_template_with_rubric(_TEMPLATE_WITH_TYPED_CRITERIA)
    assert rubric is not None
    depth = rubric.dimensions[1]
    assert depth.criteria[0].category == "essential"
    assert depth.criteria[1].category == "optional"


def test_parse_fields_dict_of_dicts_reads_required() -> None:
    toml = """
[[sections]]
id = "drawing_register"
title = "Drawing Register"
generation_mode = "transform"

[sections.fields]
number   = { dtype = "str", description = "drawing reference", required = true }
title    = { dtype = "str", description = "title in ALL CAPS",  required = true }
revision = { dtype = "str", description = "revision letter" }
"""
    schema = parse_report_template(toml)
    sec = schema.sections[0]
    assert sec.fields["number"].required is True
    assert sec.fields["title"].required is True
    assert sec.fields["revision"].required is False  # default


def test_parse_fields_array_of_tables_reads_required() -> None:
    toml = """
[[sections]]
id = "background"
title = "Background"
fields = [
    { name = "context", dtype = "str", description = "ctx", required = true },
    { name = "extras",  dtype = "str", description = "x" },
]
"""
    schema = parse_report_template(toml)
    sec = schema.sections[0]
    assert sec.fields["context"].required is True
    assert sec.fields["extras"].required is False


def test_parse_fields_inline_string_form_required_defaults_false() -> None:
    """Existing `field_name = "dtype"` shorthand never sets required."""
    toml = """
[[sections]]
id = "foo"
title = "Foo"

[sections.fields]
some_table = "table"
"""
    schema = parse_report_template(toml)
    sec = schema.sections[0]
    assert sec.fields["some_table"].required is False
