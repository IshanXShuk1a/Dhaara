"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { IntersectionWsPayload, ScoreRecord } from "@/lib/types";

export function ScoreRecords({intersectionId, payload}: {intersectionId: string; payload: IntersectionWsPayload | null}) {
  const [saved, setSaved] = useState<ScoreRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    setSaved([]); setError(null);
    api.getScoreHistory(intersectionId).then(result => { if (!cancelled) setSaved(result.records); })
      .catch(err => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [intersectionId]);
  const live = payload?.score_records ?? [];
  const records = [...live, ...saved].filter(r => !r.is_simulated).filter((r, i, all) => all.findIndex(x => x.timestamp === r.timestamp) === i)
    .sort((a, b) => b.timestamp - a.timestamp).slice(0, 6);
  return <section className="card p-4 space-y-3" aria-label="Measured traffic score records">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-sm font-semibold">Measured score records</h2>
      <span className="text-[10px] text-text-muted">Latest six observations · EW / NS averages</span>
    </div>
    <div className="overflow-x-auto">
      <table className="w-full text-[11px] text-left tabular-nums">
        <thead className="text-text-muted"><tr><th className="pb-2 font-medium">Time</th><th className="pb-2 font-medium">East + West</th><th className="pb-2 font-medium">North + South</th><th className="pb-2 font-medium">Denser pair</th><th className="pb-2 font-medium">Signal</th></tr></thead>
        <tbody>{records.map(r => <tr key={r.timestamp} className="border-t border-surface-border text-text-secondary">
          <td className="py-2">{new Date(r.timestamp * 1000).toLocaleTimeString()}</td><td>{r.pair_scores.EW ?? "—"}</td><td>{r.pair_scores.NS ?? "—"}</td><td>{r.denser_pair ?? "—"}</td><td><span className={r.green_pair ? "text-status-free" : r.yellow_pair ? "text-status-moderate" : "text-text-muted"}>{r.green_pair ? `${r.green_pair} GREEN` : r.yellow_pair ? `${r.yellow_pair} YELLOW` : "—"}</span></td>
        </tr>)}</tbody>
      </table>
    </div>
    {!records.length && <div className="text-xs text-text-muted">{error ?? "No measured score records yet."}</div>}
  </section>;
}
