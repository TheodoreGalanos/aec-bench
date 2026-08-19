# ABOUTME: Tests EntrypointAgent's production ready-set pool selection and publication.
# ABOUTME: Proves no shared fallback and verifies output returns before Harbor verification.

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from aec_bench.experimentation.proposals.session_config import (
    LoadedProposalSessionHostInputs,
    load_proposal_session_host_inputs,
)
from aec_bench.experimentation.proposals.task_package import source_task_package_sha256
from agents.entrypoint_agent import EntrypointAgent
from tests.experimentation.proposals.test_entrypoint_agent import (
    _proposal_model,
    _rlm_host_fixture,
)
from tests.experimentation.proposals.test_ready_set_session import (
    _ready_set_bundle,
    _RecordingProposalEnvironmentPool,
)
from tests.experimentation.proposals.test_session import _evaluation_coordinate


def test_entrypoint_ready_set_uses_exact_pool_and_republishes_verified_output(
    tmp_path: Path,
) -> None:
    inputs = _ready_set_inputs(tmp_path)
    environment = _ReadySetOuterEnvironment(
        environment_dir=tmp_path / "outer-environment",
        bundle=inputs.bundle,
        runtime_archive_sha256=inputs.runtime_archive.archive_sha256,
        pool_root=tmp_path / "pool",
    )
    agent = _agent(inputs)
    context = SimpleNamespace(n_input_tokens=0, n_output_tokens=0, metadata={})

    with patch(
        "agents.entrypoint_agent._provider_environment",
        return_value={},
    ):
        asyncio.run(
            agent.run(
                instruction="Untrusted derived instruction.",
                environment=environment,
                context=context,
            )
        )

    assert environment.pool_factory_call is not None
    assert environment.pool_factory_call["capacity"] == 2
    assert environment.pool_factory_call["expected_runtime_archive_sha256"] == inputs.runtime_archive.archive_sha256
    assert (
        environment.pool_factory_call["expected_runtime_archive_content_sha256"]
        == inputs.runtime_archive.content_sha256
    )
    receipt_root = environment.pool_factory_call["receipt_root"]
    assert isinstance(receipt_root, Path)
    assert receipt_root.name == "environment-pool"
    assert environment.pool_closed_before_publication is True
    assert environment.publication_events == ["session", "output"]
    assert "/workspace/output.md" in environment.uploaded_files
    session_receipt = json.loads(
        environment.uploaded_session["session-receipt.json"],
    )
    assert (
        hashlib.sha256(
            environment.uploaded_files["/workspace/output.md"],
        ).hexdigest()
        == session_receipt["final_output_artifact_sha256"]
    )
    assert context.metadata["proposal_session_receipt_sha256"] == session_receipt["content_sha256"]
    assert environment.uploaded_session["session-receipt.json"].endswith(b"\n")
    assert context.metadata["proposal_session_status"] == "completed"
    assert context.metadata["trial_record_permitted"] is True


def test_entrypoint_ready_set_fails_closed_without_pool_provider(
    tmp_path: Path,
) -> None:
    inputs = _ready_set_inputs(tmp_path)
    environment = SimpleNamespace(
        environment_dir=tmp_path / "outer-environment",
        session_id="outer.ready-set",
        compute_backend="morph",
    )
    agent = _agent(inputs)

    with (
        patch(
            "agents.entrypoint_agent._provider_environment",
            return_value={},
        ),
        pytest.raises(RuntimeError, match="isolated environment pool"),
    ):
        asyncio.run(
            agent.run(
                instruction="Ignored.",
                environment=environment,
                context=SimpleNamespace(),
            )
        )


def _ready_set_inputs(tmp_path: Path) -> LoadedProposalSessionHostInputs:
    config, _sequential_bundle, derived_task = _rlm_host_fixture(
        tmp_path / "sequential-inputs",
    )
    sequential_inputs = load_proposal_session_host_inputs(
        config.model_dump(mode="json"),
        environment_dir=derived_task / "environment",
    )
    ready_bundle, ready_source_task = _ready_set_bundle(
        tmp_path / "ready-set",
    )
    ready_config = sequential_inputs.config.model_copy(
        update={
            "source_task_dir": str(ready_source_task.resolve()),
            "source_task_package_sha256": source_task_package_sha256(ready_source_task),
            "evaluation_coordinate": _evaluation_coordinate(ready_bundle),
        },
    )
    return dataclasses.replace(
        sequential_inputs,
        config=ready_config,
        bundle=ready_bundle,
        source_task_dir=ready_source_task,
    )


def _agent(inputs: LoadedProposalSessionHostInputs) -> EntrypointAgent:
    agent = EntrypointAgent(
        logs_dir=Path("/tmp/proposal-ready-set-agent"),
        model_name=_proposal_model(inputs.bundle),
        adapter="proposal_session",
        proposal_session=inputs.config.model_dump(mode="json"),
        extra_env={},
    )
    agent._proposal_inputs = inputs
    return agent


class _ReadySetOuterEnvironment:
    def __init__(
        self,
        *,
        environment_dir: Path,
        bundle: Any,
        runtime_archive_sha256: str,
        pool_root: Path,
    ) -> None:
        self.environment_dir = environment_dir
        self.session_id = "outer.ready-set"
        self.compute_backend = "morph"
        self.pool = _RecordingProposalEnvironmentPool(
            root=pool_root,
            bundle=bundle,
            runtime_archive_sha256=runtime_archive_sha256,
            capacity=2,
        )
        self.pool_factory_call: dict[str, object] | None = None
        self.pool_open = False
        self.pool_closed_before_publication = False
        self.publication_events: list[str] = []
        self.uploaded_files: dict[str, bytes] = {}
        self.uploaded_session: dict[str, bytes] = {}

    @asynccontextmanager
    async def create_isolated_environment_pool(
        self,
        **kwargs: object,
    ) -> AsyncIterator[_RecordingProposalEnvironmentPool]:
        self.pool_factory_call = dict(kwargs)
        self.pool_open = True
        try:
            yield self.pool
        finally:
            self.pool_open = False

    async def upload_file(
        self,
        source_path: Path | str,
        target_path: str,
    ) -> None:
        self.pool_closed_before_publication = not self.pool_open
        self.publication_events.append("output")
        self.uploaded_files[target_path] = Path(source_path).read_bytes()

    async def upload_dir(
        self,
        source_dir: Path | str,
        target_dir: str,
    ) -> None:
        assert target_dir == "/workspace/proposal-session"
        self.pool_closed_before_publication = not self.pool_open
        self.publication_events.append("session")
        source = Path(source_dir)
        self.uploaded_session = {
            path.relative_to(source).as_posix(): path.read_bytes()
            for path in sorted(source.rglob("*"))
            if path.is_file()
        }
