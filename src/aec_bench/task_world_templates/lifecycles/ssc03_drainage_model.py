# ABOUTME: Materializes and verifies the SSC-03 drainage model evidence-lifecycle companion.
# ABOUTME: Defines three synthetic releases, cumulative gold states, and continuity-focused gates.

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from aec_bench.meta_harness.evidence_lifecycle import load_validated_lifecycle_submissions
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.contracts import CompositeTaskWorldTemplate

CHECKPOINT_IDS = ("initial_review", "response_review", "closeout_review")
GATE_IDS = (
    "checkpoint_contract",
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
    _write_json(output / "hidden" / "verifier-config.json", {"allowed_evidence_refs": _allowed_evidence_refs()})
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
        "staged_disclosure": _staged_disclosure_gate(config, actual),
        "finding_continuity": _finding_continuity_gate(expected, actual),
        "closure_evidence": _closure_evidence_gate(expected, actual),
        "accepted_decision_preservation": _accepted_decision_gate(expected, actual),
        "final_readiness": _final_readiness_gate(expected, actual),
        "claim_boundary": _claim_boundary_gate(actual),
    }
    reward = round(sum(float(gate["score"]) for gate in gates.values()) / len(gates), 4)
    passed = all(bool(gate["passed"]) for gate in gates.values())
    return {
        "template_id": "drainage-model-evidence-lifecycle-review",
        "lifecycle_id": "ssc03.drainage-model-evidence-lifecycle",
        "overall": "pass" if passed else "fail",
        "passed": passed,
        "reward": reward,
        "gates": gates,
    }


def _checkpoint_contract_gate(expected: dict, actual: dict) -> dict[str, Any]:
    fields = ("checkpoint_id", "review_matrix", "transition_decision", "readiness_decision")
    failures = [
        f"{checkpoint_id}.{field}"
        for checkpoint_id in CHECKPOINT_IDS
        for field in fields
        if actual[checkpoint_id].get(field) != expected[checkpoint_id].get(field)
    ]
    return _gate(failures)


def _staged_disclosure_gate(config: dict, actual: dict) -> dict[str, Any]:
    allowed = config["allowed_evidence_refs"]
    failures = []
    for checkpoint_id in CHECKPOINT_IDS:
        references, malformed = _reference_set(actual[checkpoint_id].get("evidence_refs"))
        if malformed:
            failures.append(f"{checkpoint_id}:evidence_refs_shape")
        premature = sorted(references - set(allowed[checkpoint_id]))
        failures.extend(f"{checkpoint_id}:{reference}" for reference in premature)
    return _gate(failures)


def _finding_continuity_gate(expected: dict, actual: dict) -> dict[str, Any]:
    failures = []
    fields = ("item", "status", "opened_at", "closed_at")
    for checkpoint_id in CHECKPOINT_IDS:
        expected_findings = _by_id(expected[checkpoint_id].get("findings", []), "finding_id")
        actual_findings = _by_id(actual[checkpoint_id].get("findings", []), "finding_id")
        if set(actual_findings) != set(expected_findings):
            failures.append(f"{checkpoint_id}:finding_ids")
            continue
        for finding_id, expected_finding in expected_findings.items():
            for field in fields:
                if actual_findings[finding_id].get(field) != expected_finding.get(field):
                    failures.append(f"{checkpoint_id}:{finding_id}:{field}")
    return _gate(failures)


def _closure_evidence_gate(expected: dict, actual: dict) -> dict[str, Any]:
    failures: list[str] = []
    for checkpoint_id in CHECKPOINT_IDS:
        expected_findings = _by_id(expected[checkpoint_id].get("findings", []), "finding_id")
        actual_findings = _by_id(actual[checkpoint_id].get("findings", []), "finding_id")
        for finding_id, expected_finding in expected_findings.items():
            actual_finding = actual_findings.get(finding_id, {})
            expected_refs = set(expected_finding.get("closure_evidence", []))
            actual_refs, malformed = _reference_set(actual_finding.get("closure_evidence"))
            if malformed:
                failures.append(f"{finding_id}:closure_evidence_shape")
            if expected_finding["status"] == "closed" and not expected_refs.issubset(actual_refs):
                failures.append(finding_id)
            if expected_finding["status"] == "open" and actual_refs:
                failures.append(finding_id)
        expected_requests = _by_id(expected[checkpoint_id].get("closure_evidence_requests", []), "request_id")
        actual_requests = _by_id(actual[checkpoint_id].get("closure_evidence_requests", []), "request_id")
        for request_id, expected_request in expected_requests.items():
            actual_request = actual_requests.get(request_id, {})
            if actual_request.get("status") != expected_request.get("status"):
                failures.append(request_id)
                continue
            expected_refs = set(expected_request.get("response_refs", []))
            actual_refs, malformed = _reference_set(actual_request.get("response_refs"))
            if malformed:
                failures.append(f"{request_id}:response_refs_shape")
            if expected_request["status"] == "closed" and not expected_refs.issubset(actual_refs):
                failures.append(request_id)
            if expected_request["status"] == "open" and actual_refs:
                failures.append(request_id)
    return _gate(sorted(set(failures)))


def _accepted_decision_gate(expected: dict, actual: dict) -> dict[str, Any]:
    failures = []
    for checkpoint_id in CHECKPOINT_IDS:
        expected_decisions = _by_id(expected[checkpoint_id].get("accepted_decisions", []), "decision_id")
        actual_decisions = _by_id(actual[checkpoint_id].get("accepted_decisions", []), "decision_id")
        if set(actual_decisions) != set(expected_decisions) or any(
            not _decision_matches(expected_decision, actual_decisions.get(decision_id, {}))
            for decision_id, expected_decision in expected_decisions.items()
        ):
            failures.append(checkpoint_id)
    return _gate(failures)


def _decision_matches(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    for field in ("item", "status", "superseded_by"):
        if actual.get(field) != expected.get(field):
            return False
    expected_basis = set(expected.get("basis_refs", []))
    actual_basis, malformed = _reference_set(actual.get("basis_refs"))
    if malformed or actual_basis != expected_basis:
        return False
    return expected.get("status") != "superseded" or bool(str(actual.get("supersession_reason", "")).strip())


def _final_readiness_gate(expected: dict, actual: dict) -> dict[str, Any]:
    failures = [
        checkpoint_id
        for checkpoint_id in CHECKPOINT_IDS
        if actual[checkpoint_id].get("readiness_decision") != expected[checkpoint_id]["readiness_decision"]
    ]
    if actual["closeout_review"].get("readiness_decision") != "ready_to_issue":
        failures.append("closeout_not_ready")
    return _gate(failures)


def _claim_boundary_gate(actual: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failures = [
        checkpoint_id
        for checkpoint_id in CHECKPOINT_IDS
        if not _claim_boundary_supported(str(actual[checkpoint_id].get("claim_boundary_statement", "")))
    ]
    return _gate(failures)


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


def _gate(failures: list[str]) -> dict[str, Any]:
    unique = sorted(set(failures))
    return {"passed": not unique, "score": 1.0 if not unique else 0.0, "failures": unique}


def _by_id(items: list[dict], key: str) -> dict[str, dict]:
    if not isinstance(items, list):
        return {}
    return {str(item[key]): item for item in items if isinstance(item, dict) and item.get(key)}


def _reference_set(value: Any) -> tuple[set[str], bool]:
    if not isinstance(value, list):
        return set(), True
    return {item for item in value if isinstance(item, str)}, any(not isinstance(item, str) for item in value)


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
- PRV-02 | Source authority and identity: do site, catchment, governing source, run, report, memo, and
  criteria identities remain traceable without mixing objects?
- PRV-03 | Input-revision provenance: does the reviewed run manifest identify every governing input
  revision declared by the packet?
- PRV-04 | Run/report integrity: does the report belong to the registered run and satisfy intrinsic report
  acceptance checks? Record upstream input governance in the transition decision.
- PRV-05 | Scenario propagation: is the governing design scenario preserved into the reviewed run?
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
three-digit sequence, for example the generic pattern `F-PRVXX-NNN`. Allocate closure request IDs sequentially as
`CER-NNN` when findings first open. Preserve both IDs unchanged in later cumulative submissions.

Decision-bearing items are PRV-01 through PRV-07. For each passing decision-bearing item, retain one active accepted
decision with ID `D-` plus the item without its internal hyphen plus a three-digit sequence. Preserve accepted records
byte-for-byte while their reviewed object and basis remain unchanged. When later evidence replaces that object or
basis, change the old record to `status: superseded`, add `superseded_by` (use `null` until a replacement is accepted)
and `supersession_reason`, then add the replacement accepted record when the item passes. Do not add supersession
fields to accepted records. In `basis_refs`, cite only the released sources directly necessary to support that matrix
item; do not attach the whole packet to every decision.

All arrays are cumulative. An open finding has `closed_at: null` and an empty `closure_evidence` list. A closed finding
names only released artifacts that satisfy its recorded requirement. An open closure request has an empty
`response_refs` list. Do not rewrite or remove prior records.
"""


def _releases() -> dict[str, dict[str, str]]:
    return {
        "initial_review": {
            "document-register.md": _INITIAL_REGISTER,
            "catchment-basis.md": _CATCHMENT_BASIS,
            "rainfall-basis.md": _RAINFALL_BASIS,
            "model-input-manifest-rev-a.md": _MANIFEST_A,
            "run-register-rev-e.md": _RUN_REGISTER_E,
            "hydraulic-report-042.md": _REPORT_042,
            "drainage-design-memo-rev-d.md": _MEMO_D,
            "criteria-comments.md": _CRITERIA,
        },
        "response_review": {
            "response-cover.md": _RESPONSE_COVER,
            "model-input-manifest-rev-b.md": _MANIFEST_B,
            "run-register-rev-f.md": _RUN_REGISTER_F,
            "hydraulic-report-043.md": _REPORT_043,
        },
        "closeout_review": {
            "drainage-design-memo-rev-e.md": _MEMO_E,
            "comment-response.md": _COMMENT_RESPONSE,
        },
    }


def _gold_submissions() -> dict[str, dict[str, Any]]:
    initial_decisions = _initial_decisions()
    response_decisions = _response_decisions(initial_decisions)
    closeout_decisions = _closeout_decisions(response_decisions)
    initial = {
        "checkpoint_id": "initial_review",
        "evidence_refs": [
            "REG-03 Rev E",
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
                "required_evidence": ["current manifest", "rerun identity", "reissued report"],
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
                "closure_evidence": [
                    "MANIFEST-03-042 Rev B",
                    "RUN-03-REGISTER-01 Rev F",
                    "REPORT-03-043 Rev A",
                ],
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
                "required_evidence": ["current manifest", "rerun identity", "reissued report"],
                "response_refs": [
                    "MANIFEST-03-042 Rev B",
                    "RUN-03-REGISTER-01 Rev F",
                    "REPORT-03-043 Rev A",
                ],
            },
            {
                "request_id": "CER-002",
                "finding_id": "F-PRV06-001",
                "status": "open",
                "required_evidence": ["current design memo", "formal comment response"],
                "response_refs": [],
            },
        ],
        "accepted_decisions": response_decisions,
        "readiness_decision": "not_ready_to_issue",
        "claim_boundary_statement": _CLAIM_BOUNDARY,
    }
    closeout = {
        "checkpoint_id": "closeout_review",
        "evidence_refs": response["evidence_refs"] + ["MEMO-03-DESIGN-01 Rev E", "RESP-03-CLOSEOUT-01 Rev A"],
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
                "closure_evidence": ["MEMO-03-DESIGN-01 Rev E", "RESP-03-CLOSEOUT-01 Rev A"],
            },
        ],
        "closure_evidence_requests": [
            response["closure_evidence_requests"][0],
            {
                "request_id": "CER-002",
                "finding_id": "F-PRV06-001",
                "status": "closed",
                "required_evidence": ["current design memo", "formal comment response"],
                "response_refs": ["MEMO-03-DESIGN-01 Rev E", "RESP-03-CLOSEOUT-01 Rev A"],
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
            ("D-PRV02-001", "PRV-02", ["CATCH-03-BASIS-01 Rev D", "RAIN-03-BASIS-01 Rev C"]),
            ("D-PRV04-001", "PRV-04", ["RUN-03-REGISTER-01 Rev E", "REPORT-03-042 Rev A"]),
            ("D-PRV05-001", "PRV-05", ["RAIN-03-BASIS-01 Rev C"]),
            ("D-PRV06-001", "PRV-06", ["MEMO-03-DESIGN-01 Rev D", "REPORT-03-042 Rev A"]),
            ("D-PRV07-001", "PRV-07", ["CRIT-SSC03-001 Rev C"]),
        ]
    ]


def _response_decisions(initial: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions = copy.deepcopy(initial)
    by_id = _by_id(decisions, "decision_id")
    by_id["D-PRV04-001"].update(
        {
            "status": "superseded",
            "superseded_by": "D-PRV04-002",
            "supersession_reason": "RUN-03-043 and REPORT-03-043 replace the reviewed run/report object.",
        }
    )
    by_id["D-PRV06-001"].update(
        {
            "status": "superseded",
            "superseded_by": None,
            "supersession_reason": "The current memo has not yet propagated the replacement report.",
        }
    )
    decisions.append(
        {
            "decision_id": "D-PRV04-002",
            "item": "PRV-04",
            "status": "accepted",
            "basis_refs": ["RUN-03-REGISTER-01 Rev F", "REPORT-03-043 Rev A"],
        }
    )
    return decisions


def _closeout_decisions(response: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions = copy.deepcopy(response)
    by_id = _by_id(decisions, "decision_id")
    by_id["D-PRV06-001"]["superseded_by"] = "D-PRV06-002"
    decisions.append(
        {
            "decision_id": "D-PRV06-002",
            "item": "PRV-06",
            "status": "accepted",
            "basis_refs": ["MEMO-03-DESIGN-01 Rev E", "REPORT-03-043 Rev A"],
        }
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
| REPORT-03-042 | Rev A | current submission |
| MEMO-03-DESIGN-01 | Rev D | current submission |
| CRIT-SSC03-001 | Rev C | governing criteria |
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
- Report integrity checks run identity and continuity error independently of upstream governing state.
- Memo propagation integrity checks cited run/report identity and preservation of reported values.
- A confirmed defect remains failed until corrected evidence is supplied; request that evidence as a closure
  requirement rather than reclassifying the original defect as insufficient data.
- Close a finding only when every recorded closure requirement is supported by a released source.
- Maximum continuity error: 1.75 percent.
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
