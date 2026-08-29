# ABOUTME: Filesystem loader for validated task definitions in aec-bench Python.
# ABOUTME: Reads real task instances from disk and normalizes mixed repo path layouts.

import logging
import re
import tomllib
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, Final, cast

from pydantic import ValidationError

from aec_bench.contracts.identity import EntityKey
from aec_bench.contracts.task_definition import (
    Difficulty,
    EnvironmentSpec,
    Lifecycle,
    TaskDefinition,
    TaskMetadata,
    ToolSpec,
    VerifierSpec,
    Visibility,
)

logger = logging.getLogger(__name__)


class LoadError(Exception):
    pass


# "architectural" and "plumbing" are unverified/tracked-debt — no known task instances use them.
KNOWN_DOMAINS = {
    "civil",
    "electrical",
    "ground",
    "maritime",
    "mechanical",
    "structural",
    "architectural",
    "plumbing",
}
WORKSPACE_OUTPUT_PATH_RE: Final[str] = r"/workspace/[A-Za-z0-9._/-]+"
_TASK_KEY_COMPONENT_RE: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9_-]+")


def derive_task_id(instance_dir: Path, tasks_root: Path) -> str:
    return instance_dir.relative_to(tasks_root).as_posix()


def canonical_task_key(relative_path: str) -> EntityKey:
    """Map an existing task path to the lowercase identity-key form."""

    components: list[str] = []
    for component in relative_path.split("/"):
        normalised = _TASK_KEY_COMPONENT_RE.sub("-", component.lower()).strip("-_")
        if not normalised or not normalised[0].isalnum() or not normalised[0].isascii():
            normalised = f"task-{normalised}" if normalised else "task"
        components.append(normalised)
    return EntityKey("/".join(components))


def load_task_definition(instance_dir: Path, tasks_root: Path) -> TaskDefinition:
    """Load a task, dispatching old files to the bounded compatibility reader."""

    raw_toml, instruction = _read_task_files(instance_dir)
    if "identity" in raw_toml:
        return _load_task_definition_with_metadata(instance_dir, tasks_root, raw_toml, instruction)
    return _load_legacy_task_definition(instance_dir, tasks_root, raw_toml, instruction)


def load_legacy_task_definition(
    instance_dir: Path,
    tasks_root: Path,
) -> TaskDefinition:
    """Load a pre-identity task using the temporary legacy metadata defaults."""

    raw_toml, instruction = _read_task_files(instance_dir)
    if "identity" in raw_toml:
        raise LoadError(
            "legacy task reader cannot load a task with [identity]; use load_task_definition for strict metadata"
        )
    return _load_legacy_task_definition(instance_dir, tasks_root, raw_toml, instruction)


def _load_task_definition_with_metadata(
    instance_dir: Path,
    tasks_root: Path,
    raw_toml: dict[str, Any],
    instruction: str,
) -> TaskDefinition:
    try:
        task_metadata = parse_task_metadata(raw_toml)
    except ValueError as error:
        raise LoadError(f"invalid task metadata in {instance_dir / 'task.toml'}: {error}") from error

    relative_path = derive_task_id(instance_dir, tasks_root)
    try:
        path_key = canonical_task_key(relative_path)
    except (TypeError, ValueError) as error:
        raise LoadError(f"task path is not a valid entity key: {relative_path}") from error
    if task_metadata.identity.key != path_key and path_key not in task_metadata.identity.aliases:
        raise LoadError(
            f"task identity key {task_metadata.identity.key!r} does not match task path {relative_path!r} "
            "or an explicit identity alias"
        )

    metadata = _metadata_mapping(raw_toml)
    agent = _agent_mapping(raw_toml)
    try:
        return TaskDefinition.model_validate(
            {
                "identity": task_metadata.identity,
                "task_id": str(task_metadata.identity.key),
                "task_type": _infer_task_type(relative_path.split("/")),
                "domain": _infer_domain(relative_path.split("/"), metadata),
                "category": _infer_category(relative_path.split("/"), metadata),
                "difficulty": metadata.get("difficulty", Difficulty.MEDIUM),
                "lifecycle": task_metadata.lifecycle,
                "visibility": task_metadata.visibility,
                "instruction": instruction,
                "environment": _build_environment(instance_dir, raw_toml),
                "verifier": _build_verifier(instance_dir, instruction),
                "timeout_seconds": max(1, round(float(agent.get("timeout_sec", 600.0)))),
                "tags": list(metadata.get("tags", [])),
                "metadata": metadata,
            }
        )
    except (ValidationError, KeyError, TypeError, ValueError) as error:
        raise LoadError(f"invalid task definition in {instance_dir / 'task.toml'}: {error}") from error


def parse_task_metadata(raw_toml: Mapping[str, Any]) -> TaskMetadata:
    """Parse the explicit ``[identity]`` and ``[metadata]`` task contract."""

    identity = raw_toml.get("identity")
    if not isinstance(identity, Mapping):
        raise ValueError("[identity] must declare id, key, and version")
    metadata = raw_toml.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("[metadata] must declare lifecycle and visibility")
    if "lifecycle" not in metadata:
        raise ValueError("[metadata].lifecycle is required")
    if "visibility" not in metadata:
        raise ValueError("[metadata].visibility is required; it has no default")
    return TaskMetadata.model_validate(
        {
            "identity": dict(identity),
            "lifecycle": metadata["lifecycle"],
            "visibility": metadata["visibility"],
        }
    )


def _read_task_files(instance_dir: Path) -> tuple[dict[str, Any], str]:
    task_toml_path = instance_dir / "task.toml"
    instruction_path = instance_dir / "instruction.md"

    try:
        raw_toml = tomllib.loads(task_toml_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise LoadError(f"missing task.toml: {task_toml_path}") from None
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise LoadError(f"invalid task.toml: {task_toml_path}: {error}") from error
    try:
        instruction = instruction_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise LoadError(f"missing instruction.md: {instruction_path}") from None
    except UnicodeDecodeError as error:
        raise LoadError(f"invalid instruction.md: {instruction_path}: {error}") from error
    return raw_toml, instruction


def _load_legacy_task_definition(
    instance_dir: Path,
    tasks_root: Path,
    raw_toml: dict[str, Any],
    instruction: str,
) -> TaskDefinition:
    task_id = derive_task_id(instance_dir, tasks_root)
    segments = task_id.split("/")
    metadata = _metadata_mapping(raw_toml)
    agent = _agent_mapping(raw_toml)

    task_def = TaskDefinition.model_validate(
        {
            "task_id": task_id,
            "task_type": _infer_task_type(segments),
            "domain": _infer_domain(segments, metadata),
            "category": _infer_category(segments, metadata),
            "difficulty": metadata.get("difficulty", Difficulty.MEDIUM),
            "lifecycle": Lifecycle.PROPOSED,
            "visibility": metadata.get("visibility", Visibility.PUBLIC),
            "instruction": instruction,
            "environment": EnvironmentSpec(
                dockerfile="environment/Dockerfile",
                compose_file=_optional_relative_file(
                    instance_dir,
                    "environment/docker-compose.yaml",
                ),
                manifest=_optional_relative_file(instance_dir, "environment/manifest.jsonl"),
                build_args={},
                tools=_load_tools(raw_toml),
            ),
            "verifier": VerifierSpec(
                script=_verifier_script(instance_dir),
                expected_output_path=_infer_expected_output_path(instruction),
                reward_path="/logs/verifier/reward.json",
                details_path="/logs/verifier/details.json",
            ),
            "timeout_seconds": max(1, round(float(agent.get("timeout_sec", 600.0)))),
            "tags": list(metadata.get("tags", [])),
            "metadata": metadata,
        }
    )

    # Warn about Dockerfile/extension mismatches
    for warning in _check_dockerfile_status(instance_dir, raw_toml):
        logger.warning(warning)

    return task_def


def _metadata_mapping(raw_toml: Mapping[str, Any]) -> dict[str, Any]:
    value = raw_toml.get("metadata", {})
    if not isinstance(value, Mapping):
        raise LoadError("task metadata must be a TOML table")
    return dict(value)


def _agent_mapping(raw_toml: Mapping[str, Any]) -> dict[str, Any]:
    value = raw_toml.get("agent", {})
    if not isinstance(value, Mapping):
        raise LoadError("task agent configuration must be a TOML table")
    return dict(value)


def _build_environment(instance_dir: Path, raw_toml: Mapping[str, Any]) -> EnvironmentSpec:
    return EnvironmentSpec(
        dockerfile="environment/Dockerfile",
        compose_file=_optional_relative_file(instance_dir, "environment/docker-compose.yaml"),
        manifest=_optional_relative_file(instance_dir, "environment/manifest.jsonl"),
        build_args={},
        tools=_load_tools(dict(raw_toml)),
    )


def _build_verifier(instance_dir: Path, instruction: str) -> VerifierSpec:
    return VerifierSpec(
        script=_verifier_script(instance_dir),
        expected_output_path=_infer_expected_output_path(instruction),
        reward_path="/logs/verifier/reward.json",
        details_path="/logs/verifier/details.json",
    )


def iter_task_instance_dirs(tasks_root: Path) -> list[Path]:
    return sorted(
        task_toml.parent
        for task_toml in tasks_root.rglob("task.toml")
        if (task_toml.parent / "instruction.md").exists()
    )


def load_task_catalog(tasks_root: Path) -> dict[str, TaskDefinition]:
    return {
        task.task_id: task
        for task in (
            load_task_definition(instance_dir, tasks_root) for instance_dir in iter_task_instance_dirs(tasks_root)
        )
    }


def _infer_task_type(segments: list[str]) -> str:
    if len(segments) < 2:
        raise LoadError("task path must contain at least two segments")
    return segments[1]


def _infer_domain(segments: list[str], metadata: dict[str, Any]) -> str:
    first_segment = segments[0]
    if first_segment in KNOWN_DOMAINS:
        return first_segment

    metadata_domain = metadata.get("domain")
    if isinstance(metadata_domain, str) and metadata_domain:
        return metadata_domain

    for tag in metadata.get("tags", []):
        if isinstance(tag, str) and tag in KNOWN_DOMAINS:
            return tag

    return first_segment


def _infer_category(segments: list[str], metadata: dict[str, Any]) -> str:
    first_segment = segments[0]
    return str(metadata.get("category", first_segment))


def _optional_relative_file(instance_dir: Path, relative_path: str) -> str | None:
    if (instance_dir / relative_path).exists():
        return relative_path
    return None


def _verifier_script(instance_dir: Path) -> str:
    """Resolve the verifier entry-point script.

    Harbor requires tests/test.sh as the container entry point. If only
    verify.py exists, the task will fail at runtime because Harbor runs
    ``/tests/test.sh`` unconditionally.
    """
    tests_dir = instance_dir / "tests"
    has_test_sh = (tests_dir / "test.sh").exists()
    has_verify_py = (tests_dir / "verify.py").exists()

    if not has_test_sh and not has_verify_py:
        raise LoadError(f"missing verifier script for task instance: {instance_dir}")

    if has_verify_py and not has_test_sh:
        logger.warning(
            "task %s has tests/verify.py but no tests/test.sh — "
            "Harbor requires test.sh as the entry point. "
            "Add a test.sh wrapper that calls verify.py.",
            instance_dir.name,
        )

    # Warn if ground_truth.json is at task root instead of tests/
    gt_at_root = (instance_dir / "ground_truth.json").exists()
    gt_in_tests = (tests_dir / "ground_truth.json").exists()
    if gt_at_root and not gt_in_tests:
        logger.warning(
            "task %s has ground_truth.json at task root but not in tests/ — "
            "Harbor only uploads tests/ to the container. Move it to tests/.",
            instance_dir.name,
        )

    if has_test_sh:
        return "tests/test.sh"
    return "tests/verify.py"


def _load_tools(raw_toml: dict[str, Any]) -> list[ToolSpec]:
    """Read tool definitions from parsed TOML.

    Supports two formats:
    - New: [[environment.tools]] array-of-tables with name, source, description, returns_image
    - Legacy: [tools].scripts flat list of script paths (auto-generates name/description)

    New format takes priority when both are present.
    """
    # New format: [[environment.tools]]
    env_tools = raw_toml.get("environment", {}).get("tools", [])
    if env_tools:
        return [
            ToolSpec(
                name=t["name"],
                source=t["source"],
                description=t.get("description", f"Tool: {t['name']}"),
                returns_image=t.get("returns_image", False),
            )
            for t in env_tools
        ]

    # Legacy format: [tools].scripts
    tools_section = raw_toml.get("tools", {})
    scripts: list[str] = tools_section.get("scripts", [])

    tool_specs: list[ToolSpec] = []
    for script in scripts:
        stem = PurePosixPath(script).stem
        tool_name = stem.replace("_", "-") if "_" in stem else stem
        tool_specs.append(
            ToolSpec(
                name=tool_name,
                source=script,
                description=f"Calculator tool: {stem.replace('_', ' ')}",
            )
        )
    return tool_specs


def _check_dockerfile_status(instance_dir: Path, raw_toml: dict[str, Any]) -> list[str]:
    """Check if task's Dockerfile matches its declared extensions.

    Returns a list of warning messages (empty if everything is fine).
    """
    warnings: list[str] = []
    extensions = raw_toml.get("environment", {}).get("extensions", [])
    dockerfile = instance_dir / "environment" / "Dockerfile"

    if extensions and not dockerfile.exists():
        warnings.append(
            f"Task declares extensions {extensions} but has no "
            f"environment/Dockerfile. Run: aec-bench generate dockerfiles"
        )
    elif extensions and dockerfile.exists():
        content = dockerfile.read_text(encoding="utf-8")
        if "Auto-generated" not in content:
            warnings.append(
                f"Task declares extensions {extensions} but Dockerfile appears "
                f"to be custom (not auto-generated). Run: aec-bench generate dockerfiles"
            )

    return warnings


def extract_workspace_output_paths(instruction: str) -> list[str]:
    """Extract workspace output paths from instruction text, stripping trailing punctuation."""
    return [path.rstrip(".,:;") for path in cast(list[str], re.findall(WORKSPACE_OUTPUT_PATH_RE, instruction))]


def _infer_expected_output_path(instruction: str) -> str:
    output_paths = extract_workspace_output_paths(instruction)
    if output_paths:
        return output_paths[-1]
    return "/workspace/output.jsonl"
