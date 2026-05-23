# ABOUTME: Tests that LambdaRlmAdapter accepts and stores a ConstitutionManifest.
# ABOUTME: Ensures source_fidelity and information_minimality flow from adapter into executor.

from aec_bench.adapters.lambda_rlm.adapter import LambdaRlmAdapter
from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig
from aec_bench.adapters.rlm.client import ReplayRlmClient
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.contracts.constitution import (
    ConstitutionManifest,
    InformationMinimalityParams,
    SourceFidelityParams,
)
from aec_bench.contracts.repl import DependencyTreeSchema, OutputField, TreeSection


def _minimal_template() -> ReportTemplate:
    """Single-section template — used only to satisfy LambdaRlmAdapter construction."""
    return ReportTemplate(
        DependencyTreeSchema(
            sections=(
                TreeSection(
                    id="intro",
                    title="Intro",
                    fields={"body": OutputField(name="body", dtype="str", description="")},
                    depends_on=(),
                    generation_mode="transform",
                    writing_guidance=(),
                    input_mapping=(),
                ),
            )
        )
    )


def test_adapter_accepts_constitution_kwarg():
    manifest = ConstitutionManifest(
        version="0.1.0",
        principles=[],
        source_fidelity=SourceFidelityParams(
            require_source_tracing=True,
            tbd_placeholder="[TBD]",
            gap_framing="exclude",
        ),
        information_minimality=InformationMinimalityParams(
            default_threshold=2000,
            search_threshold=10_000,
            preview_length=250,
            truncation_strategy="metadata",
        ),
    )
    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=ReplayRlmClient([]),
        template=_minimal_template(),
        source_docs={},
        config=LambdaRlmConfig(),
        workspace="/tmp",
        constitution=manifest,
    )
    assert adapter._constitution is manifest
    assert adapter._constitution.source_fidelity.gap_framing == "exclude"


def test_adapter_defaults_constitution_to_none():
    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=ReplayRlmClient([]),
        template=_minimal_template(),
        source_docs={},
        config=LambdaRlmConfig(),
        workspace="/tmp",
    )
    assert adapter._constitution is None
