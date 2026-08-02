# ABOUTME: Publishes and independently reloads immutable retrieval-state study evidence.
# ABOUTME: Recomputes reports from retained inputs instead of trusting stored conclusions.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter

from aec_bench.experiments.retrieval_state_continuity.analysis import analyse_study
from aec_bench.experiments.retrieval_state_continuity.contracts import (
    StudyManifest,
    StudyObservation,
    StudyPlan,
    StudyReport,
    TreatmentDelivery,
)
from aec_bench.experiments.retrieval_state_continuity.fixtures import build_fixture_evidence
from aec_bench.experiments.retrieval_state_continuity.planning import (
    build_provider_free_manifest,
    build_study_plan,
)
from aec_bench.meta_harness.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifact,
    ImmutableArtifactIntegrityError,
)

_MANIFEST_ADAPTER = TypeAdapter(StudyManifest)
_PLAN_ADAPTER = TypeAdapter(StudyPlan)
_DELIVERY_ADAPTER = TypeAdapter(TreatmentDelivery)
_OBSERVATION_ADAPTER = TypeAdapter(StudyObservation)
_REPORT_ADAPTER = TypeAdapter(StudyReport)


@dataclass(frozen=True, slots=True)
class PublishedStudy:
    """One complete immutable provider-free study specification bundle."""

    manifest: StudyManifest
    plan: StudyPlan
    report: StudyReport
    manifest_reference: ImmutableArtifact
    plan_reference: ImmutableArtifact
    delivery_references: tuple[ImmutableArtifact, ...]
    observation_references: tuple[ImmutableArtifact, ...]
    report_reference: ImmutableArtifact


def publish_provider_free_study(root: Path) -> PublishedStudy:
    """Publish, reload, and verify the complete provider-free analysis path."""

    repository = EvidenceRepository(Path(root), host_private=True)
    manifest = build_provider_free_manifest()
    plan = build_study_plan(manifest)
    evidence = build_fixture_evidence(manifest=manifest, plan=plan)
    report = analyse_study(
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
            model=item,
            adapter=_DELIVERY_ADAPTER,
        ).artifact
        for item in evidence.deliveries
    )
    observation_references = tuple(
        repository.publish_content_addressed_model(
            collection="observations",
            filename="observation.json",
            model=item,
            adapter=_OBSERVATION_ADAPTER,
        ).artifact
        for item in evidence.observations
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
        raise ImmutableArtifactIntegrityError("independently reloaded study report differs")
    return PublishedStudy(
        manifest=manifest,
        plan=plan,
        report=report,
        manifest_reference=manifest_reference,
        plan_reference=plan_reference,
        delivery_references=delivery_references,
        observation_references=observation_references,
        report_reference=report_reference,
    )


def reload_and_verify_study_report(*, root: Path, report_content_sha256: str) -> StudyReport:
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
    recomputed = analyse_study(
        manifest=manifest,
        plan=plan,
        deliveries=deliveries,
        observations=observations,
    )
    if recomputed != report:
        raise ImmutableArtifactIntegrityError("stored study report differs from independent recomputation")
    return report
