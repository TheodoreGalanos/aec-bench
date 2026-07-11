# ABOUTME: Defines controlled semantic event sequences for SSC-03 evidence-lifecycle variants.
# ABOUTME: Derives public calibration packages from one canonical task-specific lifecycle seed.

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from pydantic import field_validator, model_validator

from aec_bench.contracts.adaptation import AdaptationCandidate, DerivationStep
from aec_bench.contracts.validators import NonEmptyStr, StrictModel

SSC03_LIFECYCLE_FAMILY_ID = "ssc03.drainage-model-evidence-lifecycle"
SSC03_LIFECYCLE_TEMPLATE_ID = "drainage-model-evidence-lifecycle-review"
DEFAULT_SSC03_LIFECYCLE_VARIANT_ID = "staged_full_correction"
_CHECKPOINT_IDS = ("initial_review", "response_review", "closeout_review")


class Ssc03EvidenceEvent(StrEnum):
    SEMANTIC_NO_OP = "semantic_no_op"
    ASSERT_INPUT_CORRECTION = "assert_input_correction"
    RELEASE_CORRECTED_MODEL_CHAIN = "release_corrected_model_chain"
    PROPAGATE_MEMO = "propagate_memo"
    ASSERT_MEMO_CLOSURE = "assert_memo_closure"


class Ssc03CheckpointVariantSpec(StrictModel):
    checkpoint_id: Literal["initial_review", "response_review", "closeout_review"]
    events: tuple[Ssc03EvidenceEvent, ...] = ()

    @field_validator("events")
    @classmethod
    def validate_unique_events(cls, events: tuple[Ssc03EvidenceEvent, ...]) -> tuple[Ssc03EvidenceEvent, ...]:
        if len(events) != len(set(events)):
            raise ValueError("checkpoint events must be unique")
        return events


class Ssc03LifecycleVariantSpec(StrictModel):
    schema_version: Literal["1"] = "1"
    variant_id: NonEmptyStr
    summary: NonEmptyStr
    visibility: Literal["public"] = "public"
    adaptation: AdaptationCandidate
    checkpoints: tuple[Ssc03CheckpointVariantSpec, ...]

    @field_validator("variant_id")
    @classmethod
    def validate_safe_variant_id(cls, variant_id: str) -> str:
        if re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", variant_id) is None:
            raise ValueError("variant_id must contain lowercase letters, digits, and single underscores")
        return variant_id

    @model_validator(mode="after")
    def validate_identity_and_event_sequence(self) -> Ssc03LifecycleVariantSpec:
        checkpoint_ids = tuple(checkpoint.checkpoint_id for checkpoint in self.checkpoints)
        if checkpoint_ids != _CHECKPOINT_IDS:
            raise ValueError("checkpoints must use the SSC-03 lifecycle order")
        if self.adaptation.family_id != SSC03_LIFECYCLE_FAMILY_ID:
            raise ValueError("adaptation family must match the SSC-03 lifecycle family")
        if self.adaptation.seed_task_id != SSC03_LIFECYCLE_TEMPLATE_ID:
            raise ValueError("adaptation seed task must match the SSC-03 lifecycle template")
        if self.adaptation.variation != {"change_topology": self.variant_id}:
            raise ValueError("adaptation variation must identify the lifecycle variant")

        response_events = self.checkpoints[1].events
        if len(response_events) != 1:
            raise ValueError("response_review must declare exactly one controlled event")
        closeout_events = self.checkpoints[2].events
        supported_closeout_events = {
            (Ssc03EvidenceEvent.PROPAGATE_MEMO,),
            (Ssc03EvidenceEvent.ASSERT_MEMO_CLOSURE,),
            (
                Ssc03EvidenceEvent.RELEASE_CORRECTED_MODEL_CHAIN,
                Ssc03EvidenceEvent.PROPAGATE_MEMO,
            ),
        }
        if closeout_events not in supported_closeout_events:
            raise ValueError("closeout_review event combination is not supported")

        corrected_model_chain = False
        for checkpoint in self.checkpoints:
            for event in checkpoint.events:
                _validate_event_checkpoint(event, checkpoint.checkpoint_id)
                if event is Ssc03EvidenceEvent.RELEASE_CORRECTED_MODEL_CHAIN:
                    if corrected_model_chain:
                        raise ValueError("corrected model chain may be released only once")
                    corrected_model_chain = True
                elif event in {Ssc03EvidenceEvent.PROPAGATE_MEMO, Ssc03EvidenceEvent.ASSERT_MEMO_CLOSURE}:
                    if not corrected_model_chain:
                        raise ValueError("memo propagation requires a corrected model chain")
        return self


@dataclass(frozen=True)
class Ssc03LifecycleVariantContent:
    releases: dict[str, dict[str, str]]
    gold_submissions: dict[str, dict[str, Any]]
    verifier_config: dict[str, Any]


def list_ssc03_lifecycle_variant_ids() -> tuple[str, ...]:
    """Return stable public SSC-03 variant IDs in lexical order."""
    return tuple(sorted(_VARIANTS))


def get_ssc03_lifecycle_variant(variant_id: str) -> Ssc03LifecycleVariantSpec:
    """Resolve one validated public SSC-03 lifecycle variant."""
    try:
        return _VARIANTS[variant_id].model_copy(deep=True)
    except KeyError as exc:
        known = ", ".join(list_ssc03_lifecycle_variant_ids())
        raise KeyError(f"Unknown SSC-03 lifecycle variant {variant_id!r}. Known: {known}") from exc


def validate_ssc03_lifecycle_variant_payload(payload: Any) -> Ssc03LifecycleVariantSpec:
    """Validate serialized variant identity against the immutable public registry."""
    candidate = Ssc03LifecycleVariantSpec.model_validate(payload)
    registered = get_ssc03_lifecycle_variant(candidate.variant_id)
    if candidate != registered:
        raise ValueError("variant contract does not match its registered SSC-03 specification")
    return candidate


def compile_ssc03_lifecycle_variant(
    variant_id: str | None,
    *,
    seed: Ssc03LifecycleVariantContent,
) -> tuple[Ssc03LifecycleVariantSpec, Ssc03LifecycleVariantContent]:
    """Derive one controlled package from the canonical SSC-03 lifecycle seed."""
    selected_id = variant_id or DEFAULT_SSC03_LIFECYCLE_VARIANT_ID
    spec = get_ssc03_lifecycle_variant(selected_id)
    builders: dict[
        tuple[tuple[Ssc03EvidenceEvent, ...], tuple[Ssc03EvidenceEvent, ...]],
        Callable[[Ssc03LifecycleVariantContent], Ssc03LifecycleVariantContent],
    ] = {
        (
            (Ssc03EvidenceEvent.RELEASE_CORRECTED_MODEL_CHAIN,),
            (Ssc03EvidenceEvent.PROPAGATE_MEMO,),
        ): _canonical_content,
        (
            (Ssc03EvidenceEvent.SEMANTIC_NO_OP,),
            (
                Ssc03EvidenceEvent.RELEASE_CORRECTED_MODEL_CHAIN,
                Ssc03EvidenceEvent.PROPAGATE_MEMO,
            ),
        ): _semantic_no_op_content,
        (
            (Ssc03EvidenceEvent.ASSERT_INPUT_CORRECTION,),
            (
                Ssc03EvidenceEvent.RELEASE_CORRECTED_MODEL_CHAIN,
                Ssc03EvidenceEvent.PROPAGATE_MEMO,
            ),
        ): _response_assertion_content,
        (
            (Ssc03EvidenceEvent.RELEASE_CORRECTED_MODEL_CHAIN,),
            (Ssc03EvidenceEvent.ASSERT_MEMO_CLOSURE,),
        ): _memo_closeout_missing_content,
    }
    event_topology = (spec.checkpoints[1].events, spec.checkpoints[2].events)
    content = builders[event_topology](seed)
    verifier_config = copy.deepcopy(content.verifier_config)
    verifier_config["allowed_evidence_refs"] = {
        checkpoint_id: list(content.gold_submissions[checkpoint_id]["evidence_refs"])
        for checkpoint_id in _CHECKPOINT_IDS
    }
    return spec, Ssc03LifecycleVariantContent(
        releases=content.releases,
        gold_submissions=content.gold_submissions,
        verifier_config=verifier_config,
    )


def _validate_event_checkpoint(event: Ssc03EvidenceEvent, checkpoint_id: str) -> None:
    allowed = {
        "initial_review": set(),
        "response_review": {
            Ssc03EvidenceEvent.SEMANTIC_NO_OP,
            Ssc03EvidenceEvent.ASSERT_INPUT_CORRECTION,
            Ssc03EvidenceEvent.RELEASE_CORRECTED_MODEL_CHAIN,
        },
        "closeout_review": {
            Ssc03EvidenceEvent.RELEASE_CORRECTED_MODEL_CHAIN,
            Ssc03EvidenceEvent.PROPAGATE_MEMO,
            Ssc03EvidenceEvent.ASSERT_MEMO_CLOSURE,
        },
    }
    if event not in allowed[checkpoint_id]:
        raise ValueError(f"event {event.value!r} is not valid at {checkpoint_id}")


def _variant(
    variant_id: str,
    summary: str,
    *,
    response_events: tuple[Ssc03EvidenceEvent, ...],
    closeout_events: tuple[Ssc03EvidenceEvent, ...],
) -> Ssc03LifecycleVariantSpec:
    lineage = (
        []
        if variant_id == DEFAULT_SSC03_LIFECYCLE_VARIANT_ID
        else [
            DerivationStep(
                axis="change_topology",
                parent_value=DEFAULT_SSC03_LIFECYCLE_VARIANT_ID,
                value=variant_id,
            )
        ]
    )
    return Ssc03LifecycleVariantSpec(
        variant_id=variant_id,
        summary=summary,
        adaptation=AdaptationCandidate(
            family_id=SSC03_LIFECYCLE_FAMILY_ID,
            seed_task_id=SSC03_LIFECYCLE_TEMPLATE_ID,
            variation_key=f"change_topology={variant_id}",
            variation={"change_topology": variant_id},
            derivation_lineage=lineage,
        ),
        checkpoints=(
            Ssc03CheckpointVariantSpec(checkpoint_id="initial_review"),
            Ssc03CheckpointVariantSpec(checkpoint_id="response_review", events=response_events),
            Ssc03CheckpointVariantSpec(checkpoint_id="closeout_review", events=closeout_events),
        ),
    )


def _canonical_content(seed: Ssc03LifecycleVariantContent) -> Ssc03LifecycleVariantContent:
    return copy.deepcopy(seed)


def _semantic_no_op_content(seed: Ssc03LifecycleVariantContent) -> Ssc03LifecycleVariantContent:
    content = copy.deepcopy(seed)
    initial = content.gold_submissions["initial_review"]
    response = _unchanged_response(initial)
    closeout = _single_release_closeout(content.gold_submissions, response)
    content.releases["response_review"] = {"administrative-note.md": _SEMANTIC_NO_OP_NOTE}
    content.releases["closeout_review"] = _direct_closeout_release(seed)
    _configure_direct_closeout_policy(content.verifier_config)
    return Ssc03LifecycleVariantContent(
        releases=content.releases,
        gold_submissions={
            "initial_review": initial,
            "response_review": response,
            "closeout_review": closeout,
        },
        verifier_config=content.verifier_config,
    )


def _response_assertion_content(seed: Ssc03LifecycleVariantContent) -> Ssc03LifecycleVariantContent:
    content = copy.deepcopy(seed)
    initial = content.gold_submissions["initial_review"]
    response = _unchanged_response(initial)
    closeout = _single_release_closeout(content.gold_submissions, response)
    content.releases["response_review"] = {"response-assertion.md": _INPUT_CORRECTION_ASSERTION}
    content.releases["closeout_review"] = _direct_closeout_release(seed)
    _configure_direct_closeout_policy(content.verifier_config)
    return Ssc03LifecycleVariantContent(
        releases=content.releases,
        gold_submissions={
            "initial_review": initial,
            "response_review": response,
            "closeout_review": closeout,
        },
        verifier_config=content.verifier_config,
    )


def _memo_closeout_missing_content(seed: Ssc03LifecycleVariantContent) -> Ssc03LifecycleVariantContent:
    content = copy.deepcopy(seed)
    response = content.gold_submissions["response_review"]
    closeout = copy.deepcopy(response)
    closeout["checkpoint_id"] = "closeout_review"
    closeout["evidence_refs"] = list(response["evidence_refs"]) + [
        "REG-03 Rev G",
        "RESP-03-CLOSEOUT-01 Rev A",
    ]
    closeout["accepted_decisions"] = _register_only_closeout_decisions(
        response["accepted_decisions"],
        content.gold_submissions["closeout_review"]["accepted_decisions"],
    )
    content.releases["closeout_review"] = {
        "document-register-rev-g.md": _MEMO_PENDING_REGISTER,
        "comment-response.md": _MEMO_CLOSURE_ASSERTION,
    }
    content.gold_submissions["closeout_review"] = closeout
    return content


def _unchanged_response(initial: dict[str, Any]) -> dict[str, Any]:
    response = copy.deepcopy(initial)
    response["checkpoint_id"] = "response_review"
    return response


def _direct_closeout_release(seed: Ssc03LifecycleVariantContent) -> dict[str, str]:
    release = {
        **copy.deepcopy(seed.releases["closeout_review"]),
        **copy.deepcopy(seed.releases["response_review"]),
    }
    release["comment-response.md"] = _DIRECT_CLOSEOUT_RESPONSE
    return release


def _configure_direct_closeout_policy(config: dict[str, Any]) -> None:
    config["decision_evidence_policy"]["D-PRV01-002"] = {
        "required": ["REG-03 Rev G"],
        "allowed": ["REG-03 Rev G"],
    }


def _single_release_closeout(
    canonical_gold: dict[str, dict[str, Any]],
    response: dict[str, Any],
) -> dict[str, Any]:
    canonical_initial = canonical_gold["initial_review"]
    canonical_response = canonical_gold["response_review"]
    canonical_closeout = canonical_gold["closeout_review"]
    response_additions = [
        reference
        for reference in canonical_response["evidence_refs"]
        if reference not in canonical_initial["evidence_refs"]
    ]
    closeout_additions = [
        reference
        for reference in canonical_closeout["evidence_refs"]
        if reference not in canonical_response["evidence_refs"]
    ]
    closeout = copy.deepcopy(canonical_closeout)
    closeout["evidence_refs"] = list(response["evidence_refs"]) + response_additions + closeout_additions
    closeout["findings"] = [
        {
            "finding_id": "F-PRV03-001",
            "item": "PRV-03",
            "status": "closed",
            "opened_at": "initial_review",
            "closed_at": "closeout_review",
            "closure_evidence": ["MANIFEST-03-042 Rev B"],
        }
    ]
    closeout["closure_evidence_requests"] = [
        {
            "request_id": "CER-001",
            "finding_id": "F-PRV03-001",
            "status": "closed",
            "required_evidence": ["current manifest citing CATCH-03-BASIS-01 Rev D"],
            "response_refs": ["MANIFEST-03-042 Rev B"],
        }
    ]
    closeout["accepted_decisions"] = _direct_closeout_decisions(canonical_initial["accepted_decisions"])
    return closeout


def _direct_closeout_decisions(initial: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions = copy.deepcopy(initial)
    by_id = {decision["decision_id"]: decision for decision in decisions}
    by_id["D-PRV01-001"].update(
        {
            "status": "superseded",
            "superseded_by": "D-PRV01-002",
            "supersession_reason": "REG-03 Rev G registers the combined correction and closeout release.",
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
            "superseded_by": "D-PRV06-002",
            "supersession_reason": "MEMO-03-DESIGN-01 Rev E propagates the replacement run/report object.",
        }
    )
    decisions.extend(
        [
            {
                "decision_id": "D-PRV01-002",
                "item": "PRV-01",
                "status": "accepted",
                "basis_refs": ["REG-03 Rev G"],
            },
            {
                "decision_id": "D-PRV03-001",
                "item": "PRV-03",
                "status": "accepted",
                "basis_refs": [
                    "MANIFEST-03-042 Rev B",
                    "CATCH-03-BASIS-01 Rev D",
                    "RAIN-03-BASIS-01 Rev C",
                ],
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
            {
                "decision_id": "D-PRV06-002",
                "item": "PRV-06",
                "status": "accepted",
                "basis_refs": ["MEMO-03-DESIGN-01 Rev E", "REPORT-03-043 Rev A"],
            },
        ]
    )
    return decisions


def _register_only_closeout_decisions(
    response: list[dict[str, Any]],
    canonical_closeout: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    decisions = copy.deepcopy(response)
    by_id = {decision["decision_id"]: decision for decision in decisions}
    by_id["D-PRV01-002"].update(
        {
            "status": "superseded",
            "superseded_by": "D-PRV01-003",
            "supersession_reason": (
                "REG-03 Rev G records the closeout assertion while the required memo remains absent."
            ),
        }
    )
    canonical_by_id = {decision["decision_id"]: decision for decision in canonical_closeout}
    decisions.append(copy.deepcopy(canonical_by_id["D-PRV01-003"]))
    return decisions


_VARIANTS = {
    spec.variant_id: spec
    for spec in (
        _variant(
            "staged_full_correction",
            "A corrected manifest and rerun arrive at response, followed by the propagated design memo at closeout.",
            response_events=(Ssc03EvidenceEvent.RELEASE_CORRECTED_MODEL_CHAIN,),
            closeout_events=(Ssc03EvidenceEvent.PROPAGATE_MEMO,),
        ),
        _variant(
            "semantic_no_op_release",
            "An unrelated administrative note arrives before the full corrected chain is released at closeout.",
            response_events=(Ssc03EvidenceEvent.SEMANTIC_NO_OP,),
            closeout_events=(
                Ssc03EvidenceEvent.RELEASE_CORRECTED_MODEL_CHAIN,
                Ssc03EvidenceEvent.PROPAGATE_MEMO,
            ),
        ),
        _variant(
            "response_assertion_only",
            "A response asserts correction without artifacts; the complete corrected chain arrives at closeout.",
            response_events=(Ssc03EvidenceEvent.ASSERT_INPUT_CORRECTION,),
            closeout_events=(
                Ssc03EvidenceEvent.RELEASE_CORRECTED_MODEL_CHAIN,
                Ssc03EvidenceEvent.PROPAGATE_MEMO,
            ),
        ),
        _variant(
            "memo_closeout_missing",
            "The rerun is corrected, but closeout asserts memo propagation without supplying the revised memo.",
            response_events=(Ssc03EvidenceEvent.RELEASE_CORRECTED_MODEL_CHAIN,),
            closeout_events=(Ssc03EvidenceEvent.ASSERT_MEMO_CLOSURE,),
        ),
    )
}


_SEMANTIC_NO_OP_NOTE = """# Administrative Runtime Notice

This notice is not a registered project source.

The document-control filing location has changed. No model input, run, report, memo, or governing revision changes.
"""

_INPUT_CORRECTION_ASSERTION = """# Model Custodian Runtime Assertion

This assertion is not a registered project source.

The model custodian states that the catchment input has been corrected and the model rerun. The revised manifest,
run register, and report are not included in this release and must not be assumed.
"""

_DIRECT_CLOSEOUT_RESPONSE = """# Combined Correction and Closeout Response

Source: RESP-03-CLOSEOUT-01 Rev A

Finding F-PRV03-001 is nominated for closure against MANIFEST-03-042 Rev B. The corrected manifest, rerun, report,
and propagated design memo are supplied together in this release. The reviewer must independently check the full
chain before closing the finding or accepting issue readiness.
"""

_MEMO_PENDING_REGISTER = """# Closeout Document Register

Register: REG-03 Rev G
Supersedes: REG-03 Rev F

| Document | Revision | Status |
|---|---|---|
| CATCH-03-BASIS-01 | Rev D | current |
| RAIN-03-BASIS-01 | Rev C | current |
| MANIFEST-03-042 | Rev B | current submission |
| RUN-03-REGISTER-01 | Rev F | current |
| REPORT-03-043 | Rev A | current submission |
| MEMO-03-DESIGN-01 | Rev D | current; revision pending |
| CRIT-SSC03-001 | Rev C | governing criteria |
| COMMENT-03-REGISTER-01 | Rev A | current |
| RESP-03-CLOSEOUT-01 | Rev A | current response assertion |
"""

_MEMO_CLOSURE_ASSERTION = """# Closeout Comment Response

Source: RESP-03-CLOSEOUT-01 Rev A

The design custodian states that MEMO-03-DESIGN-01 Rev E propagates RUN-03-043 and REPORT-03-043 Rev A. The revised
memo is not included in this release, so the assertion alone is not closure evidence.
"""
