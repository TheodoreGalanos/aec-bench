# ABOUTME: Defines the staged structural facade submittal review lifecycle.
# ABOUTME: Reuses the existing facade template calculations with task-owned releases and verification.

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator

from aec_bench.contracts.evidence_lifecycle import (
    EvidenceCheckpointSpec,
    EvidenceLifecycleSpec,
    LifecycleTaskMetadata,
)
from aec_bench.contracts.lifecycle_evaluation import LifecycleGateResult, LifecycleVerificationResult
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.lifecycles.runtime.lifecycle import load_validated_lifecycle_submissions
from aec_bench.templates.builtin.structural.facade_submittal_source_policy_package import (
    engine as facade_submittal_engine,
)

TEMPLATE_ID = "facade-submittal-review-lifecycle"
LIFECYCLE_ID = "facade-submittal-review"
SOURCE_TEMPLATE_ID = "facade-submittal-source-policy-package"
CHECKPOINT_IDS = ("source_review", "comment_review", "response_review")
GATE_IDS = (
    "checkpoint_contract",
    "evidence_use",
    "metric_accuracy",
    "finding_continuity",
    "review_decision",
    "claim_boundary",
)

METADATA = LifecycleTaskMetadata(
    template_id=TEMPLATE_ID,
    name="Facade Submittal Review Lifecycle",
    discipline="structural",
)

_REQUIRED_SUBMISSION_FIELDS = [
    "checkpoint_id",
    "evidence_refs",
    "metrics",
    "findings",
    "review_decision",
    "readiness",
    "claim_boundary",
]

LIFECYCLE = EvidenceLifecycleSpec(
    lifecycle_id=LIFECYCLE_ID,
    checkpoints=[
        EvidenceCheckpointSpec(
            checkpoint_id="source_review",
            title="Source, calculation, and material review",
            release_path="releases/source_review",
            instruction_path="instructions/source_review.md",
            submission_path="submissions/source_review.json",
            required_submission_fields=_REQUIRED_SUBMISSION_FIELDS,
            allow_additional_submission_fields=False,
        ),
        EvidenceCheckpointSpec(
            checkpoint_id="comment_review",
            title="Comment and boundary-exception review",
            release_path="releases/comment_review",
            instruction_path="instructions/comment_review.md",
            submission_path="submissions/comment_review.json",
            depends_on=["source_review"],
            required_submission_fields=_REQUIRED_SUBMISSION_FIELDS,
            allow_additional_submission_fields=False,
        ),
        EvidenceCheckpointSpec(
            checkpoint_id="response_review",
            title="Final submittal response review",
            release_path="releases/response_review",
            instruction_path="instructions/response_review.md",
            submission_path="submissions/response_review.json",
            depends_on=["comment_review"],
            required_submission_fields=_REQUIRED_SUBMISSION_FIELDS,
            allow_additional_submission_fields=False,
        ),
    ],
)


class FacadeClaimBoundary(StrictModel):
    evidence_class: Literal["task_owned_synthetic_review"]
    authority_status: Literal["no_authority_approval"]
    project_evidence_status: Literal["not_project_evidence"]
    standards_status: Literal["no_standards_compliance_claim"]


class FacadeReviewFinding(StrictModel):
    finding_id: NonEmptyStr
    status: Literal["open", "closed"]
    evidence_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("finding evidence references must be unique")
        return value


class FacadeReviewSubmission(StrictModel):
    checkpoint_id: Literal["source_review", "comment_review", "response_review"]
    evidence_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    metrics: dict[NonEmptyStr, float] = Field(min_length=1)
    findings: tuple[FacadeReviewFinding, ...]
    review_decision: Literal["continue_review", "technical_acceptance_with_open_gaps"]
    readiness: Literal["review_in_progress", "not_ready_to_close"]
    claim_boundary: FacadeClaimBoundary

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("submission evidence references must be unique")
        return value

    @field_validator("findings")
    @classmethod
    def validate_finding_ids(cls, value: tuple[FacadeReviewFinding, ...]) -> tuple[FacadeReviewFinding, ...]:
        finding_ids = [finding.finding_id for finding in value]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("finding ids must be unique")
        return value


class FacadePhaseEvidence(StrictModel):
    phase_id: NonEmptyStr
    checkpoint_ids: tuple[NonEmptyStr, ...]
    phase_outcome: NonEmptyStr
    evidence_refs_cited: int = Field(ge=0)
    evidence_refs_expected: int | None = Field(default=None, ge=0)
    metric_accuracy_pass: bool
    finding_continuity_pass: bool
    review_decision_correct: bool


class FacadeLearningEvidence(StrictModel):
    evidence_schema: str = "aec-bench/lifecycle/facade/learning-evidence/1"
    lifecycle_template_id: NonEmptyStr
    phase_records: tuple[FacadePhaseEvidence, ...]


def extract_facade_learning_evidence(record: TrialRecord) -> FacadeLearningEvidence | None:
    """Extract phase evidence from one completed facade lifecycle record."""

    try:
        if record.task_id != f"lifecycle/{TEMPLATE_ID}":
            return None
        if record.evaluation is None or not record.evaluation.validity.verifier_completed:
            return None
        gates = _facade_phase_evidence_gates(record.evaluation.breakdown)
        submissions = _facade_phase_evidence_submissions(record)
        phase_records = (
            _facade_phase(
                phase_id="source_assessment",
                checkpoint_ids=("source_review",),
                submissions=submissions,
                gates=gates,
                gate_ids=("checkpoint_contract", "evidence_use", "metric_accuracy"),
            ),
            _facade_phase(
                phase_id="review_and_response",
                checkpoint_ids=("comment_review", "response_review"),
                submissions=submissions,
                gates=gates,
                gate_ids=("finding_continuity", "review_decision", "claim_boundary"),
            ),
        )
        return FacadeLearningEvidence(
            lifecycle_template_id=TEMPLATE_ID,
            phase_records=phase_records,
        )
    except (TypeError, ValueError, KeyError, ValidationError, json.JSONDecodeError):
        return None


def _facade_phase(
    *,
    phase_id: str,
    checkpoint_ids: tuple[str, ...],
    submissions: dict[str, FacadeReviewSubmission],
    gates: dict[str, dict[str, Any]],
    gate_ids: tuple[str, ...],
) -> FacadePhaseEvidence:
    phase_gates = {gate_id: gates[gate_id]["passed"] for gate_id in gate_ids}
    return FacadePhaseEvidence(
        phase_id=phase_id,
        checkpoint_ids=checkpoint_ids,
        phase_outcome="complete" if all(phase_gates.values()) else "incomplete",
        evidence_refs_cited=sum(len(submissions[checkpoint_id].evidence_refs) for checkpoint_id in checkpoint_ids),
        # The facade verifier does not retain expected reference counts in the
        # TrialRecord; leaving this optional is the fail-closed representation.
        evidence_refs_expected=None,
        metric_accuracy_pass=gates["metric_accuracy"]["passed"],
        finding_continuity_pass=gates["finding_continuity"]["passed"],
        review_decision_correct=gates["review_decision"]["passed"],
    )


def _facade_phase_evidence_gates(breakdown: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(breakdown, dict) or not isinstance(breakdown.get("lifecycle_gates"), dict):
        raise ValueError("phase-evidence-extraction-failed: lifecycle gates are unavailable")
    gates = breakdown["lifecycle_gates"]
    selected: dict[str, dict[str, Any]] = {}
    for gate_id in GATE_IDS:
        gate = gates.get(gate_id)
        if not isinstance(gate, dict) or not isinstance(gate.get("passed"), bool):
            raise ValueError("phase-evidence-extraction-failed: lifecycle gate is malformed")
        score = gate.get("score")
        if isinstance(score, bool) or not isinstance(score, int | float) or not 0 <= score <= 1:
            raise ValueError("phase-evidence-extraction-failed: lifecycle gate score is malformed")
        selected[gate_id] = gate
    return selected


def _facade_phase_evidence_submissions(record: TrialRecord) -> dict[str, FacadeReviewSubmission]:
    output = record.output
    agent_output = None if output is None else output.agent_output
    if agent_output is None:
        raise ValueError("phase-evidence-extraction-failed: lifecycle run is unavailable")
    run_dir = Path(agent_output.output_path)
    if not run_dir.is_absolute() or not run_dir.is_dir() or run_dir.is_symlink():
        raise ValueError("phase-evidence-extraction-failed: lifecycle run is unavailable")
    run_dir = run_dir.resolve(strict=True)
    submissions: dict[str, FacadeReviewSubmission] = {}
    for checkpoint_id in CHECKPOINT_IDS:
        path = run_dir / "episodes" / checkpoint_id / "submission.json"
        if not path.is_file() or path.is_symlink():
            raise ValueError("phase-evidence-extraction-failed: checkpoint submission is unavailable")
        payload = json.loads(path.read_text(encoding="utf-8"))
        submission = FacadeReviewSubmission.model_validate(payload)
        if submission.checkpoint_id != checkpoint_id:
            raise ValueError("phase-evidence-extraction-failed: checkpoint identity is invalid")
        submissions[checkpoint_id] = submission
    return submissions


def materialize_facade_submittal_lifecycle(output_dir: Path) -> Path:
    """Write one deterministic structural facade review lifecycle package."""
    output = Path(output_dir)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"output directory must be empty: {output}")
    for relative_path, content in _expected_package_files().items():
        path = output / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return output


def validated_facade_submittal_package(package_dir: Path) -> dict[str, Any]:
    """Validate exact task-owned package contents against the current source template."""
    package = Path(package_dir)
    expected = _expected_package_files()
    actual_paths = {path.relative_to(package).as_posix() for path in package.rglob("*") if path.is_file()}
    if actual_paths != set(expected):
        raise ValueError("facade submittal lifecycle package inventory does not match the current task")
    for relative_path, content in expected.items():
        if (package / relative_path).read_text(encoding="utf-8") != content:
            raise ValueError(f"facade submittal lifecycle package content differs: {relative_path}")
    return {
        "source_template_id": SOURCE_TEMPLATE_ID,
        "checkpoint_ids": list(CHECKPOINT_IDS),
    }


def verify_facade_submittal_lifecycle(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Verify metric use, finding continuity, and honest closeout from accepted evidence."""
    package = Path(package_dir)
    validated_facade_submittal_package(package)
    expected = _gold_submissions()
    raw = load_validated_lifecycle_submissions(package, Path(run_dir))

    actual: dict[str, FacadeReviewSubmission] = {}
    contract_failures: list[str] = []
    for checkpoint_id in CHECKPOINT_IDS:
        try:
            submission = FacadeReviewSubmission.model_validate(raw[checkpoint_id])
        except (KeyError, ValidationError) as exc:
            contract_failures.append(f"{checkpoint_id}:{exc}")
            continue
        if submission.checkpoint_id != checkpoint_id:
            contract_failures.append(f"{checkpoint_id}:checkpoint_id")
            continue
        actual[checkpoint_id] = submission

    if contract_failures:
        gates = {
            gate_id: _gate(contract_failures if gate_id == "checkpoint_contract" else ["contract_unavailable"])
            for gate_id in GATE_IDS
        }
        return _verification(gates)

    expected_models = {
        checkpoint_id: FacadeReviewSubmission.model_validate(payload) for checkpoint_id, payload in expected.items()
    }
    gates = {
        "checkpoint_contract": _gate([]),
        "evidence_use": _comparison_gate(actual, expected_models, "evidence_refs"),
        "metric_accuracy": _comparison_gate(actual, expected_models, "metrics"),
        "finding_continuity": _comparison_gate(actual, expected_models, "findings"),
        "review_decision": _decision_gate(actual, expected_models),
        "claim_boundary": _comparison_gate(actual, expected_models, "claim_boundary"),
    }
    return _verification(gates)


def _comparison_gate(
    actual: dict[str, FacadeReviewSubmission],
    expected: dict[str, FacadeReviewSubmission],
    field_name: str,
) -> LifecycleGateResult:
    failures = [
        f"{checkpoint_id}.{field_name}"
        for checkpoint_id in CHECKPOINT_IDS
        if getattr(actual[checkpoint_id], field_name) != getattr(expected[checkpoint_id], field_name)
    ]
    return _gate(failures)


def _decision_gate(
    actual: dict[str, FacadeReviewSubmission],
    expected: dict[str, FacadeReviewSubmission],
) -> LifecycleGateResult:
    failures: list[str] = []
    for checkpoint_id in CHECKPOINT_IDS:
        if actual[checkpoint_id].review_decision != expected[checkpoint_id].review_decision:
            failures.append(f"{checkpoint_id}.review_decision")
        if actual[checkpoint_id].readiness != expected[checkpoint_id].readiness:
            failures.append(f"{checkpoint_id}.readiness")
    return _gate(failures)


def _verification(gates: dict[str, LifecycleGateResult]) -> dict[str, Any]:
    passed = all(gate.passed for gate in gates.values())
    result = LifecycleVerificationResult(
        template_id=TEMPLATE_ID,
        lifecycle_id=LIFECYCLE_ID,
        overall="pass" if passed else "fail",
        passed=passed,
        reward=round(sum(gate.score for gate in gates.values()) / len(gates), 4),
        gates=gates,
    )
    return result.model_dump(mode="json", exclude={"semantic_metrics"})


def _gate(failures: list[str]) -> LifecycleGateResult:
    unique = sorted(set(failures))
    return LifecycleGateResult(passed=not unique, score=0.0 if unique else 1.0, failures=unique)


def _expected_package_files() -> dict[str, str]:
    source_values = _source_values()
    metrics = _expected_metrics(source_values)
    files = {
        "template.json": _json_text(METADATA.model_dump(mode="json")),
        "lifecycle.json": _json_text(LIFECYCLE.model_dump(mode="json")),
        "README.md": _readme(),
        "hidden/source-template.json": _json_text(
            {
                "source_template_id": SOURCE_TEMPLATE_ID,
                "source_values": source_values,
            }
        ),
        "hidden/gold-submissions.json": _json_text(_gold_submissions(metrics)),
    }
    files.update({f"instructions/{checkpoint_id}.md": content for checkpoint_id, content in _instructions().items()})
    files.update({f"releases/{path}": _json_text(payload) for path, payload in _releases(source_values).items()})
    return files


def _source_values() -> dict[str, float]:
    template_dir = Path(facade_submittal_engine.__file__).resolve().parent
    with (template_dir / "params.toml").open("rb") as stream:
        source = tomllib.load(stream)
    raw_params = source.get("params")
    if not isinstance(raw_params, dict):
        raise ValueError("facade source template has no parameter definitions")
    values: dict[str, float] = {}
    for name, raw_spec in raw_params.items():
        if not isinstance(raw_spec, dict):
            raise ValueError(f"facade source parameter is invalid: {name}")
        minimum = raw_spec.get("min")
        maximum = raw_spec.get("max")
        if not isinstance(minimum, int | float) or minimum != maximum:
            raise ValueError(f"facade lifecycle requires one fixed source value: {name}")
        values[name] = float(minimum)
    return values


def _expected_metrics(source_values: dict[str, float]) -> dict[str, float]:
    metrics = facade_submittal_engine.compute(**source_values)
    return {key: float(value) for key, value in metrics.items()}


def _releases(source: dict[str, float]) -> dict[str, dict[str, Any]]:
    return {
        "source_review/source-index.json": {
            "document_id": "facade-source-index",
            "source_items_traced": source["source_items_traced"],
            "required_source_items": source["required_source_items"],
            "boundary_exceptions": source["boundary_exceptions"],
        },
        "source_review/facade-elevation.json": {
            "document_id": "facade-elevation",
            "revision": "review-issue",
            "purpose": "source and calculation cross-check",
        },
        "source_review/calculation-report.json": {
            "document_id": "facade-calculation-report",
            "calculator_rows_checked": source["calculator_rows_checked"],
            "required_calculator_rows": source["required_calculator_rows"],
            "passing_utilization_rows": source["passing_utilization_rows"],
            "utilization_rows": source["utilization_rows"],
        },
        "source_review/material-schedule.json": {
            "document_id": "facade-material-schedule",
            "matching_material_items": source["matching_material_items"],
            "material_schedule_items": source["material_schedule_items"],
            "unapproved_substitution_count": source["unapproved_substitution_count"],
        },
        "comment_review/comment-register.json": {
            "document_id": "facade-comment-register",
            "resolved_comments": source["resolved_comments"],
            "review_comments": source["review_comments"],
        },
        "comment_review/boundary-exception-register.json": {
            "document_id": "facade-boundary-exception-register",
            "approved_boundary_exceptions": source["approved_boundary_exceptions"],
            "boundary_exceptions": source["boundary_exceptions"],
        },
        "response_review/submittal-response.json": {
            "document_id": "facade-submittal-response",
            "response_sections": source["response_sections"],
            "required_response_sections": source["required_response_sections"],
        },
    }


def _gold_submissions(metrics: dict[str, float] | None = None) -> dict[str, dict[str, Any]]:
    expected_metrics = metrics if metrics is not None else _expected_metrics(_source_values())
    claim_boundary = FacadeClaimBoundary(
        evidence_class="task_owned_synthetic_review",
        authority_status="no_authority_approval",
        project_evidence_status="not_project_evidence",
        standards_status="no_standards_compliance_claim",
    )
    source_refs = (
        "facade-source-index",
        "facade-elevation",
        "facade-calculation-report",
        "facade-material-schedule",
    )
    comment_refs = source_refs + ("facade-comment-register", "facade-boundary-exception-register")
    response_refs = comment_refs + ("facade-submittal-response",)
    source_findings = (
        FacadeReviewFinding(
            finding_id="source-trace-gap",
            status="open",
            evidence_refs=("facade-source-index",),
        ),
        FacadeReviewFinding(
            finding_id="material-match-gap",
            status="open",
            evidence_refs=("facade-material-schedule",),
        ),
    )
    comment_findings = source_findings + (
        FacadeReviewFinding(
            finding_id="comment-closeout-gap",
            status="open",
            evidence_refs=("facade-comment-register",),
        ),
    )
    response_findings = comment_findings + (
        FacadeReviewFinding(
            finding_id="response-completeness-gap",
            status="open",
            evidence_refs=("facade-submittal-response",),
        ),
    )
    metric_keys = {
        "source_review": (
            "source_trace_score",
            "calculator_check_fraction",
            "material_match_fraction",
            "utilization_pass_fraction",
            "unapproved_substitution_count",
        ),
        "comment_review": (
            "source_trace_score",
            "calculator_check_fraction",
            "material_match_fraction",
            "utilization_pass_fraction",
            "comment_resolution_fraction",
            "boundary_exception_resolution_fraction",
            "unapproved_substitution_count",
        ),
        "response_review": tuple(expected_metrics),
    }
    submissions = {
        "source_review": FacadeReviewSubmission(
            checkpoint_id="source_review",
            evidence_refs=source_refs,
            metrics={key: expected_metrics[key] for key in metric_keys["source_review"]},
            findings=source_findings,
            review_decision="continue_review",
            readiness="review_in_progress",
            claim_boundary=claim_boundary,
        ),
        "comment_review": FacadeReviewSubmission(
            checkpoint_id="comment_review",
            evidence_refs=comment_refs,
            metrics={key: expected_metrics[key] for key in metric_keys["comment_review"]},
            findings=comment_findings,
            review_decision="continue_review",
            readiness="review_in_progress",
            claim_boundary=claim_boundary,
        ),
        "response_review": FacadeReviewSubmission(
            checkpoint_id="response_review",
            evidence_refs=response_refs,
            metrics={key: expected_metrics[key] for key in metric_keys["response_review"]},
            findings=response_findings,
            review_decision="technical_acceptance_with_open_gaps",
            readiness="not_ready_to_close",
            claim_boundary=claim_boundary,
        ),
    }
    return {checkpoint_id: submission.model_dump(mode="json") for checkpoint_id, submission in submissions.items()}


def _instructions() -> dict[str, str]:
    purposes = {
        "source_review": "Review the source index, calculation report, facade elevation, and material schedule.",
        "comment_review": "Review the newly released comment and boundary-exception registers.",
        "response_review": "Review the final submittal response and record the closeout position.",
    }
    return {checkpoint_id: _instruction(checkpoint_id, purpose) for checkpoint_id, purpose in purposes.items()}


def _instruction(checkpoint_id: str, purpose: str) -> str:
    return f"""# Facade Submittal Review

{purpose}

Use only evidence currently visible in the lifecycle workspace and immutable prior submissions. Keep prior open
findings unless later evidence closes them. Calculate only metrics supported by released evidence.

Write `submissions/{checkpoint_id}.json` with exactly these fields:

- `checkpoint_id`
- cumulative `evidence_refs`
- cumulative `metrics`
- cumulative `findings` with stable IDs
- `review_decision`
- `readiness`
- `claim_boundary`

This is a task-owned synthetic review. Do not claim authority approval, accepted project evidence, or standards
compliance. Lifecycle completion means the review is recorded; it does not mean the submittal is ready to close.
"""


def _readme() -> str:
    return """# Facade Submittal Review Lifecycle

This structural lifecycle releases source, comment, and response evidence in three host-controlled checkpoints.
It reuses the calculations from the existing facade submittal source-policy template. The task verifier grades
accepted lifecycle evidence after progression completes.
"""


def _json_text(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
