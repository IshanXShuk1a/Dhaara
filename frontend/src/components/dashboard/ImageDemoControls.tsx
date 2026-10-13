"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { ImageDemoState, IntersectionWsPayload } from "@/lib/types";

export function ImageDemoControls({payload}: {payload: IntersectionWsPayload | null}) {
  const [local, setLocal] = useState<ImageDemoState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const incoming = payload?.image_demo;
  const demo = local && incoming && local.session_id === incoming.session_id && local.revision > incoming.revision ? local : incoming;
  if (!demo) return null;
  const ready = demo.ready && Boolean(payload?.signal) && !busy;
  const hasAmbulance = Object.values(demo.sources).includes("ambulance");
  async function run(action: () => Promise<IntersectionWsPayload>) {
    setBusy(true); setError(null);
    try { const response = await action(); setLocal(response.image_demo ?? null); }
    catch (e) { setError(e instanceof Error ? e.message : "Image case failed."); }
    finally { setBusy(false); }
  }
  const button = "rounded-lg border border-surface-border bg-surface-panel px-2 py-1.5 text-[11px] text-text-secondary hover:border-accent/40 disabled:opacity-40";
  return <section className="card space-y-3 p-3" aria-label="Image demonstration cases">
    <div className="flex items-center justify-between gap-2"><h2 className="text-sm font-semibold text-text-primary">Choose image case</h2><span className="rounded bg-accent/10 px-1.5 py-1 text-[9px] font-semibold text-accent">YOLO</span></div>
    <div className="grid grid-cols-2 gap-1.5">
      {demo.presets.map(item => <button key={item.id} disabled={!ready} aria-pressed={demo.case_id === item.id} onClick={() => run(() => api.selectImageCase(item.id, demo.swapped))}
        className={`${button} text-left ${demo.case_id === item.id ? "!border-accent/50 !bg-accent/10 !text-accent font-semibold" : ""}`}>{item.title}</button>)}
    </div>
    <div className="flex items-center justify-between gap-2 text-[10px] text-text-muted"><span>EW <strong className="capitalize text-text-primary">{demo.sources.EAST}</strong> · NS <strong className="capitalize text-text-primary">{demo.sources.NORTH}</strong></span><button disabled={!ready} onClick={() => run(() => api.selectImageCase(demo.case_id, !demo.swapped))} className="font-semibold text-accent disabled:opacity-40" aria-label="Swap East West and North South images">Swap EW / NS</button></div>
    <div className="grid grid-cols-[auto_auto_1fr] items-center gap-1.5">
      <button disabled={!ready} onClick={() => run(() => api.controlImageDemo({paused: !demo.paused}))} className={button}>{demo.paused ? "Play" : "Pause"}</button>
      <button disabled={!ready} aria-pressed={demo.auto_tour} onClick={() => run(() => api.controlImageDemo({auto_tour: !demo.auto_tour}))} className={`${button} ${demo.auto_tour ? "!text-accent !border-accent/40" : ""}`}>{demo.auto_tour ? "Stop tour" : "Auto tour"}</button>
      <label className="flex items-center justify-end gap-1 text-[10px] text-text-muted"><span className="sr-only">Image demo speed</span><select aria-label="Image demo speed" disabled={!ready} value={demo.speed} onChange={e => run(() => api.controlImageDemo({speed: Number(e.target.value) as 1|2|5|10}))} className="rounded-lg border border-surface-border bg-surface-panel px-1.5 py-1.5 text-[11px] text-text-primary">{[1,2,5,10].map(speed => <option key={speed} value={speed}>{speed}×</option>)}</select></label>
    </div>
    {hasAmbulance && <div className="rounded-lg border border-status-info/30 bg-status-info/5 p-2">
      <div className="flex items-center justify-between gap-2 text-[10px]"><span className="font-semibold text-text-secondary">Demo emergency lights</span><strong className="text-status-info">{demo.lights_active ? `ON · ${Math.ceil(demo.lights_remaining_s)}s` : "OFF"}</strong></div>
      <div className="mt-2 grid grid-cols-2 gap-1.5"><button disabled={!ready} onClick={() => run(() => api.controlImageDemo({lights_active: true}))} className={button}>Lights on (12s)</button><button disabled={!ready} onClick={() => run(() => api.controlImageDemo({lights_active: false}))} className={button}>Lights off</button></div>
      <p className="mt-1.5 text-[9px] leading-relaxed text-text-muted">Explicit demo input. A still image cannot confirm flashing.</p>
      {demo.paused && demo.lights_active && <p className="mt-1 text-[10px] text-status-info">Press Play to advance ambulance confirmation and yellow clearance.</p>}
    </div>}
    <div className="border-t border-surface-border pt-2 text-[10px] text-text-secondary">
      {demo.previous_green_pair ? <span>Last green <strong className="text-status-free">{demo.previous_green_pair}</strong> · Last red <strong className="text-status-congested">{demo.previous_red_pair}</strong></span> : "No previous green phase yet"}
      <div className="mt-1 text-[9px] text-text-muted">{demo.paused ? "Clock paused" : `${demo.speed}× demonstration clock`} · {demo.auto_tour ? "Cases advance after green changes" : "Case changes preserve the signal clock"}</div>
    </div>
    {!demo.ready && <p className="text-xs text-text-muted">Detecting vehicles in the four source images…</p>}
    {error && <p role="alert" className="text-[11px] text-status-congested">{error}</p>}
  </section>;
}

export function ImageSignalHistory({payload}: {payload: IntersectionWsPayload | null}) {
  const demo = payload?.image_demo;
  if (!demo) return null;
  return <section className="card space-y-3 p-4" aria-label="Image signal history">
    <div className="flex items-center justify-between gap-2"><h2 className="text-sm font-semibold">Signal history</h2><span className="text-[10px] text-text-muted">Demonstration time</span></div>
    {demo.transitions.length ? <ol className="space-y-2">{demo.transitions.slice(-5).reverse().map((item, i) => <li key={`${item.time_s}:${i}`} className="rounded-lg bg-surface-panel px-3 py-2 text-[11px]">
      <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold text-text-primary">{item.from_pair} {item.from_state.toLowerCase()} → {item.to_pair} {item.to_state.toLowerCase()}{item.target_pair ? ` → ${item.target_pair} next` : ""}</span><span className="font-mono text-text-muted">{item.time_s.toFixed(1)}s</span></div>
      <p className="mt-1 text-[10px] leading-relaxed text-text-secondary">{item.reason.join(". ")}</p>
    </li>)}</ol> : <p className="text-xs text-text-muted">The first completed phase will appear here. Use 10× speed to observe a full cycle sooner.</p>}
    <p className="border-t border-surface-border pt-2 text-[10px] leading-relaxed text-text-muted">Each pair shares its reference image. Counts come from detected vehicles inside the sample boundary. Distance is uncalibrated; movement and queue clearance cannot be measured from these still images.</p>
  </section>;
}
