# ABOUTME: Locks the complete repaired W4 probe catalogue and deterministic execution maps.
# ABOUTME: Prevents W3 sensitivity work from skipping probes or reviving superseded engine variants.

from pathlib import Path

from sensitivity import catalogue

B5_ROOT = Path(__file__).parents[2]
PROBE_DECLARATION = B5_ROOT / "declarations" / "w4-probe-catalogue.json"
FAMILY_REPAIR = B5_ROOT / "declarations" / "w4-family-coverage-repair.json"


def test_reads_exact_complete_w4_probe_catalogue() -> None:
    raw = PROBE_DECLARATION.read_bytes()

    declaration = catalogue.read_probe_catalogue(raw)

    assert catalogue.canonical_json_bytes(declaration) == raw
    assert declaration["authority"] == {
        "composition_repair_sha256": ("38ca15bf46f67ee98aa66539701bbd8fc1889c1e268d42f0f724f7942b3c2ff8"),
        "engine_mapping_repair_sha256": ("862ef1f5fc70d882d156c0ef9842bb565301344725d2206edfa49c10910576ca"),
        "family_coverage_repair_sha256": ("828bec8786523ef8b2e1485d2cfbb2df08731708b038ecaaf6bc09b66da79fce"),
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
        "schema_id": "asw-0b5.w4-probe-catalogue.v1",
        "w4_sha256": ("56502750816efec73ed821ac00ee5ead4ed76ba05e243992f794005980c19b7f"),
    }
    assert len(declaration["oat_parameters"]) == 34
    assert declaration["oat_probe_ids"] == sorted(
        f"OAT.{parameter}.{bound}" for parameter in declaration["oat_parameters"] for bound in ("lower", "upper")
    )
    assert len(declaration["oat_probe_ids"]) == 68
    assert [item["probe_id"] for item in declaration["interactions"]] == [
        "INT.00.anchor",
        "INT.01.hydraulic-supporting",
        "INT.02.hydraulic-opposing",
        "INT.03.primary-dominant",
        "INT.04.secondary-dominant",
    ]
    assert [item["probe_id"] for item in declaration["boundaries"]] == [f"BND.{index:02d}" for index in range(11)]
    assert [item["variant_id"] for item in declaration["engine_variants"]] == [
        "ENG.00.base",
        "ENG.01.curve-16",
        "ENG.02.curve-64",
        "ENG.03.report-2s",
        "ENG.04.route-report-2s",
        "ENG.05.outfall-order-swap",
        "ENG.06.outfall-target-swap",
    ]
    assert declaration["engine_case_ids"] == [
        "G10_CLEAN_A_BASE",
        "G12_CLEAN_ASSESS",
        "G21_OBSTRUCTION_TRIGGER",
        "G31_CLEARANCE_UPPER",
        "G41_COMBINED_UPPER",
        "G70_TRANSFER",
    ]
    assert declaration["mutation_ids"] == [f"M{index:02d}" for index in range(1, 31)]
    assert declaration["replay_ordinals"] == [0, 1]


def test_catalogue_grid_cardinality_is_fixed() -> None:
    declaration = catalogue.read_probe_catalogue(PROBE_DECLARATION.read_bytes())
    grids = declaration["grids"]

    assert len(grids["flow_observation"]) == 9
    assert len(grids["level_observation"]) == 9
    assert len(grids["runtime_observation"]) == 3
    assert len(grids["progression"]) == 3
    assert len(grids["intervention"]) == 3
    assert len(grids["resource"]) == 5


def test_family_coverage_repair_preserves_failed_members_and_exact_replacements() -> None:
    repair = catalogue.read_family_coverage_repair(FAMILY_REPAIR.read_bytes())

    assert repair["authority"]["predecessor_probe_catalogue_sha256"] == (
        "a210cda08dd68ac0106aee98d242f9fde0ce3fc74dcb4004e11cc00df8fe1425"
    )
    assert [item["probe_id"] for item in repair["failed_members"]] == [
        "INT.01.hydraulic-supporting",
        "INT.02.hydraulic-opposing",
    ]
    assert repair["replacements"] == [
        {
            "probe_id": "INT.01.hydraulic-supporting",
            "removed_bound_selections": ["pump.H_0", "pump.Q_0"],
            "retained_selection_groups": ["wet-well", "levels", "inflow", "system"],
        },
        {
            "probe_id": "INT.02.hydraulic-opposing",
            "removed_bound_selections": [
                "system.D",
                "system.K_minor",
                "system.L",
                "system.epsilon",
                "system.z_d",
            ],
            "retained_selection_groups": ["wet-well", "levels", "inflow", "pump"],
        },
    ]
    assert repair["status"] == "applied-pre-generation-repair"


def test_rejects_changed_but_canonical_probe_catalogue() -> None:
    declaration = catalogue.read_probe_catalogue(PROBE_DECLARATION.read_bytes())
    declaration["mutation_ids"].pop()

    try:
        catalogue.read_probe_catalogue(catalogue.canonical_json_bytes(declaration))
    except catalogue.ProbeCatalogueError as error:
        assert "content identity differs" in str(error)
    else:
        raise AssertionError("changed W4 probe catalogue was accepted")
