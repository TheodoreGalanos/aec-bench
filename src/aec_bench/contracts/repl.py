# ABOUTME: Protocol and concrete types for RLM REPL symbolic handles.
# ABOUTME: Defines how domain types present themselves to an agent's REPL environment.

from __future__ import annotations

import json
import textwrap
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from aec_bench.contracts.report_template import Block


@runtime_checkable
class ReplSerializable(Protocol):
    """Protocol for domain types that can be injected into an RLM REPL.

    Defines how a type is set up, serialised, assigned, and previewed
    in the agent's persistent Python execution environment. This is a
    presentation contract — how domain data presents itself to an agent's
    reasoning environment.
    """

    def repl_setup(self) -> str:
        """Return Python import statements needed in the REPL for this type."""
        ...

    def to_repl(self) -> str | bytes:
        """Serialise this object for transfer into the REPL."""
        ...

    def repl_assignment(self, var_name: str) -> str:
        """Return Python code that reconstructs this object as var_name."""
        ...

    def repl_preview(self, max_chars: int = 500) -> str:
        """Generate an LLM-friendly preview — metadata, not full content."""
        ...


@dataclass(frozen=True)
class TaskInstruction:
    """Wraps task instruction text as a REPL symbolic handle.

    The preview shows task structure (type, discipline, I/O summary)
    without the full instruction text. The agent accesses full text
    through code in the REPL.
    """

    text: str
    task_type: str
    discipline: str
    input_summary: str
    output_summary: str

    def repl_setup(self) -> str:
        """Return Python import statements needed in the REPL for this type."""
        return "import textwrap"

    def to_repl(self) -> str:
        """Return the full instruction text for transfer into the REPL."""
        return self.text

    def repl_assignment(self, var_name: str) -> str:
        """Return Python code that assigns the instruction text to var_name."""
        escaped = self.text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
        return f'{var_name} = """{escaped}"""'

    def repl_preview(self, max_chars: int = 500) -> str:
        """Generate an LLM-friendly preview — metadata and short text excerpt, not full content."""
        prefix = textwrap.shorten(self.text, width=200, placeholder="...")
        lines = [
            f"TaskInstruction [{self.discipline}/{self.task_type}]",
            f"  Inputs:  {self.input_summary}",
            f"  Outputs: {self.output_summary}",
            "",
            f"  Preview: {prefix}",
        ]
        preview = "\n".join(lines)
        return preview[:max_chars]


@dataclass(frozen=True)
class ParameterField:
    """A single input parameter with value, unit, and type metadata."""

    value: float | str | int
    unit: str | None
    description: str
    dtype: str


@dataclass(frozen=True)
class JsonReplMixin:
    """Mixin providing standard JSON-based REPL serialization.

    Subclasses must implement to_repl() and repl_preview().
    """

    def repl_setup(self) -> str:
        """Return Python import statements needed in the REPL for this type."""
        return "import json"

    def repl_assignment(self, var_name: str) -> str:
        """Return Python code that reconstructs this object as var_name via JSON."""
        return f"{var_name} = json.loads('''{self.to_repl()}''')"


@dataclass(frozen=True)
class ParameterTable(JsonReplMixin):
    """Wraps structured input parameters as a REPL symbolic handle.

    Preview shows field names, types, units, and values.
    In the REPL, available as a dict of dicts.
    """

    fields: Mapping[str, ParameterField]

    def to_repl(self) -> str:
        """Serialise parameters as a JSON string for transfer into the REPL."""
        data = {
            name: {"value": f.value, "unit": f.unit, "description": f.description, "dtype": f.dtype}
            for name, f in self.fields.items()
        }
        return json.dumps(data)

    def repl_preview(self, max_chars: int = 500) -> str:
        """Generate an LLM-friendly preview showing field names, values, units, and types."""
        lines = [f"ParameterTable: {len(self.fields)} fields", ""]
        for name, f in self.fields.items():
            unit_str = f" [{f.unit}]" if f.unit else ""
            lines.append(f"  {name}: {f.value}{unit_str} ({f.dtype}) — {f.description}")
        preview = "\n".join(lines)
        return preview[:max_chars]


@dataclass(frozen=True)
class OutputField:
    """A single expected output field with type and tolerance metadata."""

    name: str
    dtype: str
    description: str
    tolerance: float | None = None
    unit: str | None = None
    required: bool = False


@dataclass(frozen=True)
class FlatSchema(JsonReplMixin):
    """Wraps a flat output schema (independent fields) as a REPL symbolic handle.

    Suited for simple calculation tasks where fields are independent.
    """

    fields: Mapping[str, OutputField]

    def to_repl(self) -> str:
        """Serialise output schema as a JSON string for transfer into the REPL."""
        data = {
            name: {
                "name": f.name,
                "dtype": f.dtype,
                "description": f.description,
                "tolerance": f.tolerance,
                "unit": f.unit,
            }
            for name, f in self.fields.items()
        }
        return json.dumps(data)

    def repl_preview(self, max_chars: int = 500) -> str:
        """Generate an LLM-friendly preview showing field names, types, tolerances, and units."""
        lines = [f"OutputSchema (flat): {len(self.fields)} fields", ""]
        for name, f in self.fields.items():
            unit_str = f" [{f.unit}]" if f.unit else ""
            tol_str = f" ±{f.tolerance:.0%}" if f.tolerance else " (exact)"
            lines.append(f"  {name}: {f.dtype}{unit_str}{tol_str} — {f.description}")
        preview = "\n".join(lines)
        return preview[:max_chars]


@dataclass(frozen=True)
class SchemaSection:
    """A named group of output fields within a sectioned schema."""

    id: str
    title: str
    fields: Mapping[str, OutputField]


@dataclass(frozen=True)
class TreeSection:
    """A section in a dependency tree with optional generation metadata.

    When ``generation_mode == "compose"``, ``blocks`` carries the ordered
    block list assembled by ``aec_bench.templates.report.composer``. Other
    modes leave ``blocks`` as ``None``.
    """

    id: str
    title: str
    fields: Mapping[str, OutputField]
    depends_on: Sequence[str] = ()
    generation_mode: str | None = None
    per_discipline: bool = False
    writing_guidance: Sequence[str] = ()
    input_mapping: Sequence[str] = ()
    source_priority: Mapping[str, int] = field(default_factory=dict)
    blocks: tuple[Block, ...] | None = None


@dataclass(frozen=True)
class SectionedSchema(JsonReplMixin):
    """Wraps a sectioned output schema (independent groups) as a REPL handle.

    Suited for multi-step calculations where fields group naturally
    but groups don't depend on each other.
    """

    sections: Sequence[SchemaSection]

    def to_repl(self) -> str:
        """Serialise the sectioned schema as a JSON string for transfer into the REPL."""
        data = {
            s.id: {
                "title": s.title,
                "fields": {
                    name: {
                        "name": f.name,
                        "dtype": f.dtype,
                        "description": f.description,
                        "tolerance": f.tolerance,
                        "unit": f.unit,
                    }
                    for name, f in s.fields.items()
                },
            }
            for s in self.sections
        }
        return json.dumps(data)

    def repl_preview(self, max_chars: int = 500) -> str:
        """Generate an LLM-friendly preview listing sections and their field names."""
        lines = [f"OutputSchema (sectioned): {len(self.sections)} sections", ""]
        for s in self.sections:
            field_names = ", ".join(s.fields.keys())
            lines.append(f"  [{s.id}] {s.title}: {field_names}")
        preview = "\n".join(lines)
        return preview[:max_chars]


@dataclass(frozen=True)
class DependencyTreeSchema(JsonReplMixin):
    """Wraps a dependency-tree output schema as a REPL handle.

    Sections declare dependencies forming a DAG. Suited for
    report-generation tasks where later sections build on earlier ones.
    """

    sections: Sequence[TreeSection]

    def to_repl(self) -> str:
        """Serialise the dependency tree schema as a JSON string for transfer into the REPL."""
        data = {
            s.id: {
                "title": s.title,
                "depends_on": list(s.depends_on),
                "generation_mode": s.generation_mode,
                "per_discipline": s.per_discipline,
                "writing_guidance": list(s.writing_guidance),
                "input_mapping": list(s.input_mapping),
                "source_priority": dict(s.source_priority),
                "fields": {
                    name: {
                        "name": f.name,
                        "dtype": f.dtype,
                        "description": f.description,
                        "tolerance": f.tolerance,
                        "unit": f.unit,
                    }
                    for name, f in s.fields.items()
                },
            }
            for s in self.sections
        }
        return json.dumps(data)

    def repl_preview(self, max_chars: int = 500) -> str:
        """Generate an LLM-friendly preview showing sections and their dependency chain."""
        lines = [
            f"OutputSchema (dependency tree): {len(self.sections)} sections",
            "",
        ]
        for s in self.sections:
            deps = f" → depends on: {', '.join(s.depends_on)}" if s.depends_on else ""
            mode = f" [{s.generation_mode}]" if s.generation_mode else ""
            lines.append(f"  {s.id}: {s.title}{mode}{deps}")
        preview = "\n".join(lines)
        return preview[:max_chars]


@dataclass(frozen=True)
class StandardsRef:
    """Wraps reference standard text as a REPL symbolic handle.

    Preview shows standard name, edition, and section index.
    Full text is accessible in the REPL for searching.
    """

    standard_name: str
    edition: str
    sections: Sequence[str]
    text: str

    def repl_setup(self) -> str:
        """Return Python import statements needed in the REPL for this type."""
        return "import re"

    def to_repl(self) -> str:
        """Return the full standard text for transfer into the REPL."""
        return self.text

    def repl_assignment(self, var_name: str) -> str:
        """Return Python code that assigns the standard text to var_name."""
        escaped = self.text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
        return f'{var_name} = """{escaped}"""'

    def repl_preview(self, max_chars: int = 500) -> str:
        """Generate an LLM-friendly preview showing standard name, edition, and section index."""
        lines = [
            f"StandardsRef: {self.standard_name} ({self.edition})",
            f"  {len(self.sections)} sections:",
        ]
        for s in self.sections[:10]:
            lines.append(f"    - {s}")
        if len(self.sections) > 10:
            lines.append(f"    ... and {len(self.sections) - 10} more")
        lines.append(f"  Full text: {len(self.text):,} chars")
        preview = "\n".join(lines)
        return preview[:max_chars]


@dataclass(frozen=True)
class CalcTool:
    """Wraps a domain-specific calculation tool as a REPL symbolic handle.

    Preview shows function name, signature, and docstring.
    The tool source is importable in the REPL.
    """

    name: str
    source_path: str
    signature: str
    docstring: str

    def repl_setup(self) -> str:
        """Return Python import statements needed in the REPL for this type."""
        return ""

    def to_repl(self) -> str:
        """Return the source path for transfer into the REPL."""
        return self.source_path

    def repl_assignment(self, var_name: str) -> str:
        """Return Python code that assigns the source path to var_name."""
        return f'{var_name} = "{self.source_path}"'

    def repl_preview(self, max_chars: int = 500) -> str:
        """Generate an LLM-friendly preview showing tool name, source, signature, and docstring."""
        lines = [
            f"CalcTool: {self.name}",
            f"  Source: {self.source_path}",
            f"  Signature: {self.signature}",
            f"  {self.docstring}",
        ]
        preview = "\n".join(lines)
        return preview[:max_chars]
