# ABOUTME: Declares actor-visible report writing checks without evaluation policy.
# ABOUTME: Validates rule scope, pattern syntax, and explicit visibility at ingestion.

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import Field, model_validator

from aec_bench.contracts.validators import StrictModel


class ReportRule(StrictModel):
    id: str = Field(min_length=1)
    kind: Literal["required_pattern", "forbidden_pattern", "prose"]
    message: str = Field(min_length=1)
    severity: Literal["error", "warning"] = "error"
    sections: tuple[str, ...] = ()
    field: str | None = None
    pattern: str | None = None

    @model_validator(mode="after")
    def validate_pattern(self) -> Self:
        if self.kind == "prose":
            if self.pattern is not None:
                raise ValueError("A prose rule cannot declare a pattern")
        else:
            if not self.pattern:
                raise ValueError("Pattern rules require a non-empty pattern")
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"Invalid rule pattern: {exc}") from exc
        return self


class ReportRuleSet(StrictModel):
    visibility: Literal["public"]
    rules: tuple[ReportRule, ...] = ()

    @model_validator(mode="after")
    def unique_rules(self) -> Self:
        ids = [rule.id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate report rule IDs")
        return self
