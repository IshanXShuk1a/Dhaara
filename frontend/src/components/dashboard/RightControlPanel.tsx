"use client";

import { useState } from "react";
import clsx from "clsx";
import type { IntersectionWsPayload } from "@/lib/types";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";

interface Props {
  payload: IntersectionWsPayload | null;
}

const APPROACHES = [
  { direction: "SOUTH", camId: "CAM-02", name: "South Corridor", avatar: "S" },
  { direction: "EAST", camId: "CAM-03", name: "East Approach", avatar: "E" },
  { direction: "NORTH", camId: "CAM-01", name: "North Approach", avatar: "N" },
  { direction: "WEST", camId: "CAM-04", name: "West Highway", avatar: "W" },
];

export function RightControlPanel({ payload }: Props) {
  const [search, setSearch] = useState("");
  const lanes = payload?.lanes ?? {};
  const activeDirection = payload?.signal?.active_direction;
  const signalState = payload?.signal?.state ?? "GREEN";
  const countdown = Math.round(payload?.signal?.countdown_seconds ?? 0);
  const emergency = payload?.emergency;

  const filteredApproaches = APPROACHES.filter((a) =>
    a.name.toLowerCase().includes(search.toLowerCase()) || a.direction.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="card-interactive card p-4 bg-surface-card flex flex-col justify-between h-full space-y-4">
      {/* Top Header & Search */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-xs font-bold text-text-primary uppercase tracking-wide flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            Approaches & Allotments
          </div>
          <button className="text-text-muted hover:text-text-primary text-xs btn-tactile p-1">•••</button>
        </div>

        {/* Search Pill Input matching mockup */}
        <div className="glass-pill flex items-center gap-2 px-3 py-1.5 text-xs text-text-muted focus-within:ring-1 focus-within:ring-accent transition-all">
          <svg className="w-3.5 h-3.5 text-text-muted shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search approach..."
            className="w-full bg-transparent text-xs text-text-primary placeholder:text-text-muted focus:outline-none"
          />
        </div>

        {/* Approach Cards */}
        <div className="space-y-2 pt-1">
          {filteredApproaches.map((appr) => {
            const laneMetrics = lanes[appr.direction];
            const isAllotted = activeDirection === appr.direction && signalState === "GREEN";
            const pressure = laneMetrics?.traffic_pressure ?? 0;

            return (
              <div
                key={appr.direction}
                className={clsx(
                  "p-2.5 rounded-xl flex items-center justify-between transition-all duration-300 btn-tactile cursor-pointer",
                  isAllotted
                    ? "dark:bg-white dark:text-gray-950 dark:border-transparent dark:shadow-xl dark:ring-2 dark:ring-emerald-400 bg-emerald-50 text-slate-900 border border-emerald-300 ring-2 ring-emerald-500 shadow-md scale-[1.02]"
                    : "bg-surface-pill text-text-primary hover:bg-surface-cardHover hover:translate-x-1 border border-surface-border"
                )}
              >
                {/* Left: Avatar + Title */}
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="relative">
                    <div
                      className={clsx(
                        "w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shadow-inner transition-colors",
                        isAllotted
                          ? "dark:bg-gray-900 dark:text-white bg-emerald-600 text-white"
                          : "bg-surface-card text-text-primary border border-surface-border"
                      )}
                    >
                      {appr.avatar}
                    </div>
                    {isAllotted ? (
                      <>
                        <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 dark:ring-white ring-emerald-200" />
                        <span className="beacon-ring border border-emerald-400" />
                      </>
                    ) : (
                      <span className="absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full bg-status-online ring-2 ring-surface-card" />
                    )}
                  </div>

                  <div className="min-w-0">
                    <div className={clsx("text-xs font-bold truncate", isAllotted ? "dark:text-gray-950 text-slate-900" : "text-text-primary")}>
                      {appr.name}
                    </div>
                    <div className={clsx("text-[10px] truncate flex items-center gap-1", isAllotted ? "dark:text-emerald-800 text-emerald-700 font-semibold" : "text-text-muted")}>
                      {isAllotted ? (
                        <>
                          <span>Allotted Green:</span>
                          <AnimatedNumber value={countdown} decimals={0} suffix="s" className="font-extrabold" />
                        </>
                      ) : (
                        <>
                          <span>Queue:</span>
                          <AnimatedNumber value={laneMetrics?.queue_length_m ?? 0} decimals={0} suffix="m" />
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right: Circular Badge */}
                <div
                  className={clsx(
                    "w-7 h-7 rounded-full flex items-center justify-center font-mono font-bold text-[10px] shrink-0 ml-2 transition-transform",
                    isAllotted
                      ? "dark:bg-gray-900 dark:text-white bg-emerald-600 text-white shadow"
                      : "bg-surface-card text-text-secondary border border-surface-border"
                  )}
                >
                  <AnimatedNumber value={pressure} decimals={0} suffix="%" />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* DASHED DIVIDER */}
      <div className="border-t-2 border-dashed border-surface-border my-2" />

      {/* Lower Section: Priority & Safety Corridors */}
      <div className="space-y-3">
        <div className="text-xs font-bold text-text-primary uppercase tracking-wide">
          Priority & Safety Corridors
        </div>

        <div className="space-y-2">
          {/* Item 1: Ambulance Preemption */}
          <div className="p-2.5 rounded-xl bg-surface-pill border border-surface-border hover:bg-surface-cardHover transition-all flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-rose-500/20 text-rose-500 flex items-center justify-center font-bold text-xs shrink-0">
                🚑
              </div>
              <div className="min-w-0">
                <div className="font-semibold text-text-primary text-[11px] truncate">Emergency Vehicle</div>
                <div className="text-[10px] text-text-muted truncate">
                  {emergency?.state !== "NONE" ? `Active on ${emergency?.direction ?? "West"}` : "Standby (No Active Call)"}
                </div>
              </div>
            </div>
            <span
              className={clsx(
                "text-[10px] px-2 py-0.5 rounded-md font-medium border shrink-0",
                emergency?.state !== "NONE"
                  ? "bg-rose-500/20 text-rose-500 border-rose-500/40 animate-pulse"
                  : "bg-surface-card text-text-muted border-surface-border"
              )}
            >
              {emergency?.state !== "NONE" ? "PREEMPT" : "STANDBY"}
            </span>
          </div>

          {/* Item 2: Regional Green Wave */}
          <div className="p-2.5 rounded-xl bg-surface-pill border border-surface-border hover:bg-surface-cardHover transition-all flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-accent/20 text-accent flex items-center justify-center font-bold text-xs shrink-0">
                🌊
              </div>
              <div className="min-w-0">
                <div className="font-semibold text-text-primary text-[11px] truncate">Corridor Coordination</div>
                <div className="text-[10px] text-text-muted truncate">Janpath North-South</div>
              </div>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded-md font-medium bg-surface-card text-text-secondary border border-surface-border shrink-0">
              SYNCED
            </span>
          </div>

          {/* Item 3: Safety Compliance */}
          <div className="p-2.5 rounded-xl bg-surface-pill border border-surface-border hover:bg-surface-cardHover transition-all flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-500 flex items-center justify-center font-bold text-xs shrink-0">
                🪖
              </div>
              <div className="min-w-0">
                <div className="font-semibold text-text-primary text-[11px] truncate">Helmet Safety Monitor</div>
                <div className="text-[10px] text-text-muted truncate">Independent Enforcement</div>
              </div>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded-md font-medium bg-emerald-500/15 text-emerald-500 border border-emerald-500/30 shrink-0">
              ACTIVE
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
