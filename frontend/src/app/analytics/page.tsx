"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, Legend } from "recharts";
import { useIntersections } from "@/lib/intersectionContext";
import { api } from "@/lib/api";
import { KpiCard } from "@/components/dashboard/KpiCard";

interface AnalyticsData {
  intersection_id: string;
  volume: Array<{ lane_id: string; timestamp: string; vehicle_count: number }>;
  average_pressure_by_lane: Record<string, number | null>;
  signal_distribution: Record<string, number>;
  emergency_events_24h: number;
  helmet_violations_24h: number;
}

interface RegionalData {
  total_snapshots: number;
  total_decisions: number;
  total_emergencies_24h: number;
  total_helmet_violations_24h: number;
  average_network_pressure: number;
  average_network_speed_kmph: number;
}

export default function AnalyticsPage() {
  const { selectedId } = useIntersections();
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [regional, setRegional] = useState<RegionalData | null>(null);
  const [timeRange, setTimeRange] = useState("24h");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getRegionalAnalytics()
      .then((r) => setRegional(r))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    api
      .getAnalytics(selectedId)
      .then((d) => {
        setData(d as AnalyticsData);
        setError(null);
      })
      .catch((err) => setError(err.message));
  }, [selectedId, timeRange]);

  if (!selectedId) return <div className="text-sm text-text-muted">Select an intersection first.</div>;
  if (error) return <div className="text-sm text-status-congested p-4 rounded-lg bg-status-congested/10">{error}</div>;
  if (!data) return <div className="text-sm text-text-muted">Loading analytics telemetry...</div>;

  const pressureData = Object.entries(data.average_pressure_by_lane).map(([lane, avg]: [string, number | null]) => ({
    lane,
    pressure: avg == null ? 0 : Math.round(avg * 10) / 10,
  }));

  const distributionData = Object.entries(data.signal_distribution).map(([lane, count]) => ({ lane, count }));

  // Reshape volume rows (lane_id, timestamp, vehicle_count) into one row per timestamp
  const byTimestamp: Record<string, Record<string, number>> = {};
  for (const row of data.volume) {
    byTimestamp[row.timestamp] = byTimestamp[row.timestamp] || {};
    byTimestamp[row.timestamp][row.lane_id] = row.vehicle_count;
  }
  const volumeSeries = Object.entries(byTimestamp)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([timestamp, lanes]) => ({ timestamp: new Date(timestamp).toLocaleTimeString(), ...lanes }));
  const laneKeys: string[] = Array.from(new Set(data.volume.map((r: { lane_id: string }) => r.lane_id)));
  const laneColors: Record<string, string> = { NORTH: "#3b82f6", SOUTH: "#ef4444", EAST: "#22c55e", WEST: "#eab308" };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="text-xl font-bold text-text-primary">Historical Telemetry &amp; Analytics</div>
          <div className="text-xs text-text-muted mt-0.5">Intersection Node: <span className="font-semibold text-text-primary">{data.intersection_id}</span></div>
        </div>

        {/* Time-range filter */}
        <div className="flex items-center gap-1.5 p-1 rounded-lg bg-surface-card border border-surface-border text-xs">
          {["1h", "6h", "24h", "all"].map((tr) => (
            <button
              key={tr}
              onClick={() => setTimeRange(tr)}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                timeRange === tr ? "bg-accent text-white" : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {tr.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Regional Network KPIs */}
      {regional && (
        <div className="card p-4 bg-surface-card">
          <div className="text-xs font-semibold text-text-secondary mb-2 uppercase tracking-wide">City Network Summary (All Regional Intersections)</div>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            <KpiCard label="Network Avg Pressure" value={`${regional.average_network_pressure}%`} />
            <KpiCard label="Network Avg Speed" value={`${regional.average_network_speed_kmph} km/h`} />
            <KpiCard label="Total Snapshots" value={String(regional.total_snapshots)} />
            <KpiCard label="Total Decisions" value={String(regional.total_decisions)} />
            <KpiCard label="Emergencies (24h)" value={String(regional.total_emergencies_24h)} />
            <KpiCard label="Violations (24h)" value={String(regional.total_helmet_violations_24h)} />
          </div>
        </div>
      )}

      {/* Node-specific KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Node Emergency Events" value={String(data.emergency_events_24h)} />
        <KpiCard label="Node Helmet Violations" value={String(data.helmet_violations_24h)} />
        <KpiCard label="Approaches Tracked" value={String(Object.keys(data.average_pressure_by_lane).length)} />
        <KpiCard label="Node Snapshots Recorded" value={String(data.volume.length)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="text-sm font-semibold text-text-primary mb-3">Traffic Volume by Approach Over Time</div>
          {volumeSeries.length === 0 ? (
            <div className="text-xs text-text-muted h-56 flex items-center justify-center">
              No historical data in this window - snapshots persist automatically every 2.5s.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={volumeSeries}>
                <XAxis dataKey="timestamp" stroke="#6b7280" fontSize={11} />
                <YAxis stroke="#6b7280" fontSize={11} />
                <Tooltip contentStyle={{ background: "#15181d", border: "1px solid #23262c", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {laneKeys.map((lane) => (
                  <Line key={lane} type="monotone" dataKey={lane} stroke={laneColors[lane] ?? "#9aa1ac"} dot={false} strokeWidth={2} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card p-4">
          <div className="text-sm font-semibold text-text-primary mb-3">Average Pressure Score by Lane (0-100)</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={pressureData}>
              <XAxis dataKey="lane" stroke="#6b7280" fontSize={11} />
              <YAxis domain={[0, 100]} stroke="#6b7280" fontSize={11} />
              <Tooltip contentStyle={{ background: "#15181d", border: "1px solid #23262c", fontSize: 12 }} />
              <Bar dataKey="pressure" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-4 lg:col-span-2">
          <div className="text-sm font-semibold text-text-primary mb-3">Signal Allocation Distribution (Decisions Won per Lane)</div>
          {distributionData.length === 0 ? (
            <div className="text-xs text-text-muted h-40 flex items-center justify-center">
              No signal decisions recorded yet - running adaptive loop will record decision wins.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={distributionData} layout="vertical">
                <XAxis type="number" stroke="#6b7280" fontSize={11} />
                <YAxis type="category" dataKey="lane" stroke="#6b7280" fontSize={11} width={70} />
                <Tooltip contentStyle={{ background: "#15181d", border: "1px solid #23262c", fontSize: 12 }} />
                <Bar dataKey="count" fill="#10b981" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
