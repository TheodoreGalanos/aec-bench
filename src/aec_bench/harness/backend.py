# ABOUTME: Compute backend contract for harness execution in aec-bench Python.
# ABOUTME: Keeps Modal, Docker, and future backends behind one orchestration-facing interface.

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from aec_bench.adapters.base import AdapterResult
from aec_bench.harness.execution_payload import ExecutionBundle


@dataclass(frozen=True)
class TrialHandle:
    backend_name: str
    handle_id: str


@dataclass(frozen=True)
class CollectedArtifacts:
    output_path: Path | None = None
    conversation_path: Path | None = None
    verifier_reward_path: Path | None = None
    verifier_details_path: Path | None = None


@dataclass(frozen=True)
class BackendExecutionRequest:
    execution_bundle: ExecutionBundle
    verifier_script: Path
    verifier_reward_path: str = "/logs/verifier/reward.json"
    verifier_details_path: str | None = "/logs/verifier/details.json"


@dataclass(frozen=True)
class BackendExecutionResult:
    adapter_result: AdapterResult
    collected_artifacts: CollectedArtifacts


@runtime_checkable
class ComputeBackend(Protocol):
    def build_environment(self, *, task_dir: Path) -> str: ...

    def launch_trial(self, *, image_ref: str, workspace_dir: Path) -> TrialHandle: ...

    def execute_trial(
        self,
        *,
        handle: TrialHandle,
        request: BackendExecutionRequest,
    ) -> BackendExecutionResult: ...

    def collect_outputs(self, *, handle: TrialHandle) -> CollectedArtifacts: ...

    def teardown(self, *, handle: TrialHandle) -> None: ...
