# ABOUTME: Library route serving the benchmark template catalogue.
# ABOUTME: List view with discipline filter and detail view with params.toml data.

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from aec_bench.templates.registry import LoadedTemplate, discover_templates
from aec_bench.web.dependencies import get_web_settings
from aec_bench.web.schemas import (
    LibraryDetailResponse,
    LibraryListResponse,
    TemplateIOSchema,
    TemplateSchema,
)

router = APIRouter()


def _template_to_dict(template: LoadedTemplate) -> dict[str, Any]:
    """Convert a validated template to the existing API projection."""
    config = template.config
    meta = config.meta

    return {
        "task_id": meta.name,
        "discipline": meta.discipline,
        "description": meta.description,
        "long_description": meta.long_description,
        "tags": meta.tags,
        "standards": meta.standards,
        "inputs": [{"name": name, "description": spec.description} for name, spec in config.params.items()],
        "outputs": [{"name": name, "description": spec.description} for name, spec in config.outputs.items()],
        "param_count": len(config.params),
    }


def _dict_to_template_schema(d: dict[str, Any]) -> TemplateSchema:
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
    all_templates, _diagnostics = discover_templates(
        user_dirs=[settings.benchmark_templates_root],
        include_builtin=False,
    )
    disciplines = sorted({template.config.meta.discipline for template in all_templates})

    if discipline:
        filtered = [t for t in all_templates if t.config.meta.discipline == discipline]
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
    templates, _diagnostics = discover_templates(
        user_dirs=[settings.benchmark_templates_root],
        include_builtin=False,
    )

    match = next(
        (
            template
            for template in templates
            if template.config.meta.discipline == discipline and template.config.meta.name == template_id
        ),
        None,
    )
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    return LibraryDetailResponse(template=_dict_to_template_schema(_template_to_dict(match)))
