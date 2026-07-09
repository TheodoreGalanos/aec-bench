# ABOUTME: Tests the SSC-01 review-first road low-point issue review template.
# ABOUTME: Covers variant gold states, generated source packs, and the stage-gated review verifier.

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

from aec_bench.generation.sampler import sample_instance
from aec_bench.generation.scaffolder import scaffold_task_instance
from aec_bench.templates.registry import discover_templates, load_engine_module, load_template

TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "civil"
    / "road_low_point_issue_review_package"
)

STATUS_KEYS = [f"rlr_0{i}_status" for i in range(1, 10)]

EVIDENCE_KEYS = [
    "peak_runoff_m3_s",
    "gutter_approach_flow_m3_s",
    "spread_width_m",
    "controlling_water_level_m",
    "cabinet_freeboard_m",
    "vms_message_margin_chars",
    "battery_runtime_h",
    "network_headroom_mbps",
]

# Gold status flips, readiness code, and required register counts per packet variant.
VARIANT_EXPECTATIONS: dict[str, dict] = {
    "clean": {"flips": {}, "readiness": 0.0, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_cabinet_level": {
        "flips": {"rlr_04_status": 3.0},
        "readiness": 2.0,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_hgl_revision": {
        "flips": {"rlr_03_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "chainage_datum_mismatch": {
        "flips": {"rlr_02_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "scenario_copy_forward": {
        "flips": {"rlr_05_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "open_critical_comment": {
        "flips": {"rlr_07_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "minor_open_comment_carried": {
        "flips": {},
        "readiness": 1.0,
        "findings": 0.0,
        "requests": 0.0,
        "carried": 1.0,
    },
    "freeboard_deficient": {
        "flips": {"rlr_04_status": 1.0},
        "readiness": 2.0,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}

SOURCE_FILES = [
    "sources/document-register.md",
    "sources/road-geometry.md",
    "sources/drainage-package.md",
    "sources/field-equipment.md",
    "sources/power-comms.md",
    "sources/traffic-operations.md",
    "sources/criteria-comments.md",
]


def _load() -> tuple:
    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    return config, template_dir, engine


def _instance_for_variant(variant: str, max_seeds: int = 400):
    """Sample seeds until an instance with the requested packet variant appears."""
    config, template_dir, engine = _load()
    for seed in range(max_seeds):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        if instance.all_params["packet_variant"] == variant:
            return config, template_dir, engine, instance
    pytest.fail(f"No instance with variant {variant!r} found in {max_seeds} seeds")


def _scaffold_variant(tmp_path: Path, variant: str) -> tuple[Path, dict]:
    config, template_dir, engine, instance = _instance_for_variant(variant)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")
    instance_dir = scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)
    return instance_dir, instance.ground_truth


def _run_verifier(instance_dir: Path, input_file: Path, tmp_path: Path) -> tuple[float, dict]:
    reward_file = tmp_path / f"reward-{input_file.stem}.json"
    result = subprocess.run(
        [
            sys.executable,
            str(instance_dir / "tests" / "verify.py"),
            "--input",
            str(input_file),
            "--output",
            str(reward_file),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    reward = json.loads(reward_file.read_text(encoding="utf-8"))["reward"]
    details = json.loads((reward_file.parent / "details.json").read_text(encoding="utf-8"))
    return reward, details


def _extract_json_block(text: str) -> dict:
    matches = re.findall(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    assert matches, "No fenced JSON block found"
    return json.loads(matches[-1])


def _replace_json_block(text: str, payload: dict) -> str:
    block = "```json\n" + json.dumps(payload, indent=2) + "\n```"
    return re.sub(r"```json\s*\n.*?\n\s*```", lambda _m: block, text, count=1, flags=re.DOTALL)


# ---------------------------------------------------------------------------
# Discovery and sampling
# ---------------------------------------------------------------------------


def test_template_is_discoverable_by_builtin_name() -> None:
    templates = {config.meta.name: config for config, _path in discover_templates()}

    assert "road-low-point-issue-review-package" in templates
    config = templates["road-low-point-issue-review-package"]
    assert config.meta.discipline == "civil"
    assert config.meta.category == "road-review"
    assert config.meta.tool_mode.value == "no-tool"


def test_parameters_vary_across_seeds() -> None:
    config, _template_dir, engine = _load()

    variants = set()
    spreads = set()
    for seed in range(40):
        instance = sample_instance(config, engine.compute, "medium", seed=seed, instance_index=0)
        variants.add(instance.all_params["packet_variant"])
        spreads.add(instance.ground_truth["spread_width_m"])

    assert len(variants) >= 3, "Variant distribution collapsed"
    assert len(spreads) >= 10, "Numeric parameters do not vary across seeds (min==max regression)"


def test_same_seed_reproduces_ground_truth() -> None:
    config, _template_dir, engine = _load()

    a = sample_instance(config, engine.compute, "medium", seed=11, instance_index=0)
    b = sample_instance(config, engine.compute, "medium", seed=11, instance_index=0)

    assert a.all_params == b.all_params
    assert a.ground_truth == b.ground_truth


# ---------------------------------------------------------------------------
# Variant gold states
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant", sorted(VARIANT_EXPECTATIONS))
def test_variant_gold_statuses_and_readiness(variant: str) -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    expected = VARIANT_EXPECTATIONS[variant]

    for key in STATUS_KEYS:
        expected_code = expected["flips"].get(key, 0.0)
        assert gold[key] == expected_code, f"{variant}: {key} expected {expected_code}, got {gold[key]}"

    assert gold["readiness_code"] == expected["readiness"]
    assert gold["required_findings_count"] == expected["findings"]
    assert gold["required_information_requests_count"] == expected["requests"]
    assert gold["required_carried_actions_count"] == expected["carried"]


def test_clean_variant_evidence_is_consistent() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("clean")
    gold = instance.ground_truth
    params = instance.all_params

    for key in EVIDENCE_KEYS:
        assert key in gold, f"Missing evidence key {key}"

    assert gold["cabinet_freeboard_m"] >= float(params["minimum_cabinet_freeboard_m"])
    assert gold["spread_width_m"] < gold["allowable_spread_m"]
    assert gold["battery_runtime_h"] > float(params["required_autonomy_h"])
    assert gold["network_headroom_mbps"] > 0.0
    assert gold["vms_message_margin_chars"] > 0.0


def test_freeboard_deficient_variant_fails_criterion() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("freeboard_deficient")
    gold = instance.ground_truth

    assert gold["cabinet_freeboard_m"] < float(instance.all_params["minimum_cabinet_freeboard_m"])


def test_missing_cabinet_level_variant_omits_freeboard_evidence() -> None:
    _config, _template_dir, _engine, instance = _instance_for_variant("missing_cabinet_level")

    assert "cabinet_freeboard_m" not in instance.ground_truth


# ---------------------------------------------------------------------------
# Source pack generation
# ---------------------------------------------------------------------------


def test_build_sources_produces_seven_files_with_ids() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)

    assert sorted(sources) == sorted(SOURCE_FILES)

    joined = "\n".join(sources.values())
    for object_id in ["RD-SSC01-001", "LP-01", "CAB-01", "VMS-01", "STORM-01", "BATT-01", "ITS-NET-01"]:
        assert object_id in joined, f"Object ID {object_id} missing from source pack"

    register = sources["sources/document-register.md"]
    for doc_id in ["RD-SSC01-001", "DRN-SSC01-DES-01", "ITS-SSC01-LAY-01", "CRIT-SSC01-001"]:
        assert doc_id in register


def test_missing_cabinet_level_sources_omit_pad_level() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("missing_cabinet_level")
    sources = engine.build_sources(instance.all_params)

    equipment = sources["sources/field-equipment.md"]
    assert "pending" in equipment.lower()

    clean_params = dict(instance.all_params)
    clean_params["packet_variant"] = "clean"
    clean_equipment = engine.build_sources(clean_params)["sources/field-equipment.md"]
    assert clean_equipment != equipment


def test_stale_hgl_sources_have_revision_mismatch() -> None:
    _config, _template_dir, engine, instance = _instance_for_variant("stale_hgl_revision")
    sources = engine.build_sources(instance.all_params)

    register = sources["sources/document-register.md"]
    drainage = sources["sources/drainage-package.md"]

    assert "Rev C" in register
    assert "Rev B" in drainage


def test_sources_print_exact_engine_values() -> None:
    """Source files must carry the exact quantized values the engine computed with."""
    _config, _template_dir, engine, instance = _instance_for_variant("clean")
    sources = engine.build_sources(instance.all_params)
    drainage = sources["sources/drainage-package.md"]

    assert re.search(r"n = 0\.0\d{2}", drainage)


def _grab(pattern: str, text: str) -> float:
    match = re.search(pattern, text)
    assert match, f"Pattern not found: {pattern}"
    return float(match.group(1))


def _assert_low_point_evidence_recomputable_from_sources(variant: str) -> None:
    """Recompute the gold evidence available in a rendered source packet."""
    _config, _template_dir, engine, instance = _instance_for_variant(variant)
    gold = instance.ground_truth
    sources = engine.build_sources(instance.all_params)
    drainage = sources["sources/drainage-package.md"]
    geometry = sources["sources/road-geometry.md"]
    equipment = sources["sources/field-equipment.md"]
    power = sources["sources/power-comms.md"]
    traffic = sources["sources/traffic-operations.md"]
    criteria = sources["sources/criteria-comments.md"]

    c = _grab(r"Runoff coefficient C[^|]*\| ([\d.]+)", drainage)
    intensity = _grab(r"Rainfall intensity I[^|]*\| ([\d.]+) mm/h", drainage)
    area = _grab(r"Catchment area A[^|]*\| ([\d.]+) ha", drainage)
    bypass = _grab(r"Upstream bypass flow[^|]*\| ([\d.]+) m3/s", drainage)
    n_gutter = _grab(r"Gutter Manning n[^|]*\| n = ([\d.]+)", drainage)
    crossfall = _grab(r"Pavement crossfall[^|]*\| ([\d.]+) %", geometry)
    long_slope = _grab(r"longitudinal slope[^|]*\| ([\d.]+) %", geometry)
    lp_level = _grab(r"LP-01 pavement level[^|]*\| ([\d.]+) m AHD", geometry)

    peak = c * intensity * area / 360.0
    approach = peak + bypass
    sx = crossfall / 100.0
    sl = long_slope / 100.0
    spread = (approach * n_gutter / (0.376 * sx ** (5.0 / 3.0) * math.sqrt(sl))) ** (3.0 / 8.0)
    controlling = lp_level + spread * sx

    assert peak == pytest.approx(gold["peak_runoff_m3_s"], rel=0.01)
    assert approach == pytest.approx(gold["gutter_approach_flow_m3_s"], rel=0.01)
    assert spread == pytest.approx(gold["spread_width_m"], rel=0.01)
    assert controlling == pytest.approx(gold["controlling_water_level_m"], rel=0.01)

    if "cabinet_freeboard_m" in gold:
        pad_level = _grab(r"CAB-01 pad level[^|]*\| ([\d.]+) m AHD", equipment)
        freeboard = pad_level - controlling
        assert freeboard == pytest.approx(gold["cabinet_freeboard_m"], rel=0.01, abs=0.01)
    else:
        assert "pending survey verification" in equipment

    cap = _grab(r"Battery capacity \| ([\d.]+) kWh", power)
    eff = _grab(r"efficiency \| ([\d.]+)", power)
    load_w = _grab(r"critical load \| ([\d.]+) W", power)
    assert cap * eff / (load_w / 1000.0) == pytest.approx(gold["battery_runtime_h"], rel=0.01)

    cams = int(_grab(r"CCTV cameras \| (\d+)", power))
    cam_rate = _grab(r"Data rate per camera \| ([\d.]+) Mbps", power)
    vms_rate = _grab(r"VMS-01 data rate \| ([\d.]+) Mbps", power)
    ctrl_rate = _grab(r"Controller data rate \| ([\d.]+) Mbps", power)
    sensor_rate = _grab(r"sensor data rate \| ([\d.]+) Mbps", power)
    overhead = _grab(r"overhead allowance \| ([\d.]+) %", power)
    buffer_pct = _grab(r"capacity buffer \| ([\d.]+) %", power)
    uplink = _grab(r"Provisioned uplink \| ([\d.]+) Mbps", power)
    base = cams * cam_rate + vms_rate + ctrl_rate + sensor_rate
    required = base * (1 + overhead / 100.0) * (1 + buffer_pct / 100.0)
    assert uplink - required == pytest.approx(gold["network_headroom_mbps"], rel=0.01, abs=0.02)

    char_in = _grab(r"character height \| ([\d.]+) in", equipment)
    speed = _grab(r"Assessment speed \| ([\d.]+) km/h", traffic)
    rate = _grab(r"reading rate \| ([\d.]+) chars/s", traffic)
    msg_len = _grab(r"length \| (\d+) characters", traffic)
    reading_time = (char_in * 40.0 * 0.3048) / (speed / 3.6)
    assert reading_time * rate - msg_len == pytest.approx(gold["vms_message_margin_chars"], rel=0.01, abs=0.02)

    allowable = _grab(r"Allowable gutter spread[^|]*\| ([\d.]+) m", criteria)
    assert allowable == pytest.approx(gold["allowable_spread_m"], abs=1e-9)


@pytest.mark.parametrize("variant", ["clean", "freeboard_deficient"])
def test_evidence_recomputable_from_source_files_alone(variant: str) -> None:
    """Clean and genuine-failure packets must be solvable from rendered sources alone."""
    _assert_low_point_evidence_recomputable_from_sources(variant)


def test_missing_cabinet_level_packet_recomputes_available_evidence() -> None:
    """Missing-evidence packets must still expose all non-missing recomputable evidence."""
    _assert_low_point_evidence_recomputable_from_sources("missing_cabinet_level")


# ---------------------------------------------------------------------------
# Scaffolded instance layout
# ---------------------------------------------------------------------------


def test_scaffolded_instance_layout(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "clean")

    for rel in SOURCE_FILES:
        assert (instance_dir / "environment" / rel).exists(), f"Missing {rel}"

    dockerfile = (instance_dir / "environment" / "Dockerfile").read_text(encoding="utf-8")
    for rel in SOURCE_FILES:
        assert f"COPY {rel} /workspace/{rel}" in dockerfile

    instance_json = json.loads((instance_dir / "tests" / "instance.json").read_text(encoding="utf-8"))
    assert instance_json["all_params"]["packet_variant"] == "clean"
    assert "rlr_01_status" in instance_json["ground_truth"]

    verify_source = (instance_dir / "tests" / "verify.py").read_text(encoding="utf-8")
    assert "instance.json" in verify_source

    system_prompt = (instance_dir / "environment" / "system_prompt.md").read_text(encoding="utf-8")
    assert "review" in system_prompt.lower()

    assert not list(instance_dir.glob("environment/*_calc.py")), "no-tool template must not ship a calc script"

    instruction = (instance_dir / "instruction.md").read_text(encoding="utf-8")
    assert "{{" not in instruction
    assert "/workspace/sources/" in instruction
    assert "/workspace/output.md" in instruction
    for item in [f"RLR-0{i}" for i in range(1, 10)]:
        assert item in instruction


# ---------------------------------------------------------------------------
# Verifier: goldens
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant", sorted(VARIANT_EXPECTATIONS))
def test_golden_pass_scores_one(tmp_path: Path, variant: str) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, variant)
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    reward, _details = _run_verifier(instance_dir, golden_pass, tmp_path)
    assert reward == 1.0


@pytest.mark.parametrize("variant", ["clean", "open_critical_comment"])
def test_golden_fail_fluent_unsafe_memo_scores_low(tmp_path: Path, variant: str) -> None:
    """An all-pass, ready-to-issue memo without evidence must not pass review."""
    instance_dir, _gold = _scaffold_variant(tmp_path, variant)
    golden_fail = instance_dir / "tests" / "fixtures" / "golden_fail.md"

    reward, _details = _run_verifier(instance_dir, golden_fail, tmp_path)
    assert reward <= 0.5


# ---------------------------------------------------------------------------
# Verifier: localization and anti-gaming
# ---------------------------------------------------------------------------


def test_verifier_localizes_flipped_status(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "clean")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["review_matrix"]["RLR-03"]["status"] = "fail"
    mutated = tmp_path / "mutated-status.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["matrix"]["items"]["RLR-03"] < 1.0


def test_verifier_gates_status_credit_on_evidence(tmp_path: Path) -> None:
    """Correct statuses without computed evidence must lose matrix, evidence, and readiness credit."""
    instance_dir, _gold = _scaffold_variant(tmp_path, "clean")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["computed_evidence"] = {}
    mutated = tmp_path / "mutated-evidence.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward <= 0.6
    assert details["gates"]["readiness"]["score"] == 0.0


def test_verifier_zeroes_readiness_on_unsupported_ready_decision(tmp_path: Path) -> None:
    instance_dir, _gold = _scaffold_variant(tmp_path, "freeboard_deficient")
    golden_pass = instance_dir / "tests" / "fixtures" / "golden_pass.md"

    text = golden_pass.read_text(encoding="utf-8")
    payload = _extract_json_block(text)
    payload["readiness_decision"] = "ready_to_issue"
    mutated = tmp_path / "mutated-readiness.md"
    mutated.write_text(_replace_json_block(text, payload), encoding="utf-8")

    reward, details = _run_verifier(instance_dir, mutated, tmp_path)
    assert reward < 1.0
    assert details["gates"]["readiness"]["score"] == 0.0
