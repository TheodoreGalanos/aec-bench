# ABOUTME: Serves semantic datasets and immutable publication labels to the Web UI.
# ABOUTME: Uses exact references for result lookup and integrity without exposing routine hashes.

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, status

from aec_bench.contracts.dataset import dataset_reference_key
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.dataset.publication import resolve_dataset, verify_resolved_dataset
from aec_bench.dataset.storage import list_datasets, list_publications
from aec_bench.ledger.reader import read_trial_records
from aec_bench.web.dependencies import get_web_settings
from aec_bench.web.schemas import (
    DatasetDetailResponse,
    DatasetListItemSchema,
    DatasetsListResponse,
    DatasetTaskEntrySchema,
    ExperimentResultSchema,
    IntegrityResultSchema,
)
from aec_bench.web.utils import reward_css_class

router = APIRouter()


@router.get("/api/datasets")
def datasets_list_api(request: Request) -> DatasetsListResponse:
    """Return stable dataset IDs and human publication labels."""

    settings = get_web_settings(request)
    manifests = list_datasets(settings.datasets_root)
    labels: dict[str, list[str]] = defaultdict(list)
    for publication in list_publications(settings.datasets_root):
        labels[publication.dataset_ref.dataset_id].append(publication.label)
    datasets = [
        DatasetListItemSchema(
            dataset_id=manifest.dataset_id,
            description=manifest.description,
            task_count=len(manifest.tasks),
            labels=sorted(labels[manifest.dataset_id]),
        )
        for manifest in manifests
    ]
    return DatasetsListResponse(
        datasets=datasets,
        total_datasets=len(datasets),
        total_tasks=sum(item.task_count for item in datasets),
    )


@router.get("/api/datasets/{dataset_id}/{label}")
def dataset_detail_api(
    request: Request,
    dataset_id: str,
    label: str,
    tab: str | None = None,
) -> DatasetDetailResponse:
    """Return one published dataset resolved to its exact immutable reference."""

    settings = get_web_settings(request)
    resolved = resolve_dataset(
        datasets_root=settings.datasets_root,
        selector=f"{dataset_id}@{label}",
        project_root=settings.tasks_root.parent,
    )
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset publication not found")

    exact_id = dataset_reference_key(resolved.reference)
    by_experiment: dict[str, list[TrialRecord]] = defaultdict(list)
    for record in read_trial_records(settings.ledger_root):
        if record.dataset_id == exact_id:
            by_experiment[record.experiment_id].append(record)
    experiment_results = []
    for experiment_id, trials in sorted(by_experiment.items()):
        rewards = [trial.evaluation.reward for trial in trials]
        mean_reward = round(sum(rewards) / len(rewards), 3) if rewards else 0.0
        experiment_results.append(
            ExperimentResultSchema(
                experiment_id=experiment_id,
                trial_count=len(trials),
                mean_reward=mean_reward,
                reward_class=reward_css_class(mean_reward),
                models=sorted({trial.agent.model for trial in trials}),
            )
        )

    integrity_results: list[IntegrityResultSchema] = []
    integrity_unexpected: list[str] = []
    if tab == "integrity":
        integrity = verify_resolved_dataset(
            resolved,
            datasets_root=settings.datasets_root,
            project_root=settings.tasks_root.parent,
        )
        missing = set(integrity.missing)
        modified = set(integrity.modified)
        integrity_unexpected = list(integrity.unexpected)
        for task in resolved.manifest.tasks:
            task_status = (
                "missing" if task.task_id in missing else "modified" if task.task_id in modified else "verified"
            )
            integrity_results.append(IntegrityResultSchema(task_id=task.task_id, status=task_status))

    return DatasetDetailResponse(
        dataset_id=resolved.manifest.dataset_id,
        label=label,
        description=resolved.manifest.description,
        reference_kind=resolved.reference.kind,
        task_count=len(resolved.manifest.tasks),
        tasks=[
            DatasetTaskEntrySchema(task_id=task.task_id, path=task.path, task_kind=task.task_kind)
            for task in resolved.manifest.tasks
        ],
        experiment_results=experiment_results,
        integrity_results=integrity_results,
        integrity_unexpected=integrity_unexpected,
    )
