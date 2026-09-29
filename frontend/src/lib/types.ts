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

export interface DetectedVehicleItem {
  class: string;
  confidence: number;
  bbox: [number, number, number, number];
}

export interface TrafficClassificationResult {
  success: boolean;
  filename: string;
  classification: {
    code: "FREE_FLOW" | "MODERATE" | "HEAVY" | "GRIDLOCK" | "EMERGENCY_PRIORITY";
    label: string;
    severity: "INFO" | "LOW" | "MODERATE" | "HIGH" | "CRITICAL";
    badge_color: "emerald" | "amber" | "orange" | "rose" | "red";
    density_percentage: number;
    total_vehicles: number;
    vehicle_counts: Record<string, number>;
    emergency_detected: boolean;
    helmet_compliance: {
      compliant: number;
      violations: number;
      total_two_wheelers: number;
    };
    safety_alerts: string[];
    recommended_green_s: number;
    ai_reasoning: string;
    latency_ms: number;
    approach_breakdown?: Record<string, { queue_length_m: number; status: string; vehicles: number }>;
  };
  video_metadata?: {
    duration_s: number;
    total_frames: number;
    fps: number;
    width: number;
    height: number;
    sampled_frames: number;
    approach_queues: Record<string, number>;
  };
  detections: DetectedVehicleItem[];
  annotated_image: string;
  image_dimensions: { width: number; height: number };
}

export interface ClassifierPreset {
  id: string;
  title: string;
  description: string;
  expected_state: string;
  icon: string;
}

export interface QuadApproachResult {
  index: number;
  label: string;
  filename: string;
  rank: number;
  relative_traffic_level: "EMERGENCY_CORRIDOR" | "CRITICAL_DOMINANT" | "ELEVATED_DEMAND" | "BALANCED_NORMAL" | "SUBORDINATE_LIGHT";
  relative_status_label: string;
  relative_badge_color: "red" | "rose" | "orange" | "amber" | "emerald";
  relative_share_percentage: number;
  recommended_green_s: number;
  density_percentage: number;
  total_vehicles: number;
  vehicle_counts: Record<string, number>;
  emergency_detected: boolean;
  safety_alerts: string[];
  classification_code: string;
  classification_label: string;
  annotated_image: string;
  detections: DetectedVehicleItem[];
  image_dimensions: { width: number; height: number };
}

export interface QuadClassificationResult {
  success: boolean;
  mode: "QUAD_COMPARATIVE";
  timestamp: number;
  latency_ms: number;
  comparative_summary: {
    overall_code: "EMERGENCY_PREEMPTION" | "ASYMMETRIC_BOTTLENECK" | "UNIFORM_GRIDLOCK" | "TIDAL_ARTERIAL_SURGE" | "BALANCED_MODERATE" | "FREE_FLOW_ALL";
    overall_label: string;
    overall_severity: "INFO" | "LOW" | "MODERATE" | "HIGH" | "CRITICAL";
    overall_badge_color: "red" | "rose" | "orange" | "amber" | "emerald";
    ai_recommendation: string;
    imbalance_percentage: number;
    total_intersection_vehicles: number;
    average_density_percentage: number;
    highest_demand_approach: string;
    highest_demand_share: number;
    emergency_active: boolean;
    cycle_length_s: number;
  };
  approaches: QuadApproachResult[];
}


