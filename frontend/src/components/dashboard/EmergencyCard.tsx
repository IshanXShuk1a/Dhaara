import clsx from "clsx";
import type { IntersectionWsPayload } from "@/lib/types";

interface Props {
  payload: IntersectionWsPayload | null;
}

export function EmergencyCard({ payload }: Props) {
  const emergency = payload?.emergency;
  const isActive = emergency && emergency.state !== "NONE";

  return (
    <div className={clsx("card p-4", isActive && "border-status-emergency/50")}>
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-text-primary">EMERGENCY</div>
        {isActive && (
          <span className="text-[10px] font-semibold text-status-emergency bg-status-emergency/15 px-1.5 py-0.5 rounded animate-pulse">
            {emergency!.state}
          </span>
        )}
      </div>

      {!isActive ? (
        <div className="text-xs text-text-muted">
          No active emergency. Priority: <span className="text-text-secondary">STANDBY</span>
        </div>
      ) : (
        <div className="space-y-1.5 text-xs">
          <Row label="Direction" value={emergency!.direction ?? "N/A"} />
          <Row label="State" value={emergency!.state} />
          <Row
            label="Priority"
            value={emergency!.state === "PRIORITY_ACTIVE" ? "ACTIVE" : emergency!.state === "PRIORITY_REQUESTED" ? "REQUESTED" : "PENDING"}
          />
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-text-muted">{label}</span>
      <span className="text-text-primary font-medium">{value}</span>
    </div>
  );
}
