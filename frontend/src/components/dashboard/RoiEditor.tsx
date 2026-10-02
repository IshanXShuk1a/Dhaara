"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { LaneConfig } from "@/lib/types";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function RoiEditor({intersectionId, direction, onClose}: {intersectionId: string; direction: string; onClose: () => void}) {
  const [lanes, setLanes] = useState<LaneConfig[]>([]);
  const [points, setPoints] = useState<number[][]>([]);
  const [frame, setFrame] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);
  useEffect(() => {
    let cancelled = false; let url: string | null = null;
    const abort = new AbortController();
    const token = window.localStorage.getItem("dhaara_token");
    Promise.all([api.getLanes(intersectionId), fetch(`${API_BASE}/api/video/frame?intersection_id=${encodeURIComponent(intersectionId)}&direction=${direction}&show_lanes=false&show_boxes=false&show_labels=false&show_heat=false`,
      {headers: token ? {Authorization: `Bearer ${token}`} : {}, signal: abort.signal}).then(async r => { if (!r.ok) throw new Error("Camera frame unavailable"); return r.blob(); })])
      .then(([configured, blob]) => {
        if (cancelled) return;
        setLanes(configured); setPoints(configured.find(l => l.direction === direction)?.polygon ?? []);
        url = URL.createObjectURL(blob); setFrame(url);
      }).catch(err => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; abort.abort(); if (url) URL.revokeObjectURL(url); };
  }, [intersectionId, direction]);
  async function save() {
    setSaving(true); setError(null);
    try {
      await api.updateLanes(intersectionId, lanes.map(l => ({...l, polygon: l.direction === direction ? points : l.polygon,
        length_m: l.direction === direction ? 9.144 : l.length_m})));
      onClose();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save ROI"); }
    finally { setSaving(false); }
  }
  return <div role="dialog" aria-modal="true" aria-label={`${direction} measurement boundary`} className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
    <div className="card bg-surface-panel p-4 space-y-3 w-full max-w-3xl max-h-[calc(100dvh-2rem)] overflow-y-auto">
      <div className="flex items-center justify-between gap-3"><strong className="text-sm">{direction} measurement boundary</strong><button onClick={onClose} className="btn-tactile rounded-lg border border-surface-border px-3 py-1.5 text-xs">Close</button></div>
      <p className="text-xs text-text-muted">Mark the far edge 30 ft (9.144 m) from the signal. Click four corners: far-left, far-right, near-right, near-left.</p>
      {frame && <div className="relative mx-auto w-fit max-w-full">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={frame} alt={`${direction} ROI calibration`} className="block max-h-[58dvh] w-auto max-w-full" />
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 w-full h-full cursor-crosshair" onClick={e => {
          if (points.length >= 4) return;
          const bounds = e.currentTarget.getBoundingClientRect();
          setPoints(p => [...p, [(e.clientX - bounds.left) / bounds.width, (e.clientY - bounds.top) / bounds.height]]);
        }}>
          <polygon points={points.map(([x,y]) => `${x*100},${y*100}`).join(" ")} fill="#37d6b02b" stroke="#37d6b0" strokeWidth="0.4" />
          {points.map(([x,y],i) => <circle key={i} cx={x*100} cy={y*100} r="0.8" fill="#37d6b0" />)}
        </svg>
      </div>}
      {error && <div className="text-xs text-status-congested">{error}</div>}
      <div className="flex justify-between gap-3 text-xs"><button onClick={() => setPoints([])} disabled={!frame} className="btn-tactile rounded-lg border border-surface-border px-3 py-2 disabled:opacity-40">Redraw boundary</button><button onClick={save} disabled={saving || points.length !== 4 || lanes.length !== 4 || !frame} className="btn-tactile bg-accent text-white rounded-lg px-3 py-2 disabled:opacity-40">{saving ? "Saving..." : "Save boundary"}</button></div>
    </div>
  </div>;
}
