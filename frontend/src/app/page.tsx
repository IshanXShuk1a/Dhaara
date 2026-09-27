"use client";

import { useIntersections } from "@/lib/intersectionContext";
import { useIntersectionSocket } from "@/lib/useIntersectionSocket";
import { MultiLaneQuadView } from "@/components/dashboard/MultiLaneQuadView";
import { TrafficStatusDonut } from "@/components/charts/TrafficStatusDonut";
import { HourlyVolumeBar } from "@/components/charts/HourlyVolumeBar";
import { GlowingActivityChart } from "@/components/charts/GlowingActivityChart";
import { RightControlPanel } from "@/components/dashboard/RightControlPanel";
import { SignalCard } from "@/components/dashboard/SignalCard";
import { DecisionCard } from "@/components/dashboard/DecisionCard";
import { EventTimeline } from "@/components/dashboard/EventTimeline";

export default function DashboardPage() {
  const { selectedId, isLoading, error } = useIntersections();
  const { payload, status } = useIntersectionSocket(selectedId);

  if (isLoading) {
    return <div className="text-sm text-text-muted p-6">Loading intersections...</div>;
  }
  if (error) {
    return <div className="text-sm text-status-congested p-6">Could not load intersections: {error}</div>;
  }
  if (!selectedId) {
    return <div className="text-sm text-text-muted p-6">No intersections configured yet. Add one from the Intersections page.</div>;
  }

  return (
    <div className="space-y-5">
      {status === "DISCONNECTED" && (
        <div className="text-xs text-status-congested bg-status-congested/10 border border-status-congested/30 rounded-2xl px-4 py-2.5">
          Lost connection to the backend - retrying automatically. Values below may be stale.
        </div>
      )}

      {/* Main Grid: 2 Columns matching the mockup's Center Canvas + Right Messages/Mentors Panel */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        {/* CENTER MAIN COLUMN (Width 8.5 / 12 on XL) */}
        <div className="xl:col-span-8 space-y-5">
          {/* Row 1: 4 Approach CCTV Screens (My Courses layout with video, density, and allotment) */}
          <div>
            <MultiLaneQuadView intersectionId={selectedId} payload={payload} wsStatus={status} />
          </div>

          {/* Row 2: Two Stat Cards matching Course Statistics (Donut) & Study Hours (Bar) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <TrafficStatusDonut payload={payload} />
            <HourlyVolumeBar payload={payload} />
          </div>

          {/* Row 3: Glowing Neon Area Chart matching Activity from mockup */}
          <div>
            <GlowingActivityChart payload={payload} />
          </div>

          {/* Row 4: Signal Hardware State Machine & AI Decision Explanation */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SignalCard payload={payload} />
            <DecisionCard payload={payload} />
          </div>

          {/* Row 5: Event Timeline Audit Log */}
          <div>
            <EventTimeline intersectionId={selectedId} />
          </div>
        </div>

        {/* RIGHT COLUMN (Width 3.5 / 12 on XL) matching Messages & Mentors panel */}
        <div className="xl:col-span-4">
          <div className="sticky top-20">
            <RightControlPanel payload={payload} />
          </div>
        </div>
      </div>
    </div>
  );
}
