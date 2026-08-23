# ABOUTME: Tests the optional read-only context seam in the local lifecycle harness.
# ABOUTME: Proves model-facing learner_context access without changing lifecycle visibility or persisted state.

from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aec_bench.harness.lifecycle_local import (
    EvidenceLifecycleWorkspaceTool,
    _run_local_lifecycle_persistent_session,
    _workspace_policy,
)
from aec_bench.lifecycles.catalogue import lifecycle_operation_resolver
from aec_bench.lifecycles.compiled import compile_lifecycle
from aec_bench.lifecycles.runtime.episode import LifecycleVisibilityPolicy
from aec_bench.lifecycles.runtime.lifecycle import read_lifecycle

_TEMPLATE_ID = "drainage-model-evidence-lifecycle-review"
_VARIANT_ID = "semantic_no_op_release"
_CONTEXT_POLICY = (
    "A read-only learner_context/ directory may contain lessons retained from prior complete tasks. "
    "It is not task evidence, does not override current released sources, and cannot be modified during this "
    "lifecycle."
)


def _workspace(tmp_path: Path, *, context: bool = True) -> tuple[EvidenceLifecycleWorkspaceTool, Path]:
    package = tmp_path / "package"
    run = tmp_path / "run"
    workspace = run / "workspace"
    package.mkdir(parents=True)
    workspace.mkdir(parents=True)
    (workspace / "instruction.md").write_text("Current task", encoding="utf-8")
    context_root = tmp_path / "retained-lessons"
    (context_root / "review").mkdir(parents=True)
    (context_root / "review" / "continuity.md").write_text(
        "Preserve findings until evidence changes.\n",
        encoding="utf-8",
    )
    return (
        EvidenceLifecycleWorkspaceTool(
            package_dir=package,
            run_dir=run,
            read_only_context_root=context_root if context else None,
        ),
        context_root,
    )


def test_workspace_context_is_additive_nested_and_read_only(tmp_path: Path) -> None:
    with_context, _ = _workspace(tmp_path / "with")
    without_context, _ = _workspace(tmp_path / "without", context=False)

    baseline = json.loads(without_context.list_workspace("."))
    exposed = json.loads(with_context.list_workspace("."))
    nested = json.loads(with_context.list_workspace("learner_context/review"))
    lesson = json.loads(with_context.read_workspace_file("learner_context/review/continuity.md"))

    assert baseline == {"status": "ok", "path": ".", "entries": ["instruction.md"]}
    assert exposed == {
        "status": "ok",
        "path": ".",
        "entries": ["instruction.md", "learner_context"],
    }
    assert nested == {"status": "ok", "path": "learner_context/review", "entries": ["continuity.md"]}
    assert lesson == {
        "status": "ok",
        "path": "learner_context/review/continuity.md",
        "content": "Preserve findings until evidence changes.\n",
    }
    assert set(inspect.signature(with_context.write_checkpoint_submission).parameters) == {"checkpoint_id", "content"}


@pytest.mark.parametrize(
    "visibility_policy",
    (
        LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        LifecycleVisibilityPolicy.RAW_EVIDENCE_ONLY,
        LifecycleVisibilityPolicy.CURRENT_RELEASE_ONLY,
    ),
)
def test_workspace_context_is_independent_of_lifecycle_visibility(
    tmp_path: Path,
    visibility_policy: LifecycleVisibilityPolicy,
) -> None:
    tool, _ = _workspace(tmp_path)
    tool = EvidenceLifecycleWorkspaceTool(
        package_dir=tool.package_dir,
        run_dir=tool.run_dir,
        visibility_policy=visibility_policy,
        read_only_context_root=tool.read_only_context_root,
    )

    assert json.loads(tool.read_workspace_file("learner_context/review/continuity.md"))["status"] == "ok"
    assert json.loads(tool.read_workspace_file("submissions/unknown.json"))["status"] == "rejected"


@pytest.mark.parametrize(
    "path",
    (
        "learner_context/../instruction.md",
        "learner_context\\review\\continuity.md",
        "/learner_context/review/continuity.md",
        "learner_context/.hidden",
        "learner_context/missing.md",
    ),
)
def test_workspace_context_rejects_unsafe_or_missing_paths_without_host_disclosure(
    tmp_path: Path,
    path: str,
) -> None:
    tool, context_root = _workspace(tmp_path)

    response = json.loads(tool.read_workspace_file(path))

    assert response["status"] == "rejected"
    assert str(context_root) not in response["error"]


def test_workspace_context_rejects_symlinks(tmp_path: Path) -> None:
    tool, context_root = _workspace(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("hidden", encoding="utf-8")
    (context_root / "bridge.txt").symlink_to(outside)

    assert json.loads(tool.list_workspace("learner_context"))["status"] == "rejected"
    response = json.loads(tool.read_workspace_file("learner_context/bridge.txt"))
    assert response["status"] == "rejected"
    assert str(outside) not in response["error"]


def test_workspace_policy_labels_context_as_non_authoritative() -> None:
    prompt = _workspace_policy(
        {},
        persistent=False,
        visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        supports_evidence_requests=False,
        has_read_only_context=True,
    )
    baseline = _workspace_policy(
        {},
        persistent=False,
        visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        supports_evidence_requests=False,
    )

    assert _CONTEXT_POLICY in prompt
    assert "learner_context" not in baseline
    assert all(identifier not in prompt for identifier in ("arm_id", "state_id", "treatment_id", "probe"))


class _PersistentContextAdapter:
    def __init__(self, package: Path) -> None:
        self.package = package
        self.context_reads: list[str] = []
        self.system_prompts: list[str] = []

    def build(self, **kwargs):  # noqa: ANN003, ANN202
        native_tools = {tool.__name__: tool for tool in kwargs["native_tools"]}
        adapter = self

        class _Adapter:
            def execute(self, request):  # noqa: ANN001, ANN202
                adapter.system_prompts.append(request.system_prompt)
                listed = json.loads(native_tools["list_workspace"]("."))
                assert "learner_context" in listed["entries"]
                context = json.loads(native_tools["read_workspace_file"]("learner_context/guidance.md"))
                adapter.context_reads.append(context["content"])
                run_dir = Path(kwargs["workspace"]).parent
                gold = json.loads((adapter.package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))
                while True:
                    checkpoint_id = read_lifecycle(adapter.package, run_dir)["active_checkpoint_id"]
                    assert checkpoint_id is not None
                    written = json.loads(
                        native_tools["write_checkpoint_submission"](checkpoint_id, json.dumps(gold[checkpoint_id]))
                    )
                    assert written["status"] == "written"
                    submitted = json.loads(native_tools["submit_checkpoint"](checkpoint_id))
                    if submitted["status"] == "complete":
                        break
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="fixed-test-model",
                    configuration_record={"model": "fixed-test-model"},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text=None,
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=2,
                    usage_output_tokens=1,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _Adapter()


def test_persistent_lifecycle_receives_context_once_without_persisting_it(tmp_path: Path) -> None:
    compiled = compile_lifecycle(_TEMPLATE_ID, tmp_path / "package", variant_id=_VARIANT_ID)
    run_dir = tmp_path / "run"
    context = tmp_path / "context"
    context.mkdir()
    (context / "guidance.md").write_text("Use current registered evidence.\n", encoding="utf-8")
    adapter = _PersistentContextAdapter(compiled.package_dir)
    resolver = lifecycle_operation_resolver(compiled.package_dir, run_dir)

    result = _run_local_lifecycle_persistent_session(
        package_dir=compiled.package_dir,
        run_dir=run_dir,
        model="fixed-test-model",
        verifier=None,
        visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
        operation_resolver=resolver,
        adapter_builder=adapter.build,
        read_only_context_root=context,
    )

    assert result["evidence"]["lifecycle"]["status"] == "complete"
    assert adapter.context_reads == ["Use current registered evidence.\n"]
    assert len(adapter.system_prompts) == 1
    assert _CONTEXT_POLICY in adapter.system_prompts[0]
    persisted = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert "learner_context" not in json.dumps(persisted)
    assert not (run_dir / "workspace" / "learner_context").exists()
