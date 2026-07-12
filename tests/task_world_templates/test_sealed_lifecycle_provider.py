# ABOUTME: Tests the explicit external provider boundary for sealed holdout lifecycles.
# ABOUTME: Proves real task execution while public registries, exports, and errors remain non-disclosing.

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.meta_harness.evidence_lifecycle import (
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
)
from aec_bench.meta_harness.evidence_lifecycle_experiment import record_lifecycle_experiment
from aec_bench.meta_harness.evidence_lifecycle_local import (
    EvidenceLifecycleControlTool,
    EvidenceLifecycleWorkspaceTool,
)
from aec_bench.meta_harness.evidence_lifecycle_trial_record import finalize_lifecycle_trial_record
from aec_bench.prime_lab.lifecycle_exporter import (
    PrimeLifecycleExportConfig,
    export_prime_lifecycle_environment,
)
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.lifecycles import (
    SEALED_LIFECYCLE_RECEIPT_FILENAME,
    SealedLifecycleProvider,
    SealedLifecycleProviderError,
    bind_sealed_lifecycle,
    lifecycle_operation_resolver,
    lifecycle_package_variant,
    materialize_lifecycle_template,
    materialize_sealed_lifecycle,
    registered_lifecycle_template_ids,
    sealed_lifecycle_mount_active,
    sealed_lifecycle_provider_protocol_identity,
    verify_lifecycle_template,
)
from tests.support.sealed_lifecycle_provider import (
    FIXTURE_CHECKPOINT_ID,
    FIXTURE_OPERATION_ID,
    FIXTURE_TEMPLATE_ID,
    FakeSealedLifecycleProvider,
)

runner = CliRunner()


class _ExplodingProviderContract:
    @property
    def schema_version(self) -> str:
        raise RuntimeError("PRIVATE_PROVIDER_PROPERTY_SENTINEL")


def test_explicit_sealed_mount_runs_real_task_without_mutating_public_registries(tmp_path: Path) -> None:
    assert sealed_lifecycle_mount_active() is False
    public_before = _public_cli_data()
    public_ids_before = registered_lifecycle_template_ids()
    provider = FakeSealedLifecycleProvider()
    package = tmp_path / "private" / "package"
    run_dir = tmp_path / "private" / "run"
    mount = materialize_sealed_lifecycle(provider, package)
    assert sealed_lifecycle_mount_active() is False

    unmounted_run = tmp_path / "unmounted-run"
    with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_not_mounted$"):
        prepare_evidence_checkpoint(package, unmounted_run)
    assert not unmounted_run.exists()

    with mount.activate():
        assert sealed_lifecycle_mount_active() is True
        initial = prepare_evidence_checkpoint(package, run_dir)
        open_checkpoint_attempt(
            package,
            run_dir,
            session_id="sealed-fixture.session-001",
            execution_mode="persistent_context",
        )
        workspace = EvidenceLifecycleWorkspaceTool(package_dir=package, run_dir=run_dir)
        control = EvidenceLifecycleControlTool(
            package_dir=package,
            run_dir=run_dir,
            session_id="sealed-fixture.session-001",
        )
        source = json.loads(workspace.read_workspace_file("hydraulics/current-source.json"))
        visible_source = json.loads(source["content"])["visible_source_state_sha256"]
        operation = json.loads(
            control.execute_operation(
                FIXTURE_CHECKPOINT_ID,
                FIXTURE_OPERATION_ID,
                visible_source,
                "Derive the declared observation.",
            )
        )
        artifact = json.loads(workspace.read_workspace_file(operation["artifacts"][0]["path"]))
        result = json.loads(artifact["content"])
        written = json.loads(
            workspace.write_checkpoint_submission(
                FIXTURE_CHECKPOINT_ID,
                json.dumps(
                    {
                        "checkpoint_id": FIXTURE_CHECKPOINT_ID,
                        "selected_action_id": operation["action_id"],
                        "observed_value": result["observed_value"],
                    }
                ),
            )
        )
        completed = json.loads(control.submit_checkpoint(FIXTURE_CHECKPOINT_ID))
        verification = verify_lifecycle_template(package, run_dir)

        assert initial["checkpoint_id"] == FIXTURE_CHECKPOINT_ID
        assert operation["status"] == "completed"
        assert written["status"] == "written"
        assert completed["status"] == "complete"
        assert verification["passed"] is True
        assert verification["reward"] == 1.0

        provider.failure_stage = "verify"
        with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_verifier_failed$") as verify_error:
            verify_lifecycle_template(package, run_dir)
        _assert_sanitized_error(verify_error.value, provider)
        provider.failure_stage = "wrong_identity"
        with pytest.raises(
            SealedLifecycleProviderError,
            match="^sealed_provider_verifier_result_invalid$",
        ) as identity_error:
            verify_lifecycle_template(package, run_dir)
        _assert_sanitized_error(identity_error.value, provider)

        provider.failure_stage = None

        copied_package = tmp_path / "private" / "copied-package"
        shutil.copytree(package, copied_package)
        with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_not_mounted$"):
            prepare_evidence_checkpoint(copied_package, tmp_path / "copied-run")
        assert not (tmp_path / "copied-run").exists()

    assert sealed_lifecycle_mount_active() is False
    calls_before_listing = provider.calls.copy()
    public_after = _public_cli_data()
    assert provider.calls == calls_before_listing
    assert public_after == public_before
    assert registered_lifecycle_template_ids() == public_ids_before
    assert FIXTURE_TEMPLATE_ID not in public_ids_before
    assert lifecycle_package_variant(package) is None
    with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_not_mounted$"):
        verify_lifecycle_template(package, run_dir)
    rebound = bind_sealed_lifecycle(provider, package)
    with rebound.activate():
        assert verify_lifecycle_template(package, run_dir)["passed"] is True


def test_sealed_receipt_is_generic_exact_and_contains_no_provider_content(tmp_path: Path) -> None:
    provider = FakeSealedLifecycleProvider()
    package = tmp_path / "private-package"
    materialize_sealed_lifecycle(provider, package)

    receipt = json.loads((package / SEALED_LIFECYCLE_RECEIPT_FILENAME).read_text(encoding="utf-8"))
    protocol = sealed_lifecycle_provider_protocol_identity()
    assert receipt == {
        "provider_protocol_sha256": protocol["sha256"],
        "public_export": "forbidden",
        "public_registry": "forbidden",
        "schema_version": "1",
        "visibility": "holdout",
    }
    serialized = json.dumps(receipt, sort_keys=True)
    assert all(secret not in serialized for secret in provider.sentinels.values())


def test_public_prime_and_experiment_records_reject_sealed_packages_atomically(tmp_path: Path) -> None:
    private_provider = FakeSealedLifecycleProvider()
    private_package = tmp_path / "private-package"
    private_mount = materialize_sealed_lifecycle(private_provider, private_package)
    receipt_bytes = (private_package / SEALED_LIFECYCLE_RECEIPT_FILENAME).read_bytes()

    public_package = materialize_lifecycle_template(
        get_template("hydraulic-interaction-lifecycle-review"),
        tmp_path / "public-collision-package",
        variant_id="administrative_no_op",
    )
    secret = private_provider.sentinels["prompt"]
    (public_package / "instructions" / "baseline_analysis.md").write_text(secret, encoding="utf-8")
    (public_package / SEALED_LIFECYCLE_RECEIPT_FILENAME).write_bytes(receipt_bytes)
    export_root = tmp_path / "prime-output"

    with pytest.raises(ValueError, match="^sealed_holdout_prime_export_forbidden$") as prime_error:
        export_prime_lifecycle_environment(
            PrimeLifecycleExportConfig(
                name="must-not-exist",
                package_dirs=(public_package,),
                output_dir=export_root,
            )
        )
    assert secret not in str(prime_error.value)
    assert str(public_package) not in str(prime_error.value)
    assert not export_root.exists()
    assert lifecycle_package_variant(public_package) is None
    with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_not_mounted$"):
        verify_lifecycle_template(public_package, tmp_path / "unused-run")

    with private_mount.activate():
        with pytest.raises(ValueError, match="^sealed_holdout_public_record_forbidden$") as record_error:
            record_lifecycle_experiment(
                package_dir=private_package,
                run_dir=tmp_path / "unused-private-run",
                agent={},
                verifier=verify_lifecycle_template,
                verification={},
                tool_schema=[],
            )
    assert all(secret_value not in str(record_error.value) for secret_value in private_provider.sentinels.values())
    assert not (tmp_path / "unused-private-run" / "experiment-manifest.json").exists()

    blocked_ledger = tmp_path / "blocked-ledger"
    blocked_run = tmp_path / "blocked-run"
    manifest = cast(
        Any,
        SimpleNamespace(ledger_root=str(blocked_ledger), experiment_id="blocked-private-experiment"),
    )
    trial = cast(
        Any,
        SimpleNamespace(ledger_path=str(blocked_ledger / "record.json"), trial_id="blocked-private-trial"),
    )
    with pytest.raises(ValueError, match="^sealed_holdout_public_record_forbidden$"):
        finalize_lifecycle_trial_record(
            manifest=manifest,
            trial=trial,
            package_dir=private_package,
            run_dir=blocked_run,
        )
    assert not blocked_ledger.exists()
    assert not blocked_run.exists()


def test_provider_failures_are_sanitized_before_reaching_host_or_model_surfaces(tmp_path: Path) -> None:
    with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_contract_invalid$") as contract:
        materialize_sealed_lifecycle(
            cast(SealedLifecycleProvider, _ExplodingProviderContract()),
            tmp_path / "invalid-contract-package",
        )
    assert "PRIVATE_PROVIDER_PROPERTY_SENTINEL" not in str(contract.value)
    assert contract.value.__context__ is None
    assert contract.value.__cause__ is None

    partial_provider = FakeSealedLifecycleProvider(failure_stage="partial_materialize")
    partial_output = tmp_path / "partial-package"
    with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_materialization_failed$") as partial:
        materialize_sealed_lifecycle(partial_provider, partial_output)
    assert not partial_output.exists()
    _assert_sanitized_error(partial.value, partial_provider)

    mutating_provider = FakeSealedLifecycleProvider(failure_stage="mutate_validate")
    mutating_output = tmp_path / "mutating-package"
    with pytest.raises(
        SealedLifecycleProviderError,
        match="^sealed_provider_validation_mutated_package$",
    ):
        materialize_sealed_lifecycle(mutating_provider, mutating_output)
    assert not mutating_output.exists()

    provider = FakeSealedLifecycleProvider(failure_stage="current_source")
    package = tmp_path / "private-package"
    mount = materialize_sealed_lifecycle(provider, package)

    with mount.activate():
        with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_resolver_failed$") as exc_info:
            prepare_evidence_checkpoint(package, tmp_path / "private-run")

    message = str(exc_info.value)
    assert all(secret not in message for secret in provider.sentinels.values())
    _assert_sanitized_error(exc_info.value, provider)

    bad_hash_provider = FakeSealedLifecycleProvider(failure_stage="bad_source_hash")
    bad_hash_package = tmp_path / "bad-source-hash-package"
    bad_hash_mount = materialize_sealed_lifecycle(bad_hash_provider, bad_hash_package)
    with bad_hash_mount.activate():
        with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_resolver_failed$") as bad_hash:
            prepare_evidence_checkpoint(bad_hash_package, tmp_path / "bad-source-hash-run")
    _assert_sanitized_error(bad_hash.value, bad_hash_provider)

    mutating_resolver_provider = FakeSealedLifecycleProvider(failure_stage="mutate_current_source")
    mutating_resolver_package = tmp_path / "mutating-resolver-package"
    mutating_resolver_mount = materialize_sealed_lifecycle(
        mutating_resolver_provider,
        mutating_resolver_package,
    )
    with mutating_resolver_mount.activate():
        with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_package_changed$") as mutation:
            prepare_evidence_checkpoint(mutating_resolver_package, tmp_path / "mutating-resolver-run")
    _assert_sanitized_error(mutation.value, mutating_resolver_provider)

    mutating_verifier_provider = FakeSealedLifecycleProvider()
    mutating_verifier_package = tmp_path / "mutating-verifier-package"
    mutating_verifier_mount = materialize_sealed_lifecycle(
        mutating_verifier_provider,
        mutating_verifier_package,
    )
    mutating_verifier_provider.failure_stage = "mutate_verify"
    with mutating_verifier_mount.activate():
        with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_package_changed$") as mutation:
            verify_lifecycle_template(mutating_verifier_package, tmp_path / "unused-verifier-run")
    _assert_sanitized_error(mutation.value, mutating_verifier_provider)


@pytest.mark.parametrize("failure_stage", ["bad_plan_hash", "bad_visible_path"])
def test_malformed_private_plan_is_rejected_before_model_facing_publication(
    tmp_path: Path,
    failure_stage: str,
) -> None:
    provider = FakeSealedLifecycleProvider()
    package = tmp_path / "private-package"
    run_dir = tmp_path / "run"
    mount = materialize_sealed_lifecycle(provider, package)

    with mount.activate():
        prepare_evidence_checkpoint(package, run_dir)
        open_checkpoint_attempt(
            package,
            run_dir,
            session_id="sealed-plan.session-001",
            execution_mode="persistent_context",
        )
        workspace = EvidenceLifecycleWorkspaceTool(package_dir=package, run_dir=run_dir)
        control = EvidenceLifecycleControlTool(
            package_dir=package,
            run_dir=run_dir,
            session_id="sealed-plan.session-001",
        )
        source = json.loads(workspace.read_workspace_file("hydraulics/current-source.json"))
        visible_source = json.loads(source["content"])["visible_source_state_sha256"]
        provider.failure_stage = failure_stage
        with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_resolver_failed$") as plan_error:
            control.execute_operation(
                FIXTURE_CHECKPOINT_ID,
                FIXTURE_OPERATION_ID,
                visible_source,
                "Exercise malformed private plan rejection.",
            )

    _assert_sanitized_error(plan_error.value, provider)


def test_cached_resolver_cannot_escape_mount_or_package_hash_binding(tmp_path: Path) -> None:
    provider = FakeSealedLifecycleProvider()
    package = tmp_path / "private-package"
    mount = materialize_sealed_lifecycle(provider, package)

    with mount.activate():
        resolver = lifecycle_operation_resolver(package, tmp_path / "run")
        assert resolver is not None
        (package / "PRIVATE_EMPTY_DIRECTORY_SEMANTIC_FLAG").mkdir()
        with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_package_changed$"):
            resolver.current_source(())

    with pytest.raises(SealedLifecycleProviderError, match="^sealed_provider_not_mounted$"):
        resolver.current_source(())


def test_private_prerequisite_failure_remains_a_typed_zero_cost_rejection(tmp_path: Path) -> None:
    provider = FakeSealedLifecycleProvider(failure_stage="plan_prerequisite")
    package = tmp_path / "private-package"
    run_dir = tmp_path / "run"
    mount = materialize_sealed_lifecycle(provider, package)

    with mount.activate():
        prepare_evidence_checkpoint(package, run_dir)
        open_checkpoint_attempt(
            package,
            run_dir,
            session_id="sealed-prerequisite.session-001",
            execution_mode="persistent_context",
        )
        workspace = EvidenceLifecycleWorkspaceTool(package_dir=package, run_dir=run_dir)
        control = EvidenceLifecycleControlTool(
            package_dir=package,
            run_dir=run_dir,
            session_id="sealed-prerequisite.session-001",
        )
        source = json.loads(workspace.read_workspace_file("hydraulics/current-source.json"))
        visible_source = json.loads(source["content"])["visible_source_state_sha256"]
        result = json.loads(
            control.execute_operation(
                FIXTURE_CHECKPOINT_ID,
                FIXTURE_OPERATION_ID,
                visible_source,
                "Attempt an operation whose private prerequisite is unavailable.",
            )
        )

    assert result["status"] == "rejected"
    assert result["rejection"] == "prerequisites_incomplete"
    assert result["budget_consumed"] == 0
    assert all(secret not in json.dumps(result) for secret in provider.sentinels.values())


def _public_cli_data() -> dict[str, object]:
    result = runner.invoke(app, ["--json", "task", "composite-template", "list"])
    assert result.exit_code == 0, result.output
    return dict(json.loads(result.output)["data"])


def _assert_sanitized_error(
    error: BaseException,
    provider: FakeSealedLifecycleProvider,
) -> None:
    assert error.__context__ is None
    assert error.__cause__ is None
    serialized = repr(error)
    assert all(secret not in serialized for secret in provider.sentinels.values())
