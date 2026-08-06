# ABOUTME: Supplies a public-tool-only reference agent for Harbor lifecycle integration tests.
# ABOUTME: Derives SSC-03 submissions from staged tool outputs without hidden or verifier imports.

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from typing import Any, cast

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.adapters.transcript import TranscriptEntry, TranscriptEvent, TranscriptRole, initialize_transcript
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from agents.entrypoint_agent import EntrypointAgent


class PublicToolReferenceEntrypointAgent(EntrypointAgent):
    """Exercise the production bridge with a deterministic public-surface agent."""

    def _lifecycle_adapter_builder(self) -> Any:
        return _PublicToolBuilder().build


class _PublicToolBuilder:
    def build(
        self,
        *,
        adapter_kind: str,
        model_name: str,
        workspace: str,
        native_tools: list[Callable[..., str]],
        enable_bash: bool,
        **_kwargs: Any,
    ) -> _PublicToolLifecycleAdapter:
        del workspace
        if adapter_kind != "tool_loop" or enable_bash:
            raise ValueError("reference lifecycle agent requires the confined tool-loop surface")
        return _PublicToolLifecycleAdapter(
            model_name=model_name,
            tools={tool.__name__: tool for tool in native_tools},
        )


class _PublicToolLifecycleAdapter:
    def __init__(self, *, model_name: str, tools: dict[str, Callable[..., str]]) -> None:
        self._model_name = model_name
        self._tools = tools
        self._transcript: list[TranscriptEntry] = []
        self._tool_call_index = 0
        self._operation_results: dict[str, dict[str, Any]] = {}
        self._operation_artifacts: dict[str, dict[str, dict[str, Any] | str]] = {}

    def execute(self, request: AdapterRequest) -> AdapterResult:
        self._transcript = initialize_transcript(request)
        expected_tools = {
            "execute_operation",
            "list_workspace",
            "read_workspace_file",
            "revisit_checkpoint",
            "submit_checkpoint",
            "write_checkpoint_submission",
        }
        if set(self._tools) != expected_tools:
            raise ValueError("reference agent received an unexpected lifecycle tool surface")
        self._assert_confinement()
        self._complete_baseline()
        self._complete_revision()
        self._complete_closeout()
        return AdapterResult(
            adapter_name="tool_loop",
            resolved_model=self._model_name,
            configuration_record=dict(request.configuration),
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=self._transcript,
            raw_output_text="Completed from staged public lifecycle tool outputs.",
            usage_input_tokens=0,
            usage_output_tokens=0,
        )

    def _assert_confinement(self) -> None:
        hidden_probe = self._call("read_workspace_file", path="../tests/compiled-world/hidden/variant.json")
        if hidden_probe.get("status") != "rejected":
            raise ValueError("workspace tool exposed hidden verifier material")
        future_probe = self._call("read_workspace_file", path="inbox/revision_analysis/notice.md")
        if future_probe.get("status") != "rejected":
            raise ValueError("workspace tool exposed a future release")

    def _complete_baseline(self) -> None:
        checkpoint_id = "baseline_analysis"
        instruction = self._read_text("instruction.md")
        claim_boundary = _claim_boundary(instruction)
        operations = self._execute_declared_operations(checkpoint_id)
        decisions = self._decisions(checkpoint_id, operations, phase="baseline")
        submission = {
            "checkpoint_id": checkpoint_id,
            "visible_source_state_sha256": self._visible_source_sha256(),
            "selected_operations": _selected_operations(operations),
            "accepted_decisions": decisions,
            "readiness_decision": _readiness(decisions),
            "claim_boundary": claim_boundary,
        }
        self._write_and_submit(checkpoint_id, submission)

    def _complete_revision(self) -> None:
        checkpoint_id = "revision_analysis"
        instruction = self._read_text("instruction.md")
        claim_boundary = _claim_boundary(instruction)
        baseline = self._read_json("submissions/baseline_analysis.json")
        operations = self._execute_declared_operations(checkpoint_id)
        candidates = self._decisions(checkpoint_id, operations, phase="revision")
        baseline_by_scenario = {
            str(item["scenario_id"]): item for item in cast(list[dict[str, Any]], baseline["accepted_decisions"])
        }
        decisions: list[dict[str, Any]] = []
        supersession: list[dict[str, str]] = []
        for candidate in candidates:
            scenario_id = str(candidate["scenario_id"])
            previous = baseline_by_scenario[scenario_id]
            changed = _decision_action_ids(candidate) != _decision_action_ids(previous)
            decisions.append(candidate if changed else previous)
            if changed:
                supersession.append(
                    {
                        "scenario_id": scenario_id,
                        "superseded_decision_id": str(previous["decision_id"]),
                        "replacement_decision_id": str(candidate["decision_id"]),
                    }
                )
        current_source = self._read_json("hydraulics/current-source.json")
        submission = {
            "checkpoint_id": checkpoint_id,
            "revision_id": current_source["revision_id"],
            "visible_source_state_sha256": current_source["visible_source_state_sha256"],
            "selected_operations": _selected_operations(operations),
            "accepted_decisions": decisions,
            "supersession_lineage": supersession,
            "readiness_decision": _readiness(decisions),
            "claim_boundary": claim_boundary,
        }
        self._write_and_submit(checkpoint_id, submission)

    def _complete_closeout(self) -> None:
        checkpoint_id = "closeout_review"
        instruction = self._read_text("instruction.md")
        claim_boundary = _claim_boundary(instruction)
        revision = self._read_json("submissions/revision_analysis.json")
        selected = cast(dict[str, str], revision["selected_operations"])
        decisions = cast(list[dict[str, Any]], revision["accepted_decisions"])
        run_reference: dict[str, dict[str, str]] = {}
        report_reference: dict[str, dict[str, str]] = {}
        for scenario_id in _scenario_ids(selected):
            detention_operation = f"detention-outlet.{scenario_id}.declared-outlet"
            hgl_operation = f"network-hgl.{scenario_id}.declared-tailwater"
            detention_action = self._operation_results[detention_operation]
            hgl_action = self._operation_results[hgl_operation]
            detention = cast(
                dict[str, Any],
                self._operation_artifacts[detention_operation]["detention-outlet.json"],
            )
            hgl = cast(dict[str, Any], self._operation_artifacts[hgl_operation]["network-hgl.json"])
            report_sha256 = cast(str, self._operation_artifacts[hgl_operation]["report.md.sha256"])
            run_reference[scenario_id] = {
                "selected_operation_action_id": selected[detention_operation],
                "canonical_detention_action_id": _canonical_action_id(detention_action),
                "hydraulic_run_id": str(detention["hydraulic_run_id"]),
                "run_manifest_sha256": str(detention["hydraulic_run_manifest_sha256"]),
            }
            report_reference[scenario_id] = {
                "selected_operation_action_id": selected[hgl_operation],
                "canonical_hgl_action_id": _canonical_action_id(hgl_action),
                "hydraulic_run_id": str(hgl["hydraulic_run_id"]),
                "report_sha256": report_sha256,
            }
        visible_source_sha256 = str(revision["visible_source_state_sha256"])
        supersession = cast(list[dict[str, str]], revision["supersession_lineage"])
        readiness = str(revision["readiness_decision"])
        memo = {
            "visible_source_state_sha256": visible_source_sha256,
            "run_reference": run_reference,
            "report_reference": report_reference,
            "decision_ids": {str(item["scenario_id"]): str(item["decision_id"]) for item in decisions},
            "supersession_lineage": supersession,
            "readiness_decision": readiness,
            "claim_boundary": claim_boundary,
        }
        submission = {
            "checkpoint_id": checkpoint_id,
            "visible_source_state_sha256": visible_source_sha256,
            "selected_operations": selected,
            "run_reference": run_reference,
            "report_reference": report_reference,
            "accepted_decisions": decisions,
            "supersession_lineage": supersession,
            "readiness_decision": readiness,
            "claim_boundary": claim_boundary,
            "memo": memo,
        }
        completed = self._write_and_submit(checkpoint_id, submission)
        if completed.get("status") != "complete":
            raise ValueError("reference agent did not complete the lifecycle")

    def _execute_declared_operations(self, checkpoint_id: str) -> dict[str, dict[str, Any]]:
        catalog = self._read_json(f"checkpoints/{checkpoint_id}/operations.json")
        declared = cast(list[dict[str, Any]], catalog["operations"])
        source_operations = [item for item in declared if item["kind"] == "request_source_revision"]
        remaining = [item for item in declared if item["kind"] != "request_source_revision"]
        ordered: list[dict[str, Any]] = [*source_operations]
        scheduled = {str(item["operation_id"]) for item in source_operations}
        while remaining:
            ready = [
                item for item in remaining if set(cast(list[str], item["prerequisite_operation_ids"])) <= scheduled
            ]
            if not ready:
                raise ValueError("public operation catalogue cannot be topologically scheduled")
            ready.sort(key=lambda item: str(item["operation_id"]))
            ordered.extend(ready)
            scheduled.update(str(item["operation_id"]) for item in ready)
            remaining = [item for item in remaining if item not in ready]

        results: dict[str, dict[str, Any]] = {}
        for operation in ordered:
            operation_id = str(operation["operation_id"])
            result = self._call(
                "execute_operation",
                checkpoint_id=checkpoint_id,
                operation_id=operation_id,
                visible_source_state_sha256=self._visible_source_sha256(),
                reason=f"Derive {operation_id} from the active public source and declared operation.",
            )
            if result.get("status") == "rejected":
                raise ValueError(f"declared operation was rejected: {operation_id}: {result}")
            results[operation_id] = result
            self._operation_results[operation_id] = result
            self._operation_artifacts[operation_id] = self._read_operation_artifacts(result)
        return results

    def _decisions(
        self,
        checkpoint_id: str,
        operations: dict[str, dict[str, Any]],
        *,
        phase: str,
    ) -> list[dict[str, Any]]:
        del checkpoint_id
        decisions: list[dict[str, Any]] = []
        for scenario_id in _scenario_ids(operations):
            hydrology_id = f"hydrology.{scenario_id}"
            detention_id = f"detention-outlet.{scenario_id}.declared-outlet"
            hgl_id = f"network-hgl.{scenario_id}.declared-tailwater"
            detention = cast(dict[str, Any], self._operation_artifacts[detention_id]["detention-outlet.json"])
            hgl = cast(dict[str, Any], self._operation_artifacts[hgl_id]["network-hgl.json"])
            criteria = cast(dict[str, bool], detention["criteria"]) | cast(dict[str, bool], hgl["criteria"])
            failed = sorted(name for name, passed in criteria.items() if not passed)
            decisions.append(
                {
                    "decision_id": f"decision.{scenario_id}.{phase}",
                    "scenario_id": scenario_id,
                    "hydrology_action_id": _canonical_action_id(operations[hydrology_id]),
                    "detention_action_id": _canonical_action_id(operations[detention_id]),
                    "hgl_action_id": _canonical_action_id(operations[hgl_id]),
                    "hydraulic_run_id": detention["hydraulic_run_id"],
                    "screening_outcome": "criteria_not_met" if failed else "criteria_met",
                    "failed_criteria": failed,
                }
            )
        return decisions

    def _read_operation_artifacts(self, result: dict[str, Any]) -> dict[str, dict[str, Any] | str]:
        artifacts: dict[str, dict[str, Any] | str] = {}
        for artifact in cast(list[dict[str, str]], result["artifacts"]):
            path = artifact["path"]
            name = path.rsplit("/", 1)[-1]
            content = self._read_text(path)
            artifacts[f"{name}.sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if name.endswith(".json"):
                payload = json.loads(content)
                if not isinstance(payload, dict):
                    raise ValueError(f"operation artifact is not a JSON object: {path}")
                artifacts[name] = cast(dict[str, Any], payload)
            else:
                artifacts[name] = content
            if artifacts[f"{name}.sha256"] != artifact["sha256"]:
                raise ValueError(f"operation artifact digest does not match tool output: {path}")
        return artifacts

    def _write_and_submit(self, checkpoint_id: str, submission: dict[str, Any]) -> dict[str, Any]:
        written = self._call(
            "write_checkpoint_submission",
            checkpoint_id=checkpoint_id,
            content=json.dumps(submission, sort_keys=True),
        )
        if written.get("status") != "written":
            raise ValueError(f"checkpoint submission was rejected: {written}")
        result = self._call("submit_checkpoint", checkpoint_id=checkpoint_id)
        if result.get("status") == "rejected":
            raise ValueError(f"checkpoint submission did not advance: {result}")
        return result

    def _visible_source_sha256(self) -> str:
        return str(self._read_json("hydraulics/current-source.json")["visible_source_state_sha256"])

    def _read_json(self, path: str) -> dict[str, Any]:
        payload = json.loads(self._read_text(path))
        if not isinstance(payload, dict):
            raise ValueError(f"public lifecycle file is not a JSON object: {path}")
        return cast(dict[str, Any], payload)

    def _read_text(self, path: str) -> str:
        result = self._call("read_workspace_file", path=path)
        if result.get("status") != "ok":
            raise ValueError(f"public lifecycle file was unavailable: {path}: {result}")
        return str(result["content"])

    def _call(self, tool_name: str, **arguments: Any) -> dict[str, Any]:
        self._tool_call_index += 1
        call_id = f"public-tool-{self._tool_call_index:03d}"
        self._transcript.append(
            TranscriptEntry(
                role=TranscriptRole.ASSISTANT,
                content=json.dumps(arguments, sort_keys=True),
                event=TranscriptEvent.TOOL_CALL,
                tool_name=tool_name,
                tool_call_id=call_id,
            )
        )
        raw = self._tools[tool_name](**arguments)
        self._transcript.append(
            TranscriptEntry(
                role=TranscriptRole.TOOL,
                content=raw,
                event=TranscriptEvent.TOOL_RESULT,
                tool_name=tool_name,
                tool_call_id=call_id,
            )
        )
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError(f"lifecycle tool returned a non-object payload: {tool_name}")
        return cast(dict[str, Any], payload)


def _claim_boundary(instruction: str) -> dict[str, Any]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", instruction, flags=re.DOTALL)
    if match is None:
        raise ValueError("active public instruction does not declare its claim boundary")
    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        raise ValueError("public claim boundary is not a JSON object")
    return cast(dict[str, Any], payload)


def _selected_operations(operations: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {operation_id: str(result["action_id"]) for operation_id, result in sorted(operations.items())}


def _canonical_action_id(operation: dict[str, Any]) -> str:
    return str(operation.get("retained_from_action_id") or operation["action_id"])


def _decision_action_ids(decision: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(decision["hydrology_action_id"]),
        str(decision["detention_action_id"]),
        str(decision["hgl_action_id"]),
    )


def _scenario_ids(operations: dict[str, Any]) -> list[str]:
    return sorted(
        operation_id.removeprefix("hydrology.") for operation_id in operations if operation_id.startswith("hydrology.")
    )


def _readiness(decisions: list[dict[str, Any]]) -> str:
    return (
        "not_screening_ready"
        if any(decision["screening_outcome"] == "criteria_not_met" for decision in decisions)
        else "screening_ready"
    )
