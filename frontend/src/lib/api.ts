// Central API client. Every network call the dashboard makes goes through
// here so there is exactly one place that attaches auth headers and one
// place that defines "what does a failed request look like" - components
// must render that failure state (see ApiError) rather than a component
// inventing placeholder numbers when a fetch fails.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("dhaara_token");
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem("dhaara_token", token);
  else window.localStorage.removeItem("dhaara_token");
}

export function getStoredRole(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("dhaara_role");
}

export function setStoredRole(role: string | null) {
  if (typeof window === "undefined") return;
  if (role) window.localStorage.setItem("dhaara_role", role);
  else window.localStorage.removeItem("dhaara_role");
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  params?: Record<string, string | number | undefined>;
  isForm?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = getToken();
  let url = `${API_BASE}${path}`;
  if (options.params) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(options.params)) {
      if (value !== undefined) query.set(key, String(value));
    }
    const qs = query.toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!options.isForm && options.body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method || "GET",
      headers,
      body: options.isForm ? (options.body as FormData) : options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch (networkError) {
    throw new ApiError("Cannot reach DHAARA backend - is it running?", 0);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errBody = await response.json();
      detail = errBody.detail || detail;
    } catch {
      /* body wasn't JSON - keep statusText */
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; role: string }>("/api/auth/login", {
      method: "POST",
      body: { username, password },
    }),

  me: () => request<{ username: string; role: string }>("/api/auth/me"),

  health: () => request<{ status: string; intersections_online: string[]; intersection_count: number }>("/api/health"),

  listIntersections: () => request<import("./types").Intersection[]>("/api/intersections"),

  getTraffic: (intersectionId: string) =>
    request<{
      intersection_id: string;
      timestamp?: string;
      is_simulated?: boolean;
      lanes: Record<string, import("./types").LaneMetrics>;
      note?: string;
    }>(`/api/intersections/${intersectionId}/traffic`),

  getTrafficHistory: (intersectionId: string) =>
    request<{ intersection_id: string; volume: unknown[]; average_pressure_by_lane: Record<string, number | null> }>(
      `/api/intersections/${intersectionId}/traffic/history`
    ),

  getSignal: (intersectionId: string) => request<import("./types").SignalState>(`/api/intersections/${intersectionId}/signal`),

  setSignalMode: (intersectionId: string, mode: string) =>
    request(`/api/intersections/${intersectionId}/signal/mode`, { method: "POST", body: { mode } }),

  overrideSignal: (intersectionId: string, direction: string, operatorNote = "") =>
    request(`/api/intersections/${intersectionId}/signal/override`, {
      method: "POST",
      body: { direction, operator_note: operatorNote },
    }),

  getEmergency: (intersectionId: string) => request<import("./types").EmergencySummary>(`/api/intersections/${intersectionId}/emergency`),

  getSafety: (intersectionId: string) => request<import("./types").SafetySummary>(`/api/intersections/${intersectionId}/safety`),

  getAnalytics: (intersectionId: string) =>
    request<{
      intersection_id: string;
      volume: unknown[];
      average_pressure_by_lane: Record<string, number | null>;
      signal_distribution: Record<string, number>;
      emergency_events_24h: number;
      helmet_violations_24h: number;
    }>(`/api/analytics/${intersectionId}`),

  listEvents: (intersectionId?: string) =>
    request<import("./types").SystemEvent[]>(intersectionId ? `/api/events/${intersectionId}` : "/api/events"),

  startVideo: (intersectionId: string) => request(`/api/video/start`, { method: "POST", params: { intersection_id: intersectionId } }),
  stopVideo: (intersectionId: string) => request(`/api/video/stop`, { method: "POST", params: { intersection_id: intersectionId } }),
  videoStatus: (intersectionId: string) => request(`/api/video/status`, { params: { intersection_id: intersectionId } }),

  setSimulationTraffic: (intersectionId: string, sliders: { north: number; south: number; east: number; west: number }) =>
    request(`/api/simulation/traffic`, { method: "POST", params: { intersection_id: intersectionId }, body: sliders }),

  spawnAmbulance: (intersectionId: string, direction: string) =>
    request(`/api/simulation/ambulance`, { method: "POST", params: { intersection_id: intersectionId }, body: { direction } }),

  spawnHelmetViolation: (intersectionId: string, direction: string) =>
    request(`/api/simulation/helmet-violation`, {
      method: "POST",
      params: { intersection_id: intersectionId },
      body: { direction },
    }),

  resetSimulation: (intersectionId: string) => request(`/api/simulation/reset`, { method: "POST", params: { intersection_id: intersectionId } }),

  listAllEmergencies: () => request<Array<Record<string, unknown>>>("/api/emergency"),
  listAllSafetyEvents: () => request<Array<Record<string, unknown>>>("/api/safety"),
  getConfig: () =>
    request<{
      detection: Record<string, number>;
      signal_timings: Record<string, number>;
      fairness: Record<string, number>;
      lane_thresholds: Record<string, number>;
      pressure_weights: Record<string, number>;
    }>("/api/config"),
  updateConfig: (data: unknown) =>
    request<{
      status: string;
      detection: Record<string, number>;
      signal_timings: Record<string, number>;
      fairness: Record<string, number>;
      lane_thresholds: Record<string, number>;
      pressure_weights: Record<string, number>;
    }>("/api/config", { method: "PUT", body: data }),
  updateLanes: (intersectionId: string, lanes: unknown[]) =>
    request<import("./types").LaneMetrics[]>(`/api/intersections/${intersectionId}/lanes`, {
      method: "PUT",
      body: lanes,
    }),
  getRegionalAnalytics: () =>
    request<{
      total_snapshots: number;
      total_decisions: number;
      total_emergencies_24h: number;
      total_helmet_violations_24h: number;
      average_network_pressure: number;
      average_network_speed_kmph: number;
    }>("/api/analytics"),
  classifyImage: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<import("./types").TrafficClassificationResult>("/api/classifier/classify", {
      method: "POST",
      body: formData,
      isForm: true,
    });
  },
  getClassifierPresets: () =>
    request<import("./types").ClassifierPreset[]>("/api/classifier/presets"),
  classifyPreset: (presetId: string) =>
    request<import("./types").TrafficClassificationResult>(`/api/classifier/classify-preset/${presetId}`, {
      method: "POST",
    }),
  classifyQuadImages: (files: File[], labels?: string[]) => {
    const formData = new FormData();
    files.forEach((file, index) => {
      formData.append(`file${index + 1}`, file);
      if (labels && labels[index]) {
        formData.append(`label${index + 1}`, labels[index]);
      }
    });
    return request<import("./types").QuadClassificationResult>("/api/classifier/classify-quad", {
      method: "POST",
      body: formData,
      isForm: true,
    });
  },
  getQuadClassifierPresets: () =>
    request<import("./types").ClassifierPreset[]>("/api/classifier/quad-presets"),
  classifyQuadPreset: (presetId: string) =>
    request<import("./types").QuadClassificationResult>(`/api/classifier/classify-quad-preset/${presetId}`, {
      method: "POST",
    }),
};

export function wsBase(): string {
  const httpBase = API_BASE;
  return httpBase.replace(/^http/, "ws");
}
