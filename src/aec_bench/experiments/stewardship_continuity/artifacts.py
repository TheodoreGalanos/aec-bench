# ABOUTME: Publishes and independently reloads immutable stewardship-study evidence.
# ABOUTME: Recomputes every report instead of trusting persisted conclusions.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter

from aec_bench.experiments.stewardship_continuity.analysis import (
    analyse_continuity_study,
)
from aec_bench.experiments.stewardship_continuity.contracts import (
    ContinuityObservation,
    ContinuityStudyManifest,
    ContinuityStudyPlan,
    ContinuityStudyReport,
    TreatmentDeliveryRecord,
)
from aec_bench.experiments.stewardship_continuity.fixtures import (
    build_provider_free_fixture_evidence,
)
from aec_bench.experiments.stewardship_continuity.planning import (
    build_continuity_plan,
    build_provider_free_manifest,
)
from aec_bench.meta_harness.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifact,
    ImmutableArtifactIntegrityError,
)

_MANIFEST_ADAPTER = TypeAdapter(ContinuityStudyManifest)
_PLAN_ADAPTER = TypeAdapter(ContinuityStudyPlan)
_DELIVERY_ADAPTER = TypeAdapter(TreatmentDeliveryRecord)
_OBSERVATION_ADAPTER = TypeAdapter(ContinuityObservation)
_REPORT_ADAPTER = TypeAdapter(ContinuityStudyReport)


@dataclass(frozen=True, slots=True)
class PublishedContinuityStudy:
    """One complete immutable ASW-4A provider-free evidence bundle."""

    manifest: ContinuityStudyManifest
    plan: ContinuityStudyPlan
    report: ContinuityStudyReport
    manifest_reference: ImmutableArtifact
    plan_reference: ImmutableArtifact
    delivery_references: tuple[ImmutableArtifact, ...]
    observation_references: tuple[ImmutableArtifact, ...]
    report_reference: ImmutableArtifact


def publish_provider_free_fixture_study(
    root: Path,
) -> PublishedContinuityStudy:
    """Publish, reload, and verify the complete provider-free analysis path."""

    repository = EvidenceRepository(Path(root), host_private=True)
    manifest = build_provider_free_manifest()
    plan = build_continuity_plan(manifest)
    evidence = build_provider_free_fixture_evidence(
        manifest=manifest,
        plan=plan,
    )
    report = analyse_continuity_study(
        manifest=manifest,
        plan=plan,
        deliveries=evidence.deliveries,
        observations=evidence.observations,
    )

    manifest_reference = repository.publish_content_addressed_model(
        collection="manifests",
        filename="study-manifest.json",
        model=manifest,
        adapter=_MANIFEST_ADAPTER,
    ).artifact
    plan_reference = repository.publish_content_addressed_model(
        collection="plans",
        filename="study-plan.json",
        model=plan,
        adapter=_PLAN_ADAPTER,
    ).artifact
    delivery_references = tuple(
        repository.publish_content_addressed_model(
            collection="treatment-deliveries",
            filename="treatment-delivery.json",
            model=delivery,
            adapter=_DELIVERY_ADAPTER,
        ).artifact
        for delivery in evidence.deliveries
    )
    observation_references = tuple(
        repository.publish_content_addressed_model(
            collection="observations",
            filename="observation.json",
            model=observation,
            adapter=_OBSERVATION_ADAPTER,
        ).artifact
        for observation in evidence.observations
    )
    report_reference = repository.publish_content_addressed_model(
        collection="reports",
        filename="study-report.json",
        model=report,
        adapter=_REPORT_ADAPTER,
    ).artifact
    reloaded = reload_and_verify_study_report(
        root=repository.root,
        report_content_sha256=report.content_sha256,
    )
    if reloaded != report:
        raise ImmutableArtifactIntegrityError(
            "independently reloaded continuity report differs",
        )
    return PublishedContinuityStudy(
        manifest=manifest,
        plan=plan,
        report=report,
        manifest_reference=manifest_reference,
        plan_reference=plan_reference,
        delivery_references=delivery_references,
        observation_references=observation_references,
        report_reference=report_reference,
    )


def reload_and_verify_study_report(
    *,
    root: Path,
    report_content_sha256: str,
) -> ContinuityStudyReport:
    """Reload exact evidence and compare the stored report with recomputation."""

    repository = EvidenceRepository(Path(root), host_private=True)
    report = repository.load_content_addressed_model(
        collection="reports",
        content_sha256=report_content_sha256,
        filename="study-report.json",
        adapter=_REPORT_ADAPTER,
    ).model
    manifest = repository.load_content_addressed_model(
        collection="manifests",
        content_sha256=report.manifest_content_sha256,
        filename="study-manifest.json",
        adapter=_MANIFEST_ADAPTER,
    ).model
    plan = repository.load_content_addressed_model(
        collection="plans",
        content_sha256=report.plan_content_sha256,
        filename="study-plan.json",
        adapter=_PLAN_ADAPTER,
    ).model
    deliveries = tuple(
        repository.load_content_addressed_model(
            collection="treatment-deliveries",
            content_sha256=content_sha256,
            filename="treatment-delivery.json",
            adapter=_DELIVERY_ADAPTER,
        ).model
        for content_sha256 in report.delivery_content_sha256
    )
    observations = tuple(
        repository.load_content_addressed_model(
            collection="observations",
            content_sha256=content_sha256,
            filename="observation.json",
            adapter=_OBSERVATION_ADAPTER,
        ).model
        for content_sha256 in report.observation_content_sha256
    )
    recomputed = analyse_continuity_study(
        manifest=manifest,
        plan=plan,
        deliveries=deliveries,
        observations=observations,
    )
    if recomputed != report:
        raise ImmutableArtifactIntegrityError(
            "stored continuity report differs from independent recomputation",
        )
    return report
