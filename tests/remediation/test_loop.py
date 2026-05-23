# ABOUTME: Tests the remediation orchestrator — iteration, attempt tracking, stop conditions.
# ABOUTME: Uses stub proposer + stub verifier to isolate loop logic from real LLM / verify.py.

from pathlib import Path

from aec_bench.contracts.remediation import (
    Patch,
    PatchProposal,
    PatchStatus,
)
from aec_bench.remediation.loop import RemediationConfig, run_remediation_loop
from aec_bench.remediation.verifier_runner import VerifierResult


class _StubProposer:
    """Returns canned proposals keyed by (section, criterion); supports per-iteration variance."""

    def __init__(self, proposals_by_iteration: list[list[PatchProposal]]) -> None:
        self._proposals = proposals_by_iteration
        self.call_count = 0

    def __call__(self, *, section_id, section_excerpt, criterion, evidence, **_kwargs):
        # call_count tracks total proposer calls; pick the right iteration's list
        for iteration_proposals in self._proposals:
            for p in iteration_proposals:
                if p.patch.section_id == section_id and p.criterion == criterion:
                    self.call_count += 1
                    return p
        self.call_count += 1
        return PatchProposal(
            patch=Patch(section_id=section_id, locator_phrase="", replacement="", occurrence=1),
            criterion=criterion,
            evidence=evidence,
            rationale="no proposal",
            confidence="low",
            status=PatchStatus.REVIEW,
        )


class _StubVerifier:
    def __init__(self, reward_sequence: list[float], details_sequence: list[dict]) -> None:
        self._rewards = reward_sequence
        self._details = details_sequence
        self.call_count = 0

    def __call__(self, *, output_md_text, **_kwargs):
        reward = self._rewards[self.call_count]
        details = self._details[self.call_count]
        self.call_count += 1
        return VerifierResult(reward=reward, details=details)


def _details(reward, unsatisfied: dict[str, list[str]]) -> dict:
    """Build a minimal verifier details.json shape."""
    d = {"reward": reward}
    for dim_id, criteria in unsatisfied.items():
        d[dim_id] = {
            "score": 5.0,
            "max_score": 10.0,
            "unsatisfied": criteria,
            "evidence": f"Evidence for {dim_id}",
        }
    return d


def _setup_run(tmp_path: Path, initial_output: str, initial_details: dict) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "output.md").write_text(initial_output)
    (run_dir / "logs" / "verifier").mkdir(parents=True)
    import json

    (run_dir / "logs" / "verifier" / "details.json").write_text(json.dumps(initial_details))
    return run_dir


def test_loop_stops_at_plateau(tmp_path: Path) -> None:
    run_dir = _setup_run(
        tmp_path,
        initial_output="# Contractual Clarity\n\nInitial body content here.\n",
        initial_details=_details(0.70, {"contractual_clarity": ["vague"]}),
    )

    apply_prop = PatchProposal(
        patch=Patch(
            section_id="contractual_clarity",
            locator_phrase="Initial",
            replacement="Revised",
            occurrence=1,
        ),
        criterion="vague",
        evidence="Evidence for contractual_clarity",
        rationale="r",
        confidence="high",
        status=PatchStatus.APPLY,
    )

    proposer = _StubProposer(proposals_by_iteration=[[apply_prop], [apply_prop]])
    verifier = _StubVerifier(
        reward_sequence=[0.71, 0.715],  # tiny deltas → plateau
        details_sequence=[
            _details(0.71, {"contractual_clarity": ["vague"]}),
            _details(0.715, {"contractual_clarity": ["vague"]}),
        ],
    )

    result = run_remediation_loop(
        run_dir=run_dir,
        task_dir=tmp_path / "task",  # unused by stubs
        proposer=proposer,
        verifier=verifier,
        config=RemediationConfig(max_iterations=5, plateau_threshold=0.02),
    )
    assert result.stop_reason == "plateau"
    assert len(result.iterations) >= 1


def test_loop_stops_at_max_iterations(tmp_path: Path) -> None:
    run_dir = _setup_run(
        tmp_path,
        initial_output="# D\n\nbody one.\n",
        initial_details=_details(0.5, {"d": ["c"]}),
    )

    # Each iteration proposer returns a fresh patch whose locator exists in the current text.
    # Since the loop calls the proposer with current_output each iteration, we need different
    # locators. Simplest: all apply to fresh text by always locating the heading's content.
    apply_prop = PatchProposal(
        patch=Patch(section_id="d", locator_phrase="body one.", replacement="body one.", occurrence=1),
        criterion="c",
        evidence="Evidence for d",
        rationale="r",
        confidence="high",
        status=PatchStatus.APPLY,
    )
    proposer = _StubProposer(proposals_by_iteration=[[apply_prop]] * 5)
    verifier = _StubVerifier(
        reward_sequence=[0.6, 0.7, 0.8, 0.9, 1.0],
        details_sequence=[_details(0.6 + i * 0.1, {"d": ["c"]}) for i in range(5)],
    )

    result = run_remediation_loop(
        run_dir=run_dir,
        task_dir=tmp_path / "task",
        proposer=proposer,
        verifier=verifier,
        config=RemediationConfig(max_iterations=2, plateau_threshold=0.001),
    )
    assert result.stop_reason == "max_iterations"
    assert len(result.iterations) == 2


def test_loop_escalates_to_hitl_after_two_failed_attempts(tmp_path: Path) -> None:
    """Patch proposed twice, criterion still fails after both — goes to HITL."""
    run_dir = _setup_run(
        tmp_path,
        initial_output="# D\n\nbody body body\n",  # locator stable
        initial_details=_details(0.5, {"d": ["stubborn"]}),
    )

    stubborn = PatchProposal(
        patch=Patch(section_id="d", locator_phrase="body body body", replacement="body body body", occurrence=1),
        criterion="stubborn",
        evidence="Evidence for d",
        rationale="r",
        confidence="medium",
        status=PatchStatus.APPLY,
    )
    proposer = _StubProposer(proposals_by_iteration=[[stubborn]] * 5)
    # Reward rises enough between iterations to avoid plateau; criterion stays unsatisfied,
    # so after 2 attempts the loop escalates to HITL.
    verifier = _StubVerifier(
        reward_sequence=[0.6, 0.7, 0.8, 0.9, 1.0],
        details_sequence=[
            _details(0.6, {"d": ["stubborn"]}),
            _details(0.7, {"d": ["stubborn"]}),
            _details(0.8, {"d": ["stubborn"]}),
            _details(0.9, {"d": ["stubborn"]}),
            _details(1.0, {"d": ["stubborn"]}),
        ],
    )

    result = run_remediation_loop(
        run_dir=run_dir,
        task_dir=tmp_path / "task",
        proposer=proposer,
        verifier=verifier,
        config=RemediationConfig(max_iterations=5, plateau_threshold=0.001),
    )
    hitl_criteria = {h.criterion for h in result.hitl_items}
    assert "stubborn" in hitl_criteria


def test_loop_no_unsatisfied_criteria_exits_immediately(tmp_path: Path) -> None:
    run_dir = _setup_run(
        tmp_path,
        initial_output="perfect",
        initial_details={
            "reward": 1.0,
            "completeness": {"score": 10, "max_score": 10, "unsatisfied": []},
        },
    )

    proposer = _StubProposer(proposals_by_iteration=[])
    verifier = _StubVerifier(reward_sequence=[], details_sequence=[])

    result = run_remediation_loop(
        run_dir=run_dir,
        task_dir=tmp_path / "task",
        proposer=proposer,
        verifier=verifier,
        config=RemediationConfig(max_iterations=5, plateau_threshold=0.02),
    )
    assert result.stop_reason == "no_defects"
    assert len(result.iterations) == 0


def test_loop_carries_final_output_text(tmp_path: Path) -> None:
    """The patched output.md text must be returned in RemediationResult.final_output_text."""
    run_dir = _setup_run(
        tmp_path,
        initial_output="# D\n\nInitial body.\n",
        initial_details=_details(0.5, {"d": ["c"]}),
    )
    apply_prop = PatchProposal(
        patch=Patch(
            section_id="d",
            locator_phrase="Initial",
            replacement="FIXED",
            occurrence=1,
        ),
        criterion="c",
        evidence="Evidence for d",
        rationale="r",
        confidence="high",
        status=PatchStatus.APPLY,
    )
    proposer = _StubProposer(proposals_by_iteration=[[apply_prop]])
    verifier = _StubVerifier(
        reward_sequence=[0.9],
        details_sequence=[_details(0.9, {"d": []})],  # defect resolved
    )
    result = run_remediation_loop(
        run_dir=run_dir,
        task_dir=tmp_path / "task",
        proposer=proposer,
        verifier=verifier,
        config=RemediationConfig(max_iterations=3, plateau_threshold=0.001),
    )
    assert "FIXED" in result.final_output_text


def test_loop_uses_annotated_path_when_evidence_has_quoted_span(tmp_path: Path) -> None:
    """When evidence contains a quoted span that appears uniquely in the section,
    the loop should use the annotated path via propose_patch_annotated."""
    run_dir = _setup_run(
        tmp_path,
        initial_output="# D\n\nThe Contractor shall allow for investigation works in scope.\n",
        initial_details={
            "reward": 0.5,
            "d": {
                "score": 5,
                "max_score": 10,
                "unsatisfied": ["vague"],
                "evidence": "Uses open-ended 'allow for investigation works' language.",
            },
        },
    )

    calls: list[str] = []

    def stub_proposer(**kwargs):
        from aec_bench.contracts.remediation import Patch, PatchProposal, PatchStatus

        if "annotated_section" in kwargs:
            calls.append("annotated")
            return PatchProposal(
                patch=Patch(
                    section_id=kwargs["section_id"],
                    locator_phrase=kwargs["span_to_replace"],
                    replacement="allow up to 40 hours of investigation works",
                    occurrence=1,
                ),
                criterion=kwargs["criterion"],
                evidence=kwargs["evidence"],
                rationale="r",
                confidence="high",
                status=PatchStatus.APPLY,
            )
        calls.append("v1_locator")
        return PatchProposal(
            patch=Patch(section_id="d", locator_phrase="", replacement="", occurrence=1),
            criterion=kwargs["criterion"],
            evidence=kwargs["evidence"],
            rationale="r",
            confidence="low",
            status=PatchStatus.REVIEW,
        )

    verifier = _StubVerifier(
        reward_sequence=[0.9],
        details_sequence=[_details(0.9, {"d": []})],
    )
    result = run_remediation_loop(
        run_dir=run_dir,
        task_dir=tmp_path / "task",
        proposer=stub_proposer,
        verifier=verifier,
        config=RemediationConfig(max_iterations=2, plateau_threshold=0.001),
    )
    assert "annotated" in calls  # v2 path was used
    assert "40 hours" in result.final_output_text


def test_loop_falls_back_to_v1_when_no_quoted_span(tmp_path: Path) -> None:
    """When evidence has no quoted span, the loop falls back to the v1 locator path."""
    run_dir = _setup_run(
        tmp_path,
        initial_output="# D\n\nSome vague body text.\n",
        initial_details={
            "reward": 0.5,
            "d": {
                "score": 5,
                "max_score": 10,
                "unsatisfied": ["vague"],
                "evidence": "Section is unspecific without quoted examples.",
            },
        },
    )

    calls: list[str] = []

    def stub_proposer(**kwargs):
        from aec_bench.contracts.remediation import Patch, PatchProposal, PatchStatus

        if "annotated_section" in kwargs:
            calls.append("annotated")
        else:
            calls.append("v1_locator")
        return PatchProposal(
            patch=Patch(section_id="d", locator_phrase="vague", replacement="specific", occurrence=1),
            criterion=kwargs["criterion"],
            evidence=kwargs["evidence"],
            rationale="r",
            confidence="medium",
            status=PatchStatus.APPLY,
        )

    verifier = _StubVerifier(
        reward_sequence=[0.9],
        details_sequence=[_details(0.9, {"d": []})],
    )
    run_remediation_loop(
        run_dir=run_dir,
        task_dir=tmp_path / "task",
        proposer=stub_proposer,
        verifier=verifier,
        config=RemediationConfig(max_iterations=2, plateau_threshold=0.001),
    )
    assert "v1_locator" in calls
    assert "annotated" not in calls


def test_loop_writes_proposer_log(tmp_path: Path) -> None:
    """Every proposer call writes a record to iteration_N/proposer_log.jsonl."""
    run_dir = _setup_run(
        tmp_path,
        initial_output="# D\n\nSome 'marked' text in scope.\n",
        initial_details={
            "reward": 0.5,
            "d": {
                "score": 5,
                "max_score": 10,
                "unsatisfied": ["c"],
                "evidence": "The phrase 'marked' is too vague.",
            },
        },
    )

    def stub_proposer(**kwargs):
        from aec_bench.contracts.remediation import Patch, PatchProposal, PatchStatus

        return PatchProposal(
            patch=Patch(
                section_id=kwargs["section_id"],
                locator_phrase=kwargs.get("span_to_replace", "marked"),
                replacement="explicit",
                occurrence=1,
            ),
            criterion=kwargs["criterion"],
            evidence=kwargs["evidence"],
            rationale="r",
            confidence="high",
            status=PatchStatus.APPLY,
        )

    verifier = _StubVerifier(
        reward_sequence=[0.9],
        details_sequence=[_details(0.9, {"d": []})],
    )
    run_remediation_loop(
        run_dir=run_dir,
        task_dir=tmp_path / "task",
        proposer=stub_proposer,
        verifier=verifier,
        config=RemediationConfig(max_iterations=2, plateau_threshold=0.001),
    )

    log_path = run_dir / "remediation" / "iteration_1" / "proposer_log.jsonl"
    assert log_path.exists()
    import json

    lines = [json.loads(ln) for ln in log_path.read_text().strip().split("\n") if ln]
    assert len(lines) >= 1
    assert lines[0]["section_id"] == "d"
    assert lines[0]["criterion"] == "c"
    assert "path" in lines[0]
    assert lines[0]["path"] in ("annotated", "v1_locator")


def test_loop_uses_extracted_section_refs(tmp_path: Path) -> None:
    """When evidence mentions a real section (e.g. '2.4 Electrical'), loop targets that section
    even if the criterion's dimension_id (e.g. 'scope_coverage') isn't a real heading."""
    run_dir = _setup_run(
        tmp_path,
        initial_output="""# 1. Intro

Intro body.

# Section 2.4 Electrical

The Contractor shall allow for investigation works in electrical scope.
""",
        initial_details={
            "reward": 0.5,
            "scope_coverage": {
                "score": 5,
                "max_score": 10,
                "unsatisfied": ["vague"],
                "evidence": "Section 2.4 Electrical uses 'allow for investigation works' language.",
            },
        },
    )

    calls: list[dict] = []

    def stub_proposer(**kwargs):
        from aec_bench.contracts.remediation import Patch, PatchProposal, PatchStatus

        calls.append(dict(kwargs))
        return PatchProposal(
            patch=Patch(
                section_id=kwargs["section_id"],
                locator_phrase=kwargs.get("span_to_replace", ""),
                replacement="allow up to 40 hours of investigation works",
                occurrence=1,
            ),
            criterion=kwargs["criterion"],
            evidence=kwargs["evidence"],
            rationale="r",
            confidence="high",
            status=PatchStatus.APPLY,
        )

    verifier = _StubVerifier(
        reward_sequence=[0.9],
        details_sequence=[_details(0.9, {"scope_coverage": []})],
    )
    result = run_remediation_loop(
        run_dir=run_dir,
        task_dir=tmp_path / "task",
        proposer=stub_proposer,
        verifier=verifier,
        config=RemediationConfig(max_iterations=2, plateau_threshold=0.001),
    )
    # The proposer should have been called with section_id pointing to the real heading,
    # not the dimension id.
    section_ids = {c["section_id"] for c in calls}
    assert "scope_coverage" not in section_ids
    # At least one call was for the 2.4 Electrical section
    assert any("electrical" in sid for sid in section_ids)
    assert "40 hours" in result.final_output_text


def test_loop_uses_llm_selector_when_regex_yields_nothing(tmp_path: Path) -> None:
    """When evidence has no regex-matchable section refs, injected LLM selector picks sections."""
    run_dir = _setup_run(
        tmp_path,
        initial_output="""# 1. Intro

Intro body.

# 2. Scope of Works

Vague scope body here.
""",
        initial_details={
            "reward": 0.5,
            "scope_coverage": {
                "score": 5,
                "max_score": 10,
                "unsatisfied": ["vague"],
                "evidence": "The scope section is generally unspecific.",
            },
        },
    )

    selector_calls: list[tuple[str, list[str]]] = []

    def stub_selector(evidence: str, available_sections: list[str]) -> list[str]:
        selector_calls.append((evidence, available_sections))
        return ["scope_of_works"]

    def stub_proposer(**kwargs):
        from aec_bench.contracts.remediation import Patch, PatchProposal, PatchStatus

        return PatchProposal(
            patch=Patch(
                section_id=kwargs["section_id"],
                locator_phrase="Vague",
                replacement="Specific",
                occurrence=1,
            ),
            criterion=kwargs["criterion"],
            evidence=kwargs["evidence"],
            rationale="r",
            confidence="high",
            status=PatchStatus.APPLY,
        )

    verifier = _StubVerifier(
        reward_sequence=[0.9],
        details_sequence=[_details(0.9, {"scope_coverage": []})],
    )
    result = run_remediation_loop(
        run_dir=run_dir,
        task_dir=tmp_path / "task",
        proposer=stub_proposer,
        verifier=verifier,
        section_selector=stub_selector,
        config=RemediationConfig(max_iterations=2, plateau_threshold=0.001),
    )
    assert len(selector_calls) == 1
    assert "unspecific" in selector_calls[0][0]
    assert "Specific" in result.final_output_text


def test_loop_respects_iteration_callback_stop(tmp_path: Path) -> None:
    """Callback returning False after iteration 1 stops the loop with interactive_stop."""
    run_dir = _setup_run(
        tmp_path,
        initial_output="# D\n\n'marked' body in scope.\n",
        initial_details={
            "reward": 0.5,
            "d": {
                "score": 5,
                "max_score": 10,
                "unsatisfied": ["c"],
                "evidence": "The phrase 'marked' is vague.",
            },
        },
    )

    def stub_proposer(**kwargs):
        from aec_bench.contracts.remediation import Patch, PatchProposal, PatchStatus

        return PatchProposal(
            patch=Patch(
                section_id=kwargs["section_id"],
                locator_phrase=kwargs.get("span_to_replace", "marked"),
                replacement="clear",
                occurrence=1,
            ),
            criterion=kwargs["criterion"],
            evidence=kwargs["evidence"],
            rationale="r",
            confidence="high",
            status=PatchStatus.APPLY,
        )

    verifier = _StubVerifier(
        reward_sequence=[0.6, 0.7, 0.8],
        details_sequence=[_details(0.6 + i * 0.1, {"d": ["c"]}) for i in range(3)],
    )

    calls = []

    def stop_after_first(it) -> bool:
        calls.append(it.iteration)
        return False  # halt

    result = run_remediation_loop(
        run_dir=run_dir,
        task_dir=tmp_path / "task",
        proposer=stub_proposer,
        verifier=verifier,
        config=RemediationConfig(max_iterations=5, plateau_threshold=0.001),
        on_iteration=stop_after_first,
    )
    assert result.stop_reason == "interactive_stop"
    assert calls == [1]  # only one iteration before callback halted


def test_loop_continues_when_callback_returns_true(tmp_path: Path) -> None:
    """Callback returning True lets the loop continue through normal stop conditions."""
    run_dir = _setup_run(
        tmp_path,
        initial_output="# D\n\n'x' body\n",
        initial_details={
            "reward": 0.5,
            "d": {
                "score": 5,
                "max_score": 10,
                "unsatisfied": ["c"],
                "evidence": "Phrase 'x' vague.",
            },
        },
    )

    def stub_proposer(**kwargs):
        from aec_bench.contracts.remediation import Patch, PatchProposal, PatchStatus

        return PatchProposal(
            patch=Patch(
                section_id=kwargs["section_id"],
                locator_phrase=kwargs.get("span_to_replace", "x"),
                replacement="y",
                occurrence=1,
            ),
            criterion=kwargs["criterion"],
            evidence=kwargs["evidence"],
            rationale="r",
            confidence="high",
            status=PatchStatus.APPLY,
        )

    verifier = _StubVerifier(
        reward_sequence=[0.7, 0.9],
        details_sequence=[
            _details(0.7, {"d": ["c"]}),
            _details(0.9, {"d": []}),
        ],
    )

    calls = []

    def always_continue(it) -> bool:
        calls.append(it.iteration)
        return True

    result = run_remediation_loop(
        run_dir=run_dir,
        task_dir=tmp_path / "task",
        proposer=stub_proposer,
        verifier=verifier,
        config=RemediationConfig(max_iterations=5, plateau_threshold=0.001),
        on_iteration=always_continue,
    )
    # Should have run enough iterations for callback to be called at least once
    assert len(calls) >= 1
    # Loop stops via normal condition (no_defects after iteration 2), NOT interactive_stop
    assert result.stop_reason != "interactive_stop"
