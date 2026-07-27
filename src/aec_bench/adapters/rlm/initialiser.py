# ABOUTME: Config-driven RLM adapter initialisation from rlm.toml and template files.
# ABOUTME: Reads config paths and assembles a fully-configured RlmAdapter.

from __future__ import annotations

from pathlib import Path
from typing import Any

from aec_bench.adapters.rlm.adapter import RlmAdapter
from aec_bench.adapters.rlm.client import RlmClient
from aec_bench.adapters.rlm.config import RlmConfig, parse_rlm_config
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.adapters.rlm.template_parser import parse_report_template
from aec_bench.contracts.constitution import ConstitutionManifest, parse_constitution

# infer_constitutional_parameters is imported lazily inside build_rlm_adapter to
# avoid a circular import: constitutional.py → rlm.client → rlm/__init__.py →
# initialiser. Import occurs only when inference is actually needed.


def build_rlm_adapter(
    *,
    rlm_config_path: Path,
    client: RlmClient,
    adapter_name: str,
    model_name: str,
    subcall_client: RlmClient | None = None,
    subcall_model: str | None = None,
    compaction_client: RlmClient | None = None,
    trajectory_writer: Any | None = None,
    workspace_path: str | None = None,
    external_system_prompt: str | None = None,
    advisor_client: RlmClient | None = None,
    constitutional_client: RlmClient | None = None,
    task_metadata: dict[str, Any] | None = None,
) -> RlmAdapter:
    """Build a fully-configured RlmAdapter from config file paths.

    Reads rlm.toml for guardrails, hints, sub-call declarations,
    execution config, and template tier. If a template definition file
    is specified, loads the report template resolved relative to
    rlm.toml's directory.

    When *workspace_path* is provided, loads ``system_prompt.md`` and
    ``notes.md`` if present, and sets up the scratchpad path.

    Constitutional resolution (precedence chain):
      1. If config has constitution_inline (inline overrides present), use it.
      2. If config has constitution_path, load that file as the base manifest.
      3. Otherwise, constitution=None (legacy default-behaviour mode).
      4. If constitutional_client is provided AND a constitution was resolved,
         run inference to fill unpopulated parameter slots; user overrides win.
    """
    config = parse_rlm_config(rlm_config_path.read_text())
    template = _load_report_template(
        config,
        config_root=rlm_config_path.parent,
    )
    resolved_system_prompt, scratchpad_path = _resolve_workspace_surface(
        workspace_path=workspace_path,
        external_system_prompt=external_system_prompt,
    )
    constitution = _resolve_constitution(
        config,
        config_root=rlm_config_path.parent,
    )
    constitution = _infer_constitution(
        constitution,
        config=config,
        client=constitutional_client,
        model_name=model_name,
        task_metadata=task_metadata,
    )

    return RlmAdapter(
        adapter_name=adapter_name,
        model_name=model_name,
        client=client,
        guardrails=config.guardrails,
        execution=config.execution,
        hints=config.hints or None,
        prohibited=config.prohibited or None,
        subcall_client=subcall_client,
        subcall_model=subcall_model or config.execution.subcall_model,
        subcall_configs=config.subcalls or None,
        template=template,
        compaction_client=compaction_client,
        trajectory_writer=trajectory_writer,
        scratchpad_path=scratchpad_path,
        external_system_prompt=resolved_system_prompt or "",
        workspace_path=workspace_path,
        advisor_client=advisor_client,
        advisor_config=config.advisor,
        constitution=constitution,
    )


def _load_report_template(
    config: RlmConfig,
    *,
    config_root: Path,
) -> ReportTemplate | None:
    if not config.template_definition:
        return None
    template_path = config_root / config.template_definition
    return ReportTemplate(parse_report_template(template_path.read_text()))


def _resolve_workspace_surface(
    *,
    workspace_path: str | None,
    external_system_prompt: str | None,
) -> tuple[str | None, str | None]:
    if workspace_path is None:
        return external_system_prompt, None
    workspace = Path(workspace_path)
    resolved_prompt = _workspace_system_prompt(
        workspace,
        external_system_prompt=external_system_prompt,
    )
    return (
        _append_workspace_notes(workspace, system_prompt=resolved_prompt),
        str(workspace / ".scratchpad.json"),
    )


def _workspace_system_prompt(
    workspace: Path,
    *,
    external_system_prompt: str | None,
) -> str | None:
    if external_system_prompt is not None:
        return external_system_prompt
    system_prompt_path = workspace / "system_prompt.md"
    if not system_prompt_path.exists():
        return None
    return system_prompt_path.read_text().strip()


def _append_workspace_notes(
    workspace: Path,
    *,
    system_prompt: str | None,
) -> str | None:
    notes_path = workspace / "notes.md"
    if not notes_path.exists():
        return system_prompt
    notes = notes_path.read_text().strip()
    if not notes or notes.startswith("<!--"):
        return system_prompt
    separator = "\n\n" if system_prompt else ""
    return (
        f"{system_prompt or ''}{separator}"
        "## Project-Specific Instructions\n\n"
        f"{notes}\n\n"
        "Apply these instructions throughout the report."
    )


def _resolve_constitution(
    config: RlmConfig,
    *,
    config_root: Path,
) -> ConstitutionManifest | None:
    if config.constitution_inline is not None:
        return config.constitution_inline
    if config.constitution_path is None:
        return None
    path = _resolve_constitution_path(
        Path(config.constitution_path),
        config_root=config_root,
    )
    return parse_constitution(path.read_text())


def _resolve_constitution_path(
    path: Path,
    *,
    config_root: Path,
) -> Path:
    if path.is_absolute():
        return path
    candidate = config_root / path
    return candidate if candidate.exists() else Path.cwd() / path


def _infer_constitution(
    constitution: ConstitutionManifest | None,
    *,
    config: RlmConfig,
    client: RlmClient | None,
    model_name: str,
    task_metadata: dict[str, Any] | None,
) -> ConstitutionManifest | None:
    if constitution is None or client is None:
        return constitution
    # Lazy import — see top-of-module note about the circular dependency.
    from aec_bench.adapters.constitutional import (
        infer_constitutional_parameters,
    )

    result = infer_constitutional_parameters(
        constitution=constitution,
        task_metadata=task_metadata or {},
        capabilities=RlmAdapter.declare_capabilities(),
        client=client,
        model=config.constitution_model or model_name,
    )
    return result.manifest
