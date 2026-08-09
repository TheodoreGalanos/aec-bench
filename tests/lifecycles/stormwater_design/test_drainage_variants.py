# ABOUTME: Tests controlled semantic variants of the drainage-model evidence lifecycle.
# ABOUTME: Covers variant contracts, deterministic packages, topology state, leakage, and verification.

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.experimentation.lifecycle_studies.experiment import record_lifecycle_experiment
from aec_bench.lifecycles.catalogue import lifecycle_package_variant, materialize_lifecycle
from aec_bench.lifecycles.runtime.lifecycle import EvidenceLifecycleError, run_evidence_lifecycle
from aec_bench.lifecycles.stormwater_design.drainage_model import verify_drainage_model_lifecycle
from aec_bench.lifecycles.stormwater_design.drainage_variants import (
    DEFAULT_DRAINAGE_LIFECYCLE_VARIANT_ID,
    DrainageEvidenceEvent,
    DrainageLifecycleVariantSpec,
    get_drainage_model_variant,
    list_drainage_model_variant_ids,
)
from tests.support.lifecycle_episode import deterministic_episode_environment

EXPECTED_VARIANTS = (
    "memo_closeout_missing",
    "response_assertion_only",
    "semantic_no_op_release",
    "staged_full_correction",
)
CHECKPOINT_IDS = ("initial_review", "response_review", "closeout_review")


def test_drainage_model_variant_registry_is_explicit_and_has_canonical_default() -> None:
    assert DEFAULT_DRAINAGE_LIFECYCLE_VARIANT_ID == "staged_full_correction"
    assert list_drainage_model_variant_ids() == EXPECTED_VARIANTS

    for variant_id in EXPECTED_VARIANTS:
        spec = get_drainage_model_variant(variant_id)
        assert spec.variant_id == variant_id
        assert spec.adaptation.variation == {"change_topology": variant_id}
        assert spec.adaptation.seed_task_id == "drainage-model-evidence-lifecycle-review"
        assert spec.visibility == "public"


def test_drainage_model_variant_registry_returns_defensive_copies() -> None:
    first = get_drainage_model_variant(DEFAULT_DRAINAGE_LIFECYCLE_VARIANT_ID)
    first.summary = "caller-local mutation"

    second = get_drainage_model_variant(DEFAULT_DRAINAGE_LIFECYCLE_VARIANT_ID)
    assert second.summary != first.summary


def test_drainage_model_variant_registry_rejects_unknown_id_with_known_choices() -> None:
    with pytest.raises(KeyError, match="memo_closeout_missing.*staged_full_correction"):
        get_drainage_model_variant("not-a-variant")


def test_drainage_model_variant_contract_rejects_checkpoint_reordering() -> None:
    payload = get_drainage_model_variant(DEFAULT_DRAINAGE_LIFECYCLE_VARIANT_ID).model_dump(mode="json")
    payload["checkpoints"] = list(reversed(payload["checkpoints"]))

    with pytest.raises(ValidationError, match="checkpoints must use the drainage-model lifecycle order"):
        DrainageLifecycleVariantSpec.model_validate(payload)


def test_drainage_model_variant_contract_rejects_memo_propagation_without_corrected_model_chain() -> None:
    payload = get_drainage_model_variant(DEFAULT_DRAINAGE_LIFECYCLE_VARIANT_ID).model_dump(mode="json")
    payload["checkpoints"][1]["events"] = [DrainageEvidenceEvent.SEMANTIC_NO_OP.value]

    with pytest.raises(ValidationError, match="memo propagation requires a corrected model chain"):
        DrainageLifecycleVariantSpec.model_validate(payload)


def test_drainage_model_variant_contract_rejects_contradictory_response_events() -> None:
    payload = get_drainage_model_variant(DEFAULT_DRAINAGE_LIFECYCLE_VARIANT_ID).model_dump(mode="json")
    payload["checkpoints"][1]["events"] = [
        DrainageEvidenceEvent.SEMANTIC_NO_OP.value,
        DrainageEvidenceEvent.RELEASE_CORRECTED_MODEL_CHAIN.value,
    ]

    with pytest.raises(ValidationError, match="response_review must declare exactly one controlled event"):
        DrainageLifecycleVariantSpec.model_validate(payload)


def test_drainage_model_variant_contract_rejects_competing_closeout_events() -> None:
    payload = get_drainage_model_variant(DEFAULT_DRAINAGE_LIFECYCLE_VARIANT_ID).model_dump(mode="json")
    payload["checkpoints"][2]["events"] = [
        DrainageEvidenceEvent.PROPAGATE_MEMO.value,
        DrainageEvidenceEvent.ASSERT_MEMO_CLOSURE.value,
    ]

    with pytest.raises(ValidationError, match="closeout_review event combination is not supported"):
        DrainageLifecycleVariantSpec.model_validate(payload)


def test_default_variant_preserves_agent_visible_package_bytes(tmp_path: Path) -> None:
    package = materialize_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / "package",
    )

    assert _visible_tree_hash(package) == "4d5609b6dec09dd003d54accd085a2a0e8597a43a4ae6b535c27013504effd3a"
    assert _load_json(package / "hidden" / "variant.json")["variant_id"] == DEFAULT_DRAINAGE_LIFECYCLE_VARIANT_ID


def test_rematerializing_into_non_empty_package_is_rejected_without_mutation(tmp_path: Path) -> None:
    template = "drainage-model-evidence-lifecycle-review"
    package = materialize_lifecycle(
        template,
        tmp_path / "package",
        variant_id=DEFAULT_DRAINAGE_LIFECYCLE_VARIANT_ID,
    )
    original = _package_files(package)

    with pytest.raises(ValueError, match="output directory must be empty"):
        materialize_lifecycle(template, package, variant_id="memo_closeout_missing")

    assert _package_files(package) == original
    assert (package / "releases" / "closeout_review" / "drainage-design-memo-rev-e.md").is_file()


@pytest.mark.parametrize("variant_id", EXPECTED_VARIANTS)
def test_drainage_model_variants_materialize_deterministically_and_golden_state_verifies(
    tmp_path: Path,
    variant_id: str,
) -> None:
    template = "drainage-model-evidence-lifecycle-review"
    first = materialize_lifecycle(template, tmp_path / "first", variant_id=variant_id)
    second = materialize_lifecycle(template, tmp_path / "second", variant_id=variant_id)

    assert _package_files(first) == _package_files(second)
    assert _load_json(first / "hidden" / "variant.json")["variant_id"] == variant_id
    run_dir = _run_gold(first, tmp_path / "run")
    result = verify_drainage_model_lifecycle(first, run_dir)
    assert result["overall"] == "pass"
    assert result["reward"] == 1.0
    assert result["semantic_metrics"]["initial"]["accuracy"] == 1.0
    assert result["semantic_metrics"]["aggregate"]["retention"] == 1.0


@pytest.mark.parametrize(
    ("variant_id", "expected_failures", "expected_readiness"),
    [
        ("staged_full_correction", ("PRV-03", "PRV-06", None), "ready_to_issue"),
        ("semantic_no_op_release", ("PRV-03", "PRV-03", None), "ready_to_issue"),
        ("response_assertion_only", ("PRV-03", "PRV-03", None), "ready_to_issue"),
        ("memo_closeout_missing", ("PRV-03", "PRV-06", "PRV-06"), "not_ready_to_issue"),
    ],
)
def test_drainage_model_variant_gold_encodes_declared_change_topology(
    tmp_path: Path,
    variant_id: str,
    expected_failures: tuple[str | None, ...],
    expected_readiness: str,
) -> None:
    package = materialize_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / variant_id,
        variant_id=variant_id,
    )
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    for checkpoint_id, failing_item in zip(
        ("initial_review", "response_review", "closeout_review"),
        expected_failures,
        strict=True,
    ):
        failed = [item for item, status in gold[checkpoint_id]["review_matrix"].items() if status == "fail"]
        assert failed == ([] if failing_item is None else [failing_item])
    assert gold["closeout_review"]["readiness_decision"] == expected_readiness


@pytest.mark.parametrize("variant_id", EXPECTED_VARIANTS)
def test_rendered_sources_independently_support_variant_gold(tmp_path: Path, variant_id: str) -> None:
    package = materialize_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / variant_id,
        variant_id=variant_id,
    )
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    for checkpoint_index, checkpoint_id in enumerate(CHECKPOINT_IDS):
        source_text = _cumulative_release_text(package, checkpoint_index)
        manifest_is_current = all(
            fact in source_text
            for fact in (
                "Source: MANIFEST-03-042 Rev B",
                "Catchment basis: CATCH-03-BASIS-01 Rev D",
            )
        )
        rerun_is_traceable = all(
            fact in source_text
            for fact in (
                "RUN-03-043 uses MANIFEST-03-042 Rev B",
                "Source: REPORT-03-043 Rev A",
                "Run: RUN-03-043",
            )
        )
        memo_is_propagated = all(
            fact in source_text
            for fact in (
                "Source: MEMO-03-DESIGN-01 Rev E",
                "Cited run: RUN-03-043",
                "Cited report: REPORT-03-043 Rev A",
            )
        )
        corrected_chain = manifest_is_current and rerun_is_traceable
        expected_failure = "PRV-03" if not corrected_chain else ("PRV-06" if not memo_is_propagated else None)
        actual_failures = [item for item, status in gold[checkpoint_id]["review_matrix"].items() if status == "fail"]

        assert actual_failures == ([] if expected_failure is None else [expected_failure])
        assert gold[checkpoint_id]["transition_decision"] == {
            "model_run": "governing" if corrected_chain else "non_governing",
            "model_report": "governing" if corrected_chain else "non_governing",
            "design_claim": "supported" if corrected_chain and memo_is_propagated else "unsupported",
        }
        for evidence_ref in gold[checkpoint_id]["evidence_refs"]:
            assert evidence_ref in source_text


def test_assertion_variants_do_not_treat_assertions_as_closure_evidence(tmp_path: Path) -> None:
    template = "drainage-model-evidence-lifecycle-review"
    response_assertion = materialize_lifecycle(
        template,
        tmp_path / "response-assertion",
        variant_id="response_assertion_only",
    )
    memo_assertion = materialize_lifecycle(
        template,
        tmp_path / "memo-assertion",
        variant_id="memo_closeout_missing",
    )
    response_gold = _load_json(response_assertion / "hidden" / "gold-submissions.json")
    memo_gold = _load_json(memo_assertion / "hidden" / "gold-submissions.json")

    assert response_gold["response_review"]["findings"][0]["status"] == "open"
    assert response_gold["response_review"]["closure_evidence_requests"][0]["response_refs"] == []
    assert memo_gold["closeout_review"]["findings"][-1]["status"] == "open"
    assert memo_gold["closeout_review"]["closure_evidence_requests"][-1]["response_refs"] == []
    assert not (memo_assertion / "releases" / "closeout_review" / "drainage-design-memo-rev-e.md").exists()


@pytest.mark.parametrize("variant_id", ["semantic_no_op_release", "response_assertion_only"])
def test_deferred_correction_sources_only_name_findings_present_in_gold(tmp_path: Path, variant_id: str) -> None:
    package = materialize_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / variant_id,
        variant_id=variant_id,
    )
    source_finding_ids = {
        match
        for path in (package / "releases").rglob("*.md")
        for match in re.findall(r"F-PRV\d{2}-\d{3}", path.read_text(encoding="utf-8"))
    }
    gold = _load_json(package / "hidden" / "gold-submissions.json")
    cumulative_finding_ids = {
        finding["finding_id"] for checkpoint in gold.values() for finding in checkpoint["findings"]
    }

    assert source_finding_ids <= cumulative_finding_ids
    assert "F-PRV06-001" not in source_finding_ids


@pytest.mark.parametrize("variant_id", ["semantic_no_op_release", "response_assertion_only"])
def test_direct_closeout_decision_ids_and_lineage_follow_actual_topology(tmp_path: Path, variant_id: str) -> None:
    package = materialize_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / variant_id,
        variant_id=variant_id,
    )
    gold = _load_json(package / "hidden" / "gold-submissions.json")
    closeout = {decision["decision_id"]: decision for decision in gold["closeout_review"]["accepted_decisions"]}

    assert "D-PRV01-003" not in closeout
    assert closeout["D-PRV01-001"]["superseded_by"] == "D-PRV01-002"
    assert closeout["D-PRV01-002"] == {
        "basis_refs": ["REG-03 Rev G"],
        "decision_id": "D-PRV01-002",
        "item": "PRV-01",
        "status": "accepted",
    }
    assert closeout["D-PRV06-001"]["superseded_by"] == "D-PRV06-002"
    assert "not yet propagated" not in closeout["D-PRV06-001"]["supersession_reason"]


@pytest.mark.parametrize("variant_id", ["semantic_no_op_release", "response_assertion_only"])
def test_non_evidence_response_events_preserve_engineering_state(tmp_path: Path, variant_id: str) -> None:
    package = materialize_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / variant_id,
        variant_id=variant_id,
    )
    gold = _load_json(package / "hidden" / "gold-submissions.json")
    initial = gold["initial_review"]
    response = gold["response_review"]

    for field in (
        "evidence_refs",
        "review_matrix",
        "transition_decision",
        "findings",
        "closure_evidence_requests",
        "accepted_decisions",
        "readiness_decision",
    ):
        assert response[field] == initial[field]

    result = verify_drainage_model_lifecycle(package, _run_gold(package, tmp_path / "run"))
    initial_to_response = result["semantic_metrics"]["transitions"][0]
    assert initial_to_response["expected_update_count"] == 0
    assert initial_to_response["acquisition"] is None
    assert initial_to_response["retention"] == 1.0


def test_verifier_rejects_variant_identity_that_does_not_match_package_topology(tmp_path: Path) -> None:
    package = materialize_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / "package",
        variant_id="memo_closeout_missing",
    )
    run_dir = _run_gold(package, tmp_path / "run")
    claimed = get_drainage_model_variant("staged_full_correction").model_dump(mode="json")
    _write_json(package / "hidden" / "variant.json", claimed)

    with pytest.raises(ValueError, match="variant identity does not match materialized package content"):
        verify_drainage_model_lifecycle(package, run_dir)


@pytest.mark.parametrize("failure_kind", ["missing", "malformed"])
def test_verifier_rejects_missing_or_malformed_variant_identity(tmp_path: Path, failure_kind: str) -> None:
    package = materialize_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / "package",
    )
    variant_path = package / "hidden" / "variant.json"
    if failure_kind == "missing":
        variant_path.unlink()
    else:
        _write_json(variant_path, {"variant_id": DEFAULT_DRAINAGE_LIFECYCLE_VARIANT_ID})

    with pytest.raises(ValueError, match="invalid or missing drainage-model package variant identity"):
        verify_drainage_model_lifecycle(package, tmp_path / "unused-run")


def test_non_default_variant_is_recorded_in_manifest_and_index(tmp_path: Path) -> None:
    package = materialize_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / "package",
        variant_id="response_assertion_only",
    )
    run_dir = _run_gold(package, tmp_path / "run")
    verification = verify_drainage_model_lifecycle(package, run_dir)
    index_path = tmp_path / "experiment-index.jsonl"
    record = record_lifecycle_experiment(
        package_dir=package,
        run_dir=run_dir,
        agent=_experiment_agent(),
        verifier=verify_drainage_model_lifecycle,
        verification=verification,
        tool_schema=[],
        repository_dir=Path(__file__).resolve().parents[2],
        index_path=index_path,
    )

    manifest = _load_json(Path(record["manifest"]))
    index_entry = json.loads(index_path.read_text(encoding="utf-8").splitlines()[0])
    assert lifecycle_package_variant(package)["variant_id"] == "response_assertion_only"
    assert manifest["lifecycle"]["variant"]["variant_id"] == "response_assertion_only"
    assert index_entry["variant_id"] == "response_assertion_only"
    assert index_entry["adaptation"]["variation"] == {"change_topology": "response_assertion_only"}


def test_mismatched_variant_identity_cannot_enter_experiment_index(tmp_path: Path) -> None:
    package = materialize_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / "package",
        variant_id="memo_closeout_missing",
    )
    run_dir = _run_gold(package, tmp_path / "run")
    verification = verify_drainage_model_lifecycle(package, run_dir)
    _write_json(
        package / "hidden" / "variant.json",
        get_drainage_model_variant("staged_full_correction").model_dump(mode="json"),
    )
    index_path = tmp_path / "experiment-index.jsonl"

    with pytest.raises(ValueError, match="variant identity does not match materialized package content"):
        record_lifecycle_experiment(
            package_dir=package,
            run_dir=run_dir,
            agent=_experiment_agent(),
            verifier=verify_drainage_model_lifecycle,
            verification=verification,
            tool_schema=[],
            repository_dir=Path(__file__).resolve().parents[2],
            index_path=index_path,
        )

    assert not index_path.exists()
    assert not (run_dir / "experiment-manifest.json").exists()
    assert not (run_dir / "metrics.json").exists()


def test_valid_package_from_another_variant_cannot_be_paired_with_run(tmp_path: Path) -> None:
    template = "drainage-model-evidence-lifecycle-review"
    run_package = materialize_lifecycle(
        template,
        tmp_path / "run-package",
        variant_id="memo_closeout_missing",
    )
    supplied_package = materialize_lifecycle(
        template,
        tmp_path / "supplied-package",
        variant_id="response_assertion_only",
    )
    run_dir = _run_gold(run_package, tmp_path / "run")
    verification = verify_drainage_model_lifecycle(run_package, run_dir)
    index_path = tmp_path / "experiment-index.jsonl"

    with pytest.raises(EvidenceLifecycleError, match="package does not match lifecycle run"):
        record_lifecycle_experiment(
            package_dir=supplied_package,
            run_dir=run_dir,
            agent=_experiment_agent(),
            verifier=verify_drainage_model_lifecycle,
            verification=verification,
            tool_schema=[],
            repository_dir=Path(__file__).resolve().parents[2],
            index_path=index_path,
        )

    assert not index_path.exists()
    assert not (run_dir / "experiment-manifest.json").exists()
    assert not (run_dir / "metrics.json").exists()
    assert not (run_dir / "experiments").exists()


def test_prepared_workspace_never_contains_hidden_variant_metadata(tmp_path: Path) -> None:
    package = materialize_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / "package",
        variant_id="response_assertion_only",
    )
    _run_gold(package, tmp_path / "run")
    workspace = tmp_path / "run" / "workspace"

    assert not (workspace / "hidden").exists()
    visible_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in workspace.rglob("*")
        if path.is_file() and path.suffix in {".json", ".md"}
    )
    assert "response_assertion_only" not in visible_text


def test_variant_packages_have_distinct_host_side_hashes(tmp_path: Path) -> None:
    template = "drainage-model-evidence-lifecycle-review"
    digests = {
        hashlib.sha256(
            b"".join(
                relative.encode() + b"\0" + content
                for relative, content in _package_files(
                    materialize_lifecycle(template, tmp_path / variant_id, variant_id=variant_id)
                ).items()
            )
        ).hexdigest()
        for variant_id in EXPECTED_VARIANTS
    }

    assert len(digests) == len(EXPECTED_VARIANTS)


@pytest.mark.parametrize("variant_id", EXPECTED_VARIANTS)
def test_variant_identity_is_hidden_from_agent_visible_files(tmp_path: Path, variant_id: str) -> None:
    package = materialize_lifecycle(
        "drainage-model-evidence-lifecycle-review",
        tmp_path / variant_id,
        variant_id=variant_id,
    )

    visible_text = "\n".join(
        path.read_text(encoding="utf-8")
        for root in (package / "instructions", package / "releases")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )
    assert variant_id not in visible_text


def _run_gold(package: Path, run_dir: Path) -> Path:
    gold = _load_json(package / "hidden" / "gold-submissions.json")

    def resolve(context: dict) -> dict:
        _write_json(Path(context["submission_path"]), gold[context["checkpoint_id"]])
        return {"status": "completed"}

    run_evidence_lifecycle(
        package,
        run_dir,
        episode_environment=deterministic_episode_environment(resolve),
    )
    return run_dir


def _visible_tree_hash(package: Path) -> str:
    lines = []
    for root_name in ("instructions", "releases"):
        root = package / root_name
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.relative_to(package)}\n")
    return hashlib.sha256("".join(lines).encode()).hexdigest()


def _cumulative_release_text(package: Path, checkpoint_index: int) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for checkpoint_id in CHECKPOINT_IDS[: checkpoint_index + 1]
        for path in sorted((package / "releases" / checkpoint_id).rglob("*"))
        if path.is_file()
    )


def _package_files(package: Path) -> dict[str, bytes]:
    return {str(path.relative_to(package)): path.read_bytes() for path in sorted(package.rglob("*")) if path.is_file()}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _experiment_agent() -> dict:
    return {
        "model": "test-model",
        "adapter": "in_process",
        "execution_mode": "persistent_session",
        "memory_visibility_policy": "persistent_context",
        "max_turns_per_session": 1,
        "status": "completed",
        "sessions": [],
        "totals": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        },
    }
