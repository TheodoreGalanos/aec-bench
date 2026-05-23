# ABOUTME: Tests for the Pydantic response schemas used by JSON API endpoints.
# ABOUTME: Verifies that each schema can be instantiated and round-trips through model_dump().

from typing import Any

from aec_bench.web.schemas import (
    AggregateRowSchema,
    AnnotationSchema,
    CellStatsSchema,
    CompareResponse,
    DashboardResponse,
    DatasetDetailResponse,
    DatasetListItemSchema,
    DatasetsListResponse,
    DatasetSummarySchema,
    DatasetTaskEntrySchema,
    EvaluateResponse,
    ExperimentResultSchema,
    ExperimentSummarySchema,
    IntegrityResultSchema,
    LeaderboardResponse,
    LibraryDetailResponse,
    LibraryListResponse,
    ModelRowSchema,
    OverallRowSchema,
    ReviewQueueResponse,
    ReviewTrialResponse,
    ScorecardCellSchema,
    ScorecardRowSchema,
    SearchResponse,
    StepSummarySchema,
    TemplateIOSchema,
    TemplateSchema,
    TriageResponse,
    TrialRowSchema,
    ViewerMetaResponse,
    ViewerStateResponse,
    ViewerStepResponse,
)

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_experiment_summary_schema_round_trips() -> None:
    schema = ExperimentSummarySchema(
        experiment_id="exp-01",
        trial_count=5,
        mean_reward=0.75,
        models=["gpt-4"],
        disciplines=["electrical"],
        adapters=["openai"],
    )
    data = schema.model_dump()
    assert data["experiment_id"] == "exp-01"
    assert data["trial_count"] == 5
    assert data["mean_reward"] == 0.75


def test_dashboard_response_with_one_experiment() -> None:
    exp = ExperimentSummarySchema(
        experiment_id="exp-01",
        trial_count=3,
        mean_reward=0.6,
        models=["claude"],
        disciplines=["civil"],
        adapters=["anthropic"],
    )
    response = DashboardResponse(
        experiments=[exp],
        total_trials=3,
        total_experiments=1,
        mean_reward=0.6,
        annotated_count=0,
    )
    data = response.model_dump()
    assert len(data["experiments"]) == 1
    assert data["total_trials"] == 3
    assert data["total_experiments"] == 1
    assert data["mean_reward"] == 0.6
    assert data["annotated_count"] == 0


# ---------------------------------------------------------------------------
# Triage
# ---------------------------------------------------------------------------


def test_trial_row_schema_round_trips() -> None:
    row = TrialRowSchema(
        trial_id="trial-001",
        experiment_id="exp-01",
        task_id="electrical/voltage-drop/instance-01",
        model="gpt-4",
        adapter="openai",
        discipline="electrical",
        reward=1.0,
        reward_class="reward-perfect",
        annotation_icon="\u2713",
        annotation_verdict="pass",
    )
    data = row.model_dump()
    assert data["trial_id"] == "trial-001"
    assert data["reward"] == 1.0


def test_triage_response_with_one_trial() -> None:
    row = TrialRowSchema(
        trial_id="trial-001",
        experiment_id="exp-01",
        task_id="electrical/voltage-drop/instance-01",
        model="gpt-4",
        adapter="openai",
        discipline="electrical",
        reward=0.5,
        reward_class="reward-mid",
        annotation_icon="",
        annotation_verdict="",
    )
    response = TriageResponse(
        trials=[row],
        trial_count=1,
        annotations={},
        filters={},
        experiments=["exp-01"],
        models=["gpt-4"],
    )
    data = response.model_dump()
    assert len(data["trials"]) == 1
    assert data["trial_count"] == 1


# ---------------------------------------------------------------------------
# Viewer
# ---------------------------------------------------------------------------


def test_step_summary_schema_round_trips() -> None:
    step = StepSummarySchema(
        step=1,
        status="success",
        description="bash",
        tool_name="bash",
        duration_ms=250,
        error_count=0,
        metadata=None,
    )
    data = step.model_dump()
    assert data["step"] == 1
    assert data["duration_ms"] == 250
    assert data["metadata"] is None


def test_step_summary_schema_with_metadata() -> None:
    step = StepSummarySchema(
        step=2,
        status="fail",
        description="python",
        tool_name="python",
        duration_ms=None,
        error_count=1,
        metadata={"tokens": 1024, "template_progress": 0.5},
    )
    data = step.model_dump()
    assert data["error_count"] == 1
    assert data["metadata"]["tokens"] == 1024


def test_viewer_meta_response_minimal() -> None:
    step = StepSummarySchema(
        step=1,
        status="success",
        description="bash",
        tool_name="bash",
        duration_ms=100,
        error_count=0,
        metadata=None,
    )
    response = ViewerMetaResponse(
        trial_id="trial-001",
        experiment_id="exp-01",
        task_id="electrical/voltage-drop/instance-01",
        model="claude",
        adapter="anthropic",
        reward=0.8,
        reward_class="reward-good",
        steps=[step],
        is_rlm_trial=False,
        artefacts=[],
        annotation=None,
        total_errors=0,
        tokens_in=None,
        tokens_out=None,
        total_tokens=None,
        siblings=["trial-001"],
        prev_trial=None,
        next_trial=None,
        back_url="/",
        has_trajectory=True,
    )
    data = response.model_dump()
    assert data["trial_id"] == "trial-001"
    assert data["annotation"] is None
    assert data["tokens_in"] is None
    assert len(data["steps"]) == 1


def test_viewer_meta_response_with_annotation() -> None:
    ann = AnnotationSchema(verdict="pass", notes="Looks good", timestamp="2024-01-01T00:00:00")
    response = ViewerMetaResponse(
        trial_id="trial-002",
        experiment_id="exp-01",
        task_id="civil/pavement/instance-01",
        model="gpt-4",
        adapter="openai",
        reward=1.0,
        reward_class="reward-perfect",
        steps=[],
        is_rlm_trial=True,
        artefacts=["output.png"],
        annotation=ann,
        total_errors=0,
        tokens_in=1000,
        tokens_out=500,
        total_tokens=1500,
        siblings=["trial-002"],
        prev_trial=None,
        next_trial=None,
        back_url="/",
        has_trajectory=True,
    )
    data = response.model_dump()
    assert data["annotation"]["verdict"] == "pass"
    assert data["total_tokens"] == 1500


def test_viewer_step_response_with_message() -> None:
    msg: dict[str, Any] = {"role": "user", "content": "hello"}
    response = ViewerStepResponse(step_num=1, messages=[msg])
    data = response.model_dump()
    assert data["step_num"] == 1
    assert len(data["messages"]) == 1
    assert data["messages"][0]["role"] == "user"


def test_viewer_state_response() -> None:
    response = ViewerStateResponse(
        symbolic_state={"x": 42, "y": "hello"},
        scratchpad_data={"NOTE": "some note"},
    )
    data = response.model_dump()
    assert data["symbolic_state"]["x"] == 42
    assert data["scratchpad_data"]["NOTE"] == "some note"


# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------


def test_cell_stats_schema_round_trips() -> None:
    cell = CellStatsSchema(
        count=10,
        mean_reward=0.75,
        perfect_count=3,
        zero_count=1,
        total_cost=0.05,
        reward_class="reward-good",
        reward_bg="rgba(97, 170, 242, 0.10)",
    )
    data = cell.model_dump()
    assert data["count"] == 10
    assert data["mean_reward"] == 0.75


def test_evaluate_response_with_one_cell() -> None:
    cell = CellStatsSchema(
        count=5,
        mean_reward=0.8,
        perfect_count=2,
        zero_count=0,
        total_cost=0.02,
        reward_class="reward-good",
        reward_bg="rgba(191, 191, 186, 0.10)",
    )
    response = EvaluateResponse(
        matrix={"openai \u00b7 gpt-4": cell},
        adapters=["openai"],
        task_prefixes=["voltage-drop"],
        row_totals={"openai \u00b7 gpt-4": cell},
        col_totals={"voltage-drop": cell},
        grand_total=cell,
        label_to_parts={"openai \u00b7 gpt-4": ["openai", "gpt-4"]},
        experiments=["exp-01"],
        selected_experiment="exp-01",
    )
    data = response.model_dump()
    assert "openai \u00b7 gpt-4" in data["matrix"]
    assert data["selected_experiment"] == "exp-01"


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


def test_aggregate_row_schema_round_trips() -> None:
    row = AggregateRowSchema(
        task_type="voltage-drop",
        model_means={"openai \u00b7 gpt-4": 0.8},
        model_counts={"openai \u00b7 gpt-4": 5},
        model_reward_classes={"openai \u00b7 gpt-4": "reward-good"},
        delta=None,
        delta_class="delta-chip neutral",
    )
    data = row.model_dump()
    assert data["task_type"] == "voltage-drop"
    assert data["delta"] is None


def test_overall_row_schema_round_trips() -> None:
    row = OverallRowSchema(
        model_means={"anthropic \u00b7 claude": 0.9},
        model_counts={"anthropic \u00b7 claude": 10},
        model_reward_classes={"anthropic \u00b7 claude": "reward-good"},
        delta=0.1,
        delta_class="delta-chip positive",
    )
    data = row.model_dump()
    assert data["delta"] == 0.1


def test_compare_response_with_rows() -> None:
    agg_row = AggregateRowSchema(
        task_type="voltage-drop",
        model_means={"openai \u00b7 gpt-4": 0.75},
        model_counts={"openai \u00b7 gpt-4": 4},
        model_reward_classes={"openai \u00b7 gpt-4": "reward-good"},
        delta=None,
        delta_class="delta-chip neutral",
    )
    overall = OverallRowSchema(
        model_means={"openai \u00b7 gpt-4": 0.75},
        model_counts={"openai \u00b7 gpt-4": 4},
        model_reward_classes={"openai \u00b7 gpt-4": "reward-good"},
        delta=None,
        delta_class="delta-chip neutral",
    )
    response = CompareResponse(
        models=["openai \u00b7 gpt-4"],
        task_types=["voltage-drop"],
        aggregate_table=[agg_row],
        overall=overall,
        model_colours={"openai \u00b7 gpt-4": "var(--model-gpt-mini)"},
        model_to_parts={"openai \u00b7 gpt-4": ["openai", "gpt-4"]},
        experiments=["exp-01"],
        selected_experiment="exp-01",
        view_mode="aggregate",
        active_task_type=None,
    )
    data = response.model_dump()
    assert len(data["aggregate_table"]) == 1
    assert data["view_mode"] == "aggregate"
    assert data["active_task_type"] is None


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


def test_model_row_schema_round_trips() -> None:
    row = ModelRowSchema(
        adapter="openai",
        model="gpt-4",
        trials=20,
        mean_reward=0.85,
        perfect_pct=40.0,
        zero_pct=10.0,
        cost=1.25,
    )
    data = row.model_dump()
    assert data["trials"] == 20
    assert data["cost"] == 1.25


def test_model_row_schema_no_cost() -> None:
    row = ModelRowSchema(
        adapter="anthropic",
        model="claude",
        trials=5,
        mean_reward=0.6,
        perfect_pct=20.0,
        zero_pct=20.0,
        cost=None,
    )
    data = row.model_dump()
    assert data["cost"] is None


def test_leaderboard_response_with_model_rows() -> None:
    row = ModelRowSchema(
        adapter="openai",
        model="gpt-4",
        trials=10,
        mean_reward=0.7,
        perfect_pct=30.0,
        zero_pct=15.0,
        cost=0.5,
    )
    scorecard_cell = ScorecardCellSchema(mean_reward=0.7, trials=10)
    scorecard_row = ScorecardRowSchema(
        adapter="openai",
        model="gpt-4",
        cells={"ds-v1@1.0.0": scorecard_cell},
        overall=0.7,
    )
    dataset_summary = DatasetSummarySchema(
        name="ds-v1",
        version="1.0.0",
        summary="Test dataset",
        task_count=5,
        domains=["electrical"],
    )
    response = LeaderboardResponse(
        model_rows=[row],
        is_scorecard=False,
        scorecard_rows=[scorecard_row],
        datasets=[dataset_summary],
        selected_dataset="ds-v1@1.0.0",
    )
    data = response.model_dump()
    assert len(data["model_rows"]) == 1
    assert data["is_scorecard"] is False
    assert data["selected_dataset"] == "ds-v1@1.0.0"


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


def test_datasets_list_response_empty() -> None:
    response = DatasetsListResponse(datasets=[], total_datasets=0, total_tasks=0)
    data = response.model_dump()
    assert data["datasets"] == []
    assert data["total_datasets"] == 0
    assert data["total_tasks"] == 0


def test_dataset_list_item_schema_round_trips() -> None:
    item = DatasetListItemSchema(
        name="benchmark-v1",
        version="1.0.0",
        summary="A test dataset",
        task_count=10,
        domains=["electrical", "civil"],
        content_hash="abc123",
    )
    data = item.model_dump()
    assert data["name"] == "benchmark-v1"
    assert data["content_hash"] == "abc123"


def test_dataset_detail_response_round_trips() -> None:
    task_entry = DatasetTaskEntrySchema(
        task_id="electrical/voltage-drop/instance-01",
        domain="electrical",
        difficulty="medium",
        tags=["voltage", "cable"],
    )
    exp_result = ExperimentResultSchema(
        experiment_id="exp-01",
        trial_count=5,
        mean_reward=0.75,
        reward_class="reward-good",
        models=["gpt-4"],
    )
    integrity = IntegrityResultSchema(
        task_id="electrical/voltage-drop/instance-01",
        status="verified",
        expected_hash="abc123",
    )
    response = DatasetDetailResponse(
        name="benchmark-v1",
        version="1.0.0",
        summary="A test dataset",
        content_hash="abc123",
        task_count=1,
        domains=["electrical"],
        tasks=[task_entry],
        experiment_results=[exp_result],
        integrity_results=[integrity],
    )
    data = response.model_dump()
    assert data["name"] == "benchmark-v1"
    assert len(data["tasks"]) == 1
    assert len(data["experiment_results"]) == 1


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def test_template_schema_round_trips() -> None:
    io_schema = TemplateIOSchema(name="voltage", description="Supply voltage in V")
    template = TemplateSchema(
        task_id="voltage-drop",
        discipline="electrical",
        description="Compute voltage drop",
        long_description="Extended description of voltage drop computation.",
        tags=["voltage", "cable"],
        standards=["AS/NZS 3008"],
        inputs=[io_schema],
        outputs=[TemplateIOSchema(name="vd", description="Voltage drop in V")],
        param_count=3,
    )
    data = template.model_dump()
    assert data["task_id"] == "voltage-drop"
    assert len(data["inputs"]) == 1
    assert data["param_count"] == 3


def test_library_list_response_with_one_template() -> None:
    template = TemplateSchema(
        task_id="voltage-drop",
        discipline="electrical",
        description="Compute voltage drop",
        long_description="",
        tags=[],
        standards=[],
        inputs=[],
        outputs=[],
        param_count=0,
    )
    response = LibraryListResponse(
        templates=[template],
        disciplines=["electrical"],
        selected_discipline="electrical",
    )
    data = response.model_dump()
    assert len(data["templates"]) == 1
    assert data["selected_discipline"] == "electrical"


def test_library_detail_response_round_trips() -> None:
    template = TemplateSchema(
        task_id="voltage-drop",
        discipline="electrical",
        description="Compute voltage drop",
        long_description="",
        tags=[],
        standards=[],
        inputs=[],
        outputs=[],
        param_count=0,
    )
    response = LibraryDetailResponse(template=template)
    data = response.model_dump()
    assert data["template"]["task_id"] == "voltage-drop"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def test_search_response_with_query() -> None:
    response = SearchResponse(
        query="voltage drop",
        template_results=[{"name": "voltage-drop", "discipline": "electrical"}],
        dataset_results=[],
        total_results=1,
    )
    data = response.model_dump()
    assert data["query"] == "voltage drop"
    assert data["total_results"] == 1
    assert len(data["template_results"]) == 1


def test_search_response_empty() -> None:
    response = SearchResponse(
        query="",
        template_results=[],
        dataset_results=[],
        total_results=0,
    )
    data = response.model_dump()
    assert data["total_results"] == 0


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


def test_review_queue_response_round_trips() -> None:
    response = ReviewQueueResponse(assignments={"reviewer_id": "rev-01", "items": []})
    data = response.model_dump()
    assert data["assignments"]["reviewer_id"] == "rev-01"


def test_review_trial_response_round_trips() -> None:
    response = ReviewTrialResponse(bundle={"trial_id": "trial-001", "task": {}})
    data = response.model_dump()
    assert data["bundle"]["trial_id"] == "trial-001"
