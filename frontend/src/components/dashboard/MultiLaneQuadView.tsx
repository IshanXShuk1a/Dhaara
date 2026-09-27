"use client";

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import type { IntersectionWsPayload, LaneMetrics } from "@/lib/types";
import type { ConnectionStatus as WsStatus } from "@/lib/useIntersectionSocket";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const POLL_INTERVAL_MS = 600;

interface Props {
  intersectionId: string | null;
  payload: IntersectionWsPayload | null;
  wsStatus: WsStatus;
}

const DIRECTIONS = [
  { direction: "NORTH", camId: "CAM-01", label: "North Approach" },
  { direction: "SOUTH", camId: "CAM-02", label: "South Approach" },
  { direction: "EAST", camId: "CAM-03", label: "East Approach" },
  { direction: "WEST", camId: "CAM-04", label: "West Approach" },
] as const;

export function MultiLaneQuadView({ intersectionId, payload, wsStatus }: Props) {
  // Global overlay toggles
  const [showBoxes, setShowBoxes] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [showLanes, setShowLanes] = useState(true);
  const [showHeat, setShowHeat] = useState(true);

  // View mode: "quad" (4 screens) or "composite" (single master camera)
  const [viewMode, setViewMode] = useState<"quad" | "composite">("quad");

  const lanes = payload?.lanes ?? {};
  const activeSignalDirection = payload?.signal?.active_direction;
  const signalState = payload?.signal?.state ?? "GREEN";
  const countdown = payload?.signal?.countdown_seconds ?? 0;
  const decision = payload?.decision;

  // Calculate density rankings across all 4 lanes
  const laneEntries = Object.entries(lanes);
  const sortedByDensity = [...laneEntries].sort((a, b) => b[1].traffic_pressure - a[1].traffic_pressure);
  const highestDensityLane = sortedByDensity[0]?.[0];

  return (
    <div className="space-y-4">
      {/* Master Traffic Allotment Hub Banner */}
      <div className="card-interactive card p-4 relative overflow-hidden group">
        {/* Subtle dynamic background shimmer sweep */}
        <div className="absolute inset-0 pointer-events-none opacity-30 animate-shimmer" />

        <div className="relative z-10 flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-accent flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                AI Traffic Density Evaluation & Lane Allotment
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-accent/20 text-accent border border-accent/30 shadow-sm">
                {payload?.signal_mode ?? "ADAPTIVE"}
              </span>
            </div>
            <div className="text-xs text-text-secondary flex flex-wrap items-center gap-2">
              <span className="flex items-center gap-1">
                <span>Calculated highest density lane:</span>
                <span className="font-semibold text-text-primary">
                  {highestDensityLane ? (
                    <>
                      <span>{highestDensityLane} (</span>
                      <AnimatedNumber value={lanes[highestDensityLane]?.traffic_pressure ?? 0} decimals={1} suffix="%" />
                      <span>)</span>
                    </>
                  ) : "--"}
                </span>
              </span>
              <span>•</span>
              <span className="text-emerald-500 dark:text-emerald-400 font-medium flex items-center gap-1">
                <span>Active Green Allotment:</span>
                <span className="font-bold underline decoration-emerald-500/50 flex items-center gap-1">
                  <span>{activeSignalDirection ?? "--"} (</span>
                  <AnimatedNumber value={countdown} decimals={0} suffix="s" />
                  <span>remaining)</span>
                </span>
              </span>
            </div>
          </div>

          {/* Quick Density Mini-Gauges for all 4 lanes */}
          <div className="glass-pill flex items-center gap-3 text-xs p-2 shadow-inner">
            {DIRECTIONS.map(({ direction }) => {
              const m = lanes[direction];
              const pressure = m?.traffic_pressure ?? 0;
              const isAllotted = activeSignalDirection === direction && signalState === "GREEN";
              return (
                <div key={direction} className="text-center px-1.5 transition-all">
                  <div className="text-[10px] text-text-muted font-medium">{direction}</div>
                  <div
                    className={clsx(
                      "font-mono font-bold text-xs mt-0.5",
                      isAllotted
                        ? "text-emerald-500 dark:text-emerald-400"
                        : pressure >= 80
                        ? "text-status-congested"
                        : pressure >= 40
                        ? "text-status-moderate"
                        : "text-text-secondary"
                    )}
                  >
                    <AnimatedNumber value={pressure} decimals={0} suffix="%" />
                  </div>
                  <div className="relative flex items-center justify-center w-2 h-2 mx-auto mt-1.5">
                    <span
                      className={clsx(
                        "w-2 h-2 rounded-full",
                        isAllotted ? "bg-status-online" : "bg-text-muted/30"
                      )}
                    />
                    {isAllotted && (
                      <span className="absolute inset-0 rounded-full bg-status-online animate-ping opacity-75" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* View Mode Controls & Toggles */}
          <div className="flex items-center gap-2">
            <div className="glass-pill p-1 flex items-center gap-1 text-xs">
              <button
                onClick={() => setViewMode("quad")}
                className={clsx(
                  "btn-tactile px-2.5 py-1 rounded-lg text-xs font-medium transition-all",
                  viewMode === "quad"
                    ? "bg-accent text-white shadow-md"
                    : "text-text-muted hover:text-text-primary"
                )}
              >
                4-Screen Quad View
              </button>
              <button
                onClick={() => setViewMode("composite")}
                className={clsx(
                  "btn-tactile px-2.5 py-1 rounded-lg text-xs font-medium transition-all",
                  viewMode === "composite"
                    ? "bg-accent text-white shadow-md"
                    : "text-text-muted hover:text-text-primary"
                )}
              >
                Single Master Feed
              </button>
            </div>
          </div>
        </div>

        {/* Overlay Checkbox Bar */}
        <div className="flex flex-wrap items-center gap-4 mt-3 pt-3 border-t border-surface-border text-[11px] text-text-secondary">
          <span className="text-text-muted uppercase font-semibold text-[10px]">CCTV Overlays:</span>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={showBoxes}
              onChange={(e) => setShowBoxes(e.target.checked)}
              className="rounded border-surface-border bg-surface-card text-accent focus:ring-0 w-3.5 h-3.5"
            />
            <span>Vehicle Bounding Boxes</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={showLabels}
              onChange={(e) => setShowLabels(e.target.checked)}
              className="rounded border-surface-border bg-surface-card text-accent focus:ring-0 w-3.5 h-3.5"
            />
            <span>Track IDs & Velocity</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={showLanes}
              onChange={(e) => setShowLanes(e.target.checked)}
              className="rounded border-surface-border bg-surface-card text-accent focus:ring-0 w-3.5 h-3.5"
            />
            <span>Lane ROI Boundaries</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={showHeat}
              onChange={(e) => setShowHeat(e.target.checked)}
              className="rounded border-surface-border bg-surface-card text-accent focus:ring-0 w-3.5 h-3.5"
            />
            <span>Occupancy Heatmap</span>
          </label>
        </div>
      </div>

      {/* 4 SEPARATE LANE SCREENS (Quad View) */}
      {viewMode === "quad" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {DIRECTIONS.map(({ direction, camId, label }) => {
            const laneMetrics = lanes[direction] ?? null;
            const isAllotted = activeSignalDirection === direction && signalState === "GREEN";
            const isYellow = activeSignalDirection === direction && signalState === "YELLOW";
            const isEmergency = payload?.emergency?.state !== "NONE" && payload?.emergency?.direction === direction;

            return (
              <LaneCameraCard
                key={direction}
                camId={camId}
                direction={direction}
                label={label}
                intersectionId={intersectionId}
                metrics={laneMetrics}
                isAllotted={isAllotted}
                isYellow={isYellow}
                isEmergency={isEmergency}
                countdown={countdown}
                decision={decision}
                wsStatus={wsStatus}
                showBoxes={showBoxes}
                showLabels={showLabels}
                showLanes={showLanes}
                showHeat={showHeat}
              />
            );
          })}
        </div>
      ) : (
        /* Composite Overview Screen */
        <div className="card p-4">
          <div className="text-sm font-semibold text-text-primary mb-2">MASTER COMPOSITE INTERSECTION FEED</div>
          <CompositeScreen
            intersectionId={intersectionId}
            wsStatus={wsStatus}
            showBoxes={showBoxes}
            showLabels={showLabels}
            showLanes={showLanes}
            showHeat={showHeat}
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------
// INDIVIDUAL LANE CAMERA SCREEN (CCTV + Density Calculation + Allotment)
// ---------------------------------------------------------------------------------

interface LaneCameraCardProps {
  camId: string;
  direction: string;
  label: string;
  intersectionId: string | null;
  metrics: LaneMetrics | null;
  isAllotted: boolean;
  isYellow: boolean;
  isEmergency: boolean;
  countdown: number;
  decision: IntersectionWsPayload["decision"];
  wsStatus: WsStatus;
  showBoxes: boolean;
  showLabels: boolean;
  showLanes: boolean;
  showHeat: boolean;
}

function LaneCameraCard({
  camId,
  direction,
  label,
  intersectionId,
  metrics,
  isAllotted,
  isYellow,
  isEmergency,
  countdown,
  decision,
  wsStatus,
  showBoxes,
  showLabels,
  showLanes,
  showHeat,
}: LaneCameraCardProps) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [frameOk, setFrameOk] = useState(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);

  useEffect(() => {
    if (!intersectionId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    function token(): string | null {
      return typeof window !== "undefined" ? window.localStorage.getItem("dhaara_token") : null;
    }

    async function poll() {
      const start = performance.now();
      try {
        const t = token();
        const query = new URLSearchParams({
          intersection_id: intersectionId!,
          direction,
          show_boxes: String(showBoxes),
          show_labels: String(showLabels),
          show_lanes: String(showLanes),
          show_heat: String(showHeat),
        });
        if (t) query.set("token", t);

        const response = await fetch(`${API_BASE}/api/video/frame?${query.toString()}`, {
          headers: t ? { Authorization: `Bearer ${t}` } : {},
          cache: "no-store",
        });

        if (!response.ok) {
          if (!cancelled) setFrameOk(false);
        } else {
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          if (imgRef.current && !cancelled) {
            const previous = imgRef.current.src;
            imgRef.current.src = url;
            if (previous.startsWith("blob:")) URL.revokeObjectURL(previous);
          }
          if (!cancelled) {
            setFrameOk(true);
            setLatencyMs(Math.round(performance.now() - start));
          }
        }
      } catch {
        if (!cancelled) setFrameOk(false);
      } finally {
        if (!cancelled) timer = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [intersectionId, direction, showBoxes, showLabels, showLanes, showHeat]);

  const pressure = metrics?.traffic_pressure ?? 0;
  const status = metrics?.status ?? "FREE";
  const vehicleCount = metrics?.vehicle_count ?? 0;
  const queueLength = metrics?.queue_length_m ?? 0;
  const waitingTime = metrics?.average_waiting_time_s ?? 0;
  const averageSpeed = metrics?.average_speed_kmph ?? 0;

  // Allotment card style
  const cardBorderClass = isEmergency
    ? "ring-2 ring-status-emergency/70 shadow-2xl shadow-red-500/20"
    : isAllotted
    ? "ring-2 ring-emerald-500/70 shadow-2xl shadow-emerald-500/20"
    : isYellow
    ? "ring-1 ring-amber-500/60"
    : "border border-surface-border";

  return (
    <div
      className={clsx(
        "card-interactive relative rounded-2xl transition-all duration-300 overflow-hidden group/card flex flex-col justify-between",
        cardBorderClass
      )}
    >
      {/* Animated Glowing Conic Border Beam for Active Allotment & Emergency */}
      {isEmergency ? (
        <div className="border-beam-emergency" />
      ) : isAllotted ? (
        <div className="border-beam" />
      ) : null}

      {/* Inner Content Container */}
      <div className="card relative z-10 m-[1px] p-4 flex flex-col justify-between h-full rounded-2xl border-0 shadow-none">
        {/* Screen Header matching My Courses card header */}
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2.5">
            <div className="relative">
              <div
                className={clsx(
                  "w-8 h-8 rounded-full border flex items-center justify-center font-bold text-xs transition-colors",
                  isAllotted
                    ? "bg-emerald-500 text-white border-emerald-400"
                    : isEmergency
                    ? "bg-red-600 text-white border-red-500"
                    : "bg-surface-pill border-surface-border text-text-primary"
                )}
              >
                {direction.charAt(0)}
              </div>
              {isAllotted && (
                <span className="beacon-ring border border-emerald-400" />
              )}
              {isEmergency && (
                <span className="beacon-ring border border-red-500" />
              )}
            </div>
            <div>
              <div className="text-xs font-bold text-text-primary flex items-center gap-1.5">
                <span>{direction} Approach</span>
                <span className="text-[10px] text-text-muted">({camId})</span>
              </div>
              <div
                className={clsx(
                  "text-[10px] capitalize font-medium flex items-center gap-1",
                  isEmergency
                    ? "text-red-400 font-bold"
                    : isAllotted
                    ? "text-emerald-400 font-semibold"
                    : "text-text-muted"
                )}
              >
                {isEmergency ? (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
                    <span>Emergency Corridor Priority</span>
                  </>
                ) : isAllotted ? (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    <span>Signal Phase Allotted</span>
                  </>
                ) : (
                  status.toLowerCase()
                )}
              </div>
            </div>
          </div>

          <button className="text-text-muted hover:text-text-primary text-xs btn-tactile p-1">•••</button>
        </div>

        {/* Screen Video Feed (Cropped & Oriented to this Lane) */}
        <div
          ref={containerRef}
          className="relative bg-black rounded-xl overflow-hidden aspect-[16/9] flex items-center justify-center shadow-inner group/video border border-surface-border mb-3 select-none"
        >
          {frameOk ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              ref={imgRef}
              alt={`${direction} approach feed`}
              className="w-full h-full object-cover transition-transform duration-700 ease-out group-hover/video:scale-105"
            />
          ) : (
            <div className="text-text-muted text-xs text-center px-4">
              {wsStatus === "DISCONNECTED" ? "Backend unreachable" : `Connecting to ${camId}...`}
            </div>
          )}

          {/* High-Tech Optical Laser Scanline Beam */}
          <div className="animate-scanline" />

          {/* CRT Scanline Micro-Pattern Overlay */}
          <div className="absolute inset-0 cctv-scanlines opacity-40 pointer-events-none" />

          {/* Holographic HUD Reticle Corners */}
          <div className="absolute top-2 left-2 text-[10px] font-mono text-cyan-400/70 select-none pointer-events-none">┌</div>
          <div className="absolute top-2 right-2 text-[10px] font-mono text-cyan-400/70 select-none pointer-events-none">┐</div>
          <div className="absolute bottom-2 left-2 text-[10px] font-mono text-cyan-400/70 select-none pointer-events-none">└</div>
          <div className="absolute bottom-2 right-2 text-[10px] font-mono text-cyan-400/70 select-none pointer-events-none">┘</div>

          {/* Live Telemetry Pill with Jumping Stream Visualizer */}
          <div className="absolute top-2.5 left-3 px-2 py-0.5 rounded-full bg-black/80 backdrop-blur-md text-[10px] text-text-secondary font-mono flex items-center gap-1.5 border border-white/10 shadow-lg">
            <div className="relative flex items-center justify-center w-2 h-2">
              <span className="w-1.5 h-1.5 rounded-full bg-status-online" />
              <span className="absolute inset-0 rounded-full bg-status-online animate-ping opacity-75" />
            </div>
            <span>LIVE • {latencyMs != null ? `${latencyMs}ms` : "42ms"}</span>
            {/* 4-Bar Audio/Video Stream Activity Visualizer */}
            <div className="flex items-end gap-0.5 h-3 ml-1">
              <span className="w-0.5 bg-cyan-400 eq-bar-1 rounded-full" />
              <span className="w-0.5 bg-cyan-400 eq-bar-2 rounded-full" />
              <span className="w-0.5 bg-cyan-400 eq-bar-3 rounded-full" />
              <span className="w-0.5 bg-cyan-400 eq-bar-4 rounded-full" />
            </div>
          </div>

          {/* Emergency Priority Overlay Banner */}
          {isEmergency && (
            <div className="absolute bottom-2 right-2 px-2.5 py-1 rounded-lg bg-red-600/90 backdrop-blur-sm text-[10px] font-bold text-white flex items-center gap-1.5 shadow-lg animate-pulse border border-red-400/50">
              <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
              <span>AMBULANCE DETECTED</span>
            </div>
          )}
        </div>

        {/* Stats Row matching 68 Lessons / Sparkline / 30 day left from mockup */}
        <div className="space-y-2">
          <div className="flex items-end justify-between">
            <div>
              <div className="text-base font-extrabold text-text-primary flex items-baseline gap-1">
                <AnimatedNumber value={vehicleCount} className="tabular-nums font-extrabold" />
                <span className="text-xs font-semibold text-text-secondary">Vehicles</span>
              </div>
              <div className="text-[11px] text-text-muted flex items-center gap-1.5">
                <span>Queue:</span>
                <AnimatedNumber value={queueLength} decimals={0} suffix="m" className="text-text-secondary font-medium" />
                <span>• Speed:</span>
                <AnimatedNumber value={averageSpeed} decimals={0} suffix=" km/h" className="text-text-secondary font-medium" />
              </div>
            </div>

            {/* Mini Density Gauge Sparkline with animated gradient fill */}
            <div className="text-right">
              <div
                className={clsx(
                  "text-xs font-mono font-bold flex items-center justify-end gap-0.5",
                  pressure >= 80 ? "text-status-congested" : pressure >= 40 ? "text-amber-400" : "text-emerald-400"
                )}
              >
                <AnimatedNumber value={pressure} decimals={1} suffix="%" />
                <span>Density</span>
              </div>
              <div className="w-20 h-1.5 bg-surface-pill rounded-full mt-1 overflow-hidden relative border border-surface-border">
                <div
                  className={clsx(
                    "h-full transition-all duration-700 ease-out rounded-full relative",
                    pressure >= 80 ? "bg-status-congested" : pressure >= 40 ? "bg-amber-400" : "bg-emerald-400"
                  )}
                  style={{ width: `${Math.min(100, Math.max(5, pressure))}%` }}
                >
                  <div className="absolute inset-0 animate-shimmer" />
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Tag with Clock Icon matching mockup (e.g. 30 day left -> 48s Allotted Green) */}
          <div className="pt-2 border-t border-surface-border flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-1.5">
              <svg
                className={clsx(
                  "w-3.5 h-3.5 transition-colors",
                  isAllotted ? "text-emerald-400 animate-spin" : "text-text-muted"
                )}
                style={isAllotted ? { animationDuration: "10s" } : undefined}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className={clsx(isAllotted ? "text-emerald-400 font-bold flex items-center gap-1" : "text-text-muted flex items-center gap-1")}>
                {isAllotted ? (
                  <>
                    <AnimatedNumber value={countdown} decimals={0} suffix="s" className="font-extrabold" />
                    <span>Allotted Green Phase</span>
                  </>
                ) : (
                  <>
                    <span>Waiting in Queue (</span>
                    <AnimatedNumber value={waitingTime} decimals={0} suffix="s" />
                    <span>)</span>
                  </>
                )}
              </span>
            </div>

            {isAllotted && (
              <div className="relative flex items-center justify-center w-2.5 h-2.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-80" />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------
// COMPOSITE SCREEN (SINGLE FULL OVERVIEW)
// ---------------------------------------------------------------------------------

function CompositeScreen({
  intersectionId,
  wsStatus,
  showBoxes,
  showLabels,
  showLanes,
  showHeat,
}: {
  intersectionId: string | null;
  wsStatus: WsStatus;
  showBoxes: boolean;
  showLabels: boolean;
  showLanes: boolean;
  showHeat: boolean;
}) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [frameOk, setFrameOk] = useState(false);

  useEffect(() => {
    if (!intersectionId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    function token(): string | null {
      return typeof window !== "undefined" ? window.localStorage.getItem("dhaara_token") : null;
    }

    async function poll() {
      try {
        const t = token();
        const query = new URLSearchParams({
          intersection_id: intersectionId!,
          show_boxes: String(showBoxes),
          show_labels: String(showLabels),
          show_lanes: String(showLanes),
          show_heat: String(showHeat),
        });
        if (t) query.set("token", t);

        const response = await fetch(`${API_BASE}/api/video/frame?${query.toString()}`, {
          headers: t ? { Authorization: `Bearer ${t}` } : {},
          cache: "no-store",
        });

        if (response.ok && !cancelled) {
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          if (imgRef.current) {
            const prev = imgRef.current.src;
            imgRef.current.src = url;
            if (prev.startsWith("blob:")) URL.revokeObjectURL(prev);
          }
          setFrameOk(true);
        }
      } catch {
        if (!cancelled) setFrameOk(false);
      } finally {
        if (!cancelled) timer = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [intersectionId, showBoxes, showLabels, showLanes, showHeat]);

  return (
    <div className="relative bg-black rounded-xl overflow-hidden aspect-video flex items-center justify-center border border-surface-border shadow-inner group">
      {frameOk ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img ref={imgRef} alt="Master intersection feed" className="w-full h-full object-contain" />
      ) : (
        <div className="text-text-muted text-sm text-center px-4">
          {wsStatus === "DISCONNECTED" ? "Backend unreachable" : "Loading master camera feed..."}
        </div>
      )}

      {/* Optical Scanline & CRT Effect */}
      <div className="animate-scanline" />
      <div className="absolute inset-0 cctv-scanlines opacity-40 pointer-events-none" />

      {/* Live Badge */}
      <div className="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-black/80 backdrop-blur-md text-[11px] text-text-secondary font-mono flex items-center gap-2 border border-white/10 shadow-lg">
        <span className="w-2 h-2 rounded-full bg-status-online animate-ping" />
        <span>MASTER 360° SENSOR STREAM</span>
      </div>
    </div>
  );
}
