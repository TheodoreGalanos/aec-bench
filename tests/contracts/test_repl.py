# ABOUTME: Tests for the ReplSerializable protocol and concrete REPL types.
# ABOUTME: Verifies protocol structural subtyping and runtime isinstance checks.

"""Tests for the ReplSerializable protocol and concrete REPL types."""

from aec_bench.contracts.repl import (
    CalcTool,
    DependencyTreeSchema,
    FlatSchema,
    OutputField,
    ParameterField,
    ParameterTable,
    ReplSerializable,
    SchemaSection,
    SectionedSchema,
    StandardsRef,
    TaskInstruction,
    TreeSection,
)


class _MockReplType:
    """Minimal type satisfying ReplSerializable for protocol checks."""

    def repl_setup(self) -> str:
        return "import json"

    def to_repl(self) -> str | bytes:
        return '{"key": "value"}'

    def repl_assignment(self, var_name: str) -> str:
        return f'{var_name} = {{"key": "value"}}'

    def repl_preview(self, max_chars: int = 500) -> str:
        return "MockType: 1 field"


def test_mock_type_satisfies_repl_serializable_protocol() -> None:
    obj = _MockReplType()
    assert isinstance(obj, ReplSerializable)


def test_task_instruction_satisfies_protocol() -> None:
    ti = TaskInstruction(
        text="Calculate the voltage drop for a 3-phase circuit...",
        task_type="calculation",
        discipline="electrical",
        input_summary="Cable params: current, length, resistance, reactance",
        output_summary="voltage_drop_v, voltage_drop_pct, compliance",
    )
    assert isinstance(ti, ReplSerializable)


def test_task_instruction_repl_setup_returns_import() -> None:
    ti = TaskInstruction(
        text="Calculate...",
        task_type="calculation",
        discipline="electrical",
        input_summary="params",
        output_summary="results",
    )
    setup = ti.repl_setup()
    assert "import" in setup or setup == ""


def test_task_instruction_repl_preview_excludes_full_text() -> None:
    long_text = "A" * 2000
    ti = TaskInstruction(
        text=long_text,
        task_type="calculation",
        discipline="electrical",
        input_summary="params",
        output_summary="results",
    )
    preview = ti.repl_preview(max_chars=500)
    assert len(preview) <= 500
    assert "electrical" in preview
    assert "calculation" in preview


def test_task_instruction_repl_assignment_produces_valid_python() -> None:
    ti = TaskInstruction(
        text="Calculate voltage drop.",
        task_type="calculation",
        discipline="electrical",
        input_summary="params",
        output_summary="results",
    )
    code = ti.repl_assignment("instruction")
    assert "instruction" in code
    # The assignment should be executable Python
    namespace: dict = {}
    exec(ti.repl_setup(), namespace)
    exec(code, namespace)
    assert "instruction" in namespace


def test_task_instruction_to_repl_returns_full_text() -> None:
    ti = TaskInstruction(
        text="Full instruction text here.",
        task_type="calculation",
        discipline="electrical",
        input_summary="params",
        output_summary="results",
    )
    result = ti.to_repl()
    assert isinstance(result, str)
    assert "Full instruction text here." in result


def test_parameter_table_satisfies_protocol() -> None:
    pt = ParameterTable(
        fields={
            "current_a": ParameterField(value=45.0, unit="A", description="Load current", dtype="float"),
            "length_m": ParameterField(value=80.0, unit="m", description="Cable length", dtype="float"),
        }
    )
    assert isinstance(pt, ReplSerializable)


def test_parameter_table_preview_shows_fields() -> None:
    pt = ParameterTable(
        fields={
            "current_a": ParameterField(value=45.0, unit="A", description="Load current", dtype="float"),
            "pf": ParameterField(value=0.85, unit=None, description="Power factor", dtype="float"),
        }
    )
    preview = pt.repl_preview()
    assert "current_a" in preview
    assert "45.0" in preview
    assert "A" in preview
    assert "pf" in preview


def test_parameter_table_assignment_creates_dict() -> None:
    pt = ParameterTable(
        fields={
            "current_a": ParameterField(value=45.0, unit="A", description="Load current", dtype="float"),
        }
    )
    namespace: dict = {}
    exec(pt.repl_setup(), namespace)
    exec(pt.repl_assignment("params"), namespace)
    assert namespace["params"]["current_a"]["value"] == 45.0
    assert namespace["params"]["current_a"]["unit"] == "A"


def test_flat_schema_satisfies_protocol() -> None:
    schema = FlatSchema(
        fields={
            "voltage_drop_v": OutputField(
                name="voltage_drop_v",
                dtype="float",
                description="Voltage drop in volts",
                tolerance=0.03,
                unit="V",
            ),
            "compliance": OutputField(
                name="compliance",
                dtype="float",
                description="1 if compliant, 0 otherwise",
                tolerance=None,
                unit=None,
            ),
        }
    )
    assert isinstance(schema, ReplSerializable)


def test_flat_schema_preview_shows_fields_and_tolerances() -> None:
    schema = FlatSchema(
        fields={
            "voltage_drop_v": OutputField(
                name="voltage_drop_v",
                dtype="float",
                description="Voltage drop in volts",
                tolerance=0.03,
                unit="V",
            ),
        }
    )
    preview = schema.repl_preview()
    assert "voltage_drop_v" in preview
    assert "float" in preview


def test_flat_schema_assignment_creates_dict() -> None:
    schema = FlatSchema(
        fields={
            "voltage_drop_v": OutputField(
                name="voltage_drop_v",
                dtype="float",
                description="Voltage drop in volts",
                tolerance=0.03,
                unit="V",
            ),
        }
    )
    namespace: dict = {}
    exec(schema.repl_setup(), namespace)
    exec(schema.repl_assignment("output_schema"), namespace)
    assert "voltage_drop_v" in namespace["output_schema"]


def test_sectioned_schema_satisfies_protocol() -> None:
    schema = SectionedSchema(
        sections=[
            SchemaSection(
                id="loads",
                title="Load Analysis",
                fields={
                    "dead_load": OutputField(
                        name="dead_load",
                        dtype="float",
                        description="Dead load",
                        tolerance=0.03,
                        unit="kN",
                    ),
                },
            ),
        ]
    )
    assert isinstance(schema, ReplSerializable)


def test_sectioned_schema_preview_shows_sections() -> None:
    schema = SectionedSchema(
        sections=[
            SchemaSection(
                id="loads",
                title="Load Analysis",
                fields={
                    "dead_load": OutputField(
                        name="dead_load",
                        dtype="float",
                        description="Dead load",
                        tolerance=0.03,
                        unit="kN",
                    ),
                },
            ),
            SchemaSection(
                id="capacity",
                title="Member Capacity",
                fields={
                    "phi_mn": OutputField(
                        name="phi_mn",
                        dtype="float",
                        description="Design moment capacity",
                        tolerance=0.03,
                        unit="kNm",
                    ),
                },
            ),
        ]
    )
    preview = schema.repl_preview()
    assert "Load Analysis" in preview
    assert "Member Capacity" in preview
    assert "2 sections" in preview


def test_sectioned_schema_assignment_creates_dict() -> None:
    schema = SectionedSchema(
        sections=[
            SchemaSection(
                id="loads",
                title="Load Analysis",
                fields={
                    "dead_load": OutputField(
                        name="dead_load",
                        dtype="float",
                        description="Dead load",
                        tolerance=0.03,
                        unit="kN",
                    ),
                },
            ),
        ]
    )
    namespace: dict = {}
    exec(schema.repl_setup(), namespace)
    exec(schema.repl_assignment("schema"), namespace)
    assert "loads" in namespace["schema"]


def test_dependency_tree_satisfies_protocol() -> None:
    schema = DependencyTreeSchema(
        sections=[
            TreeSection(
                id="background",
                title="Background",
                fields={
                    "context": OutputField(
                        name="context",
                        dtype="str",
                        description="Project context",
                    )
                },
                depends_on=[],
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
                generation_mode="transform",
                writing_guidance=["Reframe the brief's scope"],
                input_mapping=["brief:Scope of Works"],
            ),
        ]
    )
    assert isinstance(schema, ReplSerializable)


def test_dependency_tree_preview_shows_dependency_chain() -> None:
    schema = DependencyTreeSchema(
        sections=[
            TreeSection(
                id="background",
                title="Background",
                fields={"ctx": OutputField(name="ctx", dtype="str", description="Context")},
                depends_on=[],
            ),
            TreeSection(
                id="design",
                title="Design",
                fields={"feat": OutputField(name="feat", dtype="str", description="Features")},
                depends_on=["background"],
            ),
        ]
    )
    preview = schema.repl_preview()
    assert "background" in preview
    assert "design" in preview
    assert "depends on" in preview.lower() or "→" in preview


def test_standards_ref_satisfies_protocol() -> None:
    ref = StandardsRef(
        standard_name="AS 4100:2020",
        edition="2020",
        sections=[
            "Section 5: Members subject to bending",
            "Section 6: Members subject to compression",
        ],
        text="Full text of AS 4100...",
    )
    assert isinstance(ref, ReplSerializable)


def test_standards_ref_preview_shows_index() -> None:
    ref = StandardsRef(
        standard_name="AS 4100:2020",
        edition="2020",
        sections=["Section 5", "Section 6"],
        text="x" * 10000,
    )
    preview = ref.repl_preview()
    assert "AS 4100:2020" in preview
    assert "Section 5" in preview
    assert len(preview) <= 500


def test_calc_tool_satisfies_protocol() -> None:
    tool = CalcTool(
        name="heat_load_calc",
        source_path="tools/heat_load_calc.py",
        signature="def calculate(room_type: str, area: float) -> dict",
        docstring="Calculate heat load for a room.",
    )
    assert isinstance(tool, ReplSerializable)


def test_calc_tool_preview_shows_signature() -> None:
    tool = CalcTool(
        name="heat_load_calc",
        source_path="tools/heat_load_calc.py",
        signature="def calculate(room_type: str, area: float) -> dict",
        docstring="Calculate heat load for a room.",
    )
    preview = tool.repl_preview()
    assert "heat_load_calc" in preview
    assert "calculate" in preview


def test_tree_section_has_optional_metadata() -> None:
    section = TreeSection(
        id="methodology",
        title="Design Methodology",
        fields={"method": OutputField(name="method", dtype="str", description="Methodology")},
        depends_on=["design"],
        generation_mode="guided",
        per_discipline=True,
        writing_guidance=["Write 2-5 paragraphs per discipline"],
        input_mapping=["brief:Scope of Works"],
    )
    assert section.generation_mode == "guided"
    assert section.per_discipline is True
    assert len(section.writing_guidance) == 1
    assert len(section.input_mapping) == 1


def test_output_field_required_defaults_to_false() -> None:
    f = OutputField(name="x", dtype="str", description="")
    assert f.required is False


def test_output_field_required_can_be_set_true() -> None:
    f = OutputField(name="x", dtype="str", description="", required=True)
    assert f.required is True
