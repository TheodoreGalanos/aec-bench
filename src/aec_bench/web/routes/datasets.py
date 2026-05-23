# ABOUTME: Datasets route serving the versioned benchmark dataset explorer.
# ABOUTME: List view with dataset cards and detail view with tasks/results/integrity tabs.

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, status

from aec_bench.dataset.integrity import verify_dataset_integrity
from aec_bench.dataset.storage import list_datasets
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
    """Return list of all datasets as JSON."""
    settings = get_web_settings(request)
    manifests = list_datasets(settings.datasets_root)
    total_tasks = sum(len(m.tasks) for m in manifests)

    datasets = [
        DatasetListItemSchema(
            name=m.name,
            version=m.version,
            summary=m.description.summary,
            task_count=len(m.tasks),
            domains=m.description.domains,
            content_hash=m.content_hash,
        )
        for m in manifests
    ]

    return DatasetsListResponse(
        datasets=datasets,
        total_datasets=len(manifests),
        total_tasks=total_tasks,
    )


@router.get("/api/datasets/{name}/{version}")
def dataset_detail_api(
    request: Request,
    name: str,
    version: str,
    tab: str | None = None,
) -> DatasetDetailResponse:
    """Return dataset detail including tasks, experiment results, and integrity data as JSON."""
    settings = get_web_settings(request)
    manifests = list_datasets(settings.datasets_root)

    manifest = next(
        (m for m in manifests if m.name == name and m.version == version),
        None,
    )
    if manifest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    dataset_id = f"{name}@{version}"

    # Always load experiment results
    records = read_trial_records(settings.ledger_root)
    ds_records = [r for r in records if getattr(r, "dataset_id", None) == dataset_id]
    by_exp: dict[str, list] = defaultdict(list)
    for r in ds_records:
        by_exp[r.experiment_id].append(r)

    experiment_results = []
    for exp_id, trials in sorted(by_exp.items()):
        rewards = [t.evaluation.reward for t in trials]
        mean_reward = round(sum(rewards) / len(rewards), 3) if rewards else 0.0
        models = sorted({t.agent.model for t in trials})
        experiment_results.append(
            ExperimentResultSchema(
                experiment_id=exp_id,
                trial_count=len(trials),
                mean_reward=mean_reward,
                reward_class=reward_css_class(mean_reward),
                models=models,
            )
        )

    # Load integrity results when tab=integrity is requested
    integrity_results = []
    if tab == "integrity":
        result = verify_dataset_integrity(
            manifest.tasks,
            project_root=settings.tasks_root.parent,
        )
        drifted_set = set(result.drifted)
        missing_set = set(result.missing)
        for task_entry in manifest.tasks:
            if task_entry.task_id in missing_set:
                s = "missing"
            elif task_entry.task_id in drifted_set:
                s = "drifted"
            else:
                s = "verified"
            integrity_results.append(
                IntegrityResultSchema(
                    task_id=task_entry.task_id,
                    status=s,
                    expected_hash=task_entry.content_hash,
                )
            )

    tasks_schema = [
        DatasetTaskEntrySchema(
            task_id=t.task_id,
            domain=t.domain,
            difficulty=t.difficulty,
            tags=t.tags,
        )
        for t in manifest.tasks
    ]

    return DatasetDetailResponse(
        name=manifest.name,
        version=manifest.version,
        summary=manifest.description.summary,
        content_hash=manifest.content_hash,
        task_count=len(manifest.tasks),
        domains=manifest.description.domains,
        tasks=tasks_schema,
        experiment_results=experiment_results,
        integrity_results=integrity_results,
    )
