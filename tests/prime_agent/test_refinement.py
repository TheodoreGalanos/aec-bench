# ABOUTME: Tests Prime refinement mode validation and portable candidate rules.
# ABOUTME: Keeps candidate loading distinct from canonical task-world replay.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aec_bench.prime_agent.refinement import (
    PrimeRefinementCandidate,
    PrimeRefinementEntry,
    PrimeRefinementKind,
    PrimeRefinementMode,
    PrimeRefinementScope,
    candidate_portability_issues,
    capture_refinement_evidence,
    empty_refinement_candidate,
    install_refinement_candidate,
    validate_refinement_request,
)


def _entry(*, content: str = "Use /refine only when it can improve the work.", path: str = "") -> PrimeRefinementEntry:
    return PrimeRefinementEntry(
        id="compact-action-state",
        kind=PrimeRefinementKind.MEMORY,
        title="Keep compact action state",
        content=content,
        path=path,
        scope=PrimeRefinementScope.LOCAL,
        reference={},
        arguments={},
        metadata={},
        source="refine",
        created_at="2026-08-09T00:00:00Z",
        updated_at="2026-08-09T00:00:00Z",
        version=1,
    )


def test_fixed_candidate_mode_requires_one_exact_candidate() -> None:
    with pytest.raises(ValueError, match="requires an exact candidate"):
        validate_refinement_request(PrimeRefinementMode.CANDIDATE, None)


def test_capture_mode_rejects_a_candidate() -> None:
    with pytest.raises(ValueError, match="does not accept a candidate"):
        validate_refinement_request(PrimeRefinementMode.CAPTURE, empty_refinement_candidate())


def test_refine_command_text_is_portable() -> None:
    candidate = PrimeRefinementCandidate(prime_harness_schema=1, entries=(_entry(),))

    assert candidate_portability_issues(candidate) == ()


def test_host_path_is_not_portable() -> None:
    candidate = PrimeRefinementCandidate(
        prime_harness_schema=1,
        entries=(_entry(path=str(Path("/Users/example/private-skill"))),),
    )

    assert candidate_portability_issues(candidate) == ("harness_entry_contains_nonportable_path",)
    with pytest.raises(ValueError, match="not portable"):
        validate_refinement_request(PrimeRefinementMode.CANDIDATE, candidate)


def test_host_path_in_refinement_content_is_not_portable() -> None:
    candidate = PrimeRefinementCandidate(
        prime_harness_schema=1,
        entries=(_entry(content="Read /etc/private-state before the next action."),),
    )

    assert candidate_portability_issues(candidate) == ("harness_entry_contains_nonportable_path",)


def test_refine_text_exception_does_not_apply_to_the_entry_path() -> None:
    candidate = PrimeRefinementCandidate(
        prime_harness_schema=1,
        entries=(_entry(path="/refine"),),
    )

    assert candidate_portability_issues(candidate) == ("harness_entry_contains_nonportable_path",)


def test_candidate_keeps_same_id_local_and_global_entries(tmp_path: Path) -> None:
    local = _entry()
    global_ = local.model_copy(update={"scope": PrimeRefinementScope.GLOBAL, "content": "Global content."})
    candidate = PrimeRefinementCandidate(prime_harness_schema=1, entries=(local, global_))

    installed = install_refinement_candidate(tmp_path / "state", candidate)
    records = json.loads(installed.read_text(encoding="utf-8"))["entries"]["memory"]

    assert set(records) == {"compact-action-state", "local:compact-action-state"}
    assert {record["scope"] for record in records.values()} == {"local", "global"}
    session_directory = tmp_path / "sessions" / "prime-root"
    evidence_directory = tmp_path / "evidence"
    session_directory.mkdir(parents=True)
    evidence_directory.mkdir()
    evidence = capture_refinement_evidence(
        mode=PrimeRefinementMode.CANDIDATE,
        state_directory=tmp_path / "state",
        session_directory=session_directory,
        evidence_directory=evidence_directory,
        base=candidate,
        environment={},
        redact_values=(),
    )
    assert evidence.candidate == candidate
    assert not evidence.drifted


def test_unknown_harness_kind_is_preserved_as_nonportable_raw_evidence(tmp_path: Path) -> None:
    state_directory = tmp_path / "state"
    session_directory = tmp_path / "sessions" / "prime-root"
    evidence_directory = tmp_path / "evidence"
    harness_file = state_directory / "harness" / "harness_state.json"
    harness_file.parent.mkdir(parents=True)
    session_directory.mkdir(parents=True)
    evidence_directory.mkdir()
    harness_file.write_text(
        json.dumps(
            {
                "schema": 1,
                "entries": {
                    "prompt": {},
                    "memory": {},
                    "skill": {},
                    "subagent": {},
                    "future-kind": {"entry": {"secret": "unknown upstream data"}},
                },
                "refinements": [],
            }
        ),
        encoding="utf-8",
    )

    evidence = capture_refinement_evidence(
        mode=PrimeRefinementMode.DISCOVER,
        state_directory=state_directory,
        session_directory=session_directory,
        evidence_directory=evidence_directory,
        base=None,
        environment={},
        redact_values=(),
    )

    assert not evidence.portable
    assert evidence.issues == ("unknown_harness_kind",)
    assert evidence.sources[0].path == "prime-harness-global.json"
    assert "future-kind" in (evidence_directory / evidence.sources[0].path).read_text(encoding="utf-8")


def test_future_harness_schema_is_preserved_but_not_portable(tmp_path: Path) -> None:
    state_directory = tmp_path / "state"
    session_directory = tmp_path / "sessions" / "prime-root"
    evidence_directory = tmp_path / "evidence"
    harness_file = state_directory / "harness" / "harness_state.json"
    harness_file.parent.mkdir(parents=True)
    session_directory.mkdir(parents=True)
    evidence_directory.mkdir()
    harness_file.write_text(
        json.dumps(
            {
                "schema": 2,
                "entries": {kind.value: {} for kind in PrimeRefinementKind},
                "refinements": [],
            }
        ),
        encoding="utf-8",
    )

    evidence = capture_refinement_evidence(
        mode=PrimeRefinementMode.DISCOVER,
        state_directory=state_directory,
        session_directory=session_directory,
        evidence_directory=evidence_directory,
        base=None,
        environment={},
        redact_values=(),
    )

    assert not evidence.portable
    assert evidence.issues == ("unsupported_harness_schema",)
    assert '"schema": 2' in (evidence_directory / evidence.sources[0].path).read_text(encoding="utf-8")
