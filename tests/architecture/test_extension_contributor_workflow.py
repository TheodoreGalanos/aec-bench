# ABOUTME: Exercises the owner-descriptor workflow for a test-local world and lifecycle extension.
# ABOUTME: Proves conformance entry points and catalogue rendering without adding production registrations.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from aec_bench.catalogue import render_lifecycle_catalogue, render_world_catalogue
from aec_bench.contracts.evidence_lifecycle import EvidenceCheckpointSpec, EvidenceLifecycleSpec, LifecycleTaskMetadata
from aec_bench.contracts.identity import EntityIdentity, EntityKey, MemberIdentity
from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef
from aec_bench.contracts.task_definition import Difficulty, Lifecycle, Visibility
from aec_bench.lifecycles.conformance import LifecycleConformanceCase, build_lifecycle_conformance_case
from aec_bench.lifecycles.runtime.definition import LifecycleDefinition, LifecycleOwnerDescriptor
from aec_bench.lifecycles.runtime.lifecycle import run_lifecycle
from aec_bench.worlds.conformance import WorldConformanceCase, WorldConformanceScenario, run_world_conformance
from aec_bench.worlds.runtime.definition import (
    InteractiveWorldDefinition,
    InteractiveWorldOwnerDescriptor,
    InteractiveWorldProfileMetadata,
    LoadedInteractiveWorldProfile,
)
from aec_bench.worlds.runtime.world_logic import ActionRejected, Transition
from tests.support.lifecycle_episode import deterministic_episode_environment


@dataclass(frozen=True, slots=True)
class _MockState:
    step: int


@dataclass(frozen=True, slots=True)
class _MockObservation:
    step: int


_MOCK_WORLD_IDENTITY = EntityIdentity(
    id=UUID("01a056f1-af83-7d01-8e6f-5b72d4c6a101"),
    key=EntityKey("examples/contributor-world"),
    version=1,
)
_MOCK_PROFILE_IDENTITY = MemberIdentity(
    id=UUID("01a056f1-af83-7d02-8e6f-5b72d4c6a102"),
    key=EntityKey("examples/contributor-world/default"),
    version=1,
    parent_id=_MOCK_WORLD_IDENTITY.id,
    registration_id="default",
)
_MOCK_PROFILE = InteractiveWorldProfileRef(
    task_world_id="contributor-world",
    profile_id="default",
    profile_content_sha256=hashlib.sha256(b"contributor-world-profile").hexdigest(),
)


def _mock_world_definition() -> InteractiveWorldDefinition:
    return InteractiveWorldDefinition(
        identity=_MOCK_WORLD_IDENTITY,
        build=WorldBuildRef(
            task_world_id="contributor-world",
            entry_point="tests.architecture.test_extension_contributor_workflow:_mock_world_definition",
            artifact_sha256="a" * 64,
        ),
        title="Contributor example world",
        summary="A small deterministic world used by the contributor workflow test.",
        domain="examples",
        tags=("example", "contributor"),
        capabilities=frozenset(),
        profiles=(_MOCK_PROFILE,),
        profile_identities=(_MOCK_PROFILE_IDENTITY,),
        profile_metadata=(
            InteractiveWorldProfileMetadata(
                profile_id="default",
                title="Default profile",
                summary="A deterministic profile for the contributor workflow test.",
                category="example",
                difficulty=Difficulty.EASY,
                lifecycle=Lifecycle.PROPOSED,
                visibility=Visibility.PUBLIC,
                tags=("example",),
            ),
        ),
        profile_loader=lambda reference: LoadedInteractiveWorldProfile(reference=reference, value={"step": 0}),
    )


def _mock_world_conformance_case() -> WorldConformanceCase:
    def transition(state: _MockState, action: str) -> Transition[_MockState, str] | ActionRejected:
        if state.step != 0:
            return ActionRejected(code="world-terminated", message="the example world is complete")
        if action != "finish":
            return ActionRejected(code="invalid-action", message="finish is the only action at step zero")
        return Transition(state=_MockState(step=1), output="finished", termination_reason="complete")

    def scenario(_seed: int) -> WorldConformanceScenario:
        return WorldConformanceScenario(
            initial_state=lambda _seed: _MockState(step=0),
            observe=lambda state: _MockObservation(step=state.step),
            transition=transition,
            actions=("finish",),
            invalid_action="unknown",
            assert_observation_safe=lambda observation: isinstance(observation, _MockObservation),
            assert_state_valid=lambda state: isinstance(state, _MockState),
            evaluate=lambda state: {"complete": state.step == 1},
            state_codec=lambda state: json.dumps({"step": state.step}).encode(),
            state_decoder=lambda payload: _MockState(**json.loads(payload)),
            observation_codec=lambda observation: json.dumps({"step": observation.step}).encode(),
            observation_decoder=lambda payload: _MockObservation(**json.loads(payload)),
            state_size_bound=100,
            observation_size_bound=100,
            assert_owner_conformance=lambda _seed: None,
        )

    return WorldConformanceCase(
        world_key="examples/contributor-world",
        scenario=scenario,
        requires_terminal_rejection=True,
    )


MOCK_WORLD_DESCRIPTOR = InteractiveWorldOwnerDescriptor(
    task_world_id="contributor-world",
    entry_point="tests.architecture.test_extension_contributor_workflow:_mock_world_definition",
    conformance_entry_point="tests.architecture.test_extension_contributor_workflow:_mock_world_conformance_case",
)


def _mock_lifecycle_case() -> LifecycleConformanceCase:
    return build_lifecycle_conformance_case(_mock_lifecycle_definition())


_MOCK_LIFECYCLE_IDENTITY = EntityIdentity(
    id=UUID("01a056f1-af83-7d03-8e6f-5b72d4c6a103"),
    key=EntityKey("examples/contributor-lifecycle"),
    version=1,
)
_MOCK_LIFECYCLE_METADATA = LifecycleTaskMetadata(
    identity=_MOCK_LIFECYCLE_IDENTITY,
    template_id="contributor-example-lifecycle",
    name="Contributor example lifecycle",
    discipline="examples",
)
_MOCK_LIFECYCLE_SPEC = EvidenceLifecycleSpec(
    lifecycle_id="contributor-example-lifecycle",
    checkpoints=[
        EvidenceCheckpointSpec(
            checkpoint_id="review",
            title="Example review",
            release_path="releases/review",
            instruction_path="instructions/review.md",
            submission_path="submissions/review.json",
        )
    ],
)


def _mock_lifecycle_materializer(output_dir: Path) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "template.json").write_text(
        json.dumps(_MOCK_LIFECYCLE_METADATA.model_dump(mode="json")), encoding="utf-8"
    )
    (output / "lifecycle.json").write_text(json.dumps(_MOCK_LIFECYCLE_SPEC.model_dump(mode="json")), encoding="utf-8")
    (output / "instructions").mkdir()
    (output / "instructions" / "review.md").write_text("Review the released example evidence.\n", encoding="utf-8")
    (output / "releases" / "review").mkdir(parents=True)
    (output / "releases" / "review" / "notice.md").write_text("Example evidence.\n", encoding="utf-8")
    return output


def _mock_lifecycle_definition() -> LifecycleDefinition:
    return LifecycleDefinition(
        metadata=_MOCK_LIFECYCLE_METADATA,
        lifecycle=_MOCK_LIFECYCLE_SPEC,
        materializer=_mock_lifecycle_materializer,
        verifier=lambda _package, _run: {"status": "pass"},
        executable_source_roots=(Path(__file__).resolve(),),
    )


def _write_mock_submission(context: dict[str, object]) -> dict[str, str]:
    submission = Path(str(context["workspace"])) / str(context["submission_path"])
    submission.parent.mkdir(parents=True, exist_ok=True)
    submission.write_text(json.dumps({"checkpoint_id": context["checkpoint_id"]}), encoding="utf-8")
    return {"adapter": "deterministic"}


MOCK_LIFECYCLE_DESCRIPTOR = LifecycleOwnerDescriptor(
    definition=_mock_lifecycle_definition(),
    conformance_entry_point="tests.architecture.test_extension_contributor_workflow:_mock_lifecycle_case",
)


def test_test_local_owners_run_conformance_and_render_into_generated_catalogues(tmp_path: Path) -> None:
    world_case = MOCK_WORLD_DESCRIPTOR.load_conformance_case()
    assert isinstance(world_case, WorldConformanceCase)
    result = run_world_conformance(world_case)
    assert result["world_key"] == "examples/contributor-world"

    lifecycle_case = MOCK_LIFECYCLE_DESCRIPTOR.load_conformance_case()
    assert isinstance(lifecycle_case, LifecycleConformanceCase)
    assert lifecycle_case.template_id == "contributor-example-lifecycle"
    package = lifecycle_case.definition.materializer(tmp_path / "package")
    result = run_lifecycle(
        package,
        tmp_path / "run",
        episode_environment=deterministic_episode_environment(
            lambda context: _write_mock_submission(context),
        ),
    )
    assert result["status"] == "complete"

    world_owner = (
        "contributor-world",
        "tests.architecture.test_extension_contributor_workflow",
        "MOCK_WORLD_DESCRIPTOR",
        "MOCK_WORLD_DESCRIPTOR",
    )
    lifecycle_owner = (
        "contributor-lifecycle",
        "tests.architecture.test_extension_contributor_workflow",
        "MOCK_LIFECYCLE_DESCRIPTOR",
        "MOCK_LIFECYCLE_DESCRIPTOR",
    )
    world_catalogue = render_world_catalogue((world_owner,))
    lifecycle_catalogue = render_lifecycle_catalogue((lifecycle_owner,))
    assert "MOCK_WORLD_DESCRIPTOR," in world_catalogue
    assert "MOCK_LIFECYCLE_DESCRIPTOR," in lifecycle_catalogue


def test_mock_world_owner_definition_has_readable_uuidv7_identity() -> None:
    definition = MOCK_WORLD_DESCRIPTOR.load()

    assert definition.identity.key == "examples/contributor-world"
    assert definition.identity.id.version == 7
    assert definition.identity.version == 1


def test_mock_lifecycle_owner_definition_has_readable_uuidv7_identity() -> None:
    definition = MOCK_LIFECYCLE_DESCRIPTOR.load()

    assert definition.identity.key == "examples/contributor-lifecycle"
    assert definition.identity.id.version == 7
    assert definition.identity.version == 1
