# ABOUTME: Defines the provider-neutral contracts shared by proposal-session runtime modules.
# ABOUTME: Keeps execution surfaces and buffered node evidence independent of orchestration.

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, TypedDict

from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.proposal_execution import (
    ProposalNodeReceipt,
)
from aec_bench.contracts.provider_broker import ProviderBrokerPolicy
from aec_bench.harness.execution_payload import ExecutionBundle
from aec_bench.harness.proposal_node_context import (
    PersistedProposalHandoffArtifact,
    ProposalNodeContextManifest,
)
from aec_bench.harness.proposal_session_evidence import (
    ProposalCandidateTransitionEvidence,
)

ProposalBackend = Literal[
    "docker",
    "modal",
    "e2b",
    "daytona",
    "morph",
]


class ProposalSessionRuntimeError(RuntimeError):
    """Host/runtime fault that must not be converted into candidate utility."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class PreparedProposalNodeInvocation:
    """Exact child request and reward-blind context for one model-bearing node."""

    node_id: str
    invocation_id: str
    context_manifest: ProposalNodeContextManifest
    execution_bundle: ExecutionBundle
    provider_broker_policy: ProviderBrokerPolicy
    output_contract: OutputCompletionContract
    node_contract_sha256: str


class ProposalSessionExecResult(Protocol):
    """Provider-neutral command result returned by a proposal environment."""

    stdout: str
    stderr: str
    return_code: int


class ProposalSessionEnvironment(Protocol):
    """Narrow candidate-container surface required by proposal orchestration."""

    async def reset_candidate_container_for_invocation(
        self,
        *,
        invocation_id: str,
        expected_runtime_digest: str,
    ) -> ProposalCandidateTransitionEvidence: ...

    async def upload_file(
        self,
        source_path: Path | str,
        target_path: str,
    ) -> None: ...

    async def upload_dir(
        self,
        source_dir: Path | str,
        target_dir: str,
    ) -> None: ...

    async def download_file(
        self,
        source_path: str,
        target_path: Path | str,
    ) -> None: ...

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
    ) -> ProposalSessionExecResult: ...


class ProposalSessionEnvironmentPool(Protocol):
    """Isolated environment leases available to ready-set proposal execution."""

    capacity: int

    def lease(
        self,
        *,
        invocation_id: str,
    ) -> AbstractAsyncContextManager[ProposalSessionEnvironment]: ...


@dataclass(frozen=True)
class ExecutedProposalNode:
    """Uncommitted node evidence buffered until deterministic publication."""

    receipt: ProposalNodeReceipt
    handoffs: tuple[PersistedProposalHandoffArtifact, ...]
    final_output_sha256: str | None
    final_commit_sha256: str | None


class NodeReceiptLineage(TypedDict):
    """Content identities inherited by every attempted or skipped node receipt."""

    session_id: str
    session_execution_sha256: str
    session_plan_sha256: str
    compilation_sha256: str
    candidate_id: str
    proposal_graph_sha256: str
    problem_view_sha256: str
    kernel_sha256: str
    fixed_harness_sha256: str
    proposal_policy_sha256: str
    node_id: str
    node_source_scope_sha256: str
    node_budget_reservation_sha256: str
    node_contract_sha256: str
