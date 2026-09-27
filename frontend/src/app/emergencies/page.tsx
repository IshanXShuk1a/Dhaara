"use client";

import { useEffect, useState } from "react";
import { useIntersections } from "@/lib/intersectionContext";
import { useIntersectionSocket } from "@/lib/useIntersectionSocket";
import { api } from "@/lib/api";
import { EmergencyCard } from "@/components/dashboard/EmergencyCard";

interface EmergencyRow {
  intersection_id: string;
  ambulance_track_id: number;
  lane_id: string;
  direction: string | null;
  confidence: number;
  state: string;
  created_at: string;
}

export default function EmergenciesPage() {
  const { selectedId } = useIntersections();
  const { payload } = useIntersectionSocket(selectedId);
  const [rows, setRows] = useState<EmergencyRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function poll() {
      api
        .listAllEmergencies()
        .then((data) => {
          setRows(data as unknown as EmergencyRow[]);
          setError(null);
        })
        .catch((err) => setError(err.message));
    }
    poll();
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      <div className="text-lg font-semibold text-text-primary">Emergencies</div>

      <div className="max-w-sm">
        <EmergencyCard payload={payload} />
      </div>

      <div className="card p-4">
        <div className="text-sm font-semibold text-text-primary mb-3">Recent emergency events (all intersections)</div>
        {error && <div className="text-xs text-status-congested">{error}</div>}
        {rows.length === 0 ? (
          <div className="text-xs text-text-muted">No emergency events recorded yet.</div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted text-left border-b border-surface-border">
                <th className="py-2 pr-3">Time</th>
                <th className="py-2 pr-3">Intersection</th>
                <th className="py-2 pr-3">Direction</th>
                <th className="py-2 pr-3">State</th>
                <th className="py-2 pr-3">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row: EmergencyRow, i: number) => (
                <tr key={i} className="border-b border-surface-border text-text-secondary">
                  <td className="py-2 pr-3">{new Date(row.created_at).toLocaleString()}</td>
                  <td className="py-2 pr-3 text-text-primary">{row.intersection_id}</td>
                  <td className="py-2 pr-3">{row.direction ?? "N/A"}</td>
                  <td className="py-2 pr-3">{row.state}</td>
                  <td className="py-2 pr-3">{Math.round(row.confidence * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
