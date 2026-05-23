# ABOUTME: Tests for constitutional harness parameter models and manifest.
# ABOUTME: Verifies typed parameter dataclasses, frozen invariant, and defaults.

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from aec_bench.contracts.constitution import (
    ConstitutionalPrinciple,
    ConstitutionManifest,
    EarnedAutonomyParams,
    InformationMinimalityParams,
    ProgressObligationParams,
    SourceFidelityParams,
    StatePersistenceParams,
)


class TestInformationMinimalityParams:
    def test_defaults(self) -> None:
        p = InformationMinimalityParams()
        assert p.default_threshold == 2000
        assert p.search_threshold == 10_000
        assert p.preview_length == 200
        assert p.truncation_strategy == "metadata"

    def test_frozen(self) -> None:
        p = InformationMinimalityParams()
        with pytest.raises(FrozenInstanceError):
            p.default_threshold = 5000  # type: ignore[misc]

    def test_custom_values(self) -> None:
        p = InformationMinimalityParams(
            default_threshold=3000,
            search_threshold=15_000,
            preview_length=500,
            truncation_strategy="head",
        )
        assert p.default_threshold == 3000
        assert p.truncation_strategy == "head"


class TestStatePersistenceParams:
    def test_defaults(self) -> None:
        p = StatePersistenceParams()
        assert p.preserve_variables is True
        assert p.preserve_scratchpad is True
        assert p.compaction_strategy == "llm_summary"

    def test_frozen(self) -> None:
        p = StatePersistenceParams()
        with pytest.raises(FrozenInstanceError):
            p.preserve_variables = False  # type: ignore[misc]


class TestProgressObligationParams:
    def test_defaults(self) -> None:
        p = ProgressObligationParams()
        assert p.gentle_nudge_turns == 10
        assert p.strong_nudge_turns == 20
        assert p.stall_threshold_turns == 3

    def test_frozen(self) -> None:
        p = ProgressObligationParams()
        with pytest.raises(FrozenInstanceError):
            p.gentle_nudge_turns = 5  # type: ignore[misc]


class TestSourceFidelityParams:
    def test_defaults(self) -> None:
        p = SourceFidelityParams()
        assert p.require_source_tracing is True
        assert p.tbd_placeholder == "[TBD]"
        assert p.gap_framing == "exclude"

    def test_frozen(self) -> None:
        p = SourceFidelityParams()
        with pytest.raises(FrozenInstanceError):
            p.tbd_placeholder = "[MISSING]"  # type: ignore[misc]


class TestEarnedAutonomyParams:
    def test_defaults(self) -> None:
        p = EarnedAutonomyParams()
        assert p.initial_mode == "constrained"
        assert p.promotion_threshold == 2
        assert p.demotion_on_stall is True

    def test_frozen(self) -> None:
        p = EarnedAutonomyParams()
        with pytest.raises(FrozenInstanceError):
            p.initial_mode = "autonomous"  # type: ignore[misc]


class TestConstitutionalPrinciple:
    def test_required_fields(self) -> None:
        p = ConstitutionalPrinciple(
            name="information_minimality",
            description="Show only what's needed.",
            evaluation_criteria="context growth rate",
        )
        assert p.name == "information_minimality"
        assert p.enabled is True  # default

    def test_can_be_disabled(self) -> None:
        p = ConstitutionalPrinciple(
            name="earned_autonomy",
            description="Constrain first, relax later.",
            evaluation_criteria="mode transitions",
            enabled=False,
        )
        assert p.enabled is False

    def test_frozen(self) -> None:
        p = ConstitutionalPrinciple(
            name="x",
            description="y",
            evaluation_criteria="z",
        )
        with pytest.raises(FrozenInstanceError):
            p.name = "other"  # type: ignore[misc]


class TestConstitutionManifest:
    def test_empty_manifest(self) -> None:
        m = ConstitutionManifest(version="0.1.0", principles=[])
        assert m.version == "0.1.0"
        assert m.principles == []
        assert m.information_minimality is None
        assert m.state_persistence is None
        assert m.progress_obligation is None
        assert m.source_fidelity is None
        assert m.earned_autonomy is None

    def test_with_all_principles(self) -> None:
        principles = [
            ConstitutionalPrinciple(
                name=name,
                description=f"desc for {name}",
                evaluation_criteria=f"eval for {name}",
            )
            for name in [
                "information_minimality",
                "state_persistence",
                "progress_obligation",
                "source_fidelity",
                "earned_autonomy",
            ]
        ]
        m = ConstitutionManifest(
            version="0.1.0",
            principles=principles,
            information_minimality=InformationMinimalityParams(default_threshold=3000),
            state_persistence=StatePersistenceParams(compaction_strategy="state_only"),
            progress_obligation=ProgressObligationParams(gentle_nudge_turns=5),
            source_fidelity=SourceFidelityParams(gap_framing="tbd"),
            earned_autonomy=EarnedAutonomyParams(initial_mode="guided"),
        )
        assert len(m.principles) == 5
        assert m.information_minimality.default_threshold == 3000
        assert m.state_persistence.compaction_strategy == "state_only"
        assert m.earned_autonomy.initial_mode == "guided"

    def test_enabled_principle_names(self) -> None:
        principles = [
            ConstitutionalPrinciple(
                name="information_minimality",
                description="d",
                evaluation_criteria="e",
                enabled=True,
            ),
            ConstitutionalPrinciple(
                name="earned_autonomy",
                description="d",
                evaluation_criteria="e",
                enabled=False,
            ),
        ]
        m = ConstitutionManifest(version="0.1.0", principles=principles)
        assert m.enabled_principle_names() == ["information_minimality"]

    def test_frozen(self) -> None:
        m = ConstitutionManifest(version="0.1.0", principles=[])
        with pytest.raises(FrozenInstanceError):
            m.version = "0.2.0"  # type: ignore[misc]


class TestPackageReExports:
    def test_imports_from_contracts(self) -> None:
        from aec_bench.contracts import (
            ConstitutionManifest,
        )

        # Sanity check: instantiate one to prove the symbol is real
        m = ConstitutionManifest(version="0.1.0", principles=[])
        assert isinstance(m, ConstitutionManifest)


class TestParseConstitution:
    def test_minimal_manifest(self) -> None:
        from aec_bench.contracts.constitution import parse_constitution

        toml_str = """
version = "0.1.0"

[[principles]]
name = "information_minimality"
description = "Show only what's needed."
evaluation_criteria = "context growth"
"""
        m = parse_constitution(toml_str)
        assert m.version == "0.1.0"
        assert len(m.principles) == 1
        assert m.principles[0].name == "information_minimality"
        assert m.principles[0].enabled is True  # default
        # No parameter overrides provided → all None
        assert m.information_minimality is None

    def test_with_parameter_overrides(self) -> None:
        from aec_bench.contracts.constitution import parse_constitution

        toml_str = """
version = "0.1.0"

[[principles]]
name = "information_minimality"
description = "d"
evaluation_criteria = "e"

[information_minimality]
default_threshold = 3000
search_threshold = 15000

[progress_obligation]
gentle_nudge_turns = 5
strong_nudge_turns = 12
"""
        m = parse_constitution(toml_str)
        assert m.information_minimality is not None
        assert m.information_minimality.default_threshold == 3000
        assert m.information_minimality.search_threshold == 15000
        # preview_length and truncation_strategy should be defaults
        assert m.information_minimality.preview_length == 200
        assert m.information_minimality.truncation_strategy == "metadata"
        assert m.progress_obligation is not None
        assert m.progress_obligation.gentle_nudge_turns == 5
        assert m.progress_obligation.strong_nudge_turns == 12
        # state_persistence, source_fidelity, earned_autonomy omitted
        assert m.state_persistence is None
        assert m.source_fidelity is None
        assert m.earned_autonomy is None

    def test_disabled_principle(self) -> None:
        from aec_bench.contracts.constitution import parse_constitution

        toml_str = """
version = "0.1.0"

[[principles]]
name = "earned_autonomy"
description = "d"
evaluation_criteria = "e"
enabled = false
"""
        m = parse_constitution(toml_str)
        assert m.principles[0].enabled is False

    def test_default_constitution_file_exists(self) -> None:
        from aec_bench.contracts.constitution import parse_constitution

        default_path = (
            Path(__file__).resolve().parents[2] / "src" / "aec_bench" / "adapters" / "constitution_default.toml"
        )
        assert default_path.exists(), f"missing {default_path}"
        m = parse_constitution(default_path.read_text())
        assert m.version == "0.1.0"
        names = [p.name for p in m.principles]
        assert names == [
            "information_minimality",
            "state_persistence",
            "progress_obligation",
            "source_fidelity",
            "earned_autonomy",
        ]
        # Default has NO parameter overrides — all inferred
        assert m.information_minimality is None
        assert m.state_persistence is None
        assert m.progress_obligation is None
        assert m.source_fidelity is None
        assert m.earned_autonomy is None
