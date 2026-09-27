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
      <div className="absolute -top-12 -right-12 w-40 h-40 rounded-full bg-accent/10 blur-3xl pointer-events-none" />

      <div className="flex items-center justify-between mb-2 relative z-10">
        <div className="text-xs font-bold text-text-primary uppercase tracking-wide flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
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
              {/* Horizontal gradient matching the mockup's vibrant neon red-to-blue glow */}
              <linearGradient id="neonActivityFill" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#ff2a70" stopOpacity={0.9} />
                <stop offset="35%" stopColor="#f43f5e" stopOpacity={0.85} />
                <stop offset="65%" stopColor="#a855f7" stopOpacity={0.8} />
                <stop offset="100%" stopColor="#06b6d4" stopOpacity={0.9} />
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
                background: isDark ? "#1b1e24" : "#ffffff",
                border: isDark ? "1px solid #292d36" : "1px solid #e2e8f0",
                borderRadius: 8,
                fontSize: 11,
                boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.1)",
              }}
              labelStyle={{ color: isDark ? "#ffffff" : "#0f172a" }}
              itemStyle={{ color: isDark ? "#ffffff" : "#0f172a" }}
              formatter={(val: number) => [`${val.toFixed(1)}%`, "Traffic Pressure"]}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#ffffff"
              strokeWidth={2.5}
              fill="url(#neonActivityFill)"
              className="glow-neon"
              isAnimationActive={true}
              animationDuration={1500}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
