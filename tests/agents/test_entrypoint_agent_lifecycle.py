# ABOUTME: Tests EntrypointAgent's explicit host-owned lifecycle bridge mode.
# ABOUTME: Proves provenance is validated without uploading runtime or hidden task authority.

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn

import pytest

from aec_bench.harness.harbor_task_export import (
    HARBOR_LIFECYCLE_BRIDGE_MODE,
    ExportedHarborTask,
    export_compiled_lifecycle_harbor_task,
)
from aec_bench.task_world_templates.compiled_world import compile_lifecycle
from agents.entrypoint_agent import EntrypointAgent

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"


class _NoSandboxAccessEnvironment:
    def __init__(self, environment_dir: Path) -> None:
        self.environment_dir = environment_dir

    async def exec(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("lifecycle setup must not execute inside the agent sandbox")

    async def upload_dir(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("lifecycle setup must not upload source or hidden task material")

    async def upload_file(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("lifecycle setup must not upload source or hidden task material")


class _CaptureLifecycleEnvironment(_NoSandboxAccessEnvironment):
    def __init__(self, environment_dir: Path, capture_dir: Path) -> None:
        super().__init__(environment_dir)
        self.capture_dir = capture_dir

    async def upload_dir(self, source_dir: str, target_dir: str) -> None:
        assert target_dir == "/workspace/lifecycle-run"
        shutil.copytree(source_dir, self.capture_dir)


class _FailingLifecycleAdapterBuilder:
    def __init__(self, message: str) -> None:
        self.message = message

    def build(self, **_kwargs: Any) -> _FailingLifecycleAdapter:
        return _FailingLifecycleAdapter(self.message)


class _FailingLifecycleAdapter:
    def __init__(self, message: str) -> None:
        self.message = message

    def execute(self, _request: Any) -> NoReturn:
        raise RuntimeError(self.message)


class _FailingLifecycleEntrypointAgent(EntrypointAgent):
    def __init__(self, *args: Any, failure_message: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.failure_message = failure_message

    def _lifecycle_adapter_builder(self) -> Any:
        return _FailingLifecycleAdapterBuilder(self.failure_message).build


def _export_task(tmp_path: Path) -> ExportedHarborTask:
    compiled = compile_lifecycle(
        TEMPLATE_ID,
        tmp_path / "compiled",
        variant_id="administrative_no_op",
    )
    return export_compiled_lifecycle_harbor_task(
        compiled,
        tmp_path / "tasks" / "civil" / "ssc03",
        project_root=REPO_ROOT,
    )


def test_lifecycle_setup_validates_task_without_touching_sandbox(tmp_path: Path) -> None:
    exported = _export_task(tmp_path)
    environment = _NoSandboxAccessEnvironment(exported.task_dir / "environment")
    agent = EntrypointAgent(
        logs_dir=tmp_path / "logs",
        model_name="claude-sonnet-4-20250514",
        lifecycle_bridge=HARBOR_LIFECYCLE_BRIDGE_MODE,
        adapter="tool_loop",
        max_turns=60,
    )

    asyncio.run(agent.setup(environment))


def test_lifecycle_setup_rejects_provenance_drift_before_sandbox_or_model_access(tmp_path: Path) -> None:
    exported = _export_task(tmp_path)
    context = exported.task_dir / "environment" / "context" / "initial" / "instruction.md"
    context.write_text("tampered\n", encoding="utf-8")
    environment = _NoSandboxAccessEnvironment(exported.task_dir / "environment")
    agent = EntrypointAgent(
        logs_dir=tmp_path / "logs",
        model_name="claude-sonnet-4-20250514",
        lifecycle_bridge=HARBOR_LIFECYCLE_BRIDGE_MODE,
        adapter="tool_loop",
    )

    with pytest.raises(ValueError, match="initial context does not match"):
        asyncio.run(agent.setup(environment))


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ({"client": {"client_kind": "replay", "payload": {}}}, "does not accept serialized clients"),
        ({"tools": []}, "owns its exact tool allowlist"),
        ({"system_prompt": "override"}, "owns its system prompt"),
        ({"adapter": "rlm"}, "requires a native tool-loop adapter"),
    ],
)
def test_lifecycle_setup_rejects_configuration_that_can_bypass_bridge(
    tmp_path: Path,
    extra: dict[str, Any],
    message: str,
) -> None:
    exported = _export_task(tmp_path)
    params: dict[str, Any] = {
        "lifecycle_bridge": HARBOR_LIFECYCLE_BRIDGE_MODE,
        "adapter": "tool_loop",
    }
    params.update(extra)
    agent = EntrypointAgent(
        logs_dir=tmp_path / "logs",
        model_name="public-tool-reference",
        **params,
    )

    with pytest.raises(ValueError, match=message):
        asyncio.run(agent.setup(_NoSandboxAccessEnvironment(exported.task_dir / "environment")))


def test_lifecycle_failure_redacts_provider_secret_from_metadata_and_uploaded_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = 'lifecycle-provider-"secret"\nmarker'
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    exported = _export_task(tmp_path)
    environment = _CaptureLifecycleEnvironment(
        exported.task_dir / "environment",
        tmp_path / "captured-lifecycle-run",
    )
    agent = _FailingLifecycleEntrypointAgent(
        logs_dir=tmp_path / "logs",
        model_name="claude-sonnet-4-20250514",
        lifecycle_bridge=HARBOR_LIFECYCLE_BRIDGE_MODE,
        adapter="tool_loop",
        failure_message=f"provider failed with {secret}",
    )
    context = SimpleNamespace(n_input_tokens=0, n_output_tokens=0, metadata={})

    asyncio.run(agent.setup(environment))
    asyncio.run(agent.run("Run the lifecycle", environment, context))

    metadata = json.dumps(context.metadata, sort_keys=True)
    assert secret not in metadata
    assert "<redacted>" in metadata
    uploaded_files = [path for path in environment.capture_dir.rglob("*") if path.is_file()]
    assert uploaded_files
    uploaded_payload = b"\n".join(path.read_bytes() for path in uploaded_files)
    assert secret.encode() not in uploaded_payload
    assert b"<redacted>" in uploaded_payload
    for path in uploaded_files:
        if path.suffix != ".json":
            continue
        parsed = json.loads(path.read_text(encoding="utf-8"))
        assert all(secret not in value for value in _nested_strings(parsed))


def _nested_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [nested for key, item in value.items() for nested in [*_nested_strings(key), *_nested_strings(item)]]
    if isinstance(value, list):
        return [nested for item in value for nested in _nested_strings(item)]
    return []
