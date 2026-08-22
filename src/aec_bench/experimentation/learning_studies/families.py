# ABOUTME: Loads and resolves optional TOML learning-family overlays.
# ABOUTME: Converts authored members to exact task inputs without task execution or a global catalogue.

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import ValidationError

from aec_bench.contracts.learning_family import LearningFamilySpec


def load_learning_family(path: Path) -> LearningFamilySpec:
    """Parse one caller-selected family file with strict TOML validation."""

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return LearningFamilySpec.model_validate(data)
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as error:
        raise ValueError(f"could not load learning family {path}: {error}") from error


__all__ = ("load_learning_family",)
