# ABOUTME: Config-driven RLM adapter initialisation from rlm.toml and template files.
# ABOUTME: Reads config paths and assembles a fully-configured RlmAdapter.

from __future__ import annotations

from pathlib import Path
from typing import Any

from aec_bench.adapters.rlm.adapter import RlmAdapter
from aec_bench.adapters.rlm.client import RlmClient
from aec_bench.adapters.rlm.config import parse_rlm_config
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
    advisor_client: RlmClient | None = None,
    constitutional_client: RlmClient | None = None,
    task_metadata: dict | None = None,
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

    template: ReportTemplate | None = None
    if config.template_definition:
        template_path = rlm_config_path.parent / config.template_definition
        schema = parse_report_template(template_path.read_text())
        template = ReportTemplate(schema)

    # Load external system prompt and notes from workspace
    external_system_prompt = ""
    scratchpad_path: str | None = None

    if workspace_path:
        ws = Path(workspace_path)

        system_prompt_file = ws / "system_prompt.md"
        if system_prompt_file.exists():
            external_system_prompt = system_prompt_file.read_text().strip()

        notes_file = ws / "notes.md"
        if notes_file.exists():
            notes = notes_file.read_text().strip()
            # Skip placeholder/empty notes
            if notes and not notes.startswith("<!--"):
                sep = "\n\n" if external_system_prompt else ""
                external_system_prompt += (
                    f"{sep}## Project-Specific Instructions\n\n"
                    f"{notes}\n\n"
                    "Apply these instructions throughout the report."
                )

        scratchpad_path = str(ws / ".scratchpad.json")

    # Resolve constitution (precedence: inline > path > None)
    constitution: ConstitutionManifest | None = None
    if config.constitution_inline is not None:
        constitution = config.constitution_inline
    elif config.constitution_path is not None:
        base_path = Path(config.constitution_path)
        if not base_path.is_absolute():
            # Try relative to rlm_config_path's directory first
            candidate = rlm_config_path.parent / base_path
            if not candidate.exists():
                # Fall back to cwd-relative
                candidate = Path.cwd() / base_path
            base_path = candidate
        constitution = parse_constitution(base_path.read_text())

    # Run inference to fill unpopulated slots when a client is provided
    if constitution is not None and constitutional_client is not None:
        # Lazy import — see top-of-module note about the circular dependency.
        from aec_bench.adapters.constitutional import infer_constitutional_parameters

        capabilities = RlmAdapter.declare_capabilities()
        result = infer_constitutional_parameters(
            constitution=constitution,
            task_metadata=task_metadata or {},
            capabilities=capabilities,
            client=constitutional_client,
            model=config.constitution_model or model_name,
        )
        constitution = result.manifest

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
        external_system_prompt=external_system_prompt,
        workspace_path=workspace_path,
        advisor_client=advisor_client,
        advisor_config=config.advisor,
        constitution=constitution,
    )
