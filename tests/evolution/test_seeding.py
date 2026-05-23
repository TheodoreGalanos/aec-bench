# ABOUTME: Tests for deterministic skill auto-seeding based on detected behavioral patterns.
# ABOUTME: Covers pattern-to-skill mapping, budget enforcement, and skip-if-exists logic.

from aec_bench.evolution.analysis import BehavioralPattern
from aec_bench.evolution.seeding import compute_seed_skills


def _make_pattern(name: str, count: int = 3) -> BehavioralPattern:
    return BehavioralPattern(
        name=name,
        count=count,
        description=f"Pattern: {name}",
        affected_trial_ids=tuple(f"t{i}" for i in range(count)),
    )


class TestComputeSeedSkills:
    def test_blind_action_seeds_verification_skill(self) -> None:
        patterns = [_make_pattern("blind_action")]
        seeds = compute_seed_skills(patterns, existing_skill_names=set())
        assert len(seeds) == 1
        assert seeds[0].name == "verification-checkpoint"
        assert "verify" in seeds[0].body.lower()

    def test_no_verification_seeds_skill(self) -> None:
        patterns = [_make_pattern("no_verification")]
        seeds = compute_seed_skills(patterns, existing_skill_names=set())
        assert len(seeds) == 1
        assert seeds[0].name == "mandatory-verification"

    def test_skips_existing_skill(self) -> None:
        patterns = [_make_pattern("blind_action")]
        seeds = compute_seed_skills(
            patterns,
            existing_skill_names={"verification-checkpoint"},
        )
        assert seeds == []

    def test_respects_budget(self) -> None:
        patterns = [
            _make_pattern("blind_action"),
            _make_pattern("no_verification"),
            _make_pattern("analysis_paralysis"),
        ]
        seeds = compute_seed_skills(
            patterns,
            existing_skill_names=set(),
            budget_remaining=1,
        )
        assert len(seeds) == 1
        assert seeds[0].name == "verification-checkpoint"

    def test_no_patterns_no_skills(self) -> None:
        seeds = compute_seed_skills([], existing_skill_names=set())
        assert seeds == []

    def test_unknown_pattern_is_skipped(self) -> None:
        patterns = [_make_pattern("some_unknown_pattern")]
        seeds = compute_seed_skills(patterns, existing_skill_names=set())
        assert seeds == []

    def test_all_three_patterns_produce_three_skills(self) -> None:
        patterns = [
            _make_pattern("blind_action"),
            _make_pattern("no_verification"),
            _make_pattern("analysis_paralysis"),
        ]
        seeds = compute_seed_skills(patterns, existing_skill_names=set())
        assert len(seeds) == 3
        names = {s.name for s in seeds}
        assert names == {"verification-checkpoint", "mandatory-verification", "action-forcing"}

    def test_budget_none_returns_all_matching(self) -> None:
        patterns = [
            _make_pattern("blind_action"),
            _make_pattern("no_verification"),
        ]
        seeds = compute_seed_skills(
            patterns,
            existing_skill_names=set(),
            budget_remaining=None,
        )
        assert len(seeds) == 2

    def test_analysis_paralysis_seeds_action_forcing(self) -> None:
        patterns = [_make_pattern("analysis_paralysis")]
        seeds = compute_seed_skills(patterns, existing_skill_names=set())
        assert len(seeds) == 1
        assert seeds[0].name == "action-forcing"

    def test_partial_existing_skills_skipped(self) -> None:
        patterns = [
            _make_pattern("blind_action"),
            _make_pattern("no_verification"),
        ]
        seeds = compute_seed_skills(
            patterns,
            existing_skill_names={"verification-checkpoint"},
        )
        assert len(seeds) == 1
        assert seeds[0].name == "mandatory-verification"


class TestNewSeedSkills:
    def test_seeds_progressive_verification_for_redundant_verification(self) -> None:
        pattern = BehavioralPattern(
            name="redundant_verification",
            count=2,
            description="Agent re-checks same results repeatedly",
            affected_trial_ids=("t1", "t2"),
        )
        seeds = compute_seed_skills([pattern], set(), budget_remaining=5)
        assert len(seeds) == 1
        assert seeds[0].name == "progressive-verification"

    def test_seeds_read_before_act_for_no_exploration(self) -> None:
        pattern = BehavioralPattern(
            name="no_exploration",
            count=2,
            description="Agent starts executing without reading the task",
            affected_trial_ids=("t1", "t2"),
        )
        seeds = compute_seed_skills([pattern], set(), budget_remaining=5)
        assert len(seeds) == 1
        assert seeds[0].name == "read-before-act"

    def test_all_five_patterns_produce_five_skills(self) -> None:
        patterns = [
            _make_pattern("blind_action"),
            _make_pattern("no_verification"),
            _make_pattern("analysis_paralysis"),
            _make_pattern("redundant_verification"),
            _make_pattern("no_exploration"),
        ]
        seeds = compute_seed_skills(patterns, existing_skill_names=set())
        assert len(seeds) == 5
        names = {s.name for s in seeds}
        assert names == {
            "verification-checkpoint",
            "mandatory-verification",
            "action-forcing",
            "progressive-verification",
            "read-before-act",
        }

    def test_new_patterns_respect_budget(self) -> None:
        patterns = [
            _make_pattern("redundant_verification"),
            _make_pattern("no_exploration"),
        ]
        seeds = compute_seed_skills(patterns, existing_skill_names=set(), budget_remaining=1)
        assert len(seeds) == 1
        assert seeds[0].name == "progressive-verification"

    def test_new_patterns_skip_existing(self) -> None:
        patterns = [
            _make_pattern("redundant_verification"),
            _make_pattern("no_exploration"),
        ]
        seeds = compute_seed_skills(
            patterns,
            existing_skill_names={"progressive-verification"},
        )
        assert len(seeds) == 1
        assert seeds[0].name == "read-before-act"
