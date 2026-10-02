import clsx from "clsx";
import type { IntersectionWsPayload } from "@/lib/types";

export function DecisionCard({payload}: {payload: IntersectionWsPayload | null}) {
  const demand = payload?.demand;
  const emergency = payload?.emergency;
  const denser = demand?.denser_pair;
  const explanation = payload?.decision?.reason?.join(". ") || "Awaiting a processed frame from all four cameras.";
  const ambulanceActive = emergency?.flashing_lights_confirmed && emergency.state === "PRIORITY_ACTIVE";
  return <section className="card p-4 space-y-3 text-xs" aria-label="Traffic demand decision">
    <h2 className="text-sm font-semibold text-text-primary">Current demand</h2>
    <div className="flex items-center justify-between gap-2">
      <span className="text-text-muted">Denser pair</span>
      <strong className="rounded-md bg-accent/10 px-2 py-1 text-[11px] font-semibold text-accent">{denser === "EW" ? "East + West" : denser === "NS" ? "North + South" : denser === "BALANCED" ? "Balanced" : "Awaiting cameras"}</strong>
    </div>
    <div className="flex items-center justify-between gap-2">
      <span className="text-text-muted">Difference / threshold</span><strong className="tabular-nums font-medium">{demand?.score_difference ?? "—"} / {demand?.difference_threshold ?? "—"}</strong>
    </div>
    <p className="rounded-lg bg-surface-panel p-2.5 text-[11px] leading-relaxed text-text-secondary">{explanation}</p>
    <div className="border-t border-surface-border pt-3">
      <div className="flex items-center gap-1.5 text-[11px] text-text-muted"><span className={clsx("h-1.5 w-1.5 rounded-full", ambulanceActive ? "bg-status-congested" : "bg-text-muted")} />Ambulance priority</div>
      <div className={clsx("mt-1 text-[11px] font-medium", ambulanceActive ? "text-status-congested" : "text-text-secondary")}>{ambulanceActive ? `${emergency.direction} · flashing lights confirmed` : emergency?.visible_ambulances ? "Visible; emergency lights not confirmed" : "Inactive"}</div>
    </div>
    <div className="text-[10px] leading-relaxed text-text-muted">Weights: car 2 · auto 1.5 · two wheeler 1.<br />Only vehicles within the counted area contribute.</div>
  </section>;
}
