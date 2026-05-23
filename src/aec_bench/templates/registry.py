# ABOUTME: Registry for loading, discovering, and validating task generation templates.
# ABOUTME: Handles TOML parsing with field remapping, dynamic engine import, and directory scanning.

import importlib.util
import tomllib
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from aec_bench.templates.contracts import (
    ArchetypeRange,
    ArchetypeSpec,
    DifficultyPreset,
    OutputSpec,
    ParamSpec,
    TemplateConfig,
    TemplateMeta,
)

# Files that must be present in every template directory.
_REQUIRED_FILES = ("engine.py", "params.toml", "instruction.md")

# Known fields for DifficultyPreset — anything else becomes `extra`.
_DIFFICULTY_KNOWN_FIELDS = frozenset({"description", "visibility", "archetypes", "hidden_params", "replacement_text"})


def _remap_param_spec(raw: dict[str, Any]) -> dict[str, Any]:
    """Remap TOML param keys to ParamSpec model field names.

    TOML uses `min` and `max`; the model uses `min_value` and `max_value`.
    """
    remapped = dict(raw)
    if "min" in remapped:
        remapped["min_value"] = remapped.pop("min")
    if "max" in remapped:
        remapped["max_value"] = remapped.pop("max")
    return remapped


def _parse_archetype_spec(raw: dict[str, Any]) -> dict[str, Any]:
    """Restructure a raw TOML archetype entry into ArchetypeSpec-compatible dict.

    TOML encodes param ranges as direct keys with inline tables:
        cohesion_kpa = {min = 5, max = 15}

    These are collected into the `params` dict; description and site_contexts
    remain as top-level fields.
    """
    description = raw.get("description", "")
    site_contexts = raw.get("site_contexts", [])
    params: dict[str, ArchetypeRange] = {}

    for key, value in raw.items():
        if key in {"description", "site_contexts"}:
            continue
        if isinstance(value, dict) and "min" in value and "max" in value:
            params[key] = ArchetypeRange(min=value["min"], max=value["max"])

    return {
        "description": description,
        "site_contexts": site_contexts,
        "params": params,
    }


def _parse_difficulty_preset(raw: dict[str, Any]) -> dict[str, Any]:
    """Split a raw TOML difficulty entry into known fields and extras.

    Any key not in _DIFFICULTY_KNOWN_FIELDS goes into the `extra` dict.
    """
    known: dict[str, Any] = {}
    extra: dict[str, Any] = {}

    for key, value in raw.items():
        if key in _DIFFICULTY_KNOWN_FIELDS:
            known[key] = value
        else:
            extra[key] = value

    known["extra"] = extra
    return known


def load_engine_module(template_dir: Path) -> ModuleType:
    """Dynamically load engine.py from template_dir and verify it has a callable compute.

    Raises FileNotFoundError if engine.py is absent.
    Raises ValueError if the module lacks a callable compute attribute.
    """
    engine_path = template_dir / "engine.py"
    if not engine_path.exists():
        msg = f"engine.py not found in {template_dir}"
        raise FileNotFoundError(msg)

    spec = importlib.util.spec_from_file_location(f"_template_engine_{template_dir.name}", engine_path)
    if spec is None or spec.loader is None:
        msg = f"Cannot create module spec from {engine_path}"
        raise ValueError(msg)

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    if not hasattr(module, "compute") or not callable(module.compute):
        msg = f"engine.py in {template_dir} must define a callable 'compute' function"
        raise ValueError(msg)

    return module


def load_template(template_dir: Path) -> tuple[TemplateConfig, Path]:
    """Load a template from a directory, returning (TemplateConfig, template_dir).

    Checks for required files, parses params.toml with field remapping,
    and verifies engine.py has a callable compute function.

    Raises FileNotFoundError if any required file is missing.
    Raises ValueError if engine.py lacks a compute function or TOML is malformed.
    """
    for filename in _REQUIRED_FILES:
        fpath = template_dir / filename
        if not fpath.exists():
            msg = f"Required file '{filename}' not found in {template_dir}"
            raise FileNotFoundError(msg)

    with open(template_dir / "params.toml", "rb") as fh:
        raw_toml = tomllib.load(fh)

    meta = TemplateMeta.model_validate(raw_toml.get("meta", {}))

    params: dict[str, ParamSpec] = {}
    for name, raw_param in raw_toml.get("params", {}).items():
        params[name] = ParamSpec.model_validate(_remap_param_spec(raw_param))

    outputs: dict[str, OutputSpec] = {}
    for name, raw_output in raw_toml.get("outputs", {}).items():
        outputs[name] = OutputSpec.model_validate(raw_output)

    archetypes: dict[str, ArchetypeSpec] = {}
    for name, raw_arch in raw_toml.get("archetypes", {}).items():
        archetypes[name] = ArchetypeSpec.model_validate(_parse_archetype_spec(raw_arch))

    difficulty: dict[str, DifficultyPreset] = {}
    for name, raw_diff in raw_toml.get("difficulty", {}).items():
        difficulty[name] = DifficultyPreset.model_validate(_parse_difficulty_preset(raw_diff))

    # constraints can be either a flat list at top level: constraints = ["rule1", "rule2"]
    # or a section with rules key: [constraints] rules = ["rule1", "rule2"]
    raw_constraints = raw_toml.get("constraints", [])
    if isinstance(raw_constraints, dict):
        constraints: list[str] = raw_constraints.get("rules", [])
    else:
        constraints = raw_constraints

    config = TemplateConfig(
        meta=meta,
        params=params,
        outputs=outputs,
        archetypes=archetypes,
        difficulty=difficulty,
        constraints=constraints,
    )

    # Verify the engine module is loadable and has compute.
    load_engine_module(template_dir)

    return config, template_dir


def discover_templates(user_dirs: Sequence[Path] = ()) -> list[tuple[TemplateConfig, Path]]:
    """Scan built-in and user template directories for valid templates.

    Built-in templates live under the `builtin/` subdirectory of this package's
    templates directory. User directories are scanned similarly.

    A directory is considered a template candidate if it directly contains engine.py.
    Candidates that fail to load are silently skipped.

    Returns a list of (TemplateConfig, Path) tuples for all successfully loaded templates.
    """
    builtin_dir = Path(__file__).parent / "builtin"

    search_dirs: list[Path] = []
    if builtin_dir.exists():
        search_dirs.append(builtin_dir)
    search_dirs.extend(user_dirs)

    results: list[tuple[TemplateConfig, Path]] = []

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        # Recursively find all engine.py files; each parent directory is a candidate.
        for engine_path in sorted(search_dir.rglob("engine.py")):
            candidate = engine_path.parent
            try:
                config, path = load_template(candidate)
                results.append((config, path))
            except (FileNotFoundError, ValueError):
                # Skip templates that fail to load; errors surface via validate_template.
                pass
            except Exception:
                # Unexpected errors (syntax, import, permission) — log-worthy but not fatal
                import logging

                logging.getLogger(__name__).debug(
                    "Skipping template at %s due to unexpected error", candidate, exc_info=True
                )

    return results


def validate_template(template_dir: Path) -> list[str]:
    """Validate a template directory, returning a list of error strings.

    An empty list means the template is valid. Each string describes one problem.
    Checks required files, TOML structure, and engine.py compute callable.
    """
    errors: list[str] = []

    for filename in _REQUIRED_FILES:
        fpath = template_dir / filename
        if not fpath.exists():
            errors.append(f"Missing required file: {filename}")

    if errors:
        # Cannot proceed with further checks if core files are missing.
        return errors

    try:
        load_template(template_dir)
    except FileNotFoundError as exc:
        errors.append(f"Missing file: {exc}")
    except ValueError as exc:
        msg = str(exc)
        if "compute" in msg.lower():
            errors.append(f"engine.py missing callable compute: {exc}")
        else:
            errors.append(f"Template validation error: {exc}")
    except Exception as exc:
        errors.append(f"Unexpected error loading template: {exc}")

    return errors


def has_custom_verifier(template_dir: Path) -> bool:
    """Return True if the template directory contains a custom verify.py."""
    return (template_dir / "verify.py").exists()
