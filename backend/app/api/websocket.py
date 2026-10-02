"""
WebSocket endpoint: /ws/intersections/{intersection_id}

Pushes the same IntersectionSnapshot data the REST layer exposes, on every
processed frame/tick, so the dashboard updates live without polling. Handles
disconnect/reconnect gracefully: a broken send silently drops that one
connection from the broadcast set rather than crashing the control loop.
"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.core.state import app_state

router = APIRouter()
logger = get_logger("dhaara.websocket")


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, intersection_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(intersection_id, []).append(websocket)

    def disconnect(self, intersection_id: str, websocket: WebSocket) -> None:
        if intersection_id in self._connections and websocket in self._connections[intersection_id]:
            self._connections[intersection_id].remove(websocket)

    async def broadcast(self, intersection_id: str, payload: dict) -> None:
        stale: list[WebSocket] = []
        for ws in self._connections.get(intersection_id, []):
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(intersection_id, ws)


connection_manager = ConnectionManager()


def snapshot_to_payload(intersection_id: str, controller) -> dict:
    snapshot = controller.last_snapshot
    if snapshot is None:
        return {"intersection_id": intersection_id, "status": "NO_DATA"}
    return {
        "intersection_id": intersection_id,
        "frame_index": snapshot.frame_index,
        "timestamp": snapshot.timestamp,
        "demand": snapshot.demand,
        "score_records": snapshot.score_records,
        "is_simulated": snapshot.is_simulated,
        "signal": {
            "state": snapshot.signal_state,
            "active_direction": snapshot.signal_active_direction,
            "target_direction": getattr(snapshot, "signal_target_direction", None),
            "countdown_s": snapshot.signal_countdown_s,
            "mode": getattr(snapshot, "signal_mode", "ADAPTIVE"),
            "directions": snapshot.direction_signals,
        },
        "decision": (
            {
                "selected_direction": snapshot.decision.selected_direction,
                "green_duration_s": snapshot.decision.green_duration_s,
                "reason": snapshot.decision.reason,
                "mode": snapshot.decision.mode,
                "traffic_pressure": snapshot.decision.traffic_pressure,
                "queue_length_m": snapshot.decision.queue_length_m,
                "waiting_time_s": snapshot.decision.waiting_time_s,
                "vehicle_count": snapshot.decision.vehicle_count,
                "fairness_applied": snapshot.decision.fairness_applied,
                "action": snapshot.decision.action,
                "pair_scores": snapshot.decision.pair_scores,
                "denser_pair": snapshot.decision.denser_pair,
                "score_difference": snapshot.decision.score_difference,
            }
            if snapshot.decision
            else None
        ),
        "emergency": {
            "state": snapshot.emergency_state,
            "direction": snapshot.emergency_direction,
            "active_track_id": controller.emergency_manager.active_track_id,
            "active_lane_id": controller.emergency_manager.active_lane_id,
            "flashing_lights_confirmed": snapshot.ambulance_lights.get(controller.emergency_manager.active_track_id, False),
            "visible_ambulances": len(snapshot.ambulance_lights),
        },
        "safety": getattr(snapshot, "safety_summary", {
            "compliant_count": controller.helmet_analyzer.compliant_count,
            "violation_count": controller.helmet_analyzer.violation_count,
            "compliance_rate": controller.helmet_analyzer.compliance_rate,
        }),
        "cameras": snapshot.camera_statuses,
        "lanes": {
            lane_id: {
                "vehicle_count": m.vehicle_count,
                "vehicle_score": m.vehicle_score,
                "vehicle_counts": m.vehicle_counts,
                "density": m.vehicle_count,
                "occupancy": m.occupancy,
                "queue_length_m": m.queue_length_m,
                "average_speed_kmph": m.average_speed_kmph,
                "average_waiting_time_s": m.average_waiting_time_s,
                "flow_rate": m.flow_rate,
                "traffic_pressure": m.traffic_pressure,
                "status": m.status.value,
                "reasons": m.reasons,
            }
            for lane_id, m in snapshot.lane_metrics.items()
        },
    }


@router.websocket("/ws/intersections/{intersection_id}")
async def intersection_ws(websocket: WebSocket, intersection_id: str):
    runtime = app_state.get(intersection_id)
    if runtime is None:
        await websocket.close(code=4404)
        return

    await connection_manager.connect(intersection_id, websocket)
    logger.info(f"WebSocket connected for {intersection_id}")
    try:
        # Send current state immediately on connect, then wait for the
        # background control loop to push further updates via broadcast().
        with runtime.lock:
            payload = snapshot_to_payload(intersection_id, runtime.controller)
            if runtime.simulation_lab is not None:
                payload["simulation"] = runtime.simulation_lab.metadata()
        await websocket.send_json(payload)
        while True:
            # We don't expect inbound messages, but awaiting receive lets us
            # detect disconnects promptly rather than only on the next send.
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {intersection_id}")
    finally:
        connection_manager.disconnect(intersection_id, websocket)
