# ABOUTME: Tests EntrypointAgent's host-owned proposal-session setup boundary.
# ABOUTME: Proves it installs only pinned filtered runtime bytes and rejects config injection.

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aec_bench.contracts.harness_instance import AgentBindingConfig
from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.task_definition import Visibility
from aec_bench.harness.proposal_runtime_archive import (
    build_proposal_runtime_archive,
)
from aec_bench.harness.proposal_session_config import (
    ProposalSessionHostConfig,
)
from aec_bench.harness.proposal_task_package import (
    ProposalTaskPackageIdentity,
    build_proposal_task_package,
)
from aec_bench.meta_harness.program_proposal_compilation import (
    ProposalRunSessionBundle,
)
from agents.entrypoint_agent import (
    _LIBRARY_ARCHIVE_REMOTE_PATH,
    _PROPOSAL_RUNTIME_ARCHIVE_REMOTE_PATH,
    _PROPOSAL_SESSION_REMOTE_ROOT,
    EntrypointAgent,
)
from tests.harness.test_proposal_session import (
    _compiled_rlm_commit_bundle,
    _evaluation_coordinate,
    _RecordingProposalEnvironment,
    _sha,
)
from tests.harness.test_proposal_session_config import _host_fixture

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_ROOT = _PROJECT_ROOT / "src" / "aec_bench"


def test_proposal_setup_loads_exact_host_inputs_and_uploads_only_filtered_runtime(
    tmp_path: Path,
) -> None:
    config, expected_bundle, derived_task = _host_fixture(tmp_path)
    agent = EntrypointAgent(
        logs_dir=tmp_path / "logs",
        model_name=_proposal_model(expected_bundle),
        adapter="proposal_session",
        proposal_session=config.model_dump(mode="json"),
        extra_env={},
    )
    environment = _environment(derived_task / "environment")
    uploaded: list[tuple[bytes, str]] = []
    commands: list[str] = []

    async def capture_upload(local_path: str, remote_path: str) -> None:
        uploaded.append((Path(local_path).read_bytes(), remote_path))

    async def execute(command: str, **_kwargs: Any) -> MagicMock:
        commands.append(command)
        return _exec_result()

    environment.upload_file = AsyncMock(side_effect=capture_upload)
    environment.exec = AsyncMock(side_effect=execute)

    with patch(
        "agents.entrypoint_agent.inject_trajectory_writer",
        new_callable=AsyncMock,
    ) as inject:
        asyncio.run(agent.setup(environment))

    assert agent._proposal_inputs is not None
    assert agent._proposal_inputs.bundle == expected_bundle
    assert uploaded == [
        (
            Path(config.runtime_archive_path).read_bytes(),
            _PROPOSAL_RUNTIME_ARCHIVE_REMOTE_PATH,
        )
    ]
    assert not any(remote == _LIBRARY_ARCHIVE_REMOTE_PATH for _, remote in uploaded)
    assert any(config.runtime_archive_sha256 in command for command in commands)
    assert any("tarfile" in command and "/opt/aec_bench" in command for command in commands)
    inject.assert_not_awaited()


@pytest.mark.parametrize(
    ("extra_parameters", "message"),
    (
        ({"adapter": "direct"}, "adapter"),
        ({"client": {"client_kind": "replay", "payload": {}}}, "unsupported"),
        ({"tools": []}, "unsupported"),
        ({"system_prompt": "candidate supplied"}, "unsupported"),
        ({"extra_env": {"PRIVATE": "value"}}, "environment variables"),
    ),
)
def test_proposal_setup_rejects_injected_agent_configuration(
    tmp_path: Path,
    extra_parameters: dict[str, object],
    message: str,
) -> None:
    config, bundle, derived_task = _host_fixture(tmp_path)
    parameters: dict[str, object] = {
        "adapter": "proposal_session",
        "proposal_session": config.model_dump(mode="json"),
        "extra_env": {},
    }
    parameters.update(extra_parameters)
    agent = EntrypointAgent(
        logs_dir=tmp_path / "logs",
        model_name=_proposal_model(bundle),
        **parameters,
    )
    environment = _environment(derived_task / "environment")

    with pytest.raises(ValueError, match=message):
        asyncio.run(agent.setup(environment))

    environment.upload_file.assert_not_awaited()
    environment.exec.assert_not_awaited()


def test_proposal_setup_fails_closed_when_remote_archive_install_fails(
    tmp_path: Path,
) -> None:
    config, bundle, derived_task = _host_fixture(tmp_path)
    agent = EntrypointAgent(
        logs_dir=tmp_path / "logs",
        model_name=_proposal_model(bundle),
        adapter="proposal_session",
        proposal_session=config.model_dump(mode="json"),
        extra_env={},
    )
    environment = _environment(derived_task / "environment")
    environment.exec = AsyncMock(
        return_value=_exec_result(
            return_code=1,
            stderr="proposal runtime digest mismatch",
        )
    )

    with pytest.raises(RuntimeError, match="proposal runtime digest mismatch"):
        asyncio.run(agent.setup(environment))

    assert agent._proposal_inputs is None


def test_proposal_setup_rejects_missing_pinned_dependencies_without_mutable_install(
    tmp_path: Path,
) -> None:
    config, bundle, derived_task = _host_fixture(tmp_path)
    agent = EntrypointAgent(
        logs_dir=tmp_path / "logs",
        model_name=_proposal_model(bundle),
        adapter="proposal_session",
        proposal_session=config.model_dump(mode="json"),
        extra_env={},
    )
    environment = _environment(derived_task / "environment")
    commands: list[str] = []

    async def execute(command: str, **_kwargs: Any) -> MagicMock:
        commands.append(command)
        if "import pydantic_ai" in command:
            return _exec_result(
                return_code=1,
                stderr="runtime dependency mismatch",
            )
        return _exec_result()

    environment.exec = AsyncMock(side_effect=execute)

    with pytest.raises(
        RuntimeError,
        match="Pinned proposal runtime dependencies",
    ):
        asyncio.run(agent.setup(environment))

    assert not any("pip install" in command for command in commands)
    assert agent._proposal_inputs is None


def test_proposal_run_executes_host_owned_session_and_uploads_receipt_without_secrets(
    tmp_path: Path,
) -> None:
    config, bundle, derived_task = _host_fixture(tmp_path)
    agent = EntrypointAgent(
        logs_dir=tmp_path / "logs",
        model_name=_proposal_model(bundle),
        adapter="proposal_session",
        proposal_session=config.model_dump(mode="json"),
        extra_env={},
    )
    environment = _environment(derived_task / "environment")
    environment.session_id = "harbor-environment.1"
    environment.compute_backend = "morph"
    asyncio.run(agent.setup(environment))
    uploaded_session: dict[str, bytes] = {}

    async def capture_session(source_dir: str, target_dir: str) -> None:
        assert target_dir == _PROPOSAL_SESSION_REMOTE_ROOT
        source = Path(source_dir)
        uploaded_session.update(
            {
                path.relative_to(source).as_posix(): path.read_bytes()
                for path in sorted(source.rglob("*"))
                if path.is_file()
            }
        )

    environment.upload_dir = AsyncMock(side_effect=capture_session)
    provider_environment = {
        "AWS_BEARER_TOKEN_BEDROCK": "ephemeral-secret",
        "AWS_REGION": "ap-southeast-2",
    }
    receipt_payload = {
        "schema_version": "aecbench.proposal-session-receipt.v1",
        "session_id": "proposal-session.harbor-environment.1",
        "status": "completed",
        "trial_record_permitted": True,
    }
    receipt = SimpleNamespace(
        session_id=receipt_payload["session_id"],
        status=SimpleNamespace(value="completed"),
        trial_record_permitted=True,
        failure_code=None,
        content_sha256=hashlib.sha256(b"proposal-session-receipt").hexdigest(),
        node_receipts=(
            SimpleNamespace(
                resources=SimpleNamespace(tokens_in=11, tokens_out=7),
            ),
            SimpleNamespace(
                resources=SimpleNamespace(tokens_in=13, tokens_out=5),
            ),
        ),
        model_dump=lambda **_kwargs: {
            **receipt_payload,
            "content_sha256": hashlib.sha256(b"proposal-session-receipt").hexdigest(),
        },
    )
    captured: dict[str, object] = {}

    async def execute_session(**kwargs: object) -> object:
        captured.update(kwargs)
        return receipt

    context = SimpleNamespace(
        n_input_tokens=0,
        n_output_tokens=0,
        metadata={},
    )
    with (
        patch(
            "agents.entrypoint_agent._provider_environment",
            return_value=provider_environment,
        ),
        patch(
            "agents.entrypoint_agent.run_proposal_session",
            new=AsyncMock(side_effect=execute_session),
        ),
        patch(
            "agents.entrypoint_agent.validate_runtime_limit_contract",
            side_effect=AssertionError("generic runtime validation must not handle proposal sessions"),
        ),
    ):
        asyncio.run(
            agent.run(
                instruction="Untrusted derived-task instruction.",
                environment=environment,
                context=context,
            )
        )

    execution = captured["execution"]
    assert captured["bundle"] == bundle
    assert captured["source_task_root"] == Path(config.source_task_dir)
    assert captured["environment"] is environment
    assert captured["child_environment"] == provider_environment
    assert execution.session_id == "proposal-session.harbor-environment.1"
    assert execution.environment_session_id == "harbor-environment.1"
    assert execution.backend == "morph"
    assert execution.runtime_archive_sha256 == config.runtime_archive_sha256
    assert uploaded_session["session-receipt.json"].endswith(b"\n")
    assert json.loads(uploaded_session["session-receipt.json"]) == receipt.model_dump(mode="json")
    assert b"ephemeral-secret" not in b"".join(uploaded_session.values())
    assert context.n_input_tokens == 24
    assert context.n_output_tokens == 12
    assert context.metadata == {
        "adapter_name": "proposal_session",
        "resolved_model": _proposal_model(bundle),
        "model": _proposal_model(bundle),
        "proposal_session_id": "proposal-session.harbor-environment.1",
        "proposal_session_receipt_sha256": receipt.content_sha256,
        "proposal_session_status": "completed",
        "trial_record_permitted": True,
        "failure_code": None,
        "candidate_id": bundle.compilation.candidate_ref.candidate_id,
        "proposal_graph_sha256": bundle.compilation.proposal_graph.content_sha256,
        "compilation_sha256": bundle.compilation.content_sha256,
        "session_plan_sha256": bundle.session_plan.content_sha256,
        "reward_owner": "harbor_verifier",
    }


def test_proposal_run_requires_completed_setup(tmp_path: Path) -> None:
    config, bundle, derived_task = _host_fixture(tmp_path)
    agent = EntrypointAgent(
        logs_dir=tmp_path / "logs",
        model_name=_proposal_model(bundle),
        adapter="proposal_session",
        proposal_session=config.model_dump(mode="json"),
        extra_env={},
    )
    environment = _environment(derived_task / "environment")
    environment.session_id = "harbor-environment.1"
    environment.compute_backend = "morph"

    with pytest.raises(RuntimeError, match="setup has not completed"):
        asyncio.run(
            agent.run(
                instruction="Ignored.",
                environment=environment,
                context=SimpleNamespace(),
            )
        )


def test_proposal_entrypoint_runs_complete_local_isolation_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, bundle, derived_task = _rlm_host_fixture(tmp_path)
    environment = _EntrypointProposalEnvironment(
        environment_dir=derived_task / "environment",
        root=tmp_path / "environment-runtime",
        bundle=bundle,
        runtime_archive_sha256=config.runtime_archive_sha256,
    )
    agent = EntrypointAgent(
        logs_dir=tmp_path / "logs",
        model_name=_proposal_model(bundle),
        adapter="proposal_session",
        proposal_session=config.model_dump(mode="json"),
        extra_env={},
    )
    context = SimpleNamespace(
        n_input_tokens=0,
        n_output_tokens=0,
        metadata={},
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "local-isolation-secret")

    asyncio.run(agent.setup(environment))
    asyncio.run(
        agent.run(
            instruction="This derived instruction must not define the proposal graph.",
            environment=environment,
            context=context,
        )
    )

    receipt = json.loads(
        environment.proposal_session_files["session-receipt.json"],
    )
    assert receipt["status"] == "completed"
    assert receipt["trial_record_permitted"] is True
    assert receipt["planned_node_ids"] == list(
        bundle.session_plan.planned_node_ids,
    )
    assert environment.reset_node_ids == list(
        bundle.session_plan.topological_order,
    )
    assert environment.output_by_node["finalize"] == environment.remote_files["/workspace/output.md"]
    assert context.n_input_tokens == 30
    assert context.n_output_tokens == 30
    assert context.metadata["proposal_session_receipt_sha256"] == receipt["content_sha256"]
    persisted = b"".join(environment.proposal_session_files.values())
    assert b"local-isolation-secret" not in persisted
    assert str(Path(config.source_task_dir)).encode() not in b"".join(
        content
        for target, content in environment.uploaded_files
        if target == "/workspace/proposal-execution-bundle.json"
    )


def _environment(environment_dir: Path) -> AsyncMock:
    environment = AsyncMock()
    environment.environment_dir = environment_dir
    environment.exec = AsyncMock(return_value=_exec_result())
    environment.upload_file = AsyncMock()
    environment.upload_dir = AsyncMock()
    environment.download_file = AsyncMock()
    return environment


def _exec_result(
    *,
    return_code: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> MagicMock:
    result = MagicMock()
    result.return_code = return_code
    result.stdout = stdout
    result.stderr = stderr
    return result


def _proposal_model(bundle: ProposalRunSessionBundle) -> str:
    configurations = tuple(
        binding.configuration
        for binding in bundle.fixed_harness.bindings
        if isinstance(binding.configuration, AgentBindingConfig)
    )
    assert len(configurations) == 1
    return configurations[0].model


def _rlm_host_fixture(
    tmp_path: Path,
) -> tuple[ProposalSessionHostConfig, ProposalRunSessionBundle, Path]:
    bundle, source_task_dir = _compiled_rlm_commit_bundle(
        tmp_path / "governed",
    )
    bundle_path = tmp_path / "proposal-session-bundle.json"
    bundle_path.write_text(
        bundle.model_dump_json(),
        encoding="utf-8",
    )
    runtime_archive = build_proposal_runtime_archive(
        package_root=_PACKAGE_ROOT,
        archive_path=tmp_path / "proposal-runtime.tar.gz",
    )
    output_contract = OutputCompletionContract.model_validate_json(
        (source_task_dir / "environment" / "output_contract.json").read_bytes(),
    )
    derived = build_proposal_task_package(
        source_task_dir=source_task_dir,
        destination_task_dir=tmp_path / "derived-task",
        identity=ProposalTaskPackageIdentity(
            task_id=bundle.task_snapshot.task_id,
            task_revision=bundle.task_snapshot.definition_sha256,
            source_task_package_sha256=bundle.task_snapshot.package_sha256,
            problem_view_sha256=(bundle.compilation.proposal_freeze.problem_view.content_sha256),
            output_contract_sha256=(bundle.compilation.proposal_graph.finalizer.output_completion_contract_sha256),
            visibility=Visibility.PUBLIC,
        ),
        output_contract=output_contract,
        verifier_asset_paths=("tests/test.sh",),
    )
    bundle_bytes = bundle_path.read_bytes()
    return (
        ProposalSessionHostConfig(
            bundle_path=str(bundle_path.resolve()),
            bundle_file_sha256=hashlib.sha256(bundle_bytes).hexdigest(),
            bundle_content_sha256=bundle.content_sha256,
            source_task_dir=str(source_task_dir.resolve()),
            source_task_package_sha256=bundle.task_snapshot.package_sha256,
            runtime_archive_path=str(runtime_archive.path.resolve()),
            runtime_archive_sha256=runtime_archive.archive_sha256,
            runtime_archive_content_sha256=runtime_archive.content_sha256,
            evaluation_coordinate=_evaluation_coordinate(bundle),
            execution_schedule_sha256=_sha("execution-schedule"),
            execution_assignment_sha256=_sha("execution-assignment"),
        ),
        bundle,
        derived.path,
    )


class _EntrypointProposalEnvironment(_RecordingProposalEnvironment):
    def __init__(
        self,
        *,
        environment_dir: Path,
        root: Path,
        bundle: ProposalRunSessionBundle,
        runtime_archive_sha256: str,
    ) -> None:
        super().__init__(
            root=root,
            bundle=bundle,
            runtime_archive_sha256=runtime_archive_sha256,
        )
        self.environment_dir = environment_dir
        self.session_id = "local-isolation.1"
        self.compute_backend = "morph"
        self.proposal_session_files: dict[str, bytes] = {}

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        if command.startswith(
            "python -m aec_bench.harness.provider_broker_bootstrap",
        ):
            return await super().exec(
                command,
                cwd=cwd,
                env=env,
                timeout_sec=timeout_sec,
            )
        return _exec_result(return_code=0)

    async def upload_dir(
        self,
        source_dir: Path | str,
        target_dir: str,
    ) -> None:
        if target_dir != _PROPOSAL_SESSION_REMOTE_ROOT:
            await super().upload_dir(source_dir, target_dir)
            return
        source = Path(source_dir)
        self.proposal_session_files = {
            path.relative_to(source).as_posix(): path.read_bytes()
            for path in sorted(source.rglob("*"))
            if path.is_file()
        }
        self.remote_files.update(
            {f"{target_dir}/{relative}": content for relative, content in self.proposal_session_files.items()}
        )
