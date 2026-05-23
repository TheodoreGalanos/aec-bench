# ABOUTME: End-to-end tests for constitutional harness integration in the RLM adapter.
# ABOUTME: Verifies capability declaration, constitution loading, and wiring into components.

from aec_bench.adapters.base import AdapterCapabilities
from aec_bench.adapters.rlm.adapter import RlmAdapter
from aec_bench.adapters.rlm.client import RlmCompletionResponse


class StubClient:
    def generate(self, *, model, messages, system_prompt=None):
        return RlmCompletionResponse(
            output_text="FINAL",
            input_tokens=1,
            output_tokens=1,
        )

    def generate_with_tools(self, **kwargs):  # pragma: no cover
        raise NotImplementedError


class TestRlmCapabilities:
    def test_rlm_declares_all_capabilities(self) -> None:
        caps = RlmAdapter.declare_capabilities()
        assert isinstance(caps, AdapterCapabilities)
        assert caps.has_context_filtering is True
        assert caps.has_state_persistence is True
        assert caps.has_compaction is True
        assert caps.has_scaffolding is True
        assert caps.has_review_phase is True
        assert caps.has_source_tracing is True


class TestRlmAdapterStoresConstitution:
    def test_accepts_constitution_kwarg(self) -> None:
        from aec_bench.contracts.constitution import ConstitutionManifest

        manifest = ConstitutionManifest(version="0.1.0", principles=[])
        adapter = RlmAdapter(
            adapter_name="rlm-test",
            model_name="claude-opus-4-6",
            client=StubClient(),
            constitution=manifest,
        )
        assert adapter.constitution is manifest

    def test_no_constitution_defaults_to_none(self) -> None:
        adapter = RlmAdapter(
            adapter_name="rlm-test",
            model_name="claude-opus-4-6",
            client=StubClient(),
        )
        assert adapter.constitution is None


class TestRlmAdapterUsesConstitution:
    def test_context_filter_uses_constitutional_threshold(self) -> None:
        """When a constitution has a custom default_threshold, the adapter's
        internal ContextFilter must reflect it."""
        from aec_bench.adapters.rlm.adapter import RlmAdapter
        from aec_bench.contracts.constitution import (
            ConstitutionalPrinciple,
            ConstitutionManifest,
            InformationMinimalityParams,
        )

        manifest = ConstitutionManifest(
            version="0.1.0",
            principles=[
                ConstitutionalPrinciple(
                    name="information_minimality",
                    description="d",
                    evaluation_criteria="e",
                )
            ],
            information_minimality=InformationMinimalityParams(default_threshold=500),
        )
        adapter = RlmAdapter(
            adapter_name="rlm-test",
            model_name="claude-opus-4-6",
            client=StubClient(),
            constitution=manifest,
        )
        cf = adapter.build_context_filter()
        msg = cf.build_context_message(stdout="x" * 600, error=None, code="print('x'*600)")
        assert "Output: 600 chars" in msg

    def test_scaffolding_uses_constitutional_thresholds(self) -> None:
        from aec_bench.adapters.rlm.adapter import RlmAdapter
        from aec_bench.adapters.rlm.template import TemplateStatus
        from aec_bench.contracts.constitution import (
            ConstitutionalPrinciple,
            ConstitutionManifest,
            ProgressObligationParams,
        )

        manifest = ConstitutionManifest(
            version="0.1.0",
            principles=[
                ConstitutionalPrinciple(
                    name="progress_obligation",
                    description="d",
                    evaluation_criteria="e",
                )
            ],
            progress_obligation=ProgressObligationParams(gentle_nudge_turns=2),
        )
        adapter = RlmAdapter(
            adapter_name="rlm-test",
            model_name="claude-opus-4-6",
            client=StubClient(),
            constitution=manifest,
        )
        scaffolding = adapter.build_scaffolding_state()
        for _ in range(2):
            scaffolding.record_progress(0)
        status = TemplateStatus(
            completed_sections=0,
            total_sections=5,
            completed=[],
            unlocked=["intro"],
            pending=[],
        )
        out = scaffolding.build_footer(
            template_status=status,
            scratchpad_keys=["note"],
        )
        assert "without filling a section" in out

    def test_no_constitution_uses_default_behaviour(self) -> None:
        from aec_bench.adapters.rlm.adapter import RlmAdapter

        adapter = RlmAdapter(
            adapter_name="rlm-test",
            model_name="claude-opus-4-6",
            client=StubClient(),
            constitution=None,
        )
        # With no constitution, build_context_filter returns a default-params
        # filter — default_threshold=2000 applies.
        cf = adapter.build_context_filter()
        short = cf.build_context_message(stdout="x" * 1000, error=None, code="print('x'*1000)")
        assert short == "x" * 1000  # under 2000 threshold, verbatim

    def test_system_prompt_includes_constitution(self) -> None:
        from aec_bench.adapters.rlm.adapter import RlmAdapter
        from aec_bench.contracts.constitution import (
            ConstitutionalPrinciple,
            ConstitutionManifest,
            SourceFidelityParams,
        )

        manifest = ConstitutionManifest(
            version="0.1.0",
            principles=[
                ConstitutionalPrinciple(
                    name="source_fidelity",
                    description="d",
                    evaluation_criteria="e",
                )
            ],
            source_fidelity=SourceFidelityParams(tbd_placeholder="[MISSING]"),
        )
        adapter = RlmAdapter(
            adapter_name="rlm-test",
            model_name="claude-opus-4-6",
            client=StubClient(),
            constitution=manifest,
        )
        sys_prompt = adapter.build_effective_system_prompt()
        assert "CONSTITUTION" in sys_prompt
        assert "[MISSING]" in sys_prompt


class TestBuildRlmAdapterWithConstitution:
    def test_loads_constitution_from_path(self, tmp_path) -> None:
        from aec_bench.adapters.rlm.client import RlmCompletionResponse
        from aec_bench.adapters.rlm.initialiser import build_rlm_adapter

        # Write a minimal rlm.toml referencing the default constitution
        rlm_toml = tmp_path / "rlm.toml"
        rlm_toml.write_text("""
[template]
tier = "flat"

[constitution]
path = "src/aec_bench/adapters/constitution_default.toml"
model = "claude-opus-4-6"

[constitution.information_minimality]
default_threshold = 2500
""")

        # StubInferenceClient returns a valid JSON inference response
        class StubInferenceClient:
            def generate(self, *, model, messages, system_prompt=None):
                inferred = (
                    '{"information_minimality": {"default_threshold": 9999,'
                    ' "search_threshold": 11000, "preview_length": 250,'
                    ' "truncation_strategy": "metadata"}}'
                )
                return RlmCompletionResponse(
                    output_text=inferred,
                    input_tokens=10,
                    output_tokens=20,
                )

            def generate_with_tools(self, **kwargs):  # pragma: no cover
                raise NotImplementedError

        adapter = build_rlm_adapter(
            rlm_config_path=rlm_toml,
            client=StubClient(),
            adapter_name="rlm-test",
            model_name="claude-opus-4-6",
            constitutional_client=StubInferenceClient(),
        )
        # User override (2500) must win over inferred (9999)
        assert adapter.constitution is not None
        assert adapter.constitution.information_minimality.default_threshold == 2500

    def test_no_constitution_section_yields_none(self, tmp_path) -> None:
        from aec_bench.adapters.rlm.initialiser import build_rlm_adapter

        rlm_toml = tmp_path / "rlm.toml"
        rlm_toml.write_text("""
[template]
tier = "flat"
""")
        adapter = build_rlm_adapter(
            rlm_config_path=rlm_toml,
            client=StubClient(),
            adapter_name="rlm-test",
            model_name="claude-opus-4-6",
        )
        assert adapter.constitution is None
