# ABOUTME: Proves durable V4 session activation selection and exact recovery.
# ABOUTME: Checks immutable bindings, linked replacement, strict scope, and pointer integrity.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from world_run_support import create_world_run

import aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository as repository_runtime
from aec_bench.ledger.durability import DurableFileReplaceError
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationWorldRunError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session_activation import (
    PUMP_STATION_SESSION_ACTIVATION_BINDING_VERSION,
    PumpStationSessionActivationBinding,
)


def _reference_repository(root: Path) -> PumpStationWorldRunRepository:
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="session-authority-run",
        episode_id="session-authority-episode",
        world_branch_id="session-authority-branch",
    )
    return run.repository


def _binding(
    repository: PumpStationWorldRunRepository,
    *,
    active_activation_id: str = "session-activation-0001",
    prior_binding_id: str | None = None,
    session_event_sequence: int = 0,
    information_set_manifest_content_id: str = "1" * 64,
    retrieval_state_head: str = "2" * 64,
) -> PumpStationSessionActivationBinding:
    snapshot = repository.current_snapshot()
    return PumpStationSessionActivationBinding(
        binding_version=PUMP_STATION_SESSION_ACTIVATION_BINDING_VERSION,
        active_activation_id=active_activation_id,
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
        sequence=snapshot.sequence,
        session_id="session-authority-session",
        agent_tenure_id="session-authority-tenure",
        actor_view_id="3" * 64,
        information_set_manifest_content_id=information_set_manifest_content_id,
        retrieval_state_head=retrieval_state_head,
        prior_binding_id=prior_binding_id,
        session_event_sequence=session_event_sequence,
        host_authority_id="session-authority-host",
    )


def test_exact_session_activation_republish_recovers_one_immutable_binding(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    repository = _reference_repository(root)
    binding = _binding(repository)

    published = repository.publish_session_activation(binding)
    reopened = PumpStationWorldRunRepository(root)
    repeated = reopened.publish_session_activation(binding)

    assert published == binding
    assert repeated == binding
    assert reopened.load_active_session_activation() == binding
    assert reopened.load_session_activation(binding.binding_id) == binding
    assert len(tuple((root / "session-authority" / "bindings").glob("*.json"))) == 1
    assert len(tuple((root / "session-authority" / "activation-claims").glob("*.json"))) == 1
    assert (root / "session-authority" / "active.json").is_file()


def test_session_activation_replacement_links_the_selected_binding(
    tmp_path: Path,
) -> None:
    repository = _reference_repository(tmp_path / "run")
    first = _binding(repository)
    repository.publish_session_activation(first)
    second = _binding(
        repository,
        active_activation_id="session-activation-0002",
        prior_binding_id=first.binding_id,
        session_event_sequence=1,
        information_set_manifest_content_id="4" * 64,
        retrieval_state_head="5" * 64,
    )

    repository.publish_session_activation(second)

    assert repository.load_active_session_activation() == second
    assert repository.load_session_activation(first.binding_id) == first
    assert repository.load_session_activation(second.binding_id) == second


def test_session_activation_rejects_changed_content_for_one_activation_id(
    tmp_path: Path,
) -> None:
    repository = _reference_repository(tmp_path / "run")
    first = _binding(repository)
    repository.publish_session_activation(first)
    conflicting = replace(
        first,
        prior_binding_id=first.binding_id,
        session_event_sequence=1,
        information_set_manifest_content_id="6" * 64,
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        repository.publish_session_activation(conflicting)

    assert raised.value.code == "session-activation-conflict"
    assert repository.load_active_session_activation() == first


@pytest.mark.parametrize(
    ("change", "expected_code"),
    (
        ({"state_id": "7" * 64}, "session-activation-stale"),
        ({"commit_id": "8" * 64}, "session-activation-stale"),
        ({"sequence": 1}, "session-activation-stale"),
        ({"run_id": "foreign-run"}, "session-activation-scope"),
        ({"episode_id": "foreign-episode"}, "session-activation-scope"),
        ({"world_branch_id": "foreign-branch"}, "session-activation-scope"),
    ),
)
def test_session_activation_rejects_stale_or_foreign_replacement(
    tmp_path: Path,
    change: dict[str, object],
    expected_code: str,
) -> None:
    repository = _reference_repository(tmp_path / "run")
    first = _binding(repository)
    repository.publish_session_activation(first)
    replacement_values = {
        "active_activation_id": "session-activation-0002",
        "prior_binding_id": first.binding_id,
        "session_event_sequence": 1,
        **change,
    }
    replacement = replace(first, **replacement_values)

    with pytest.raises(PumpStationWorldRunError) as raised:
        repository.publish_session_activation(replacement)

    assert raised.value.code == expected_code
    assert repository.load_active_session_activation() == first


@pytest.mark.parametrize(
    ("change", "expected_code"),
    (
        ({"prior_binding_id": "d" * 64}, "session-activation-stale"),
        ({"session_event_sequence": 2}, "session-activation-stale"),
        ({"host_authority_id": "another-host"}, "session-activation-authority"),
    ),
)
def test_session_activation_replacement_requires_one_monotonic_host_chain(
    tmp_path: Path,
    change: dict[str, object],
    expected_code: str,
) -> None:
    repository = _reference_repository(tmp_path / "run")
    first = _binding(repository)
    repository.publish_session_activation(first)
    replacement_values = {
        "active_activation_id": "session-activation-0002",
        "prior_binding_id": first.binding_id,
        "session_event_sequence": 1,
        **change,
    }
    replacement = replace(first, **replacement_values)

    with pytest.raises(PumpStationWorldRunError) as raised:
        repository.publish_session_activation(replacement)

    assert raised.value.code == expected_code
    assert repository.load_active_session_activation() == first


@pytest.mark.parametrize(
    "damaged_bytes",
    (
        b'{"$type":"PumpStationActiveSessionPointer"',
        b"{}\n",
    ),
)
def test_active_session_activation_fails_closed_for_a_torn_or_corrupt_pointer(
    tmp_path: Path,
    damaged_bytes: bytes,
) -> None:
    root = tmp_path / "run"
    repository = _reference_repository(root)
    repository.publish_session_activation(_binding(repository))
    (root / "session-authority" / "active.json").write_bytes(damaged_bytes)

    with pytest.raises(PumpStationWorldRunError):
        repository.load_active_session_activation()


def test_session_activation_retry_completes_a_staged_binding_after_pointer_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    repository = _reference_repository(root)
    first = _binding(repository)
    repository.publish_session_activation(first)
    second = _binding(
        repository,
        active_activation_id="session-activation-0002",
        prior_binding_id=first.binding_id,
        session_event_sequence=1,
        information_set_manifest_content_id="9" * 64,
    )
    replace_bytes = repository_runtime.replace_file_bytes_durable

    def fail_active_pointer(
        directory: Path,
        file_name: str,
        payload: bytes,
        *,
        host_private: bool = False,
    ) -> None:
        if file_name == "active.json":
            raise DurableFileReplaceError("simulated pointer interruption")
        replace_bytes(
            directory,
            file_name,
            payload,
            host_private=host_private,
        )

    monkeypatch.setattr(
        repository_runtime,
        "replace_file_bytes_durable",
        fail_active_pointer,
    )
    with pytest.raises(PumpStationWorldRunError) as raised:
        repository.publish_session_activation(second)
    assert raised.value.code == "artifact-integrity"
    monkeypatch.setattr(
        repository_runtime,
        "replace_file_bytes_durable",
        replace_bytes,
    )

    assert repository.load_active_session_activation() == first
    assert repository.publish_session_activation(second) == second
    assert repository.load_active_session_activation() == second


def test_legacy_run_never_creates_v4_session_authority_paths(
    tmp_path: Path,
) -> None:
    run = create_world_run(tmp_path / "legacy-run")
    binding = PumpStationSessionActivationBinding(
        binding_version=PUMP_STATION_SESSION_ACTIVATION_BINDING_VERSION,
        active_activation_id="legacy-session-activation",
        run_id=run.manifest.run_id,
        episode_id=run.manifest.episode_id,
        world_branch_id=run.manifest.world_branch_id,
        state_id=run.snapshot().state_id,
        commit_id=run.snapshot().commit_id,
        sequence=run.snapshot().sequence,
        session_id="legacy-session",
        agent_tenure_id="legacy-tenure",
        actor_view_id="a" * 64,
        information_set_manifest_content_id="b" * 64,
        retrieval_state_head="c" * 64,
        prior_binding_id=None,
        session_event_sequence=0,
        host_authority_id="legacy-host",
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository.publish_session_activation(binding)

    assert raised.value.code == "record-versions"
    assert not (run.repository.root / "session-authority").exists()
