"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useAuth } from "@/lib/auth";
import { RoiEditor } from "./RoiEditor";
import clsx from "clsx";
import type { IntersectionWsPayload } from "@/lib/types";
import type { ConnectionStatus as WsStatus } from "@/lib/useIntersectionSocket";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const DIRECTIONS = ["EAST", "WEST", "NORTH", "SOUTH"] as const;
type Direction = typeof DIRECTIONS[number];
interface Props {
  intersectionId: string | null;
  payload: IntersectionWsPayload | null;
  wsStatus: WsStatus;
}
interface Overlays { show_boxes: boolean; show_labels: boolean; show_lanes: boolean; show_heat: boolean }

export function MultiLaneQuadView({ intersectionId, payload, wsStatus }: Props) {
  const [view, setView] = useState<"MASTER" | Direction>("MASTER");
  const [fullscreen, setFullscreen] = useState(false);
  const [overlays, setOverlays] = useState<Overlays>({ show_boxes: true, show_labels: true, show_lanes: true, show_heat: false });
  const containerRef = useRef<HTMLDivElement>(null);
  const visible = view === "MASTER" ? DIRECTIONS : [view];
  useEffect(() => {
    const update = () => setFullscreen(document.fullscreenElement === containerRef.current);
    document.addEventListener("fullscreenchange", update);
    return () => document.removeEventListener("fullscreenchange", update);
  }, []);
  return (
    <section ref={containerRef} aria-label="Directional cameras" className="card min-w-0 bg-surface-card p-3 space-y-2.5 [&:fullscreen]:overflow-y-auto [&:fullscreen]:bg-surface-canvas [&:fullscreen]:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-text-primary">Directional cameras</h2>
          <div className="text-[11px] text-text-muted">Vehicles counted only inside the marked boundary</div>
        </div>
        <button onClick={() => {
          if (fullscreen) document.exitFullscreen?.().catch(() => {});
          else containerRef.current?.requestFullscreen?.().catch(() => {});
        }} aria-label={fullscreen ? "Exit camera fullscreen" : "Open camera fullscreen"}
          className="btn-tactile inline-flex items-center gap-1.5 rounded-lg border border-surface-border px-2.5 py-1.5 text-[11px] text-text-secondary">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M1.5 6V1.5H6M10 1.5h4.5V6M14.5 10v4.5H10M6 14.5H1.5V10" /></svg>
          {fullscreen ? "Exit fullscreen" : "Fullscreen"}
        </button>
      </div>
      <div role="tablist" aria-label="Camera views" className="flex gap-1 overflow-x-auto rounded-lg bg-surface-panel p-1 text-[11px]">
        {(["MASTER", ...DIRECTIONS] as const).map((direction) => (
          <button key={direction} role="tab" aria-selected={view === direction} onClick={() => setView(direction)}
            className={clsx("btn-tactile flex-1 rounded-md px-2 py-1.5 whitespace-nowrap", view === direction ? "bg-accent/15 text-accent font-semibold" : "text-text-muted hover:text-text-primary")}>
            {direction === "MASTER" ? "All four" : direction.charAt(0) + direction.slice(1).toLowerCase()}
          </button>
        ))}
      </div>
      <div className={clsx("grid gap-2.5", view === "MASTER" ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-1")}>
        {visible.map((direction) => <CameraPanel key={`${intersectionId}:${direction}`} direction={direction}
          compact={view === "MASTER"} intersectionId={intersectionId} payload={payload} wsStatus={wsStatus} overlays={overlays} />)}
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-surface-border pt-2 text-[11px] text-text-secondary">
        <span className="text-text-muted">Overlay</span>
        {([["show_boxes", "Vehicle boxes"], ["show_labels", "Labels"], ["show_lanes", "Counted area"]] as const).map(([key, label]) => (
          <label key={key} className="flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" checked={overlays[key]} onChange={e => setOverlays(v => ({ ...v, [key]: e.target.checked }))} className="accent-accent" />
            {label}
          </label>
        ))}
      </div>
    </section>
  );
}

function CameraPanel({ direction, compact, intersectionId, payload, wsStatus, overlays }: Props & {direction: Direction; compact: boolean; overlays: Overlays}) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [frameOk, setFrameOk] = useState(false);
  const { role } = useAuth();
  const [editing, setEditing] = useState(false);
  const synthetic = Boolean(payload?.is_simulated);
  const metrics = !synthetic && payload?.cameras?.[direction]?.status === "ONLINE" ? payload?.lanes?.[direction] : undefined;
  const signal = !synthetic ? payload?.signal?.directions?.[direction] : undefined;
  const camera = !synthetic ? payload?.cameras?.[direction] : undefined;
  useEffect(() => {
    if (!intersectionId || synthetic) {
      setFrameOk(false);
      if (imgRef.current) imgRef.current.removeAttribute("src");
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let currentUrl: string | null = null;
    const controller = new AbortController();
    setFrameOk(false);
    async function poll() {
      try {
        const query = new URLSearchParams({ intersection_id: intersectionId!, direction,
          ...Object.fromEntries(Object.entries(overlays).map(([key, value]) => [key, String(value)])) });
        const token = window.localStorage.getItem("dhaara_token");
        const response = await fetch(`${API_BASE}/api/video/frame?${query}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {}, cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error("Camera unavailable");
        const blob = await response.blob();
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        if (imgRef.current) imgRef.current.src = url;
        if (currentUrl) URL.revokeObjectURL(currentUrl);
        currentUrl = url;
        setFrameOk(true);
      } catch {
        if (!cancelled) setFrameOk(false);
      } finally {
        if (!cancelled) timer = setTimeout(poll, 500);
      }
    }
    poll();
    return () => { cancelled = true; clearTimeout(timer); controller.abort(); if (currentUrl) URL.revokeObjectURL(currentUrl); };
  }, [intersectionId, direction, overlays, synthetic]);

  function snapshot() {
    if (!frameOk || !imgRef.current?.src) return;
    const link = document.createElement("a");
    link.href = imgRef.current.src;
    link.download = `dhaara-${direction.toLowerCase()}-${Date.now()}.jpg`;
    link.click();
  }
  const signalClass = signal === "GREEN" ? "text-status-free" : signal === "YELLOW" ? "text-status-moderate" : signal === "RED" ? "text-status-congested" : "text-text-muted";
  const count = metrics?.vehicle_count;
  const imageStyle = {"--camera-image-height": compact ? "clamp(116px, calc((100dvh - 480px) / 2), 240px)" : "clamp(240px, 54dvh, 620px)"} as CSSProperties;
  return (
    <article className="min-w-0 overflow-hidden rounded-xl border border-surface-border bg-surface-panel" data-camera-direction={direction}>
      <div className="flex items-center justify-between gap-2 px-3 py-1.5 text-[11px]">
        <span className="flex items-center gap-2 font-semibold text-text-primary"><span className="grid h-5 w-5 place-items-center rounded-md bg-accent/10 text-[10px] text-accent">{direction[0]}</span>{direction.charAt(0) + direction.slice(1).toLowerCase()}</span>
        <span className={clsx("font-semibold flex items-center gap-1.5", signalClass)}>
          <span className={clsx("w-1.5 h-1.5 rounded-full", signal === "GREEN" ? "bg-status-free" : signal === "YELLOW" ? "bg-status-moderate" : signal === "RED" ? "bg-status-congested" : "bg-text-muted")} />
          {signal ?? "Awaiting signal"}
        </span>
      </div>
      <div style={imageStyle} className={clsx("relative bg-[#071018] overflow-hidden flex items-center justify-center", compact ? "aspect-video md:aspect-auto md:h-[var(--camera-image-height)]" : "h-[var(--camera-image-height)]")}>
        {/* Keep mounted while loading so the first frame can be assigned. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img ref={imgRef} alt={`${direction} independent camera`} className={clsx("w-full h-full object-contain", !frameOk && "hidden")} />
        {!frameOk && <div className="flex flex-col items-center gap-2 px-4 text-center text-[11px] text-slate-400">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true"><rect x="2" y="6" width="14" height="12" rx="2" /><path d="m16 10 6-3v10l-6-3" /></svg>
          {synthetic ? "Real camera input required" : wsStatus === "DISCONNECTED" ? "Backend unreachable" : camera?.status === "OFFLINE" ? `${direction} camera offline` : `Loading ${direction.toLowerCase()} camera...`}
        </div>}
      </div>
      <div className="space-y-1 px-3 py-1.5">
        <div className="flex items-center justify-between gap-2 text-[11px]">
          <span className="text-text-secondary"><strong className="tabular-nums font-semibold text-text-primary">{count ?? "—"}</strong> vehicles in counted area</span>
          <span className="text-text-muted">Score <strong className="ml-1 text-sm tabular-nums text-accent">{metrics?.vehicle_score ?? "—"}</strong></span>
        </div>
        <div className="flex items-center justify-between gap-2 text-[10px] text-text-muted">
          <span className="truncate" title={payload?.demand?.rickshaw_supported === false ? "The loaded detector does not classify auto-rickshaws separately." : undefined}>
            Cars {metrics?.vehicle_counts?.car ?? (metrics ? 0 : "—")} <span aria-hidden="true">·</span> Autos {payload?.demand?.rickshaw_supported === false ? "—" : metrics?.vehicle_counts?.rickshaw ?? (metrics ? 0 : "—")} <span aria-hidden="true">·</span> Bikes {metrics ? (metrics.vehicle_counts?.motorcycle ?? 0) + (metrics.vehicle_counts?.bicycle ?? 0) : "—"}
          </span>
          <div className="flex flex-shrink-0 items-center gap-2">
            <button onClick={snapshot} disabled={!frameOk} className="btn-tactile rounded-sm text-text-secondary hover:text-accent disabled:opacity-40" title={`Save ${direction.toLowerCase()} camera snapshot`} aria-label={`Save ${direction.toLowerCase()} camera snapshot`}>
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true"><path d="M8 1v9m-3-3 3 3 3-3M2 11v3h12v-3" /></svg>
            </button>
            {role === "ADMIN" && <button onClick={() => setEditing(true)} disabled={!frameOk} className="btn-tactile rounded-sm text-accent disabled:opacity-40" aria-label={`Set ${direction.toLowerCase()} 30 ft boundary`} title="Set 30 ft measurement boundary">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true"><path d="M1.5 5.5h13v5h-13zM4 5.5v2.5m3-2.5v4m3-4v2.5" /></svg>
            </button>}
          </div>
        </div>
      </div>
      {editing && intersectionId && <RoiEditor intersectionId={intersectionId} direction={direction} onClose={() => setEditing(false)} />}
    </article>
  );
}
