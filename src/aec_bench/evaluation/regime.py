# ABOUTME: Publishes, loads, and compares exact evaluation-regime artifacts.
# ABOUTME: Reports semantic policy paths instead of reconstructing compatibility from component hashes.

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import JsonValue

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.evaluation_plane import EvaluationRegime, EvaluationRegimeEnvelope
from aec_bench.contracts.evaluation_refs import EvaluationRegimeRef
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.ledger.artifact_repository import ArtifactRepository, canonical_model_bytes

EVALUATION_REGIME_MEDIA_TYPE = "application/vnd.aec-bench.evaluation-regime+json;version=1"


class EvaluationRegimeChange(FrozenStrictModel):
    """One semantic field change between two evaluation regimes."""

    path: NonEmptyStr
    kind: Literal["added", "removed", "changed"]
    before: JsonValue = None
    after: JsonValue = None


class EvaluationRegimeDiff(FrozenStrictModel):
    """Ordered semantic changes between two exact regime artifacts."""

    left: EvaluationRegimeRef
    right: EvaluationRegimeRef
    changes: tuple[EvaluationRegimeChange, ...]

    @property
    def identical(self) -> bool:
        return not self.changes


def publish_evaluation_regime(
    repository: ArtifactRepository,
    regime: EvaluationRegime,
) -> EvaluationRegimeRef:
    """Publish one regime envelope and return its only compatibility reference."""

    envelope = EvaluationRegimeEnvelope(regime=regime)
    artifact = repository.publish_model(value=envelope, media_type=EVALUATION_REGIME_MEDIA_TYPE)
    return EvaluationRegimeRef(regime_id=regime.regime_id, artifact=artifact)


def expected_evaluation_regime_ref(
    regime: EvaluationRegime,
    *,
    artifact_id: str | None = None,
) -> EvaluationRegimeRef:
    """Return the exact reference expected for canonical regime-envelope bytes."""

    payload = canonical_model_bytes(EvaluationRegimeEnvelope(regime=regime))
    digest = hashlib.sha256(payload).hexdigest()
    return EvaluationRegimeRef(
        regime_id=regime.regime_id,
        artifact=ArtifactRef(
            artifact_id=artifact_id or f"artifacts/sha256/{digest[:2]}/{digest}",
            sha256=digest,
            size_bytes=len(payload),
            media_type=EVALUATION_REGIME_MEDIA_TYPE,
        ),
    )


def validate_evaluation_regime_ref(regime: EvaluationRegime, ref: EvaluationRegimeRef) -> None:
    """Fail unless a reference identifies the canonical bytes of this regime."""

    expected = expected_evaluation_regime_ref(regime, artifact_id=ref.artifact.artifact_id)
    if ref != expected:
        raise ValueError("evaluation regime reference does not identify the supplied canonical regime bytes")


def load_evaluation_regime(
    repository: ArtifactRepository,
    ref: EvaluationRegimeRef,
) -> EvaluationRegime:
    """Load and verify one exact regime artifact."""

    if ref.artifact.media_type != EVALUATION_REGIME_MEDIA_TYPE:
        raise ValueError("evaluation regime reference has an unsupported media type")
    payload = repository.read_bytes(ref.artifact)
    envelope = EvaluationRegimeEnvelope.model_validate_json(payload)
    if envelope.regime.regime_id != ref.regime_id:
        raise ValueError("evaluation regime ID differs from its artifact reference")
    return envelope.regime


def resolve_evaluation_regime(
    repository: ArtifactRepository,
    artifact_id: str,
) -> tuple[EvaluationRegimeRef, EvaluationRegime]:
    """Resolve a canonical artifact ID for CLI inspection."""

    artifact = repository.resolve_ref(artifact_id=artifact_id, media_type=EVALUATION_REGIME_MEDIA_TYPE)
    payload = repository.read_bytes(artifact)
    envelope = EvaluationRegimeEnvelope.model_validate_json(payload)
    ref = EvaluationRegimeRef(regime_id=envelope.regime.regime_id, artifact=artifact)
    return ref, envelope.regime


def diff_evaluation_regimes(
    *,
    left_ref: EvaluationRegimeRef,
    left: EvaluationRegime,
    right_ref: EvaluationRegimeRef,
    right: EvaluationRegime,
) -> EvaluationRegimeDiff:
    """Describe semantic regime changes in stable path order."""

    changes: list[EvaluationRegimeChange] = []
    _collect_changes(
        path="regime",
        left=left.model_dump(mode="json"),
        right=right.model_dump(mode="json"),
        changes=changes,
    )
    return EvaluationRegimeDiff(left=left_ref, right=right_ref, changes=tuple(changes))


def _collect_changes(
    *,
    path: str,
    left: Any,
    right: Any,
    changes: list[EvaluationRegimeChange],
) -> None:
    if type(left) is not type(right):
        changes.append(EvaluationRegimeChange(path=path, kind="changed", before=left, after=right))
        return
    if isinstance(left, dict):
        left_keys = set(left)
        right_keys = set(right)
        for key in sorted(left_keys | right_keys):
            child_path = f"{path}.{key}"
            if key not in left:
                changes.append(EvaluationRegimeChange(path=child_path, kind="added", after=right[key]))
            elif key not in right:
                changes.append(EvaluationRegimeChange(path=child_path, kind="removed", before=left[key]))
            else:
                _collect_changes(path=child_path, left=left[key], right=right[key], changes=changes)
        return
    if isinstance(left, list):
        for index in range(max(len(left), len(right))):
            child_path = f"{path}[{index}]"
            if index >= len(left):
                changes.append(EvaluationRegimeChange(path=child_path, kind="added", after=right[index]))
            elif index >= len(right):
                changes.append(EvaluationRegimeChange(path=child_path, kind="removed", before=left[index]))
            else:
                _collect_changes(path=child_path, left=left[index], right=right[index], changes=changes)
        return
    if left != right:
        changes.append(EvaluationRegimeChange(path=path, kind="changed", before=left, after=right))


def format_evaluation_regime_diff(diff: EvaluationRegimeDiff) -> str:
    """Format a concise human-readable semantic diff."""

    if diff.identical:
        return "No semantic evaluation-regime changes."
    lines = []
    for change in diff.changes:
        before = json.dumps(change.before, sort_keys=True, ensure_ascii=False)
        after = json.dumps(change.after, sort_keys=True, ensure_ascii=False)
        if change.kind == "added":
            lines.append(f"+ {change.path}: {after}")
        elif change.kind == "removed":
            lines.append(f"- {change.path}: {before}")
        else:
            lines.append(f"~ {change.path}: {before} -> {after}")
    return "\n".join(lines)


__all__ = (
    "EVALUATION_REGIME_MEDIA_TYPE",
    "EvaluationRegimeChange",
    "EvaluationRegimeDiff",
    "diff_evaluation_regimes",
    "expected_evaluation_regime_ref",
    "format_evaluation_regime_diff",
    "load_evaluation_regime",
    "publish_evaluation_regime",
    "resolve_evaluation_regime",
    "validate_evaluation_regime_ref",
)
