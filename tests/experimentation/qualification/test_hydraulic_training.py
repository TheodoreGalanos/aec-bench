# ABOUTME: Proves local hydraulic training qualification uses real tools and disjoint project groups.
# ABOUTME: Checks that only verified training controls enter assistant/tool demonstration rows.

import json
from pathlib import Path

import pytest

from aec_bench.experimentation.engineering_decisions.definitions import HydraulicExperiment
from aec_bench.experimentation.qualification.hydraulic_training import qualify_hydraulic_training


def test_local_qualification_retains_only_training_demonstrations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vf = pytest.importorskip("verifiers")
    monkeypatch.syspath_prepend(str(Path(vf.__file__).parents[1]))
    definition = HydraulicExperiment(revisions=("administrative_no_op",))
    report = qualify_hydraulic_training(tmp_path / "qualification", definition)
    assert report["local_passed"]
    assert report["training_config"] == "accepted_by_installed_prime_cli"
    assert report["rollout_isolation"]
    assert report["incomplete_zero_reward"]
    assert len(report["controls"]) == 2
    assert report["training_demonstrations"] == 1
    assert report["hosted_run"] == report["weight_update"] == "not_run"
    output = tmp_path / "qualification"
    demos = [json.loads(line) for line in (output / "training_demonstrations.jsonl").read_text().splitlines()]
    assert len(demos) == 1
    messages = demos[0]["messages"]
    assert sum(message["role"] == "system" for message in messages) == 1
    calls = [call for message in messages for call in message.get("tool_calls", [])]
    assert len(calls) <= 128
    assert any(call["function"]["name"] == "read_workspace_file" for call in calls)
    assert sum(call["function"]["name"] == "submit_checkpoint" for call in calls) == 3
    assert all(tool["type"] == "function" for tool in demos[0]["tools"])
    assert all("state" not in tool["function"]["parameters"]["properties"] for tool in demos[0]["tools"])
    assert "dataset_assignment" not in json.dumps(demos)
    assert "lifecycle_verification" not in json.dumps(demos)
    # Acceptance fixtures exist locally but are not included in the transferable environment.
    manifest = json.loads(
        (output / report["environment_package"] / "aec_hydraulic_training" / "lifecycle_manifest.json").read_text()
    )
    assert len(manifest["packages"]) == 2
    assert len(list((output / "acceptance").glob("*/administrative_no_op/package/lifecycle.json"))) == 1
    with pytest.raises(ValueError, match="must be empty"):
        qualify_hydraulic_training(output, definition)
