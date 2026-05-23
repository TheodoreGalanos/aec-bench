# ABOUTME: Tests that the RLM system prompt reflects constitutional SourceFidelityParams.
# ABOUTME: Validates the CONSTITUTION block and anti-hallucination phrasing.

from aec_bench.adapters.rlm.adapter import (
    _build_system_prompt,
    build_constitution_section,
)
from aec_bench.contracts.constitution import (
    ConstitutionalPrinciple,
    ConstitutionManifest,
    EarnedAutonomyParams,
    InformationMinimalityParams,
    ProgressObligationParams,
    SourceFidelityParams,
    StatePersistenceParams,
)


def _minimal_manifest(
    *,
    source_fidelity: SourceFidelityParams | None = None,
    info_min: InformationMinimalityParams | None = None,
    progress: ProgressObligationParams | None = None,
    state: StatePersistenceParams | None = None,
    autonomy: EarnedAutonomyParams | None = None,
) -> ConstitutionManifest:
    principles = [
        ConstitutionalPrinciple(
            name="information_minimality",
            description="Show only what's needed.",
            evaluation_criteria="growth",
        ),
        ConstitutionalPrinciple(
            name="state_persistence",
            description="Durable state.",
            evaluation_criteria="state ratio",
        ),
        ConstitutionalPrinciple(
            name="progress_obligation",
            description="Don't speculate.",
            evaluation_criteria="turns",
        ),
        ConstitutionalPrinciple(
            name="source_fidelity",
            description="Trace facts.",
            evaluation_criteria="accuracy",
        ),
        ConstitutionalPrinciple(
            name="earned_autonomy",
            description="Start constrained.",
            evaluation_criteria="mode transitions",
        ),
    ]
    return ConstitutionManifest(
        version="0.1.0",
        principles=principles,
        information_minimality=info_min or InformationMinimalityParams(),
        state_persistence=state or StatePersistenceParams(),
        progress_obligation=progress or ProgressObligationParams(),
        source_fidelity=source_fidelity or SourceFidelityParams(),
        earned_autonomy=autonomy or EarnedAutonomyParams(),
    )


class TestBuildConstitutionSection:
    def test_empty_when_no_manifest(self) -> None:
        assert build_constitution_section(None) == ""

    def test_mentions_enabled_principles(self) -> None:
        m = _minimal_manifest()
        text = build_constitution_section(m)
        assert "CONSTITUTION" in text
        assert "information_minimality" in text or "Information Minimality" in text
        assert "source_fidelity" in text or "Source Fidelity" in text

    def test_custom_tbd_placeholder(self) -> None:
        m = _minimal_manifest(source_fidelity=SourceFidelityParams(tbd_placeholder="[MISSING]"))
        text = build_constitution_section(m)
        assert "[MISSING]" in text

    def test_gap_framing_exclude(self) -> None:
        m = _minimal_manifest(source_fidelity=SourceFidelityParams(gap_framing="exclude"))
        text = build_constitution_section(m)
        # Exclude framing → omit entirely language
        assert "omit" in text.lower()

    def test_gap_framing_tbd(self) -> None:
        m = _minimal_manifest(source_fidelity=SourceFidelityParams(gap_framing="tbd"))
        text = build_constitution_section(m)
        # TBD framing → placeholder language
        assert "[TBD]" in text or "placeholder" in text.lower()

    def test_require_source_tracing_false_softens_language(self) -> None:
        m = _minimal_manifest(
            source_fidelity=SourceFidelityParams(require_source_tracing=False),
        )
        text = build_constitution_section(m)
        # When tracing not required, remove the "every fact must trace" line
        assert "every fact" not in text.lower()

    def test_threshold_surfaced_in_info_minimality_line(self) -> None:
        m = _minimal_manifest(
            info_min=InformationMinimalityParams(default_threshold=3500),
        )
        text = build_constitution_section(m)
        assert "3,500" in text or "3500" in text

    def test_gentle_nudge_turns_surfaced(self) -> None:
        m = _minimal_manifest(
            progress=ProgressObligationParams(gentle_nudge_turns=7),
        )
        text = build_constitution_section(m)
        assert "7" in text

    def test_state_persistence_line_rendered(self) -> None:
        m = _minimal_manifest()
        text = build_constitution_section(m)
        assert "State Persistence" in text
        assert "compaction" in text.lower()

    def test_state_persistence_custom_strategy(self) -> None:
        m = _minimal_manifest(
            state=StatePersistenceParams(compaction_strategy="state_only"),
        )
        text = build_constitution_section(m)
        assert "state_only" in text

    def test_earned_autonomy_line_rendered(self) -> None:
        m = _minimal_manifest()
        text = build_constitution_section(m)
        assert "Earned Autonomy" in text
        assert "constrained" in text  # default initial_mode

    def test_earned_autonomy_custom_mode(self) -> None:
        m = _minimal_manifest(
            autonomy=EarnedAutonomyParams(initial_mode="autonomous"),
        )
        text = build_constitution_section(m)
        assert "autonomous" in text


class TestBuildSystemPromptWithConstitution:
    def test_constitution_block_injected(self) -> None:
        m = _minimal_manifest()
        prompt = _build_system_prompt(
            hints=None,
            variables=None,
            prohibited=None,
            external_system_prompt="",
            constitution=m,
        )
        assert "CONSTITUTION" in prompt

    def test_no_constitution_no_block(self) -> None:
        prompt = _build_system_prompt(
            hints=None,
            variables=None,
            prohibited=None,
            external_system_prompt="",
            constitution=None,
        )
        assert "CONSTITUTION" not in prompt
