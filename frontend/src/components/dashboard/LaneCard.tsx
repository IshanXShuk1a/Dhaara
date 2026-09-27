import clsx from "clsx";
import type { LaneStatus } from "@/lib/types";

const STATUS_STYLES: Record<LaneStatus, string> = {
  FREE: "text-status-free border-status-free/40 bg-status-free/10",
  LOW: "text-status-low border-status-low/40 bg-status-low/10",
  MODERATE: "text-status-moderate border-status-moderate/40 bg-status-moderate/10",
  HIGH: "text-status-high border-status-high/40 bg-status-high/10",
  CONGESTED: "text-status-congested border-status-congested/40 bg-status-congested/10",
};

interface Props {
  direction: string;
  vehicleCount: number;
  occupancy: number;
  queueLengthM: number;
  averageSpeedKmph: number;
  averageWaitingTimeS: number;
  trafficPressure: number;
  status: LaneStatus;
  isActiveSignal?: boolean;
}

export function LaneCard(props: Props) {
  const { direction, vehicleCount, occupancy, queueLengthM, averageSpeedKmph, averageWaitingTimeS, trafficPressure, status, isActiveSignal } = props;

  return (
    <div className={clsx("card p-4 relative", isActiveSignal && "ring-1 ring-accent")}>
      {isActiveSignal && (
        <div className="absolute top-3 right-3 text-[10px] font-semibold text-accent bg-accent/15 px-1.5 py-0.5 rounded">
          GREEN NOW
        </div>
      )}
      <div className="text-sm font-semibold text-text-primary">{direction}</div>
      <div className={clsx("inline-block mt-1 text-xs font-semibold px-2 py-0.5 rounded-md border", STATUS_STYLES[status])}>
        {status}
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 mt-3 text-xs">
        <Metric label="Vehicles" value={String(vehicleCount)} />
        <Metric label="Occupancy" value={`${Math.round(occupancy * 100)}%`} />
        <Metric label="Queue" value={`${queueLengthM.toFixed(0)}m`} />
        <Metric label="Speed" value={`${averageSpeedKmph.toFixed(0)} km/h`} />
        <Metric label="Waiting" value={`${averageWaitingTimeS.toFixed(0)}s`} />
        <Metric label="Pressure" value={trafficPressure.toFixed(0)} />
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-text-secondary">
      <span className="text-text-muted">{label}</span>
      <span className="font-medium text-text-primary tabular-nums">{value}</span>
    </div>
  );
}
