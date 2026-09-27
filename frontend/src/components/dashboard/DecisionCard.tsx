import type { IntersectionWsPayload } from "@/lib/types";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";

interface Props {
  payload: IntersectionWsPayload | null;
}

export function DecisionCard({ payload }: Props) {
  const decision = payload?.decision;
  const laneMetrics = decision?.selected_direction && payload?.lanes ? payload.lanes[decision.selected_direction] : null;

  const pressure = decision?.traffic_pressure ?? laneMetrics?.traffic_pressure ?? 0;
  const queue = decision?.queue_length_m ?? laneMetrics?.queue_length_m ?? 0;
  const wait = decision?.waiting_time_s ?? laneMetrics?.average_waiting_time_s ?? 0;
  const vehicles = decision?.vehicle_count ?? laneMetrics?.vehicle_count ?? 0;

  return (
    <div className="card-interactive card p-4 flex flex-col justify-between relative overflow-hidden group">
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-bold text-text-primary uppercase tracking-wide flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            {decision ? `AI REASONING • ${decision.selected_direction}` : "DECISION ENGINE"}
          </div>
          <button className="text-text-muted hover:text-text-primary text-xs btn-tactile p-1">•••</button>
        </div>

        {!decision ? (
          <div className="text-xs text-text-muted">Awaiting traffic snapshot analysis...</div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-2 p-2.5 rounded-xl bg-surface-raised border border-surface-border mb-3 text-xs shadow-inner">
              <div className="flex justify-between items-center">
                <span className="text-text-muted">Traffic pressure</span>
                <span className="text-text-primary font-semibold">
                  <AnimatedNumber value={pressure} decimals={0} suffix="%" />
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-text-muted">Queue</span>
                <span className="text-text-primary font-semibold">
                  <AnimatedNumber value={queue} decimals={0} suffix="m" />
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-text-muted">Waiting time</span>
                <span className="text-text-primary font-semibold">
                  <AnimatedNumber value={wait} decimals={0} suffix="s" />
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-text-muted">Vehicles</span>
                <span className="text-text-primary font-semibold">
                  <AnimatedNumber value={vehicles} decimals={0} />
                </span>
              </div>
            </div>

            <div className="mb-2">
              <div className="text-[10px] text-text-muted uppercase font-semibold">Phase Grant:</div>
              <div className="text-sm font-bold text-accent flex items-center gap-1.5 mt-0.5">
                <span>{decision.selected_direction} PRIORITY &middot;</span>
                <span className="text-text-primary font-medium text-xs flex items-center gap-0.5">
                  <AnimatedNumber value={decision.green_duration_s} decimals={0} suffix="s" className="font-bold" />
                  <span>green</span>
                </span>
              </div>
            </div>

            <div className="text-xs text-text-muted mb-1.5">Reason:</div>
            <ul className="space-y-1">
              {decision.reason.map((r, i) => (
                <li key={i} className="text-xs text-text-secondary flex gap-2">
                  <span className="text-accent font-bold">&bull;</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      {decision && (
        <div className="mt-3 pt-2 border-t border-surface-border flex items-center justify-between text-[11px] text-text-muted">
          <span>Mode: {decision.mode}</span>
          {decision.fairness_applied && <span className="text-status-moderate font-medium">Fairness Guard Applied</span>}
        </div>
      )}
    </div>
  );
}
