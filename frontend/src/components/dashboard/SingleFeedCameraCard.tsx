"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import type { IntersectionWsPayload } from "@/lib/types";
import type { ConnectionStatus as WsStatus } from "@/lib/useIntersectionSocket";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const POLL_INTERVAL_MS = 500;

interface Props {
  intersectionId: string | null;
  payload: IntersectionWsPayload | null;
  wsStatus: WsStatus;
}

const APPROACH_OPTIONS = [
  { key: "AUTO", label: "Auto (Allotted Green)", camId: "AUTO" },
  { key: "NORTH", label: "North (CAM-01)", camId: "CAM-01" },
  { key: "SOUTH", label: "South (CAM-02)", camId: "CAM-02" },
  { key: "EAST", label: "East (CAM-03)", camId: "CAM-03" },
  { key: "WEST", label: "West (CAM-04)", camId: "CAM-04" },
  { key: "COMPOSITE", label: "Master 360°", camId: "CAM-MASTER" },
];

export function SingleFeedCameraCard({ intersectionId, payload, wsStatus }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  const [selectedApproach, setSelectedApproach] = useState<string>("AUTO");
  const [frameOk, setFrameOk] = useState(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);

  // Overlay toggles
  const [showBoxes, setShowBoxes] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [showLanes, setShowLanes] = useState(true);
  const [showHeat, setShowHeat] = useState(true);

  const lanes = payload?.lanes ?? {};
  const activeDirection = payload?.signal?.active_direction ?? "NORTH";
  const signalState = payload?.signal?.state ?? "GREEN";
  const countdown = Math.round(payload?.signal?.countdown_seconds ?? payload?.signal?.countdown_s ?? 0);
  const emergency = payload?.emergency;
  const isEmergency = emergency && emergency.state !== "NONE";

  // If AUTO is selected, follow the active allotted lane (or emergency lane)
  const effectiveDirection =
    selectedApproach === "AUTO"
      ? (isEmergency && emergency?.direction ? emergency.direction : activeDirection)
      : selectedApproach;

  const currentLaneMetrics = lanes[effectiveDirection] ?? null;
  const pressure = currentLaneMetrics?.traffic_pressure ?? 0;
  const vehicleCount = currentLaneMetrics?.vehicle_count ?? 0;
  const queueLength = currentLaneMetrics?.queue_length_m ?? 0;
  const averageSpeed = currentLaneMetrics?.average_speed_kmph ?? 0;

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
          show_boxes: String(showBoxes),
          show_labels: String(showLabels),
          show_lanes: String(showLanes),
          show_heat: String(showHeat),
        });
        if (effectiveDirection !== "COMPOSITE") {
          query.set("direction", effectiveDirection);
        }
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
  }, [intersectionId, effectiveDirection, showBoxes, showLabels, showLanes, showHeat]);

  const handleSnapshot = () => {
    if (!imgRef.current?.src) return;
    const link = document.createElement("a");
    link.href = imgRef.current.src;
    link.download = `dhaara-snapshot-${effectiveDirection}-${Date.now()}.jpg`;
    link.click();
  };

  const handleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen?.().catch(() => {});
    } else {
      document.exitFullscreen?.().catch(() => {});
    }
  };

  return (
    <div className="card-interactive card p-4 relative overflow-hidden group space-y-3.5">
      {/* Dynamic Border Glow on Active Green or Emergency */}
      {isEmergency ? (
        <div className="border-beam-emergency" />
      ) : signalState === "GREEN" ? (
        <div className="border-beam" />
      ) : null}

      {/* Top Header: Title, Telemetry, and Actions */}
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-accent flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
              LIVE CCTV STREAM • {effectiveDirection === "COMPOSITE" ? "360° MASTER FEED" : `${effectiveDirection} APPROACH`}
            </span>
            {isEmergency ? (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-500 border border-rose-500/30 animate-pulse">
                EMERGENCY PRIORITY ACTIVE
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-500 border border-emerald-500/30">
                ALLOTTED GREEN: {activeDirection} ({countdown}s)
              </span>
            )}
          </div>
          <div className="text-[11px] text-text-muted flex items-center gap-2">
            <span>HD Ingestion</span>
            <span>•</span>
            <span>28.4 FPS</span>
            <span>•</span>
            <span className="font-mono text-text-secondary">{latencyMs != null ? `${latencyMs}ms` : "38ms"} Latency</span>
          </div>
        </div>

        {/* Action Controls & Link to Image Classifier */}
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/classify"
            className="btn-tactile px-3 py-1.5 rounded-xl bg-gradient-to-r from-accent to-purple-600 text-white font-medium text-xs flex items-center gap-1.5 shadow-sm hover:opacity-95"
            title="Classify custom traffic images using AI"
          >
            <span>📸</span>
            <span>Classify Image</span>
          </Link>
          <button
            onClick={handleSnapshot}
            title="Download Snapshot"
            className="btn-tactile text-xs px-2.5 py-1.5 rounded-xl bg-surface-pill border border-surface-border text-text-secondary hover:text-text-primary transition-colors"
          >
            Snapshot
          </button>
          <button
            onClick={handleFullscreen}
            title="Toggle Fullscreen"
            className="btn-tactile text-xs px-2.5 py-1.5 rounded-xl bg-surface-pill border border-surface-border text-text-secondary hover:text-text-primary transition-colors"
          >
            Fullscreen
          </button>
        </div>
      </div>

      {/* Approach Selector Tabs */}
      <div className="relative z-10 flex items-center justify-between gap-2 overflow-x-auto pb-1">
        <div className="glass-pill p-1 flex items-center gap-1 text-xs">
          {APPROACH_OPTIONS.map((opt) => {
            const isSelected = selectedApproach === opt.key;
            return (
              <button
                key={opt.key}
                onClick={() => setSelectedApproach(opt.key)}
                className={clsx(
                  "btn-tactile px-3 py-1 rounded-lg text-xs font-medium transition-all whitespace-nowrap",
                  isSelected
                    ? "bg-accent/15 text-accent border border-accent/30 shadow-sm font-semibold"
                    : "text-text-muted hover:text-text-primary"
                )}
              >
                {opt.label}
              </button>
            );
          })}
        </div>

        {/* Real-time Density Badge for Selected Approach */}
        {effectiveDirection !== "COMPOSITE" && (
          <div className="glass-pill px-3 py-1 text-xs flex items-center gap-2 shrink-0">
            <span className="text-[10px] text-text-muted uppercase">Approach Density:</span>
            <span
              className={clsx(
                "font-mono font-bold text-xs flex items-center gap-1",
                pressure >= 75 ? "text-status-congested" : pressure >= 40 ? "text-status-moderate" : "text-status-free"
              )}
            >
              <AnimatedNumber value={pressure} decimals={1} suffix="%" />
            </span>
          </div>
        )}
      </div>

      {/* Single Live Video Camera Viewport */}
      <div
        ref={containerRef}
        className="relative bg-background-secondary rounded-2xl overflow-hidden aspect-[16/9] flex items-center justify-center shadow-inner group/video border border-surface-border hover:border-accent/25 transition-colors duration-300 select-none"
      >
        {frameOk ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            ref={imgRef}
            alt="Live intersection camera feed"
            className="w-full h-full object-contain transition-transform duration-700 ease-out group-hover/video:scale-[1.01]"
          />
        ) : (
          <div className="text-text-muted text-xs text-center px-4 space-y-1">
            <div className="font-semibold text-sm">
              {wsStatus === "DISCONNECTED" ? "Backend Unreachable" : `Connecting to ${effectiveDirection} feed...`}
            </div>
            <div className="text-[11px] text-text-muted">Ensure backend simulation or RTSP stream is running.</div>
          </div>
        )}

        {/* High-Tech Optical Laser Scanline Beam */}
        <div className="animate-scanline" />

        {/* Authentic CRT Scanline Pattern Overlay */}
        <div className="absolute inset-0 cctv-scanlines opacity-40 pointer-events-none" />

        {/* Holographic HUD Reticle Corners */}
        <div className="absolute top-2.5 left-2.5 text-xs font-mono text-accent/35 select-none pointer-events-none">┌</div>
        <div className="absolute top-2.5 right-2.5 text-xs font-mono text-accent/35 select-none pointer-events-none">┐</div>
        <div className="absolute bottom-2.5 left-2.5 text-xs font-mono text-accent/35 select-none pointer-events-none">└</div>
        <div className="absolute bottom-2.5 right-2.5 text-xs font-mono text-accent/35 select-none pointer-events-none">┘</div>

        {/* Live Telemetry Pill with Jumping Stream Visualizer */}
        <div className="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-surface/90 backdrop-blur-md text-[10px] text-text-primary font-mono flex items-center gap-1.5 border border-surface-border shadow-lg">
          <div className="relative flex items-center justify-center w-2 h-2">
            <span className="w-1.5 h-1.5 rounded-full bg-status-online status-dot" />
          </div>
          <span>LIVE • {latencyMs != null ? `${latencyMs}ms` : "38ms"}</span>
          <div className="flex items-end gap-0.5 h-3 ml-1.5">
            <span className="w-0.5 bg-accent/70 eq-bar-1 rounded-full" />
            <span className="w-0.5 bg-accent/70 eq-bar-2 rounded-full" />
            <span className="w-0.5 bg-accent/70 eq-bar-3 rounded-full" />
            <span className="w-0.5 bg-accent/70 eq-bar-4 rounded-full" />
          </div>
        </div>

        {/* Emergency Overlay Alert */}
        {isEmergency && (
          <div className="absolute bottom-3 right-3 px-3 py-1 rounded-lg bg-rose-600/95 backdrop-blur-sm text-xs font-bold text-white flex items-center gap-2 shadow-xl animate-pulse border border-rose-400/50">
            <span className="w-2 h-2 rounded-full bg-white animate-ping" />
            <span>AMBULANCE DETECTED ({emergency?.direction ?? "WEST"})</span>
          </div>
        )}
      </div>

      {/* Bottom Live Metrics & Overlay Controls */}
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-3 pt-1">
        {/* Real-time Telemetry Metrics */}
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <div>
            <span className="text-text-muted text-[10px] uppercase block">Vehicles</span>
            <span className="font-extrabold text-sm text-text-primary flex items-center gap-1">
              <AnimatedNumber value={vehicleCount} decimals={0} />
              <span className="text-[10px] text-text-muted font-normal">units</span>
            </span>
          </div>
          <div className="h-6 w-px bg-surface-border" />
          <div>
            <span className="text-text-muted text-[10px] uppercase block">Queue</span>
            <span className="font-extrabold text-sm text-text-primary flex items-center gap-1">
              <AnimatedNumber value={queueLength} decimals={0} suffix="m" />
            </span>
          </div>
          <div className="h-6 w-px bg-surface-border" />
          <div>
            <span className="text-text-muted text-[10px] uppercase block">Avg Speed</span>
            <span className="font-extrabold text-sm text-text-primary flex items-center gap-1">
              <AnimatedNumber value={averageSpeed} decimals={0} suffix=" km/h" />
            </span>
          </div>
        </div>

        {/* Overlay Checkboxes */}
        <div className="flex flex-wrap items-center gap-3 text-[11px] text-text-secondary">
          <label className="flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showBoxes}
              onChange={(e) => setShowBoxes(e.target.checked)}
              className="rounded border-surface-border bg-surface-card text-accent focus:ring-0 w-3.5 h-3.5"
            />
            <span>Bounding Boxes</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showLabels}
              onChange={(e) => setShowLabels(e.target.checked)}
              className="rounded border-surface-border bg-surface-card text-accent focus:ring-0 w-3.5 h-3.5"
            />
            <span>Labels & IDs</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showLanes}
              onChange={(e) => setShowLanes(e.target.checked)}
              className="rounded border-surface-border bg-surface-card text-accent focus:ring-0 w-3.5 h-3.5"
            />
            <span>Lanes</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showHeat}
              onChange={(e) => setShowHeat(e.target.checked)}
              className="rounded border-surface-border bg-surface-card text-accent focus:ring-0 w-3.5 h-3.5"
            />
            <span>Heatmap</span>
          </label>
        </div>
      </div>
    </div>
  );
}
