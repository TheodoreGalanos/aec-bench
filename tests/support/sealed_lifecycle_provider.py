# ABOUTME: Provides a domain-neutral external lifecycle provider used only by sealed-boundary tests.
# ABOUTME: Keeps fake private prompts, sources, mappings, gold values, and verifier rules out of public registries.

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from aec_bench.meta_harness.evidence_lifecycle import (
    load_validated_lifecycle_submissions,
    read_evidence_lifecycle_state,
)
from aec_bench.meta_harness.evidence_lifecycle_state import (
    LifecycleOperationActionRecord,
    LifecycleOperationDisposition,
)
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    LifecycleOperationPlan,
    LifecycleOperationPrerequisiteError,
    LifecycleOperationSourceContext,
    lifecycle_operation_source_identity,
)
from aec_bench.task_world_templates.contracts import (
    CompositeTaskWorldTemplate,
    EvidenceLifecycleSpec,
    LifecycleOperationSpec,
)

FIXTURE_TEMPLATE_ID = "fixture-sealed-lifecycle"
FIXTURE_LIFECYCLE_ID = "fixture.sealed.lifecycle"
FIXTURE_CHECKPOINT_ID = "fixture_review"
FIXTURE_OPERATION_ID = "derive.fixture-observation"
FIXTURE_OPERATION_KIND = "derive_fixture_observation"


class FakeSealedLifecycleProvider:
    """Represent one fake selected target without offering enumeration or discovery."""

    schema_version = "1"

    def __init__(self, *, failure_stage: str | None = None) -> None:
        self.failure_stage = failure_stage
        self.audit_revision = "fixture-audit-v1"
        self.calls: Counter[str] = Counter()
        self.sentinels = {
            "target_id": "PRIVATE_TARGET_SENTINEL_7QX",
            "prompt": "PRIVATE_PROMPT_SENTINEL_8RX",
            "source": "PRIVATE_SOURCE_SENTINEL_9SX",
            "action_mapping": "PRIVATE_ACTION_MAPPING_SENTINEL_0TX",
            "gold": "PRIVATE_GOLD_SENTINEL_1UX",
            "verifier_rule": "PRIVATE_VERIFIER_RULE_SENTINEL_2VX",
            "annotation": "PRIVATE_ANNOTATION_SENTINEL_3WX",
            "path": "PRIVATE_PATH_SENTINEL_4YX",
        }
        self.gold_value = 14

    def audit_contract_identity(self, package_dir: Path) -> dict[str, str]:
        """Return opaque hashes for the provider, resolver, and verifier semantics."""
        self.calls["audit_contract_identity"] += 1
        if self.failure_stage == "audit_contract_identity":
            raise RuntimeError(self.sentinels["verifier_rule"])
        package = Path(package_dir)
        if not package.is_dir():
            raise ValueError(self.sentinels["path"])
        return {
            "schema_version": "1",
            "provider_contract_sha256": _canonical_sha256(
                {"contract": "fixture-provider", "revision": self.audit_revision}
            ),
            "resolver_contract_sha256": _canonical_sha256(
                {"contract": "fixture-resolver", "revision": self.audit_revision}
            ),
            "verifier_contract_sha256": _canonical_sha256(
                {"contract": "fixture-verifier", "revision": self.audit_revision}
            ),
        }

    def materialize(self, output_dir: Path) -> Path:
        self.calls["materialize"] += 1
        if self.failure_stage == "materialize":
            raise RuntimeError(self.sentinels["prompt"])
        output = Path(output_dir)
        if self.failure_stage == "partial_materialize":
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(self.sentinels["prompt"], encoding="utf-8")
            raise RuntimeError(self.sentinels["path"])
        template = _template()
        output.mkdir(parents=True)
        _write_json(output / "template.json", template.model_dump(mode="json"))
        _write_json(output / "world.json", template.compile_task_world_payload())
        assert template.evidence_lifecycle is not None
        _write_json(output / "lifecycle.json", template.evidence_lifecycle.model_dump(mode="json"))
        (output / "instructions").mkdir()
        (output / "instructions" / f"{FIXTURE_CHECKPOINT_ID}.md").write_text(
            f"# Fixture review\n\n{self.sentinels['prompt']}\n",
            encoding="utf-8",
        )
        (output / "releases" / FIXTURE_CHECKPOINT_ID).mkdir(parents=True)
        (output / "releases" / FIXTURE_CHECKPOINT_ID / "notice.md").write_text(
            "Use the declared operation to derive the visible fixture observation.\n",
            encoding="utf-8",
        )
        _write_json(
            output / "hidden" / "source.json",
            {
                "schema_version": "1",
                "measurement": 7,
                "source_note": self.sentinels["source"],
            },
        )
        _write_json(
            output / "hidden" / "operation-resolution.json",
            {
                "schema_version": "1",
                "operation_id": FIXTURE_OPERATION_ID,
                "mapping_note": self.sentinels["action_mapping"],
            },
        )
        return output

    def validate_package(self, package_dir: Path) -> None:
        self.calls["validate_package"] += 1
        if self.failure_stage == "validate_package":
            raise RuntimeError(self.sentinels["source"])
        package = Path(package_dir)
        template = CompositeTaskWorldTemplate.model_validate(_read_json(package / "template.json"))
        lifecycle = EvidenceLifecycleSpec.model_validate(_read_json(package / "lifecycle.json"))
        source = _read_json(package / "hidden" / "source.json")
        resolution = _read_json(package / "hidden" / "operation-resolution.json")
        if (
            template.template_id != FIXTURE_TEMPLATE_ID
            or template.evidence_lifecycle != lifecycle
            or source.get("source_note") != self.sentinels["source"]
            or resolution.get("mapping_note") != self.sentinels["action_mapping"]
        ):
            raise ValueError(self.sentinels["verifier_rule"])
        if self.failure_stage == "mutate_validate":
            source["measurement"] = int(source["measurement"]) + 1
            _write_json(package / "hidden" / "source.json", source)

    def build_operation_resolver(self, package_dir: Path, run_dir: Path) -> FixtureOperationResolver:
        self.calls["build_operation_resolver"] += 1
        if self.failure_stage == "build_operation_resolver":
            raise RuntimeError(self.sentinels["path"])
        return FixtureOperationResolver(
            package_dir=package_dir,
            run_dir=run_dir,
            failure_stage=self.failure_stage,
            private_error=self.sentinels["action_mapping"],
        )

    def verify(self, package_dir: Path, run_dir: Path) -> dict[str, Any]:
        self.calls["verify"] += 1
        if self.failure_stage == "verify":
            raise RuntimeError(self.sentinels["verifier_rule"])
        if self.failure_stage == "mutate_verify":
            source_path = Path(package_dir) / "hidden" / "source.json"
            source = _read_json(source_path)
            source["measurement"] = int(source["measurement"]) + 1
            _write_json(source_path, source)
            return {
                "lifecycle_id": FIXTURE_LIFECYCLE_ID,
                "overall": "pass",
                "passed": True,
                "reward": 1.0,
                "gates": {
                    "fixture_contract": {
                        "passed": True,
                        "score": 1.0,
                        "failures": [],
                    }
                },
            }
        submissions = load_validated_lifecycle_submissions(package_dir, run_dir)
        state = read_evidence_lifecycle_state(package_dir, run_dir)
        actions = [action for checkpoint in state["checkpoint_runs"] for action in checkpoint["operation_actions"]]
        submission = submissions.get(FIXTURE_CHECKPOINT_ID, {})
        action_id = actions[0]["action_id"] if len(actions) == 1 else None
        artifact = (
            Path(run_dir) / "lifecycle_operations" / str(action_id) / "artifacts" / "fixture-result.json"
            if action_id is not None
            else Path(run_dir) / "missing"
        )
        result = _read_json(artifact) if artifact.is_file() else {}
        passed = bool(
            state["status"] == "complete"
            and len(actions) == 1
            and actions[0]["outcome"] == "completed"
            and submission.get("selected_action_id") == action_id
            and submission.get("observed_value") == self.gold_value
            and result.get("observed_value") == self.gold_value
        )
        lifecycle_id = "different-private-lifecycle" if self.failure_stage == "wrong_identity" else FIXTURE_LIFECYCLE_ID
        return {
            "lifecycle_id": lifecycle_id,
            "overall": "pass" if passed else "fail",
            "passed": passed,
            "reward": 1.0 if passed else 0.0,
            "gates": {
                "fixture_contract": {
                    "passed": passed,
                    "score": 1.0 if passed else 0.0,
                    "failures": [] if passed else ["fixture_contract_failed"],
                }
            },
        }


class FixtureOperationResolver:
    """Resolve one deterministic fake operation for the provider contract tests."""

    def __init__(
        self,
        *,
        package_dir: Path,
        run_dir: Path,
        failure_stage: str | None,
        private_error: str,
    ) -> None:
        self.package_dir = Path(package_dir)
        self.run_dir = Path(run_dir)
        self.failure_stage = failure_stage
        self.private_error = private_error

    def current_source(
        self,
        actions: Sequence[LifecycleOperationActionRecord],
    ) -> LifecycleOperationSourceContext:
        del actions
        if self.failure_stage == "current_source":
            raise RuntimeError(self.private_error)
        source_state = _read_json(self.package_dir / "hidden" / "source.json")
        physical, visible = lifecycle_operation_source_identity(
            source_state=source_state,
            revision_id="fixture-source",
        )
        if self.failure_stage == "mutate_current_source":
            mutated = dict(source_state)
            mutated["measurement"] = int(mutated["measurement"]) + 1
            _write_json(self.package_dir / "hidden" / "source.json", mutated)
        return LifecycleOperationSourceContext(
            revision_id="fixture-source",
            package_dir=self.package_dir,
            physical_source_state_sha256=(self.private_error if self.failure_stage == "bad_source_hash" else physical),
            visible_source_state_sha256=visible,
            source_state=source_state,
        )

    def plan(
        self,
        operation: LifecycleOperationSpec,
        actions: Sequence[LifecycleOperationActionRecord],
    ) -> LifecycleOperationPlan:
        if self.failure_stage == "plan_prerequisite":
            raise LifecycleOperationPrerequisiteError(self.private_error)
        if self.failure_stage == "plan":
            raise RuntimeError(self.private_error)
        if operation.operation_id != FIXTURE_OPERATION_ID or operation.kind != FIXTURE_OPERATION_KIND:
            raise ValueError(self.private_error)
        source = self.current_source(actions)
        payload = {
            "schema_version": "1",
            "operation_id": operation.operation_id,
            "measurement": source.source_state["measurement"],
        }
        return LifecycleOperationPlan(
            operation_id=operation.operation_id,
            operation_kind=operation.kind,
            disposition=LifecycleOperationDisposition.COMPUTED,
            source_before=source,
            source_after=source,
            input_projection_sha256=(
                self.private_error if self.failure_stage == "bad_plan_hash" else _canonical_sha256(payload)
            ),
            prerequisite_action_ids=(),
            model_visible_artifact_paths=(
                "private\\result.json" if self.failure_stage == "bad_visible_path" else "fixture-result.json",
            ),
            payload=payload,
        )

    def execute(self, plan: LifecycleOperationPlan, artifact_dir: Path) -> None:
        if self.failure_stage == "execute":
            raise RuntimeError(self.private_error)
        _write_json(
            Path(artifact_dir) / plan.model_visible_artifact_paths[0],
            {
                "schema_version": "1",
                "operation_id": plan.operation_id,
                "observed_value": int(plan.payload["measurement"]) * 2,
            },
        )


def _template() -> CompositeTaskWorldTemplate:
    template_id = FIXTURE_TEMPLATE_ID
    world_id = f"aec.task_world.composite.{template_id}"
    return CompositeTaskWorldTemplate.model_validate(
        {
            "template_id": template_id,
            "name": "Fixture sealed lifecycle",
            "summary": "Domain-neutral fake package for external provider contract tests.",
            "pattern": "sealed-fixture",
            "discipline_scope": ["fixture"],
            "source_artifacts": [],
            "stages": [
                {
                    "id": FIXTURE_CHECKPOINT_ID,
                    "title": "Fixture review",
                    "discipline": "fixture",
                }
            ],
            "handoffs": [],
            "verifier_gates": [],
            "deliverables": [],
            "data_gaps": [],
            "evidence_lifecycle": {
                "lifecycle_id": FIXTURE_LIFECYCLE_ID,
                "world_id": world_id,
                "checkpoints": [
                    {
                        "checkpoint_id": FIXTURE_CHECKPOINT_ID,
                        "title": "Fixture review",
                        "release_path": f"releases/{FIXTURE_CHECKPOINT_ID}",
                        "instruction_path": f"instructions/{FIXTURE_CHECKPOINT_ID}.md",
                        "submission_path": f"submissions/{FIXTURE_CHECKPOINT_ID}.json",
                        "required_submission_fields": [
                            "checkpoint_id",
                            "selected_action_id",
                            "observed_value",
                        ],
                        "conditional_operations": {
                            "operation_budget": 1,
                            "operations": [
                                {
                                    "operation_id": FIXTURE_OPERATION_ID,
                                    "kind": FIXTURE_OPERATION_KIND,
                                    "title": "Derive fixture observation",
                                    "description": "Compute one deterministic observation from the current source.",
                                }
                            ],
                        },
                    }
                ],
            },
        }
    )


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
