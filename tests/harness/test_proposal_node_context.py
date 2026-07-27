# ABOUTME: Tests least-privilege materialization for one governed proposal-session node.
# ABOUTME: Proves exact source, handoff, instruction, workspace, and forbidden-path boundaries.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from aec_bench.harness.proposal_node_context import (
    PersistedProposalHandoffArtifact,
    ProposalNodeContextArtifactKind,
    ProposalNodeContextError,
    ProposalNodeContextManifest,
    materialize_proposal_node_context,
)
from aec_bench.meta_harness.program_proposal_compilation import (
    ProposalRunSessionBundle,
    compile_governed_proposal,
)
from tests.meta_harness.test_program_proposal_compilation import (
    _compile_arguments,
    _governed_graph_fixture,
)


def test_semantic_context_contains_only_objective_and_allowlisted_source(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_serial_bundle(tmp_path)
    workspace = tmp_path / "invocations" / "analyse"

    manifest = materialize_proposal_node_context(
        bundle=bundle,
        node_id="analyse",
        source_task_root=source_task_root,
        invocation_workspace=workspace,
        upstream_handoff_artifacts=(),
    )

    assert isinstance(manifest, ProposalNodeContextManifest)
    graph = bundle.compilation.proposal_graph
    analyse = next(node for node in graph.semantic_subtasks if node.node_id == "analyse")
    assert (workspace / "instruction.md").read_text(encoding="utf-8") == analyse.objective
    assert graph.finalizer.objective not in (workspace / "instruction.md").read_text(encoding="utf-8")
    assert graph.problem_view_sha256 == bundle.compilation.proposal_freeze.problem_view.content_sha256
    assert bundle.compilation.proposal_freeze.problem_view.public_instruction not in (
        workspace / "instruction.md"
    ).read_text(encoding="utf-8")
    assert (workspace / "sources" / "0001.bin").read_bytes() == (
        source_task_root / "source" / "rainfall.txt"
    ).read_bytes()
    assert {path.relative_to(workspace).as_posix() for path in workspace.rglob("*") if path.is_file()} == {
        "context-manifest.json",
        "instruction.md",
        "sources/0001.bin",
    }
    source_artifact = manifest.artifact(
        ProposalNodeContextArtifactKind.PUBLIC_SOURCE,
        "rainfall-input",
    )
    assert source_artifact.workspace_relative_path == "sources/0001.bin"
    assert (
        source_artifact.artifact_sha256
        == hashlib.sha256((source_task_root / "source" / "rainfall.txt").read_bytes()).hexdigest()
    )
    persisted_manifest = json.loads((workspace / "context-manifest.json").read_text(encoding="utf-8"))
    assert persisted_manifest == manifest.model_dump(mode="json")


def test_context_materialization_is_content_stable_across_fresh_workspaces(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_serial_bundle(tmp_path)

    first = materialize_proposal_node_context(
        bundle=bundle,
        node_id="analyse",
        source_task_root=source_task_root,
        invocation_workspace=tmp_path / "first",
        upstream_handoff_artifacts=(),
    )
    second = materialize_proposal_node_context(
        bundle=bundle,
        node_id="analyse",
        source_task_root=source_task_root,
        invocation_workspace=tmp_path / "second",
        upstream_handoff_artifacts=(),
    )

    assert first == second
    assert first.content_sha256 == second.content_sha256
    assert (tmp_path / "first" / "context-manifest.json").read_bytes() == (
        tmp_path / "second" / "context-manifest.json"
    ).read_bytes()


def test_downstream_context_requires_exact_persisted_handoff_set(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_serial_bundle(tmp_path)
    handoff = _persisted_handoff(
        tmp_path / "persisted" / "facts.json",
        handoff_id="handoff.facts",
        content=b'{"facts":[{"depth_mm":22}]}\n',
    )

    manifest = materialize_proposal_node_context(
        bundle=bundle,
        node_id="assess",
        source_task_root=source_task_root,
        invocation_workspace=tmp_path / "assess",
        upstream_handoff_artifacts=(handoff,),
    )

    assert not (tmp_path / "assess" / "sources").exists()
    assert (tmp_path / "assess" / "upstream" / "0001.bin").read_bytes() == (handoff.artifact_path.read_bytes())
    upstream = manifest.artifact(
        ProposalNodeContextArtifactKind.UPSTREAM_HANDOFF,
        "handoff.facts",
    )
    assert upstream.artifact_sha256 == handoff.artifact_sha256
    assert upstream.byte_size == handoff.byte_size

    with pytest.raises(ProposalNodeContextError, match="missing.*handoff.facts"):
        materialize_proposal_node_context(
            bundle=bundle,
            node_id="assess",
            source_task_root=source_task_root,
            invocation_workspace=tmp_path / "missing",
            upstream_handoff_artifacts=(),
        )

    extra = _persisted_handoff(
        tmp_path / "persisted" / "extra.json",
        handoff_id="handoff.extra",
        content=b'{"extra":true}\n',
    )
    with pytest.raises(ProposalNodeContextError, match="extra.*handoff.extra"):
        materialize_proposal_node_context(
            bundle=bundle,
            node_id="assess",
            source_task_root=source_task_root,
            invocation_workspace=tmp_path / "extra",
            upstream_handoff_artifacts=(handoff, extra),
        )


def test_finalizer_receives_public_instruction_and_exact_upstream_only(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_serial_bundle(tmp_path)
    handoff = _persisted_handoff(
        tmp_path / "persisted" / "findings.json",
        handoff_id="handoff.findings",
        content=b'{"findings":[{"status":"review"}]}\n',
    )
    workspace = tmp_path / "finalize"

    manifest = materialize_proposal_node_context(
        bundle=bundle,
        node_id="finalize",
        source_task_root=source_task_root,
        invocation_workspace=workspace,
        upstream_handoff_artifacts=(handoff,),
    )

    problem_view = bundle.compilation.proposal_freeze.problem_view
    assert (workspace / "instruction.md").read_text(encoding="utf-8") == problem_view.public_instruction
    assert not (workspace / "sources").exists()
    assert manifest.node_id == bundle.compilation.proposal_graph.finalizer.node_id
    assert tuple(
        artifact.logical_id
        for artifact in manifest.artifacts
        if artifact.kind is ProposalNodeContextArtifactKind.UPSTREAM_HANDOFF
    ) == ("handoff.findings",)


@pytest.mark.parametrize("preexisting_content", (False, True))
def test_workspace_must_be_new_and_never_preexisting(
    tmp_path: Path,
    preexisting_content: bool,
) -> None:
    bundle, source_task_root = _compiled_serial_bundle(tmp_path)
    workspace = tmp_path / "existing"
    workspace.mkdir()
    if preexisting_content:
        (workspace / "stale.txt").write_text("stale", encoding="utf-8")

    with pytest.raises(ProposalNodeContextError, match="fresh"):
        materialize_proposal_node_context(
            bundle=bundle,
            node_id="analyse",
            source_task_root=source_task_root,
            invocation_workspace=workspace,
            upstream_handoff_artifacts=(),
        )

    assert workspace.exists()
    assert (workspace / "stale.txt").exists() is preexisting_content


def test_source_bytes_must_match_exact_task_snapshot_and_source_manifest(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_serial_bundle(tmp_path)
    source_path = source_task_root / "source" / "rainfall.txt"
    source_path.write_text("tampered rainfall\n", encoding="utf-8")
    workspace = tmp_path / "tampered"

    with pytest.raises(ProposalNodeContextError, match="source task package"):
        materialize_proposal_node_context(
            bundle=bundle,
            node_id="analyse",
            source_task_root=source_task_root,
            invocation_workspace=workspace,
            upstream_handoff_artifacts=(),
        )

    assert not workspace.exists()


def test_invocation_workspace_cannot_mutate_the_frozen_source_task(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_serial_bundle(tmp_path)
    workspace = source_task_root / "invocation-context"

    with pytest.raises(ProposalNodeContextError, match="disjoint"):
        materialize_proposal_node_context(
            bundle=bundle,
            node_id="analyse",
            source_task_root=source_task_root,
            invocation_workspace=workspace,
            upstream_handoff_artifacts=(),
        )

    assert not workspace.exists()


def test_source_symlinks_and_forbidden_task_paths_fail_closed(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_serial_bundle(tmp_path)
    source_path = source_task_root / "source" / "rainfall.txt"
    external = tmp_path / "external.txt"
    external.write_text("external", encoding="utf-8")
    source_path.unlink()
    source_path.symlink_to(external)

    with pytest.raises(ProposalNodeContextError, match="symbolic link"):
        materialize_proposal_node_context(
            bundle=bundle,
            node_id="analyse",
            source_task_root=source_task_root,
            invocation_workspace=tmp_path / "symlink",
            upstream_handoff_artifacts=(),
        )

    for forbidden_path in (
        "../secret.txt",
        "task.toml",
        "world.json",
        "tests/test.sh",
        "verifier/check.py",
        "gold/answer.json",
    ):
        poisoned = _bundle_with_source_path(bundle, forbidden_path)
        with pytest.raises(ProposalNodeContextError, match="forbidden"):
            materialize_proposal_node_context(
                bundle=poisoned,
                node_id="analyse",
                source_task_root=source_task_root,
                invocation_workspace=tmp_path / hashlib.sha256(forbidden_path.encode("utf-8")).hexdigest()[:8],
                upstream_handoff_artifacts=(),
            )


def test_upstream_artifact_hash_and_file_type_are_verified_before_publication(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _compiled_serial_bundle(tmp_path)
    handoff = _persisted_handoff(
        tmp_path / "persisted" / "facts.json",
        handoff_id="handoff.facts",
        content=b'{"facts":[]}\n',
    )
    wrong_hash = handoff.model_copy(update={"artifact_sha256": hashlib.sha256(b"wrong").hexdigest()})
    with pytest.raises(ProposalNodeContextError, match="handoff.*SHA"):
        materialize_proposal_node_context(
            bundle=bundle,
            node_id="assess",
            source_task_root=source_task_root,
            invocation_workspace=tmp_path / "wrong-hash",
            upstream_handoff_artifacts=(wrong_hash,),
        )

    directory_artifact = handoff.model_copy(update={"artifact_path": tmp_path / "persisted"})
    with pytest.raises(ProposalNodeContextError, match="regular file"):
        materialize_proposal_node_context(
            bundle=bundle,
            node_id="assess",
            source_task_root=source_task_root,
            invocation_workspace=tmp_path / "directory",
            upstream_handoff_artifacts=(directory_artifact,),
        )


def _compiled_serial_bundle(
    tmp_path: Path,
) -> tuple[ProposalRunSessionBundle, Path]:
    fixture, governed, _ = _governed_graph_fixture(tmp_path, shape="serial")
    result = compile_governed_proposal(
        **_compile_arguments(fixture, governed),
    )
    assert isinstance(result, ProposalRunSessionBundle)
    source_task_root = fixture.ledger.root.parent / "tasks" / result.compilation.proposal_freeze.problem_view.task_id
    return result, source_task_root


def _persisted_handoff(
    path: Path,
    *,
    handoff_id: str,
    content: bytes,
) -> PersistedProposalHandoffArtifact:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return PersistedProposalHandoffArtifact(
        handoff_id=handoff_id,
        artifact_path=path,
        artifact_sha256=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
    )


def _bundle_with_source_path(
    bundle: ProposalRunSessionBundle,
    task_relative_path: str,
) -> ProposalRunSessionBundle:
    compilation = bundle.compilation
    source_manifest = compilation.source_scope_manifest
    source = source_manifest.sources[0].model_copy(update={"task_relative_path": task_relative_path})
    poisoned_manifest = source_manifest.model_copy(update={"sources": (source,)})
    poisoned_compilation = compilation.model_copy(update={"source_scope_manifest": poisoned_manifest})
    poisoned_plan = bundle.session_plan.model_copy(update={"compilation": poisoned_compilation})
    return bundle.model_copy(
        update={
            "compilation": poisoned_compilation,
            "session_plan": poisoned_plan,
        }
    )
