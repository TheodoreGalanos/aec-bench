# ABOUTME: Tests for the constitutional inference engine.
# ABOUTME: Unit-tested via a stub RlmClient — no real LLM calls.

from aec_bench.adapters.base import AdapterCapabilities
from aec_bench.adapters.constitutional import (
    ConstitutionalInferenceResult,
    build_inference_prompt,
    infer_constitutional_parameters,
    merge_with_overrides,
)
from aec_bench.adapters.rlm.client import RlmCompletionResponse
from aec_bench.contracts.constitution import (
    ConstitutionManifest,
    InformationMinimalityParams,
    ProgressObligationParams,
    parse_constitution,
)

DEFAULT_CONSTITUTION_TOML = """
version = "0.1.0"

[[principles]]
name = "information_minimality"
description = "Show only what's needed for next decision."
evaluation_criteria = "context growth"

[[principles]]
name = "state_persistence"
description = "Durable state is memory."
evaluation_criteria = "state routing ratio"

[[principles]]
name = "progress_obligation"
description = "Intervene on speculation."
evaluation_criteria = "turns to first output"

[[principles]]
name = "source_fidelity"
description = "Trace facts to sources."
evaluation_criteria = "factual accuracy"

[[principles]]
name = "earned_autonomy"
description = "Constrain first."
evaluation_criteria = "mode transitions"
"""


TASK_METADATA_STUB = {
    "difficulty": "medium",
    "discipline": "electrical",
    "is_template_based": True,
    "section_count": 9,
    "tools": ["repl", "extract", "grep"],
}


class StubRlmClient:
    """Minimal RlmClient stub returning a canned JSON response."""

    def __init__(self, response_text: str, error: str | None = None) -> None:
        self._response_text = response_text
        self._error = error
        self.calls: list[dict] = []

    def generate(self, *, model: str, messages, system_prompt: str | None = None) -> RlmCompletionResponse:
        self.calls.append({"model": model, "messages": messages, "system": system_prompt})
        return RlmCompletionResponse(
            output_text=self._response_text,
            input_tokens=100,
            output_tokens=200,
            error_message=self._error,
        )

    def generate_with_tools(self, **kwargs):  # pragma: no cover
        raise NotImplementedError


class TestBuildInferencePrompt:
    def test_includes_principles(self) -> None:
        cons = parse_constitution(DEFAULT_CONSTITUTION_TOML)
        caps = AdapterCapabilities(
            has_context_filtering=True,
            has_state_persistence=True,
            has_compaction=True,
            has_scaffolding=True,
            has_source_tracing=True,
        )
        prompt = build_inference_prompt(
            constitution=cons,
            task_metadata=TASK_METADATA_STUB,
            capabilities=caps,
        )
        for principle in cons.principles:
            assert principle.name in prompt
            assert principle.description in prompt

    def test_includes_task_metadata(self) -> None:
        cons = parse_constitution(DEFAULT_CONSTITUTION_TOML)
        caps = AdapterCapabilities(has_context_filtering=True)
        prompt = build_inference_prompt(
            constitution=cons,
            task_metadata=TASK_METADATA_STUB,
            capabilities=caps,
        )
        assert "electrical" in prompt
        assert "medium" in prompt

    def test_omits_unsupported_principles(self) -> None:
        cons = parse_constitution(DEFAULT_CONSTITUTION_TOML)
        # No scaffolding → progress_obligation + earned_autonomy unsupported
        caps = AdapterCapabilities(has_context_filtering=True)
        prompt = build_inference_prompt(
            constitution=cons,
            task_metadata=TASK_METADATA_STUB,
            capabilities=caps,
        )
        assert "information_minimality" in prompt
        assert "progress_obligation" not in prompt
        assert "earned_autonomy" not in prompt


class TestInferConstitutionalParameters:
    def test_populates_all_params(self) -> None:
        cons = parse_constitution(DEFAULT_CONSTITUTION_TOML)
        caps = AdapterCapabilities(
            has_context_filtering=True,
            has_state_persistence=True,
            has_compaction=True,
            has_scaffolding=True,
            has_source_tracing=True,
        )
        response_json = """
        {
          "information_minimality": {
            "default_threshold": 1800,
            "search_threshold": 9000,
            "preview_length": 200,
            "truncation_strategy": "metadata"
          },
          "state_persistence": {
            "preserve_variables": true,
            "preserve_scratchpad": true,
            "compaction_strategy": "llm_summary"
          },
          "progress_obligation": {
            "gentle_nudge_turns": 8,
            "strong_nudge_turns": 16,
            "stall_threshold_turns": 3
          },
          "source_fidelity": {
            "require_source_tracing": true,
            "tbd_placeholder": "[TBD]",
            "gap_framing": "exclude"
          },
          "earned_autonomy": {
            "initial_mode": "constrained",
            "promotion_threshold": 2,
            "demotion_on_stall": true
          }
        }
        """
        client = StubRlmClient(response_json)
        result = infer_constitutional_parameters(
            constitution=cons,
            task_metadata=TASK_METADATA_STUB,
            capabilities=caps,
            client=client,
            model="claude-opus-4-6",
        )

        assert isinstance(result, ConstitutionalInferenceResult)
        assert result.error is None
        manifest = result.manifest
        assert manifest.information_minimality.default_threshold == 1800
        assert manifest.progress_obligation.gentle_nudge_turns == 8
        assert manifest.source_fidelity.gap_framing == "exclude"
        assert manifest.earned_autonomy.initial_mode == "constrained"

    def test_respects_user_overrides(self) -> None:
        """User-provided parameter models are kept; inference only fills None slots."""
        cons = parse_constitution(DEFAULT_CONSTITUTION_TOML)
        # Pre-populate information_minimality as a user override
        cons_with_override = ConstitutionManifest(
            version=cons.version,
            principles=cons.principles,
            information_minimality=InformationMinimalityParams(default_threshold=5000),
        )
        caps = AdapterCapabilities(
            has_context_filtering=True,
            has_state_persistence=True,
            has_compaction=True,
            has_scaffolding=True,
            has_source_tracing=True,
        )
        # Inference response tries to set default_threshold=1000 — should be ignored
        response_json = """
        {
          "information_minimality": {
            "default_threshold": 1000,
            "search_threshold": 9000,
            "preview_length": 200,
            "truncation_strategy": "metadata"
          }
        }
        """
        client = StubRlmClient(response_json)
        result = infer_constitutional_parameters(
            constitution=cons_with_override,
            task_metadata=TASK_METADATA_STUB,
            capabilities=caps,
            client=client,
            model="claude-opus-4-6",
        )
        # User override wins
        assert result.manifest.information_minimality.default_threshold == 5000

    def test_fallback_on_client_error(self) -> None:
        cons = parse_constitution(DEFAULT_CONSTITUTION_TOML)
        caps = AdapterCapabilities(
            has_context_filtering=True,
            has_state_persistence=True,
            has_compaction=True,
            has_scaffolding=True,
            has_source_tracing=True,
        )
        client = StubRlmClient("", error="rate limited")
        result = infer_constitutional_parameters(
            constitution=cons,
            task_metadata=TASK_METADATA_STUB,
            capabilities=caps,
            client=client,
            model="claude-opus-4-6",
        )
        assert result.error == "rate limited"
        # Manifest falls back to constructor defaults for every param
        assert result.manifest.information_minimality == InformationMinimalityParams()
        assert result.manifest.progress_obligation == ProgressObligationParams()

    def test_fallback_on_unparseable_response(self) -> None:
        cons = parse_constitution(DEFAULT_CONSTITUTION_TOML)
        caps = AdapterCapabilities(
            has_context_filtering=True,
            has_state_persistence=True,
            has_compaction=True,
            has_scaffolding=True,
            has_source_tracing=True,
        )
        client = StubRlmClient("this is not json at all")
        result = infer_constitutional_parameters(
            constitution=cons,
            task_metadata=TASK_METADATA_STUB,
            capabilities=caps,
            client=client,
            model="claude-opus-4-6",
        )
        assert result.error is not None
        assert "parse" in result.error.lower()
        assert result.manifest.information_minimality == InformationMinimalityParams()

    def test_skips_disabled_principles(self) -> None:
        _old = (
            '[[principles]]\nname = "earned_autonomy"\n'
            'description = "Constrain first."\nevaluation_criteria = "mode transitions"'
        )
        _new = (
            '[[principles]]\nname = "earned_autonomy"\n'
            'description = "Constrain first."\nevaluation_criteria = "mode transitions"'
            "\nenabled = false"
        )
        toml_disabled = DEFAULT_CONSTITUTION_TOML.replace(_old, _new)
        cons = parse_constitution(toml_disabled)
        caps = AdapterCapabilities(
            has_context_filtering=True,
            has_state_persistence=True,
            has_compaction=True,
            has_scaffolding=True,
            has_source_tracing=True,
        )
        client = StubRlmClient("{}")  # empty response
        result = infer_constitutional_parameters(
            constitution=cons,
            task_metadata=TASK_METADATA_STUB,
            capabilities=caps,
            client=client,
            model="claude-opus-4-6",
        )
        # Disabled principle gets None (no fallback instantiated)
        assert result.manifest.earned_autonomy is None

    def test_handles_fenced_json_response(self) -> None:
        cons = parse_constitution(DEFAULT_CONSTITUTION_TOML)
        caps = AdapterCapabilities(
            has_context_filtering=True,
            has_state_persistence=True,
            has_compaction=True,
            has_scaffolding=True,
            has_source_tracing=True,
        )
        fenced_response = """Here is the answer:

```json
{
  "information_minimality": {
    "default_threshold": 1500,
    "search_threshold": 8000,
    "preview_length": 200,
    "truncation_strategy": "metadata"
  }
}
```

Hope that helps."""
        client = StubRlmClient(fenced_response)
        result = infer_constitutional_parameters(
            constitution=cons,
            task_metadata=TASK_METADATA_STUB,
            capabilities=caps,
            client=client,
            model="claude-opus-4-6",
        )
        assert result.error is None
        assert result.manifest.information_minimality.default_threshold == 1500


class TestMergeWithOverrides:
    def test_overrides_beat_inferred(self) -> None:
        user = ConstitutionManifest(
            version="0.1.0",
            principles=[],
            information_minimality=InformationMinimalityParams(default_threshold=5000),
        )
        inferred = ConstitutionManifest(
            version="0.1.0",
            principles=[],
            information_minimality=InformationMinimalityParams(default_threshold=1000),
            progress_obligation=ProgressObligationParams(gentle_nudge_turns=7),
        )
        merged = merge_with_overrides(user=user, inferred=inferred)
        assert merged.information_minimality.default_threshold == 5000  # user wins
        assert merged.progress_obligation.gentle_nudge_turns == 7  # inferred fills gap
