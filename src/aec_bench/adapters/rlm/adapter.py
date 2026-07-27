# ABOUTME: Exposes the stable RLM adapter while delegating execution to its typed lifecycle.
# ABOUTME: Retains prompt and constitutional compatibility surfaces for existing callers.

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from aec_bench.adapters.base import (
    AdapterCapabilities,
    AdapterRequest,
    AdapterResult,
)
from aec_bench.adapters.rlm.client import RlmClient
from aec_bench.adapters.rlm.config import (
    ExecutionConfig,
    GuardrailConfig,
    SubcallConfig,
)
from aec_bench.adapters.rlm.context_filter import ContextFilter
from aec_bench.adapters.rlm.engine import ReplEnvironment
from aec_bench.adapters.rlm.execution_lifecycle import (
    GUARDRAIL_FAILURE_KINDS,
    run_rlm_execution,
)
from aec_bench.adapters.rlm.prompt_surface import (
    build_constitution_section,
)
from aec_bench.adapters.rlm.prompt_surface import (
    build_repl_tool_description as _build_repl_tool_description,
)
from aec_bench.adapters.rlm.prompt_surface import (
    build_system_prompt as _build_system_prompt,
)
from aec_bench.adapters.rlm.prompt_surface import (
    enabled_subcall_names as _enabled_subcall_names,
)
from aec_bench.adapters.rlm.prompt_surface import (
    format_code_preview as _format_code_preview,
)
from aec_bench.adapters.rlm.prompt_surface import (
    make_help as _make_help,
)
from aec_bench.adapters.rlm.repl_runtime import (
    build_context_filter as build_runtime_context_filter,
)
from aec_bench.adapters.rlm.repl_runtime import (
    build_scaffolding_state as build_runtime_scaffolding_state,
)
from aec_bench.adapters.rlm.repl_runtime import (
    load_repl_commands,
    resolve_state_persistence_params,
)
from aec_bench.adapters.rlm.runtime_contracts import RlmRuntimeConfig
from aec_bench.adapters.rlm.scaffolding import ScaffoldingState
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.contracts.advisor import AdvisorConfig
from aec_bench.contracts.constitution import ConstitutionManifest

if TYPE_CHECKING:
    from aec_bench.contracts.constitution import StatePersistenceParams

_GUARDRAIL_FAILURE_KINDS = GUARDRAIL_FAILURE_KINDS

__all__ = [
    "RlmAdapter",
    "_GUARDRAIL_FAILURE_KINDS",
    "_build_repl_tool_description",
    "_build_system_prompt",
    "_format_code_preview",
    "_make_help",
    "build_constitution_section",
]


class RlmAdapter:
    """Adapter that runs a recursive, persistent-REPL language-model loop."""

    @classmethod
    def declare_capabilities(cls) -> AdapterCapabilities:
        """Declare which constitutional mechanisms this adapter supports."""
        return AdapterCapabilities(
            has_context_filtering=True,
            has_state_persistence=True,
            has_compaction=True,
            has_scaffolding=True,
            has_review_phase=True,
            has_source_tracing=True,
        )

    def __init__(
        self,
        *,
        adapter_name: str,
        model_name: str,
        client: RlmClient,
        guardrails: GuardrailConfig | None = None,
        execution: ExecutionConfig | None = None,
        hints: list[str] | None = None,
        subcall_client: RlmClient | None = None,
        subcall_model: str | None = None,
        subcall_configs: dict[str, SubcallConfig] | None = None,
        template: ReportTemplate | None = None,
        compaction_client: RlmClient | None = None,
        trajectory_writer: Any | None = None,
        scratchpad_path: str | None = None,
        external_system_prompt: str = "",
        workspace_path: str | None = None,
        prohibited: list[str] | None = None,
        advisor_client: RlmClient | None = None,
        advisor_config: AdvisorConfig | None = None,
        constitution: ConstitutionManifest | None = None,
    ) -> None:
        self._adapter_name = adapter_name
        self._model_name = model_name
        self._client = client
        self._guardrail_config = guardrails or GuardrailConfig()
        self._execution_config = execution or ExecutionConfig()
        self._hints = hints
        self._prohibited = prohibited
        self._subcall_client = subcall_client
        self._subcall_model = subcall_model
        self._subcall_configs = subcall_configs
        self._template = template
        self._compaction_client = compaction_client
        self._trajectory_writer = trajectory_writer
        self._scratchpad_path = scratchpad_path
        self._external_system_prompt = external_system_prompt
        self._workspace_path = workspace_path
        self._advisor_client = advisor_client
        self._advisor_config = advisor_config
        self.constitution = constitution

    def build_context_filter(self) -> ContextFilter:
        """Create a constitution-driven context filter."""
        return build_runtime_context_filter(self._runtime_config())

    def build_scaffolding_state(self) -> ScaffoldingState:
        """Create constitution-driven progress and autonomy scaffolding."""
        return build_runtime_scaffolding_state(self._runtime_config())

    def build_effective_system_prompt(
        self,
        *,
        max_iterations: int | None = None,
    ) -> str:
        """Return the resolved system prompt, including the constitution block."""
        return _build_system_prompt(
            hints=self._hints,
            variables=None,
            prohibited=self._prohibited,
            external_system_prompt=self._external_system_prompt,
            constitution=self.constitution,
            max_iterations=max_iterations,
            scratchpad_enabled=self._scratchpad_path is not None,
            enabled_subcalls=_enabled_subcall_names(self._subcall_configs),
            template_enabled=self._template is not None,
        )

    def resolve_state_persistence_params(self) -> StatePersistenceParams:
        """Return state-persistence params from the constitution or defaults."""
        return resolve_state_persistence_params(self._runtime_config())

    def _load_repl_commands(self, repl: ReplEnvironment) -> None:
        """Load task-specific REPL commands from the configured workspace."""
        if self._workspace_path is None:
            return
        load_repl_commands(
            repl,
            workspace_path=self._workspace_path,
            template=self._template,
        )

    def _emit(self, tag: str, message: str) -> None:
        """Write a real-time progress line to stderr."""
        sys.stderr.write(f"[{tag:12s}] {message}\n")
        sys.stderr.flush()

    def execute(self, request: AdapterRequest) -> AdapterResult:
        """Run the typed RLM execution lifecycle."""
        return run_rlm_execution(
            self._runtime_config(),
            request,
            emit=self._emit,
        )

    def adapter_name(self) -> str:
        return self._adapter_name

    def resolved_model(self) -> str:
        return self._model_name

    def _runtime_config(self) -> RlmRuntimeConfig:
        return RlmRuntimeConfig(
            adapter_name=self._adapter_name,
            model_name=self._model_name,
            client=self._client,
            guardrails=self._guardrail_config,
            execution=self._execution_config,
            hints=self._hints,
            prohibited=self._prohibited,
            subcall_client=self._subcall_client,
            subcall_model=self._subcall_model,
            subcall_configs=self._subcall_configs,
            template=self._template,
            compaction_client=self._compaction_client,
            trajectory=self._trajectory_writer,
            scratchpad_path=self._scratchpad_path,
            external_system_prompt=self._external_system_prompt,
            workspace_path=self._workspace_path,
            advisor_client=self._advisor_client,
            advisor_config=self._advisor_config,
            constitution=self.constitution,
        )
