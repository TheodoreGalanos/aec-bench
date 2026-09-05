# ABOUTME: Tests investigation choice, hidden-state separation, costs, and deadlines.
# ABOUTME: Distinguishes a correct response from supported and timely decision making.

from dataclasses import replace

from aec_bench.experimentation.engineering_decisions.dam_investigation import run_dam_investigation
from aec_bench.experimentation.engineering_decisions.policies import evidence_first_action
from aec_bench.worlds.monitoring.dam_seepage.investigation import investigation_scenarios
from aec_bench.worlds.monitoring.dam_seepage.world import SeepageAction as A
from aec_bench.worlds.monitoring.dam_seepage.world import initial_state, observe, transition
from aec_bench.worlds.runtime.world_logic import ActionRejected


def test_hidden_fault_pair_has_identical_opening_observations() -> None:
    routine, fault, _ = investigation_scenarios()
    assert observe(initial_state(routine)) == observe(initial_state(fault))


def test_observation_policy_selects_sufficient_evidence_under_budget() -> None:
    for scenario, cost in zip(investigation_scenarios(), (7, 2, 2), strict=True):
        report = run_dam_investigation(scenario, evidence_first_action)
        assert report["evaluation"]["successful"]
        assert not report["rejections"]
        assert report["evaluation"]["investigation_spent"] == cost
        assert report["perfect_information_minimum_cost"] == cost


def test_correct_escalation_without_evidence_is_not_success() -> None:
    report = run_dam_investigation(investigation_scenarios()[1], lambda _: A.ESCALATE_FOR_ENGINEERING_REVIEW)
    assert report["evaluation"]["response_correct"]
    assert not report["evaluation"]["evidence_complete"]
    assert not report["evaluation"]["successful"]


def test_unnecessary_waiting_misses_the_urgent_deadline() -> None:
    actions = iter((A.RECORD_CONFIRMATION_READING, A.CHECK_MEASUREMENT_SYSTEM, A.ESCALATE_FOR_ENGINEERING_REVIEW))
    report = run_dam_investigation(investigation_scenarios()[2], lambda _: next(actions))
    assert report["evaluation"]["response_correct"]
    assert report["evaluation"]["evidence_complete"]
    assert not report["evaluation"]["response_timely"]
    assert not report["evaluation"]["successful"]


def test_insufficient_budget_rejects_without_consuming_state() -> None:
    state = replace(initial_state(investigation_scenarios()[0]), investigation_spent=7)
    result = transition(state, A.INSPECT_DOWNSTREAM_AREA)
    assert isinstance(result, ActionRejected)
    assert state.investigation_spent == 7


def test_duplicate_investigation_rejection_does_not_charge_again() -> None:
    from aec_bench.contracts.world_interface import WorldActorActionRequest
    from aec_bench.worlds.monitoring.dam_seepage.definition import DamSeepageProfile
    from aec_bench.worlds.monitoring.dam_seepage.episode_runtime import DamSeepageEpisodeHost

    scenario = investigation_scenarios()[0]
    host = DamSeepageEpisodeHost(profile=DamSeepageProfile(scenario, initial_state(scenario)))
    request = WorldActorActionRequest(
        request_id="instrument",
        decision_id=host.observe().decision_id,
        action_name=A.CHECK_MEASUREMENT_SYSTEM.value,
        arguments={},
    )
    first = host.invoke(request)
    assert host.invoke(request) == first
    assert host.state.investigation_spent == 2
    repeated = request.model_copy(update={"request_id": "repeat", "decision_id": host.observe().decision_id})
    assert host.invoke(repeated).status == "rejected"
    assert host.state.investigation_spent == 2
