import clsx from "clsx";
import type { IntersectionWsPayload } from "@/lib/types";

export function SignalCard({ payload, compact = false }: {payload: IntersectionWsPayload | null; compact?: boolean}) {
  const signal = payload?.signal;
  const demand = payload?.demand;
  return <section className="card p-4 space-y-3" aria-label="Paired signal control">
    <div className="flex items-center justify-between gap-2">
      <h2 className="text-sm font-semibold text-text-primary">Paired signals</h2>
      <span className="rounded-md bg-accent/10 px-1.5 py-1 text-[9px] font-semibold tracking-wide text-accent">{signal?.mode ?? "WAITING"}</span>
    </div>
    <div className={clsx("grid gap-2.5", compact ? "grid-cols-1" : "grid-cols-2")}>
      {(["EW", "NS"] as const).map(pair => {
        const active = signal?.active_direction === pair;
        const color = signal?.directions?.[pair === "EW" ? "EAST" : "NORTH"];
        const priorityHold = signal?.state === "GREEN" && signal.countdown_s <= 0 && payload?.emergency?.state === "PRIORITY_ACTIVE";
        const held = signal?.state === "GREEN" && signal.mode === "MANUAL";
        const waitingThroughYellow = signal?.state === "YELLOW" && color === "RED" && signal.target_direction !== pair;
        const remaining = signal ? signal.countdown_s + (color === "RED" && signal.state === "GREEN" ? demand?.yellow_duration_s ?? 0 : 0) : null;
        const timer = held || priorityHold ? active ? "Held" : "Waiting" : waitingThroughYellow ? "Waiting" : remaining !== null ? `${Math.ceil(remaining)}s` : "—";
        return <div key={pair} className={clsx("rounded-xl border p-3", color === "GREEN" ? "border-status-free/30 bg-status-free/5" : color === "YELLOW" ? "border-status-moderate/40 bg-status-moderate/5" : "border-surface-border bg-surface-panel")}>
          <div className="flex items-center gap-3">
            <div className="flex flex-col gap-1 rounded-lg bg-[#101922] px-1.5 py-2" aria-hidden="true">
              {(["RED", "YELLOW", "GREEN"] as const).map(light => <span key={light} className={clsx("h-2.5 w-2.5 rounded-full", light !== color ? "bg-slate-700" : light === "GREEN" ? "bg-status-free shadow-[0_0_8px_rgba(46,213,156,0.5)]" : light === "YELLOW" ? "bg-status-moderate shadow-[0_0_8px_rgba(247,189,72,0.5)]" : "bg-status-congested shadow-[0_0_8px_rgba(244,104,130,0.4)]")} />)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold">{pair === "EW" ? "East + West" : "North + South"}</span>
                <span className={clsx("text-[10px] font-bold", color === "GREEN" ? "text-status-free" : color === "YELLOW" ? "text-status-moderate" : color === "RED" ? "text-status-congested" : "text-text-muted")}>{color ?? "—"}</span>
              </div>
              <div className="mt-1.5 flex items-end justify-between gap-2">
                <span className="text-[10px] text-text-muted">Avg. score <strong className="ml-1 text-sm tabular-nums font-semibold text-text-primary">{demand?.pair_scores?.[pair] ?? "—"}</strong></span>
                <span className={clsx("font-semibold tabular-nums tracking-tight", timer === "Waiting" || timer === "Held" ? "text-sm" : "text-2xl")}>{timer}</span>
              </div>
            </div>
          </div>
          {color === "GREEN" && demand?.full_phase_required && <div className="text-[10px] text-text-muted mt-2">Completing the full phase after an early switch</div>}
        </div>;
      })}
    </div>
    <div className="flex items-center justify-between border-t border-surface-border pt-2.5 text-[10px] text-text-muted">
      <span>{demand?.phase_duration_s ?? "—"}s green phase</span><span>{demand?.yellow_duration_s ?? "—"}s yellow clearance</span>
    </div>
    {signal?.state === "YELLOW" && <div className="text-[11px] text-status-moderate">{signal.active_direction} yellow → {signal.target_direction} green</div>}
  </section>;
}
