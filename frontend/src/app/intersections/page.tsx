"use client";

import clsx from "clsx";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useIntersections } from "@/lib/intersectionContext";

const STATUS_COLORS: Record<string, string> = {
  ONLINE: "bg-status-online text-status-online border-status-online/30",
  OFFLINE: "bg-status-offline text-status-offline border-status-offline/30",
  HIGH_TRAFFIC: "bg-status-moderate text-status-moderate border-status-moderate/30",
  EMERGENCY: "bg-status-emergency text-status-emergency border-status-emergency/30",
};

export default function IntersectionsPage() {
  const router = useRouter();
  const { intersections, selectedId, setSelectedId, isLoading, error, refresh } = useIntersections();

  function handleSelectAndOpen(id: string) {
    setSelectedId(id);
    router.push("/");
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xl font-bold text-text-primary">Regional Traffic Grid Intersections</div>
          <div className="text-xs text-text-muted mt-1">
            DHAARA regional coordinator aggregates decentralized intersection nodes across the city network.
          </div>
        </div>
        <button
          onClick={refresh}
          className="text-xs px-3 py-1.5 rounded-lg border border-surface-border text-text-secondary hover:bg-surface-card transition-colors"
        >
          Refresh Grid
        </button>
      </div>

      {isLoading && <div className="text-sm text-text-muted">Loading network intersections...</div>}
      {error && <div className="text-sm text-status-congested p-3 rounded-lg bg-status-congested/10 border border-status-congested/30">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {intersections.map((intersection) => {
          const isSelected = intersection.id === selectedId;
          const statusStyle = STATUS_COLORS[intersection.status] ?? "bg-surface-border text-text-secondary border-surface-border";

          return (
            <div
              key={intersection.id}
              className={clsx(
                "card p-5 transition-all flex flex-col justify-between",
                isSelected ? "ring-2 ring-accent border-accent/40 bg-accent/5" : "hover:border-accent/40"
              )}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-base font-bold text-text-primary">{intersection.id}</span>
                    {isSelected && (
                      <span className="text-[10px] uppercase font-bold text-accent bg-accent/15 px-1.5 py-0.5 rounded">
                        Active Selection
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-md border bg-surface-card">
                    <span className={clsx("status-dot", statusStyle.split(" ")[0])} />
                    <span className={statusStyle.split(" ")[1]}>{intersection.status.replace("_", " ")}</span>
                  </div>
                </div>

                <div className="text-sm font-medium text-text-secondary">{intersection.name}</div>
                <div className="text-xs text-text-muted mt-0.5">{intersection.location}</div>

                <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-surface-border text-xs">
                  <div>
                    <div className="text-text-muted text-[11px]">Approaches</div>
                    <div className="text-text-primary font-medium mt-0.5">4 (N, S, E, W)</div>
                  </div>
                  <div>
                    <div className="text-text-muted text-[11px]">Control Mode</div>
                    <div className="text-text-primary font-medium mt-0.5">ADAPTIVE</div>
                  </div>
                  <div>
                    <div className="text-text-muted text-[11px]">Camera Source</div>
                    <div className="text-text-primary font-medium mt-0.5">LIVE INGESTION</div>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 mt-5 pt-3 border-t border-surface-border">
                <button
                  onClick={() => setSelectedId(intersection.id)}
                  className={clsx(
                    "text-xs px-3 py-1.5 rounded-lg border transition-colors flex-1 text-center font-medium",
                    isSelected
                      ? "border-accent text-accent bg-accent/10"
                      : "border-surface-border text-text-secondary hover:bg-surface-card hover:text-text-primary"
                  )}
                >
                  {isSelected ? "Currently Selected" : "Select Node"}
                </button>
                <button
                  onClick={() => handleSelectAndOpen(intersection.id)}
                  className="text-xs px-3.5 py-1.5 rounded-lg bg-accent text-white font-medium hover:bg-accent/90 transition-colors flex items-center gap-1"
                >
                  <span>Open Live Dashboard</span>
                  <span>&rarr;</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <div className="card p-4 bg-surface-card flex items-center justify-between text-xs">
        <div className="text-text-muted">
          Showing <span className="font-semibold text-text-primary">{intersections.length}</span> synchronized regional intersection nodes.
        </div>
        <Link href="/" className="text-accent hover:underline font-medium">
          Return to Live Dashboard &rarr;
        </Link>
      </div>
    </div>
  );
}
