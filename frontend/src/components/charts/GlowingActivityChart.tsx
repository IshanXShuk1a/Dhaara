"use client";

import { useState } from "react";
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import type { IntersectionWsPayload } from "@/lib/types";
import { useTheme } from "@/lib/theme";

interface Props {
  payload: IntersectionWsPayload | null;
}

export function GlowingActivityChart({ payload }: Props) {
  const { isDark } = useTheme();
  const [range, setRange] = useState("One Week");

  // Derive points from real backend lane metrics
  const lanes = payload?.lanes ?? {};
  const southPressure = lanes["SOUTH"]?.traffic_pressure ?? 86;
  const eastPressure = lanes["EAST"]?.traffic_pressure ?? 52;
  const northPressure = lanes["NORTH"]?.traffic_pressure ?? 20;
  const westPressure = lanes["WEST"]?.traffic_pressure ?? 8;

  const data = [
    { day: "S", value: 30 },
    { day: "M", value: Math.max(25, northPressure * 0.9) },
    { day: "T", value: 45 },
    { day: "W", value: Math.max(60, southPressure) },
    { day: "T", value: Math.max(40, eastPressure) },
    { day: "F", value: 75 },
    { day: "S", value: 20 },
  ];

  return (
    <div className="card-interactive card p-4 bg-surface-card flex flex-col justify-between relative overflow-hidden group">
      {/* Background ambient glow highlight */}
      <div className="absolute -top-12 -right-12 w-40 h-40 rounded-full bg-accent/[0.05] blur-3xl pointer-events-none" />

      <div className="flex items-center justify-between mb-2 relative z-10">
        <div className="text-xs font-bold text-text-primary uppercase tracking-wide flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-accent status-dot" />
          Activity • Real-Time Traffic Pressure
        </div>
        <div className="glass-pill flex items-center gap-1.5 px-2.5 py-1 text-[11px] text-text-secondary cursor-pointer btn-tactile hover:text-text-primary">
          <svg className="w-3 h-3 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{range}</span>
          <span className="text-[9px]">▼</span>
        </div>
      </div>

      <div className="h-44 w-full relative z-10">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
            <defs>
              {/* Vertical telemetry gradient matching the command-center ITS palette */}
              <linearGradient id="commandActivityFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#37D6B0" stopOpacity={0.28} />
                <stop offset="65%" stopColor="#37D6B0" stopOpacity={0.06} />
                <stop offset="100%" stopColor="#070B0D" stopOpacity={0.0} />
              </linearGradient>
            </defs>

            <XAxis
              dataKey="day"
              stroke="#6b7280"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              dy={6}
            />
            <YAxis
              domain={[0, 100]}
              stroke="#4b5563"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              ticks={[20, 40, 60, 80, 100]}
            />
            <Tooltip
              contentStyle={{
                background: isDark ? "#0D1517" : "#ffffff",
                border: isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid #e2e8f0",
                borderRadius: 8,
                fontSize: 11,
                boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.4)",
              }}
              labelStyle={{ color: isDark ? "#ffffff" : "#0f172a" }}
              itemStyle={{ color: "#37D6B0" }}
              formatter={(val: number) => [`${val.toFixed(1)}%`, "Traffic Pressure"]}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#37D6B0"
              strokeWidth={2}
              fill="url(#commandActivityFill)"
              isAnimationActive={true}
              animationDuration={800}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
