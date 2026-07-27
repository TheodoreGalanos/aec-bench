# ABOUTME: Builds the graph-hidden public task view supplied to decomposition proposers.
# ABOUTME: Audits package, source, output, snapshot, and fixed-harness inputs before invocation.

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Generic, TypeVar

from aec_bench.contracts.harness_instance import (
    CompiledHarnessInstance,
    TaskSourceBindingConfig,
)
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.program_proposal import (
    DecompositionLeakageAudit,
    DecompositionProblemView,
    FixedHarnessCapabilityProjection,
    PublicAuthorityBoundary,
    PublicDataGapBoundary,
    PublicSourceRef,
)
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.evaluation.task_world import TASK_WORLD_SIDECARS
from aec_bench.meta_harness.task_snapshot import (
    TaskSnapshotError,
    build_task_snapshot,
    graph_hidden_task_snapshot_sha256,
)

_ProposalT = TypeVar("_ProposalT")
_AUDIT_POLICY = {
    "policy_id": "aecbench.decomposition-problem-view-leakage.v1",
    "package_markers": (
        "world/task-world sidecars",
        "composite materializer artifacts",
        "ready-made agent answers",
    ),
    "public_text_classes": (
        "world",
        "stage labels",
        "routes",
        "handoffs",
        "topology",
        "verifier or evaluation policy",
        "answer or oracle",
        "catalogue or template source",
        "nested metadata",
    ),
    "source_path_policy": "relative regular files inside the exact task package only",
}
_AUDIT_POLICY_SHA256 = canonical_content_sha256(_AUDIT_POLICY)
_COMPOSITE_MARKERS = (
    PurePosixPath("template.json"),
    PurePosixPath("hidden/world_state.json"),
    PurePosixPath("hidden/verifier_config.json"),
    PurePosixPath("agent/structured_answer.json"),
)
_FORBIDDEN_SOURCE_PARTS = frozenset(
    {
        "agent",
        "catalogue",
        "gold",
        "hidden",
        "oracle",
        "template",
        "templates",
        "tests",
        "verifier",
    }
)
_FORBIDDEN_SOURCE_NAMES = frozenset(
    {
        "ground_truth.json",
        "output_contract.json",
        "structured_answer.json",
        "task.toml",
        "template.json",
        *TASK_WORLD_SIDECARS,
    }
)
_TEXT_FINDING_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "task_world_sidecar",
        re.compile(
            r"\btask[-_ ]?world\b|[\"']world[_ -]?(?:id|state|profile)[\"']\s*:|"
            r"\bworld[_ -]?sidecar\b",
            re.IGNORECASE,
        ),
    ),
    (
        "stage_label",
        re.compile(
            r"\bstage[_ -]?(?:id|title|label)\b|[\"']stages[\"']\s*:|"
            r"\brequired[_ -]?stages?\s*:",
            re.IGNORECASE,
        ),
    ),
    (
        "route",
        re.compile(
            r"\broute[_ -]?id\b|[\"']routes?[\"']\s*:|"
            r"\binternal[_ -]?route\s*:.*(?:->|→)|\brouting[_ -]?graph\b",
            re.IGNORECASE,
        ),
    ),
    (
        "handoff",
        re.compile(
            r"\bhandoff[_ -]?id\b|[\"']handoffs?[\"']\s*:|"
            r"\bproducer[_ -]stage\b|\bconsumer[_ -]stages?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "topology",
        re.compile(
            r"\btopolog(?:y|ies)\b|\b(?:stage|execution)[_ -]?graph\b|\bDAG\b|"
            r"\bfan[-_ ]?(?:in|out)\b|\bdependency[_ -]?edge\b|\bpredecessor[_ -]?stage\b",
            re.IGNORECASE,
        ),
    ),
    (
        "verifier_or_policy",
        re.compile(
            r"\bverifier[_ -]?(?:script|config|policy|gate)\b|\btests/test\.sh\b|"
            r"\bcritic\b|\bacceptance[_ -]?(?:policy|surface|threshold)\b|"
            r"\beligibility\b|\bdenominator\b|\bevidence[-_ ]?rules?\b|"
            r"\bscoring[_ -]?(?:policy|rubric|threshold)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "authority_policy",
        re.compile(
            r"\bauthority[_ -]?(?:policy|event|grant|ledger)\b|"
            r"\bpromotion[_ -]?(?:approval|authority)\b|\bcapability[_ -]?policy\b",
            re.IGNORECASE,
        ),
    ),
    (
        "answer_or_oracle",
        re.compile(
            r"\bexpected[_ -]?answer\b|\bground[_ -]?truth\b|\bgold(?:en)?[_ -]?(?:answer|output)\b|"
            r"\bgold(?:en)?\b|\boracle\b|\bready[-_ ]?made\b|\bstructured[_ -]?answer\b|"
            r"\bagent[_ -]?answer\b",
            re.IGNORECASE,
        ),
    ),
    (
        "catalogue_or_template",
        re.compile(
            r"\bcatalogue[_ -]?source\b|\btemplate[_ -]?(?:id|source|json)\b|"
            r"\btemplate\.json\b",
            re.IGNORECASE,
        ),
    ),
    (
        "nested_metadata",
        re.compile(
            r"[\"']metadata[\"']\s*:|^\s*metadata\s*:",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class PublicSourceBinding:
    """Host-owned filesystem binding that is projected to an opaque public source ref."""

    source_id: str
    relative_path: str
    media_type: str


@dataclass(frozen=True, slots=True)
class AuditedDecompositionProblemView:
    """A public problem view paired with the exact successful host leakage audit."""

    problem_view: DecompositionProblemView
    audit: DecompositionLeakageAudit


class DecompositionProblemViewRejected(ValueError):
    """Raised when a graph-hidden view cannot be created without leaking host state."""

    def __init__(self, audit: DecompositionLeakageAudit) -> None:
        self.audit = audit
        super().__init__("decomposition problem view rejected: " + ", ".join(audit.finding_codes))


@dataclass(frozen=True, slots=True)
class DecompositionProposalInvocation(Generic[_ProposalT]):
    """One proposer result bound to the audited public view it actually received."""

    proposal: _ProposalT
    problem_view: DecompositionProblemView
    audit: DecompositionLeakageAudit


def build_decomposition_problem_view(
    *,
    task: TaskDefinition,
    tasks_root: Path,
    task_snapshot: TaskSnapshotRef,
    output_contract: OutputCompletionContract,
    harness: CompiledHarnessInstance,
    public_sources: tuple[PublicSourceBinding, ...],
    public_domain_id: str,
    public_task_family_id: str,
    data_gap_boundaries: tuple[PublicDataGapBoundary, ...] = (),
    authority_boundaries: tuple[PublicAuthorityBoundary, ...] = (),
) -> AuditedDecompositionProblemView:
    """Build a reward-blind proposer view only after every host-side leakage check passes."""
    root = Path(tasks_root).resolve()
    unresolved_task_dir = root / task.task_id
    task_dir = unresolved_task_dir.resolve()
    findings: set[str] = set()

    valid_task_dir = task_dir.is_relative_to(root) and task_dir.is_dir() and not unresolved_task_dir.is_symlink()
    if not valid_task_dir:
        findings.add("task_package_invalid")
    if valid_task_dir:
        _audit_package_markers(task_dir=task_dir, findings=findings)
    _audit_public_text(task.task_id, findings=findings)
    _audit_public_text(task.instruction, findings=findings)
    _audit_public_text(public_domain_id, findings=findings)
    _audit_public_text(public_task_family_id, findings=findings)
    _audit_public_text(
        json.dumps(output_contract.model_dump(mode="json"), sort_keys=True),
        findings=findings,
    )
    for data_gap_boundary in data_gap_boundaries:
        _audit_public_text(data_gap_boundary.boundary_id, findings=findings)
        _audit_public_text(data_gap_boundary.statement, findings=findings)
    for authority_boundary in authority_boundaries:
        _audit_public_text(
            authority_boundary.boundary_id,
            findings=findings,
            allow_public_authority_term=True,
        )
        _audit_public_text(
            authority_boundary.statement,
            findings=findings,
            allow_public_authority_term=True,
        )

    source_refs = (
        _load_public_sources(
            task_dir=task_dir,
            bindings=public_sources,
            findings=findings,
        )
        if valid_task_dir
        else ()
    )
    audited_input_sha256 = _audited_input_sha256(
        task=task,
        task_snapshot=task_snapshot,
        output_contract=output_contract,
        harness=harness,
        public_sources=public_sources,
        resolved_source_refs=source_refs,
        public_domain_id=public_domain_id,
        public_task_family_id=public_task_family_id,
        data_gap_boundaries=data_gap_boundaries,
        authority_boundaries=authority_boundaries,
    )
    exact_snapshot = (
        _validate_exact_snapshot(
            task=task,
            tasks_root=root,
            expected=task_snapshot,
            findings=findings,
        )
        if valid_task_dir
        else None
    )
    if valid_task_dir:
        _validate_output_contract(
            task=task,
            task_dir=task_dir,
            expected=output_contract,
            findings=findings,
        )
    capability_ids = _safe_harness_capability_ids(
        task_id=task.task_id,
        harness=harness,
        findings=findings,
    )

    if findings or exact_snapshot is None:
        raise DecompositionProblemViewRejected(
            _failed_audit(
                audited_input_sha256=audited_input_sha256,
                findings=findings or {"task_snapshot_mismatch"},
            )
        )

    fixed_harness = FixedHarnessCapabilityProjection(
        kernel_sha256=harness.kernel_ref.content_sha256,
        harness_policy_sha256=fixed_harness_policy_sha256(harness),
        capability_ids=capability_ids,
        aggregate_budget=harness.budget,
    )
    problem_view = DecompositionProblemView(
        problem_id=f"decomposition-problem.{task.task_id}.{audited_input_sha256[:12]}",
        task_id=task.task_id,
        task_revision=exact_snapshot.definition_sha256,
        public_task_snapshot_sha256=graph_hidden_task_snapshot_sha256(exact_snapshot),
        public_instruction=task.instruction,
        public_sources=source_refs,
        output_contract=output_contract,
        fixed_harness=fixed_harness,
        public_domain_id=public_domain_id,
        public_task_family_id=public_task_family_id,
        data_gap_boundaries=data_gap_boundaries,
        authority_boundaries=authority_boundaries,
    )
    audit = DecompositionLeakageAudit(
        audit_id=f"decomposition-leakage-audit.{audited_input_sha256[:16]}",
        audited_input_sha256=audited_input_sha256,
        audit_policy_sha256=_AUDIT_POLICY_SHA256,
        passed=True,
        finding_codes=(),
        problem_view_sha256=problem_view.content_sha256,
    )
    return AuditedDecompositionProblemView(problem_view=problem_view, audit=audit)


def invoke_decomposition_proposer(
    *,
    proposer: Callable[[DecompositionProblemView], _ProposalT],
    **build_kwargs: Any,
) -> DecompositionProposalInvocation[_ProposalT]:
    """Invoke a local or provider proposer only after the public view passes host audit."""
    built = build_decomposition_problem_view(**build_kwargs)
    proposal = proposer(built.problem_view)
    return DecompositionProposalInvocation(
        proposal=proposal,
        problem_view=built.problem_view,
        audit=built.audit,
    )


def _audit_package_markers(*, task_dir: Path, findings: set[str]) -> None:
    if any((task_dir / sidecar).exists() for sidecar in TASK_WORLD_SIDECARS):
        findings.add("task_world_sidecar")
    present_composite_markers = tuple(marker for marker in _COMPOSITE_MARKERS if (task_dir / marker).exists())
    if present_composite_markers:
        findings.add("composite_materializer_package")
    if (task_dir / "template.json").exists():
        findings.add("nested_metadata")
    if (task_dir / "agent" / "structured_answer.json").exists():
        findings.add("ready_made_answer")


def _load_public_sources(
    *,
    task_dir: Path,
    bindings: tuple[PublicSourceBinding, ...],
    findings: set[str],
) -> tuple[PublicSourceRef, ...]:
    source_ids = tuple(binding.source_id for binding in bindings)
    if not bindings or len(source_ids) != len(set(source_ids)):
        findings.add("public_source_binding_invalid")

    refs: list[PublicSourceRef] = []
    for binding in bindings:
        _audit_public_text(binding.source_id, findings=findings)
        _audit_public_text(binding.relative_path, findings=findings)
        _audit_public_text(binding.media_type, findings=findings)
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", binding.source_id) is None:
            findings.add("public_source_binding_invalid")
            continue
        relative = PurePosixPath(binding.relative_path)
        if _forbidden_source_path(relative):
            findings.add("forbidden_source_path")
            continue
        candidate = task_dir / relative
        if _contains_symlink(task_dir=task_dir, relative=relative):
            findings.add("forbidden_source_path")
            continue
        resolved = candidate.resolve()
        if not resolved.is_relative_to(task_dir) or not resolved.is_file():
            findings.add("forbidden_source_path")
            continue
        try:
            content = resolved.read_bytes()
        except OSError:
            findings.add("public_source_not_auditable")
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            findings.add("public_source_not_auditable")
            continue
        _audit_public_text(text, findings=findings)
        source_sha256 = hashlib.sha256(content).hexdigest()
        refs.append(
            PublicSourceRef(
                source_id=binding.source_id,
                opaque_handle=f"public-source:{binding.source_id}:{source_sha256[:16]}",
                media_type=binding.media_type,
                byte_size=len(content),
                source_sha256=source_sha256,
            )
        )
    return tuple(sorted(refs, key=lambda source: source.source_id))


def _contains_symlink(*, task_dir: Path, relative: PurePosixPath) -> bool:
    current = task_dir
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def _forbidden_source_path(relative: PurePosixPath) -> bool:
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        return True
    lowered_parts = tuple(part.lower() for part in relative.parts)
    if any(part in _FORBIDDEN_SOURCE_PARTS for part in lowered_parts):
        return True
    lowered_name = lowered_parts[-1]
    return lowered_name in _FORBIDDEN_SOURCE_NAMES or any(
        token in lowered_name
        for token in (
            "expected_answer",
            "ground_truth",
            "oracle",
            "ready_made",
            "structured_answer",
            "verifier",
        )
    )


def _validate_exact_snapshot(
    *,
    task: TaskDefinition,
    tasks_root: Path,
    expected: TaskSnapshotRef,
    findings: set[str],
) -> TaskSnapshotRef | None:
    try:
        actual = build_task_snapshot(task=task, tasks_root=tasks_root)
    except (OSError, TaskSnapshotError, ValueError):
        findings.add("task_snapshot_mismatch")
        return None
    if actual != expected or actual.world is not None:
        findings.add("task_snapshot_mismatch")
        return None
    return actual


def _validate_output_contract(
    *,
    task: TaskDefinition,
    task_dir: Path,
    expected: OutputCompletionContract,
    findings: set[str],
) -> None:
    path = task_dir / "environment" / "output_contract.json"
    try:
        actual = OutputCompletionContract.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        findings.add("output_contract_mismatch")
        return
    if actual != expected or actual.output_path != task.verifier.expected_output_path:
        findings.add("output_contract_mismatch")


def _safe_harness_capability_ids(
    *,
    task_id: str,
    harness: CompiledHarnessInstance,
    findings: set[str],
) -> tuple[str, ...]:
    task_refs = {
        task_ref
        for binding in harness.bindings
        if isinstance(binding.configuration, TaskSourceBindingConfig)
        for task_ref in binding.configuration.task_refs
    }
    if task_id not in task_refs:
        findings.add("harness_task_binding_mismatch")
    operations = tuple(
        operation
        for operation in harness.program_surface.operations
        if not operation.allowed_task_refs or task_id in operation.allowed_task_refs
    )
    if not operations:
        findings.add("harness_capability_projection_empty")
    capability_ids = tuple(sorted(operation.operation_id for operation in operations))
    for capability_id in capability_ids:
        if re.search(
            r"critic|accept|verif|world|graph|topolog|handoff|route|gold|oracle|expected|metadata",
            capability_id,
            re.IGNORECASE,
        ):
            findings.add("harness_capability_projection_unsafe")
    return capability_ids


def fixed_harness_policy_sha256(harness: CompiledHarnessInstance) -> str:
    """Hash complete H0 semantics while replacing only task identities with a placeholder."""
    normalized_bindings: list[dict[str, Any]] = []
    for binding in sorted(harness.bindings, key=lambda item: item.binding_id):
        configuration = binding.configuration.model_dump(mode="json")
        if isinstance(binding.configuration, TaskSourceBindingConfig):
            configuration["task_refs"] = ["<task>"]
        normalized_bindings.append(
            {
                "binding_id": binding.binding_id,
                "capability_ref": binding.capability_ref.model_dump(mode="json"),
                "capability_kind": binding.capability_kind.value,
                "depends_on": list(binding.depends_on),
                "topology_role": binding.topology_role.value,
                "contract_ids": list(binding.contract_ids),
                "configuration": configuration,
            }
        )

    normalized_operations: list[dict[str, Any]] = []
    for operation in sorted(
        harness.program_surface.operations,
        key=lambda item: item.operation_id,
    ):
        payload = operation.model_dump(mode="json", exclude={"content_sha256"})
        payload["allowed_task_refs"] = ["<task>"] if operation.allowed_task_refs else []
        normalized_operations.append(payload)

    return canonical_content_sha256(
        {
            "schema_version": "aecbench.fixed-harness-policy.v1",
            "kernel_ref": harness.kernel_ref.model_dump(mode="json"),
            "contracts": [
                contract.model_dump(mode="json", exclude={"content_sha256"})
                for contract in sorted(
                    harness.contracts,
                    key=lambda item: item.contract_id,
                )
            ],
            "budget": harness.budget.model_dump(mode="json"),
            "recursion_policy": harness.recursion_policy.model_dump(mode="json"),
            "bindings": normalized_bindings,
            "program_surface": {
                "surface_id": harness.program_surface.surface_id,
                "operations": normalized_operations,
            },
            "compatibility_notes": list(harness.compatibility_notes),
        }
    )


def _audit_public_text(
    value: str,
    *,
    findings: set[str],
    allow_public_authority_term: bool = False,
) -> None:
    for code, pattern in _TEXT_FINDING_PATTERNS:
        if code == "authority_policy" and allow_public_authority_term:
            continue
        if pattern.search(value):
            findings.add(code)


def _failed_audit(
    *,
    audited_input_sha256: str,
    findings: set[str],
) -> DecompositionLeakageAudit:
    return DecompositionLeakageAudit(
        audit_id=f"decomposition-leakage-audit.{audited_input_sha256[:16]}",
        audited_input_sha256=audited_input_sha256,
        audit_policy_sha256=_AUDIT_POLICY_SHA256,
        passed=False,
        finding_codes=tuple(sorted(findings)),
        problem_view_sha256=None,
    )


def _audited_input_sha256(
    *,
    task: TaskDefinition,
    task_snapshot: TaskSnapshotRef,
    output_contract: OutputCompletionContract,
    harness: CompiledHarnessInstance,
    public_sources: tuple[PublicSourceBinding, ...],
    resolved_source_refs: tuple[PublicSourceRef, ...],
    public_domain_id: str,
    public_task_family_id: str,
    data_gap_boundaries: tuple[PublicDataGapBoundary, ...],
    authority_boundaries: tuple[PublicAuthorityBoundary, ...],
) -> str:
    return canonical_content_sha256(
        {
            "task_definition_sha256": canonical_content_sha256(task.model_dump(mode="json")),
            "task_snapshot": task_snapshot.model_dump(mode="json"),
            "output_contract": output_contract.model_dump(mode="json"),
            "compiled_harness_sha256": harness.content_sha256,
            "public_sources": [
                {
                    "source_id": binding.source_id,
                    "relative_path_sha256": hashlib.sha256(binding.relative_path.encode("utf-8")).hexdigest(),
                    "media_type": binding.media_type,
                }
                for binding in sorted(public_sources, key=lambda item: item.source_id)
            ],
            "resolved_public_sources": [
                source.model_dump(mode="json", exclude={"content_sha256"}) for source in resolved_source_refs
            ],
            "public_domain_id": public_domain_id,
            "public_task_family_id": public_task_family_id,
            "data_gap_boundaries": [
                boundary.model_dump(mode="json", exclude={"content_sha256"}) for boundary in data_gap_boundaries
            ],
            "authority_boundaries": [
                boundary.model_dump(mode="json", exclude={"content_sha256"}) for boundary in authority_boundaries
            ],
            "audit_policy_sha256": _AUDIT_POLICY_SHA256,
        }
    )
