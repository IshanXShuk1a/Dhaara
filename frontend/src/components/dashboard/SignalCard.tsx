import clsx from "clsx";
import type { IntersectionWsPayload } from "@/lib/types";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";

const DIRECTIONS = ["NORTH", "SOUTH", "EAST", "WEST"];

const COLOR_TEXT: Record<string, string> = {
  GREEN: "text-status-free font-bold",
  YELLOW: "text-status-moderate font-bold",
  ALL_RED: "text-status-congested font-bold",
};

interface Props {
  payload: IntersectionWsPayload | null;
}

export function SignalCard({ payload }: Props) {
  const signal = payload?.signal;
  const activeDirection = signal?.active_direction;
  const targetDirection = signal?.target_direction;
  const color = signal?.state ?? "ALL_RED";
  const mode = signal?.mode ?? payload?.decision?.mode ?? "ADAPTIVE";

  return (
    <div className="card-interactive card p-4 relative overflow-hidden group">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-bold text-text-primary uppercase tracking-wide flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-status-free status-dot" />
          SIGNAL HARDWARE CONTROLLER
        </div>
        <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-surface-elevated border border-surface-border text-text-secondary shadow-sm">
          {mode}
        </span>
      </div>

      <div className="flex items-baseline gap-2 mb-1">
        <span className="text-xs text-text-muted">Active State:</span>
        <span className="text-sm font-bold text-text-primary flex items-center gap-1.5">
          <span>{activeDirection ?? "--"}</span>
          <span className={COLOR_TEXT[color] ?? "text-text-primary"}>
            &rarr; {color}
            {color !== "GREEN" && targetDirection ? ` (to ${targetDirection})` : ""}
          </span>
        </span>
      </div>

      <div className="flex items-baseline gap-2 mb-4">
        <span className="text-xs text-text-muted">Remaining Time:</span>
        <span className="text-sm font-bold text-text-primary tabular-nums flex items-center gap-1">
          {signal ? (
            <>
              <AnimatedNumber value={signal.countdown_s} decimals={0} suffix="s" className="font-extrabold text-accent" />
              <span className="text-text-secondary text-xs">active phase</span>
            </>
          ) : (
            "N/A"
          )}
        </span>
      </div>

      <div className="grid grid-cols-4 gap-2">
        {DIRECTIONS.map((direction) => {
          const isActive = direction === activeDirection;
          const isTarget = direction === targetDirection;
          let dotClass = "bg-status-congested/60 shadow-[0_0_6px_rgba(239,98,98,0.35)]";
          let borderClass = "border-surface-border bg-surface";
          let labelBadge = "RED";

          if (isActive) {
            if (color === "GREEN") {
              dotClass = "bg-status-free shadow-[0_0_12px_rgba(66,211,146,0.6)]";
              borderClass = "border-status-free/40 bg-status-free/10 ring-1 ring-status-free/20";
              labelBadge = "GREEN";
            } else if (color === "YELLOW") {
              dotClass = "bg-status-moderate shadow-[0_0_12px_rgba(232,184,74,0.6)]";
              borderClass = "border-status-moderate/40 bg-status-moderate/10 ring-1 ring-status-moderate/20";
              labelBadge = "YELLOW";
            } else {
              dotClass = "bg-status-congested shadow-[0_0_10px_rgba(239,98,98,0.5)]";
              borderClass = "border-status-congested/40 bg-status-congested/10";
              labelBadge = "ALL RED";
            }
          } else if (isTarget) {
            borderClass = "border-accent/30 bg-accent/[0.06]";
            labelBadge = "NEXT";
          }

          return (
            <div key={direction} className={clsx("rounded-xl border p-2.5 text-center transition-all duration-300 relative", borderClass)}>
              <div className="relative flex items-center justify-center mx-auto mb-1.5 w-4 h-4">
                <div className={clsx("h-3 w-3 rounded-full transition-all duration-300", dotClass)} />
                {isActive && color === "GREEN" && (
                  <span className="beacon-ring border border-status-free/40" />
                )}
                {isActive && color === "YELLOW" && (
                  <span className="beacon-ring border border-status-moderate/40" />
                )}
              </div>
              <div className="text-[11px] font-bold text-text-primary">{direction}</div>
              <div className="text-[9px] text-text-muted uppercase tracking-wider font-semibold">{labelBadge}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
