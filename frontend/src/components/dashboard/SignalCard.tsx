import clsx from "clsx";
import type { IntersectionWsPayload } from "@/lib/types";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";

const DIRECTIONS = ["NORTH", "SOUTH", "EAST", "WEST"];

const COLOR_TEXT: Record<string, string> = {
  GREEN: "text-emerald-400 font-extrabold",
  YELLOW: "text-amber-400 font-extrabold",
  ALL_RED: "text-rose-400 font-extrabold",
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
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          SIGNAL HARDWARE CONTROLLER
        </div>
        <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-surface-card border border-surface-border text-text-secondary shadow-sm">
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
          let dotClass = "bg-red-500/70 shadow-[0_0_8px_rgba(239,68,68,0.4)]";
          let borderClass = "border-surface-border bg-surface-card";
          let labelBadge = "RED";

          if (isActive) {
            if (color === "GREEN") {
              dotClass = "bg-emerald-400 shadow-[0_0_18px_rgba(16,185,129,0.9)]";
              borderClass = "border-emerald-500/70 bg-emerald-500/10 ring-1 ring-emerald-500/40 shadow-lg shadow-emerald-500/10";
              labelBadge = "GREEN";
            } else if (color === "YELLOW") {
              dotClass = "bg-amber-400 shadow-[0_0_18px_rgba(245,158,11,0.9)] animate-pulse";
              borderClass = "border-amber-400/70 bg-amber-400/10 ring-1 ring-amber-400/40 shadow-lg shadow-amber-400/10";
              labelBadge = "YELLOW";
            } else {
              dotClass = "bg-red-500 shadow-[0_0_18px_rgba(239,68,68,0.9)]";
              borderClass = "border-red-500/70 bg-red-500/10";
              labelBadge = "ALL RED";
            }
          } else if (isTarget) {
            borderClass = "border-accent/50 bg-accent/10";
            labelBadge = "NEXT";
          }

          return (
            <div key={direction} className={clsx("rounded-xl border p-2.5 text-center transition-all duration-300 relative", borderClass)}>
              <div className="relative flex items-center justify-center mx-auto mb-1.5 w-4 h-4">
                <div className={clsx("h-3 w-3 rounded-full transition-all duration-300", dotClass)} />
                {isActive && color === "GREEN" && (
                  <span className="beacon-ring border border-emerald-400" />
                )}
                {isActive && color === "YELLOW" && (
                  <span className="beacon-ring border border-amber-400" />
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
