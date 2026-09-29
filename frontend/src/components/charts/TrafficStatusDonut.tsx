"use client";

import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import clsx from "clsx";
import type { IntersectionWsPayload } from "@/lib/types";
import { useTheme } from "@/lib/theme";

interface Props {
  payload: IntersectionWsPayload | null;
}

export function TrafficStatusDonut({ payload }: Props) {
  const { isDark } = useTheme();
  const lanes = payload?.lanes ?? {};
  const laneList = Object.values(lanes);

  // Group by status
  let congestedCount = 0;
  let moderateCount = 0;
  let freeCount = 0;

  laneList.forEach((l) => {
    if (l.status === "CONGESTED" || l.status === "HIGH") congestedCount += 1;
    else if (l.status === "MODERATE") moderateCount += 1;
    else freeCount += 1;
  });

  const total = laneList.length || 4;
  const data = [
    { name: "Congested", value: congestedCount || 1, color: "#EF6262" },
    { name: "Moderate", value: moderateCount || 1, color: "#E8B84A" },
    { name: "Free / Low", value: freeCount || 2, color: "#42D392" },
  ];

  return (
    <div className="card-interactive card p-4 flex flex-col justify-between h-full bg-surface-card relative overflow-hidden group">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs font-bold text-text-primary uppercase tracking-wide flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-accent status-dot" />
          Traffic Density Status
        </div>
        <button className="text-text-muted hover:text-text-primary text-xs btn-tactile p-1">•••</button>
      </div>

      <div className="flex items-center justify-between gap-2 flex-1">
        {/* Legend on left matching mockup */}
        <div className="space-y-2 text-xs">
          <div className="flex items-center gap-2 group/item cursor-pointer">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#EF6262] shadow-sm shadow-[#EF6262]/30 group-hover/item:scale-125 transition-transform" />
            <span className="text-text-secondary text-[11px]">Congested</span>
          </div>
          <div className="flex items-center gap-2 group/item cursor-pointer">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#E8B84A] shadow-sm shadow-[#E8B84A]/30 group-hover/item:scale-125 transition-transform" />
            <span className="text-text-secondary text-[11px]">Moderate</span>
          </div>
          <div className="flex items-center gap-2 group/item cursor-pointer">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#42D392] shadow-sm shadow-[#42D392]/30 group-hover/item:scale-125 transition-transform" />
            <span className="text-text-secondary text-[11px]">Free / Low</span>
          </div>
        </div>

        {/* Circular Donut Ring with rotating ambient aura */}
        <div className="w-28 h-28 relative flex items-center justify-center">
          {/* Subtle rotating radar sweep in background */}
          <div className="absolute inset-2 rounded-full border border-dashed border-white/10 animate-radar pointer-events-none" />

          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                innerRadius={36}
                outerRadius={48}
                paddingAngle={4}
                dataKey="value"
                stroke="none"
                animationDuration={800}
                animationEasing="ease-out"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
