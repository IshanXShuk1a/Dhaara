"use client";

import { useState } from "react";
import { useIntersections } from "@/lib/intersectionContext";
import { useIntersectionSocket } from "@/lib/useIntersectionSocket";
import { useAuth, canOperate } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";

const DIRECTIONS = ["NORTH", "SOUTH", "EAST", "WEST"] as const;

export default function SimulationPage() {
  const { selectedId } = useIntersections();
  const { role } = useAuth();
  const { payload } = useIntersectionSocket(selectedId);
  const [sliders, setSliders] = useState({ north: 10, south: 10, east: 10, west: 10 });
  const [mode, setMode] = useState("ADAPTIVE");
  const [operatorNote, setOperatorNote] = useState("Judge evaluation demo override");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const canControl = canOperate(role);

  async function run(action: () => Promise<unknown>, label: string) {
    if (!selectedId) return;
    setBusy(true);
    setMessage(null);
    try {
      await action();
      setMessage(`${label}: executed successfully`);
    } catch (err) {
      setMessage(err instanceof ApiError ? `${label} failed: ${err.message}` : `${label} failed`);
    } finally {
      setBusy(false);
    }
  }

  // Judge Demo Scenarios (Spec Section 46)
  async function triggerScenario(scenarioNum: number) {
    if (!selectedId) return;
    if (scenarioNum === 1) {
      // Scenario 1: One lane FREE, one CONGESTED
      const s = { north: 4, south: 28, east: 7, west: 2 };
      setSliders(s);
      await run(async () => {
        await api.setSignalMode(selectedId, "ADAPTIVE");
        await api.setSimulationTraffic(selectedId, s);
      }, "Scenario 1 (One FREE, One CONGESTED: SOUTH=28, WEST=2)");
    } else if (scenarioNum === 2) {
      // Scenario 2: Traffic shifts dynamically to EAST
      const s = { north: 3, south: 4, east: 29, west: 2 };
      setSliders(s);
      await run(async () => {
        await api.setSimulationTraffic(selectedId, s);
      }, "Scenario 2 (Dynamic Shift: EAST surges to 29)");
    } else if (scenarioNum === 3) {
      // Scenario 3: Balanced adaptive cycling
      const s = { north: 15, south: 16, east: 14, west: 13 };
      setSliders(s);
      await run(async () => {
        await api.setSignalMode(selectedId, "ADAPTIVE");
        await api.setSimulationTraffic(selectedId, s);
      }, "Scenario 3 (Adaptive Signal Cycling: Balanced Pressure)");
    } else if (scenarioNum === 4) {
      // Scenario 4: Ambulance priority detected on WEST
      await run(async () => {
        await api.spawnAmbulance(selectedId, "WEST");
      }, "Scenario 4 (Ambulance Detected on WEST -> Priority Request)");
    } else if (scenarioNum === 5) {
      // Scenario 5: Helmet violation detected on EAST
      await run(async () => {
        await api.spawnHelmetViolation(selectedId, "EAST");
      }, "Scenario 5 (Helmet Violation Detected on EAST)");
    } else if (scenarioNum === 6) {
      // Scenario 6: Fixed vs Adaptive comparison
      const targetMode = mode === "FIXED" ? "ADAPTIVE" : "FIXED";
      setMode(targetMode);
      await run(async () => {
        await api.setSignalMode(selectedId, targetMode);
      }, `Scenario 6 (Switched to ${targetMode} Mode)`);
    }
  }

  if (!selectedId) return <div className="text-sm text-text-muted">Select an intersection first.</div>;

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <div className="text-xl font-bold text-text-primary">Traffic Simulator &amp; Control Console</div>
        <div className="text-xs text-text-muted mt-1">
          Mutates the backend&apos;s real scenario state (VehicleScripts). Every parameter flows through the full
          causal pipeline: Detector &rarr; Tracker &rarr; Lane Assigner &rarr; Lane Intelligence &rarr; Decision Engine &rarr; Signal FSM.
        </div>
      </div>

      {!canControl && (
        <div className="text-xs text-status-moderate bg-status-moderate/10 border border-status-moderate/30 rounded-lg px-3 py-2">
          Your role ({role}) is read-only for controls. Sign in as TRAFFIC_OPERATOR or ADMIN to modify live simulation.
        </div>
      )}

      {/* Section 46: Judge Demo Scenarios */}
      <div className="card p-5 border-accent/40 bg-accent/5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-sm font-bold text-accent tracking-wide uppercase">Judge Demo Scenarios</div>
          <span className="text-[11px] font-medium bg-accent/20 text-accent px-2 py-0.5 rounded">6 Scenarios</span>
        </div>
        <div className="text-xs text-text-secondary leading-relaxed">
          One-click evaluation scenarios executing the complete end-to-end backend causal chain:
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5 pt-1">
          <button
            disabled={!canControl || busy}
            onClick={() => triggerScenario(1)}
            className="text-left p-3 rounded-lg border border-surface-border bg-surface-card hover:border-accent/60 transition-all text-xs disabled:opacity-50"
          >
            <div className="font-semibold text-text-primary">Scenario 1: Lane Congestion</div>
            <div className="text-[11px] text-text-muted mt-1">SOUTH=28 (Congested) vs WEST=2 (Free). Demonstrates explainable free-lane detection.</div>
          </button>
          <button
            disabled={!canControl || busy}
            onClick={() => triggerScenario(2)}
            className="text-left p-3 rounded-lg border border-surface-border bg-surface-card hover:border-accent/60 transition-all text-xs disabled:opacity-50"
          >
            <div className="font-semibold text-text-primary">Scenario 2: Traffic Shift</div>
            <div className="text-[11px] text-text-muted mt-1">Congestion shifts dynamically to EAST=29. Decision engine re-ranks in real-time.</div>
          </button>
          <button
            disabled={!canControl || busy}
            onClick={() => triggerScenario(3)}
            className="text-left p-3 rounded-lg border border-surface-border bg-surface-card hover:border-accent/60 transition-all text-xs disabled:opacity-50"
          >
            <div className="font-semibold text-text-primary">Scenario 3: Adaptive Cycling</div>
            <div className="text-[11px] text-text-muted mt-1">Dynamic green duration calculated from waiting time, queue, and fairness.</div>
          </button>
          <button
            disabled={!canControl || busy}
            onClick={() => triggerScenario(4)}
            className="text-left p-3 rounded-lg border border-surface-border bg-surface-card hover:border-accent/60 transition-all text-xs disabled:opacity-50"
          >
            <div className="font-semibold text-text-primary">Scenario 4: Ambulance Dispatch</div>
            <div className="text-[11px] text-text-muted mt-1">Approaching WEST ambulance &rarr; Temporal confirmation &rarr; Safe green clearance.</div>
          </button>
          <button
            disabled={!canControl || busy}
            onClick={() => triggerScenario(5)}
            className="text-left p-3 rounded-lg border border-surface-border bg-surface-card hover:border-accent/60 transition-all text-xs disabled:opacity-50"
          >
            <div className="font-semibold text-text-primary">Scenario 5: Safety Violation</div>
            <div className="text-[11px] text-text-muted mt-1">No-helmet motorcycle on EAST. Violations logged without affecting signal timing.</div>
          </button>
          <button
            disabled={!canControl || busy}
            onClick={() => triggerScenario(6)}
            className="text-left p-3 rounded-lg border border-surface-border bg-surface-card hover:border-accent/60 transition-all text-xs disabled:opacity-50"
          >
            <div className="font-semibold text-text-primary">Scenario 6: Fixed vs Adaptive</div>
            <div className="text-[11px] text-text-muted mt-1">Compare rigid 30s fixed cycle against real-time AI pressure allocation.</div>
          </button>
        </div>
      </div>

      {/* Traffic Sliders */}
      <div className="card p-4 space-y-4">
        <div className="text-sm font-semibold text-text-primary">Per-Direction Traffic Volume Sliders</div>
        {DIRECTIONS.map((dir) => {
          const key = dir.toLowerCase() as keyof typeof sliders;
          return (
            <div key={dir} className="flex items-center gap-3">
              <span className="w-14 text-xs font-medium text-text-secondary">{dir}</span>
              <input
                type="range"
                min={0}
                max={35}
                value={sliders[key]}
                disabled={!canControl}
                onChange={(e) => setSliders((s) => ({ ...s, [key]: Number(e.target.value) }))}
                className="flex-1 accent-accent cursor-pointer"
              />
              <span className="w-10 text-xs font-bold text-text-primary tabular-nums text-right">{sliders[key]}</span>
            </div>
          );
        })}
        <div className="flex gap-2">
          <button
            disabled={!canControl || busy}
            onClick={() => run(() => api.setSimulationTraffic(selectedId, sliders), "Apply traffic sliders")}
            className="text-xs px-4 py-2 rounded-lg bg-accent text-white font-medium hover:bg-accent/90 disabled:opacity-50 transition-colors"
          >
            Apply Volume to Backend
          </button>
          <button
            disabled={!canControl || busy}
            onClick={() => {
              const reset = { north: 10, south: 10, east: 10, west: 10 };
              setSliders(reset);
              run(() => api.setSimulationTraffic(selectedId, reset), "Reset volume to baseline (10)");
            }}
            className="text-xs px-3 py-2 rounded-lg border border-surface-border text-text-secondary hover:bg-surface-card disabled:opacity-50"
          >
            Set All to 10
          </button>
        </div>
      </div>

      {/* Emergency & Safety Triggers */}
      <div className="card p-4 space-y-3">
        <div className="text-sm font-semibold text-text-primary">Emergency &amp; Road Safety Controls</div>
        <div>
          <div className="text-xs text-text-muted mb-1.5">Spawn Approaching Ambulance:</div>
          <div className="flex flex-wrap gap-2">
            {DIRECTIONS.map((dir) => (
              <button
                key={dir}
                disabled={!canControl || busy}
                onClick={() => run(() => api.spawnAmbulance(selectedId, dir), `Spawn ambulance (${dir})`)}
                className="text-xs px-3 py-2 rounded-lg border border-surface-border bg-surface-card text-text-primary hover:border-status-emergency/60 disabled:opacity-50"
              >
                Ambulance &middot; {dir}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="text-xs text-text-muted mb-1.5">Spawn Motorcycle Helmet Violation:</div>
          <div className="flex flex-wrap gap-2">
            {DIRECTIONS.map((dir) => (
              <button
                key={dir}
                disabled={!canControl || busy}
                onClick={() => run(() => api.spawnHelmetViolation(selectedId, dir), `Helmet violation (${dir})`)}
                className="text-xs px-3 py-2 rounded-lg border border-surface-border bg-surface-card text-text-primary hover:border-status-moderate/60 disabled:opacity-50"
              >
                No Helmet &middot; {dir}
              </button>
            ))}
          </div>
        </div>
        <div className="pt-2">
          <button
            disabled={!canControl || busy}
            onClick={() => run(() => api.resetSimulation(selectedId), "Reset simulation")}
            className="text-xs px-3 py-2 rounded-lg border border-status-congested/40 text-status-congested hover:bg-status-congested/10 disabled:opacity-50"
          >
            Reset Simulation State
          </button>
        </div>
      </div>

      {/* Police / Operator Override (Spec Section 24) */}
      <div className="card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold text-text-primary">Police / Operator Manual Override</div>
          <span className="text-[10px] text-text-muted uppercase tracking-wider font-semibold">Section 24 Compliant</span>
        </div>
        <div className="text-xs text-text-muted">
          Allows an authorized traffic officer to force phase selection, pause adaptive cycling, or resume AI control. All overrides are logged with audit timestamps.
        </div>

        <div className="flex items-center gap-2 pt-1">
          <input
            type="text"
            value={operatorNote}
            onChange={(e) => setOperatorNote(e.target.value)}
            placeholder="Operator override reason..."
            className="flex-1 bg-surface-card border border-surface-border rounded-lg text-xs px-3 py-2 text-text-primary"
          />
        </div>

        <div>
          <div className="text-xs text-text-muted mb-1.5">Force Phase Direction (Safe Transition Enforced):</div>
          <div className="flex flex-wrap gap-2">
            {DIRECTIONS.map((dir) => (
              <button
                key={dir}
                disabled={!canControl || busy}
                onClick={() => run(() => api.overrideSignal(selectedId, dir, operatorNote), `Override to ${dir}`)}
                className="text-xs px-3 py-1.5 rounded-lg border border-accent/40 bg-accent/10 text-accent font-medium hover:bg-accent/20 disabled:opacity-50"
              >
                Force {dir} Green
              </button>
            ))}
          </div>
        </div>

        <div className="flex gap-2 pt-1">
          <button
            disabled={!canControl || busy}
            onClick={() => {
              setMode("MANUAL");
              run(() => api.setSignalMode(selectedId, "MANUAL"), "Pause adaptive control (Hold Current Phase)");
            }}
            className="text-xs px-3 py-1.5 rounded-lg border border-surface-border text-status-moderate hover:bg-status-moderate/10 disabled:opacity-50"
          >
            Pause Adaptive Control
          </button>
          <button
            disabled={!canControl || busy}
            onClick={() => {
              setMode("ADAPTIVE");
              run(() => api.setSignalMode(selectedId, "ADAPTIVE"), "Resume adaptive AI control");
            }}
            className="text-xs px-3 py-1.5 rounded-lg border border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/10 disabled:opacity-50"
          >
            Resume Adaptive Control
          </button>
          <button
            disabled={!canControl || busy}
            onClick={() => {
              setMode("FIXED");
              run(() => api.setSignalMode(selectedId, "FIXED"), "Switch to FIXED 30s cycle");
            }}
            className="text-xs px-3 py-1.5 rounded-lg border border-surface-border text-text-secondary hover:bg-surface-card disabled:opacity-50"
          >
            Set Fixed Timing (30s)
          </button>
        </div>

        <div className="text-xs text-text-muted pt-1">
          Active Mode: <span className="text-text-primary font-semibold">{payload?.signal?.mode ?? mode}</span> &middot; Signal:{" "}
          <span className="text-text-primary font-semibold">{payload?.signal?.active_direction ?? "--"} ({payload?.signal?.state ?? "--"})</span>
        </div>
      </div>

      {message && (
        <div className="text-xs text-text-primary p-3 rounded-lg bg-surface-raised border border-accent/30 flex items-center gap-2">
          <span className="status-dot bg-accent" />
          <span>{message}</span>
        </div>
      )}
    </div>
  );
}
