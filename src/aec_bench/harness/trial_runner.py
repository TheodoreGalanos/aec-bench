# ABOUTME: Minimal trial orchestration for one benchmark execution in aec-bench Python.
# ABOUTME: Ties backend provisioning, adapter execution, transcript persistence,
# ABOUTME: verifier reading, and TrialRecord construction together.

from dataclasses import dataclass
from pathlib import Path

from aec_bench.adapters.base import AdapterRequest, RemoteExecutableAdapter
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.trial_record import (
    AdaptationProvenance,
    Completeness,
    TrialRecord,
)
from aec_bench.contracts.validators import infer_output_format, normalize_workspace_path
from aec_bench.harness.backend import BackendExecutionRequest, ComputeBackend
from aec_bench.harness.execution_payload import build_execution_bundle
from aec_bench.harness.transcript_artifacts import write_transcript_artifact
from aec_bench.harness.trial_record_builder import build_trial_record
from aec_bench.harness.verifier_artifacts import read_verifier_artifacts
from aec_bench.tasks.instance import ResolvedTaskInstance


@dataclass(frozen=True)
class TrialRunner:
    artifacts_dir: Path

    def run(
        self,
        *,
        trial_id: str,
        experiment_id: str,
        task: ResolvedTaskInstance,
        task_revision: str,
        backend: ComputeBackend,
        adapter: RemoteExecutableAdapter,
        runtime_image: str,
        adapter_revision: str | None = None,
        tool_versions: dict[str, str] | None = None,
        adaptation: AdaptationProvenance | None = None,
    ) -> TrialRecord:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        image_ref = backend.build_environment(task_dir=task.instance_dir)
        handle = backend.launch_trial(image_ref=image_ref, workspace_dir=task.instance_dir)

        try:
            request = AdapterRequest(
                instruction=task.task.instruction,
                tools=task.task.environment.tools,
                output_path=normalize_workspace_path(task.task.verifier.expected_output_path),
                output_format=infer_output_format(task.task.verifier.expected_output_path),
            )
            execution = backend.execute_trial(
                handle=handle,
                request=BackendExecutionRequest(
                    execution_bundle=build_execution_bundle(
                        execution=adapter.serialize_execution(),
                        request=request,
                    ),
                    verifier_script=task.verifier_script,
                    verifier_reward_path=task.task.verifier.reward_path,
                    verifier_details_path=task.task.verifier.details_path,
                ),
            )
            result = execution.adapter_result
            conversation_path = write_transcript_artifact(
                path=self.artifacts_dir / f"{trial_id}-conversation.jsonl",
                transcript=result.transcript,
            )
            artifacts = execution.collected_artifacts
            evaluation = read_verifier_artifacts(
                reward_path=artifacts.verifier_reward_path,
                details_path=artifacts.verifier_details_path,
                output_parseable=result.agent_output.status is AgentOutputStatus.COMPLETED,
                schema_valid=result.agent_output.status is AgentOutputStatus.COMPLETED,
            )
            return build_trial_record(
                trial_id=trial_id,
                experiment_id=experiment_id,
                task=task.task,
                task_revision=task_revision,
                request=request,
                result=result,
                evaluation=evaluation,
                total_seconds=0.0,
                runtime_image=runtime_image,
                compute_backend=handle.backend_name,
                adapter_revision=adapter_revision,
                tool_versions=tool_versions,
                raw_output_path=_as_posix_or_none(artifacts.output_path),
                conversation_path=conversation_path.as_posix(),
                # trajectory_path is None here because trajectory.jsonl collection
                # from the container workspace is backend-specific. Backends that
                # expose the file should resolve it before calling build_trial_record.
                trajectory_path=None,
                adaptation=adaptation,
                # PARTIAL because input_files provenance is not tracked by the runner.
                # COMPLETE requires adapter_revision + tool_versions + input_files.
                completeness=Completeness.PARTIAL,
            )
        finally:
            backend.teardown(handle=handle)


def _as_posix_or_none(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.as_posix()
