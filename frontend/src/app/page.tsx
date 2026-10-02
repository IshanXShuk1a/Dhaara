"use client";
import Link from "next/link";
import { useIntersections } from "@/lib/intersectionContext";
import { useIntersectionSocket } from "@/lib/useIntersectionSocket";
import { MultiLaneQuadView } from "@/components/dashboard/MultiLaneQuadView";
import { SignalCard } from "@/components/dashboard/SignalCard";
import { DecisionCard } from "@/components/dashboard/DecisionCard";
import { ScoreRecords } from "@/components/dashboard/ScoreRecords";

export default function DashboardPage() {
  const { selectedId, isLoading, error } = useIntersections();
  const { payload, status } = useIntersectionSocket(selectedId);
  if (isLoading) return <div className="text-sm text-text-muted p-6">Loading intersections...</div>;
  if (error) return <div className="text-sm text-status-congested p-6">Could not load intersections: {error}</div>;
  if (!selectedId) return <div className="text-sm text-text-muted p-6">No intersection configured.</div>;
  const current = payload?.intersection_id === selectedId ? payload : null;
  const measured = current?.is_simulated ? null : current;
  const online = measured?.cameras ? Object.values(measured.cameras).filter(camera => camera.status === "ONLINE").length : null;
  return <div className="space-y-4">
    <div className="flex flex-wrap justify-between items-center gap-2">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-text-primary">Intersection overview</h1>
        <p className="mt-0.5 text-xs text-text-muted">Four camera feeds · East / West and North / South control</p>
      </div>
      <div className="flex items-center gap-2 rounded-full border border-surface-border bg-surface-card px-3 py-1.5 text-xs text-text-secondary">
        <span className={`h-1.5 w-1.5 rounded-full ${status === "CONNECTED" && online ? "bg-status-free" : "bg-status-moderate"}`} />
        {online !== null ? `${online} / 4 cameras online` : "Connecting cameras"}
      </div>
    </div>
    {(status === "DISCONNECTED" || status === "STALE") && <div role="status" className="text-xs text-status-moderate border border-status-moderate/30 bg-status-moderate/5 rounded-xl px-3 py-2">
      {status === "STALE" ? "Camera state has stopped updating." : "Backend disconnected."} Displayed values may be stale.
    </div>}
    {current?.is_simulated && <div role="status" className="text-xs text-status-moderate border border-status-moderate/30 rounded-xl px-3 py-2">
      Synthetic inputs are unavailable in the camera dashboard. <Link href="/simulation" className="underline font-semibold">Open the Simulation lab.</Link>
    </div>}
    <div className="grid min-w-0 grid-cols-1 items-start gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
      <MultiLaneQuadView intersectionId={selectedId} payload={current} wsStatus={status} />
      <aside className="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-1" aria-label="Signal control and traffic demand">
        <SignalCard payload={measured} compact />
        <DecisionCard payload={measured} />
      </aside>
    </div>
    <ScoreRecords intersectionId={selectedId} payload={measured} />
  </div>;
}
