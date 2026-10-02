"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useIntersectionSocket } from "@/lib/useIntersectionSocket";
import { SIMULATION_CASES, SIMULATION_ID, type SimulationDirection, type SimulationSnapshot, type SimulationSpeed } from "@/lib/simulation";

const IntersectionScene = dynamic(() => import("@/components/simulation/IntersectionScene"), {
  ssr: false, loading: () => <div className="flex h-[440px] items-center justify-center bg-[#dce7f0] text-sm text-slate-600">Preparing the 3D intersection…</div>,
});

function ControlIcon({ name }: { name: "play" | "pause" | "reset" }) {
  return <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    {name === "play" ? <path d="m7 4 9 6-9 6z" /> : name === "pause" ? <path d="M7 4v12M13 4v12" /> : <path d="M4 7a6 6 0 1 1 0 6M4 3v4h4" />}
  </svg>;
}

export default function SimulationPage() {
  const { payload, status, lastUpdate } = useIntersectionSocket(SIMULATION_ID);
  const [snapshot, setSnapshot] = useState<SimulationSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"perspective" | "overhead">("perspective");
  const [resetView, setResetView] = useState(0);
  const [ambulanceDirection, setAmbulanceDirection] = useState<SimulationDirection>("NORTH");
  const [now, setNow] = useState(Date.now());
  const [receivedAt, setReceivedAt] = useState(Date.now());

  useEffect(() => {
    let active = true;
    api.getSimulation().then(data => { if (active) { setSnapshot(current => current ?? data); setReceivedAt(Date.now()); } })
      .catch(e => { if (active) setError(e instanceof Error ? e.message : "Cannot load the simulation."); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!payload) return;
    const incoming = payload as SimulationSnapshot;
    setSnapshot(current => current?.simulation && incoming.simulation && incoming.simulation.run_id < current.simulation.run_id ? current : incoming);
    setReceivedAt(lastUpdate ?? Date.now());
  }, [payload, lastUpdate]);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 100); return () => window.clearInterval(timer); }, []);

  async function run(action: () => Promise<SimulationSnapshot>) {
    setBusy(true); setError(null);
    try { const data = await action(); setSnapshot(data); setReceivedAt(Date.now()); }
    catch (e) { setError(e instanceof Error ? e.message : "Simulation action failed."); }
    finally { setBusy(false); }
  }

  const simulation = snapshot?.simulation;
  const selectedCase = SIMULATION_CASES.find(c => c.id === simulation?.scenario);
  const connected = status === "CONNECTED" && Boolean(snapshot?.signal) && now - receivedAt < 2000;
  const paused = simulation?.paused ?? false;
  const speed = simulation?.speed ?? 1;
  const signal = snapshot?.signal;
  const elapsed = connected && !paused ? Math.max(0, now - receivedAt) / 1000 * speed : 0;
  const remaining = signal ? Math.ceil(Math.max(0, signal.countdown_s - elapsed)) : null;
  const activePair = signal?.active_direction === "NS" ? "North + South" : "East + West";
  const nextPair = signal?.target_direction === "NS" ? "North + South" : "East + West";
  const priority = snapshot?.emergency?.flashing_lights_confirmed && snapshot.emergency.state === "PRIORITY_ACTIVE";
  const phaseText = !connected ? "Waiting for simulation" : paused ? "Simulation paused" : signal?.state === "YELLOW" ? `${activePair} is turning yellow` : `${activePair} has green`;
  const countdownText = priority ? "Priority" : remaining === null ? "—" : `${remaining}s`;
  const ready = Boolean(simulation) && connected && !busy;

  return <div className="mx-auto max-w-[1680px] space-y-4 pb-4">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <div className="mb-1.5 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-accent"><span className="h-1.5 w-1.5 rounded-full bg-accent" /> Learn by exploring</div>
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary sm:text-[28px]">Traffic playground</h1>
        <p className="mt-1 text-xs text-text-secondary sm:text-sm">One intersection. Four directions. See why the lights change.</p>
      </div>
      <div className="rounded-full border border-accent/25 bg-accent/10 px-3 py-1.5 text-[11px] font-medium text-accent">Separate simulation lab</div>
    </div>
    {error && <div role="alert" className="rounded-xl border border-status-congested/30 bg-status-congested/10 px-4 py-3 text-sm text-status-congested">{error}</div>}
    {status !== "CONNECTED" && <div role="status" className="rounded-xl border border-status-moderate/30 bg-status-moderate/10 px-4 py-2 text-xs text-status-moderate">{status === "CONNECTING" ? "Connecting to the simulation controller…" : "Simulation connection interrupted. Cars are paused until it reconnects."}</div>}
    <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0 space-y-3">
        <section className="card overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-surface-border px-4 py-3">
            <div className="flex items-center gap-2"><span className="rounded-md bg-accent/10 px-2 py-1 text-[10px] font-bold tracking-wider text-accent">3D</span><h2 className="text-sm font-semibold text-text-primary">{simulation?.label ?? "Four-way intersection"}</h2></div>
            <div className="inline-flex rounded-lg border border-surface-border bg-surface-panel p-0.5">
              {(["perspective", "overhead"] as const).map(v => <button key={v} onClick={() => setView(v)} aria-pressed={view === v} className={`rounded-md px-2.5 py-1 text-[11px] font-medium ${view === v ? "bg-surface-elevated text-text-primary shadow-sm" : "text-text-muted hover:text-text-primary"}`}>{v === "perspective" ? "3D view" : "Top view"}</button>)}
              <button onClick={() => setResetView(v => v + 1)} title="Reset camera position" aria-label="Reset camera position" className="rounded-md px-2 text-text-muted hover:text-text-primary"><ControlIcon name="reset" /></button>
            </div>
          </div>
          <div className="relative">
            <IntersectionScene snapshot={snapshot} running={connected} view={view} resetView={resetView} />
            <div className="pointer-events-none absolute left-3 top-3 rounded-xl border border-white/70 bg-white/90 px-3 py-2 text-[11px] text-slate-600 shadow-sm"><div className="font-semibold text-slate-800">Drag to orbit</div><div className="mt-0.5">Scroll or pinch to zoom</div></div>
            <div className="pointer-events-none absolute bottom-3 left-3 right-3 flex flex-wrap items-center justify-between gap-2">
              <span className="rounded-lg border border-white/70 bg-white/90 px-3 py-2 text-[11px] font-medium text-slate-700">E + W move together · N + S move together</span>
              <span className="rounded-lg border border-white/70 bg-white/90 px-3 py-2 font-mono text-[11px] text-slate-700">{paused ? "PAUSED" : `${speed}× simulation time`}</span>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div className="flex items-center gap-2">
              <button disabled={!ready} onClick={() => run(() => api.controlSimulation({ paused: !paused }))} className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-white disabled:opacity-40"><ControlIcon name={paused ? "play" : "pause"} />{paused ? "Play" : "Pause"}</button>
              <button disabled={!ready} onClick={() => run(() => api.setSimulationScenario(simulation!.scenario))} className="flex items-center gap-1.5 rounded-lg border border-surface-border bg-surface-panel px-3 py-2 text-xs text-text-secondary disabled:opacity-40"><ControlIcon name="reset" />Restart case</button>
            </div>
            <label className="flex items-center gap-2 text-xs text-text-secondary">Speed<select aria-label="Simulation speed" value={speed} disabled={!ready} onChange={e => run(() => api.controlSimulation({ speed: Number(e.target.value) as SimulationSpeed }))} className="rounded-lg border border-surface-border bg-surface-panel px-2 py-1.5 text-xs text-text-primary disabled:opacity-40">{[1,2,5,10].map(s => <option key={s} value={s}>{s}×</option>)}</select></label>
          </div>
        </section>
        <div className="grid gap-3 sm:grid-cols-2">
          {(["EW", "NS"] as const).map(pair => {
            const color = signal?.directions[pair === "EW" ? "EAST" : "NORTH"];
            const current = signal?.active_direction === pair;
            const score = snapshot?.demand?.pair_scores[pair];
            const style = color === "GREEN" ? "text-status-free border-status-free/25 bg-status-free/10" : color === "YELLOW" ? "text-status-moderate border-status-moderate/25 bg-status-moderate/10" : "text-status-congested border-status-congested/20 bg-status-congested/5";
            return <div key={pair} className={`rounded-xl border px-4 py-3 ${connected ? style : "border-surface-border bg-surface-card text-text-muted"}`}>
              <div className="flex items-center justify-between gap-2"><span className="text-xs font-semibold">{pair === "EW" ? "East + West" : "North + South"}</span><span className="text-[10px] font-bold tracking-wider">{connected ? color : "OFFLINE"}</span></div>
              <div className="mt-2 flex items-baseline justify-between gap-2"><span className="text-2xl font-semibold tabular-nums">{typeof score === "number" ? score : "—"}<span className="ml-1.5 text-[10px] font-normal opacity-70">average score</span></span><span className="font-mono text-sm font-semibold">{current && connected ? countdownText : "Wait"}</span></div>
            </div>;
          })}
        </div>
        <p className="px-1 text-[11px] leading-relaxed text-text-muted">Scenario arrivals are replenished to hold demand steady. This miniature is illustrative; the camera dashboard uses actual video and calibrated counting areas.</p>
      </div>
      <aside className="space-y-3">
        <section className="card p-4">
          <div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold text-text-primary">Choose a traffic case</h2><span className="text-[10px] text-text-muted">5 cases</span></div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
            {SIMULATION_CASES.map((c, index) => <button key={c.id} disabled={busy || status !== "CONNECTED"} onClick={() => run(() => api.setSimulationScenario(c.id))} aria-pressed={simulation?.scenario === c.id} className={`flex items-start gap-3 rounded-xl border p-3 text-left transition-colors disabled:opacity-40 ${simulation?.scenario === c.id ? "border-accent/50 bg-accent/10" : "border-surface-border bg-surface-panel hover:border-accent/40"}`}>
              <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-[11px] font-semibold ${simulation?.scenario === c.id ? "bg-accent text-white" : "bg-surface-elevated text-text-muted"}`}>{index + 1}</span>
              <span><span className="block text-xs font-semibold text-text-primary">{c.title}</span><span className="mt-1 block text-[10px] text-text-muted">{c.description}</span></span>
            </button>)}
          </div>
        </section>
        <section className="card p-4" aria-live="polite">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-accent">What is happening?</div>
          <h2 className="mt-2 text-sm font-semibold text-text-primary">{phaseText}</h2>
          <p className="mt-2 text-xs leading-relaxed text-text-secondary">{signal?.state === "YELLOW" ? `${nextPair} stays red while the outgoing traffic clears. Green follows after the complete 3-second yellow interval.` : priority ? "Flashing ambulance lights are confirmed. Its pair holds green until emergency priority clears." : selectedCase?.lesson ?? "Choose a case to see the signal rules in action."}</p>
          <div className="mt-3 grid grid-cols-2 gap-2 border-t border-surface-border pt-3 text-[10px] text-text-muted"><span>Green <strong className="text-text-secondary">70s</strong></span><span>Yellow <strong className="text-text-secondary">3s</strong></span><span>Score gap <strong className="text-text-secondary">20+</strong></span><span>Almost empty <strong className="text-text-secondary">≤ 5</strong></span></div>
        </section>
        <section className="card p-4">
          <h2 className="text-xs font-semibold text-text-primary">Try an ambulance</h2>
          <p className="mt-1.5 text-[11px] leading-relaxed text-text-muted">Priority requires an ambulance with flashing emergency lights.</p>
          <label className="mt-3 flex items-center justify-between gap-2 text-[11px] text-text-secondary">Approach<select aria-label="Ambulance approach" value={ambulanceDirection} onChange={e => setAmbulanceDirection(e.target.value as SimulationDirection)} className="rounded-lg border border-surface-border bg-surface-panel px-2 py-1.5 text-text-primary">{["NORTH", "SOUTH", "EAST", "WEST"].map(d => <option key={d} value={d}>{d.charAt(0) + d.slice(1).toLowerCase()}</option>)}</select></label>
          <div className="mt-2 grid grid-cols-2 gap-2"><button disabled={!ready} onClick={() => run(() => api.simulationAmbulance(ambulanceDirection, true))} className="rounded-lg border border-status-info/30 bg-status-info/10 px-2 py-2 text-[11px] font-semibold text-status-info disabled:opacity-40">Lights on</button><button disabled={!ready} onClick={() => run(() => api.simulationAmbulance(ambulanceDirection, false))} className="rounded-lg border border-surface-border bg-surface-panel px-2 py-2 text-[11px] text-text-secondary disabled:opacity-40">Lights off</button></div>
        </section>
      </aside>
    </div>
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-surface-border bg-surface-panel px-4 py-3 text-[11px] text-text-muted"><span className="font-semibold text-text-secondary">How scores work</span><span>Car <strong className="text-text-primary">2</strong></span><span>Auto / rickshaw <strong className="text-text-primary">1.5</strong></span><span>Two-wheeler <strong className="text-text-primary">1</strong></span><span>Pair score = average of its two directions</span></div>
  </div>;
}
