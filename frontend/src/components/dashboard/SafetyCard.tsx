"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SafetySummary } from "@/lib/types";

interface Props {
  intersectionId: string | null;
}

export function SafetyCard({ intersectionId }: Props) {
  const [summary, setSummary] = useState<SafetySummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!intersectionId) return;
    let cancelled = false;
    function poll() {
      api
        .getSafety(intersectionId!)
        .then((s) => {
          if (!cancelled) {
            setSummary(s);
            setError(null);
          }
        })
        .catch((err) => {
          if (!cancelled) setError(err.message);
        });
    }
    poll();
    const interval = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [intersectionId]);

  return (
    <div className="card p-4">
      <div className="text-sm font-semibold text-text-primary mb-3">ROAD SAFETY</div>

      {error ? (
        <div className="text-xs text-status-congested">{error}</div>
      ) : !summary ? (
        <div className="text-xs text-text-muted">Loading...</div>
      ) : (
        <>
          <div className="text-2xl font-semibold text-text-primary tabular-nums">
            {summary.compliance_rate == null ? "N/A" : `${Math.round(summary.compliance_rate * 100)}%`}
          </div>
          <div className="text-xs text-text-muted mb-3">Helmet compliance</div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <div className="text-text-muted">Compliant</div>
              <div className="text-text-primary font-medium">{summary.compliant_count}</div>
            </div>
            <div>
              <div className="text-text-muted">Violations</div>
              <div className="text-status-congested font-medium">{summary.violation_count}</div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
