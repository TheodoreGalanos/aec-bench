# ABOUTME: Pydantic contract models defining the structure of a valid task generation template.
# ABOUTME: Models cover parameter spaces, output expectations, archetypes, and difficulty presets.

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.validators import StrictModel, ensure_non_empty_string


class ToolMode(StrEnum):
    WITH_TOOL = "with-tool"
    NO_TOOL = "no-tool"
    BOTH = "both"


class ParamType(StrEnum):
    FLOAT = "float"
    INT = "int"
    ENUM = "enum"


class VisibilityLevel(StrEnum):
    ALL_GIVEN = "all_given"
    PARTIAL = "partial"
    SCENARIO_ONLY = "scenario_only"


class TemplateMeta(StrictModel):
    """Metadata describing a task generation template."""

    name: str
    description: str
    long_description: str = ""
    discipline: str
    category: str
    standards: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    tool_mode: ToolMode

    @field_validator("name", "description", "discipline", "category")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        return ensure_non_empty_string(value)


class ParamSpec(StrictModel):
    """Specification for a single parameter in a template's parameter space."""

    type: ParamType
    description: str
    unit: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    values: list[str] | None = None
    default: Any | None = None
    optional: bool = False
    derivable_from: str | None = None

    @model_validator(mode="after")
    def validate_type_constraints(self) -> "ParamSpec":
        if self.type in {ParamType.FLOAT, ParamType.INT}:
            if self.min_value is None or self.max_value is None:
                msg = "float and int params require both min_value and max_value"
                raise ValueError(msg)
        if self.type is ParamType.ENUM:
            if not self.values:
                msg = "enum params require a non-empty values list"
                raise ValueError(msg)
        return self


class OutputSpec(StrictModel):
    """Specification for a single expected output of a template."""

    description: str
    tolerance: float = 0.03

    @field_validator("description")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        return ensure_non_empty_string(value)


class ArchetypeRange(StrictModel):
    """Min/max range for a parameter within an archetype."""

    min: float
    max: float


class ArchetypeSpec(StrictModel):
    """A named soil or site archetype with associated parameter ranges."""

    description: str
    site_contexts: list[str]
    params: dict[str, ArchetypeRange]


class DifficultyPreset(StrictModel):
    """Configuration for one difficulty level of a template."""

    description: str
    visibility: VisibilityLevel
    archetypes: list[str]
    # Parameters hidden from the agent at this difficulty level (inferred from context).
    hidden_params: list[str] = Field(default_factory=list)
    replacement_text: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_partial_visibility(self) -> "DifficultyPreset":
        if self.visibility is VisibilityLevel.PARTIAL and not self.hidden_params:
            msg = "partial visibility requires at least one hidden_param"
            raise ValueError(msg)
        return self


class TemplateConfig(StrictModel):
    """Top-level configuration for a task generation template.

    Constraint evaluation (the `constraints` list) is deferred to Phase 2.
    """

    meta: TemplateMeta
    params: dict[str, ParamSpec]
    outputs: dict[str, OutputSpec]
    archetypes: dict[str, ArchetypeSpec] = Field(default_factory=dict)
    difficulty: dict[str, DifficultyPreset] = Field(default_factory=dict)
    # Constraint expressions are stored as strings and evaluated in Phase 2.
    constraints: list[str] = Field(default_factory=list)
