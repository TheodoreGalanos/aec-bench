# ABOUTME: Search route for finding templates, datasets, trials, experiments, workspaces.
# ABOUTME: Substring-on-lowercase matching; each group capped at 10 results.

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Request

from aec_bench.dataset.storage import list_datasets
from aec_bench.evolution.report_data import discover_workspaces
from aec_bench.ledger.reader import read_trial_records
from aec_bench.search import SearchEntry, build_index_from_paths, search
from aec_bench.web.dependencies import get_web_settings
from aec_bench.web.schemas import (
    ExperimentSearchResult,
    SearchResponse,
    TrialSearchResult,
    WorkspaceSearchResult,
)

router = APIRouter()

_GROUP_CAP = 10


def _text_rank(query_terms: list[str], *fields: str) -> int:
    rank = 0
    for term in query_terms:
        rank += next(
            (field_index for field_index, field in enumerate(fields) if term in field.lower()),
            len(fields),
        )
    return rank


def _template_rank(
    query: str,
    query_terms: list[str],
    match: SearchEntry,
) -> tuple[int, int, str, str]:
    return (
        0 if match.name.lower() == query else 1,
        _text_rank(
            query_terms,
            match.name,
            match.category,
            " ".join(match.tags),
            " ".join(match.standards),
            match.description,
            match.long_description,
            " ".join(match.inputs),
            " ".join(match.outputs),
            match.discipline,
        ),
        match.discipline,
        match.name,
    )


@router.get("/api/search")
def search_api(
    request: Request,
    q: str = "",
) -> SearchResponse:
    """Return search results across templates, datasets, trials, experiments, and workspaces."""
    settings = get_web_settings(request)
    query = q.strip()

    template_results: list[dict] = []
    dataset_results: list[dict] = []
    trial_results: list[TrialSearchResult] = []
    experiment_results: list[ExperimentSearchResult] = []
    workspace_results: list[WorkspaceSearchResult] = []

    if not query:
        return SearchResponse(
            query=query,
            template_results=template_results,
            dataset_results=dataset_results,
            trial_results=trial_results,
            experiment_results=experiment_results,
            workspace_results=workspace_results,
            total_results=0,
        )

    query_lower = query.lower()
    terms = query_lower.split()

    # Templates (existing logic)
    index = build_index_from_paths(settings.tasks_root, settings.benchmark_templates_root)
    template_matches = sorted(
        search(query, index, kind="template"),
        key=lambda match: _template_rank(query_lower, terms, match),
    )
    template_results = [
        {
            "name": m.name,
            "task_id": f"{m.discipline}/{m.name}",
            "discipline": m.discipline,
            "description": m.long_description or m.description,
            "standards": list(m.standards),
            "tags": list(m.tags),
        }
        for m in template_matches[:_GROUP_CAP]
    ]

    # Datasets (existing logic)
    manifests = list_datasets(settings.datasets_root)
    dataset_matches = [
        m for m in manifests if query_lower in m.name.lower() or query_lower in m.description.summary.lower()
    ]
    dataset_matches = sorted(
        dataset_matches,
        key=lambda match: _text_rank(terms, match.name, match.description.summary),
    )
    dataset_results = [
        {
            "name": m.name,
            "version": m.version,
            "summary": m.description.summary,
            "task_count": len(m.tasks),
            "domains": m.description.domains,
        }
        for m in dataset_matches[:_GROUP_CAP]
    ]

    # Trials — load all records (mtime-cached) then filter
    records = read_trial_records(settings.ledger_root)
    for record in records:
        search_text = " ".join(
            [
                record.trial_id,
                record.experiment_id,
                record.task.task_id,
                record.agent.model,
            ]
        ).lower()
        if all(term in search_text for term in terms):
            trial_results.append(
                TrialSearchResult(
                    trial_id=record.trial_id,
                    experiment_id=record.experiment_id,
                    task_id=record.task.task_id,
                    model=record.agent.model,
                    reward=record.evaluation.reward,
                )
            )
            if len(trial_results) >= _GROUP_CAP:
                break

    # Experiments — aggregate distinct experiment_ids from the ledger.
    # Intentional asymmetry: experiments match on experiment_id only (narrow,
    # user-intent: "jump to this experiment"), while trials match on 4 fields
    # (broad, user-intent: "find trials mentioning X"). A query like "haiku"
    # matches trials by model but does NOT match experiments — by design.
    experiment_buckets: dict[str, list[float]] = defaultdict(list)
    for record in records:
        experiment_buckets[record.experiment_id].append(record.evaluation.reward)

    for experiment_id, rewards in experiment_buckets.items():
        if query_lower not in experiment_id.lower():
            continue
        experiment_results.append(
            ExperimentSearchResult(
                experiment_id=experiment_id,
                trial_count=len(rewards),
                mean_reward=sum(rewards) / len(rewards) if rewards else 0.0,
            )
        )
        if len(experiment_results) >= _GROUP_CAP:
            break

    # Workspaces — de-dupe by path; skipped if workspaces_root not configured
    if settings.workspaces_root is not None and settings.workspaces_root.exists():
        seen_paths: set[str] = set()
        for ws in discover_workspaces(settings.workspaces_root):
            if ws["path"] in seen_paths:
                continue
            seen_paths.add(ws["path"])
            if query_lower not in ws["name"].lower():
                continue
            workspace_results.append(
                WorkspaceSearchResult(
                    name=ws["name"],
                    path=ws["path"],
                    has_swarm=(settings.workspaces_root / ws["path"] / "_swarm_runs" / "events.jsonl").exists(),
                )
            )
            if len(workspace_results) >= _GROUP_CAP:
                break

    return SearchResponse(
        query=query,
        template_results=template_results,
        dataset_results=dataset_results,
        trial_results=trial_results,
        experiment_results=experiment_results,
        workspace_results=workspace_results,
        total_results=(
            len(template_results)
            + len(dataset_results)
            + len(trial_results)
            + len(experiment_results)
            + len(workspace_results)
        ),
    )
