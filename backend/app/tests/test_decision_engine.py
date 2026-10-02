import pytest
from app.services.decision.decision_engine import TrafficDecisionEngine
from app.services.decision.vehicle_scoring import score_classes
from app.services.lanes.lane_intelligence import LaneMetrics, LaneStatus


def metrics(e=0, w=0, n=0, s=0):
    return {d: LaneMetrics(d, 0, 0, 0, 0, 0, 0, 0, LaneStatus.FREE, [], value)
            for d, value in zip(("EAST", "WEST", "NORTH", "SOUTH"), (e, w, n, s))}


def test_requested_weights_and_aliases():
    score, counts = score_classes(["car", "car", "auto", "ricksaw", "motorbike", "scooter"])
    assert score == 9
    assert counts == {"car": 2, "rickshaw": 2, "motorcycle": 2}


def test_pair_scores_are_means_of_individual_weighted_scores():
    decision = TrafficDecisionEngine().decide(metrics(20, 8, 30, 10), "EW", elapsed_s=10)
    assert decision.pair_scores == {"EW": 14, "NS": 20}
    assert decision.denser_pair == "NS"
    assert decision.score_difference == 6
    assert decision.selected_direction == "EW"


def test_initial_denser_pair_requires_twenty_point_difference():
    assert TrafficDecisionEngine().decide(metrics(20, 20, 40, 40), "EW").selected_direction == "NS"
    assert TrafficDecisionEngine().decide(metrics(20, 20, 39, 39), "EW").selected_direction == "EW"


def test_normal_timer_alternates_even_when_same_pair_remains_denser():
    engine = TrafficDecisionEngine()
    demand = metrics(80, 80, 1, 1)
    assert engine.decide(demand, "EW", elapsed_s=69.9).selected_direction == "EW"
    first = engine.decide(demand, "EW", elapsed_s=70)
    assert first.selected_direction == "NS" and first.action == "TIMER"
    assert engine.decide(demand, "NS", elapsed_s=70).selected_direction == "EW"


def test_early_switch_requires_three_seconds_of_persistent_low_score():
    engine = TrafficDecisionEngine()
    demand = metrics(5, 5, 25, 25)
    assert engine.decide(demand, "EW", elapsed_s=27).action == "HOLD"
    assert engine.decide(demand, "EW", elapsed_s=29.9).action == "HOLD"
    result = engine.decide(demand, "EW", elapsed_s=30)
    assert result.selected_direction == "NS" and result.action == "EARLY"
    assert result.green_duration_s == 70


@pytest.mark.parametrize("elapsed,e,w,n,s", [(50,5,5,40,40),(51,0,0,40,40),(30,5.1,5.1,40,40),(30,5,5,24.9,24.9)])
def test_early_switch_boundaries(elapsed,e,w,n,s):
    engine = TrafficDecisionEngine()
    engine.decide(metrics(e,w,n,s), "EW", elapsed_s=elapsed-3)
    assert engine.decide(metrics(e,w,n,s), "EW", elapsed_s=elapsed).action == "HOLD"


def test_low_score_streak_resets_when_demand_or_camera_data_changes():
    engine = TrafficDecisionEngine()
    engine.decide(metrics(0,0,30,30), "EW", elapsed_s=10)
    engine.decide(metrics(6,6,30,30), "EW", elapsed_s=12)
    assert engine.decide(metrics(0,0,30,30), "EW", elapsed_s=14).action == "HOLD"
    engine.decide(metrics(0,0,30,30), "EW", elapsed_s=16, data_complete=False)
    assert engine.decide(metrics(0,0,30,30), "EW", elapsed_s=18).action == "HOLD"


def test_early_receiving_phase_cannot_be_cut_short_again():
    engine = TrafficDecisionEngine()
    demand = metrics(40,40,0,0)
    engine.decide(demand,"NS",elapsed_s=10,full_phase_required=True)
    assert engine.decide(demand,"NS",elapsed_s=20,full_phase_required=True).action == "HOLD"
    result = engine.decide(demand,"NS",elapsed_s=70,full_phase_required=True)
    assert result.action == "TIMER" and result.selected_direction == "EW"


def test_missing_camera_disables_demand_rules_but_normal_timer_continues():
    engine = TrafficDecisionEngine()
    demand = metrics(0,0,50,50)
    result = engine.decide(demand,"EW",elapsed_s=30,data_complete=False)
    assert result.action == "HOLD" and result.denser_pair is None
    assert result.pair_scores == {"EW": None, "NS": None}
    assert engine.decide(demand,"EW",elapsed_s=70,data_complete=False).selected_direction == "NS"


def test_emergency_override_requires_flashing_lights():
    demand = metrics(40,40,0,0)
    result = TrafficDecisionEngine().decide(demand,"EW",emergency_direction="NORTH",elapsed_s=30)
    assert result.selected_direction == "EW"
    result = TrafficDecisionEngine().decide(demand,"EW",emergency_direction="NORTH",elapsed_s=30,emergency_lights_active=True)
    assert result.selected_direction == "NS" and result.action == "EMERGENCY"


def test_empty_metrics_rejected():
    with pytest.raises(ValueError):
        TrafficDecisionEngine().decide({},"EW")


def test_density_updates_during_yellow_cannot_change_pending_pair():
    engine = TrafficDecisionEngine()
    result = engine.decide(metrics(80,80,0,0),"EW",elapsed_s=2,transition_target="NS",
                           emergency_direction="WEST",emergency_lights_active=True)
    assert result.selected_direction == "NS" and result.action == "YELLOW"
    assert result.denser_pair == "EW"
