# ABOUTME: Executes and verifies declared task-world stage artifacts outside the scored TrialRecord ledger.
# ABOUTME: Renders exact routed context, parses stage outputs, and builds content-bound finalization requests.

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.run_bundle import RunBundle, TaskSnapshotRef
from aec_bench.contracts.stage_execution import (
    DeclaredStage,
    DeclaredStageGraph,
    KernelInstructionOverride,
    StageContextManifest,
    StageContextRoute,
    StageExecutionReceipt,
    StageJobFileDigest,
    StageOutput,
    StageResourceEvidence,
)
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.ledger.durability import fsync_directory, mkdir_durable
from aec_bench.meta_harness.program_execution import OperationExecutionContext

_FINAL_JSON_BLOCK = re.compile(r"```json\s*(?P<body>\{.*?\})\s*```", re.DOTALL)


class DeclaredStageRuntimeError(ValueError):
    """Stable stage-runtime failure that may be surfaced through the px operation boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class StoredStageExecutionReceipt:
    """Physical content-addressed receipt and its exact immutable contract."""

    def __init__(
        self,
        *,
        path: Path,
        reference: ArtifactReference,
        receipt: StageExecutionReceipt,
    ) -> None:
        self.path = path
        self.reference = reference
        self.receipt = receipt


def prepare_stage_instruction(
    *,
    bundle: RunBundle,
    tasks_root: Path,
    task_id: str,
    stage_id: str,
    upstream_values: JsonValue | None,
    artifacts_root: Path,
    run_id: str,
    program_node_id: str,
    attempt: int,
) -> tuple[
    KernelInstructionOverride,
    StageContextManifest,
    ArtifactReference,
    tuple[StageExecutionReceipt, ...],
]:
    """Reverify upstream receipts and render exactly the declared inputs for one stage."""

    snapshot, graph = _stage_graph(bundle, task_id)
    stage = graph.stage(stage_id)
    if stage is None:
        raise DeclaredStageRuntimeError(
            "declared_stage_unknown",
            f"task {task_id!r} does not declare stage {stage_id!r}",
        )
    upstream = _load_upstream_receipts(upstream_values)
    _validate_upstream_set(
        bundle=bundle,
        run_id=run_id,
        snapshot=snapshot,
        graph=graph,
        stage=stage,
        receipts=upstream,
    )
    context_payload, routes = _routed_context(
        graph=graph,
        stage=stage,
        receipts=upstream,
    )
    task_dir = Path(tasks_root) / task_id
    instruction = (task_dir / "instruction.md").read_text(encoding="utf-8")
    system_prompt_path = task_dir / "environment" / "system_prompt.md"
    system_prompt = system_prompt_path.read_text(encoding="utf-8") if system_prompt_path.is_file() else ""
    rendered_context = _render_stage_context(
        task_id=task_id,
        graph=graph,
        stage=stage,
        context_payload=context_payload,
    )
    namespace = (
        Path(artifacts_root)
        / bundle.content_sha256
        / "runs"
        / _safe_segment(run_id)
        / "stage-contexts"
        / _safe_segment(program_node_id)
        / f"a{attempt}"
    )
    rendered_reference = _store_bytes(
        namespace=namespace,
        filename="rendered-context.md",
        kind="stage-context",
        media_type="text/markdown",
        encoded=rendered_context.encode("utf-8"),
    )
    manifest = StageContextManifest(
        task_id=task_id,
        stage_graph_sha256=graph.content_sha256,
        consumer_stage_id=stage_id,
        base_context_sha256=canonical_content_sha256(
            {
                "instruction_sha256": hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
                "system_prompt_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
            }
        ),
        routes=routes,
        rendered_context=rendered_reference,
    )
    manifest_reference = _store_model(
        namespace=namespace,
        filename="stage-context-manifest.json",
        kind="stage-context-manifest",
        model=manifest,
    )
    effective_instruction = (
        instruction.rstrip()
        + "\n\n"
        + rendered_context
        + "\n\n"
        + _stage_output_contract(task_id=task_id, graph=graph, stage=stage)
    )
    override = KernelInstructionOverride(
        mode="declared_stage",
        task_id=task_id,
        original_instruction_sha256=hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
        effective_instruction=effective_instruction,
        stage_id=stage_id,
        context_manifest_sha256=manifest.content_sha256,
    )
    return override, manifest, manifest_reference, upstream


def persist_stage_execution(
    *,
    bundle: RunBundle,
    task_id: str,
    stage_id: str,
    run_id: str,
    context: OperationExecutionContext,
    context_manifest: StageContextManifest,
    context_manifest_reference: ArtifactReference,
    upstream_receipts: tuple[StageExecutionReceipt, ...],
    job_dir: Path,
    artifacts_root: Path,
) -> StoredStageExecutionReceipt:
    """Parse one completed isolated job and publish its tamper-evident receipt."""

    snapshot, graph = _stage_graph(bundle, task_id)
    stage = graph.stage(stage_id)
    if stage is None:
        raise DeclaredStageRuntimeError("declared_stage_unknown", f"unknown stage {stage_id!r}")
    raw_output_path, agent_result_path, result_path = _single_stage_job_files(job_dir)
    raw_output = raw_output_path.read_text(encoding="utf-8")
    parsed_output = _parse_stage_output(
        raw_output,
        task_id=task_id,
        stage=stage,
        required_output_ids=graph.required_output_ids(stage_id),
    )
    namespace = (
        Path(artifacts_root)
        / bundle.content_sha256
        / "runs"
        / _safe_segment(run_id)
        / "stage-outputs"
        / _safe_segment(context.node_id)
        / f"a{context.attempt_index}"
    )
    parsed_reference = _store_model(
        namespace=namespace,
        filename="stage-output.json",
        kind="stage-output",
        model=parsed_output,
    )
    resources = _stage_resources(
        agent_result_path=agent_result_path,
        result_path=result_path,
    )
    upstream_references = tuple(_receipt_reference(receipt) for receipt in upstream_receipts)
    receipt = StageExecutionReceipt(
        bundle_id=bundle.bundle_id,
        bundle_sha256=bundle.content_sha256,
        run_id=run_id,
        program_sha256=bundle.program.content_sha256,
        program_node_id=context.node_id,
        operation_sha256=context.operation_ref.content_sha256,
        attempt=context.attempt_index,
        task_id=task_id,
        task_package_sha256=snapshot.package_sha256,
        world_package_sha256=graph.world_package_sha256,
        stage_graph_sha256=graph.content_sha256,
        stage_id=stage_id,
        context_manifest=context_manifest_reference,
        upstream_receipts=upstream_references,
        raw_output=_file_reference(
            raw_output_path,
            kind="stage-output-raw",
            media_type="text/markdown",
        ),
        parsed_output=parsed_reference,
        agent_result=_file_reference(
            agent_result_path,
            kind="stage-agent-result",
            media_type="application/json",
        ),
        job_dir=str(Path(job_dir).resolve()),
        job_files=_job_file_digests(job_dir),
        resources=resources,
    )
    receipt_reference = _store_model(
        namespace=(Path(artifacts_root) / bundle.content_sha256 / "runs" / _safe_segment(run_id) / "stage-receipts"),
        filename="stage-execution-receipt.json",
        kind="stage-execution-receipt",
        model=receipt,
    )
    loaded = load_stage_execution_receipt(Path(receipt_reference.path))
    if loaded != receipt:
        raise DeclaredStageRuntimeError(
            "stage_receipt_round_trip_mismatch",
            "persisted stage receipt differs from the completed isolated dispatch",
        )
    return StoredStageExecutionReceipt(
        path=Path(receipt_reference.path),
        reference=receipt_reference,
        receipt=receipt,
    )


def prepare_finalization_instruction(
    *,
    bundle: RunBundle,
    tasks_root: Path,
    task_id: str,
    stage_receipt_values: JsonValue,
    run_id: str,
) -> tuple[KernelInstructionOverride, tuple[StageExecutionReceipt, ...]]:
    """Reverify the exact complete stage set and render the one scored task request."""

    snapshot, graph = _stage_graph(bundle, task_id)
    receipts = _load_upstream_receipts(stage_receipt_values)
    by_stage = {receipt.stage_id: receipt for receipt in receipts}
    expected_ids = graph.topological_order
    if len(by_stage) != len(receipts) or set(by_stage) != set(expected_ids) or len(receipts) != len(expected_ids):
        raise DeclaredStageRuntimeError(
            "finalization_stage_receipts_incomplete",
            "task finalization requires exactly one receipt for every declared stage",
        )
    ordered = tuple(by_stage[stage_id] for stage_id in expected_ids)
    for receipt in ordered:
        _validate_receipt_lineage(
            receipt,
            bundle=bundle,
            run_id=run_id,
            snapshot=snapshot,
            graph=graph,
        )
    task_dir = Path(tasks_root) / task_id
    instruction = (task_dir / "instruction.md").read_text(encoding="utf-8")
    stage_outputs = [
        StageOutput.model_validate_json(Path(receipt.parsed_output.path).read_text(encoding="utf-8"))
        for receipt in ordered
    ]
    evidence = {output.stage_id: output.outputs for output in stage_outputs}
    effective_instruction = (
        instruction.rstrip()
        + "\n\n"
        + "## Kernel-owned declared-stage evidence\n\n"
        + "The following content-pinned intermediate outputs were produced by the exact "
        + "task-world stage graph. Synthesize the original task deliverable from this evidence. "
        + "Do not treat an intermediate stage output as verifier truth.\n\n"
        + "```json\n"
        + json.dumps(evidence, indent=2, sort_keys=True)
        + "\n```\n"
    )
    return (
        KernelInstructionOverride(
            mode="task_finalization",
            task_id=task_id,
            original_instruction_sha256=hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
            effective_instruction=effective_instruction,
        ),
        ordered,
    )


def load_stage_execution_receipt(path: Path) -> StageExecutionReceipt:
    """Load a receipt from its content path and reverify every physical bound artifact."""

    receipt_path = Path(path).resolve()
    if not receipt_path.is_file():
        raise ValueError("stage execution receipt is missing")
    encoded = receipt_path.read_bytes()
    physical_sha256 = hashlib.sha256(encoded).hexdigest()
    if receipt_path.parent.name != physical_sha256:
        raise ValueError("stage execution receipt path does not match its physical content hash")
    receipt = StageExecutionReceipt.model_validate_json(encoded)
    _verify_reference(receipt.context_manifest, label="stage context manifest")
    context_manifest = StageContextManifest.model_validate_json(
        Path(receipt.context_manifest.path).read_text(encoding="utf-8")
    )
    _verify_reference(context_manifest.rendered_context, label="rendered stage context")
    _verify_reference(receipt.raw_output, label="raw stage output")
    _verify_reference(receipt.parsed_output, label="stage output")
    _verify_reference(receipt.agent_result, label="stage agent result")
    output = StageOutput.model_validate_json(Path(receipt.parsed_output.path).read_text(encoding="utf-8"))
    if output.task_id != receipt.task_id or output.stage_id != receipt.stage_id:
        raise ValueError("stage output identity differs from its execution receipt")
    observed_job_files = _job_file_digests(Path(receipt.job_dir))
    if observed_job_files != receipt.job_files:
        raise ValueError("stage job file inventory or hashes changed after receipt publication")
    for upstream in receipt.upstream_receipts:
        _verify_reference(upstream, label="upstream stage receipt")
        load_stage_execution_receipt(Path(upstream.path))
    return receipt


def stage_receipt_reference(receipt: StageExecutionReceipt) -> ArtifactReference:
    """Return the physical content-addressed reference for one verified receipt."""

    return _receipt_reference(receipt)


def _load_upstream_receipts(value: JsonValue | None) -> tuple[StageExecutionReceipt, ...]:
    if value is None:
        return ()
    values: list[JsonValue]
    if isinstance(value, list):
        values = value
    else:
        values = [value]
    receipts: list[StageExecutionReceipt] = []
    for item in values:
        if not isinstance(item, dict):
            raise DeclaredStageRuntimeError(
                "stage_receipt_reference_invalid",
                "stage receipt inputs must be content-pinned artifact references",
            )
        try:
            reference = ArtifactReference.model_validate(item)
        except ValueError as error:
            raise DeclaredStageRuntimeError(
                "stage_receipt_reference_invalid",
                f"invalid stage receipt reference: {error}",
            ) from error
        if reference.kind != "stage-execution-receipt":
            raise DeclaredStageRuntimeError(
                "stage_receipt_reference_invalid",
                "stage inputs accept only stage-execution-receipt artifacts",
            )
        _verify_reference(reference, label="upstream stage receipt")
        receipts.append(load_stage_execution_receipt(Path(reference.path)))
    return tuple(receipts)


def _validate_upstream_set(
    *,
    bundle: RunBundle,
    run_id: str,
    snapshot: TaskSnapshotRef,
    graph: DeclaredStageGraph,
    stage: DeclaredStage,
    receipts: tuple[StageExecutionReceipt, ...],
) -> None:
    expected_ids = graph.predecessor_stage_ids(stage.stage_id)
    by_stage = {receipt.stage_id: receipt for receipt in receipts}
    if len(by_stage) != len(receipts) or set(by_stage) != set(expected_ids):
        raise DeclaredStageRuntimeError(
            "stage_predecessor_receipts_mismatch",
            f"stage {stage.stage_id!r} requires exact predecessor receipts {expected_ids!r}",
        )
    for receipt in receipts:
        _validate_receipt_lineage(
            receipt,
            bundle=bundle,
            run_id=run_id,
            snapshot=snapshot,
            graph=graph,
        )


def _validate_receipt_lineage(
    receipt: StageExecutionReceipt,
    *,
    bundle: RunBundle,
    run_id: str,
    snapshot: TaskSnapshotRef,
    graph: DeclaredStageGraph,
) -> None:
    expected = (
        bundle.bundle_id,
        bundle.content_sha256,
        run_id,
        bundle.program.content_sha256,
        snapshot.task_id,
        snapshot.package_sha256,
        graph.world_package_sha256,
        graph.content_sha256,
    )
    observed = (
        receipt.bundle_id,
        receipt.bundle_sha256,
        receipt.run_id,
        receipt.program_sha256,
        receipt.task_id,
        receipt.task_package_sha256,
        receipt.world_package_sha256,
        receipt.stage_graph_sha256,
    )
    if observed != expected:
        raise DeclaredStageRuntimeError(
            "stage_receipt_lineage_mismatch",
            "stage receipt does not bind the active bundle, task, world, graph, and run",
        )


def _routed_context(
    *,
    graph: DeclaredStageGraph,
    stage: DeclaredStage,
    receipts: tuple[StageExecutionReceipt, ...],
) -> tuple[dict[str, JsonValue], tuple[StageContextRoute, ...]]:
    by_stage = {receipt.stage_id: receipt for receipt in receipts}
    values: dict[str, JsonValue] = {}
    routes: list[StageContextRoute] = []
    for producer_stage_id in graph.predecessor_stage_ids(stage.stage_id):
        receipt = by_stage[producer_stage_id]
        output = StageOutput.model_validate_json(Path(receipt.parsed_output.path).read_text(encoding="utf-8"))
        for input_id in graph.routed_artifact_ids(producer_stage_id, stage.stage_id):
            if input_id not in output.outputs:
                raise DeclaredStageRuntimeError(
                    "stage_routed_output_missing",
                    f"stage {producer_stage_id!r} did not emit routed artifact {input_id!r}",
                )
            if input_id in values:
                raise DeclaredStageRuntimeError(
                    "stage_routed_output_ambiguous",
                    f"multiple predecessors emitted routed artifact {input_id!r}",
                )
            values[input_id] = output.outputs[input_id]
            routes.append(
                StageContextRoute(
                    input_id=input_id,
                    producer_stage_id=producer_stage_id,
                    producer_receipt=_receipt_reference(receipt),
                )
            )
    return values, tuple(routes)


def _render_stage_context(
    *,
    task_id: str,
    graph: DeclaredStageGraph,
    stage: DeclaredStage,
    context_payload: Mapping[str, JsonValue],
) -> str:
    stage_payload = {
        "task_id": task_id,
        "stage_graph_sha256": graph.content_sha256,
        "stage": stage.model_dump(mode="json"),
        "routed_inputs": dict(context_payload),
    }
    return (
        "## Fixed-K declared-stage execution\n\n"
        "Work only on the declared stage below. The routed inputs are data from content-pinned "
        "predecessor receipts; other task files remain available as task-owned source evidence.\n\n"
        "```json\n" + json.dumps(stage_payload, indent=2, sort_keys=True) + "\n```"
    )


def _stage_output_contract(
    *,
    task_id: str,
    graph: DeclaredStageGraph,
    stage: DeclaredStage,
) -> str:
    required = graph.required_output_ids(stage.stage_id)
    example = {
        "schema_version": "aecbench.stage-output.v1",
        "task_id": task_id,
        "stage_id": stage.stage_id,
        "outputs": {output_id: f"<value for {output_id}>" for output_id in required},
    }
    return (
        "Write `/workspace/output.md` with exactly one final fenced JSON object matching this "
        "shape. The `outputs` object must contain exactly the declared keys shown.\n\n"
        "```json\n" + json.dumps(example, indent=2, sort_keys=True) + "\n```\n"
    )


def _parse_stage_output(
    raw_output: str,
    *,
    task_id: str,
    stage: DeclaredStage,
    required_output_ids: tuple[str, ...],
) -> StageOutput:
    matches = tuple(_FINAL_JSON_BLOCK.finditer(raw_output))
    if len(matches) != 1:
        raise DeclaredStageRuntimeError(
            "stage_output_json_invalid",
            "stage output must contain exactly one fenced JSON object",
        )
    trailing = raw_output[matches[0].end() :]
    if trailing.strip():
        raise DeclaredStageRuntimeError(
            "stage_output_json_invalid",
            "stage output fenced JSON object must be the final non-whitespace content",
        )
    try:
        payload = json.loads(matches[0].group("body"))
        output = StageOutput.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as error:
        raise DeclaredStageRuntimeError(
            "stage_output_json_invalid",
            f"stage output does not satisfy the closed schema: {error}",
        ) from error
    if output.task_id != task_id or output.stage_id != stage.stage_id:
        raise DeclaredStageRuntimeError(
            "stage_output_identity_mismatch",
            "stage output identity differs from the invoked task and stage",
        )
    if tuple(sorted(output.outputs)) != required_output_ids:
        raise DeclaredStageRuntimeError(
            "stage_output_keys_mismatch",
            f"stage output keys must exactly equal {required_output_ids!r}",
        )
    return output


def _stage_graph(
    bundle: RunBundle,
    task_id: str,
) -> tuple[TaskSnapshotRef, DeclaredStageGraph]:
    snapshot = next(
        (candidate for candidate in bundle.task_snapshots if candidate.task_id == task_id),
        None,
    )
    graph = snapshot.world.stage_graph if snapshot is not None and snapshot.world is not None else None
    if snapshot is None or graph is None:
        raise DeclaredStageRuntimeError(
            "declared_stage_graph_missing",
            f"task {task_id!r} has no content-pinned declared stage graph",
        )
    return snapshot, graph


def _single_stage_job_files(job_dir: Path) -> tuple[Path, Path, Path]:
    root = Path(job_dir).resolve()
    output_paths = tuple(sorted(root.rglob("artifacts/agent/output.md")))
    if len(output_paths) != 1:
        raise DeclaredStageRuntimeError(
            "stage_job_output_ambiguous",
            "isolated stage dispatch must produce exactly one agent output artifact",
        )
    trial_dir = output_paths[0].parents[2]
    agent_result = trial_dir / "artifacts" / "agent" / "agent_result.json"
    result = trial_dir / "result.json"
    if not agent_result.is_file() or not result.is_file():
        raise DeclaredStageRuntimeError(
            "stage_job_evidence_incomplete",
            "isolated stage dispatch lacks agent_result.json or result.json",
        )
    return output_paths[0], agent_result, result


def _stage_resources(
    *,
    agent_result_path: Path,
    result_path: Path,
) -> StageResourceEvidence:
    agent = _json_object(agent_result_path)
    result = _json_object(result_path)
    result_agent = result.get("agent_result")
    result_agent_payload = result_agent if isinstance(result_agent, dict) else {}
    return StageResourceEvidence(
        wall_seconds=_elapsed_seconds(result),
        tokens_in=_optional_int(agent, "usage_input_tokens", "input_tokens"),
        tokens_out=_optional_int(agent, "usage_output_tokens", "output_tokens"),
        cache_read_tokens=_optional_int(
            agent,
            "usage_cache_read_tokens",
            "cache_read_input_tokens",
        ),
        cache_write_tokens=_optional_int(
            agent,
            "usage_cache_write_tokens",
            "cache_creation_input_tokens",
        ),
        estimated_cost_usd=_optional_float(result_agent_payload, "cost_usd"),
        agent_turns=_optional_int(agent, "turns_used"),
        tool_calls=_optional_int(agent, "tool_calls_used", "tool_calls"),
    )


def _elapsed_seconds(result: Mapping[str, Any]) -> float:
    started = result.get("started_at")
    finished = result.get("finished_at")
    if not isinstance(started, str) or not isinstance(finished, str):
        return 0.0
    try:
        return max(
            0.0,
            (
                datetime.fromisoformat(finished.replace("Z", "+00:00"))
                - datetime.fromisoformat(started.replace("Z", "+00:00"))
            ).total_seconds(),
        )
    except ValueError:
        return 0.0


def _json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DeclaredStageRuntimeError(
            "stage_job_evidence_invalid",
            f"invalid JSON evidence at {path}: {error}",
        ) from error
    if not isinstance(payload, dict):
        raise DeclaredStageRuntimeError(
            "stage_job_evidence_invalid",
            f"stage evidence at {path} must be a JSON object",
        )
    return payload


def _optional_int(payload: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _optional_float(payload: Mapping[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, int | float) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None


def _job_file_digests(job_dir: Path) -> tuple[StageJobFileDigest, ...]:
    root = Path(job_dir).resolve()
    if not root.is_dir():
        raise ValueError("completed stage job directory is missing")
    return tuple(
        StageJobFileDigest(
            relative_path=path.relative_to(root).as_posix(),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            size_bytes=path.stat().st_size,
        )
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file())
    )


def _receipt_reference(receipt: StageExecutionReceipt) -> ArtifactReference:
    """Recover the physical receipt reference from its content-addressed artifact identity."""

    encoded = _encoded_model(receipt)
    physical_sha256 = hashlib.sha256(encoded).hexdigest()
    candidates = tuple(
        Path(reference.path)
        for reference in (
            receipt.context_manifest,
            receipt.raw_output,
            receipt.parsed_output,
            receipt.agent_result,
        )
    )
    run_root = next(
        (parent for candidate in candidates for parent in candidate.parents if parent.name == "runs"),
        None,
    )
    if run_root is None:
        raise ValueError("stage receipt artifacts do not expose a content-addressed run root")
    run_namespace = run_root / _safe_segment(receipt.run_id) / "stage-receipts"
    path = run_namespace / physical_sha256 / "stage-execution-receipt.json"
    if not path.is_file() or path.read_bytes() != encoded:
        raise ValueError("physical stage receipt artifact is missing")
    return ArtifactReference(
        kind="stage-execution-receipt",
        path=str(path.resolve()),
        sha256=physical_sha256,
        media_type="application/json",
    )


def _file_reference(
    path: Path,
    *,
    kind: str,
    media_type: str,
) -> ArtifactReference:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise ValueError(f"{kind} artifact is missing")
    return ArtifactReference(
        kind=kind,
        path=str(resolved),
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        media_type=media_type,
    )


def _verify_reference(reference: ArtifactReference, *, label: str) -> None:
    path = Path(reference.path)
    if not path.is_file():
        raise ValueError(f"{label} artifact is missing")
    if hashlib.sha256(path.read_bytes()).hexdigest() != reference.sha256:
        raise ValueError(f"{label} artifact hash changed after publication")


def _store_model(
    *,
    namespace: Path,
    filename: str,
    kind: str,
    model: Any,
) -> ArtifactReference:
    return _store_bytes(
        namespace=namespace,
        filename=filename,
        kind=kind,
        media_type="application/json",
        encoded=_encoded_model(model),
    )


def _encoded_model(model: Any) -> bytes:
    return (json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _store_bytes(
    *,
    namespace: Path,
    filename: str,
    kind: str,
    media_type: str,
    encoded: bytes,
) -> ArtifactReference:
    sha256 = hashlib.sha256(encoded).hexdigest()
    path = (Path(namespace) / sha256 / filename).resolve()
    _write_content_addressed(path, encoded)
    return ArtifactReference(
        kind=kind,
        path=str(path),
        sha256=sha256,
        media_type=media_type,
    )


def _write_content_addressed(path: Path, encoded: bytes) -> None:
    mkdir_durable(path.parent)
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError("content-addressed stage artifact contains different bytes")
        return
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != encoded:
                raise ValueError("content-addressed stage artifact contains different bytes") from None
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_segment(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in "-." else "-" for character in value)
    if not safe or safe in {".", ".."}:
        raise ValueError("runtime identifier cannot be represented as a safe path segment")
    return safe
