# ABOUTME: Tests for swarm dashboard Pydantic response schemas.
# ABOUTME: Validates serialisation of swarm state, agents, budget, and events.

from aec_bench.web.schemas import (
    SwarmAgentSchema,
    SwarmBudgetSchema,
    SwarmCentroidSchema,
    SwarmEventSchema,
    SwarmEventsResponse,
    SwarmLineageNodeSchema,
    SwarmRunSummarySchema,
    SwarmStateResponse,
)


def test_swarm_run_summary_schema():
    s = SwarmRunSummarySchema(
        run_id="abc123",
        workspace="heat-load-audit-swarm",
        status="completed",
        agent_count=3,
        total_evals=47,
        best_score=0.87,
        total_cost_usd=4.38,
        elapsed_seconds=433.0,
        strategy="qd",
    )
    d = s.model_dump()
    assert d["run_id"] == "abc123"
    assert d["status"] == "completed"


def test_swarm_state_response():
    resp = SwarmStateResponse(
        run_id="abc123",
        workspace="ws",
        status="completed",
        agents=[
            SwarmAgentSchema(
                agent_id="agent-0",
                model="sonnet-4.6",
                status="active",
                eval_count=5,
                best_score=0.87,
                budget_consumed_usd=1.2,
            ),
        ],
        budget=SwarmBudgetSchema(
            max_cost_usd=5.0,
            total_spent_usd=4.38,
            spend_percentage=0.876,
            phase="winding_down",
        ),
        centroids=[
            SwarmCentroidSchema(x=0.1, y=0.2, occupied=True, reward=0.87, version="evo-5", agent_id="agent-0"),
            SwarmCentroidSchema(x=0.5, y=0.6, occupied=False),
        ],
        lineage=[
            SwarmLineageNodeSchema(
                version="evo-5",
                parent_version="evo-3",
                agent_id="agent-0",
                cross_agent=False,
                surprise=False,
                mutation_type="prompt_rewrite",
                reward=0.87,
            ),
        ],
        notes=[],
        consolidation_reports=[],
        events=[],
        total_evals=47,
        best_score=0.87,
        elapsed_seconds=433.0,
    )
    d = resp.model_dump()
    assert len(d["agents"]) == 1
    assert len(d["centroids"]) == 2
    assert d["centroids"][1]["occupied"] is False


def test_swarm_events_response():
    resp = SwarmEventsResponse(
        events=[
            SwarmEventSchema(
                event_type="eval_completed",
                timestamp="2026-04-08T02:20:00Z",
                agent_id="agent-0",
                payload={"score": 0.87},
                sequence_number=10,
            ),
        ],
    )
    assert len(resp.events) == 1
    assert resp.events[0].sequence_number == 10
