# ABOUTME: Exercises the typed Hx/px motif archive and its evidence-gated status promotions.
# ABOUTME: Proves content identity, lineage diversity, holdout isolation, and deterministic persistence.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from aec_bench.experimentation.governance.motifs import (
    HarnessProgramEvidenceReference,
    HarnessProgramMotif,
    MotifApplicabilityDescriptor,
    MotifLibrary,
    MotifPromotionDecision,
    MotifPromotionPolicy,
    MotifSelectionDecision,
    MotifSelectionOutcome,
    MotifSelectionReason,
    MotifSelectionRequest,
    MotifStatus,
    MotifStructuralDescriptor,
    MotifTemplate,
    PairedRepairEvidenceReference,
    QualityEvidenceReference,
    TransferEvidenceReference,
    apply_motif_promotion,
    decide_motif_promotion,
    resolve_motif_selection,
    select_motif,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _template(kind: str, label: str = "base") -> MotifTemplate:
    return MotifTemplate.create(
        kind=kind,
        payload={
            "entrypoint": f"{kind}.{label}",
            "stages": ["decompose", "execute", "verify"],
        },
    )


def _descriptor() -> MotifStructuralDescriptor:
    return MotifStructuralDescriptor(
        decomposition_pattern="recursive_partition",
        orchestration_pattern="bounded_parallel",
        decomposition_depth=3,
        maximum_parallelism=4,
        tool_surface=("artifact.read", "solver.run", "verifier.check"),
        state_mode="ephemeral",
    )


def _applicability() -> MotifApplicabilityDescriptor:
    return MotifApplicabilityDescriptor(
        task_pattern="review_first",
        stage_pattern="evidence_then_decision",
        stage_count=3,
        fanout_characteristic="bounded",
        branching_characteristic="conditional",
        evidence_surfaces=("source_pack", "verifier_gates"),
        required_tool_surface=("artifact.read", "verifier.check"),
        state_mode="ephemeral",
    )


def _repair(
    review_lineage_id: str,
    *,
    attempt: int = 1,
    accepted: bool = True,
    split: str = "repair_gate",
) -> PairedRepairEvidenceReference:
    return PairedRepairEvidenceReference.create(
        attempt_id=f"repair-{review_lineage_id}-{attempt}",
        decision_sha256=_sha(f"decision-{review_lineage_id}-{attempt}"),
        review_lineage_id=review_lineage_id,
        split=split,
        accepted=accepted,
        mean_reward_delta=0.2,
        validity_rate=1.0,
        estimated_cost_usd=0.5,
    )


def _harness_program_evidence(
    review_lineage_ids: tuple[str, ...],
    *,
    subject_hx_template_sha256: str | None = None,
    subject_px_template_sha256: str | None = None,
    split: str = "calibration",
    joint_incremental_uplift: float = 0.03,
    joint_incremental_uplift_lower_bound: float = 0.01,
) -> HarnessProgramEvidenceReference:
    return HarnessProgramEvidenceReference.create(
        analysis_sha256=_sha("harness-program-" + "-".join(review_lineage_ids)),
        subject_hx_template_sha256=subject_hx_template_sha256 or _template("hx").template_sha256,
        subject_px_template_sha256=subject_px_template_sha256 or _template("px").template_sha256,
        review_lineage_ids=review_lineage_ids,
        split=split,
        harness_main_effect=0.08,
        program_main_effect=0.06,
        interaction=0.03,
        joint_uplift=0.17,
        joint_incremental_uplift=joint_incremental_uplift,
        joint_incremental_uplift_lower_bound=joint_incremental_uplift_lower_bound,
        validity_rate=0.99,
        estimated_cost_usd=2.0,
        holdout_accessed_during_selection=False,
    )


def _quality(
    review_lineage_ids: tuple[str, ...],
    *,
    subject_hx_template_sha256: str | None = None,
    subject_px_template_sha256: str | None = None,
    objective_reward: float = 0.82,
    validity_rate: float = 0.99,
    estimated_cost_usd: float = 4.0,
    split: str = "calibration",
    holdout_accessed_during_selection: bool = False,
    included_in_harness_program_reference_sha256: str | None = None,
) -> QualityEvidenceReference:
    return QualityEvidenceReference.create(
        evaluation_sha256=_sha("quality-" + "-".join(review_lineage_ids) + str(objective_reward)),
        subject_hx_template_sha256=subject_hx_template_sha256 or _template("hx").template_sha256,
        subject_px_template_sha256=subject_px_template_sha256 or _template("px").template_sha256,
        review_lineage_ids=review_lineage_ids,
        split=split,
        objective_reward=objective_reward,
        validity_rate=validity_rate,
        estimated_cost_usd=estimated_cost_usd,
        holdout_accessed_during_selection=holdout_accessed_during_selection,
        included_in_harness_program_reference_sha256=included_in_harness_program_reference_sha256,
    )


def _transfer(
    *,
    selected_before_holdout: bool = True,
    archive_frozen: bool = True,
) -> TransferEvidenceReference:
    return TransferEvidenceReference.create(
        evaluation_sha256=_sha(f"transfer-{selected_before_holdout}-{archive_frozen}"),
        review_lineage_ids=("holdout-family-a", "holdout-family-b"),
        split="holdout",
        objective_reward=0.78,
        validity_rate=0.98,
        joint_uplift=0.18,
        joint_incremental_uplift=0.08,
        joint_incremental_uplift_lower_bound=0.02,
        estimated_cost_usd=3.0,
        selected_before_holdout=selected_before_holdout,
        archive_frozen=archive_frozen,
    )


def _motif(
    *,
    status: MotifStatus = MotifStatus.CANDIDATE,
    review_lineage_ids: tuple[str, ...] = ("family-a", "family-b"),
    objective_reward: float = 0.82,
    template_label: str = "base",
    repair_refs: tuple[PairedRepairEvidenceReference, ...] | None = None,
    transfer_refs: tuple[TransferEvidenceReference, ...] = (),
) -> HarnessProgramMotif:
    repairs = repair_refs or tuple(_repair(lineage_id) for lineage_id in review_lineage_ids)
    hx_template = _template("hx", template_label)
    px_template = _template("px", template_label)
    return HarnessProgramMotif.create(
        status=status,
        kernel_abi_sha256=_sha("kernel-abi-v1"),
        hx_template=hx_template,
        px_template=px_template,
        applicability=_applicability(),
        descriptor=_descriptor(),
        accepted_repair_refs=repairs,
        harness_program_evidence_refs=(
            _harness_program_evidence(
                review_lineage_ids,
                subject_hx_template_sha256=hx_template.template_sha256,
                subject_px_template_sha256=px_template.template_sha256,
            ),
        ),
        quality_evidence_refs=(
            _quality(
                review_lineage_ids,
                subject_hx_template_sha256=hx_template.template_sha256,
                subject_px_template_sha256=px_template.template_sha256,
                objective_reward=objective_reward,
            ),
        ),
        transfer_evidence_refs=transfer_refs,
    )


def test_motif_rejects_harness_program_evidence_earned_by_a_different_harness_program_pair() -> None:
    hx_template = _template("hx", "child")
    px_template = _template("px", "child")
    parent_harness_program = _harness_program_evidence(
        ("family-a", "family-b"),
        subject_hx_template_sha256=_template("hx", "parent").template_sha256,
        subject_px_template_sha256=_template("px", "parent").template_sha256,
    )

    with pytest.raises(ValidationError, match="harness-program evidence subject"):
        HarnessProgramMotif.create(
            status=MotifStatus.CANDIDATE,
            kernel_abi_sha256=_sha("kernel-abi-v1"),
            hx_template=hx_template,
            px_template=px_template,
            applicability=_applicability(),
            descriptor=_descriptor(),
            accepted_repair_refs=(_repair("family-a"), _repair("family-b")),
            harness_program_evidence_refs=(parent_harness_program,),
        )


def _policy() -> MotifPromotionPolicy:
    return MotifPromotionPolicy(
        minimum_supporting_review_lineages=2,
        minimum_objective_reward=0.75,
        minimum_validity_rate=0.95,
        minimum_joint_uplift=0.1,
        minimum_joint_incremental_uplift=0.02,
        minimum_joint_incremental_uplift_lower_bound=0.0,
        maximum_estimated_cost_usd=10.0,
        minimum_transfer_review_lineages=2,
        minimum_transfer_objective_reward=0.7,
        minimum_transfer_validity_rate=0.95,
        minimum_transfer_joint_uplift=0.1,
        minimum_transfer_joint_incremental_uplift=0.05,
        minimum_transfer_joint_incremental_uplift_lower_bound=0.0,
        maximum_transfer_estimated_cost_usd=5.0,
    )


def _selection_request(
    library: MotifLibrary,
    *,
    kernel_abi_sha256: str | None = None,
    applicability: MotifApplicabilityDescriptor | None = None,
    selection_split: str = "discovery",
    archive_frozen: bool = True,
    target_review_lineage_ids: tuple[str, ...] = (),
    eligible_statuses: tuple[MotifStatus, ...] | None = None,
) -> MotifSelectionRequest:
    return MotifSelectionRequest.create(
        archive_sha256=library.archive_sha256,
        archive_frozen=archive_frozen,
        kernel_abi_sha256=kernel_abi_sha256 or _sha("kernel-abi-v1"),
        applicability=applicability or _applicability(),
        selection_split=selection_split,
        target_review_lineage_ids=target_review_lineage_ids,
        eligible_statuses=eligible_statuses,
    )


def test_templates_and_motif_records_are_content_addressed() -> None:
    first = MotifTemplate.create(kind="hx", payload={"b": [2], "a": 1})
    second = MotifTemplate.create(kind="hx", payload={"a": 1, "b": [2]})

    assert first.template_sha256 == second.template_sha256

    motif = _motif()
    rebuilt = HarnessProgramMotif.model_validate(motif.model_dump(mode="json"))

    assert rebuilt.motif_sha256 == motif.motif_sha256
    assert "reward" not in MotifStructuralDescriptor.model_fields
    assert "objective_reward" not in MotifStructuralDescriptor.model_fields
    assert motif.objective_reward == pytest.approx(0.82)


def test_motif_template_nested_containers_are_immutable_without_changing_identity() -> None:
    template = MotifTemplate.create(
        kind="hx",
        payload={
            "entrypoint": "hx.review",
            "configuration": {
                "mode": "strict",
                "stages": ["decompose", "verify"],
            },
        },
    )
    original_sha256 = "6d737e022bcfde310ba63bbef25e999ce8bd076680d1cfa126427b8a54b7c33c"
    assert template.template_sha256 == original_sha256
    original_dump = template.model_dump(mode="json")
    configuration = cast(dict[str, Any], template.payload["configuration"])
    stages = cast(list[str], configuration["stages"])

    with pytest.raises(TypeError):
        configuration["mode"] = "permissive"
    with pytest.raises(TypeError):
        stages.append("bypass")

    assert template.template_sha256 == original_sha256
    assert template.model_dump(mode="json") == original_dump
    assert template.model_copy(deep=True).model_dump(mode="json") == original_dump


def test_quality_view_records_actual_cost_without_double_counting_shared_harness_program_run() -> None:
    harness_program_evidence = _harness_program_evidence(("family-a", "family-b"))
    quality = _quality(
        ("family-a", "family-b"),
        estimated_cost_usd=0.75,
        included_in_harness_program_reference_sha256=harness_program_evidence.reference_sha256,
    )
    motif = HarnessProgramMotif.create(
        status=MotifStatus.CANDIDATE,
        kernel_abi_sha256=_sha("kernel-abi-v1"),
        hx_template=_template("hx"),
        px_template=_template("px"),
        applicability=_applicability(),
        descriptor=_descriptor(),
        accepted_repair_refs=(_repair("family-a"), _repair("family-b")),
        harness_program_evidence_refs=(harness_program_evidence,),
        quality_evidence_refs=(quality,),
    )

    assert quality.estimated_cost_usd == pytest.approx(0.75)
    assert motif.estimated_cost_usd == pytest.approx(3.0)


@pytest.mark.parametrize(
    ("repair", "message"),
    [
        (_repair("family-a", accepted=False), "accepted paired repair"),
        (_repair("family-a", split="holdout"), "holdout evidence cannot support motif repair"),
    ],
)
def test_motif_rejects_rejected_or_holdout_repair_references(
    repair: PairedRepairEvidenceReference,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        HarnessProgramMotif.create(
            status=MotifStatus.CANDIDATE,
            kernel_abi_sha256=_sha("kernel-abi-v1"),
            hx_template=_template("hx"),
            px_template=_template("px"),
            applicability=_applicability(),
            descriptor=_descriptor(),
            accepted_repair_refs=(repair,),
        )


def test_motif_rejects_calibration_evidence_with_holdout_leakage() -> None:
    leaked = _quality(
        ("family-a",),
        split="holdout",
        holdout_accessed_during_selection=True,
    )

    with pytest.raises(ValidationError, match="holdout evidence cannot support motif selection"):
        HarnessProgramMotif.create(
            status=MotifStatus.CANDIDATE,
            kernel_abi_sha256=_sha("kernel-abi-v1"),
            hx_template=_template("hx"),
            px_template=_template("px"),
            applicability=_applicability(),
            descriptor=_descriptor(),
            accepted_repair_refs=(_repair("family-a"),),
            quality_evidence_refs=(leaked,),
        )


def test_repetitions_of_one_review_lineage_do_not_satisfy_reusable_support() -> None:
    motif = _motif(
        status=MotifStatus.PROVISIONAL,
        review_lineage_ids=("family-a",),
        repair_refs=(_repair("family-a", attempt=1), _repair("family-a", attempt=2)),
    )

    decision = decide_motif_promotion(motif, MotifStatus.REUSABLE, _policy())

    assert motif.supporting_review_lineage_ids == ("family-a",)
    assert decision.accepted is False
    assert decision.reasons == (
        "insufficient_distinct_review_lineages",
        "insufficient_distinct_calibration_review_lineages",
    )


def test_reusable_promotion_requires_harness_program_and_quality_evidence_from_calibration() -> None:
    motif = _motif(status=MotifStatus.PROVISIONAL)
    discovery_harness_program = _harness_program_evidence(
        ("family-a", "family-b"),
        subject_hx_template_sha256=motif.hx_template.template_sha256,
        subject_px_template_sha256=motif.px_template.template_sha256,
        split="discovery",
    )
    discovery_quality = _quality(
        ("family-a", "family-b"),
        subject_hx_template_sha256=motif.hx_template.template_sha256,
        subject_px_template_sha256=motif.px_template.template_sha256,
        split="discovery",
    )
    motif = HarnessProgramMotif.create(
        status=motif.status,
        kernel_abi_sha256=motif.kernel_abi_sha256,
        hx_template=motif.hx_template,
        px_template=motif.px_template,
        applicability=motif.applicability,
        descriptor=motif.descriptor,
        accepted_repair_refs=motif.accepted_repair_refs,
        harness_program_evidence_refs=(discovery_harness_program,),
        quality_evidence_refs=(discovery_quality,),
    )

    decision = decide_motif_promotion(motif, MotifStatus.REUSABLE, _policy())

    assert decision.accepted is False
    assert "harness_program_evidence_must_use_calibration_split" in decision.reasons
    assert "quality_evidence_must_use_calibration_split" in decision.reasons


def test_reusable_promotion_requires_two_distinct_calibration_review_lineages() -> None:
    motif = _motif(status=MotifStatus.PROVISIONAL)
    one_task_set_study = _harness_program_evidence(
        ("family-a",),
        subject_hx_template_sha256=motif.hx_template.template_sha256,
        subject_px_template_sha256=motif.px_template.template_sha256,
    )
    one_task_set_quality = _quality(
        ("family-a",),
        subject_hx_template_sha256=motif.hx_template.template_sha256,
        subject_px_template_sha256=motif.px_template.template_sha256,
    )
    motif = HarnessProgramMotif.create(
        status=motif.status,
        kernel_abi_sha256=motif.kernel_abi_sha256,
        hx_template=motif.hx_template,
        px_template=motif.px_template,
        applicability=motif.applicability,
        descriptor=motif.descriptor,
        accepted_repair_refs=motif.accepted_repair_refs,
        harness_program_evidence_refs=(one_task_set_study,),
        quality_evidence_refs=(one_task_set_quality,),
    )

    decision = decide_motif_promotion(motif, MotifStatus.REUSABLE, _policy())

    assert decision.accepted is False
    assert "insufficient_distinct_calibration_review_lineages" in decision.reasons


@pytest.mark.parametrize(
    ("motif", "target"),
    [
        (_motif(status=MotifStatus.PROVISIONAL), MotifStatus.REUSABLE),
        (
            _motif(status=MotifStatus.REUSABLE, transfer_refs=(_transfer(),)),
            MotifStatus.TRANSFER_VALIDATED,
        ),
    ],
)
def test_pure_decision_cannot_cross_a_governed_motif_status_edge(
    motif: HarnessProgramMotif,
    target: MotifStatus,
) -> None:
    decision = decide_motif_promotion(motif, target, _policy())

    assert decision.accepted is True
    with pytest.raises(ValueError, match="governed motif promotion"):
        apply_motif_promotion(motif, decision, _policy())


@pytest.mark.parametrize(
    ("harness_program_evidence", "reason"),
    [
        (
            _harness_program_evidence(("family-a", "family-b"), joint_incremental_uplift=0.01),
            "minimum_joint_incremental_uplift_not_met",
        ),
        (
            _harness_program_evidence(
                ("family-a", "family-b"),
                joint_incremental_uplift_lower_bound=-0.01,
            ),
            "minimum_joint_incremental_uplift_lower_bound_not_met",
        ),
    ],
)
def test_reusable_promotion_requires_joint_incremental_strength(
    harness_program_evidence: HarnessProgramEvidenceReference,
    reason: str,
) -> None:
    candidate = _motif(status=MotifStatus.PROVISIONAL)
    candidate = HarnessProgramMotif.create(
        status=candidate.status,
        kernel_abi_sha256=candidate.kernel_abi_sha256,
        hx_template=candidate.hx_template,
        px_template=candidate.px_template,
        applicability=candidate.applicability,
        descriptor=candidate.descriptor,
        accepted_repair_refs=candidate.accepted_repair_refs,
        harness_program_evidence_refs=(harness_program_evidence,),
        quality_evidence_refs=candidate.quality_evidence_refs,
    )

    decision = decide_motif_promotion(candidate, MotifStatus.REUSABLE, _policy())

    assert decision.accepted is False
    assert reason in decision.reasons


@pytest.mark.parametrize(
    ("transfer", "reason"),
    [
        (_transfer(selected_before_holdout=False), "holdout_selection_leakage"),
        (_transfer(archive_frozen=False), "holdout_archive_not_frozen"),
    ],
)
def test_transfer_promotion_fails_closed_on_holdout_leakage(
    transfer: TransferEvidenceReference,
    reason: str,
) -> None:
    motif = _motif(status=MotifStatus.REUSABLE, transfer_refs=(transfer,))

    decision = decide_motif_promotion(motif, MotifStatus.TRANSFER_VALIDATED, _policy())

    assert decision.accepted is False
    assert reason in decision.reasons


def test_library_add_query_and_archive_hash_are_deterministic() -> None:
    lower = _motif(objective_reward=0.76, template_label="lower")
    higher = _motif(objective_reward=0.91, template_label="higher")

    forward = MotifLibrary.create().add(lower).add(higher)
    reverse = MotifLibrary.create().add(higher).add(lower)
    queried = forward.query(
        kernel_abi_sha256=_sha("kernel-abi-v1"),
        descriptor=_descriptor(),
        statuses=(MotifStatus.CANDIDATE,),
    )

    assert forward.archive_sha256 == reverse.archive_sha256
    assert forward.motifs == reverse.motifs
    assert [motif.motif_sha256 for motif in queried] == [
        higher.motif_sha256,
        lower.motif_sha256,
    ]
    assert forward.add(higher) == forward


def test_library_save_load_round_trip_and_detects_tampering(tmp_path: Path) -> None:
    library = MotifLibrary.create((_motif(),))
    path = tmp_path / "motifs.json"

    library.save(path)
    loaded = MotifLibrary.load(path)

    assert loaded == library
    assert path.read_text(encoding="utf-8").endswith("\n")

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["motifs"][0]["status"] = MotifStatus.RETIRED.value
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError, match="motif_sha256 must bind"):
        MotifLibrary.load(path)


def test_rejected_decision_cannot_be_applied() -> None:
    motif = _motif(status=MotifStatus.PROVISIONAL, review_lineage_ids=("family-a",))
    decision = decide_motif_promotion(motif, MotifStatus.REUSABLE, _policy())

    with pytest.raises(ValueError, match="rejected motif promotion"):
        apply_motif_promotion(motif, decision, _policy())


def test_forged_accepted_promotion_decision_cannot_bypass_policy() -> None:
    candidate = _motif(status=MotifStatus.CANDIDATE, review_lineage_ids=("family-a",))
    forged = MotifPromotionDecision.create(
        motif_sha256=candidate.motif_sha256,
        current_status=candidate.status,
        target_status=MotifStatus.TRANSFER_VALIDATED,
        reasons=(),
    )

    with pytest.raises(ValueError, match="does not match the current evidence gate"):
        apply_motif_promotion(candidate, forged, _policy())


def test_holdout_transfer_lineages_must_be_unseen_during_selection() -> None:
    overlapping_transfer = TransferEvidenceReference.create(
        evaluation_sha256=_sha("overlapping-transfer"),
        review_lineage_ids=("family-a", "holdout-family-b"),
        split="holdout",
        objective_reward=0.8,
        validity_rate=1.0,
        joint_uplift=0.2,
        joint_incremental_uplift=0.1,
        joint_incremental_uplift_lower_bound=0.03,
        estimated_cost_usd=1.0,
        selected_before_holdout=True,
        archive_frozen=True,
    )
    motif = _motif(status=MotifStatus.REUSABLE, transfer_refs=(overlapping_transfer,))

    decision = decide_motif_promotion(motif, MotifStatus.TRANSFER_VALIDATED, _policy())

    assert decision.accepted is False
    assert "holdout_review_lineage_seen_during_selection" in decision.reasons


def test_selection_is_deterministic_and_uses_only_prebound_calibration_quality() -> None:
    probe_by_label = {
        label: _motif(status=MotifStatus.REUSABLE, template_label=label) for label in ("rank-a", "rank-b")
    }
    lower_label, higher_label = tuple(probe_by_label)
    structurally_first = _motif(
        status=MotifStatus.REUSABLE,
        objective_reward=0.76,
        template_label=lower_label,
    )
    higher_reward = _motif(
        status=MotifStatus.REUSABLE,
        objective_reward=0.99,
        template_label=higher_label,
    )
    forward = MotifLibrary.create((structurally_first, higher_reward))
    reverse = MotifLibrary.create((higher_reward, structurally_first))

    forward_decision = select_motif(forward, _selection_request(forward))
    reverse_decision = select_motif(reverse, _selection_request(reverse))

    assert forward.archive_sha256 == reverse.archive_sha256
    assert forward_decision == reverse_decision
    assert forward_decision.outcome is MotifSelectionOutcome.SELECTED
    assert forward_decision.selected_motif_sha256 == higher_reward.motif_sha256
    assert forward_decision.selected_hx_template == higher_reward.hx_template
    assert forward_decision.selected_px_template == higher_reward.px_template
    assert "reward" not in MotifSelectionRequest.model_fields
    assert "objective_reward" not in MotifSelectionRequest.model_fields
    assert "reward" not in MotifSelectionDecision.model_fields
    assert "objective_reward" not in MotifSelectionDecision.model_fields


def test_selection_prefers_transfer_validated_status_before_template_tie_break() -> None:
    reusable = _motif(status=MotifStatus.REUSABLE, template_label="reusable")
    transfer_validated = _motif(
        status=MotifStatus.TRANSFER_VALIDATED,
        template_label="transfer-validated",
    )
    library = MotifLibrary.create((reusable, transfer_validated))

    decision = select_motif(library, _selection_request(library))

    assert decision.outcome is MotifSelectionOutcome.SELECTED
    assert decision.selected_motif_sha256 == transfer_validated.motif_sha256


def test_selection_rejects_kernel_abi_mismatch() -> None:
    library = MotifLibrary.create((_motif(status=MotifStatus.REUSABLE),))
    request = _selection_request(library, kernel_abi_sha256=_sha("kernel-abi-v2"))

    decision = select_motif(library, request)

    assert decision.outcome is MotifSelectionOutcome.NO_SELECTION
    assert decision.reasons == (MotifSelectionReason.KERNEL_ABI_MISMATCH,)
    assert decision.selected_motif_sha256 is None
    assert resolve_motif_selection(library, request, decision) is None


def test_selection_rejects_a_motif_that_has_already_seen_the_target_review_lineage() -> None:
    reusable = _motif(status=MotifStatus.REUSABLE)
    library = MotifLibrary.create((reusable,))
    request = _selection_request(
        library,
        target_review_lineage_ids=("family-a", "holdout-family"),
    )

    decision = select_motif(library, request)

    assert decision.outcome is MotifSelectionOutcome.NO_SELECTION
    assert decision.reasons == (MotifSelectionReason.TARGET_REVIEW_LINEAGE_ALREADY_SEEN,)
    assert decision.target_review_lineage_ids == ("family-a", "holdout-family")


def test_default_selection_eligibility_excludes_provisional_motifs() -> None:
    provisional = _motif(status=MotifStatus.PROVISIONAL)
    library = MotifLibrary.create((provisional,))
    request = _selection_request(library)

    decision = select_motif(library, request)

    assert request.eligible_statuses == (
        MotifStatus.REUSABLE,
        MotifStatus.TRANSFER_VALIDATED,
    )
    assert decision.outcome is MotifSelectionOutcome.NO_SELECTION
    assert decision.reasons == (MotifSelectionReason.NO_ELIGIBLE_MOTIF_MATCH,)


def test_holdout_split_is_rejected_before_motif_selection() -> None:
    library = MotifLibrary.create((_motif(status=MotifStatus.REUSABLE),))
    request = _selection_request(library, selection_split="holdout")

    decision = select_motif(library, request)

    assert decision.outcome is MotifSelectionOutcome.NO_SELECTION
    assert decision.reasons == (MotifSelectionReason.HOLDOUT_SELECTION_FORBIDDEN,)
    assert decision.selected_hx_template is None
    assert decision.selected_px_template is None


def test_selection_requires_an_explicitly_frozen_matching_archive_identity() -> None:
    reusable = _motif(status=MotifStatus.REUSABLE)
    library = MotifLibrary.create((reusable,))

    unfrozen_request = _selection_request(library, archive_frozen=False)
    unfrozen_decision = select_motif(library, unfrozen_request)

    assert unfrozen_decision.reasons == (MotifSelectionReason.ARCHIVE_NOT_FROZEN,)

    frozen_request = _selection_request(library)
    changed_library = library.add(_motif(status=MotifStatus.REUSABLE, template_label="later"))
    changed_decision = select_motif(changed_library, frozen_request)

    assert changed_library.archive_sha256 != frozen_request.archive_sha256
    assert changed_decision.outcome is MotifSelectionOutcome.NO_SELECTION
    assert changed_decision.reasons == (MotifSelectionReason.ARCHIVE_IDENTITY_MISMATCH,)


def test_selection_rejection_reasons_and_status_identity_are_canonical() -> None:
    library = MotifLibrary.create((_motif(status=MotifStatus.REUSABLE),))
    request = MotifSelectionRequest.create(
        archive_sha256=_sha("different-archive"),
        archive_frozen=False,
        kernel_abi_sha256=_sha("kernel-abi-v1"),
        applicability=_applicability(),
        selection_split="holdout",
        eligible_statuses=(MotifStatus.TRANSFER_VALIDATED, MotifStatus.REUSABLE),
    )
    canonical_request = MotifSelectionRequest.create(
        archive_sha256=_sha("different-archive"),
        archive_frozen=False,
        kernel_abi_sha256=_sha("kernel-abi-v1"),
        applicability=_applicability(),
        selection_split="holdout",
        eligible_statuses=(MotifStatus.REUSABLE, MotifStatus.TRANSFER_VALIDATED),
    )

    decision = select_motif(library, request)

    assert request == canonical_request
    assert decision.reasons == (
        MotifSelectionReason.ARCHIVE_IDENTITY_MISMATCH,
        MotifSelectionReason.ARCHIVE_NOT_FROZEN,
        MotifSelectionReason.HOLDOUT_SELECTION_FORBIDDEN,
    )


def test_structural_miss_returns_a_typed_no_selection_decision() -> None:
    library = MotifLibrary.create((_motif(status=MotifStatus.REUSABLE),))
    different_applicability = _applicability().model_copy(update={"stage_count": 4})
    request = _selection_request(library, applicability=different_applicability)

    decision = select_motif(library, request)

    assert decision.outcome is MotifSelectionOutcome.NO_SELECTION
    assert decision.reasons == (MotifSelectionReason.NO_ELIGIBLE_MOTIF_MATCH,)
    assert decision.archive_sha256 == request.archive_sha256
    assert decision.kernel_abi_sha256 == request.kernel_abi_sha256
    assert decision.applicability == request.applicability
    assert decision.eligible_statuses == request.eligible_statuses
    assert decision.selection_split == request.selection_split


def test_selection_request_and_decision_detect_tampering() -> None:
    first = _motif(status=MotifStatus.REUSABLE)
    second = _motif(status=MotifStatus.REUSABLE, template_label="other")
    library = MotifLibrary.create((first, second))
    request = _selection_request(library)
    decision = select_motif(library, request)

    request_payload = request.model_dump(mode="json")
    request_payload["archive_sha256"] = _sha("different-archive")
    with pytest.raises(ValidationError, match="request_sha256 must bind"):
        MotifSelectionRequest.model_validate(request_payload)

    decision_payload = decision.model_dump(mode="json")
    decision_payload["selected_motif_sha256"] = _sha("forged-motif")
    with pytest.raises(ValidationError, match="decision_sha256 must bind"):
        MotifSelectionDecision.model_validate(decision_payload)

    unselected = next(motif for motif in library.motifs if motif.motif_sha256 != decision.selected_motif_sha256)
    forged = MotifSelectionDecision.create(request=request, selected_motif=unselected)
    with pytest.raises(ValueError, match="does not match deterministic motif selection"):
        resolve_motif_selection(library, request, forged)
