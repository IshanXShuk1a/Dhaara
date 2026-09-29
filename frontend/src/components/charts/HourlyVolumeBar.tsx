"use client";

import { BarChart, Bar, XAxis, ResponsiveContainer, Cell } from "recharts";
import type { IntersectionWsPayload } from "@/lib/types";
import { AnimatedNumber } from "@/components/ui/AnimatedNumber";
import { useTheme } from "@/lib/theme";

interface Props {
  payload: IntersectionWsPayload | null;
}

const DAYS_DATA = [
  { day: "S", volume: 38 },
  { day: "M", volume: 65 },
  { day: "T", volume: 45 },
  { day: "W", volume: 92 },
  { day: "T", volume: 84 },
  { day: "F", volume: 56 },
  { day: "S", volume: 72 },
];

export function HourlyVolumeBar({ payload }: Props) {
  const { isDark } = useTheme();
  const lanes = payload?.lanes ?? {};
  const totalVehicles = Object.values(lanes).reduce((sum, l) => sum + l.vehicle_count, 0);
  const totalDisplay = totalVehicles > 0 ? totalVehicles * 128 : 3211;

  return (
    <div className="card-interactive card p-4 flex flex-col justify-between h-full bg-surface-card relative overflow-hidden group">
      <div className="flex items-center justify-between mb-1">
        <div className="text-xs font-bold text-text-primary uppercase tracking-wide flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-accent status-dot" />
          Intersection Flow
        </div>
        <div className="text-right">
          <div className="text-[11px] font-bold text-text-primary font-mono flex items-center gap-1">
            <AnimatedNumber value={totalDisplay} decimals={0} suffix=" veh" className="text-accent font-extrabold" />
          </div>
          <div className="text-[9px] text-text-muted">Total Volume</div>
        </div>
      </div>

      <div className="h-28 w-full mt-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={DAYS_DATA} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="day"
              stroke="#6b7280"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              dy={4}
            />
            <Bar dataKey="volume" radius={[4, 4, 0, 0]} animationDuration={800} animationEasing="ease-out">
              {DAYS_DATA.map((entry, index) => (
                <Cell
                  key={`bar-${index}`}
                  fill={index === 3 || index === 4 ? "#37D6B0" : (isDark ? "rgba(255, 255, 255, 0.14)" : "rgba(0, 0, 0, 0.15)")}
                  className="hover:opacity-80 transition-opacity cursor-pointer"
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
