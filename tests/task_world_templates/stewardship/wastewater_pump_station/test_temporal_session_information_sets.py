# ABOUTME: Tests immutable V2 temporal session information-set publication and lookup.
# ABOUTME: Proves current-session selection without changing existing V1 artifact bytes.

from __future__ import annotations

from pathlib import Path

import pytest

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence import (
    TemporalAccessContext,
    TemporalEvidenceIntegrityError,
    TemporalEvidenceRepository,
    TemporalInformationSetManifest,
    TemporalSessionInformationSetManifestV2,
)


def _context() -> TemporalAccessContext:
    return TemporalAccessContext(
        run_id="run-session-projection",
        episode_id="episode-session-projection",
        world_instance_id="station-001",
        world_branch_id="branch-session-projection",
        world_state_id="state-004",
        world_commit_id="commit-004",
        world_sequence=4,
        world_time_seconds=86_400,
        actor_id="pump-station-actor",
        actor_role="station-steward",
        agent_tenure_id="tenure-002",
        session_id="session-002",
        base_view_id="view-004",
        prior_information_set_id="information-set-004",
        tool_contract_id="pump-station-actor-interface.v2",
        branch_ancestor_ids=(),
    )


def _session_manifest(
    *,
    sequence: int = 0,
    prior_binding_content_id: str | None = None,
    information_set_id: str = "information-set-004",
    retrieval_state_content_id: str | None = None,
    visible_material_ids: tuple[str, ...] = ("source-reference-system",),
) -> TemporalSessionInformationSetManifestV2:
    context = _context()
    return TemporalSessionInformationSetManifestV2(
        session_binding_sequence=sequence,
        session_activation_content_id=canonical_content_sha256({"activation": context.session_id}),
        prior_session_binding_content_id=prior_binding_content_id,
        task_world_id="wastewater-pump-station-stewardship",
        run_id=context.run_id,
        episode_id=context.episode_id,
        world_instance_id=context.world_instance_id,
        world_branch_id=context.world_branch_id,
        branch_ancestor_ids=context.branch_ancestor_ids,
        world_state_id=context.world_state_id,
        world_commit_id=context.world_commit_id,
        world_sequence=context.world_sequence,
        world_time_seconds=context.world_time_seconds,
        actor_id=context.actor_id,
        actor_role=context.actor_role,
        agent_tenure_id=context.agent_tenure_id,
        session_id=context.session_id,
        base_view_id=context.base_view_id,
        information_set_id=information_set_id,
        tenure_started_at_seconds=context.world_time_seconds,
        observation_history_view_ids=(context.base_view_id,),
        continuity_carrier="current_actor_view",
        conversation_prefix_id=None,
        tool_contract_id=context.tool_contract_id,
        workspace_tool_ids=("pump-station-actor-interface.v2",),
        source_artifact_ids=(
            "source-reference-system",
            "source-package",
            "source-temporal-bundle",
        ),
        visible_material_ids=visible_material_ids,
        retrieval_state_content_id=(
            retrieval_state_content_id or canonical_content_sha256({"retrieval_state": sequence})
        ),
    )


def test_session_information_sets_keep_v1_bytes_and_load_current_and_history(
    tmp_path: Path,
) -> None:
    repository = TemporalEvidenceRepository(tmp_path / "temporal-evidence")
    context = _context()
    legacy = TemporalInformationSetManifest(
        information_set_id=context.prior_information_set_id,
        base_view_id=context.base_view_id,
        agent_tenure_id=context.agent_tenure_id,
        tenure_started_at_seconds=context.world_time_seconds,
        observation_history_view_ids=(context.base_view_id,),
        continuity_carrier="current_actor_view",
        workspace_tool_ids=("pump-station-actor-interface.v2",),
        visible_material_ids=(),
    )
    repository.publish_current_information_set(context, legacy)
    legacy_path = repository.root / "private" / "information-sets" / f"{legacy.content_sha256}.json"
    legacy_bytes = legacy_path.read_bytes()
    first = _session_manifest()
    second = _session_manifest(
        sequence=1,
        prior_binding_content_id=first.content_sha256,
        information_set_id="information-set-after-search",
        visible_material_ids=("source-reference-system", "event-search-001"),
    )

    repository.publish_current_session_information_set(first)
    repository.publish_current_session_information_set(second)
    repository.publish_current_session_information_set(second)
    restarted = TemporalEvidenceRepository(repository.root)

    assert (
        restarted.load_current_session_information_set(
            run_id=context.run_id,
            session_id=context.session_id,
            agent_tenure_id=context.agent_tenure_id,
        )
        == second
    )
    assert (
        restarted.load_session_information_set(
            first.content_sha256,
            run_id=context.run_id,
            session_id=context.session_id,
            agent_tenure_id=context.agent_tenure_id,
        )
        == first
    )
    assert repository.load_current_information_set(context) == legacy
    assert legacy_path.read_bytes() == legacy_bytes


def test_session_information_set_publication_rejects_broken_or_foreign_chain(
    tmp_path: Path,
) -> None:
    repository = TemporalEvidenceRepository(tmp_path / "temporal-evidence")
    context = _context()
    first = _session_manifest()
    repository.publish_current_session_information_set(first)
    changed_at_same_sequence = _session_manifest(
        information_set_id="changed-at-same-sequence",
    )

    with pytest.raises(
        TemporalEvidenceIntegrityError,
        match="session information-set sequence",
    ):
        repository.publish_current_session_information_set(changed_at_same_sequence)

    with pytest.raises(
        TemporalEvidenceIntegrityError,
        match="another session",
    ):
        repository.load_session_information_set(
            first.content_sha256,
            run_id=context.run_id,
            session_id="session-foreign",
            agent_tenure_id=context.agent_tenure_id,
        )


def test_first_session_information_set_must_start_the_binding_chain(
    tmp_path: Path,
) -> None:
    repository = TemporalEvidenceRepository(tmp_path / "temporal-evidence")
    orphan = _session_manifest(
        sequence=1,
        prior_binding_content_id=canonical_content_sha256({"missing": "prior"}),
    )

    with pytest.raises(
        TemporalEvidenceIntegrityError,
        match="must start at sequence zero",
    ):
        repository.publish_current_session_information_set(orphan)

    assert (
        repository.load_current_session_information_set(
            run_id=orphan.run_id,
            session_id=orphan.session_id,
            agent_tenure_id=orphan.agent_tenure_id,
        )
        is None
    )
