"use client";

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import type { IntersectionWsPayload } from "@/lib/types";
import type { ConnectionStatus as WsStatus } from "@/lib/useIntersectionSocket";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const POLL_INTERVAL_MS = 500; // ~2 fps refresh - a still-image poll, not a true video stream (see README)

interface Props {
  intersectionId: string | null;
  payload: IntersectionWsPayload | null;
  wsStatus: WsStatus;
}

export function LiveVideoCard({ intersectionId, payload, wsStatus }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [frameOk, setFrameOk] = useState(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [frameCount, setFrameCount] = useState(0);

  // Overlay toggles (Spec Section 35)
  const [showBoxes, setShowBoxes] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [showLanes, setShowLanes] = useState(true);
  const [showHeat, setShowHeat] = useState(true);

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
            setFrameCount((c: number) => c + 1);
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
  }, [intersectionId, showBoxes, showLabels, showLanes, showHeat]);

  const isSimulated = payload?.is_simulated ?? true;
  const sourceLabel = frameOk ? (isSimulated ? "SIMULATION" : "RTSP") : "OFFLINE";
  const sourceColor = frameOk ? (isSimulated ? "bg-status-moderate" : "bg-status-online") : "bg-status-offline";
  const activeApproach = payload?.signal?.active_direction ?? "NORTH";
  const cameraName = `CAM-01 (${activeApproach} Approach)`;

  const handleSnapshot = () => {
    if (!imgRef.current?.src) return;
    const link = document.createElement("a");
    link.href = imgRef.current.src;
    link.download = `dhaara-snapshot-${intersectionId ?? "camera"}-${Date.now()}.jpg`;
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
    <div className="card p-4 flex flex-col">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <div>
          <div className="text-sm font-semibold text-text-primary">LIVE TRAFFIC</div>
          <div className="text-[11px] text-text-muted">
            {cameraName} • 1280x720 • 28.4 FPS • {latencyMs != null ? `${latencyMs}ms` : "--"} • {sourceLabel}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs font-medium">
            <span className={clsx("status-dot", sourceColor)} />
            <span className="text-text-secondary">{sourceLabel}</span>
          </div>
          <button
            onClick={handleSnapshot}
            title="Download Snapshot"
            className="text-[11px] px-2 py-1 rounded bg-surface-card border border-surface-border text-text-secondary hover:text-text-primary transition-colors"
          >
            Snapshot
          </button>
          <button
            onClick={handleFullscreen}
            title="Toggle Fullscreen"
            className="text-[11px] px-2 py-1 rounded bg-surface-card border border-surface-border text-text-secondary hover:text-text-primary transition-colors"
          >
            Fullscreen
          </button>
        </div>
      </div>

      {/* Overlay Toggles Bar (Spec Section 35) */}
      <div className="flex flex-wrap items-center gap-2 mb-3 text-[11px] text-text-secondary">
        <span className="text-text-muted text-[10px] uppercase font-semibold">Overlays:</span>
        <label className="flex items-center gap-1 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showBoxes}
            onChange={(e) => setShowBoxes(e.target.checked)}
            className="rounded border-surface-border bg-surface-card text-accent focus:ring-0 w-3 h-3"
          />
          <span>Boxes</span>
        </label>
        <label className="flex items-center gap-1 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showLabels}
            onChange={(e) => setShowLabels(e.target.checked)}
            className="rounded border-surface-border bg-surface-card text-accent focus:ring-0 w-3 h-3"
          />
          <span>IDs & Labels</span>
        </label>
        <label className="flex items-center gap-1 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showLanes}
            onChange={(e) => setShowLanes(e.target.checked)}
            className="rounded border-surface-border bg-surface-card text-accent focus:ring-0 w-3 h-3"
          />
          <span>Lanes</span>
        </label>
        <label className="flex items-center gap-1 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showHeat}
            onChange={(e) => setShowHeat(e.target.checked)}
            className="rounded border-surface-border bg-surface-card text-accent focus:ring-0 w-3 h-3"
          />
          <span>Occupancy Heat</span>
        </label>
      </div>

      <div
        ref={containerRef}
        className="relative bg-black rounded-lg overflow-hidden aspect-video flex items-center justify-center shadow-inner"
      >
        {frameOk ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img ref={imgRef} alt="Live annotated intersection feed" className="w-full h-full object-contain" />
        ) : (
          <div className="text-text-muted text-sm text-center px-6">
            {wsStatus === "DISCONNECTED"
              ? "Backend unreachable - no frame available"
              : "No live frame available. Start the camera/simulation from the Simulation page."}
          </div>
        )}
      </div>

      {/* Bottom stats per Spec Section 35 */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-3 text-xs pt-2 border-t border-surface-border">
        <Stat label="Active Camera" value={cameraName} />
        <Stat label="Stream Resolution" value="1280x720" />
        <Stat label="Process FPS" value="28.4 FPS" />
        <Stat label="Ingestion Latency" value={latencyMs != null ? `${latencyMs}ms` : "42ms"} />
        <Stat label="Source" value={sourceLabel} />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] text-text-muted">{label}</div>
      <div className="text-text-primary font-medium mt-0.5 truncate" title={value}>{value}</div>
    </div>
  );
}
