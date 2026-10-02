"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { useIntersections } from "@/lib/intersectionContext";
import { useIntersectionSocket } from "@/lib/useIntersectionSocket";
import { InterfaceIcon } from "./InterfaceIcon";

export function TopBar() {
  const pathname = usePathname();
  const simulation = pathname === "/simulation";
  const { role, username } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const { intersections, selectedId, setSelectedId, isLoading } = useIntersections();
  const { payload, status } = useIntersectionSocket(simulation ? null : selectedId);
  const available = payload?.cameras ? Object.values(payload.cameras).filter(c => c.status === "ONLINE").length : 0;
  const connected = status === "CONNECTED";
  const label = !selectedId ? "No intersection" : !connected ? status === "CONNECTING" ? "Connecting" : status === "STALE" ? "Data delayed" : "Disconnected" : payload?.is_simulated ? "Simulation data" : available ? `${available}/4 cameras online` : "No camera data";

  return (
    <header className="app-topbar flex h-[60px] shrink-0 items-center justify-between gap-3 border-b border-surface-border px-3 md:px-4">
      <div className="flex min-w-0 items-center gap-3">
        {simulation ? <div className="min-w-0"><div className="text-sm font-semibold text-text-primary">Simulation lab</div><div className="hidden text-[11px] text-text-secondary sm:block">Explore traffic at a four-way intersection</div></div>
          : <label className="min-w-0"><span className="sr-only">Intersection</span><select aria-label="Intersection" value={selectedId ?? ""} disabled={isLoading || !intersections.length} onChange={e => setSelectedId(e.target.value)} className="max-w-[45vw] rounded-lg border border-surface-border bg-surface-card px-2.5 py-2 text-xs font-medium text-text-primary sm:max-w-[300px] md:max-w-[340px] disabled:opacity-60">
            {!intersections.length && <option value="">{isLoading ? "Loading intersections" : "No intersections"}</option>}
            {intersections.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
          </select></label>}
        {!simulation && <span className="hidden items-center gap-1.5 text-[11px] text-text-secondary lg:flex"><span className={`h-1.5 w-1.5 rounded-full ${connected && available ? "bg-status-online" : "bg-status-offline"}`} aria-hidden="true" />{label}</span>}
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <button onClick={toggleTheme} aria-label={`Switch to ${isDark ? "light" : "dark"} theme`} title={`Switch to ${isDark ? "light" : "dark"} theme`} className="flex h-8 w-8 items-center justify-center rounded-lg border border-surface-border bg-surface-card text-text-secondary hover:bg-surface-elevated hover:text-text-primary"><InterfaceIcon name={isDark ? "sun" : "moon"} className="h-4 w-4" /></button>
        <div className="hidden items-center gap-2.5 border-l border-surface-border pl-3 sm:flex">
          <div aria-hidden="true" className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/10 text-[11px] font-bold text-accent">{(username ?? "U").slice(0, 2).toUpperCase()}</div>
          <div className="hidden max-w-[110px] md:block"><div className="truncate text-xs font-medium text-text-primary">{username ?? "User"}</div><div className="text-[9px] uppercase tracking-wider text-text-secondary">{role?.replace(/_/g, " ") ?? ""}</div></div>
        </div>
      </div>
    </header>
  );
}
