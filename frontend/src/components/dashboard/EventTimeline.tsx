"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { api } from "@/lib/api";
import type { SystemEvent } from "@/lib/types";

interface Props {
  intersectionId: string | null;
}

const SEVERITY_COLORS: Record<string, string> = {
  INFO: "text-text-secondary",
  WARNING: "text-status-moderate",
  ERROR: "text-status-high",
  CRITICAL: "text-status-congested",
};

export function EventTimeline({ intersectionId }: Props) {
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!intersectionId) return;
    let cancelled = false;
    function poll() {
      api
        .listEvents(intersectionId!)
        .then((list) => {
          if (!cancelled) {
            setEvents(list);
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
    <div className="card-interactive card p-4 relative overflow-hidden group">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-bold text-text-primary uppercase tracking-wide flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          SYSTEM AUDIT & EVENT TIMELINE
        </div>
        <span className="text-[10px] text-text-muted font-mono">{events.length} logs</span>
      </div>
      {error && <div className="text-xs text-status-congested mb-2">{error}</div>}
      {events.length === 0 ? (
        <div className="text-xs text-text-muted">No events recorded yet.</div>
      ) : (
        <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
          {events.map((event: SystemEvent, i: number) => (
            <div
              key={i}
              className="text-xs flex items-center gap-2 p-1.5 rounded-lg hover:bg-surface-raised transition-all duration-200"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-surface-border shrink-0" />
              <span className="text-text-muted shrink-0 tabular-nums font-mono text-[10px]">
                {new Date(event.timestamp).toLocaleTimeString()}
              </span>
              <span className={clsx("font-bold text-[11px]", SEVERITY_COLORS[event.severity] ?? "text-text-secondary")}>
                {event.event_type}
              </span>
              <span className="text-text-secondary truncate">{event.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
