"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import type { IntersectionWsPayload, LaneStatus } from "@/lib/types";

const STATUS_COLORS: Record<LaneStatus, string> = {
  FREE: "#22c55e",
  LOW: "#84cc16",
  MODERATE: "#eab308",
  HIGH: "#f97316",
  CONGESTED: "#ef4444",
};

interface Props {
  payload: IntersectionWsPayload | null;
}

export function PressureChart({ payload }: Props) {
  const lanes = payload?.lanes ?? {};
  const data = Object.entries(lanes).map(([direction, metrics]) => ({
    direction,
    pressure: metrics.traffic_pressure,
    status: metrics.status,
  }));

  return (
    <div className="card p-4">
      <div className="text-sm font-semibold text-text-primary mb-3">TRAFFIC PRESSURE BY DIRECTION</div>
      {data.length === 0 ? (
        <div className="text-xs text-text-muted h-48 flex items-center justify-center">No data yet</div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <XAxis dataKey="direction" stroke="#6b7280" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis domain={[0, 100]} stroke="#6b7280" fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ background: "#15181d", border: "1px solid #23262c", borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: "#e5e7eb" }}
            />
            <Bar dataKey="pressure" radius={[4, 4, 0, 0]}>
              {data.map((entry, index) => (
                <Cell key={index} fill={STATUS_COLORS[entry.status]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
