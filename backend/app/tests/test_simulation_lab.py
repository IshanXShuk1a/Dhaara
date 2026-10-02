"""Educational scenarios exercise the same scoring and signal rules as cameras."""
from __future__ import annotations

import pytest

from app.core.domain_config import DEFAULT_CONFIG
from app.services.simulation.lab import create_simulation_runtime


@pytest.mark.parametrize("scenario,scores", [
    ("balanced", {"EW":16,"NS":16}),
    ("ns_busy", {"EW":8,"NS":36}),
    ("ew_busy", {"EW":36,"NS":8}),
    ("empty_ew", {"EW":4,"NS":36}),
    ("empty_ns", {"EW":36,"NS":4}),
])
def test_scenarios_keep_replenished_demand_and_score_from_detections(scenario, scores):
    runtime = create_simulation_runtime(DEFAULT_CONFIG)
    lab = runtime.simulation_lab
    lab.reset(runtime, scenario)
    assert runtime.controller.last_snapshot.demand["pair_scores"] == scores
    lab.step(runtime, 55)
    assert runtime.controller.last_snapshot.demand["pair_scores"] == scores
    assert runtime.controller.last_snapshot.is_simulated


@pytest.mark.parametrize("scenario,outgoing,incoming", [("empty_ew","EW","NS"),("empty_ns","NS","EW")])
def test_empty_green_demonstration_has_yellow_and_full_receiving_phase(scenario, outgoing, incoming):
    runtime = create_simulation_runtime(DEFAULT_CONFIG)
    lab = runtime.simulation_lab
    lab.reset(runtime, scenario)
    assert runtime.controller.last_snapshot.signal_countdown_s == 40
    assert runtime.controller.last_snapshot.signal_active_direction == outgoing
    lab.step(runtime, 3.0)
    snapshot = runtime.controller.last_snapshot
    assert snapshot.signal_state == "YELLOW" and snapshot.signal_target_direction == incoming
    assert snapshot.signal_countdown_s == 3
    lab.step(runtime, 2.8)
    assert runtime.controller.last_snapshot.signal_state == "YELLOW"
    lab.step(runtime, .2)
    snapshot = runtime.controller.last_snapshot
    assert snapshot.signal_state == "GREEN" and snapshot.signal_active_direction == incoming
    assert snapshot.signal_countdown_s == 70
    assert snapshot.demand["full_phase_required"]
    lab.step(runtime, 69.8)
    assert runtime.controller.last_snapshot.signal_state == "GREEN"
    lab.step(runtime, .2)
    assert runtime.controller.last_snapshot.signal_state == "YELLOW"
    assert runtime.controller.last_snapshot.signal_target_direction == outgoing


def test_virtual_speed_and_pause_do_not_need_real_camera_capture():
    runtime = create_simulation_runtime(DEFAULT_CONFIG)
    lab = runtime.simulation_lab
    lab.speed = 5
    lab.step(runtime, 1)
    assert runtime.controller.last_snapshot.signal_countdown_s == 65
    lab.paused = True
    snapshot = lab.step(runtime, 20)
    assert snapshot.signal_countdown_s == 65 and lab.simulated_time_s == pytest.approx(5)
    assert all(c.path == "" for c in runtime.cameras.values())
    with pytest.raises(ValueError, match="cannot restart live video"):
        runtime.restart_video_inputs()
    assert runtime.is_simulated and runtime.controller.last_snapshot is snapshot


@pytest.mark.parametrize("lights_active,priority", [(False,False),(True,True)])
def test_simulated_ambulance_requires_actual_flashing_pixel_evidence(monkeypatch, lights_active, priority):
    import app.services.simulation.lab as lab_module
    import app.services.controllers.intersection_controller as controller_module
    clock = [100.0]
    monkeypatch.setattr(lab_module.time,"monotonic",lambda:clock[0])
    monkeypatch.setattr(controller_module.time,"time",lambda:clock[0])
    runtime = create_simulation_runtime(DEFAULT_CONFIG)
    lab = runtime.simulation_lab
    lab.spawn_ambulance(runtime,"NORTH",lights_active)
    for _ in range(12):
        clock[0] += .2
        lab.step(runtime,.2)
    snapshot = runtime.controller.last_snapshot
    assert bool(snapshot.signal_target_direction == "NS") == priority
    assert any(snapshot.ambulance_lights.values()) == priority
    assert snapshot.demand["pair_scores"] == {"EW":16,"NS":16}  # outside measurement ROI
    if priority:
        assert snapshot.signal_state == "YELLOW" and snapshot.decision.action == "YELLOW"
    else:
        assert snapshot.signal_state == "GREEN" and snapshot.signal_active_direction == "EW"
