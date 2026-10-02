"""
EventBus

A minimal in-process publish/subscribe bus for the backend-internal events
listed in the spec (VEHICLE_DETECTED, LANE_STATUS_CHANGED, SIGNAL_CHANGED,
AMBULANCE_DETECTED, EMERGENCY_PRIORITY_REQUESTED, EMERGENCY_RESOLVED,
HELMET_VIOLATION, CAMERA_OFFLINE, MODEL_ERROR, MANUAL_OVERRIDE, ...).

Subscribers are plain callables; the WebSocket manager and the
system-events persistence layer both subscribe to this bus rather than
being called directly by every service, keeping services decoupled from
transport/persistence concerns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable


class EventType(str, Enum):
    VEHICLE_DETECTED = "VEHICLE_DETECTED"
    LANE_STATUS_CHANGED = "LANE_STATUS_CHANGED"
    TRAFFIC_LEVEL_CHANGED = "TRAFFIC_LEVEL_CHANGED"
    SIGNAL_CHANGED = "SIGNAL_CHANGED"
    DECISION_MADE = "DECISION_MADE"
    AMBULANCE_DETECTED = "AMBULANCE_DETECTED"
    EMERGENCY_PRIORITY_REQUESTED = "EMERGENCY_PRIORITY_REQUESTED"
    EMERGENCY_RESOLVED = "EMERGENCY_RESOLVED"
    HELMET_VIOLATION = "HELMET_VIOLATION"
    CAMERA_OFFLINE = "CAMERA_OFFLINE"
    MODEL_ERROR = "MODEL_ERROR"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    CONFIGURATION_CHANGED = "CONFIGURATION_CHANGED"
    SYSTEM_STARTUP = "SYSTEM_STARTUP"


@dataclass(frozen=True)
class Event:
    type: EventType
    intersection_id: str | None
    message: str
    severity: str = "INFO"
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self):
        self._subscribers: list[Subscriber] = []

    def subscribe(self, subscriber: Subscriber) -> None:
        self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: Subscriber) -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    def publish(self, event: Event) -> None:
        for subscriber in self._subscribers:
            subscriber(event)


event_bus = EventBus()
