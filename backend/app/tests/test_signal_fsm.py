import pytest
from dataclasses import replace
from app.core.domain_config import DomainConfig, SignalTimings
from app.services.signals.signal_fsm import SignalFSM, SignalMode, PhaseColor

DIRECTIONS = ["EAST", "WEST", "NORTH", "SOUTH"]

def test_every_change_clears_outgoing_pair_before_opposing_green():
    fsm = SignalFSM(DIRECTIONS)
    for direction in DIRECTIONS * 5:
        changed = fsm.request_phase_change(direction,"updated demand")
        if changed:
            assert fsm.state.color == PhaseColor.YELLOW
            assert sum(s == "GREEN" for s in fsm.direction_states.values()) == 0
            assert sum(s == "YELLOW" for s in fsm.direction_states.values()) == 2
            assert fsm.other_directions_are_red()
            fsm.tick(3)
        assert sum(s == "GREEN" for s in fsm.direction_states.values()) == 2
        assert fsm.direction_states[direction] == "GREEN"
        assert fsm.other_directions_are_red()


def test_previous_hardware_state_remains_immutable():
    fsm = SignalFSM(DIRECTIONS)
    previous = fsm.state
    fsm.request_phase_change("SOUTH","change demand")
    assert previous.active_direction == "EW" and previous.color == PhaseColor.GREEN
    assert fsm.state.active_direction == "EW" and fsm.state.target_direction == "NS"
    assert fsm.state.color == PhaseColor.YELLOW
    fsm.tick(3)
    assert fsm.state.active_direction == "NS" and previous.color == PhaseColor.GREEN
    assert [(t.from_color,t.to_color) for t in fsm.history] == [(PhaseColor.GREEN,PhaseColor.YELLOW),(PhaseColor.YELLOW,PhaseColor.GREEN)]


def test_exact_yellow_boundary_and_full_new_green_timer():
    fsm = SignalFSM(DIRECTIONS)
    fsm.tick(70)
    fsm.request_phase_change("NS","timer elapsed")
    assert fsm.countdown_s == 3
    fsm.tick(2.99)
    assert fsm.state.color == PhaseColor.YELLOW
    assert fsm.direction_states["NORTH"] == "RED"
    fsm.tick(.01)
    assert fsm.state.color == PhaseColor.GREEN
    assert fsm.state.active_direction == "NS" and fsm.countdown_s == 70
    assert fsm.state.previous_phase == "EW" and fsm.state.target_direction is None


def test_late_processing_tick_does_not_consume_incoming_green():
    fsm = SignalFSM(DIRECTIONS)
    fsm.request_phase_change("NS","change")
    fsm.tick(10)
    assert fsm.state.active_direction == "NS" and fsm.countdown_s == 70


def test_repeated_or_forced_requests_and_mode_changes_cannot_bypass_yellow():
    fsm = SignalFSM(DIRECTIONS)
    fsm.request_phase_change("NORTH","early switch",protect_full_phase=True)
    fsm.tick(1)
    fsm.set_mode(SignalMode.MANUAL)
    for target in ["NORTH","SOUTH","EAST","WEST"]:
        assert not fsm.request_phase_change(target,"force",force=True)
    assert fsm.countdown_s == 2 and fsm.state.target_direction == "NS"
    fsm.tick(2)
    assert fsm.state.mode == SignalMode.MANUAL
    assert fsm.state.full_phase_required and fsm.countdown_s == 70


def test_configuration_update_cannot_shorten_yellow_in_progress():
    fsm = SignalFSM(DIRECTIONS)
    fsm.request_phase_change("NS","change")
    fsm._timings = replace(fsm._timings,yellow_s=1)
    fsm.tick(1)
    assert fsm.state.color == PhaseColor.YELLOW and fsm.countdown_s == 2
    fsm.tick(2)
    fsm.request_phase_change("EW","new setting")
    assert fsm.countdown_s == 1


def test_cancelled_emergency_finishes_yellow_and_resumes_previous_green_clock():
    fsm = SignalFSM(DIRECTIONS)
    fsm.tick(30)
    fsm.request_phase_change("NS","ambulance",action="EMERGENCY")
    fsm.tick(1)
    fsm.cancel_pending_emergency()
    assert fsm.state.color == PhaseColor.YELLOW and fsm.countdown_s == 2
    assert fsm.state.target_direction == "EW"
    fsm.tick(2)
    assert fsm.state.color == PhaseColor.GREEN and fsm.state.active_direction == "EW"
    assert fsm.countdown_s == 40 and fsm.state.previous_phase is None


def test_same_pair_request_never_restarts_green():
    fsm = SignalFSM(DIRECTIONS)
    fsm.tick(30)
    assert not fsm.request_phase_change("WEST","higher demand")
    assert fsm.state.elapsed_s == 30 and fsm.countdown_s == 40


def test_unknown_direction_preserves_state():
    fsm = SignalFSM(DIRECTIONS)
    previous = fsm.state
    with pytest.raises(ValueError):
        fsm.request_phase_change("NORTHWEST","invalid")
    assert fsm.state is previous


@pytest.mark.parametrize("directions", [["EAST","EAST"],["EAST","WEST"],DIRECTIONS+["EAST"]])
def test_invalid_direction_set_rejected(directions):
    with pytest.raises(ValueError):
        SignalFSM(directions)


@pytest.mark.parametrize("duration", [0,-1,float("nan"),float("inf")])
def test_invalid_yellow_duration_rejected(duration):
    with pytest.raises(ValueError):
        SignalFSM(DIRECTIONS,DomainConfig(signal_timings=SignalTimings(yellow_s=duration)))


def test_manual_request_between_live_ticks_gets_full_yellow_wall_time():
    now = [0.0]
    fsm = SignalFSM(DIRECTIONS,clock=lambda:now[0])
    now[0] = 30
    fsm.tick(30)
    now[0] = 30.19  # request arrives just before the next processing tick
    fsm.request_phase_change("NS","manual",force=True)
    now[0] = 30.2
    fsm.tick(.2)
    assert fsm.state.color == PhaseColor.YELLOW
    assert fsm.countdown_s == pytest.approx(2.99)
    now[0] = 33.18
    fsm.tick(100)  # caller dt cannot prematurely complete a live yellow interval
    assert fsm.state.color == PhaseColor.YELLOW
    now[0] = 33.19
    fsm.tick(0)
    assert fsm.state.color == PhaseColor.GREEN and fsm.countdown_s == 70
