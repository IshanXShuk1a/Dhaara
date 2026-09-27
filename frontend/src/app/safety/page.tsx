"use client";

import { useEffect, useState } from "react";
import { useIntersections } from "@/lib/intersectionContext";
import { api } from "@/lib/api";
import { SafetyCard } from "@/components/dashboard/SafetyCard";

interface SafetyRow {
  intersection_id: string;
  event_type: string;
  lane_id: string;
  track_id: number;
  confidence: number;
  created_at: string;
}

export default function SafetyPage() {
  const { selectedId } = useIntersections();
  const [rows, setRows] = useState<SafetyRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function poll() {
      api
        .listAllSafetyEvents()
        .then((data) => {
          setRows(data as unknown as SafetyRow[]);
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
      <div className="text-lg font-semibold text-text-primary">Road Safety</div>

      <div className="max-w-sm">
        <SafetyCard intersectionId={selectedId} />
      </div>

      <div className="card p-4">
        <div className="text-sm font-semibold text-text-primary mb-3">Helmet violation events (all intersections)</div>
        {error && <div className="text-xs text-status-congested">{error}</div>}
        {rows.length === 0 ? (
          <div className="text-xs text-text-muted">No violations recorded yet.</div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted text-left border-b border-surface-border">
                <th className="py-2 pr-3">Time</th>
                <th className="py-2 pr-3">Intersection</th>
                <th className="py-2 pr-3">Lane</th>
                <th className="py-2 pr-3">Track ID</th>
                <th className="py-2 pr-3">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row: SafetyRow, i: number) => (
                <tr key={i} className="border-b border-surface-border text-text-secondary">
                  <td className="py-2 pr-3">{new Date(row.created_at).toLocaleString()}</td>
                  <td className="py-2 pr-3 text-text-primary">{row.intersection_id}</td>
                  <td className="py-2 pr-3">{row.lane_id}</td>
                  <td className="py-2 pr-3">#{row.track_id}</td>
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
