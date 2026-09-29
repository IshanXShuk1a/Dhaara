"use client";

import { useState } from "react";
import clsx from "clsx";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { useIntersections } from "@/lib/intersectionContext";
import { useIntersectionSocket } from "@/lib/useIntersectionSocket";

export function TopBar() {
  const { role, username } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const { intersections, selectedId, setSelectedId } = useIntersections();
  const { payload, status } = useIntersectionSocket(selectedId);
  const [searchQuery, setSearchQuery] = useState("");

  const isSimulated = payload?.is_simulated;
  const liveLabel = status !== "CONNECTED" ? status : isSimulated ? "SIMULATION" : "LIVE";
  const liveColor =
    status !== "CONNECTED"
      ? "bg-status-offline"
      : isSimulated
      ? "bg-status-moderate"
      : "bg-status-online";

  return (
    <header className="h-16 px-6 border-b border-surface-border bg-surface-panel flex items-center justify-between gap-4 sticky top-0 z-20 select-none transition-colors duration-300">
      {/* Search Bar matching the mockup's pill search input */}
      <div className="flex-1 max-w-md">
        <div className="glass-pill flex items-center gap-2.5 px-4 py-2 text-xs text-text-muted transition-all focus-within:border-accent/40 focus-within:ring-1 focus-within:ring-accent/20">
          <svg className="w-3.5 h-3.5 text-text-muted shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search intersections, cameras, violations..."
            className="w-full bg-transparent text-xs text-text-primary placeholder:text-text-muted focus:outline-none"
          />
        </div>
      </div>

      {/* Middle/Center: Intersection & Live Mode Selectors */}
      <div className="flex items-center gap-3">
        <div className="glass-pill flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary">
          <span className="text-[10px] uppercase font-bold text-text-muted">Node</span>
          <select
            value={selectedId ?? ""}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSelectedId(e.target.value)}
            className="bg-transparent text-xs text-text-primary font-medium focus:outline-none cursor-pointer"
          >
            {intersections.map((i) => (
              <option key={i.id} value={i.id} className="bg-surface-card text-text-primary">
                {i.name}
              </option>
            ))}
          </select>
        </div>

        <div className="glass-pill flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-text-primary">
          <span className={clsx("status-dot", liveColor)} />
          <span className="text-[11px]">{payload?.signal_mode ?? "ADAPTIVE"}</span>
        </div>

        {payload?.emergency && payload.emergency.state !== "NONE" && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold bg-status-emergency/15 text-status-emergency border border-status-emergency/30">
            <span>PRIORITY ACTIVE</span>
          </div>
        )}
      </div>

      {/* Right Controls: Notification Bell, Toggle Switch, and Operator Profile */}
      <div className="flex items-center gap-4">
        {/* Notification Bell with unread badge */}
        <button
          title="Notifications & Alerts"
          className="btn-tactile relative p-2 rounded-xl text-text-secondary hover:text-text-primary hover:bg-surface-card transition-all"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          <span className="absolute top-1.5 right-1.5 w-2 h-2">
            <span className="w-2 h-2 rounded-full bg-status-emergency status-dot ring-2 ring-surface-panel" />
          </span>
        </button>

        {/* Dark/Light mode toggle switch */}
        <button
          onClick={toggleTheme}
          title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
          className={clsx(
            "btn-tactile w-12 h-6 rounded-full border p-0.5 flex items-center transition-all duration-300 cursor-pointer shadow-inner",
            isDark ? "bg-surface-pill border-surface-border" : "bg-sky-100 border-sky-300"
          )}
        >
          <div
            className={clsx(
              "w-5 h-5 rounded-full transition-transform duration-300 shadow-md flex items-center justify-center text-[10px]",
              isDark ? "translate-x-6 bg-slate-900 text-amber-300" : "translate-x-0 bg-amber-400 text-white"
            )}
          >
            {isDark ? "🌙" : "☀️"}
          </div>
        </button>

        {/* Separator */}
        <div className="h-6 w-px bg-surface-border" />

        {/* Operator Profile Pill matching mockup avatar and name */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-accent to-status-info p-[1.5px] shadow-sm">
            <div className="w-full h-full rounded-[10px] bg-surface-card flex items-center justify-center text-xs font-bold text-text-primary">
              {username ? username.charAt(0).toUpperCase() : "A"}
            </div>
          </div>
          <div className="text-left hidden sm:block">
            <div className="text-xs font-semibold text-text-primary leading-tight">
              {username || "Admin Controller"}
            </div>
            <div className="text-[10px] text-text-muted capitalize">{role || "Operator"}</div>
          </div>
        </div>
      </div>
    </header>
  );
}
