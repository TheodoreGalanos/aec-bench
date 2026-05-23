# ABOUTME: Library route serving the benchmark template catalogue.
# ABOUTME: List view with discipline filter and detail view with params.toml data.

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from aec_bench.generation.discovery import scan_templates
from aec_bench.web.dependencies import get_web_settings
from aec_bench.web.schemas import (
    LibraryDetailResponse,
    LibraryListResponse,
    TemplateIOSchema,
    TemplateSchema,
)

router = APIRouter()


def _template_to_dict(template) -> dict:
    """Convert a LibraryTemplate to a dict for the template context."""
    meta = template.params_raw.get("meta", {})
    params = template.params_raw.get("params", {})
    outputs = template.params_raw.get("outputs", {})

    return {
        "task_id": template.task_id,
        "discipline": template.discipline,
        "description": meta.get("description", ""),
        "long_description": meta.get("long_description", ""),
        "tags": meta.get("tags", []),
        "standards": meta.get("standards", []),
        "inputs": [{"name": name, "description": spec.get("description", name)} for name, spec in params.items()],
        "outputs": [{"name": name, "description": spec.get("description", name)} for name, spec in outputs.items()],
        "param_count": len(params),
    }


def _dict_to_template_schema(d: dict) -> TemplateSchema:
    """Convert a _template_to_dict result to a TemplateSchema."""
    return TemplateSchema(
        task_id=d["task_id"],
        discipline=d["discipline"],
        description=d["description"],
        long_description=d["long_description"],
        tags=d["tags"],
        standards=d["standards"],
        inputs=[TemplateIOSchema(name=i["name"], description=i["description"]) for i in d["inputs"]],
        outputs=[TemplateIOSchema(name=o["name"], description=o["description"]) for o in d["outputs"]],
        param_count=d["param_count"],
    )


@router.get("/api/library")
def library_api(
    request: Request,
    discipline: str | None = None,
) -> LibraryListResponse:
    """Return the template catalogue as JSON."""
    settings = get_web_settings(request)
    all_templates = scan_templates(settings.benchmark_templates_root)
    disciplines = sorted({t.discipline for t in all_templates})

    if discipline:
        filtered = [t for t in all_templates if t.discipline == discipline]
    else:
        filtered = all_templates

    templates_schema = [_dict_to_template_schema(_template_to_dict(t)) for t in filtered]

    return LibraryListResponse(
        templates=templates_schema,
        disciplines=disciplines,
        selected_discipline=discipline or "",
    )


@router.get("/api/library/{discipline}/{template_id}")
def library_detail_api(
    request: Request,
    discipline: str,
    template_id: str,
) -> LibraryDetailResponse:
    """Return a single template's detail as JSON."""
    settings = get_web_settings(request)
    templates = scan_templates(settings.benchmark_templates_root)

    match = next(
        (t for t in templates if t.discipline == discipline and t.task_id == template_id),
        None,
    )
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    return LibraryDetailResponse(template=_dict_to_template_schema(_template_to_dict(match)))
