# ABOUTME: Materializes and verifies the SSC-03 drainage model evidence-lifecycle companion.
# ABOUTME: Defines three synthetic releases, cumulative gold states, and continuity-focused gates.

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from aec_bench.meta_harness.evidence_lifecycle import load_validated_lifecycle_submissions
from aec_bench.meta_harness.evidence_lifecycle_metrics import score_semantic_transitions
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.contracts import CompositeTaskWorldTemplate

CHECKPOINT_IDS = ("initial_review", "response_review", "closeout_review")
GATE_IDS = (
    "checkpoint_contract",
    "reviewer_self_consistency",
    "staged_disclosure",
    "finding_continuity",
    "closure_evidence",
    "accepted_decision_preservation",
    "final_readiness",
    "claim_boundary",
)


def materialize_ssc03_evidence_lifecycle(
    output_dir: Path,
    *,
    template: CompositeTaskWorldTemplate | None = None,
) -> Path:
    """Write the runnable three-release SSC-03 lifecycle package."""
    output = Path(output_dir)
    template = template or get_template("drainage-model-evidence-lifecycle-review")
    if template.template_id != "drainage-model-evidence-lifecycle-review":
        raise ValueError(f"unexpected SSC-03 lifecycle template: {template.template_id}")
    if template.evidence_lifecycle is None:
        raise ValueError("SSC-03 lifecycle template is missing its evidence_lifecycle contract")

    _write_json(output / "template.json", template.model_dump(mode="json"))
    _write_json(output / "world.json", template.compile_task_world_payload())
    _write_json(output / "lifecycle.json", template.evidence_lifecycle.model_dump(mode="json"))
    (output / "README.md").parent.mkdir(parents=True, exist_ok=True)
    (output / "README.md").write_text(_readme(), encoding="utf-8")

    for checkpoint_id, instruction in _instructions().items():
        path = output / "instructions" / f"{checkpoint_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(instruction, encoding="utf-8")
    for checkpoint_id, files in _releases().items():
        for relative_path, content in files.items():
            path = output / "releases" / checkpoint_id / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    _write_json(output / "hidden" / "gold-submissions.json", _gold_submissions())
    _write_json(
        output / "hidden" / "verifier-config.json",
        {
            "allowed_evidence_refs": _allowed_evidence_refs(),
            "decision_evidence_policy": _decision_evidence_policy(),
            "closure_request_policy": _closure_request_policy(),
        },
    )
    return output


def verify_ssc03_evidence_lifecycle(package_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Grade checkpoint state and continuity without requiring exact review prose."""
    package = Path(package_dir)
    run = Path(run_dir)
    expected = _read_json(package / "hidden" / "gold-submissions.json")
    config = _read_json(package / "hidden" / "verifier-config.json")
    actual = load_validated_lifecycle_submissions(package, run)

    gates = {
        "checkpoint_contract": _checkpoint_contract_gate(expected, actual),
        "reviewer_self_consistency": _reviewer_self_consistency_gate(actual),
        "staged_disclosure": _staged_disclosure_gate(config, actual),
        "finding_continuity": _finding_continuity_gate(expected, actual),
        "closure_evidence": _closure_evidence_gate(config, expected, actual),
        "accepted_decision_preservation": _accepted_decision_gate(config, expected, actual),
        "final_readiness": _final_readiness_gate(expected, actual),
        "claim_boundary": _claim_boundary_gate(actual),
    }
    reward = round(sum(float(gate["score"]) for gate in gates.values()) / len(gates), 4)
    passed = all(bool(gate["passed"]) for gate in gates.values())
    semantic_metrics = score_semantic_transitions(
        checkpoint_ids=CHECKPOINT_IDS,
        expected={checkpoint_id: _semantic_atoms(expected[checkpoint_id]) for checkpoint_id in CHECKPOINT_IDS},
        actual={checkpoint_id: _semantic_atoms(actual[checkpoint_id]) for checkpoint_id in CHECKPOINT_IDS},
    )
    return {
        "template_id": "drainage-model-evidence-lifecycle-review",
        "lifecycle_id": "ssc03.drainage-model-evidence-lifecycle",
        "overall": "pass" if passed else "fail",
        "passed": passed,
        "reward": reward,
        "gates": gates,
        "semantic_metrics": semantic_metrics.model_dump(mode="json"),
    }


def _checkpoint_contract_gate(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    checks = 0
    for checkpoint_id in CHECKPOINT_IDS:
        checks += 1
        if actual[checkpoint_id].get("checkpoint_id") != expected[checkpoint_id].get("checkpoint_id"):
            failures.append(f"{checkpoint_id}.checkpoint_id")
        for item in (f"PRV-0{index}" for index in range(1, 8)):
            checks += 1
            if actual[checkpoint_id].get("review_matrix", {}).get(item) != expected[checkpoint_id]["review_matrix"].get(
                item
            ):
                failures.append(f"{checkpoint_id}.review_matrix.{item}")
        for field in ("model_run", "model_report", "design_claim"):
            checks += 1
            if actual[checkpoint_id].get("transition_decision", {}).get(field) != expected[checkpoint_id][
                "transition_decision"
            ].get(field):
                failures.append(f"{checkpoint_id}.transition_decision.{field}")
        checks += 1
        if actual[checkpoint_id].get("readiness_decision") != expected[checkpoint_id].get("readiness_decision"):
            failures.append(f"{checkpoint_id}.readiness_decision")
    return _gate(failures, checks)


def _reviewer_self_consistency_gate(actual: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failures = []
    for checkpoint_id in CHECKPOINT_IDS:
        checkpoint = actual[checkpoint_id]
        expected_status = "pass" if _submitted_state_is_consistent(checkpoint) else "fail"
        if checkpoint.get("review_matrix", {}).get("PRV-08") != expected_status:
            failures.append(f"{checkpoint_id}.PRV-08")
    return _gate(failures, len(CHECKPOINT_IDS))


def _submitted_state_is_consistent(checkpoint: dict[str, Any]) -> bool:
    matrix = checkpoint.get("review_matrix", {})
    run_status = _governing_status(matrix, ("PRV-02", "PRV-03", "PRV-05"))
    report_status = _downstream_status(run_status, matrix.get("PRV-04"), positive="governing")
    claim_status = _downstream_status(report_status, matrix.get("PRV-06"), positive="supported")
    open_findings = any(
        isinstance(finding, dict) and finding.get("status") == "open" for finding in checkpoint.get("findings", [])
    )
    ready = (
        all(matrix.get(f"PRV-0{index}") == "pass" for index in range(1, 8))
        and (run_status, report_status, claim_status) == ("governing", "governing", "supported")
        and not open_findings
    )
    expected_readiness = "ready_to_issue" if ready else "not_ready_to_issue"
    return (
        checkpoint.get("transition_decision")
        == {
            "model_run": run_status,
            "model_report": report_status,
            "design_claim": claim_status,
        }
        and checkpoint.get("readiness_decision") == expected_readiness
    )


def _governing_status(matrix: dict[str, Any], items: tuple[str, ...]) -> str:
    states = [matrix.get(item) for item in items]
    if any(state in {"insufficient_data", "not_applicable", None} for state in states):
        return "insufficient_data"
    return "governing" if all(state == "pass" for state in states) else "non_governing"


def _downstream_status(upstream: str, item_status: Any, *, positive: str) -> str:
    if upstream == "insufficient_data" or item_status in {"insufficient_data", "not_applicable", None}:
        return "insufficient_data"
    if upstream != "governing" or item_status != "pass":
        return "unsupported" if positive == "supported" else "non_governing"
    return positive


def _staged_disclosure_gate(config: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    allowed = config["allowed_evidence_refs"]
    failures = []
    checks = 0
    for checkpoint_id in CHECKPOINT_IDS:
        references, malformed = _reference_set(actual[checkpoint_id].get("evidence_refs"))
        checks += 1 + len(references)
        if malformed:
            failures.append(f"{checkpoint_id}:evidence_refs_shape")
        premature = sorted(references - set(allowed[checkpoint_id]))
        failures.extend(f"{checkpoint_id}:{reference}" for reference in premature)
    return _gate(failures, checks)


def _finding_continuity_gate(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    failures = []
    checks = 0
    fields = ("item", "status", "opened_at", "closed_at")
    for checkpoint_id in CHECKPOINT_IDS:
        expected_findings = _by_id(expected[checkpoint_id].get("findings", []), "finding_id")
        actual_findings = _by_id(actual[checkpoint_id].get("findings", []), "finding_id")
        checks += 1
        if set(actual_findings) != set(expected_findings):
            failures.append(f"{checkpoint_id}:finding_ids")
        for finding_id, expected_finding in expected_findings.items():
            for field in fields:
                checks += 1
                if actual_findings.get(finding_id, {}).get(field) != expected_finding.get(field):
                    failures.append(f"{checkpoint_id}:{finding_id}:{field}")
    return _gate(failures, checks)


def _closure_evidence_gate(config: dict[str, Any], expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    checks = 0
    prior_requests: dict[str, dict[str, Any]] = {}
    policies = config["closure_request_policy"]
    for checkpoint_id in CHECKPOINT_IDS:
        expected_findings = _by_id(expected[checkpoint_id].get("findings", []), "finding_id")
        actual_findings = _by_id(actual[checkpoint_id].get("findings", []), "finding_id")
        for finding_id, expected_finding in expected_findings.items():
            actual_finding = actual_findings.get(finding_id, {})
            expected_refs = set(expected_finding.get("closure_evidence", []))
            actual_refs, malformed = _reference_set(actual_finding.get("closure_evidence"))
            checks += 2
            if malformed:
                failures.append(f"{checkpoint_id}:{finding_id}:closure_evidence_shape")
            if expected_finding["status"] == "closed" and not expected_refs.issubset(actual_refs):
                failures.append(f"{checkpoint_id}:{finding_id}:closure_evidence")
            if expected_finding["status"] == "open" and actual_refs:
                failures.append(f"{checkpoint_id}:{finding_id}:closure_evidence")
        expected_requests = _by_id(expected[checkpoint_id].get("closure_evidence_requests", []), "request_id")
        actual_requests = _by_id(actual[checkpoint_id].get("closure_evidence_requests", []), "request_id")
        checks += 1
        if set(actual_requests) != set(expected_requests):
            failures.append(f"{checkpoint_id}:request_ids")
        for request_id, expected_request in expected_requests.items():
            actual_request = actual_requests.get(request_id, {})
            checks += 6
            if actual_request.get("finding_id") != expected_request.get("finding_id"):
                failures.append(f"{checkpoint_id}:{request_id}:finding_id")
            if actual_request.get("status") != expected_request.get("status"):
                failures.append(f"{checkpoint_id}:{request_id}:status")
            requirements = actual_request.get("required_evidence")
            if not _request_requirements_complete(requirements, policies[request_id]["required_terms"]):
                failures.append(f"{checkpoint_id}:{request_id}:requirement_incomplete")
            if request_id in prior_requests and (
                requirements != prior_requests[request_id].get("required_evidence")
                or actual_request.get("finding_id") != prior_requests[request_id].get("finding_id")
            ):
                failures.append(f"{checkpoint_id}:{request_id}:requirement_changed")
            actual_refs, malformed = _reference_set(actual_request.get("response_refs"))
            if malformed:
                failures.append(f"{checkpoint_id}:{request_id}:response_refs_shape")
            if expected_request["status"] == "closed":
                required_refs = set(policies[request_id]["required_response_refs"])
                if not required_refs.issubset(actual_refs):
                    failures.append(f"{checkpoint_id}:{request_id}:response_refs")
            if expected_request["status"] == "open" and actual_refs:
                failures.append(f"{checkpoint_id}:{request_id}:response_refs")
        prior_requests = actual_requests
    return _gate(failures, checks)


def _request_requirements_complete(value: Any, required_terms: list[list[str]]) -> bool:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return False
    text = _normalized_text(" ".join(value))
    return all(any(term in text for term in group) for group in required_terms)


def _normalized_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _accepted_decision_gate(config: dict[str, Any], expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    checks = 0
    prior_decisions: dict[str, dict[str, Any]] = {}
    policies = config["decision_evidence_policy"]
    for checkpoint_id in CHECKPOINT_IDS:
        expected_decisions = _by_id(expected[checkpoint_id].get("accepted_decisions", []), "decision_id")
        actual_decisions = _by_id(actual[checkpoint_id].get("accepted_decisions", []), "decision_id")
        checks += 1
        if set(actual_decisions) != set(expected_decisions):
            failures.append(f"{checkpoint_id}:decision_ids")
        for decision_id, expected_decision in expected_decisions.items():
            actual_decision = actual_decisions.get(decision_id, {})
            for field in ("item", "status", "superseded_by"):
                checks += 1
                if actual_decision.get(field) != expected_decision.get(field):
                    failures.append(f"{checkpoint_id}:{decision_id}:{field}")
            if expected_decision.get("status") == "superseded":
                checks += 1
                if not str(actual_decision.get("supersession_reason", "")).strip():
                    failures.append(f"{checkpoint_id}:{decision_id}:supersession_reason")
            actual_basis, malformed = _reference_set(actual_decision.get("basis_refs"))
            checks += 3
            if malformed:
                failures.append(f"{checkpoint_id}:{decision_id}:basis_shape")
            policy = policies[decision_id]
            if not _decision_basis_is_complete(policy, actual_basis):
                failures.append(f"{checkpoint_id}:{decision_id}:basis_required")
            if not actual_basis.issubset(set(policy["allowed"])):
                failures.append(f"{checkpoint_id}:{decision_id}:basis_disallowed")
            if decision_id in prior_decisions:
                checks += 1
                prior_basis, prior_malformed = _reference_set(prior_decisions[decision_id].get("basis_refs"))
                if prior_malformed or actual_basis != prior_basis:
                    failures.append(f"{checkpoint_id}:{decision_id}:basis_changed")
        prior_decisions = actual_decisions
    return _gate(failures, checks)


def _decision_basis_is_complete(policy: dict[str, Any], actual_basis: set[str]) -> bool:
    alternatives = policy.get("required_alternatives")
    if alternatives is None:
        alternatives = [policy["required"]]
    return any(set(required).issubset(actual_basis) for required in alternatives)


def _final_readiness_gate(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    failures = [
        checkpoint_id
        for checkpoint_id in CHECKPOINT_IDS
        if actual[checkpoint_id].get("readiness_decision") != expected[checkpoint_id]["readiness_decision"]
    ]
    return _gate(failures, len(CHECKPOINT_IDS))


def _claim_boundary_gate(actual: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failures = []
    for checkpoint_id in CHECKPOINT_IDS:
        supported = _claim_boundary_supported(str(actual[checkpoint_id].get("claim_boundary_statement", "")))
        if not supported:
            failures.append(f"{checkpoint_id}.statement")
        expected_matrix = "pass" if supported else "fail"
        if actual[checkpoint_id].get("review_matrix", {}).get("PRV-09") != expected_matrix:
            failures.append(f"{checkpoint_id}.PRV-09")
    return _gate(failures, len(CHECKPOINT_IDS) * 2)


def _claim_boundary_supported(statement: str) -> bool:
    text = re.sub(r"[^a-z0-9]+", " ", statement.lower()).strip()
    positive_claims = (
        "is benchmark ready",
        "certifies benchmark readiness",
        "constitutes accepted project evidence",
        "represents accepted project evidence",
        "confirms standards compliance",
        "has authority approval",
        "is ready for executable verification",
    )
    concepts = (
        ("authority approval", "regulatory approval", "authority acceptance", "ahj approval"),
        ("accepted project evidence", "project of record evidence", "acceptance as project evidence"),
        ("standards compliance", "compliance with any standard", "compliance certification"),
        ("source pack hardening", "source packet hardening", "hardening of the source pack"),
        ("executable verifier readiness", "executable verification readiness", "ready for executable verification"),
        ("benchmark readiness", "benchmark certification", "benchmark ready"),
    )
    return (
        bool(text)
        and not any(claim in text for claim in positive_claims)
        and "task owned synthetic" in text
        and any(negation in text for negation in ("does not", "do not", "not constitute", "not represent"))
        and all(any(term in text for term in group) for group in concepts)
    )


def _gate(failures: list[str], checks: int) -> dict[str, Any]:
    unique = sorted(set(failures))
    failed_checks = min(len(unique), checks)
    score = round((checks - failed_checks) / checks, 4) if checks else 0.0
    return {"passed": not unique, "score": score, "failures": unique}


def _by_id(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {str(item[key]): item for item in items if isinstance(item, dict) and item.get(key)}


def _reference_set(value: Any) -> tuple[set[str], bool]:
    if not isinstance(value, list):
        return set(), True
    return {item for item in value if isinstance(item, str)}, any(not isinstance(item, str) for item in value)


def _semantic_atoms(submission: dict[str, Any]) -> dict[str, Any]:
    """Project one SSC-03 submission into stable, reward-independent state atoms."""
    atoms: dict[str, Any] = {}
    matrix = submission.get("review_matrix")
    matrix = matrix if isinstance(matrix, dict) else {}
    for index in range(1, 10):
        item = f"PRV-0{index}"
        atoms[f"review_matrix.{item}"] = matrix.get(item)

    transition = submission.get("transition_decision")
    transition = transition if isinstance(transition, dict) else {}
    for field in ("model_run", "model_report", "design_claim"):
        atoms[f"transition_decision.{field}"] = transition.get(field)
    atoms["readiness_decision"] = submission.get("readiness_decision")

    _record_atoms(
        atoms,
        collection_name="findings",
        records=submission.get("findings"),
        identity_key="finding_id",
        scalar_fields=("item", "status", "opened_at", "closed_at"),
    )
    _record_atoms(
        atoms,
        collection_name="closure_evidence_requests",
        records=submission.get("closure_evidence_requests"),
        identity_key="request_id",
        scalar_fields=("finding_id", "status"),
    )
    _record_atoms(
        atoms,
        collection_name="accepted_decisions",
        records=submission.get("accepted_decisions"),
        identity_key="decision_id",
        scalar_fields=("item", "status", "superseded_by"),
    )
    return atoms


def _record_atoms(
    atoms: dict[str, Any],
    *,
    collection_name: str,
    records: Any,
    identity_key: str,
    scalar_fields: tuple[str, ...],
) -> None:
    if not isinstance(records, list):
        atoms[f"{collection_name}.__identity_valid"] = False
        return
    identified = {
        record[identity_key]: record
        for record in records
        if isinstance(record, dict) and isinstance(record.get(identity_key), str) and record[identity_key]
    }
    atoms[f"{collection_name}.__identity_valid"] = len(identified) == len(records)
    for record_id, record in identified.items():
        prefix = f"{collection_name}.{record_id}"
        for field in scalar_fields:
            atoms[f"{prefix}.{field}"] = record.get(field)


def _instructions() -> dict[str, str]:
    return {
        checkpoint_id: _instruction(checkpoint_id, purpose)
        for checkpoint_id, purpose in {
            "initial_review": "Review the initial registered model evidence and establish the cumulative review state.",
            "response_review": "Review the newly released response evidence against the prior checkpoint state.",
            "closeout_review": "Review the newly released closeout evidence and determine final readiness.",
        }.items()
    }


def _instruction(checkpoint_id: str, purpose: str) -> str:
    return f"""# SSC-03 Drainage Model Evidence Lifecycle

{purpose}

Use only evidence currently visible under `inbox/` plus immutable prior submissions under `submissions/`.
Do not assume later evidence exists. Preserve stable finding, request, and accepted-decision IDs. Close a finding
only when the current or prior released evidence satisfies its recorded closure requirement. A response assertion
without the required artifact is not closure evidence.

Write the cumulative JSON review state to `submissions/{checkpoint_id}.json`. It must contain:

- `checkpoint_id`
- `evidence_refs`
- `review_matrix` for PRV-01 through PRV-09
- `transition_decision` for model run, model report, and design claim
- cumulative `findings` with stable IDs, states, and closure evidence
- cumulative `closure_evidence_requests`
- cumulative `accepted_decisions`
- `readiness_decision`
- `claim_boundary_statement`

{_review_contract()}

This is a task-owned synthetic source packet. Do not claim authority approval, accepted project evidence,
standards compliance, source-pack hardening, executable-verifier readiness, or benchmark readiness.
"""


def _review_contract() -> str:
    return """## Review Matrix

- PRV-01 | Packet completeness: are all required basis, manifest, run-register, report, memo, and criteria
  records present with IDs and revisions?
- PRV-02 | Stable source authority and basis identity: do the catchment, rainfall, and criteria sources
  remain traceable without mixing objects? Receipt belongs to PRV-01, run/report identity to PRV-04, and
  memo/report identity to PRV-06.
- PRV-03 | Input-revision provenance: does every input revision in the reviewed run manifest equal the
  corresponding current registered revision? This item owns manifest input-revision equality.
- PRV-04 | Run/report integrity: does the report belong to the registered run and satisfy intrinsic report
  acceptance checks? Record upstream input governance in the transition decision.
- PRV-05 | Scenario propagation: are the governing rainfall basis and design-storm identity preserved into
  the reviewed manifest? Do not duplicate a PRV-03 revision mismatch under PRV-05.
- PRV-06 | Downstream claim propagation: does the design memo preserve citation and value propagation for
  the reviewed run and report? Record whether that evidence governs in the transition decision.
- PRV-07 | Comment and action closure: is every critical comment closed and every carried action controlled?
- PRV-08 | Transition and readiness consistency: do the transition and readiness states reconcile with the
  matrix and registers?
- PRV-09 | Claim boundary: does the review avoid unsupported approval, compliance, hardening,
  verifier-readiness, or benchmark-readiness claims?

## JSON Contract

Use registered document IDs and revisions exactly as written in the sources. Reference lists contain strings, never
objects. Matrix values and decisions are lowercase enum strings, not explanatory objects. Use this exact shape:

```json
{
  "checkpoint_id": "<active checkpoint_id>",
  "evidence_refs": ["DOC-ID Rev X"],
  "review_matrix": {
    "PRV-01": "pass|fail|not_applicable|insufficient_data",
    "PRV-02": "...",
    "PRV-03": "...",
    "PRV-04": "...",
    "PRV-05": "...",
    "PRV-06": "...",
    "PRV-07": "...",
    "PRV-08": "...",
    "PRV-09": "..."
  },
  "transition_decision": {
    "model_run": "governing|non_governing|insufficient_data",
    "model_report": "governing|non_governing|insufficient_data",
    "design_claim": "supported|unsupported|insufficient_data"
  },
  "findings": [
    {
      "finding_id": "F-PRVXX-NNN",
      "item": "PRV-XX",
      "status": "open|closed",
      "opened_at": "checkpoint_id",
      "closed_at": "checkpoint_id|null",
      "closure_evidence": ["DOC-ID Rev X"]
    }
  ],
  "closure_evidence_requests": [
    {
      "request_id": "CER-NNN",
      "finding_id": "F-PRVXX-NNN",
      "status": "open|closed",
      "required_evidence": ["artifact description"],
      "response_refs": ["DOC-ID Rev X"]
    }
  ],
  "accepted_decisions": [
    {
      "decision_id": "D-PRVXX-NNN",
      "item": "PRV-XX",
      "status": "accepted",
      "basis_refs": ["DOC-ID Rev X"]
    }
  ],
  "readiness_decision": "ready_to_issue|ready_with_carried_actions|not_ready_to_issue",
  "claim_boundary_statement": "..."
}
```

For each failed item, open one finding. Build its ID as `F-` plus the item with its internal hyphen removed plus a
three-digit sequence, for example the generic pattern `F-PRVXX-NNN`. Sequence finding and decision IDs independently
within each PRV item; the first finding and first decision for PRV-06 are therefore numbered `001` regardless of IDs
used by other items. Allocate closure request IDs sequentially across the task as `CER-NNN` when findings first open.
Preserve all IDs unchanged in later cumulative submissions.

Decision-bearing items are PRV-01 through PRV-07. For each passing decision-bearing item, retain one active accepted
decision with ID `D-` plus the item without its internal hyphen plus a three-digit sequence. Preserve accepted records
byte-for-byte while their reviewed object and basis remain unchanged. When later evidence replaces that object or
basis, change the old record to `status: superseded`, add `superseded_by` (use `null` until a replacement is accepted)
and `supersession_reason`, then add the replacement accepted record when the item passes. Do not add supersession
fields to accepted records. In `basis_refs`, cite only the released sources directly necessary to support that matrix
item; do not attach the whole packet to every decision.

The decision record for PRV-01 owns the currently released document register; PRV-02 owns the stable catchment,
rainfall, and criteria identity; PRV-04 owns the run/report pair; PRV-05 owns scenario propagation into the reviewed
manifest; PRV-06 owns the memo/report pair; and PRV-07 owns the comment and action register. A report may pass
PRV-04's intrinsic integrity check independently, but it may govern in the transition only when its parent run
governs.

All arrays are cumulative. An open finding has `closed_at: null` and an empty `closure_evidence` list. A closed finding
names only released artifacts that satisfy its recorded requirement. An open closure request has an empty
`response_refs` list. Do not rewrite or remove prior records.
"""


def _releases() -> dict[str, dict[str, str]]:
    return {
        "initial_review": {
            "document-register.md": _INITIAL_REGISTER,
            "comment-action-register.md": _COMMENT_ACTION_REGISTER,
            "catchment-basis.md": _CATCHMENT_BASIS,
            "rainfall-basis.md": _RAINFALL_BASIS,
            "model-input-manifest-rev-a.md": _MANIFEST_A,
            "run-register-rev-e.md": _RUN_REGISTER_E,
            "hydraulic-report-042.md": _REPORT_042,
            "drainage-design-memo-rev-d.md": _MEMO_D,
            "criteria-comments.md": _CRITERIA,
        },
        "response_review": {
            "document-register-rev-f.md": _RESPONSE_REGISTER,
            "response-cover.md": _RESPONSE_COVER,
            "model-input-manifest-rev-b.md": _MANIFEST_B,
            "run-register-rev-f.md": _RUN_REGISTER_F,
            "hydraulic-report-043.md": _REPORT_043,
        },
        "closeout_review": {
            "document-register-rev-g.md": _CLOSEOUT_REGISTER,
            "drainage-design-memo-rev-e.md": _MEMO_E,
            "comment-response.md": _COMMENT_RESPONSE,
        },
    }


def _gold_submissions() -> dict[str, dict[str, Any]]:
    initial_decisions = _initial_decisions()
    response_decisions = _response_decisions(initial_decisions)
    closeout_decisions = _closeout_decisions(response_decisions)
    initial: dict[str, Any] = {
        "checkpoint_id": "initial_review",
        "evidence_refs": [
            "REG-03 Rev E",
            "COMMENT-03-REGISTER-01 Rev A",
            "CATCH-03-BASIS-01 Rev D",
            "RAIN-03-BASIS-01 Rev C",
            "MANIFEST-03-042 Rev A",
            "RUN-03-REGISTER-01 Rev E",
            "REPORT-03-042 Rev A",
            "MEMO-03-DESIGN-01 Rev D",
            "CRIT-SSC03-001 Rev C",
        ],
        "review_matrix": _matrix("PRV-03"),
        "transition_decision": {
            "model_run": "non_governing",
            "model_report": "non_governing",
            "design_claim": "unsupported",
        },
        "findings": [
            {
                "finding_id": "F-PRV03-001",
                "item": "PRV-03",
                "status": "open",
                "opened_at": "initial_review",
                "closed_at": None,
                "closure_evidence": [],
            }
        ],
        "closure_evidence_requests": [
            {
                "request_id": "CER-001",
                "finding_id": "F-PRV03-001",
                "status": "open",
                "required_evidence": ["current manifest citing CATCH-03-BASIS-01 Rev D"],
                "response_refs": [],
            }
        ],
        "accepted_decisions": initial_decisions,
        "readiness_decision": "not_ready_to_issue",
        "claim_boundary_statement": _CLAIM_BOUNDARY,
    }
    response = {
        "checkpoint_id": "response_review",
        "evidence_refs": initial["evidence_refs"]
        + [
            "REG-03 Rev F",
            "RESP-03-001 Rev A",
            "MANIFEST-03-042 Rev B",
            "RUN-03-REGISTER-01 Rev F",
            "REPORT-03-043 Rev A",
        ],
        "review_matrix": _matrix("PRV-06"),
        "transition_decision": {
            "model_run": "governing",
            "model_report": "governing",
            "design_claim": "unsupported",
        },
        "findings": [
            {
                "finding_id": "F-PRV03-001",
                "item": "PRV-03",
                "status": "closed",
                "opened_at": "initial_review",
                "closed_at": "response_review",
                "closure_evidence": ["MANIFEST-03-042 Rev B"],
            },
            {
                "finding_id": "F-PRV06-001",
                "item": "PRV-06",
                "status": "open",
                "opened_at": "response_review",
                "closed_at": None,
                "closure_evidence": [],
            },
        ],
        "closure_evidence_requests": [
            {
                "request_id": "CER-001",
                "finding_id": "F-PRV03-001",
                "status": "closed",
                "required_evidence": ["current manifest citing CATCH-03-BASIS-01 Rev D"],
                "response_refs": ["MANIFEST-03-042 Rev B"],
            },
            {
                "request_id": "CER-002",
                "finding_id": "F-PRV06-001",
                "status": "open",
                "required_evidence": ["current design memo citing and propagating the governing report"],
                "response_refs": [],
            },
        ],
        "accepted_decisions": response_decisions,
        "readiness_decision": "not_ready_to_issue",
        "claim_boundary_statement": _CLAIM_BOUNDARY,
    }
    closeout = {
        "checkpoint_id": "closeout_review",
        "evidence_refs": response["evidence_refs"]
        + ["REG-03 Rev G", "MEMO-03-DESIGN-01 Rev E", "RESP-03-CLOSEOUT-01 Rev A"],
        "review_matrix": _matrix(),
        "transition_decision": {
            "model_run": "governing",
            "model_report": "governing",
            "design_claim": "supported",
        },
        "findings": [
            response["findings"][0],
            {
                "finding_id": "F-PRV06-001",
                "item": "PRV-06",
                "status": "closed",
                "opened_at": "response_review",
                "closed_at": "closeout_review",
                "closure_evidence": ["MEMO-03-DESIGN-01 Rev E"],
            },
        ],
        "closure_evidence_requests": [
            response["closure_evidence_requests"][0],
            {
                "request_id": "CER-002",
                "finding_id": "F-PRV06-001",
                "status": "closed",
                "required_evidence": ["current design memo citing and propagating the governing report"],
                "response_refs": ["MEMO-03-DESIGN-01 Rev E"],
            },
        ],
        "accepted_decisions": closeout_decisions,
        "readiness_decision": "ready_to_issue",
        "claim_boundary_statement": _CLAIM_BOUNDARY,
    }
    return {"initial_review": initial, "response_review": response, "closeout_review": closeout}


def _allowed_evidence_refs() -> dict[str, list[str]]:
    gold = _gold_submissions()
    return {checkpoint_id: list(gold[checkpoint_id]["evidence_refs"]) for checkpoint_id in CHECKPOINT_IDS}


def _decision_evidence_policy() -> dict[str, dict[str, Any]]:
    return {
        "D-PRV01-001": {
            "required": ["REG-03 Rev E"],
            "allowed": ["REG-03 Rev E"],
        },
        "D-PRV01-002": {
            "required": ["REG-03 Rev F"],
            "allowed": ["REG-03 Rev F"],
        },
        "D-PRV01-003": {
            "required": ["REG-03 Rev G"],
            "allowed": ["REG-03 Rev G"],
        },
        "D-PRV02-001": {
            "required": ["CATCH-03-BASIS-01 Rev D", "RAIN-03-BASIS-01 Rev C", "CRIT-SSC03-001 Rev C"],
            "allowed": [
                "REG-03 Rev E",
                "REG-03 Rev F",
                "REG-03 Rev G",
                "CATCH-03-BASIS-01 Rev D",
                "RAIN-03-BASIS-01 Rev C",
                "CRIT-SSC03-001 Rev C",
            ],
        },
        "D-PRV03-001": {
            "required_alternatives": [
                ["MANIFEST-03-042 Rev B", "REG-03 Rev F"],
                ["MANIFEST-03-042 Rev B", "CATCH-03-BASIS-01 Rev D", "RAIN-03-BASIS-01 Rev C"],
            ],
            "allowed": [
                "REG-03 Rev F",
                "CATCH-03-BASIS-01 Rev D",
                "RAIN-03-BASIS-01 Rev C",
                "MANIFEST-03-042 Rev B",
                "RUN-03-REGISTER-01 Rev F",
            ],
        },
        "D-PRV04-001": {
            "required": ["RUN-03-REGISTER-01 Rev E", "REPORT-03-042 Rev A"],
            "allowed": ["RUN-03-REGISTER-01 Rev E", "REPORT-03-042 Rev A", "CRIT-SSC03-001 Rev C"],
        },
        "D-PRV04-002": {
            "required": ["RUN-03-REGISTER-01 Rev F", "REPORT-03-043 Rev A"],
            "allowed": ["RUN-03-REGISTER-01 Rev F", "REPORT-03-043 Rev A", "CRIT-SSC03-001 Rev C"],
        },
        "D-PRV05-001": {
            "required": ["RAIN-03-BASIS-01 Rev C", "MANIFEST-03-042 Rev A"],
            "allowed": ["RAIN-03-BASIS-01 Rev C", "MANIFEST-03-042 Rev A"],
        },
        "D-PRV05-002": {
            "required": ["RAIN-03-BASIS-01 Rev C", "MANIFEST-03-042 Rev B"],
            "allowed": ["RAIN-03-BASIS-01 Rev C", "MANIFEST-03-042 Rev B"],
        },
        "D-PRV06-001": {
            "required": ["MEMO-03-DESIGN-01 Rev D", "REPORT-03-042 Rev A"],
            "allowed": ["MEMO-03-DESIGN-01 Rev D", "REPORT-03-042 Rev A", "RUN-03-REGISTER-01 Rev E"],
        },
        "D-PRV06-002": {
            "required": ["MEMO-03-DESIGN-01 Rev E", "REPORT-03-043 Rev A"],
            "allowed": ["MEMO-03-DESIGN-01 Rev E", "REPORT-03-043 Rev A", "RUN-03-REGISTER-01 Rev F"],
        },
        "D-PRV07-001": {
            "required": ["COMMENT-03-REGISTER-01 Rev A"],
            "allowed": ["COMMENT-03-REGISTER-01 Rev A", "CRIT-SSC03-001 Rev C"],
        },
    }


def _closure_request_policy() -> dict[str, dict[str, Any]]:
    return {
        "CER-001": {
            "required_terms": [["manifest"], ["catchment basis", "catchment revision", "rev d"]],
            "required_response_refs": ["MANIFEST-03-042 Rev B"],
        },
        "CER-002": {
            "required_terms": [["memo"], ["report", "run", "propagat"]],
            "required_response_refs": ["MEMO-03-DESIGN-01 Rev E"],
        },
    }


def _matrix(failing_item: str | None = None) -> dict[str, str]:
    return {f"PRV-0{index}": "fail" if f"PRV-0{index}" == failing_item else "pass" for index in range(1, 10)}


def _initial_decisions() -> list[dict[str, Any]]:
    return [
        {
            "decision_id": decision_id,
            "item": item,
            "status": "accepted",
            "basis_refs": basis_refs,
        }
        for decision_id, item, basis_refs in [
            ("D-PRV01-001", "PRV-01", ["REG-03 Rev E"]),
            (
                "D-PRV02-001",
                "PRV-02",
                ["CATCH-03-BASIS-01 Rev D", "RAIN-03-BASIS-01 Rev C", "CRIT-SSC03-001 Rev C"],
            ),
            ("D-PRV04-001", "PRV-04", ["RUN-03-REGISTER-01 Rev E", "REPORT-03-042 Rev A"]),
            ("D-PRV05-001", "PRV-05", ["RAIN-03-BASIS-01 Rev C", "MANIFEST-03-042 Rev A"]),
            ("D-PRV06-001", "PRV-06", ["MEMO-03-DESIGN-01 Rev D", "REPORT-03-042 Rev A"]),
            ("D-PRV07-001", "PRV-07", ["COMMENT-03-REGISTER-01 Rev A"]),
        ]
    ]


def _response_decisions(initial: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions = copy.deepcopy(initial)
    by_id = _by_id(decisions, "decision_id")
    by_id["D-PRV01-001"].update(
        {
            "status": "superseded",
            "superseded_by": "D-PRV01-002",
            "supersession_reason": "REG-03 Rev F registers the response evidence release.",
        }
    )
    by_id["D-PRV04-001"].update(
        {
            "status": "superseded",
            "superseded_by": "D-PRV04-002",
            "supersession_reason": "RUN-03-043 and REPORT-03-043 replace the reviewed run/report object.",
        }
    )
    by_id["D-PRV05-001"].update(
        {
            "status": "superseded",
            "superseded_by": "D-PRV05-002",
            "supersession_reason": "MANIFEST-03-042 Rev B replaces the reviewed scenario-propagation object.",
        }
    )
    by_id["D-PRV06-001"].update(
        {
            "status": "superseded",
            "superseded_by": None,
            "supersession_reason": "The current memo has not yet propagated the replacement report.",
        }
    )
    decisions.extend(
        [
            {
                "decision_id": "D-PRV01-002",
                "item": "PRV-01",
                "status": "accepted",
                "basis_refs": ["REG-03 Rev F"],
            },
            {
                "decision_id": "D-PRV03-001",
                "item": "PRV-03",
                "status": "accepted",
                "basis_refs": ["MANIFEST-03-042 Rev B", "REG-03 Rev F"],
            },
            {
                "decision_id": "D-PRV04-002",
                "item": "PRV-04",
                "status": "accepted",
                "basis_refs": ["RUN-03-REGISTER-01 Rev F", "REPORT-03-043 Rev A"],
            },
            {
                "decision_id": "D-PRV05-002",
                "item": "PRV-05",
                "status": "accepted",
                "basis_refs": ["RAIN-03-BASIS-01 Rev C", "MANIFEST-03-042 Rev B"],
            },
        ]
    )
    return decisions


def _closeout_decisions(response: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions = copy.deepcopy(response)
    by_id = _by_id(decisions, "decision_id")
    by_id["D-PRV01-002"].update(
        {
            "status": "superseded",
            "superseded_by": "D-PRV01-003",
            "supersession_reason": "REG-03 Rev G registers the closeout evidence release.",
        }
    )
    by_id["D-PRV06-001"]["superseded_by"] = "D-PRV06-002"
    decisions.extend(
        [
            {
                "decision_id": "D-PRV01-003",
                "item": "PRV-01",
                "status": "accepted",
                "basis_refs": ["REG-03 Rev G"],
            },
            {
                "decision_id": "D-PRV06-002",
                "item": "PRV-06",
                "status": "accepted",
                "basis_refs": ["MEMO-03-DESIGN-01 Rev E", "REPORT-03-043 Rev A"],
            },
        ]
    )
    return decisions


def _readme() -> str:
    return """# Drainage Model Evidence Lifecycle Review

This package is one task world executed through three evidence checkpoints. The lifecycle runner keeps future
releases outside the agent workspace, preserves prior submissions, and returns one cumulative parent task run.
The packet is task-owned synthetic evidence and does not represent accepted project evidence.
"""


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


_CLAIM_BOUNDARY = (
    "This review covers a task-owned synthetic source packet and does not claim authority approval, accepted "
    "project evidence, standards compliance, source-pack hardening, executable-verifier readiness, or benchmark "
    "readiness."
)

_INITIAL_REGISTER = """# Document Register

Register: REG-03 Rev E

| Document | Revision | Status |
|---|---|---|
| CATCH-03-BASIS-01 | Rev D | current |
| RAIN-03-BASIS-01 | Rev C | current |
| MANIFEST-03-042 | Rev A | current submission |
| RUN-03-REGISTER-01 | Rev E | current |
| REPORT-03-042 | Rev A | current submission |
| MEMO-03-DESIGN-01 | Rev D | current submission |
| CRIT-SSC03-001 | Rev C | governing criteria |
| COMMENT-03-REGISTER-01 | Rev A | current |
"""

_COMMENT_ACTION_REGISTER = """# Comment and Action Register

Source: COMMENT-03-REGISTER-01 Rev A
Open critical comments: 0
Carried actions: 0
"""

_CATCHMENT_BASIS = """# Governing Catchment Basis

Source: CATCH-03-BASIS-01 Rev D
Catchment: CATCH-03-A
Catchment area: 45.93 ha
"""

_RAINFALL_BASIS = """# Governing Rainfall Basis

Source: RAIN-03-BASIS-01 Rev C
Design storm: STORM-03-A
"""

_MANIFEST_A = """# Model Input Manifest

Source: MANIFEST-03-042 Rev A
Catchment basis: CATCH-03-BASIS-01 Rev C
Rainfall basis: RAIN-03-BASIS-01 Rev C
Design storm: STORM-03-A
Catchment area: 44.39 ha
"""

_RUN_REGISTER_E = """# Run Register

Source: RUN-03-REGISTER-01 Rev E
RUN-03-042 uses MANIFEST-03-042 Rev A and produces REPORT-03-042 Rev A.
"""

_REPORT_042 = """# Hydraulic Report

Source: REPORT-03-042 Rev A
Run: RUN-03-042
Peak flow: 2.75 m3/s
Maximum HGL: 20.45 m AHD
Continuity error: 1.27 percent
"""

_MEMO_D = """# Drainage Design Memo

Source: MEMO-03-DESIGN-01 Rev D
Cited run: RUN-03-042
Cited report: REPORT-03-042 Rev A
Adopted peak flow: 2.75 m3/s
Adopted maximum HGL: 20.45 m AHD
"""

_CRITERIA = """# Model Governance Criteria

Source: CRIT-SSC03-001 Rev C

- A run may govern only when all manifest input revisions match the current register.
- PRV-03 owns manifest input-revision equality between the manifest and current registered inputs.
- PRV-05 owns rainfall-basis and design-storm identity, independent of whether the cited revision is current.
- Do not duplicate a PRV-03 revision mismatch under PRV-05.
- Report integrity checks run identity and continuity error independently of upstream governing state.
- A report may govern in the transition only when its parent run governs.
- Memo propagation integrity checks cited run/report identity and preservation of reported values.
- A confirmed defect remains failed until corrected evidence is supplied; request that evidence as a closure
  requirement rather than reclassifying the original defect as insufficient data.
- Close a finding only when every recorded closure requirement is supported by a released source.
- Maximum continuity error: 1.75 percent.
"""

_RESPONSE_REGISTER = """# Response Document Register

Register: REG-03 Rev F
Supersedes: REG-03 Rev E

| Document | Revision | Status |
|---|---|---|
| CATCH-03-BASIS-01 | Rev D | current |
| RAIN-03-BASIS-01 | Rev C | current |
| MANIFEST-03-042 | Rev B | current submission |
| RUN-03-REGISTER-01 | Rev F | current |
| REPORT-03-043 | Rev A | current submission |
| MEMO-03-DESIGN-01 | Rev D | current submission |
| CRIT-SSC03-001 | Rev C | governing criteria |
| COMMENT-03-REGISTER-01 | Rev A | current |
| RESP-03-001 | Rev A | current response |
"""

_RESPONSE_COVER = """# Response Cover

Source: RESP-03-001 Rev A
The model custodian submits a revised manifest, rerun, and reissued report in response to the initial review.
Each artifact must be checked rather than accepted from this assertion alone.
"""

_MANIFEST_B = """# Revised Model Input Manifest

Source: MANIFEST-03-042 Rev B
Catchment basis: CATCH-03-BASIS-01 Rev D
Rainfall basis: RAIN-03-BASIS-01 Rev C
Design storm: STORM-03-A
Catchment area: 45.93 ha
"""

_RUN_REGISTER_F = """# Revised Run Register

Source: RUN-03-REGISTER-01 Rev F
RUN-03-043 uses MANIFEST-03-042 Rev B and produces REPORT-03-043 Rev A.
RUN-03-042 is superseded.
"""

_REPORT_043 = """# Reissued Hydraulic Report

Source: REPORT-03-043 Rev A
Run: RUN-03-043
Peak flow: 2.91 m3/s
Maximum HGL: 20.62 m AHD
Continuity error: 1.18 percent
"""

_CLOSEOUT_REGISTER = """# Closeout Document Register

Register: REG-03 Rev G
Supersedes: REG-03 Rev F

| Document | Revision | Status |
|---|---|---|
| CATCH-03-BASIS-01 | Rev D | current |
| RAIN-03-BASIS-01 | Rev C | current |
| MANIFEST-03-042 | Rev B | current submission |
| RUN-03-REGISTER-01 | Rev F | current |
| REPORT-03-043 | Rev A | current submission |
| MEMO-03-DESIGN-01 | Rev E | current submission |
| CRIT-SSC03-001 | Rev C | governing criteria |
| COMMENT-03-REGISTER-01 | Rev A | current |
| RESP-03-CLOSEOUT-01 | Rev A | current response |
"""

_MEMO_E = """# Revised Drainage Design Memo

Source: MEMO-03-DESIGN-01 Rev E
Cited run: RUN-03-043
Cited report: REPORT-03-043 Rev A
Adopted peak flow: 2.91 m3/s
Adopted maximum HGL: 20.62 m AHD
"""

_COMMENT_RESPONSE = """# Closeout Comment Response

Source: RESP-03-CLOSEOUT-01 Rev A
Finding F-PRV06-001 is nominated for closure against MEMO-03-DESIGN-01 Rev E.
The reviewer must independently confirm the cited run, report, and values before closure.
"""
