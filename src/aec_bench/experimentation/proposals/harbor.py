# ABOUTME: Builds the exact Harbor job for one governed proposal session.
# ABOUTME: Keeps proposal task and host validation outside the generic Harbor harness.

from __future__ import annotations

import hashlib
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.contracts.harness_instance import AgentBindingConfig
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.experimentation.proposals.morph.constants import (
    PROPOSAL_MORPH_BACKEND,
    PROPOSAL_MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH,
)
from aec_bench.experimentation.proposals.session_config import (
    ProposalSessionHostConfig,
    ProposalSessionHostConfigError,
    load_proposal_session_host_inputs,
)
from aec_bench.experimentation.proposals.task_packaging.contracts import (
    ProposalTaskPackageFile,
    ProposalTaskPackageManifest,
)
from aec_bench.harness.harbor_dispatch import (
    ENTRYPOINT_AGENT_IMPORT_PATH,
    HarborDispatchError,
    validate_harbor_job_config,
)
from aec_bench.tasks.loader import LoadError, canonical_task_key, load_task_definition


@dataclass(frozen=True)
class ProposalHarborDispatchInput:
    """Exact host and derived-task inputs for one proposal candidate session."""

    host_config: ProposalSessionHostConfig
    derived_task_path: Path
    derived_task: TaskDefinition
    derived_task_manifest: ProposalTaskPackageManifest
    repetitions: int = 1


def build_proposal_harbor_job_config(
    *,
    dispatch: ProposalHarborDispatchInput,
    jobs_dir: Path | str = "jobs",
) -> dict[str, Any]:
    """Build one validated proposal-only Harbor candidate job."""

    if type(dispatch.repetitions) is not int or dispatch.repetitions != 1:
        raise HarborDispatchError(
            "proposal Harbor dispatch requires exactly one repetition",
        )
    task_path = _exact_proposal_task_path(dispatch.derived_task_path)
    try:
        host_inputs = load_proposal_session_host_inputs(
            dispatch.host_config.model_dump(mode="json"),
            environment_dir=task_path / "environment",
        )
    except ProposalSessionHostConfigError as error:
        raise HarborDispatchError(
            f"proposal dispatch host inputs are invalid: {error}",
        ) from error
    if (
        host_inputs.config != dispatch.host_config
        or host_inputs.derived_task_manifest != dispatch.derived_task_manifest
    ):
        raise HarborDispatchError(
            "derived proposal task manifest differs from the exact host inputs",
        )
    _validate_exact_proposal_task_package(
        task_path=task_path,
        manifest=dispatch.derived_task_manifest,
    )
    _validate_exact_proposal_task(
        task_path=task_path,
        task=dispatch.derived_task,
        manifest=dispatch.derived_task_manifest,
        expected_task_id=host_inputs.bundle.task_snapshot.task_id,
    )
    agent_configurations = tuple(
        binding.configuration
        for binding in host_inputs.bundle.fixed_harness.bindings
        if isinstance(binding.configuration, AgentBindingConfig)
    )
    if len(agent_configurations) != 1:
        raise HarborDispatchError(
            "proposal fixed H0 requires exactly one agent binding",
        )
    fixed_agent = agent_configurations[0]
    host_payload = dispatch.host_config.model_dump(mode="json")
    runtime_binding = {
        "runtime_archive_path": dispatch.host_config.runtime_archive_path,
        "runtime_archive_sha256": dispatch.host_config.runtime_archive_sha256,
        "runtime_archive_content_sha256": dispatch.host_config.runtime_archive_content_sha256,
    }
    config: dict[str, Any] = {
        "job_name": f"proposal-{host_inputs.bundle.compilation.candidate_ref.candidate_id}",
        "jobs_dir": str(jobs_dir),
        "n_attempts": 1,
        "timeout_multiplier": 1.0,
        "metrics": [
            {"type": "mean"},
            {"type": "min"},
            {"type": "max"},
        ],
        "n_concurrent_trials": 1,
        "quiet": False,
        "environment": {
            "import_path": PROPOSAL_MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH,
            "force_build": False,
            "delete": True,
            "kwargs": {
                "compute_backend": PROPOSAL_MORPH_BACKEND,
                **runtime_binding,
            },
        },
        "agents": [
            {
                "name": fixed_agent.agent_name,
                "import_path": ENTRYPOINT_AGENT_IMPORT_PATH,
                "model_name": fixed_agent.model,
                "kwargs": {
                    "adapter": "proposal_session",
                    "extra_env": {},
                    "proposal_session": host_payload,
                },
            }
        ],
        "datasets": [],
        "tasks": [{"path": str(task_path)}],
        "artifacts": [
            {
                "source": "/workspace/proposal-session",
                "destination": "agent/proposal-session",
            },
            {
                "source": "/workspace/output.md",
                "destination": "agent/output.md",
            },
            {
                "source": "/workspace/agent_result.json",
                "destination": "agent/agent_result.json",
            },
        ],
    }
    try:
        validate_harbor_job_config(config)
    except ValueError as error:
        raise HarborDispatchError(
            f"proposal Harbor JobConfig is invalid: {error}",
        ) from error
    return config


def _exact_proposal_task_path(path: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise HarborDispatchError(
            "derived proposal task path must be absolute",
        )
    if candidate.is_symlink():
        raise HarborDispatchError(
            "derived proposal task path must not be a symbolic link",
        )
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise HarborDispatchError(
            "derived proposal task path must be an existing directory",
        ) from error
    if resolved != candidate or not resolved.is_dir():
        raise HarborDispatchError(
            "derived proposal task path must be an exact existing directory",
        )
    return resolved


def _validate_exact_proposal_task(
    *,
    task_path: Path,
    task: TaskDefinition,
    manifest: ProposalTaskPackageManifest,
    expected_task_id: str,
) -> None:
    if (
        task.task_id != expected_task_id
        or manifest.task_id != expected_task_id
        or task.visibility is not manifest.visibility
    ):
        raise HarborDispatchError(
            "derived proposal task identity does not match the compiled session",
        )
    try:
        task_root = next(
            (
                ancestor
                for ancestor in task_path.parents
                if str(canonical_task_key(task_path.relative_to(ancestor).as_posix())) == expected_task_id
            ),
            None,
        )
        if task_root is None:
            raise LoadError("derived proposal task path does not contain its canonical task identity")
        observed = load_task_definition(
            task_path,
            task_root,
        )
    except (LoadError, OSError, ValueError) as error:
        raise HarborDispatchError(
            f"derived proposal task cannot be loaded: {error}",
        ) from error
    observed_payload = observed.model_dump(
        mode="json",
        exclude={"domain", "task_id", "task_type"},
    )
    expected_payload = task.model_dump(
        mode="json",
        exclude={"domain", "task_id", "task_type"},
    )
    if observed_payload != expected_payload:
        raise HarborDispatchError(
            "derived proposal task bytes differ from the supplied task",
        )


def _validate_exact_proposal_task_package(
    *,
    task_path: Path,
    manifest: ProposalTaskPackageManifest,
) -> None:
    manifest_path = "proposal-task-package.json"
    expected = {item.path: item for item in manifest.files}
    observed: set[str] = set()
    for path in sorted(
        task_path.rglob("*"),
        key=lambda candidate: candidate.relative_to(task_path).as_posix(),
    ):
        relative = path.relative_to(task_path).as_posix()
        if _validate_exact_proposal_task_package_member(
            path=path,
            relative=relative,
            manifest_path=manifest_path,
            manifest_entry=expected.get(relative),
        ):
            observed.add(relative)
    if observed != set(expected):
        raise HarborDispatchError(
            "derived proposal task package does not match its exact manifest surface",
        )


def _validate_exact_proposal_task_package_member(
    *,
    path: Path,
    relative: str,
    manifest_path: str,
    manifest_entry: ProposalTaskPackageFile | None,
) -> bool:
    if path.is_symlink():
        raise HarborDispatchError(
            f"derived proposal task package contains a symbolic link: {relative}",
        )
    try:
        path_stat = path.stat(follow_symlinks=False)
    except OSError as error:
        raise HarborDispatchError(
            f"derived proposal task package member cannot be inspected: {relative}",
        ) from error
    if stat.S_ISDIR(path_stat.st_mode):
        return False
    if not stat.S_ISREG(path_stat.st_mode):
        raise HarborDispatchError(
            f"derived proposal task package member is not a regular file: {relative}",
        )
    if relative == manifest_path:
        return False
    if manifest_entry is None:
        raise HarborDispatchError(
            f"derived proposal task package contains an undeclared member: {relative}",
        )
    if path_stat.st_size != manifest_entry.byte_size:
        raise HarborDispatchError(
            f"derived proposal task package member identity mismatch: {relative}",
        )
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise HarborDispatchError(
            f"derived proposal task package member cannot be read: {relative}",
        ) from error
    if len(payload) != manifest_entry.byte_size or hashlib.sha256(payload).hexdigest() != manifest_entry.sha256:
        raise HarborDispatchError(
            f"derived proposal task package member identity mismatch: {relative}",
        )
    return True
