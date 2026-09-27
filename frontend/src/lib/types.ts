// Types mirror the backend's Pydantic schemas (app/schemas/*.py) field-for-
// field. Keeping them hand-in-sync (rather than any partial subset) means a
// component either has the real field or doesn't compile - no silent
// fallback to an invented shape.

export type LaneStatus = "FREE" | "LOW" | "MODERATE" | "HIGH" | "CONGESTED";
export type SignalColor = "GREEN" | "YELLOW" | "ALL_RED";
export type SignalMode = "FIXED" | "ADAPTIVE" | "MANUAL" | "EMERGENCY";
export type EmergencyState =
  | "NONE"
  | "DETECTED"
  | "CONFIRMED"
  | "PRIORITY_REQUESTED"
  | "PRIORITY_ACTIVE"
  | "PASSED"
  | "RESOLVED";
export type UserRole = "ADMIN" | "TRAFFIC_OPERATOR" | "VIEWER";

export interface LaneMetrics {
  vehicle_count: number;
  occupancy: number;
  queue_length_m: number;
  average_speed_kmph: number;
  average_waiting_time_s: number;
  flow_rate?: number;
  traffic_pressure: number;
  status: LaneStatus;
  reasons?: string[];
}

export interface SignalDecision {
  selected_direction: string;
  green_duration_s: number;
  reason: string[];
  mode: string;
  traffic_pressure?: number;
  queue_length_m?: number;
  waiting_time_s?: number;
  vehicle_count?: number;
  fairness_applied?: boolean;
}

export interface SignalState {
  intersection_id: string;
  color: SignalColor;
  active_direction: string;
  target_direction: string | null;
  countdown_s: number;
  mode: SignalMode;
  decision: SignalDecision | null;
}

export interface EmergencySummary {
  intersection_id: string;
  state: EmergencyState;
  active_direction: string | null;
  active_lane_id: string | null;
  active_track_id: number | null;
  recent_events: Array<{
    ambulance_track_id: number;
    lane_id: string;
    direction: string | null;
    confidence: number;
    state: string;
    timestamp: number;
  }>;
}

export interface SafetySummary {
  intersection_id: string;
  compliant_count: number;
  violation_count: number;
  compliance_rate: number | null; // null -> UI must show "N/A"
}

export interface Intersection {
  id: string;
  name: string;
  location: string;
  status: string;
  created_at: string;
}

export interface SystemEvent {
  intersection_id: string | null;
  event_type: string;
  message: string;
  severity: "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  timestamp: string;
}

// WebSocket payload shape - see app/api/websocket.py:snapshot_to_payload
export interface IntersectionWsPayload {
  intersection_id: string;
  status?: "NO_DATA";
  frame_index?: number;
  is_simulated?: boolean;
  signal?: {
    state: SignalColor;
    active_direction: string;
    target_direction?: string | null;
    countdown_s: number;
    mode?: string;
  };
  decision?: {
    selected_direction: string;
    green_duration_s: number;
    reason: string[];
    mode: string;
    traffic_pressure?: number;
    queue_length_m?: number;
    waiting_time_s?: number;
    vehicle_count?: number;
    fairness_applied?: boolean;
  } | null;
  emergency?: {
    state: EmergencyState;
    direction: string | null;
    active_track_id?: number | null;
    active_lane_id?: string | null;
  };
  safety?: {
    compliant_count: number;
    violation_count: number;
    compliance_rate: number | null;
  };
  lanes?: Record<
    string,
    {
      vehicle_count: number;
      occupancy: number;
      queue_length_m: number;
      average_speed_kmph: number;
      average_waiting_time_s: number;
      flow_rate?: number;
      traffic_pressure: number;
      status: LaneStatus;
      reasons?: string[];
    }
  >;
}
